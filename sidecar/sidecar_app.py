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
