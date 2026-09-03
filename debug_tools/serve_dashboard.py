#!/usr/bin/env python3
"""
Dedicated Standalone Dashboard Server for Black Magic Converter Debug Tools.
Serves interactive dashboard on http://127.0.0.1:8766 with live log streaming,
database queries, YAML config synchronization, and Blackmagic Camera Tooling (Tool 1 & Tool 2).
"""

import os
import sys
import json
import webbrowser
import argparse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from debug_tools.core.database import DatabaseManager
from src.camera.camera_client import CameraClient
from src.camera.ftp_client import FtpClient
from src.camera.tool_auto_transfer import AutoTransferTool
from src.camera.tool_batch_recorder import BatchRecorderTool


class CameraDebugManager:
    """Manages Camera Tool 1 and Tool 2 within the debug suite."""

    def __init__(
        self,
        camera_ip: str = "192.168.1.118",
        camera_ftp: str = "ftp://PYXIS-6K.local",
        dest_dir: Optional[str] = None,
    ):
        self.camera_ip = camera_ip
        self.camera_ftp = camera_ftp
        default_dest = Path(_repo_root) / "watch_folders" / "00_IN_INGEST"
        self.dest_dir = Path(dest_dir) if dest_dir else default_dest
        self.dest_dir.mkdir(parents=True, exist_ok=True)

        self.camera_client = CameraClient(host=self.camera_ip)
        self.ftp_client = FtpClient(host=self.camera_ftp)

        self.tool1 = AutoTransferTool(
            camera_client=self.camera_client,
            ftp_client=self.ftp_client,
            dest_dir=self.dest_dir,
        )
        self.tool2 = BatchRecorderTool(
            camera_client=self.camera_client,
        )

    def update_config(self, camera_ip: Optional[str] = None, camera_ftp: Optional[str] = None, dest_dir: Optional[str] = None):
        if camera_ip:
            self.camera_ip = camera_ip
            self.camera_client = CameraClient(host=self.camera_ip)
            self.tool1.camera = self.camera_client
            self.tool2.camera = self.camera_client
        if camera_ftp:
            self.camera_ftp = camera_ftp
            self.ftp_client = FtpClient(host=self.camera_ftp)
            self.tool1.ftp = self.ftp_client
        if dest_dir:
            self.dest_dir = Path(dest_dir)
            self.dest_dir.mkdir(parents=True, exist_ok=True)
            self.tool1.dest_dir = self.dest_dir

    def get_status(self) -> Dict[str, Any]:
        connected = False
        product = {}
        recording = False
        workingset = []
        try:
            product = self.camera_client.get_product()
            recording = self.camera_client.get_record_state()
            workingset = self.camera_client.get_workingset()
            connected = True
        except Exception:
            connected = False

        return {
            "connected": connected,
            "camera_ip": self.camera_ip,
            "camera_ftp": self.camera_ftp,
            "dest_dir": str(self.dest_dir),
            "product": product,
            "recording": recording,
            "active_disk": workingset[0] if workingset else None,
            "tool1": self.tool1.get_status(),
            "tool2": self.tool2.get_status(),
        }

    def test_connection(self, ip: Optional[str] = None, ftp_host: Optional[str] = None) -> Dict[str, Any]:
        target_ip = ip or self.camera_ip
        target_ftp = ftp_host or self.camera_ftp
        c_test = CameraClient(host=target_ip, timeout=3.0)
        f_test = FtpClient(host=target_ftp, timeout=3.0)

        http_ok = False
        ftp_ok = False
        product_name = ""
        error_msg = ""

        try:
            prod = c_test.get_product()
            http_ok = True
            product_name = prod.get("productName", prod.get("deviceName", "Blackmagic Camera"))
        except Exception as e:
            error_msg = f"REST Error: {e}"

        try:
            ftp_ok = f_test.test_connection()
        except Exception as e:
            if not error_msg:
                error_msg = f"FTP Error: {e}"
            else:
                error_msg += f" | FTP Error: {e}"

        return {
            "http_ok": http_ok,
            "ftp_ok": ftp_ok,
            "product_name": product_name,
            "error": error_msg,
            "camera_ip": target_ip,
            "camera_ftp": target_ftp,
        }


# Global singleton camera manager
camera_mgr = CameraDebugManager()


