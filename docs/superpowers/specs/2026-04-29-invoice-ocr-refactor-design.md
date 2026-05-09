# 轻量重构设计文档 — app.py 拆分 + 测试

**日期:** 2026-04-29
**目标:** 将 app.py 600+ 行代码拆分为职责清晰的模块，并为核心逻辑补充单元测试

## 拆分方案

### 目标文件结构

```
invoice_ocr/
├── app.py                  ─ 精简后的 Gradio UI
├── invoice_config.py       ─ 不变
├── ocr_engine.py           ─ [新] OCR 图像处理
├── field_extractor.py      ─ [新] 发票类型检测 + 字段提取
├── export.py               ─ [新] Excel 导出
├── tests/                  ─ [新]
│   ├── __init__.py
│   ├── test_field_extractor.py
│   └── test_export.py
├── styles.css
├── requirements.txt
└── CLAUDE.md
```

### 各文件职责

**ocr_engine.py**
- `pdf_first_page_to_image()` — PDF 转图片
- `detect_file_type()` — 文件类型检测
- `InvoiceImageProcessor` 类 — 封装 RapidOCR 调用，接收图像返回 OCR 原始结果

**field_extractor.py**
- `InvoiceFieldExtractor` 类
  - `detect_invoice_type(text_list)` — 关键词匹配检测发票类型
  - `extract_fields(text_list, detected_type)` — 从 OCR 文本中提取开票日期和价税合计小写
  - `validate_invoice_data()` — 委托给 invoice_config.py 的验证函数

**export.py**
- `export_table_data(table_data)` — DataFrame/列表转 Excel + 总计行

**app.py（精简后）**
- `load_custom_css()` — 加载样式
- `InvoiceCORProcessor` — 保留为门面类，内部委托 ocr_engine + field_extractor
- `process_pdf_invoice()` — 批量 PDF 处理流程（UI 层逻辑）
- `process_with_fields_image()` — 单图处理入口（UI 层逻辑）
- Gradio UI 定义 + 事件绑定
- `export_table_data` 改为 import 自 export.py
- 删除 `create_invoice_examples()`（引用不存在的图片）

### 测试覆盖范围

- `test_field_extractor.py`: 5 种发票类型的 `detect_invoice_type` 识别准确性；`extract_fields` 对日期和价税合计的提取
- `test_export.py`: Excel 导出功能，包含总计行计算

### 约束

- 不改变现有功能和用户界面行为
- 不新增依赖
- `invoice_config.py` 保持不变