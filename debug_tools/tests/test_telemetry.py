"""
Unit tests for TelemetryCollector and LeakAnalyzer.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from debug_tools.core.database import DatabaseManager
from debug_tools.telemetry.collector import TelemetryCollector
from debug_tools.telemetry.leak_analyzer import LeakAnalyzer


class TestTelemetryAndLeakAnalyzer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.db = DatabaseManager(self.db_path)
        self.test_run_id = "tr_telemetry_001"
        self.db.create_test_run({
            "test_run_id": self.test_run_id,
            "start_time_iso": datetime.now(timezone.utc).isoformat(),
            "requested_duration_sec": 60,
            "video_order_mode": "sequential",
            "host_os": "macOS",
            "status": "RUNNING",
        })

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_telemetry_collection_and_storage(self):
        collector = TelemetryCollector(
            test_run_id=self.test_run_id,
            db=self.db,
            app_pid=os.getpid(),
        )
        sample = collector.sample_now()
        self.assertEqual(sample["test_run_id"], self.test_run_id)
        self.assertGreater(sample["disk_free_bytes"], 0)

        stored = self.db.get_telemetry_for_run(self.test_run_id)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["test_run_id"], self.test_run_id)

    def test_leak_analyzer_memory_growth_detection(self):
        analyzer = LeakAnalyzer(ram_leak_threshold_mb_hr=10.0)

        # Simulate synthetic samples with 100MB/hr growth
        samples = []
        for i in range(100):
            # 100 samples, 2 seconds apart, increasing RAM
            rss = int((100 + i * 2) * 1024 * 1024)
            samples.append({
                "test_run_id": self.test_run_id,
                "timestamp_iso": datetime.now(timezone.utc).isoformat(),
                "app_ram_rss_bytes": rss,
                "active_thread_count": 5,
                "open_file_handles": 10,
            })

        report = analyzer.analyze_telemetry_and_jobs(samples, [])
        self.assertTrue(report.is_suspected_ram_leak)
        self.assertGreater(report.ram_growth_slope_mb_per_hr, 10.0)
        self.assertFalse(report.is_suspected_thread_leak)
        self.assertFalse(report.is_suspected_fd_leak)


if __name__ == "__main__":
    unittest.main()