class DashboardServerHandler(BaseHTTPRequestHandler):
    """HTTP handler serving the dashboard, live logs, database records, and camera controls."""

    def log_message(self, format, *args):
        pass

    def _send_json(self, status_code: int, data: Any):
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status_code: int, content: str):
        body = content.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _parse_body(self) -> Dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len > 0:
            raw = self.rfile.read(content_len).decode("utf-8", errors="ignore")
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
        path = self.path.split("?")[0]
        params = {}
        if "?" in self.path:
            raw_params = self.path.split("?", 1)[1]
            for p in raw_params.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = v

        if path in ("/", "/dashboard"):
            dash_file = Path(__file__).resolve().parent / "dashboard.html"
            if dash_file.is_file():
                with open(dash_file, "r", encoding="utf-8") as f:
                    self._send_html(200, f.read())
            else:
                self._send_html(404, "<h1>dashboard.html not found</h1>")

        elif path == "/api/logs":
            stream = params.get("stream", "braw_watcher")
            logs_dir = Path(__file__).resolve().parent.parent / "logs"
            if stream.endswith(".log") or stream.endswith(".jsonl"):
                target_log = logs_dir / stream
            else:
                ext = ".jsonl" if stream == "results" else ".log"
                target_log = logs_dir / f"{stream}{ext}"

            lines = []
            if target_log.is_file():
                try:
                    with open(target_log, "r", encoding="utf-8", errors="ignore") as f:
                        all_lines = f.readlines()
                        lines = [line.strip() for line in all_lines[-150:]]
                except Exception as e:
                    lines = [f"[ERROR] Could not read log file: {e}"]
            else:
                lines = [f"[INFO] Log file {target_log.name} does not exist yet."]

            self._send_json(200, {"stream": stream, "lines": lines})

        elif path == "/api/jobs":
            db_file = Path(__file__).resolve().parent.parent / "database" / "test_runs.db"
            if db_file.is_file():
                try:
                    db = DatabaseManager(str(db_file))
                    conn = db._get_connection()
                    cur = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 50;")
                    jobs = [dict(r) for r in cur.fetchall()]
                    self._send_json(200, {"jobs": jobs})
                except Exception as e:
                    self._send_json(500, {"error": str(e), "jobs": []})
            else:
                self._send_json(200, {"jobs": []})

        elif path == "/api/runs":
            db_file = Path(__file__).resolve().parent.parent / "database" / "test_runs.db"
            if db_file.is_file():
                try:
                    db = DatabaseManager(str(db_file))
                    conn = db._get_connection()
                    cur = conn.execute("SELECT * FROM test_runs ORDER BY start_time_iso DESC LIMIT 10;")
                    runs = [dict(r) for r in cur.fetchall()]
                    self._send_json(200, {"runs": runs})
                except Exception as e:
                    self._send_json(500, {"error": str(e), "runs": []})
            else:
                self._send_json(200, {"runs": []})

        # Camera APIs
        elif path == "/api/camera/status":
            self._send_json(200, camera_mgr.get_status())

        elif path == "/api/camera/tool2/formats":
            self._send_json(200, camera_mgr.tool2.get_supported_options())

        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        body = self._parse_body()

        # Chaos controls
        if path == "/api/chaos/kill":
            self._send_json(200, {"status": "ok", "action": "sigkill_triggered"})
        elif path == "/api/chaos/delay":
            self._send_json(200, {"status": "ok", "action": "delay_triggered"})
        elif path == "/api/chaos/corrupt":
            self._send_json(200, {"status": "ok", "action": "corruption_triggered"})

        # Camera APIs
        elif path == "/api/camera/config":
            camera_mgr.update_config(
                camera_ip=body.get("camera_ip"),
                camera_ftp=body.get("camera_ftp"),
                dest_dir=body.get("dest_dir"),
            )
            self._send_json(200, {"status": "ok", "config": camera_mgr.get_status()})

        elif path == "/api/camera/test":
            res = camera_mgr.test_connection(
                ip=body.get("camera_ip"),
                ftp_host=body.get("camera_ftp"),
            )
            self._send_json(200, res)

        elif path == "/api/camera/tool1/toggle":
            enable = body.get("active", not camera_mgr.tool1.is_active)
            import_today = body.get("import_today", False)
            if enable:
                res = camera_mgr.tool1.activate(auto_import_same_day=import_today)
            else:
                res = camera_mgr.tool1.deactivate()
            self._send_json(200, res)

        elif path == "/api/camera/tool1/import-today":
            res = camera_mgr.tool1.import_same_day_clips()
            self._send_json(200, res)

        elif path == "/api/camera/tool2/start":
            duration = int(body.get("clip_duration", 60))
            custom_count = body.get("custom_clip_count")
            codec = body.get("codec")
            res = body.get("record_resolution")
            fps = body.get("frame_rate")
            result = camera_mgr.tool2.start_batch(
                clip_duration=duration,
                custom_clip_count=custom_count,
                codec=codec,
                record_resolution=res,
                frame_rate=fps,
            )
            self._send_json(200, result)

        elif path == "/api/camera/tool2/pause":
            self._send_json(200, camera_mgr.tool2.pause_batch())

        elif path == "/api/camera/tool2/resume":
            self._send_json(200, camera_mgr.tool2.resume_batch())

        elif path == "/api/camera/tool2/stop":
            self._send_json(200, camera_mgr.tool2.stop_batch())

        else:
            self._send_json(404, {"error": "Action not found"})


def main():
    parser = argparse.ArgumentParser(description="Black Magic Converter Debug & Telemetry Dashboard Server")
    parser.add_argument("--port", type=int, default=8766, help="Port to serve dashboard (default: 8766)")
    parser.add_argument("--camera-ip", type=str, default="192.168.1.118", help="Default Blackmagic camera IP")
    parser.add_argument("--camera-ftp", type=str, default="ftp://PYXIS-6K.local", help="Default Blackmagic camera FTP URL")
    parser.add_argument("--open", action="store_true", help="Automatically open browser on launch")
    args = parser.parse_args()

    camera_mgr.update_config(camera_ip=args.camera_ip, camera_ftp=args.camera_ftp)

    server_address = ("127.0.0.1", args.port)
    httpd = HTTPServer(server_address, DashboardServerHandler)

    url = f"http://127.0.0.1:{args.port}/dashboard"
    print("\n" + "=" * 70)
    print(" Black Magic Converter — Debug, Telemetry & Camera Tooling Hub")
    print("=" * 70)
    print(f"• Dashboard URL:   {url}")
    print(f"• Camera IP:       {camera_mgr.camera_ip}")
    print(f"• Camera FTP:      {camera_mgr.camera_ftp}")
    print(f"• Ingest Target:   {camera_mgr.dest_dir}")
    print("=" * 70 + "\n")

    if args.open:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard server stopped.")


if __name__ == "__main__":
    main()
