"""
Unit tests for WatchdogSupervisor and HeartbeatMonitor.
"""

import os
import sys
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from debug_tools.core.database import DatabaseManager
from debug_tools.supervisor.watchdog import WatchdogSupervisor
from debug_tools.supervisor.heartbeat import HeartbeatMonitor


class TestWatchdogRecovery(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.failures_dir = os.path.join(self.temp_dir, "failures")
        self.logs_dir = os.path.join(self.temp_dir, "logs")
        self.db = DatabaseManager(self.db_path)
        self.test_run_id = "tr_watchdog_001"
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

    def test_watchdog_spawn_and_terminate(self):
        # Supervises a lightweight python process
        cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
        supervisor = WatchdogSupervisor(
            app_command=cmd,
            test_run_id=self.test_run_id,
            db=self.db,
            failures_dir=self.failures_dir,
            logs_dir=self.logs_dir,
        )

        started = supervisor.start_application()
        self.assertTrue(started)
        self.assertIsNotNone(supervisor.app_process)
        self.assertIsNone(supervisor.app_process.poll())

        proc = supervisor.app_process
        supervisor.stop()
        self.assertIsNotNone(proc.poll())

    def test_watchdog_crash_recovery_and_bundling(self):
        # Process that exits immediately with non-zero code
        cmd = [sys.executable, "-c", "import sys; sys.exit(42)"]
        supervisor = WatchdogSupervisor(
            app_command=cmd,
            test_run_id=self.test_run_id,
            db=self.db,
            failures_dir=self.failures_dir,
            logs_dir=self.logs_dir,
            max_consecutive_restarts=2,
        )

        job_id = "job_crash_test"
        self.db.create_job({
            "job_id": job_id,
            "test_run_id": self.test_run_id,
            "source_filename": "crash.braw",
            "source_sha256": "abc",
            "submitted_filename": "crash.braw",
            "state": "TRANSCODING",
        })

        # Start process
        supervisor.start_application()
        # Wait for exit
        supervisor.app_process.wait()

        # check_and_recover should detect exit, record crash, and restart
        ok = supervisor.check_and_recover(active_job_id=job_id)
        self.assertEqual(supervisor.total_crashes, 1)

        # Check crash recorded in database
        crashes = self.db.get_crashes_for_run(self.test_run_id)
        self.assertEqual(len(crashes), 1)
        self.assertEqual(crashes[0]["exit_code"], 42)

        # Check failure bundle folder created
        bundle = os.path.join(self.failures_dir, job_id)
        self.assertTrue(os.path.isdir(bundle))
        self.assertTrue(os.path.isfile(os.path.join(bundle, "metadata.json")))
        self.assertTrue(os.path.isfile(os.path.join(bundle, "crash.json")))

        supervisor.stop()


if __name__ == "__main__":
    unittest.main()
