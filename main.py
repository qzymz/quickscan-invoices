# -*- coding: utf-8 -*-
"""发票OCR专用识别系统 - FastAPI 后端"""

import json
import os
import uuid
import io
import asyncio
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, HTMLResponse
from PIL import Image

from ocr_engine import InvoiceImageProcessor, pdf_first_page_to_image
from export import export_table_data

app = FastAPI(title="发票OCR识别系统")

# 静态文件和模板
BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# 全局处理器
invoice_processor = InvoiceImageProcessor()

# 任务状态存储（内存，适合单实例）
tasks: Dict[str, Dict[str, Any]] = {}


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

        if file_ext == ".pdf":
            img = pdf_first_page_to_image(io.BytesIO(content))
            result_data, _, _ = invoice_processor.process_invoice(img, confidence)
            result_data["source_type"] = "PDF"
            result_data["file_name"] = file.filename
        elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
            img = Image.open(io.BytesIO(content))
            result_data, _, _ = invoice_processor.process_invoice(img, confidence)
            result_data["source_type"] = "Image"
            result_data["file_name"] = file.filename
        else:
            raise HTTPException(status_code=400, detail=f"不支持的文件格式: {file_ext}")

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"识别失败: {str(e)}")


@app.post("/api/batch-recognize")
async def batch_recognize(
    files: list[UploadFile] = File(...),
    confidence: float = 0.5,
):
    """批量文件识别，返回 task_id 用于轮询进度"""
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "total": len(files),
        "results": [],
        "table_data": [],
        "error": None,
    }

    asyncio.create_task(_run_batch(task_id, files, confidence))

    return {"task_id": task_id, "total": len(files)}


async def _run_batch(task_id: str, files: list[UploadFile], confidence: float):
    """后台执行批量识别"""
    tasks[task_id]["status"] = "processing"

    for i, file in enumerate(files):
        try:
            content = await file.read()
            file_ext = os.path.splitext(file.filename)[1].lower()

            if file_ext == ".pdf":
                img = pdf_first_page_to_image(io.BytesIO(content))
                result_data, _, _ = invoice_processor.process_invoice(img, confidence)
                result_data["source_type"] = "PDF"
                result_data["processed_page"] = 1
            elif file_ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"]:
                img = Image.open(io.BytesIO(content))
                result_data, _, _ = invoice_processor.process_invoice(img, confidence)
                result_data["source_type"] = "Image"
            else:
                result_data = {"error": f"不支持的格式: {file_ext}", "file_name": file.filename}

            result_data["file_name"] = file.filename
            tasks[task_id]["results"].append(result_data)
            tasks[task_id]["table_data"].append([
                file.filename,
                result_data.get("extracted_fields", {}).get("开票日期", "未识别"),
                result_data.get("extracted_fields", {}).get("价税合计小写", "未识别"),
            ])
        except Exception as e:
            tasks[task_id]["results"].append({"error": str(e), "file_name": file.filename})
            tasks[task_id]["table_data"].append([file.filename, "处理失败", f"错误: {str(e)}"])

        tasks[task_id]["progress"] = i + 1

    tasks[task_id]["status"] = "done"


@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    """轮询获取任务进度和结果"""
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
