# Tauri 2 Desktop Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the existing FastAPI + HTML/CSS/JS QuickScan Invoices app as a Tauri 2 desktop application with automatic Python sidecar management.

**Architecture:** Tauri 2 shell embeds the existing frontend in a WebView, launches the FastAPI app as a child process (sidecar) on startup, and kills it on exit. Frontend discovers the sidecar's port via a Tauri `invoke('get_port')` call.

**Tech Stack:** Tauri 2, Rust, PyInstaller, Python/FastAPI, WebView2 (Windows)

---

### Task 1: Install prerequisites and initialize Tauri 2 project

**Files:**
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/src/lib.rs`
- Create: `src-tauri/src/main.rs`
- Create: `src-tauri/build.rs`
- Create: `src-tauri/icons/` (placeholder)
- Create: `src-tauri/capabilities/default.json`
- Create: `package.json`

- [ ] **Step 1: Install Rust toolchain**

```bash
# On Windows, use rustup installer
curl --proto '=https' --tlsv1.2 -sSf https://win.rustup.rs | sh
# Then restart shell and verify:
cargo --version
rustc --version
```

If Rust is already installed, skip this step.

- [ ] **Step 2: Install Tauri CLI**

```bash
cargo install tauri-cli --version "^2"
# Or via npm:
npm install -g @tauri-apps/cli
```

- [ ] **Step 3: Create `package.json`**

```json
{
  "name": "quickscan-invoices",
  "version": "1.0.0",
  "description": "QuickScan Invoices - Invoice OCR Desktop App",
  "scripts": {
    "tauri": "tauri",
    "tauri:dev": "tauri dev",
    "tauri:build": "tauri build"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2"
  }
}
```

- [ ] **Step 4: Initialize Tauri 2 project structure**

```bash
cd D:/trae/quickscan-invoices
mkdir -p src-tauri/src src-tauri/capabilities src-tauri/icons
```

- [ ] **Step 5: Create `src-tauri/tauri.conf.json`**

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "QuickScan Invoices",
  "version": "1.0.0",
  "identifier": "com.quickscan.invoices",
  "build": {
    "frontendDist": "../src-tauri/dist",
    "devUrl": "http://localhost:8000",
    "beforeDevCommand": "",
    "beforeBuildCommand": ""
  },
  "app": {
    "withGlobalTauri": true,
    "windows": [
      {
        "title": "QuickScan · 发票识别终端",
        "width": 1400,
        "height": 900,
        "resizable": true,
        "fullscreen": false
      }
    ],
    "security": {
      "csp": "default-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self' http://localhost:*; font-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; img-src 'self' data: blob:;"
    }
  },
  "bundle": {
    "active": true,
    "targets": ["msi"],
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ],
    "resources": {
      "sidecar/*": "sidecar/"
    }
  }
}
```

- [ ] **Step 6: Create `src-tauri/Cargo.toml`**

```toml
[package]
name = "quickscan-invoices"
version = "1.0.0"
description = "QuickScan Invoices - Invoice OCR Desktop App"
authors = []
edition = "2021"

[lib]
name = "quickscan_invoices_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[[bin]]
name = "quickscan-invoices"
path = "src/main.rs"

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-shell = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
portpicker = "0.1"
```

- [ ] **Step 7: Create `src-tauri/build.rs`**

```rust
fn main() {
    tauri_build::build()
}
```

- [ ] **Step 8: Commit**

```bash
git add package.json src-tauri/tauri.conf.json src-tauri/Cargo.toml src-tauri/build.rs
git commit -m "feat: initialize Tauri 2 project structure"
```

---

### Task 2: Create Python sidecar entry point and PyInstaller spec

**Files:**
- Create: `sidecar/sidecar_app.py`
- Create: `sidecar/sidecar.spec`
- Create: `sidecar/build_sidecar.bat`

- [ ] **Step 1: Create `sidecar/sidecar_app.py`**

This is the sidecar entry point. It reads port from CLI args, starts uvicorn on that port, and prints `READY:<port>` to stdout when bound.

