# Tauri 2 Desktop Packaging Design

**Date:** 2026-05-12
**Status:** Approved

## Problem

QuickScan Invoices is currently a FastAPI web app that requires users to manually start `uvicorn main:app` and access `localhost:8000` in a browser. Goal: package as a desktop application users can launch with a double-click.

## Decision

Keep all existing Python code and frontend code unchanged. Add a Tauri 2 shell that:
1. Starts FastAPI as a child process (sidecar) on application launch
2. Embeds the existing HTML/CSS/JS frontend in its WebView
3. Cleans up the child process on exit

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 Tauri 2 App                     │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │           WebView (Frontend)              │  │
│  │  index.html + style.css + app.js          │  │
│  │  Fetch → http://localhost:{port}/api/*    │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌────────────────────────────────────────────┐  │
│  │         Rust Layer (Tauri commands)        │  │
│  │  - setup(): start Python sidecar           │  │
│  │  - on_exit(): kill sidecar                 │  │
│  │  - get_port() → return port to frontend    │  │
│  └────────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │         Python Sidecar (child process)     │  │
│  │  uvicorn main:app --port {random}          │  │
│  │  ├── FastAPI + Jinja2 templates            │  │
│  │  ├── InvoiceImageProcessor (RapidOCR)      │  │
│  │  └── InvoiceFieldExtractor (regex)         │  │
│  └─────────────────────────────────────────────┘  │
│                                                   │
└───────────────────────────────────────────────────┘
```

## New Components

### 1. PyInstaller Sidecar Build

- All Python dependencies (FastAPI, uvicorn, RapidOCR, PyMuPDF, Pillow, pandas, openpyxl) packaged into a single `.exe` via PyInstaller
- Custom entry script that reads port from CLI arg (`--port`) or environment variable
- Sidecar outputs the bound port to stdout so Rust can capture it
- Built separately from Tauri, output placed in `src-tauri/sidecar/`

### 2. Tauri 2 Shell

- **`src-tauri/Cargo.toml`** — Rust dependencies: `tauri`, `tauri-plugin-shell`
- **`src-tauri/tauri.conf.json`** — Tauri config: app name, bundle targets, security (CSP), dev/prod paths
- **`src-tauri/src/lib.rs`** — Plugin setup/teardown:
  - `setup()`: spawn sidecar executable from `tauri.conf` resources, capture port from stdout, store port in app state
  - `get_port()` command: frontend invokes this to get the sidecar's port
  - `on_exit()`: kill the sidecar process
- **`src-tauri/dist/`** — contains existing frontend files (index.html, css/, js/)

### 3. Frontend Port Discovery

- Frontend JS calls `invoke('get_port')` on page load
- Sets `window.API_BASE = http://localhost:{port}`
- All existing Fetch calls unchanged, just using dynamic base URL

## Data Flow

1. User double-clicks QuickScan Invoices
2. Tauri launches, runs `setup()` which spawns the Python sidecar
3. Sidecar starts uvicorn on a random available port, prints it to stdout
4. Rust captures port, stores it in `State<PortStore>`
5. Frontend loads, calls `invoke('get_port')`, receives port number
6. Frontend sets `API_BASE` and makes Fetch calls as before
7. User closes app → `on_exit()` kills sidecar process

## Error Handling

- **Sidecar fails to start** — show Tauri dialog: "OCR 引擎启动失败，请检查安装"
- **Port already in use** — sidecar tries next available port
- **Sidecar crashes during operation** — frontend detects connection error, shows "服务已断开" dialog
- **Graceful shutdown** — `on_exit()` sends SIGTERM, waits 3s, then SIGKILL

## Build Artifacts

- **Development**: `tauri dev` — uses existing Python virtualenv, no sidecar packaging needed
- **Production**: `tauri build` — bundles sidecar exe + frontend into native Windows installer (`.msi` or `.exe`)

## Scope

- Windows only for now, architecture does not hardcode Windows paths
- No changes to existing Python business logic, OCR engine, field extractor, or export modules
- No changes to existing frontend HTML/CSS/JS logic
