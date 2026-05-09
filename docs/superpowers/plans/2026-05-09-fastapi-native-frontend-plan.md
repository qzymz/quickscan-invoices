# Remove Gradio / FastAPI + Native Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Gradio UI with FastAPI backend + pure HTML/CSS/JS frontend, remove MCP and gradio dependency.

**Architecture:** FastAPI serves static files (HTML/CSS/JS) and exposes 4 REST APIs for invoice recognition, batch processing with polling progress, and Excel export. Frontend uses vanilla JS with Fetch API.

**Tech Stack:** FastAPI, uvicorn, vanilla HTML/CSS/JS

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `main.py` | Create | FastAPI application with API routes |
| `app.py` | Delete | Replaced by main.py |
| `start.bat` | Modify | Launch via `uvicorn main:app` |
| `requirements.txt` | Modify | Remove gradio, add fastapi+uvicorn |
| `templates/index.html` | Create | Frontend page |
| `static/css/style.css` | Create | Native CSS (from styles.css, remove .gradio-* hacks) |
| `static/js/app.js` | Create | Frontend interaction logic |
| `CLAUDE.md` | Update | Reflect new architecture |

Existing modules (`ocr_engine.py`, `field_extractor.py`, `export.py`, `invoice_config.py`, `tests/`) remain unchanged.

---

### Task 1: Create FastAPI Backend (main.py)

**Files:**
- Create: `main.py`

- [ ] **Step 1: Create main.py with FastAPI application**

```python
# -*- coding: utf-8 -*-
"""发票OCR专用识别系统 - FastAPI 后端"""

import json
import os
import uuid
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, HTMLResponse
from PIL import Image
import pandas as pd

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


def _process_single_image(image: Image.Image, filename: str, confidence: float) -> Dict[str, Any]:
    """处理单张图片，返回结构化数据"""
    result_data, vis_text, table_data = invoice_processor.process_invoice(image, confidence)
    result_data["source_type"] = "Image"
    result_data["file_name"] = filename
    return result_data


def _process_single_pdf(pdf_file, filename: str, confidence: float) -> Dict[str, Any]:
    """处理单个PDF，返回结构化数据"""
    img = pdf_first_page_to_image(pdf_file)
    result_data, vis_text, table_data = invoice_processor.process_invoice(img, confidence)
    result_data["source_type"] = "PDF"
    result_data["processed_page"] = 1
    result_data["file_name"] = filename
    return result_data


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
            import io
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

    # 启动后台任务
    import asyncio
    asyncio.create_task(_run_batch(task_id, files, confidence))

    return {"task_id": task_id, "total": len(files)}


async def _run_batch(task_id: str, files: list[UploadFile], confidence: float):
    """后台执行批量识别"""
    import io

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
```

- [ ] **Step 2: Create templates/ and static/ directories**

Run: `mkdir templates static static/css static/js`

- [ ] **Step 3: Verify main.py parses**

