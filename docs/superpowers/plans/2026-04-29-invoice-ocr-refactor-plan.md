# Invoice OCR Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split monolithic app.py (613 lines) into focused modules and add unit tests for core extraction/export logic.

**Architecture:** Create three new modules (ocr_engine.py, field_extractor.py, export.py) by extracting code from app.py. Keep InvoiceCORProcessor as a facade class that delegates to the new modules. Delete dead code (create_invoice_examples referencing missing images).

**Tech Stack:** Python 3.7+, RapidOCR, Gradio, pandas, pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `field_extractor.py` | Create | Invoice type detection + field extraction logic |
| `ocr_engine.py` | Create | PDF-to-image conversion + file type detection |
| `export.py` | Create | Excel export with total row calculation |
| `app.py` | Rewrite (keep UI section) | Slimmed to UI + facade class that imports from new modules |
| `tests/__init__.py` | Create | Package marker |
| `tests/test_field_extractor.py` | Create | Tests for detect_invoice_type + extract_fields |
| `tests/test_export.py` | Create | Tests for export_table_data |
| `CLAUDE.md` | Update | Reflect new file structure |
| `requirements.txt` | Modify | Add `pytest` |

---

### Task 1: Create field_extractor.py

**Files:**
- Create: `field_extractor.py`

- [ ] **Step 1: Create field_extractor.py with InvoiceFieldExtractor class**

```python
# -*- coding: utf-8 -*-
"""发票字段提取模块 — 从 OCR 文本中检测发票类型并提取关键字段"""

import re
from typing import Dict, List, Any
from invoice_config import (
    INVOICE_TYPES,
    DATE_PATTERNS,
    validate_invoice_data,
)


class InvoiceFieldExtractor:
    """发票字段提取器"""

    def __init__(self):
        self.invoice_types = INVOICE_TYPES
        self.date_patterns = DATE_PATTERNS

    def detect_invoice_type(self, text_list: List[str]) -> str:
        """检测发票类型"""
        if not text_list:
            return "未知类型"

        combined_text = " ".join(text_list).lower()

        for invoice_type, config in self.invoice_types.items():
            keywords = config.get("keywords", [])
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    return invoice_type

        return "通用发票"

    def _extract_date(self, combined_text: str) -> str:
        """提取开票日期"""
        for pattern in self.date_patterns:
            match = re.search(pattern, combined_text)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_total_amount(self, lines: List[str]) -> str:
        """提取价税合计小写"""
        tax_total_amount = ""

        # 模式1: 价税合计 + 小写 + 货币符号
        for line in lines:
            if "价税合计" in line and ("小写" in line or "（小写）" in line) and ("￥" in line or "¥" in line):
                price_match = re.search(r"[￥¥]\s*([\d,]+\.?\d*)", line)
                if price_match:
                    return price_match.group(1).strip()

        # 模式2: 包含"价税合计"的行中查找金额
        for line in lines:
            if "价税合计" in line:
                price_match = re.search(r"[￥¥]\s*([\d,]+\.?\d*)", line)
                if price_match:
                    return price_match.group(1).strip()

        # 模式3: "（小写）" + 货币符号
        for line in lines:
            if "（小写）" in line and ("￥" in line or "¥" in line):
                price_match = re.search(r"[￥¥]\s*([\d,]+\.?\d*)", line)
                if price_match:
                    return price_match.group(1).strip()

        # 模式4: 所有带货币符号的行中选最大金额
        all_amounts = []
        for line in lines:
            if "￥" in line or "¥" in line:
                for match in re.finditer(r"[￥¥]\s*([\d,]+\.?\d*)", line):
                    amount_str = match.group(1).strip()
                    try:
                        amount = float(amount_str.replace(",", ""))
                        all_amounts.append((amount, amount_str))
                    except ValueError:
                        continue

        if all_amounts:
            all_amounts.sort(reverse=True)
            return all_amounts[0][1]

        return ""

    def extract_fields(self, text_list: List[str], detected_type: str = None) -> Dict[str, Any]:
        """提取发票字段（开票日期、价税合计小写）"""
        if not text_list:
            return {}

        extracted_fields = {}
        combined_text = " ".join(text_list)

        date_str = self._extract_date(combined_text)
        if date_str:
            extracted_fields["开票日期"] = date_str

        total_amount = self._extract_total_amount(text_list)
        if total_amount:
            extracted_fields["价税合计小写"] = total_amount

        return extracted_fields

    def validate(self, extracted_fields: Dict[str, Any]) -> Dict[str, Any]:
        """验证提取的字段"""
        return validate_invoice_data(extracted_fields)
```

