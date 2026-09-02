"""
Unit tests for JobStateMachine and DatabaseManager.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from debug_tools.core.database import DatabaseManager
from debug_tools.core.state_machine import JobStateMachine, JobState, InvalidStateTransitionError
from debug_tools.core.logger import MultiStreamLogger


class TestStateMachineAndDatabase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.logs_dir = os.path.join(self.temp_dir, "logs")
        self.db = DatabaseManager(self.db_path)
        self.logger = MultiStreamLogger(logs_dir=self.logs_dir, test_run_id="tr_test_001")

        # Create test run
        self.test_run_id = "tr_test_001"
        self.db.create_test_run({
            "test_run_id": self.test_run_id,
            "start_time_iso": datetime.now(timezone.utc).isoformat(),
            "requested_duration_sec": 60,
            "video_order_mode": "sequential",
            "host_os": "macOS",
            "status": "RUNNING",
        })

    def tearDown(self):
        self.logger.close()
        self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_database_crud(self):
        job_id = "job_0001"
        self.db.create_job({
            "job_id": job_id,
            "test_run_id": self.test_run_id,
            "source_filename": "sample.braw",
            "source_sha256": "abc123hash",
            "submitted_filename": "job_0001_sample.braw",
            "state": "DISCOVERED",
        })

        job = self.db.get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job["state"], "DISCOVERED")
        self.assertEqual(job["source_filename"], "sample.braw")

        self.db.update_job(job_id, {"state": "COMPLETED", "result": "SUCCESS", "avg_fps": 60.5})
        updated = self.db.get_job(job_id)
        self.assertEqual(updated["state"], "COMPLETED")
        self.assertEqual(updated["result"], "SUCCESS")
        self.assertEqual(updated["avg_fps"], 60.5)

    def test_state_machine_valid_progression(self):
        job_id = "job_0002"
        self.db.create_job({
            "job_id": job_id,
            "test_run_id": self.test_run_id,
            "source_filename": "sample2.braw",
            "source_sha256": "def456hash",
            "submitted_filename": "job_0002_sample2.braw",
            "state": "DISCOVERED",
        })

        sm = JobStateMachine(job_id=job_id, test_run_id=self.test_run_id, db=self.db, logger=self.logger)
        self.assertEqual(sm.current_state, JobState.DISCOVERED)

        # Progression: DISCOVERED -> PREPARING -> SOURCE_ANALYZED -> COPYING_TO_WATCH -> SUBMITTED -> DETECTED -> TRANSCODING -> OUTPUT_DETECTED -> VALIDATING -> COMPLETED
        sm.transition_to(JobState.PREPARING)
        sm.transition_to(JobState.SOURCE_ANALYZED)
        sm.transition_to(JobState.COPYING_TO_WATCH)
        sm.transition_to(JobState.SUBMITTED)
        sm.transition_to(JobState.DETECTED)
        sm.transition_to(JobState.TRANSCODING)
        sm.transition_to(JobState.OUTPUT_DETECTED)
        sm.transition_to(JobState.VALIDATING)
        sm.transition_to(JobState.COMPLETED)

        self.assertEqual(sm.current_state, JobState.COMPLETED)
        job = self.db.get_job(job_id)
        self.assertEqual(job["state"], "COMPLETED")

        events = self.db.get_events_for_job(job_id)
        self.assertEqual(len(events), 9)

    def test_state_machine_invalid_transition(self):
        job_id = "job_0003"
        self.db.create_job({
            "job_id": job_id,
            "test_run_id": self.test_run_id,
            "source_filename": "sample3.braw",
            "source_sha256": "ghi789hash",
            "submitted_filename": "job_0003_sample3.braw",
            "state": "DISCOVERED",
        })

        sm = JobStateMachine(job_id=job_id, test_run_id=self.test_run_id, db=self.db, logger=self.logger)
        # Attempt illegal jump: DISCOVERED -> COMPLETED
        with self.assertRaises(InvalidStateTransitionError):
            sm.transition_to(JobState.COMPLETED)


if __name__ == "__main__":
    unittest.main()