Run: `python -c "import ast; ast.parse(open('main.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Verify FastAPI imports work**

Run: `python -c "from fastapi import FastAPI; print('FastAPI OK')"`
Expected: `FastAPI OK`

---

### Task 2: Create Frontend HTML (templates/index.html)

**Files:**
- Create: `templates/index.html`

- [ ] **Step 1: Create index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>发票OCR识别系统</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <div class="main-container">
        <div class="header-section fade-in-up">
            <h1 class="header-title">🧾 发票OCR识别系统</h1>
            <p class="header-subtitle">基于AI的智能发票识别与字段提取平台</p>
            <div class="header-features">
                <span class="feature-tag">多类型识别</span>
                <span class="feature-tag">批量处理</span>
                <span class="feature-tag">Excel导出</span>
            </div>
        </div>

        <div class="content-section">
            <!-- 左侧上传区 -->
            <div class="input-section fade-in-up">
                <div class="input-title">📄 上传发票文件</div>

                <!-- Tab 切换 -->
                <div class="tab-nav">
                    <button class="tab-btn active" data-tab="pdf">PDF发票</button>
                    <button class="tab-btn" data-tab="image">图片发票</button>
                </div>

                <!-- PDF上传 -->
                <div class="tab-content active" id="tab-pdf">
                    <div class="upload-area" id="pdf-upload">
                        <input type="file" id="pdf-files" accept=".pdf" multiple>
                        <p class="upload-hint">选择多个PDF文件</p>
                    </div>
                    <div class="param-row">
                        <label>置信度阈值</label>
                        <input type="range" id="pdf-confidence" min="0.1" max="1.0" step="0.1" value="0.5">
                        <span id="pdf-confidence-value">0.5</span>
                    </div>
                    <button class="btn-primary" id="btn-pdf-recognize">🚀 开始识别</button>
                </div>

                <!-- 图片上传 -->
                <div class="tab-content" id="tab-image">
                    <div class="upload-area" id="image-upload">
                        <input type="file" id="image-files" accept="image/*">
                        <p class="upload-hint">选择图片文件</p>
                    </div>
                    <div class="param-row">
                        <label>置信度阈值</label>
                        <input type="range" id="image-confidence" min="0.1" max="1.0" step="0.1" value="0.5">
                        <span id="image-confidence-value">0.5</span>
                    </div>
                    <button class="btn-primary" id="btn-image-recognize">🚀 开始识别</button>
                </div>

                <!-- 进度条 -->
                <div class="progress-container" id="progress-container" style="display: none;">
                    <div class="progress-bar" id="progress-bar"></div>
                    <span id="progress-text">处理中...</span>
                </div>
            </div>

            <!-- 右侧结果区 -->
            <div class="output-section fade-in-up">
                <div class="input-title">📊 识别结果</div>

                <!-- 结果表格 -->
                <table class="result-table" id="result-table">
                    <thead>
                        <tr>
                            <th>文件名</th>
                            <th>开票日期</th>
                            <th>价税合计小写</th>
                        </tr>
                    </thead>
                    <tbody id="result-tbody">
                        <tr><td colspan="3" class="empty-msg">请上传发票文件开始识别</td></tr>
                    </tbody>
                </table>

                <!-- 导出按钮 -->
                <button class="btn-primary" id="btn-export" disabled>📥 导出并下载结果</button>

                <!-- 详情标签页 -->
                <div class="detail-tabs">
                    <button class="detail-tab-btn active" data-detail="json">🎯 JSON格式</button>
                    <button class="detail-tab-btn" data-detail="raw">📝 原始文本</button>
                </div>

                <div class="detail-content active" id="detail-json">
                    <pre id="json-output">等待识别结果...</pre>
                </div>
                <div class="detail-content" id="detail-raw">
                    <table class="raw-table" id="raw-table">
                        <thead>
                            <tr>
                                <th>序号</th>
                                <th>文本内容</th>
                                <th>置信度</th>
                            </tr>
                        </thead>
                        <tbody id="raw-tbody">
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <script src="/static/js/app.js"></script>
</body>
</html>
```

---

### Task 3: Create Frontend CSS (static/css/style.css)

**Files:**
- Create: `static/css/style.css`

- [ ] **Step 1: Create style.css**

