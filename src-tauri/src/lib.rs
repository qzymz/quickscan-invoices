use serde::Serialize;
use std::fs::OpenOptions;
use std::io::Write;
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

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

fn log_to_file(exe_dir: &std::path::Path, line: &str) {
    let log_path = exe_dir.join("sidecar.log");
    if let Ok(mut f) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(log_path)
    {
        let _ = writeln!(f, "{}", line);
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
            let resource_path = app
                .path()
                .resolve(
                    "sidecar/quickscan-sidecar.exe",
                    tauri::path::BaseDirectory::Resource,
                )
                .ok();

            #[cfg(not(debug_assertions))]
            let sidecar_path = resource_path
                .filter(|p| p.exists())
                .unwrap_or_else(|| {
                    std::env::current_exe()
                        .ok()
                        .and_then(|exe| exe.parent().map(|p| p.to_path_buf()))
                        .unwrap_or_default()
                        .join("sidecar")
                        .join("quickscan-sidecar.exe")
                });

            if !sidecar_path.exists() {
                #[cfg(not(debug_assertions))]
                {
                    let exe_dir = std::env::current_exe()
                        .ok()
                        .and_then(|e| e.parent().map(|p| p.to_path_buf()))
                        .unwrap_or_default();
                    log_to_file(&exe_dir, &format!("Sidecar not found at {:?}", sidecar_path));
                    return Err(Box::new(std::io::Error::new(
                        std::io::ErrorKind::NotFound,
                        "OCR 引擎未找到，请确保 sidecar/quickscan-sidecar/quickscan-sidecar.exe 存在",
                    )));
                }
            }

            let sidecar_dir = sidecar_path
                .parent()
                .unwrap_or_else(|| std::path::Path::new("."))
                .to_path_buf();

            #[cfg(not(debug_assertions))]
            {
                let exe_dir = std::env::current_exe()
                    .ok()
                    .and_then(|e| e.parent().map(|p| p.to_path_buf()))
                    .unwrap_or_default();
                log_to_file(
                    &exe_dir,
                    &format!(
                        "Launching sidecar: {:?} (cwd: {:?}, port: {})",
                        sidecar_path, sidecar_dir, port
                    ),
                );
            }

            // Start sidecar without capturing stdout (prevents blocking)
            let child = Command::new(&sidecar_path)
                .current_dir(&sidecar_dir)
                .args(["--port", &port.to_string()])
                .spawn();

            let child = match child {
                Ok(c) => c,
                Err(e) => {
                    #[cfg(not(debug_assertions))]
                    {
                        let exe_dir = std::env::current_exe()
                            .ok()
                            .and_then(|e| e.parent().map(|p| p.to_path_buf()))
                            .unwrap_or_default();
                        log_to_file(&exe_dir, &format!("Failed to spawn: {}", e));
                    }
                    return Err(Box::new(std::io::Error::new(
                        std::io::ErrorKind::Other,
                        format!("无法启动 OCR 引擎: {}", e),
                    )));
                }
            };

            // We already know the port since we passed it via --port
            println!("Sidecar started on port {}", port);
            app.manage(AppState {
                port,
                child: Mutex::new(Some(child)),
            });
            Ok(())
        })
        .on_window_event(|_window, event| {
            if let tauri::WindowEvent::CloseRequested { api: _, .. } = event {
                // Graceful shutdown handled in cleanup
            }
        })
        .invoke_handler(tauri::generate_handler![get_port, sidecar_status])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
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
