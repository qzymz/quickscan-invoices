# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QuickScan Invoices — a FastAPI web app with native HTML/CSS/JS frontend that uses RapidOCR to extract structured fields (date, total amount) from uploaded invoice images and PDFs. Supports 5 invoice types (VAT special, VAT ordinary, electronic, machine-printed, handwritten).

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app (default: localhost:8000)
uvicorn main:app --reload

# Run on custom host/port
uvicorn main:app --host 0.0.0.0 --port 8080
```

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

**API endpoints:**
- `GET /` — Serves the frontend HTML page
- `POST /api/recognize` — Single file recognition (image or PDF)
- `POST /api/batch-recognize` — Batch file recognition, returns task_id for polling
- `GET /api/status/{task_id}` — Poll task progress and results
- `POST /api/export` — Export table data as Excel file download

**Key modules:**
- `main.py` — FastAPI application with API routes, static file serving, and background task management
- `ocr_engine.py` — `InvoiceImageProcessor.process_invoice()` runs OCR, delegates field extraction
- `field_extractor.py` — `InvoiceFieldExtractor.detect_invoice_type()`, `extract_fields()`, `validate()`
- `export.py` — `export_table_data()` writes Excel with total row

**Key patterns in `invoice_config.py`:**
- `INVOICE_TYPES` — defines 5 invoice types with keyword lists and regex field patterns
- `COMMON_FIELD_PATTERNS`, `AMOUNT_PATTERNS`, `TAX_PATTERNS`, `DATE_PATTERNS` — reusable regex
- `validate_invoice_data()` — checks required fields (开票日期, 价税合计小写)

## Important Notes

- The system currently extracts only **开票日期** and **价税合计小写** in the UI table, despite `invoice_config.py` defining many more field patterns
- Verification: `python -m pytest tests/ -v` (20 tests)