- [ ] **Step 2: Verify field_extractor.py is syntactically valid**

Run: `python -c "import field_extractor; print('OK')"`
Expected: `OK`

---

### Task 2: Create ocr_engine.py

**Files:**
- Create: `ocr_engine.py`

- [ ] **Step 1: Create ocr_engine.py with OCR processing**

```python
# -*- coding: utf-8 -*-
"""OCR 图像处理模块 — PDF 转图片 + RapidOCR 调用"""

import os
from typing import Dict, List, Any, Tuple, Optional
from rapidocr import RapidOCR
from PIL import Image
import fitz  # PyMuPDF
import numpy as np
from datetime import datetime

from field_extractor import InvoiceFieldExtractor


def pdf_first_page_to_image(pdf_file) -> Image.Image:
    """将PDF第一页渲染为PIL.Image对象，兼容gradio NamedString/BytesIO/真实文件"""
    try:
        if hasattr(pdf_file, "seek") and hasattr(pdf_file, "read"):
            pdf_file.seek(0)
            pdf_bytes = pdf_file.read()
        else:
            with open(pdf_file.name, "rb") as f:
                pdf_bytes = f.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img
    except Exception as e:
        raise Exception(f"PDF转图片失败: {e}")


def detect_file_type(file_path: str) -> str:
    """检测文件类型"""
    if not file_path:
        return "unknown"
    file_extension = os.path.splitext(file_path)[1].lower()
    if file_extension in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']:
        return "image"
    elif file_extension == '.pdf':
        return "pdf"
    else:
        return "unknown"


class InvoiceImageProcessor:
    """发票图像处理引擎（门面类，委托给 InvoiceFieldExtractor）"""

    def __init__(self):
        self.ocr_engine = RapidOCR()
        self.field_extractor = InvoiceFieldExtractor()

    def process_invoice(self, img_input, confidence_threshold: float = 0.5) -> Tuple[Dict[str, Any], str, List[List[Any]]]:
        """处理发票图像，返回结构化数据和原始OCR数据"""
        ocr_result = self.ocr_engine(
            img_input,
            use_det=True,
            use_cls=True,
            use_rec=True,
            text_score=confidence_threshold,
            box_thresh=0.5,
            unclip_ratio=1.6,
            return_word_box=False,
        )

        text_list = ocr_result.txts if ocr_result.txts else []
        invoice_type = self.field_extractor.detect_invoice_type(text_list)
        extracted_fields = self.field_extractor.extract_fields(text_list, invoice_type)
        validation_result = self.field_extractor.validate(extracted_fields)

        # 构建原始OCR识别数据
        raw_ocr_results = []
        boxes = getattr(ocr_result, 'boxes', None)
        scores = getattr(ocr_result, 'scores', None)
        txts = getattr(ocr_result, 'txts', None)
        if boxes is not None and txts is not None and scores is not None:
            for text, box, score in zip(txts, boxes, scores):
                box_list = box.tolist() if hasattr(box, 'tolist') else box
                raw_ocr_results.append({
                    "text": text,
                    "box": box_list,
                    "score": float(score)
                })
        elif txts is not None and scores is not None:
            for text, score in zip(txts, scores):
                raw_ocr_results.append({
                    "text": text,
                    "box": None,
                    "score": float(score)
                })

        result_data = {
            "invoice_type": invoice_type,
            "confidence": float(np.mean(scores)) if scores is not None and len(scores) > 0 else 0.0,
            "processing_time": float(ocr_result.elapse),
            "timestamp": datetime.now().isoformat(),
            "raw_ocr_results": raw_ocr_results,
            "extracted_fields": extracted_fields,
            "validation": validation_result,
            "raw_text": text_list
        }

        vis_text = f"发票类型: {invoice_type}\n"
        vis_text += f"置信度: {result_data['confidence']:.3f}\n"
        vis_text += f"处理时间: {result_data['processing_time']:.3f}秒\n"
        vis_text += f"数据有效性: {'✅ 有效' if validation_result['is_valid'] else '❌ 无效'}\n\n"

        if validation_result['missing_fields']:
            vis_text += f"缺失字段: {', '.join(validation_result['missing_fields'])}\n"

        if validation_result['warnings']:
            vis_text += f"警告信息: {', '.join(validation_result['warnings'])}\n"

        vis_text += "\n提取字段:\n"
        for field, value in extracted_fields.items():
            vis_text += f"{field}: {value}\n"

        table_data = []
        if text_list and scores is not None and len(scores) > 0:
            for i, (text, score) in enumerate(zip(text_list, scores)):
                table_data.append([i, text, f"{score:.3f}"])
        else:
            table_data = [[0, "未识别到文本", "0.000"]]

        return result_data, vis_text, table_data
```

