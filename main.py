# -*- coding: utf-8 -*-
"""QuickScan Invoices - FastAPI 后端"""

import json
import os
import uuid
import io
import asyncio
import tempfile
import traceback
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, HTMLResponse
from PIL import Image
import fitz
import numpy as np

from ocr_engine import InvoiceImageProcessor, pdf_first_page_to_image
from export import export_table_data

import logging
import time
logger = logging.getLogger("quickscan")
logger.setLevel(logging.DEBUG)

app = FastAPI(title="QuickScan Invoices")

# CORS 支持（Tauri dev 模式下跨域请求）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件和模板
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# 全局处理器
invoice_processor = InvoiceImageProcessor()

# 任务状态存储（内存，适合单实例）
tasks: Dict[str, Dict[str, Any]] = {}
TASK_TTL = 300  # 5 minutes

def _cleanup_old_tasks():
    """Remove completed tasks older than TASK_TTL"""
    now = time.time()
    expired = [tid for tid, t in tasks.items()
               if t["status"] in ("done", "error") and now - t.get("created_at", now) > TASK_TTL]
    for tid in expired:
        del tasks[tid]


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """返回前端页面"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/recognize")
async def recognize(
    file: UploadFile = File(...),
    confidence: float = 0.5,
):
    """单文件识别（图片或PDF）"""
    try:
        file_ext = os.path.splitext(file.filename)[1].lower()
        content = await file.read()

        result_data = _process_file_bytes(content, file_ext, confidence)
        result_data["file_name"] = file.filename

        return {
            "status": "success",
            "result": result_data,
            "table_row": [
                result_data["file_name"],
                result_data["extracted_fields"].get("开票日期", "未识别"),
                result_data["extracted_fields"].get("价税合计小写", "未识别"),
            ],
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


@app.post("/api/batch-recognize")
async def batch_recognize(
    files: list[UploadFile] = File(...),
    confidence: float = 0.5,
):
    """批量文件识别，返回 task_id 用于轮询进度"""
    # 在请求结束前先把文件内容全部读入内存
    file_data = []
    for f in files:
        content = await f.read()
        file_data.append({"filename": f.filename, "content": content})

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "total": len(file_data),
        "results": [],
        "table_data": [],
        "created_at": time.time(),
        "error": None,
    }

    asyncio.create_task(_run_batch(task_id, file_data, confidence))

    return {"task_id": task_id, "total": len(file_data)}


def _process_file_bytes(content: bytes, file_ext: str, confidence: float) -> Dict[str, Any]:
    """从文件字节数据中提取结构化信息"""
    import sys
    print(f"  >>> _process_file_bytes called: ext={file_ext}, size={len(content)}, python={sys.executable}", flush=True)
    if file_ext == ".pdf":
        tmp_path = os.path.join(tempfile.gettempdir(), f"invoice_{uuid.uuid4().hex}.pdf")
        print(f"  >>> Writing temp PDF: {tmp_path}", flush=True)
        with open(tmp_path, "wb") as f:
            f.write(content)
        print(f"  >>> Temp file written: {os.path.getsize(tmp_path)} bytes", flush=True)
        try:
            result_data, _, _ = _process_pdf_file(tmp_path, confidence)
            result_data["source_type"] = "PDF"
            result_data["processed_page"] = 1
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            print(f"  >>> Temp file cleaned", flush=True)
    elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
        ext_map = {".jpg": ".jpg", ".jpeg": ".jpg", ".png": ".png", ".bmp": ".bmp", ".tiff": ".tiff", ".tif": ".tif"}
        suffix = ext_map.get(file_ext, ".jpg")
        tmp_path = os.path.join(tempfile.gettempdir(), f"invoice_{uuid.uuid4().hex}{suffix}")
        with open(tmp_path, "wb") as f:
            f.write(content)
        try:
            result_data, _, _ = _process_image_file(tmp_path, confidence)
            result_data["source_type"] = "Image"
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    else:
        raise ValueError(f"不支持的格式: {file_ext}")

    return result_data


def _process_pdf_file(pdf_path: str, confidence: float):
    """处理 PDF 文件"""
    doc = fitz.open(pdf_path)
    page = doc.load_page(0)
    pix = page.get_pixmap(dpi=300)
    img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
    doc.close()
    result_data, _, _ = invoice_processor.process_invoice(img_array, confidence)
    return result_data, None, None


def _process_image_file(img_path: str, confidence: float):
    """处理图片文件"""
    img_array = np.array(Image.open(img_path))
    result_data, _, _ = invoice_processor.process_invoice(img_array, confidence)
    return result_data, None, None


async def _run_batch(task_id: str, file_data: list[dict], confidence: float):
    """后台执行批量识别"""
    tasks[task_id]["status"] = "processing"
    print(f"\n>>> _run_batch started, task_id={task_id}, files={len(file_data)}", flush=True)

    for i, fd in enumerate(file_data):
        filename = fd["filename"]
        content = fd["content"]
        file_ext = os.path.splitext(filename)[1].lower()

        print(f"\n>>> Processing [{i+1}/{len(file_data)}]: {filename}", flush=True)
        print(f">>> Content size: {len(content)} bytes, ext: {file_ext}", flush=True)

        try:
            result_data = _process_file_bytes(content, file_ext, confidence)
            result_data["file_name"] = filename
            print(f">>> SUCCESS: {result_data.get('extracted_fields')}", flush=True)
            tasks[task_id]["results"].append(result_data)
            tasks[task_id]["table_data"].append([
                filename,
                result_data.get("extracted_fields", {}).get("开票日期", "未识别"),
                result_data.get("extracted_fields", {}).get("价税合计小写", "未识别"),
            ])
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"\n{'='*60}", flush=True)
            print(f"ERROR in batch: {filename}", flush=True)
            print(f"Exception type: {type(e).__name__}", flush=True)
            print(f"Exception message: {e}", flush=True)
            print(f"Full traceback:\n{tb}", flush=True)
            print(f"{'='*60}\n", flush=True)
            tasks[task_id]["results"].append({"error": str(e), "file_name": filename})
            tasks[task_id]["table_data"].append([filename, "处理失败", f"错误: {str(e)}"])

        tasks[task_id]["progress"] = i + 1

    tasks[task_id]["status"] = "done"
    print(f">>> _run_batch finished, task_id={task_id}\n", flush=True)


@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    """轮询获取任务进度和结果"""
    _cleanup_old_tasks()
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    return {
        "status": task["status"],
        "progress": task["progress"],
        "total": task["total"],
        "results": task["results"],
        "table_data": task["table_data"],
        "error": task["error"],
    }


@app.post("/api/export")
async def export(table_data: list[list]):
    """导出Excel文件"""
    if not table_data:
        raise HTTPException(status_code=400, detail="无数据可导出")

    try:
        tmp_path = export_table_data(table_data)
        if tmp_path is None:
            raise HTTPException(status_code=500, detail="导出失败")

        return FileResponse(
            tmp_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=os.path.basename(tmp_path),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")
