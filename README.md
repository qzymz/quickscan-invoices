# QuickScan Invoices

> 基于 RapidOCR 的智能发票识别系统，FastAPI + 原生前端，支持批量处理与 Excel 导出。

## 概览

QuickScan Invoices 是一款面向财务场景的发票 OCR 识别工具。用户上传发票图片或 PDF，系统自动识别发票类型并提取关键字段（开票日期、价税合计），结果可导出为 Excel 文件。

**核心特性：**

| 特性 | 说明 |
|------|------|
| 多类型识别 | 自动识别 5 种发票类型（增值税专用/普通、电子、机打、手写） |
| 批量处理 | 一次上传多个文件，后台异步处理，前端实时轮询进度 |
| 拖拽上传 | 支持拖放文件，带文件列表管理 |
| 深色 UI | 金融终端风格界面，Playfair Display + DM Sans 排版 |
| Excel 导出 | 含金额总计行，一键下载 |
| 零前端框架 | 纯原生 HTML/CSS/JS，无 Vue/React 依赖 |

## 快速开始

### 安装

```bash
# 克隆项目
cd quickscan-invoices

# 安装依赖
pip install -r requirements.txt
```

### 启动

```bash
# Windows：双击启动脚本
start.bat

# 或手动启动
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

访问 `http://localhost:8000` 即可使用。

### 运行测试

```bash
python -m pytest tests/ -v
```

## 架构

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (Browser)                 │
│  index.html  │  style.css  │  app.js                  │
│  Tab切换 │ 拖拽上传 │ Toast通知 │ 500ms轮询 │ 统计卡片  │
└──────────────────────┬──────────────────────────────┘
                       │ Fetch API
                       ▼
┌─────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                  │
│                                                     │
│  GET  /                  →  前端页面                  │
│  POST /api/recognize     →  单文件识别               │
│  POST /api/batch-recognize → 批量识别 (返回task_id)   │
│  GET  /api/status/{id}   →  轮询进度                 │
│  POST /api/export        →  Excel 下载               │
│  GET  /static/*          →  静态资源                 │
└────────┬─────────────┬──────────────┬───────────────┘
         │             │              │
         ▼             ▼              ▼
   ┌──────────┐  ┌────────────┐  ┌─────────┐
   │ocr_engine│  │field_      │  │ export  │
   │   .py    │  │extractor.py│  │  .py    │
   └──────────┘  └────────────┘  └─────────┘
```

### 项目结构

```
quickscan-invoices/
├── main.py                 # FastAPI 应用入口
│   ├── GET  /              # 前端页面
│   ├── POST /api/recognize # 单文件识别
│   ├── POST /api/batch-recognize  # 批量识别
│   ├── GET  /api/status/{task_id} # 进度轮询
│   └── POST /api/export    # Excel 导出
│
├── ocr_engine.py           # OCR 处理层
│   ├── pdf_first_page_to_image()  # PDF → Image (PyMuPDF, 300 DPI)
│   ├── detect_file_type()         # 文件类型检测
│   └── InvoiceImageProcessor      # 门面类：OCR → 字段提取
│
├── field_extractor.py      # 字段提取层
│   ├── detect_invoice_type()      # 关键词匹配识别发票类型
│   ├── extract_fields()           # 正则提取目标字段
│   └── validate()                 # 校验必需字段
│
├── invoice_config.py       # 配置层：5 种发票类型的正则规则
├── export.py               # Excel 导出（含总计行计算）
│
├── templates/index.html    # 前端页面（Jinja2 模板）
├── static/css/style.css    # 深色金融终端样式
├── static/js/app.js        # 前端交互逻辑（Fetch + FormData）
│
├── requirements.txt        # 依赖列表
├── start.bat               # Windows 启动脚本
├── CLAUDE.md               # 项目文档
└── tests/                  # 单元测试（20 个）
    ├── test_field_extractor.py
    └── test_export.py
```

## API 文档

### POST `/api/recognize`

单文件识别。支持图片和 PDF。

```bash
curl -X POST http://localhost:8000/api/recognize \
  -F "file=@invoice.pdf" \
  -F "confidence=0.5"
```

**响应：**
```json
{
  "status": "success",
  "result": {
    "invoice_type": "电子发票",
    "extracted_fields": {
      "开票日期": "2023年03月02日",
      "价税合计小写": "80.60"
    },
    "raw_ocr_results": [...]
  },
  "table_row": ["invoice.pdf", "2023年03月02日", "80.60"]
}
```

### POST `/api/batch-recognize`

批量文件识别。返回 `task_id` 用于轮询。

```bash
curl -X POST http://localhost:8000/api/batch-recognize \
  -F "files=@a.pdf" -F "files=@b.pdf"
```

**响应：**
```json
{
  "task_id": "a1b2c3d4-...",
  "total": 2
}
```

### GET `/api/status/{task_id}`

轮询批量任务进度。

```bash
curl http://localhost:8000/api/status/a1b2c3d4-...
```

**响应：**
```json
{
  "status": "done",
  "progress": 2,
  "total": 2,
  "results": [...],
  "table_data": [["a.pdf", "2023-03-02", "80.60"], ...]
}
```

### POST `/api/export`

导出 Excel 文件。

```bash
curl -X POST http://localhost:8000/api/export \
  -H "Content-Type: application/json" \
  -d '[["a.pdf", "2023-03-02", "80.60"]]' \
  --output result.xlsx
```

## 支持的发票类型

| 类型 | 识别关键词 |
|------|-----------|
| 增值税专用发票 | "增值税专用发票" |
| 增值税普通发票 | "增值税", "普通发票" |
| 电子发票 | "电子发票", "电子普通发票" |
| 通用机打发票 | "机打发票", "通用机打" |
| 手写发票 | "手写发票", "定额发票" |

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + uvicorn |
| OCR 引擎 | RapidOCR (ONNX Runtime) |
| PDF 处理 | PyMuPDF (fitz), 300 DPI |
| 字段提取 | 正则表达式 + 关键词匹配 |
| Excel 导出 | pandas + openpyxl |
| 前端 | 原生 HTML/CSS/JS（零框架） |
| 字体 | Playfair Display + DM Sans + JetBrains Mono |

## 依赖

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

## 许可证

Apache License 2.0

> 本系统仅用于学习和研究目的，实际使用时请确保符合相关法律法规。
