# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Invoice OCR Recognition System (发票OCR识别系统) — a Gradio-based web app that uses RapidOCR to extract structured fields (date, total amount) from uploaded invoice images and PDFs. Supports 5 invoice types (VAT special, VAT ordinary, electronic, machine-printed, handwritten).

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app (default: localhost:7860)
python app.py

# Run with MCP server mode
python app.py --mcp-server

# Run on custom host/port
python app.py --host 0.0.0.0 --port 8080
```

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

**Key modules:**
- `ocr_engine.py` — `InvoiceImageProcessor.process_invoice()` runs OCR, delegates field extraction
- `field_extractor.py` — `InvoiceFieldExtractor.detect_invoice_type()`, `extract_fields()`, `validate()`
- `export.py` — `export_table_data()` writes Excel with total row
- `app.py` — Gradio UI components + event binding, imports from above modules

**Key patterns in `invoice_config.py`:**
- `INVOICE_TYPES` — defines 5 invoice types with keyword lists and regex field patterns
- `COMMON_FIELD_PATTERNS`, `AMOUNT_PATTERNS`, `TAX_PATTERNS`, `DATE_PATTERNS` — reusable regex
- `validate_invoice_data()` — checks required fields (开票日期, 价税合计小写)

## Important Notes

- The system currently extracts only **开票日期** and **价税合计小写** in the UI table, despite `invoice_config.py` defining many more field patterns
- The app defaults to `mcp_server=True` in `demo.launch()`
- Verification: `python -m pytest tests/ -v` (20 tests)