```python
# -*- coding: utf-8 -*-
"""Sidecar entry point — starts uvicorn with the QuickScan FastAPI app."""

import sys
import os
import socket
import signal

# Ensure the project root is on sys.path so imports like `main` resolve.
# In PyInstaller bundle, _MEIPASS contains the packed files.
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    sys.path.insert(0, BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, BASE_DIR)


def find_free_port(start: int = 0) -> int:
    """Ask the OS for a free port, or use the provided start port."""
    if start > 0:
        return start
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    # Parse --port argument
    port = 0
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    port = find_free_port(port)

    # Print ready signal to stdout (captured by Rust)
    print(f"READY:{port}", flush=True)

    # Set environment for uvicorn to find the app module
    os.environ["PYTHONPATH"] = BASE_DIR

    import uvicorn
    from main import app

    # Handle SIGTERM for graceful shutdown
    def handle_signal(signum, frame):
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create `sidecar/sidecar.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
a = Analysis(
    ['sidecar_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../templates', 'templates'),
        ('../static', 'static'),
    ],
    hiddenimports=[
        'main',
        'ocr_engine',
        'field_extractor',
        'export',
        'invoice_config',
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        'rapidocr',
        'fitz',
        'PIL',
        'numpy',
        'pandas',
        'openpyxl',
        'fastapi',
        'jinja2',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='quickscan-sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='quickscan-sidecar',
)
```

- [ ] **Step 3: Create `sidecar/build_sidecar.bat`**

```bat
@echo off
echo Building sidecar with PyInstaller...
cd /d "%~dp0"
pip install pyinstaller
pyinstaller --clean sidecar.spec
echo Build complete: dist\quickscan-sidecar\
```

- [ ] **Step 4: Commit**

```bash
git add sidecar/sidecar_app.py sidecar/sidecar.spec sidecar/build_sidecar.bat
git commit -m "feat: add Python sidecar entry point and PyInstaller spec"
```

---

### Task 3: Implement Rust sidecar management (lib.rs)

**Files:**
- Create: `src-tauri/src/lib.rs`
- Create: `src-tauri/src/main.rs`

- [ ] **Step 1: Create `src-tauri/src/main.rs`**

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    quickscan_invoices_lib::run()
}
```

- [ ] **Step 2: Create `src-tauri/src/lib.rs`**

```rust
use serde::Serialize;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Emitter;

struct AppState {
    port: u16,
    child: Mutex<Option<Child>>,
}

#[derive(Serialize)]
struct PortResponse {
    port: u16,
}

#[tauri::command]
fn get_port(state: tauri::State<AppState>) -> PortResponse {
    PortResponse { port: state.port }
}

#[tauri::command]
fn sidecar_status(state: tauri::State<AppState>) -> String {
    let child = state.child.lock().unwrap();
    match &*child {
        Some(c) => match c.try_wait() {
            Ok(Some(status)) => format!("Exited: {}", status),
            Ok(None) => "Running".to_string(),
            Err(e) => format!("Error: {}", e),
        },
        None => "Not started".to_string(),
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            // Find a free port
            let port = portpicker::pick_unused_port().expect("No free ports available");

            // Determine sidecar path
            #[cfg(debug_assertions)]
            let sidecar_path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                .parent()
                .unwrap()
                .join("sidecar")
                .join("dist")
                .join("quickscan-sidecar")
                .join("quickscan-sidecar.exe");

            #[cfg(not(debug_assertions))]
            let sidecar_path = app.path()
                .resolve("sidecar/quickscan-sidecar/quickscan-sidecar.exe", tauri::path::BaseDirectory::Resource)
                .expect("Failed to resolve sidecar resource path");

            if !sidecar_path.exists() {
                // In dev mode without bundled sidecar, fall back to python + uvicorn
                #[cfg(debug_assertions)]
                {
                    println!("Sidecar not found at {:?}, using python uvicorn directly", sidecar_path);
                    let project_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
                        .parent()
                        .unwrap()
                        .to_path_buf();

                    let child = Command::new("python")
                        .args([
                            "-m",
                            "uvicorn",
                            "main:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            &port.to_string(),
                        ])
                        .current_dir(&project_root)
                        .spawn();

                    match child {
                        Ok(c) => {
                            println!("Python sidecar started on port {}", port);
                            app.manage(AppState {
                                port,
                                child: Mutex::new(Some(c)),
                            });
                            return Ok(());
                        }
                        Err(e) => {
                            eprintln!("Failed to start Python sidecar: {}", e);
                            return Err(Box::new(std::io::Error::new(
                                std::io::ErrorKind::Other,
                                format!("无法启动 OCR 引擎: {}", e),
                            )));
                        }
                    }
                }

                #[cfg(not(debug_assertions))]
                {
                    return Err(Box::new(std::io::Error::new(
                        std::io::ErrorKind::NotFound,
                        "OCR 引擎未找到，请重新安装应用",
                    )));
                }
            }

            let child = Command::new(&sidecar_path)
                .args(["--port", &port.to_string()])
                .stdout(std::process::Stdio::piped())
                .stderr(std::process::Stdio::piped())
                .spawn();

            match child {
                Ok(c) => {
                    println!("Sidecar started on port {}", port);
                    app.manage(AppState {
                        port,
                        child: Mutex::new(Some(c)),
                    });
                    Ok(())
                }
                Err(e) => {
                    eprintln!("Failed to start sidecar: {}", e);
                    Err(Box::new(std::io::Error::new(
                        std::io::ErrorKind::Other,
                        format!("无法启动 OCR 引擎: {}", e),
                    )))
                }
            }
        })
        .on_window_event(|_window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                // Graceful shutdown handled in cleanup
            }
        })
        .invoke_handler(tauri::generate_handler![get_port, sidecar_status])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                // Kill sidecar process on exit
                let state = app_handle.try_state::<AppState>();
                if let Some(state) = state {
                    let mut child = state.child.lock().unwrap();
                    if let Some(ref mut c) = *child {
                        println!("Shutting down sidecar...");
                        let _ = c.kill();
                        let _ = c.wait();
                    }
                }
            }
        });
}
```

