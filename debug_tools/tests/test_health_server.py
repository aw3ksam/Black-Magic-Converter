"""
Unit tests for embedded Health API Server and AppStateHolder.
"""

import os
import time
import json
import urllib.request
import unittest

from debug_tools.core.health_server import HealthServer, global_app_state


class TestHealthServer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.port = 18765
        cls.server = HealthServer(host="127.0.0.1", port=cls.port)
        cls.server.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_health_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["pid"], os.getpid())

    def test_ready_and_status_transitions(self):
        # 1. State is IDLE -> /ready should be 200
        global_app_state.set_idle()
        url_ready = f"http://127.0.0.1:{self.port}/ready"
        with urllib.request.urlopen(url_ready, timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(data["ready"])

        # 2. State is TRANSCODING -> /ready should be 503
        global_app_state.set_transcoding("input.braw", job_id="job_test_01", total_frames=100)
        global_app_state.update_progress(frames_processed=50, total_frames=100, fps=60.0)

        try:
            urllib.request.urlopen(url_ready, timeout=2.0)
            self.fail("Expected HTTP 503 for non-idle /ready")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 503)

        # 3. Check /status
        url_status = f"http://127.0.0.1:{self.port}/status"
        with urllib.request.urlopen(url_status, timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["state"], "TRANSCODING")
            self.assertEqual(data["active_job_id"], "job_test_01")
            self.assertEqual(data["frames_processed"], 50)
            self.assertEqual(data["instantaneous_fps"], 60.0)

        global_app_state.set_idle()

    def test_dashboard_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/dashboard"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8")
            self.assertIn("Black Magic Converter", content)
            self.assertIn("dashboard", content.lower())

    def test_logs_endpoint(self):
        url = f"http://127.0.0.1:{self.port}/api/logs?stream=braw_watcher"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["stream"], "braw_watcher")
            self.assertIsInstance(data["lines"], list)


if __name__ == "__main__":
    unittest.main()