- [ ] **Step 2: Verify ocr_engine.py is syntactically valid**

Run: `python -c "import ocr_engine; print('OK')"`
Expected: `OK`

---

### Task 3: Create export.py

**Files:**
- Create: `export.py`

- [ ] **Step 1: Create export.py with export_table_data function**

```python
# -*- coding: utf-8 -*-
"""Excel 导出模块"""

import os
import datetime
import tempfile
import pandas as pd


def export_table_data(table_data):
    """将表格数据导出为Excel格式并保存到临时文件"""
    if isinstance(table_data, pd.DataFrame):
        if table_data.empty:
            return None
        df = table_data
    elif isinstance(table_data, list):
        if not table_data:
            return None
        df = pd.DataFrame(table_data, columns=["文件名", "开票日期", "价税合计小写"])
    else:
        return None

    # 计算金额总计
    try:
        df['价税合计小写'] = pd.to_numeric(df['价税合计小写'], errors='coerce')
        total_amount = df['价税合计小写'].sum()
        total_row = pd.DataFrame([{'文件名': '总计', '开票日期': '', '价税合计小写': total_amount}])
        df = pd.concat([df, total_row], ignore_index=True)
    except Exception as e:
        print(f"计算金额总计失败: {e}")

    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
        with pd.ExcelWriter(tmp_file.name, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='发票识别结果')
        return tmp_file.name
```

- [ ] **Step 2: Verify export.py is syntactically valid**

Run: `python -c "import export; print('OK')"`
Expected: `OK`

---

### Task 4: Create Tests

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_field_extractor.py`
- Create: `tests/test_export.py`

- [ ] **Step 1: Create tests/__init__.py** (empty file)

- [ ] **Step 2: Create tests/test_field_extractor.py**

```python
# -*- coding: utf-8 -*-
"""测试字段提取逻辑"""

import pytest
from field_extractor import InvoiceFieldExtractor


@pytest.fixture
def extractor():
    return InvoiceFieldExtractor()


class TestDetectInvoiceType:
    """测试发票类型检测"""

    def test_vat_special_invoice(self, extractor):
        text = ["增值税专用发票", "发票代码：12345678", "价税合计（小写）¥190.90"]
        assert extractor.detect_invoice_type(text) == "增值税专用发票"

    def test_vat_ordinary_invoice(self, extractor):
        text = ["增值税普通发票", "发票号码：87654321"]
        assert extractor.detect_invoice_type(text) == "增值税普通发票"

    def test_electronic_invoice(self, extractor):
        text = ["电子发票", "电子普通发票"]
        assert extractor.detect_invoice_type(text) == "电子发票"

    def test_machine_printed_invoice(self, extractor):
        text = ["通用机打发票", "商品名称：办公用品"]
        assert extractor.detect_invoice_type(text) == "通用机打发票"

    def test_handwritten_invoice(self, extractor):
        text = ["手写发票", "手写"]
        assert extractor.detect_invoice_type(text) == "手写发票"

    def test_unknown_type(self, extractor):
        text = ["这是一张普通的纸"]
        assert extractor.detect_invoice_type(text) == "通用发票"

    def test_empty_text(self, extractor):
        assert extractor.detect_invoice_type([]) == "未知类型"