```css
/* 发票OCR识别系统 - 原生 CSS 样式 */

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.9) 0%, rgba(118, 75, 162, 0.9) 100%);
    margin: 0;
    padding: 0;
    min-height: 100vh;
    background-attachment: fixed;
    color: #333;
}

.main-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
}

/* 头部 */
.header-section {
    text-align: center;
    margin-bottom: 30px;
    padding: 30px;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 20px;
    box-shadow: 0 8px 32px rgba(81, 85, 141, 0.37);
}

.header-title {
    font-size: 3rem;
    font-weight: 700;
    background: linear-gradient(45deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 10px;
}

.header-subtitle {
    font-size: 1.2rem;
    color: #666;
    margin: 0 0 20px;
}

.header-features {
    display: flex;
    justify-content: center;
    gap: 20px;
    flex-wrap: wrap;
}

.feature-tag {
    background: linear-gradient(45deg, #667eea, #764ba2);
    color: white;
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 0.9rem;
    font-weight: 500;
}

/* 主内容两栏布局 */
.content-section {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 30px;
    align-items: stretch;
}

@media (max-width: 768px) {
    .content-section {
        grid-template-columns: 1fr;
    }
    .header-title {
        font-size: 2rem;
    }
}

/* 上传区和结果区 */
.input-section,
.output-section {
    background: rgba(255, 255, 255, 0.95);
    border-radius: 20px;
    padding: 30px;
    box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
    display: flex;
    flex-direction: column;
}

.input-title {
    font-size: 1.5rem;
    font-weight: 600;
    color: #333;
    margin-bottom: 20px;
}

/* Tab 导航 */
.tab-nav {
    display: flex;
    gap: 0;
    margin-bottom: 20px;
    border-radius: 10px;
    overflow: hidden;
}

.tab-btn {
    flex: 1;
    padding: 12px 20px;
    border: none;
    background: #e8e8e8;
    color: #666;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
}

.tab-btn.active {
    background: linear-gradient(45deg, #667eea, #764ba2);
    color: white;
}

.tab-btn:hover:not(.active) {
    background: #ddd;
}

.tab-content {
    display: none;
    flex-direction: column;
    gap: 15px;
}

.tab-content.active {
    display: flex;
}

/* 上传区域 */
.upload-area {
    border: 2px dashed #667eea;
    border-radius: 15px;
    padding: 30px;
    text-align: center;
    background: rgba(102, 126, 234, 0.05);
    transition: border-color 0.3s;
}

.upload-area:hover {
    border-color: #764ba2;
}

.upload-area input[type="file"] {
    display: block;
    margin: 10px auto;
    cursor: pointer;
}

.upload-hint {
    color: #999;
    font-size: 0.9rem;
    margin: 5px 0 0;
}

/* 参数行 */
.param-row {
    display: flex;
    align-items: center;
    gap: 10px;
}

.param-row label {
    font-weight: 600;
    min-width: 100px;
}

.param-row input[type="range"] {
    flex: 1;
    accent-color: #667eea;
}

/* 按钮 */
.btn-primary {
    background: linear-gradient(45deg, #667eea, #764ba2);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 25px;
    font-weight: 600;
    font-size: 1rem;
    cursor: pointer;
    box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    transition: transform 0.3s, box-shadow 0.3s;
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
}

.btn-primary:active {
    transform: translateY(0);
}

.btn-primary:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
}

/* 进度条 */
.progress-container {
    margin-top: 15px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.progress-bar {
    flex: 1;
    height: 8px;
    background: #e8e8e8;
    border-radius: 4px;
    overflow: hidden;
}

.progress-bar::after {
    content: '';
    display: block;
    height: 100%;
    background: linear-gradient(45deg, #667eea, #764ba2);
    transition: width 0.3s;
    width: var(--progress, 0%);
}

/* 结果表格 */
.result-table {
    width: 100%;
    border-collapse: collapse;
    background: white;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 15px;
}

.result-table th,
.result-table td {
    padding: 10px 12px;
    border-bottom: 1px solid #eee;
    text-align: left;
}

.result-table th {
    background: #f8f8f8;
    font-weight: 600;
    color: #333;
}

.result-table tbody tr:hover {
    background: #f5f5f5;
}

.empty-msg {
    text-align: center;
    color: #999;
    padding: 40px;
}

/* 详情标签页 */
.detail-tabs {
    display: flex;
    gap: 0;
    margin-bottom: 0;
    border-radius: 10px 10px 0 0;
    overflow: hidden;
}

.detail-tab-btn {
    flex: 1;
    padding: 10px;
    border: none;
    background: #e8e8e8;
    color: #666;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
}

.detail-tab-btn.active {
    background: #667eea;
    color: white;
}

.detail-content {
    display: none;
    background: white;
    border-radius: 0 0 10px 10px;
    padding: 15px;
    max-height: 300px;
    overflow-y: auto;
}

.detail-content.active {
    display: block;
}

#json-output {
    background: #f8f8f8;
    padding: 10px;
    border-radius: 8px;
    font-size: 0.85rem;
    white-space: pre-wrap;
    word-break: break-all;
    margin: 0;
    max-height: 280px;
    overflow-y: auto;
}

/* 原始文本表格 */
.raw-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}

.raw-table th,
.raw-table td {
    padding: 6px 8px;
    border-bottom: 1px solid #eee;
    text-align: left;
}

.raw-table th {
    background: #f8f8f8;
    font-weight: 600;
}

/* 加载动画 */
.loading-spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid #f3f3f3;
    border-top: 2px solid #667eea;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-right: 8px;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* 淡入动画 */
.fade-in-up {
    animation: fadeInUp 0.6s ease-out;
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(30px); }
    to { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 2: Create templates/index.html (empty placeholder for now, will be filled in Task 2)**

Wait — step 2 already covered the HTML. This CSS step is standalone.

---

### Task 4: Create Frontend JS (static/js/app.js)

**Files:**
- Create: `static/js/app.js`

- [ ] **Step 1: Create app.js**

```javascript
// 发票OCR识别系统 - 前端交互逻辑

