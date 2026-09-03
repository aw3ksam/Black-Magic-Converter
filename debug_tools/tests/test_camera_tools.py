"""
Unit tests for Blackmagic Camera Tooling Suite (Tool 1 & Tool 2).
Validates CameraClient, FtpClient, AutoTransferTool, and BatchRecorderTool.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import sys
import threading
import time
import unittest

_repo_root = str(Path(__file__).resolve().parent.parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from src.camera.camera_client import CameraClient
from src.camera.ftp_client import FtpClient
from src.camera.tool_auto_transfer import AutoTransferTool
from src.camera.tool_batch_recorder import BatchRecorderTool, DURATION_PRESETS


class MockCameraHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/control/api/v1/system/product":
            self._send_json({"deviceName": "PYXIS-6K", "productName": "Blackmagic PYXIS 6K", "softwareVersion": "8.6"})
        elif self.path == "/control/api/v1/transports/0/record":
            self._send_json({"recording": False})
        elif self.path == "/control/api/v1/clips":
            self._send_json({
                "clips": [
                    {"clipUniqueId": 101, "filePath": "A001_09021200_C001.braw", "fileSize": 1048576},
                    {"clipUniqueId": 102, "filePath": "A001_09021210_C002.braw", "fileSize": 2097152},
                ]
            })
        elif self.path == "/control/api/v1/system/supportedFormats":
            self._send_json({
                "supportedFormats": [
                    {
                        "recordResolution": {"width": 4096, "height": 2304},
                        "codecs": ["BRaw:8_1", "BRaw:5_1"],
                        "frameRates": ["24", "29.97"],
                    }
                ]
            })
        elif self.path == "/control/api/v1/system/format":
            self._send_json({
                "codec": "BRaw:8_1",
                "recordResolution": {"width": 4096, "height": 2304},
                "frameRate": "24",
            })
        elif self.path == "/control/api/v1/media/workingset":
            self._send_json({
                "workingset": [
                    {
                        "volume": "A001",
                        "bytesRemaining": 500000000000,
                        "totalExpectedRemainingRecordTimeSeconds": 7200,
                    }
                ]
            })
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        if self.path == "/control/api/v1/transports/0/record":
            self._send_json({"success": True}, status=200)
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_PUT(self):
        if self.path == "/control/api/v1/transports/0/record":
            self._send_json({"success": True}, status=200)
        elif self.path == "/control/api/v1/system/format":
            self._send_json({"success": True}, status=200)
        else:
            self._send_json({"error": "not found"}, status=404)


class TestCameraTools(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), MockCameraHandler)
        cls.port = cls.server.server_port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.client = CameraClient(host="127.0.0.1", port=self.port, timeout=2.0)

    def test_camera_client_product_and_record(self):
        prod = self.client.get_product()
        self.assertEqual(prod.get("productName"), "Blackmagic PYXIS 6K")
        self.assertFalse(self.client.get_record_state())
        self.assertTrue(self.client.start_record())
        self.assertTrue(self.client.stop_record())

    def test_camera_client_clips_and_formats(self):
        clips = self.client.get_clips()
        self.assertEqual(len(clips), 2)
        self.assertEqual(clips[0]["clipUniqueId"], 101)

        formats = self.client.get_supported_formats()
        self.assertEqual(len(formats), 1)
        self.assertIn("BRaw:8_1", formats[0]["codecs"])

    def test_ftp_client_path_resolution(self):
        ftp = FtpClient(host="ftp://PYXIS-6K.local")
        self.assertEqual(ftp.host, "PYXIS-6K.local")

        resolved = ftp.resolve_remote_path("A001_09021200_C001.braw", volume="A001")
        self.assertEqual(resolved, "usb/A001/A001_09021200_C001.braw")

        already_usb = ftp.resolve_remote_path("usb/A001/clip.braw")
        self.assertEqual(already_usb, "usb/A001/clip.braw")

    def test_tool1_auto_transfer_snapshot(self):
        ftp = FtpClient(host="127.0.0.1")
        tmp_dir = Path("/tmp/cam_test_dest")
        tmp_dir.mkdir(parents=True, exist_ok=True)

        events = []
        tool1 = AutoTransferTool(
            camera_client=self.client,
            ftp_client=ftp,
            dest_dir=tmp_dir,
            on_event_cb=lambda e: events.append(e),
        )

        res = tool1.activate()
        self.assertTrue(res["success"])
        self.assertTrue(tool1.is_active)
        # Verify that existing clips 101 and 102 are in baseline known set
        self.assertIn(101, tool1.known_clip_ids)
        self.assertIn(102, tool1.known_clip_ids)
        self.assertEqual(res["baseline_clips_ignored"], 2)

        deact = tool1.deactivate()
        self.assertFalse(tool1.is_active)

    def test_tool2_presets_and_status(self):
        tool2 = BatchRecorderTool(camera_client=self.client)
        opts = tool2.get_supported_options()
        self.assertTrue(opts["success"])
        self.assertEqual(len(opts["duration_presets"]), 4)

        # Check preset durations
        self.assertEqual(DURATION_PRESETS[15]["clips"], 240)
        self.assertEqual(DURATION_PRESETS[30]["clips"], 120)
        self.assertEqual(DURATION_PRESETS[45]["clips"], 80)
        self.assertEqual(DURATION_PRESETS[60]["clips"], 60)

        status = tool2.get_status()
        self.assertFalse(status["is_active"])
        self.assertEqual(status["state"], "idle")


if __name__ == "__main__":
    unittest.main()