- [ ] **Step 3: Commit**

```bash
git add src-tauri/src/lib.rs src-tauri/src/main.rs
git commit -m "feat: implement Rust sidecar management with Tauri commands"
```

---

### Task 4: Add frontend port discovery and Tauri integration

**Files:**
- Modify: `templates/index.html` (add Tauri script reference)
- Modify: `static/js/app.js` (add port discovery)

- [ ] **Step 1: Modify `templates/index.html` — add Tauri integration block**

Add this block right before the existing `<script src="/static/js/app.js"></script>` line:

```html
    <!-- Tauri port discovery (only active in Tauri WebView) -->
    <script>
        (async function() {
            // Detect if running inside Tauri WebView
            const isTauri = typeof window.__TAURI__ !== 'undefined' ||
                            window.location.protocol === 'tauri:' ||
                            (window.__TAURI_INTERNALS__ !== undefined);

            if (!isTauri) {
                // Running in regular browser with uvicorn, use default port 8000
                window.API_BASE = 'http://localhost:8000';
                return;
            }

            try {
                // Wait for Tauri to be ready
                const { invoke } = window.__TAURI__.core;
                const result = await invoke('get_port');
                window.API_BASE = 'http://localhost:' + result.port;
                console.log('Tauri sidecar port:', result.port);
            } catch (e) {
                console.error('Failed to get sidecar port:', e);
                window.API_BASE = 'http://localhost:8000';
            }
        })();
    </script>
    <script src="/static/js/app.js"></script>
```

Remove the existing `<script src="/static/js/app.js"></script>` line and replace with the block above (which includes the script tag at the end).

- [ ] **Step 2: Modify `static/js/app.js` — use `window.API_BASE` instead of relative paths**

Replace the `/api/recognize` fetch call in `processImageBatch` (around line 423):

```javascript
const resp = await fetch(window.API_BASE + "/api/recognize", { method: "POST", body: formData });
```

Replace the `/api/batch-recognize` fetch call in `processPdfBatch` (around line 477):

```javascript
const resp = await fetch(window.API_BASE + "/api/batch-recognize", { method: "POST", body: formData });
```

Replace the `/api/status/` fetch call in `processPdfBatch` (around line 490):

```javascript
const statusResp = await fetch(window.API_BASE + "/api/status/" + task_id);
```

Replace the `/api/export` fetch call (around line 356):

```javascript
const resp = await fetch(window.API_BASE + "/api/export", {
```

- [ ] **Step 3: Add connection error handling**

Add this function near the top of the IIFE, after the `showToast` function:

```javascript
    // ========== API error detection ==========
    async function checkApiConnection() {
        try {
            const resp = await fetch(window.API_BASE + "/", { method: "GET" });
            return resp.ok;
        } catch (e) {
            return false;
        }
    }

    // Check API connection on load (only in Tauri)
    setTimeout(async () => {
        if (window.API_BASE && window.API_BASE.includes('localhost')) {
            const connected = await checkApiConnection();
            if (!connected) {
                showToast("无法连接到 OCR 服务，请重启应用", "error");
                const indicator = document.getElementById("status-indicator");
                if (indicator) {
                    indicator.className = "status-indicator error";
                    const label = indicator.querySelector(".status-label");
                    if (label) label.textContent = "离线";
                }
            }
        }
    }, 3000);
```

- [ ] **Step 4: Commit**

```bash
git add templates/index.html static/js/app.js
git commit -m "feat: add Tauri port discovery and API base URL integration"
```

---

### Task 5: Create Tauri dist directory and copy frontend assets

**Files:**
- Create: `src-tauri/dist/index.html`
- Create: `src-tauri/dist/css/style.css`
- Create: `src-tauri/dist/js/app.js`

- [ ] **Step 1: Create dist directory and copy assets**