(function () {
    "use strict";

    // 全局状态
    let tableData = [];
    let isProcessing = false;

    // DOM 元素
    const els = {
        pdfFiles: document.getElementById("pdf-files"),
        pdfConfidence: document.getElementById("pdf-confidence"),
        pdfConfValue: document.getElementById("pdf-confidence-value"),
        btnPdfRecognize: document.getElementById("btn-pdf-recognize"),
        imgFiles: document.getElementById("image-files"),
        imgConfidence: document.getElementById("image-confidence"),
        imgConfValue: document.getElementById("image-confidence-value"),
        btnImgRecognize: document.getElementById("btn-image-recognize"),
        resultTbody: document.getElementById("result-tbody"),
        btnExport: document.getElementById("btn-export"),
        jsonOutput: document.getElementById("json-output"),
        rawTbody: document.getElementById("raw-tbody"),
        progressContainer: document.getElementById("progress-container"),
        progressBar: document.getElementById("progress-bar"),
        progressText: document.getElementById("progress-text"),
    };

    // Tab 切换
    document.querySelectorAll(".tab-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
        });
    });

    // 详情标签页切换
    document.querySelectorAll(".detail-tab-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".detail-tab-btn").forEach((b) => b.classList.remove("active"));
            document.querySelectorAll(".detail-content").forEach((c) => c.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById("detail-" + btn.dataset.detail).classList.add("active");
        });
    });

    // 置信度滑块更新
    els.pdfConfidence.addEventListener("input", () => {
        els.pdfConfValue.textContent = els.pdfConfidence.value;
    });
    els.imgConfidence.addEventListener("input", () => {
        els.imgConfValue.textContent = els.imgConfidence.value;
    });

    // 更新结果表格
    function updateResultTable(rows) {
        tableData = rows;
        els.resultTbody.innerHTML = "";
        if (rows.length === 0) {
            els.resultTbody.innerHTML = '<tr><td colspan="3" class="empty-msg">无数据</td></tr>';
            els.btnExport.disabled = true;
            return;
        }
        rows.forEach((row) => {
            const tr = document.createElement("tr");
            row.forEach((cell) => {
                const td = document.createElement("td");
                td.textContent = cell;
                tr.appendChild(td);
            });
            els.resultTbody.appendChild(tr);
        });
        els.btnExport.disabled = false;
    }

    // 显示 JSON 结果
    function showJsonResult(results) {
        els.jsonOutput.textContent = JSON.stringify(results, null, 2);
    }

    // 显示原始文本
    function showRawTable(rawOcrResults) {
        els.rawTbody.innerHTML = "";
        if (!rawOcrResults || rawOcrResults.length === 0) {
            els.rawTbody.innerHTML = '<tr><td colspan="3">无数据</td></tr>';
            return;
        }
        rawOcrResults.forEach((item, i) => {
            const tr = document.createElement("tr");
            const tdIdx = document.createElement("td");
            tdIdx.textContent = i;
            const tdText = document.createElement("td");
            tdText.textContent = item.text || "";
            const tdScore = document.createElement("td");
            tdScore.textContent = (item.score || 0).toFixed(3);
            tr.appendChild(tdIdx);
            tr.appendChild(tdText);
            tr.appendChild(tdScore);
            els.rawTbody.appendChild(tr);
        });
    }

    // 显示/隐藏进度条
    function showProgress(progress, total) {
        els.progressContainer.style.display = "flex";
        els.progressBar.style.setProperty("--progress", ((progress / total) * 100) + "%");
        els.progressText.textContent = `处理中 ${progress}/${total}...`;
    }

    function hideProgress() {
        els.progressContainer.style.display = "none";
    }

    function setButtonLoading(loading) {
        isProcessing = loading;
        document.querySelectorAll(".btn-primary").forEach((btn) => {
            btn.disabled = loading;
        });
    }

    // 单文件识别（图片）
    els.btnImgRecognize.addEventListener("click", async () => {
        const files = els.imgFiles.files;
        if (files.length === 0) {
            alert("请先选择图片文件");
            return;
        }
        setButtonLoading(true);
        hideProgress();
        const confidence = parseFloat(els.imgConfidence.value);

        try {
            const results = [];
            const rows = [];
            const formData = new FormData();

            for (let i = 0; i < files.length; i++) {
                formData.append("file", files[i]);
                formData.append("confidence", confidence);

                const resp = await fetch("/api/recognize", {
                    method: "POST",
                    body: formData,
                });

                if (!resp.ok) {
                    const err = await resp.json();
                    results.push({ error: err.detail, file_name: files[i].name });
                    rows.push([files[i].name, "处理失败", `错误: ${err.detail}`]);
                    continue;
                }

                const data = await resp.json();
                results.push(data.result);
                rows.push(data.table_row);

                showProgress(i + 1, files.length);
                updateResultTable(rows);
                showJsonResult(results);

                // 显示第一个结果的原始文本
                if (data.result.raw_ocr_results) {
                    showRawTable(data.result.raw_ocr_results);
                }

                // 清空 FormData
                formData.delete("file");
            }
        } catch (e) {
            alert("请求失败: " + e.message);
        } finally {
            setButtonLoading(false);
            setTimeout(hideProgress, 2000);
        }
    });

    // 批量识别（PDF）
    els.btnPdfRecognize.addEventListener("click", async () => {
        const files = els.pdfFiles.files;
        if (files.length === 0) {
            alert("请先选择PDF文件");
            return;
        }
        setButtonLoading(true);
        hideProgress();
        const confidence = parseFloat(els.pdfConfidence.value);

        try {
            const formData = new FormData();
            for (const file of files) {
                formData.append("files", file);
            }
            formData.append("confidence", confidence);

            // 提交批量任务
            const resp = await fetch("/api/batch-recognize", {
                method: "POST",
                body: formData,
            });

            if (!resp.ok) {
                const err = await resp.json();
                alert("提交失败: " + err.detail);
                setButtonLoading(false);
                return;
            }

            const { task_id, total } = await resp.json();

            // 轮询进度
            const pollInterval = setInterval(async () => {
                const statusResp = await fetch("/api/status/" + task_id);
                const status = await statusResp.json();

                showProgress(status.progress, status.total);

                if (status.table_data) {
                    updateResultTable(status.table_data);
                    showJsonResult(status.results);

                    // 显示第一个结果的原始文本
                    if (status.results.length > 0 && status.results[0].raw_ocr_results) {
                        showRawTable(status.results[0].raw_ocr_results);
                    }
                }

                if (status.status === "done" || status.status === "error") {
                    clearInterval(pollInterval);
                    setTimeout(hideProgress, 2000);
                    setButtonLoading(false);
                }
            }, 500);
        } catch (e) {
            alert("请求失败: " + e.message);
            setButtonLoading(false);
        }
    });

    // 导出 Excel
    els.btnExport.addEventListener("click", async () => {
        if (tableData.length === 0) {
            alert("无数据可导出");
            return;
        }

        try {
            const resp = await fetch("/api/export", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(tableData),
            });

            if (!resp.ok) {
                const err = await resp.json();
                alert("导出失败: " + err.detail);
                return;
            }

            // 触发下载
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "invoice_results.xlsx";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (e) {
            alert("导出失败: " + e.message);
        }
    });
})();
```

---

### Task 5: Update requirements.txt, start.bat, CLAUDE.md, delete app.py

**Files:**
- Modify: `requirements.txt`
- Modify: `start.bat`
- Modify: `CLAUDE.md`
- Delete: `app.py`

- [ ] **Step 1: Update requirements.txt**

Replace entire content:

```
fastapi
uvicorn
jinja2
python_multipart>=0.0.20
numpy
rapidocr
Pillow
PyMuPDF
pandas
openpyxl
pytest
```

- [ ] **Step 2: Update start.bat**

```bat
@echo off
echo ========================================
echo   Invoice OCR System
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.7+.
    pause
    exit /b 1
)

