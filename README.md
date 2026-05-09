---
# 详细文档见https://modelscope.cn/docs/%E5%88%9B%E7%A9%BA%E9%97%B4%E5%8D%A1%E7%89%87
domain:
tags:
-
datasets:
  evaluation:
  -
  test:
  -
  train:
  -
models:
-
license: Apache License 2.0
---
# 🧾 QuickScan Invoices

基于 RapidOCR 的智能发票识别系统，支持多种发票类型的自动识别、批量处理和字段提取。

## ✨ 主要功能

- **多类型发票识别** - 支持增值税专用发票、普通发票、电子发票等
- **智能字段提取** - 自动提取开票日期、价税合计等关键信息
- **批量处理** - 支持同时上传和处理多个 PDF/图片文件
- **多格式支持** - 支持图像文件(JPG、PNG、BMP、TIFF)和 PDF 文件
- **高端 UI** - 深色金融终端风格，Playfair Display + DM Sans 排版
- **结构化表格输出** - 清晰展示识别结果，含统计卡片和进度动画
- **Excel 导出** - 识别结果导出为 Excel，含金额总计
- **拖拽上传** - 支持拖放文件上传，带文件列表管理

## 🚀 快速开始

### 环境要求
- Python 3.7+
- Windows/Linux/MacOS

### 安装依赖
```bash
pip install -r requirements.txt
```

### 启动系统
```bash
# 使用启动脚本
start.bat

# 或直接运行
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

启动后访问 `http://localhost:8000` 即可使用。

## 📋 使用方法

1. **上传发票** - 拖拽或点击上传区域选择发票文件
2. **调整参数** - 设置置信度阈值（可选，默认0.5）
3. **开始识别** - 点击「开始识别」按钮
4. **查看结果** - 结果表格、统计卡片和 JSON 详情实时展示
5. **导出结果** - 点击「导出 Excel」下载识别结果

## 📁 项目结构

```
quickscan-invoices/
├── main.py                 # FastAPI 应用（API 路由 + 静态文件服务）
├── ocr_engine.py           # PDF转图片 + RapidOCR 调用
├── field_extractor.py      # 发票类型检测 + 正则字段提取
├── export.py               # Excel 导出（含总计行）
├── invoice_config.py       # 发票类型正则配置
├── templates/index.html    # 前端页面
├── static/css/style.css    # 前端样式
├── static/js/app.js        # 前端交互逻辑
├── requirements.txt        # 依赖
├── start.bat               # Windows 启动脚本
└── tests/                  # pytest 单元测试
    ├── test_field_extractor.py
    └── test_export.py
```

## 🔧 技术栈

- **FastAPI** - 高性能 Web 框架
- **uvicorn** - ASGI 服务器
- **Jinja2** - 模板引擎
- **RapidOCR** - OCR 引擎
- **PyMuPDF (fitz)** - PDF 处理
- **pandas + openpyxl** - Excel 导出
- **原生 HTML/CSS/JS** - 前端界面（无框架依赖）

## 📊 支持的发票类型

- 增值税专用发票
- 增值税普通发票
- 电子发票
- 通用机打发票
- 手写发票

## 📄 许可证

本项目采用 Apache License 2.0 许可证。

---

**注意**：本系统仅用于学习和研究目的，实际使用时请确保符合相关法律法规。
