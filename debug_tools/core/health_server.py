"""
Embedded Health & Status API Server for black-magic-converter.
Complies with Section 4.6 of the Reliability & Observability Specification.
Runs a lightweight HTTP server in a daemon thread on 127.0.0.1:8765.
"""

import os
import sys
import time
import json
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Callable, Dict, Any


class AppStateHolder:
    """Thread-safe application status tracker."""

    def __init__(self):
        self._lock = threading.Lock()
        self.start_time = time.time()
        self.state = "IDLE"  # IDLE, STABILIZING, TRANSCODING, SHUTDOWN, ERROR
        self.active_job_id: Optional[str] = None
        self.input_file: Optional[str] = None
        self.output_file: Optional[str] = None
        self.frames_processed: int = 0
        self.total_frames: int = 0
        self.instantaneous_fps: float = 0.0
        self.job_start_time: Optional[float] = None
        self.shutdown_handler: Optional[Callable[[], None]] = None

    def set_idle(self):
        with self._lock:
            self.state = "IDLE"
            self.active_job_id = None
            self.input_file = None
            self.output_file = None
            self.frames_processed = 0
            self.total_frames = 0
            self.instantaneous_fps = 0.0
            self.job_start_time = None

    def set_stabilizing(self, filename: str, job_id: Optional[str] = None):
        with self._lock:
            self.state = "STABILIZING"
            self.input_file = filename
            self.active_job_id = job_id or f"job_{int(time.time())}"
            self.job_start_time = time.time()

    def set_transcoding(
        self,
        input_file: str,
        output_file: Optional[str] = None,
        job_id: Optional[str] = None,
        total_frames: int = 0,
    ):
        with self._lock:
            self.state = "TRANSCODING"
            self.input_file = input_file
            self.output_file = output_file
            self.active_job_id = job_id or self.active_job_id
            self.total_frames = total_frames
            self.frames_processed = 0
            self.instantaneous_fps = 0.0
            if not self.job_start_time:
                self.job_start_time = time.time()

    def update_progress(self, frames_processed: int, total_frames: Optional[int] = None, fps: float = 0.0):
        with self._lock:
            self.frames_processed = frames_processed
            if total_frames and total_frames > 0:
                self.total_frames = total_frames
            self.instantaneous_fps = fps

    def get_status_dict(self) -> Dict[str, Any]:
        with self._lock:
            elapsed_sec = (time.time() - self.job_start_time) if self.job_start_time else 0.0
            estimated_remaining = 0.0
            if self.instantaneous_fps > 0 and self.total_frames > self.frames_processed:
                estimated_remaining = round((self.total_frames - self.frames_processed) / self.instantaneous_fps, 1)

            return {
                "state": self.state,
                "active_job_id": self.active_job_id,
                "input_file": self.input_file,
                "output_file": self.output_file,
                "frames_processed": self.frames_processed,
                "total_frames": self.total_frames,
                "instantaneous_fps": round(self.instantaneous_fps, 2),
                "elapsed_sec": round(elapsed_sec, 2),
                "estimated_remaining_sec": estimated_remaining,
            }

    def get_health_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": "healthy",
                "uptime_sec": round(time.time() - self.start_time, 1),
                "pid": os.getpid(),
                "state": self.state,
            }

    def is_ready(self) -> bool:
        with self._lock:
            return self.state == "IDLE"


# Global state instance
global_app_state = AppStateHolder()


class HealthRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for health, status, ready, and shutdown."""

    def log_message(self, format, *args):
        # Silence default stderr logging from BaseHTTPRequestHandler
        pass

    def _send_json(self, status_code: int, data: Dict[str, Any]):
        try:
            body = json.dumps(data, indent=2).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def _send_html(self, status_code: int, html_content: str):
        try:
            body = html_content.encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/dashboard"):
            dashboard_file = Path(__file__).resolve().parent.parent / "dashboard.html"
            if dashboard_file.is_file():
                with open(dashboard_file, "r", encoding="utf-8") as f:
                    self._send_html(200, f.read())
            else:
                self._send_html(200, "<h1>Black Magic Converter Debug Dashboard</h1><p>dashboard.html not found.</p>")
        elif path == "/health":
            self._send_json(200, global_app_state.get_health_dict())
        elif path == "/status":
            self._send_json(200, global_app_state.get_status_dict())
        elif path == "/ready":
            if global_app_state.is_ready():
                self._send_json(200, {"ready": True, "state": "IDLE"})
            else:
                self._send_json(503, {"ready": False, "state": global_app_state.state})
        else:
            self._send_json(404, {"error": "Not Found", "available_routes": ["/dashboard", "/health", "/status", "/ready", "/shutdown"]})

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/shutdown":
            self._send_json(200, {"status": "shutting_down", "pid": os.getpid()})
            if global_app_state.shutdown_handler:
                threading.Thread(target=global_app_state.shutdown_handler, daemon=True).start()
        else:
            self._send_json(404, {"error": "Not Found"})


class HealthServer:
    """Embedded HTTP server wrapper running in a background thread."""

    def __init__(self, host: str = "127.0.0.1", port: int = 8765):
        self.host = host
        self.port = port
        self.httpd: Optional[HTTPServer] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False

    def start(self, shutdown_callback: Optional[Callable[[], None]] = None):
        if self.running:
            return

        if shutdown_callback:
            global_app_state.shutdown_handler = shutdown_callback

        try:
            # Allow port reuse to avoid address already in use after rapid restarts
            class ReusableHTTPServer(HTTPServer):
                allow_reuse_address = True

            self.httpd = ReusableHTTPServer((self.host, self.port), HealthRequestHandler)
            self.running = True
            self.thread = threading.Thread(
                target=self.httpd.serve_forever,
                name="HealthServerThread",
                daemon=True,
            )
            self.thread.start()
        except Exception as e:
            sys.stderr.write(f"Warning: Could not bind HealthServer to {self.host}:{self.port}: {e}\n")

    def stop(self):
        self.running = False
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass


_server_instance: Optional[HealthServer] = None
_server_lock = threading.Lock()


def start_health_server(host: str = "127.0.0.1", port: int = 8765, shutdown_callback: Optional[Callable[[], None]] = None) -> HealthServer:
    """Starts singleton health server if not already running."""
    global _server_instance
    with _server_lock:
        if _server_instance is None:
            _server_instance = HealthServer(host=host, port=port)
            _server_instance.start(shutdown_callback=shutdown_callback)
        return _server_instance
