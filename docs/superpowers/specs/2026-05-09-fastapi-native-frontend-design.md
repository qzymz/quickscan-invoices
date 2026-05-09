# 移除 Gradio / FastAPI + 原生前端 设计文档

**日期:** 2026-05-09
**目标:** 移除 Gradio 依赖，用 FastAPI + 纯 HTML/CSS/JS 重写整个前端交互层

## 架构

### 后端 API

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/recognize` | POST | 上传单个文件，返回识别结果 JSON |
| `/api/batch-recognize` | POST | 上传多个文件，返回 task_id |
| `/api/status/<task_id>` | GET | 轮询获取任务进度和结果 |
| `/api/export` | POST | 传入表格数据，返回 Excel 文件 |
| `/` | GET | 返回 index.html |
| `/static/...` | GET | 静态资源 |

### 前端

- 单页面 `index.html`，左右两栏布局（上传区 + 结果区）
- Tab 切换：PDF / 图片
- Fetch API 调用后端接口
- FormData 上传文件
- 多文件上传通过 task_id 轮询进度（500ms 间隔）
- 纯原生 CSS，从 styles.css 改造，去除 .gradio-* hack

### 文件结构

```
invoice_ocr/
├── main.py                 ─ FastAPI 应用（替代 app.py）
├── ocr_engine.py           ─ 不变
├── field_extractor.py      ─ 不变
├── export.py               ─ 不变
├── invoice_config.py       ─ 不变
├── requirements.txt        ─ 移除 gradio，增加 fastapi+uvicorn
├── static/
│   ├── css/style.css       ─ 原生 CSS
│   └── js/app.js           ─ 前端交互逻辑
├── templates/
│   └── index.html          ─ 前端页面
├── tests/                  ─ 不变
└── CLAUDE.md               ─ 更新
```

### 关键约束

- 不改变 OCR/字段提取/导出逻辑
- `ocr_engine.py`、`field_extractor.py`、`export.py` 保持不变
- 移除 gradio 依赖
- 移除 mcp_server 功能