class TestExtractFields:
    """测试字段提取"""

    def test_extract_date_chinese_format(self, extractor):
        text = ["开票日期：2024年3月15日", "价税合计（小写）¥100.00"]
        result = extractor.extract_fields(text)
        assert result["开票日期"] == "2024年3月15日"

    def test_extract_date_dash_format(self, extractor):
        text = ["开票日期: 2024-03-15", "价税合计（小写）¥100.00"]
        result = extractor.extract_fields(text)
        assert result["开票日期"] == "2024-03-15"

    def test_extract_total_amount_with_label(self, extractor):
        text = ["价税合计（小写）¥190.90"]
        result = extractor.extract_fields(text)
        assert result["价税合计小写"] == "190.90"

    def test_extract_total_amount_with_comma(self, extractor):
        text = ["价税合计（小写）¥1,234.56"]
        result = extractor.extract_fields(text)
        assert result["价税合计小写"] == "1,234.56"

    def test_extract_fallback_to_largest_amount(self, extractor):
        text = ["税额 ¥10.00", "价税合计 ¥500.00"]
        result = extractor.extract_fields(text)
        assert result["价税合计小写"] == "500.00"

    def test_empty_text_returns_empty_dict(self, extractor):
        assert extractor.extract_fields([]) == {}

    def test_no_matching_fields_returns_empty(self, extractor):
        text = ["一些无关的文本"]
        result = extractor.extract_fields(text)
        assert result == {}
```

- [ ] **Step 3: Create tests/test_export.py**

```python
# -*- coding: utf-8 -*-
"""测试 Excel 导出逻辑"""

import os
import pandas as pd
import pytest
from export import export_table_data


class TestExportTableData:
    """测试导出表格数据"""

    def test_export_list_data(self):
        table_data = [
            ["fp1.jpg", "2024年3月15日", "100.00"],
            ["fp2.jpg", "2024-03-20", "200.50"],
        ]
        result = export_table_data(table_data)
        assert result is not None
        assert os.path.exists(result)
        assert result.endswith('.xlsx')

        # 验证内容
        df = pd.read_excel(result, sheet_name='发票识别结果')
        assert len(df) == 3  # 2行数据 + 1行总计
        assert df.iloc[-1]['文件名'] == '总计'
        # 清理
        os.unlink(result)

    def test_export_dataframe(self):
        df = pd.DataFrame({
            "文件名": ["fp1.jpg"],
            "开票日期": ["2024-01-01"],
            "价税合计小写": ["50.00"]
        })
        result = export_table_data(df)
        assert result is not None
        assert os.path.exists(result)
        # 清理
        os.unlink(result)

    def test_export_empty_list_returns_none(self):
        assert export_table_data([]) is None

    def test_export_empty_dataframe_returns_none(self):
        df = pd.DataFrame()
        assert export_table_data(df) is None

    def test_export_invalid_type_returns_none(self):
        assert export_table_data("not a list or dataframe") is None

    def test_export_total_row_calculated_correctly(self):
        table_data = [
            ["a.jpg", "2024-01-01", "100.00"],
            ["b.jpg", "2024-01-02", "50.00"],
        ]
        result = export_table_data(table_data)
        df = pd.read_excel(result, sheet_name='发票识别结果')
        total_row = df[df['文件名'] == '总计']
        assert total_row.iloc[0]['价税合计小写'] == 150.0
        # 清理
        os.unlink(result)