:: Check dependencies
echo [1/2] Checking dependencies...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    echo Dependencies OK.
)
echo.

:: Start app
echo [2/2] Starting app...
echo URL: http://localhost:8000
echo.
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
```

- [ ] **Step 3: Delete app.py**

Run: `del app.py`

- [ ] **Step 4: Update CLAUDE.md Architecture section**

Replace the Architecture section:

```markdown
## Architecture

```
main.py               ─ FastAPI web app (API routes + static file serving)
ocr_engine.py         ─ PDF-to-image, file type detection, InvoiceImageProcessor facade
field_extractor.py    ─ InvoiceFieldExtractor: type detection + regex field extraction
export.py             ─ Excel export with total row
invoice_config.py     ─ Regex patterns per invoice type (configuration, unchanged)
templates/index.html  ─ Frontend page (vanilla HTML/CSS/JS)
static/css/style.css  ─ Frontend styles
static/js/app.js      ─ Frontend interaction logic
requirements.txt      ─ Dependencies: fastapi, uvicorn, rapidocr, PyMuPDF, Pillow, pandas, openpyxl, pytest, jinja2, python_multipart
tests/                ─ pytest unit tests
  test_field_extractor.py  ─ Tests for detect_invoice_type + extract_fields
  test_export.py           ─ Tests for export_table_data
```

