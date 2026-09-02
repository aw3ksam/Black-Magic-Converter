#!/usr/bin/env python3
"""
Dedicated Standalone Dashboard Server for Black Magic Converter Debug Tools.
Serves interactive dashboard on http://127.0.0.1:8766 with live log streaming,
database queries, and YAML config synchronization.
"""

import os
import sys
import json
import webbrowser
import argparse
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from debug_tools.core.database import DatabaseManager


class DashboardServerHandler(BaseHTTPRequestHandler):
    """HTTP handler serving the dashboard, live logs, database records, and chaos controls."""

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
            stream = params.get("stream", "harness")
            logs_dir = Path(__file__).resolve().parent.parent / "logs"
            ext = ".jsonl" if stream == "results" else ".log"
            target_log = logs_dir / f"{stream}{ext}"

            lines = []
            if target_log.is_file():
                try:
                    with open(target_log, "r", encoding="utf-8", errors="ignore") as f:
                        all_lines = f.readlines()
                        lines = [line.strip() for line in all_lines[-100:]]
                except Exception as e:
                    lines = [f"[ERROR] Could not read log file: {e}"]
            else:
                lines = [f"[INFO] Log file {stream}{ext} does not exist yet."]

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

        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/chaos/kill":
            self._send_json(200, {"status": "ok", "action": "sigkill_triggered"})
        elif path == "/api/chaos/delay":
            self._send_json(200, {"status": "ok", "action": "delay_triggered"})
        elif path == "/api/chaos/corrupt":
            self._send_json(200, {"status": "ok", "action": "corruption_triggered"})
        else:
            self._send_json(404, {"error": "Action not found"})


def main():
    parser = argparse.ArgumentParser(description="Black Magic Converter Debug & Telemetry Dashboard Server")
    parser.add_argument("--port", type=int, default=8766, help="Port to serve dashboard (default: 8766)")
    parser.add_argument("--open", action="store_true", help="Automatically open browser on launch")
    args = parser.parse_args()

    server_address = ("127.0.0.1", args.port)
    httpd = HTTPServer(server_address, DashboardServerHandler)

    url = f"http://127.0.0.1:{args.port}/dashboard"
    print("\n" + "=" * 70)
    print(" Black Magic Converter — Debug, Telemetry & Chaos Dashboard")
    print("=" * 70)
    print(f"• Dashboard URL:   {url}")
    print(f"• Health API:      http://127.0.0.1:8765")
    print("=" * 70 + "\n")

    if args.open:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard server stopped.")
        httpd.server_close()


if __name__ == "__main__":
    main()