```

- [ ] **Step 4: Install pytest and run tests**

Run: `pip install pytest`
Run: `python -m pytest tests/ -v`
Expected: All tests pass (13 tests)

- [ ] **Step 5: Commit**

```bash
git add field_extractor.py ocr_engine.py export.py tests/__init__.py tests/test_field_extractor.py tests/test_export.py
git commit -m "feat: split app.py into focused modules + add unit tests
- Create field_extractor.py with InvoiceFieldExtractor (detect + extract)
- Create ocr_engine.py with InvoiceImageProcessor (OCR facade)
- Create export.py with export_table_data
- Add tests for field_extractor and export modules"
```

---

### Task 5: Rewrite app.py to Use New Modules

**Files:**
- Rewrite: `app.py` (replace entire file content)

- [ ] **Step 1: Replace app.py with slimmed version**

```python
# -*- coding: utf-8 -*-
"""
发票OCR专用识别系统
基于RapidOCR的智能发票识别与字段提取平台
"""

import gradio as gr
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple
from PIL import Image

from ocr_engine import InvoiceImageProcessor, pdf_first_page_to_image, detect_file_type
from invoice_config import (
    get_invoice_types_list,
    get_all_field_patterns,
    validate_invoice_data,
)
from export import export_table_data


# 读取外部样式文件
def load_custom_css():
    """加载自定义CSS样式，兼容Gradio 6.0+"""
    try:
        with open('styles.css', 'r', encoding='utf-8') as f:
            css_content = f.read()
            updated_css = css_content + """
            .gradio-container {
                background: linear-gradient(135deg, #e3f2fd 0%, #f5f9ff 50%, #e8f5fd 100%) !important;
                background-attachment: fixed !important;
                background-size: cover !important;
            }
            body {
                background: transparent !important;
            }
            """
            return updated_css
    except FileNotFoundError:
        return """
        body {
            font-family: 'Segoe UI', sans-serif;
            background: transparent !important;
        }
        .gradio-container {
            background: linear-gradient(135deg, #e3f2fd 0%, #f5f9ff 50%, #e8f5fd 100%) !important;
            background-attachment: fixed !important;
            background-size: cover !important;
        }
        .gr-container {
            background: linear-gradient(135deg, #e3f2fd 0%, #f5f9ff 50%, #e8f5fd 100%) !important;
            background-attachment: fixed !important;
            background-size: cover !important;
        }
        .gr-button {
            background: linear-gradient(45deg, #667eea, #764ba2) !important;
            color: white !important;
        }
        .gr-group {
            background: rgba(255, 255, 255, 0.95) !important;
            border-radius: 15px !important;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08) !important;
        }
        .gr-databox {
            background: white !important;
            border: 2px solid #e2e8f0 !important;
        }
        .gr-textbox {
            background: white !important;
            border: 2px solid #e2e8f0 !important;
        }
        """
    except Exception as e:
        print(f"加载样式文件时出错: {e}")
        return ""


# 全局处理器实例
invoice_processor = InvoiceImageProcessor()


def process_pdf_invoice(pdf_files, confidence_threshold: float = 0.5, progress=gr.Progress()):
    try:
        all_results = []
        result_table_data = []
        all_table_data = []

        for i, pdf_file in enumerate(pdf_files):
            file_basename = os.path.basename(pdf_file.name)
            progress((i, len(pdf_files)), f"处理第 {i+1} 个PDF文件: {file_basename}")

            try:
                img = pdf_first_page_to_image(pdf_file)
                result_data, vis_text, table_data = invoice_processor.process_invoice(img, confidence_threshold)
                result_data["source_type"] = "PDF"
                result_data["processed_page"] = 1
                result_data["file_name"] = file_basename

                all_results.append(result_data)

                for row in table_data:
                    all_table_data.append([len(all_table_data) + 1, f"{file_basename}: {row[1]}", row[2]])

                invoice_date = result_data["extracted_fields"].get("开票日期", "未识别")
                total_amount = result_data["extracted_fields"].get("价税合计小写", "未识别")
                result_table_data.append([file_basename, invoice_date, total_amount])

            except Exception as e:
                error_msg = f"PDF处理失败: {str(e)}"
                all_results.append({
                    "error": error_msg,
                    "file_name": file_basename,
                    "source_type": "PDF"
                })
                all_table_data.append([len(all_table_data) + 1, f"{file_basename}: PDF处理失败", "0.000"])
                result_table_data.append([file_basename, "处理失败", f"错误: {str(e)}"])

        progress(1, "处理完成")
        return json.dumps(all_results, ensure_ascii=False, indent=2), result_table_data, all_table_data
    except Exception as e:
        error_msg = f"批量PDF处理失败: {str(e)}"
        return json.dumps([{"error": error_msg}]), [["", "批量处理失败", f"错误: {str(e)}"]], [[0, "批量PDF处理失败", "0.000"]]


