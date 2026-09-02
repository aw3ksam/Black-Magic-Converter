"""
Unit tests for ReportGenerator producing HTML, JSON, and CSV reports.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from debug_tools.core.database import DatabaseManager
from debug_tools.reporting.report_generator import ReportGenerator


class TestReportGenerator(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.reports_dir = os.path.join(self.temp_dir, "reports")
        self.db = DatabaseManager(self.db_path)

        self.test_run_id = "tr_report_test_001"
        self.db.create_test_run({
            "test_run_id": self.test_run_id,
            "start_time_iso": datetime.now(timezone.utc).isoformat(),
            "requested_duration_sec": 60,
            "video_order_mode": "sequential",
            "host_os": "macOS",
            "status": "COMPLETED",
            "total_submitted": 2,
            "total_completed": 2,
            "total_failed": 0,
            "total_crashes": 0,
        })

        # Add synthetic jobs
        self.db.create_job({
            "job_id": "job_0001_test",
            "test_run_id": self.test_run_id,
            "source_filename": "clip1.braw",
            "source_sha256": "sha1",
            "submitted_filename": "job_0001_clip1.braw",
            "output_filename": "job_0001_clip1.mp4",
            "state": "COMPLETED",
            "result": "SUCCESS",
            "source_duration_sec": 10.0,
            "output_duration_sec": 10.0,
            "wall_time_sec": 5.0,
            "avg_fps": 60.0,
            "realtime_factor": 2.0,
        })
        self.db.create_job({
            "job_id": "job_0002_test",
            "test_run_id": self.test_run_id,
            "source_filename": "clip2.braw",
            "source_sha256": "sha2",
            "submitted_filename": "job_0002_clip2.braw",
            "output_filename": "job_0002_clip2.mp4",
            "state": "COMPLETED",
            "result": "SUCCESS",
            "source_duration_sec": 20.0,
            "output_duration_sec": 20.0,
            "wall_time_sec": 10.0,
            "avg_fps": 58.0,
            "realtime_factor": 2.0,
        })

        # Add synthetic telemetry
        for i in range(5):
            self.db.insert_telemetry({
                "test_run_id": self.test_run_id,
                "job_id": "job_0001_test",
                "timestamp_iso": datetime.now(timezone.utc).isoformat(),
                "cpu_total_percent": 25.0 + i,
                "app_cpu_percent": 20.0 + i,
                "app_ram_rss_bytes": 100 * 1024 * 1024 + i * 1024,
                "disk_read_mbs": 5.0,
                "disk_write_mbs": 12.0,
                "disk_free_bytes": 50 * 1024 * 1024 * 1024,
                "active_thread_count": 8,
                "open_file_handles": 14,
            })

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_generate_all_reports(self):
        generator = ReportGenerator(db=self.db, reports_dir=self.reports_dir)
        paths = generator.generate_all_reports(self.test_run_id)

        self.assertTrue(os.path.isfile(paths["json"]))
        self.assertTrue(os.path.isfile(paths["csv"]))
        self.assertTrue(os.path.isfile(paths["html"]))

        with open(paths["html"], "r", encoding="utf-8") as f:
            html = f.read()
            self.assertIn(self.test_run_id, html)
            self.assertIn("job_0001_test", html)
            self.assertIn("job_0002_test", html)


if __name__ == "__main__":
    unittest.main()