**Core flow:**
1. User uploads image(s) or PDF(s) via browser UI
2. Frontend sends files to `/api/recognize` (single) or `/api/batch-recognize` (batch) via Fetch API
3. FastAPI delegates to `ocr_engine.InvoiceImageProcessor` for OCR + field extraction
4. Frontend polls `/api/status/<task_id>` for batch progress (500ms interval)
5. Results displayed in HTML table + JSON detail view; exportable via `/api/export`
```

- [ ] **Step 5: Verify existing tests still pass**

Run: `python -m pytest tests/ -v`
Expected: 20 tests pass (ocr_engine.py, field_extractor.py, export.py unchanged)

- [ ] **Step 6: Verify FastAPI app starts**

Run: `timeout 5 python -c "from main import app; print('main.py imports OK')"`
Expected: `main.py imports OK`

- [ ] **Step 7: Commit**

```bash
git add main.py templates/index.html static/css/style.css static/js/app.js requirements.txt start.bat CLAUDE.md
git rm app.py
git commit -m "feat: replace gradio with fastapi + native frontend
- Create main.py with FastAPI REST API (recognize, batch, status, export)
- Create templates/index.html, static/css/style.css, static/js/app.js
- Remove gradio dependency, remove app.py, remove mcp_server
- Update requirements.txt with fastapi+uvicorn+jinja2
- Update start.bat to use uvicorn"
```
