use serde::Serialize;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::{Emitter, Manager};

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
    let mut child = state.child.lock().unwrap();
    match child.as_mut() {
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
            let sidecar_path = app
                .path()
                .resolve(
                    "sidecar/quickscan-sidecar/quickscan-sidecar.exe",
                    tauri::path::BaseDirectory::Resource,
                )
                .expect("Failed to resolve sidecar resource path");

            if !sidecar_path.exists() {
                // In dev mode without bundled sidecar, fall back to python + uvicorn
                #[cfg(debug_assertions)]
                {
                    println!(
                        "Sidecar not found at {:?}, using python uvicorn directly",
                        sidecar_path
                    );
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