The Tauri `frontendDist` config points to `src-tauri/dist`. In production builds, the frontend files go here. Create a build script or copy manually:

```bash
mkdir -p src-tauri/dist/css src-tauri/dist/js
cp templates/index.html src-tauri/dist/index.html
cp static/css/style.css src-tauri/dist/css/style.css
cp static/js/app.js src-tauri/dist/js/app.js
```

- [ ] **Step 2: Create `copy-dist.bat` for easy copying**

```bat
@echo off
echo Copying frontend assets to Tauri dist...
mkdir src-tauri\dist\css 2>nul
mkdir src-tauri\dist\js 2>nul
copy /Y templates\index.html src-tauri\dist\index.html
copy /Y static\css\style.css src-tauri\dist\css\style.css
copy /Y static\js\app.js src-tauri\dist\js\app.js
echo Done.
```

- [ ] **Step 3: Commit**

```bash
git add src-tauri/dist/ copy-dist.bat
git commit -m "feat: add frontend assets for Tauri production build"
```

---

### Task 6: Add placeholder icons and finalize bundle config

**Files:**
- Create: `src-tauri/icons/32x32.png` (or any valid PNG)
- Create: `src-tauri/icons/128x128.png`
- Create: `src-tauri/icons/128x128@2x.png`
- Create: `src-tauri/icons/icon.ico`
- Create: `src-tauri/capabilities/default.json`

- [ ] **Step 1: Generate placeholder icons**

Use Tauri's icon generator or create minimal PNG files. The simplest approach:

```bash
# Install tauri icon tool if using npm
npx @tauri-apps/cli icon path/to/source.png

# Or create minimal 32x32, 128x128 PNGs manually
# For now, create a minimal valid icon set using Python
python -c "
from PIL import Image
import os
os.makedirs('src-tauri/icons', exist_ok=True)
for size in [32, 128, 256]:
    img = Image.new('RGBA', (size, size), (12, 16, 23, 255))
    if size == 128:
        img.save('src-tauri/icons/128x128.png')
        img.save('src-tauri/icons/128x128@2x.png')
    elif size == 32:
        img.save('src-tauri/icons/32x32.png')
    elif size == 256:
        img.save('src-tauri/icons/icon.ico')
"
```

- [ ] **Step 2: Create `src-tauri/capabilities/default.json`**

```json
{
  "identifier": "default",
  "description": "Default capabilities for QuickScan Invoices",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "shell:allow-open"
  ]
}
```

- [ ] **Step 3: Commit**

```bash
git add src-tauri/icons/ src-tauri/capabilities/default.json
git commit -m "feat: add placeholder icons and default Tauri capabilities"
```

---

### Task 7: Test development mode

**Files:** No new files — verification step.

- [ ] **Step 1: Build sidecar for dev (or use python directly)**

In dev mode, the Rust code falls back to `python -m uvicorn main:app` if the sidecar exe is not found. Ensure Python dependencies are installed:

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: Run Tauri dev mode**

```bash
cd D:/trae/quickscan-invoices
# Option 1: Using cargo tauri (requires Rust)
cargo tauri dev

# Option 2: Using npm
npm install
npm run tauri:dev
```

Expected behavior:
1. Tauri window opens
2. Python uvicorn starts in background on a random port
3. Frontend loads in WebView
4. File upload and recognition work as before

- [ ] **Step 3: Verify all features**

- [ ] Upload image file → recognition works
- [ ] Upload PDF file → batch recognition works
- [ ] Export Excel → downloads file
- [ ] Close window → Python process terminates

---

### Task 8: Build production bundle

**Files:**
- Create: `sidecar/build_sidecar.bat` (already exists from Task 2)
- Modify: `src-tauri/tauri.conf.json` (already exists)

- [ ] **Step 1: Build the PyInstaller sidecar**

```bash
cd sidecar
build_sidecar.bat
# Output: sidecar/dist/quickscan-sidecar/quickscan-sidecar.exe
```

- [ ] **Step 2: Copy sidecar to Tauri resources**

```bash
mkdir -p src-tauri/sidecar
cp -r sidecar/dist/quickscan-sidecar src-tauri/sidecar/
```

- [ ] **Step 3: Copy frontend assets**

```bash
copy-dist.bat
```

- [ ] **Step 4: Run Tauri build**

```bash
cargo tauri build
# Or: npm run tauri:build
```

Expected output: `src-tauri/target/release/bundle/msi/QuickScan Invoices_x.x.x_x64_en-US.msi`

- [ ] **Step 5: Install and test the MSI**

Install the generated MSI and verify:
- Application launches on double-click
- OCR recognition works
- Excel export works
- Application closes cleanly