def process_mixed_input(file_input, confidence_threshold: float = 0.5):
    if file_input is None:
        return {"error": "请先上传文件"}, "请先上传文件", []
    file_type = detect_file_type(file_input.name)
    if file_type == "image":
        return process_with_fields_image(file_input, confidence_threshold)
    elif file_type == "pdf":
        return process_pdf_invoice(file_input, confidence_threshold)
    else:
        error_msg = "不支持的文件格式，请上传图像或PDF文件"
        return {"error": error_msg}, error_msg, [[0, "不支持的文件格式", "0.000"]]


def process_with_fields_image(img_path, confidence_threshold: float = 0.5):
    """处理图像发票，返回结构化数据、结构化表格和原始文本表格"""
    if img_path is None:
        return {"error": "请先上传图片"}, [["", "请先上传图片", ""]], []
    try:
        img_input = Image.open(img_path)
        result_data, vis_text, table_data = invoice_processor.process_invoice(img_input, confidence_threshold)
        result_data["source_type"] = "Image"
        result_data["file_name"] = os.path.basename(img_path) if isinstance(img_path, str) else "未知图片"

        file_name = result_data["file_name"]
        invoice_date = result_data["extracted_fields"].get("开票日期", "未识别")
        total_amount = result_data["extracted_fields"].get("价税合计小写", "未识别")
        result_table_data = [[file_name, invoice_date, total_amount]]

        return json.dumps(result_data, ensure_ascii=False, indent=2), result_table_data, table_data
    except Exception as e:
        error_msg = f"图片处理失败: {str(e)}"
        return {"error": error_msg}, [["", "处理失败", error_msg]], [[0, "图片处理失败", "0.000"]]


def export_invoice_config(confidence_threshold):
    """导出发票配置"""
    config_data = {
        "supported_invoice_types": get_invoice_types_list(),
        "confidence_threshold": confidence_threshold,
        "return_format": "JSON格式",
        "field_patterns": get_all_field_patterns(),
        "export_time": datetime.now().isoformat()
    }
    return json.dumps(config_data, ensure_ascii=False, indent=2)


# 加载自定义CSS样式
custom_css = load_custom_css()

# 创建Gradio界面
with gr.Blocks(
    title="🧾 发票OCR专用识别系统"
) as demo:
    gr.HTML(f'<style>{custom_css}</style>')

    with gr.Row():
        gr.HTML(
            """
            <div class="header-section fade-in-up">
                <h1 class="header-title">🧾 发票OCR专用识别系统</h1>
                <p class="header-subtitle">基于AI的智能发票识别与字段提取平台</p>
            </div>
            """
        )

    with gr.Row():
        with gr.Column(scale=1):
            with gr.Group(elem_classes="input-section fade-in-up"):
                gr.HTML('<div class="input-title">📄 上传发票文件</div>')
                with gr.Tabs():
                    with gr.Tab("PDF发票"):
                        pdf_input = gr.File(label="上传PDF发票", file_types=[".pdf"], file_count="multiple", elem_classes="image-upload")
                        confidence_pdf = gr.Slider(label="🎯 置信度阈值", minimum=0.1, maximum=1.0, value=0.5, step=0.1)
                        with gr.Row():
                            run_btn_pdf = gr.Button("🚀 开始识别", variant="primary", size="lg", elem_classes="gr-button")
                    with gr.Tab("图片发票"):
                        img_input = gr.Image(label="上传发票图片", type="filepath", elem_classes="image-upload")
                        confidence_img = gr.Slider(label="🎯 置信度阈值", minimum=0.1, maximum=1.0, value=0.5, step=0.1)
                        with gr.Row():
                            run_btn_img = gr.Button("🚀 开始识别", variant="primary", size="lg", elem_classes="gr-button")

        with gr.Column(scale=1):
            with gr.Group(elem_classes="output-section fade-in-up"):
                gr.HTML('<div class="input-title">📊 识别结果</div>')
                progress_bar = gr.Progress()

                result_table = gr.Dataframe(
                    label="发票识别结果",
                    headers=["文件名", "开票日期", "价税合计小写"],
                    datatype=["str", "str", "str"],
                    elem_classes="gr-databox"
                )

                download_output = gr.DownloadButton("📥 导出并下载结果", variant="primary")

                with gr.Tabs():
                    with gr.TabItem("🎯 JSON格式"):
                        result_output = gr.Textbox(label="", lines=12, max_lines=15, elem_classes="gr-textbox")
                    with gr.TabItem("📝 原始文本"):
                        table_output = gr.Dataframe(label="", headers=["序号", "文本内容", "置信度"], datatype=["number", "str", "number"], elem_classes="gr-databox")

    # 绑定PDF发票按钮事件
    run_btn_pdf.click(
        fn=process_pdf_invoice,
        inputs=[pdf_input, confidence_pdf],
        outputs=[result_output, result_table, table_output]
    )

    # 绑定图片发票按钮事件
    run_btn_img.click(
        fn=process_with_fields_image,
        inputs=[img_input, confidence_img],
        outputs=[result_output, result_table, table_output]
    )

    # 绑定导出下载按钮事件
    download_output.click(
        fn=export_table_data,
        inputs=[result_table],
        outputs=[download_output]
    )

