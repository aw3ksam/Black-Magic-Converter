"""
Embedded HTTP and SSE Event Stream Server for Blackmagic Camera Tooling.
Provides static dashboard serving and REST/SSE API endpoints.
"""

from __future__ import annotations
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import logging
import os
from pathlib import Path
import queue
import socketserver
import sys
import threading
import time
from typing import Any, Dict, List, Optional
import urllib.parse

from .camera_client import CameraClient
from .ftp_client import FtpClient
from .tool_auto_transfer import AutoTransferTool
from .tool_batch_recorder import BatchRecorderTool

logger = logging.getLogger("bm_camera.server")


class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        """Suppress benign client disconnect exceptions."""
        exc_type, exc_val, _ = sys.exc_info()
        if exc_type in (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            logger.debug(f"Client {client_address} disconnected: {exc_val}")
            return
        super().handle_error(request, client_address)


class ToolingEngine:
    """Core coordinator engine wrapping camera, FTP, Tool 1, and Tool 2."""

    def __init__(
        self,
        camera_ip: str = "192.168.8.133",
        ftp_host: Optional[str] = None,
        dest_dir: str = "./transfers",
    ):
        self.camera_ip = camera_ip
        self.ftp_host = ftp_host or camera_ip
        self.dest_dir = Path(dest_dir)

        self.camera_client = CameraClient(host=self.camera_ip)
        self.ftp_client = FtpClient(host=self.ftp_host)

        # Event broadcaster for SSE clients
        self.sse_subscribers: List[queue.Queue] = []
        self._sse_lock = threading.Lock()

        # Tools
        self.tool1 = AutoTransferTool(
            camera_client=self.camera_client,
            ftp_client=self.ftp_client,
            dest_dir=self.dest_dir,
            on_event_cb=self.broadcast_event,
        )

        self.tool2 = BatchRecorderTool(
            camera_client=self.camera_client,
            on_event_cb=self.broadcast_event,
        )

    def broadcast_event(self, event: Dict[str, Any]):
        """Broadcasts an event to all connected SSE clients."""
        with self._sse_lock:
            for q in list(self.sse_subscribers):
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass

    def add_sse_subscriber(self) -> queue.Queue:
        q = queue.Queue(maxsize=100)
        with self._sse_lock:
            self.sse_subscribers.append(q)
        return q

    def remove_sse_subscriber(self, q: queue.Queue):
        with self._sse_lock:
            if q in self.sse_subscribers:
                self.sse_subscribers.remove(q)

    def get_system_summary(self) -> Dict[str, Any]:
        """Fetch unified camera telemetry and tool states."""
        product_info = {}
        active_disk = {}
        recording_state = False
        connected = False

        try:
            product_info = self.camera_client.get_product()
            recording_state = self.camera_client.get_record_state()
            workingset = self.camera_client.get_workingset()
            if workingset:
                active_disk = workingset[0]
            connected = True
        except Exception as e:
            logger.debug(f"Camera poll status error: {e}")
            connected = False

        return {
            "connected": connected,
            "camera_ip": self.camera_ip,
            "ftp_host": self.ftp_host,
            "product": product_info,
            "recording": recording_state,
            "active_disk": active_disk,
            "tool1": self.tool1.get_status(),
            "tool2": self.tool2.get_status(),
            "timestamp": datetime.now().isoformat(),
        }


def make_request_handler(engine: ToolingEngine, static_dir: Path):
    """Creates a custom HTTP request handler bound to the tooling engine."""

    class CameraDashboardHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(static_dir), **kwargs)

        def log_message(self, format, *args):
            # Suppress excessive static file polling logs
            if "/api/events" not in str(args) and "/api/status" not in str(args):
                logger.debug("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), format % args))

        def _send_json(self, data: Any, status: int = 200):
            payload = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(payload)

        def _parse_body(self) -> Dict[str, Any]:
            content_len = int(self.headers.get("Content-Length", 0))
            if content_len > 0:
                raw = self.rfile.read(content_len).decode("utf-8")
                try:
                    return json.loads(raw)
                except Exception:
                    return {}
            return {}

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path

            if path == "/api/status":
                self._send_json(engine.get_system_summary())
                return

            elif path == "/api/formats":
                opts = engine.tool2.get_supported_options()
                self._send_json(opts)
                return

            elif path == "/api/tool1/status":
                self._send_json(engine.tool1.get_status())
                return

            elif path == "/api/tool2/status":
                self._send_json(engine.tool2.get_status())
                return

            elif path == "/api/events":
                # Server-Sent Events (SSE) Stream
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()

                client_q = engine.add_sse_subscriber()
                try:
                    # Initial state
                    init_data = f"data: {json.dumps({'type': 'init', 'data': engine.get_system_summary()})}\n\n"
                    self.wfile.write(init_data.encode("utf-8"))
                    self.wfile.flush()

                    while True:
                        try:
                            msg = client_q.get(timeout=2.0)
                            sse_line = f"data: {json.dumps(msg)}\n\n"
                            self.wfile.write(sse_line.encode("utf-8"))
                            self.wfile.flush()
                        except queue.Empty:
                            # Keep-alive heartbeat ping
                            heartbeat = f"data: {json.dumps({'type': 'ping', 'timestamp': time.time()})}\n\n"
                            self.wfile.write(heartbeat.encode("utf-8"))
                            self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
                finally:
                    engine.remove_sse_subscriber(client_q)
                return

            # Default fallback to static file serving
            super().do_GET()

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            body = self._parse_body()

            if path == "/api/tool1/toggle":
                enable = body.get("active", not engine.tool1.is_active)
                import_today = body.get("import_today", False)
                if enable:
                    res = engine.tool1.activate(auto_import_same_day=import_today)
                else:
                    res = engine.tool1.deactivate()
                self._send_json(res)
                return

            elif path == "/api/tool1/import-today":
                res = engine.tool1.import_same_day_clips()
                self._send_json(res)
                return

            elif path == "/api/tool1/config":
                dest = body.get("dest_dir")
                if dest:
                    engine.tool1.dest_dir = Path(dest)
                    engine.dest_dir = Path(dest)
                self._send_json({"success": True, "dest_dir": str(engine.dest_dir)})
                return

            elif path == "/api/tool2/start":
                duration = int(body.get("clip_duration", 60))
                custom_count = body.get("custom_clip_count")
                codec = body.get("codec")
                res = body.get("record_resolution")
                fps = body.get("frame_rate")
                result = engine.tool2.start_batch(
                    clip_duration=duration,
                    custom_clip_count=custom_count,
                    codec=codec,
                    record_resolution=res,
                    frame_rate=fps,
                )
                self._send_json(result)
                return

            elif path == "/api/tool2/pause":
                self._send_json(engine.tool2.pause_batch())
                return

            elif path == "/api/tool2/resume":
                self._send_json(engine.tool2.resume_batch())
                return

            elif path == "/api/tool2/stop":
                self._send_json(engine.tool2.stop_batch())
                return

            self._send_json({"error": "Endpoint not found"}, status=404)

    return CameraDashboardHandler


def start_server(
    host: str = "0.0.0.0",
    port: int = 8080,
    camera_ip: str = "192.168.8.133",
    ftp_host: Optional[str] = None,
    dest_dir: str = "./transfers",
    static_dir: Optional[Path] = None,
) -> ThreadedHTTPServer:
    """Start the dashboard web server."""
    if static_dir is None:
        static_dir = Path(__file__).resolve().parent.parent / "dashboard"

    engine = ToolingEngine(camera_ip=camera_ip, ftp_host=ftp_host, dest_dir=dest_dir)
    handler_class = make_request_handler(engine, static_dir)
    server = ThreadedHTTPServer((host, port), handler_class)

    logger.info(f"Dashboard server running at http://localhost:{port}")
    return server