if __name__ == "__main__":
    demo.launch(mcp_server=True, server_name="0.0.0.0")
```

- [ ] **Step 2: Verify app.py can be parsed**

Run: `python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Run full test suite to ensure nothing broke**

Run: `python -m pytest tests/ -v`
Expected: All tests pass (13 tests)

- [ ] **Step 4: Verify app.py imports work (without launching Gradio)**

Run: `python -c "from ocr_engine import InvoiceImageProcessor; from export import export_table_data; print('imports OK')"`
Expected: `imports OK`

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "refactor: slim app.py to use new modules + remove dead code
- InvoiceCORProcessor replaced with InvoiceImageProcessor from ocr_engine
- export_table_data imported from export module
- Removed create_invoice_examples (referenced missing images)
- Removed process_mixed_input dead code path
- Updated CLAUDE.md to reflect new structure"
```

---

### Task 6: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md Architecture section to reflect new file structure**

Replace the Architecture section with:

```markdown
## Architecture

```
app.py                ─ Gradio web UI (UI components + event binding)
ocr_engine.py         ─ PDF-to-image, file type detection, InvoiceImageProcessor facade
field_extractor.py    ─ InvoiceFieldExtractor: type detection + regex field extraction
export.py             ─ Excel export with total row
invoice_config.py     ─ Regex patterns per invoice type (configuration, unchanged)
styles.css            ─ Custom CSS for Gradio UI
requirements.txt      ─ Dependencies: gradio, rapidocr, PyMuPDF, Pillow, pandas, openpyxl, pytest
tests/                ─ pytest unit tests
  test_field_extractor.py  ─ Tests for detect_invoice_type + extract_fields
  test_export.py           ─ Tests for export_table_data
```

**Core flow:**
1. User uploads image(s) or PDF(s) via Gradio UI (two tabs: PDF tab, Image tab)
2. PDFs are rendered to images via PyMuPDF (`fitz`), first page only (ocr_engine.py)
3. RapidOCR extracts raw text from the image (ocr_engine.py)
4. `InvoiceFieldExtractor` detects invoice type by keyword matching, then extracts fields via regex (field_extractor.py)
5. Currently only two fields are actively extracted and displayed: **开票日期** (invoice date) and **价税合计小写** (total amount with tax)
6. Results shown in a Dataframe table + JSON detail view; exportable to Excel via export.py
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with refactored file structure"
```

- [ ] **Step 3: Update requirements.txt to include pytest**

Add `pytest` to requirements.txt.

- [ ] **Step 4: Final commit**

```bash
git add requirements.txt
git commit -m "chore: add pytest to requirements.txt"
```
