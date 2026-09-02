"""
Formal Job State Machine and Transition Guard.
Complies with Section 4.4 of the Reliability & Observability Specification.
Enforces valid state transitions and logs all transition events into SQLite and structured NDJSON logs.
"""

import json
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Optional, Set, Any

from debug_tools.core.database import DatabaseManager
from debug_tools.core.logger import MultiStreamLogger


class JobState(str, Enum):
    DISCOVERED = "DISCOVERED"
    PREPARING = "PREPARING"
    SOURCE_ANALYZED = "SOURCE_ANALYZED"
    COPYING_TO_WATCH = "COPYING_TO_WATCH"
    SUBMITTED = "SUBMITTED"
    DETECTED = "DETECTED"
    TRANSCODING = "TRANSCODING"
    OUTPUT_DETECTED = "OUTPUT_DETECTED"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"
    INTERRUPTED = "INTERRUPTED"


class InvalidStateTransitionError(Exception):
    """Raised when an illegal state transition is attempted."""
    pass


class JobStateMachine:
    """
    Guards and records lifecycle transitions for a single transcoding job.
    """

    VALID_TRANSITIONS: Dict[JobState, Set[JobState]] = {
        JobState.DISCOVERED: {JobState.PREPARING, JobState.FAILED, JobState.INTERRUPTED},
        JobState.PREPARING: {JobState.SOURCE_ANALYZED, JobState.FAILED, JobState.INTERRUPTED},
        JobState.SOURCE_ANALYZED: {JobState.COPYING_TO_WATCH, JobState.FAILED, JobState.INTERRUPTED},
        JobState.COPYING_TO_WATCH: {JobState.SUBMITTED, JobState.FAILED, JobState.INTERRUPTED},
        JobState.SUBMITTED: {JobState.DETECTED, JobState.FAILED, JobState.INTERRUPTED},
        JobState.DETECTED: {JobState.TRANSCODING, JobState.FAILED, JobState.INTERRUPTED},
        JobState.TRANSCODING: {JobState.OUTPUT_DETECTED, JobState.FAILED, JobState.RECOVERING, JobState.INTERRUPTED},
        JobState.OUTPUT_DETECTED: {JobState.VALIDATING, JobState.FAILED, JobState.INTERRUPTED},
        JobState.VALIDATING: {JobState.COMPLETED, JobState.FAILED, JobState.INTERRUPTED},
        JobState.FAILED: {JobState.RECOVERING, JobState.COMPLETED},
        JobState.RECOVERING: {JobState.PREPARING, JobState.FAILED, JobState.INTERRUPTED},
        JobState.COMPLETED: set(),  # Terminal state
        JobState.INTERRUPTED: {JobState.RECOVERING, JobState.FAILED},
    }

    def __init__(
        self,
        job_id: str,
        test_run_id: str,
        initial_state: JobState = JobState.DISCOVERED,
        db: Optional[DatabaseManager] = None,
        logger: Optional[MultiStreamLogger] = None,
    ):
        self.job_id = job_id
        self.test_run_id = test_run_id
        self.current_state = initial_state
        self.db = db
        self.logger = logger

    def can_transition_to(self, new_state: JobState) -> bool:
        allowed = self.VALID_TRANSITIONS.get(self.current_state, set())
        return new_state in allowed

    def transition_to(
        self,
        new_state: JobState,
        component: str = "harness",
        event_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> JobState:
        """
        Validates transition, updates current state, and writes event to SQLite and NDJSON logger.
        """
        if not self.can_transition_to(new_state):
            err_msg = (
                f"Illegal state transition for job {self.job_id}: "
                f"{self.current_state.value} -> {new_state.value}"
            )
            if self.logger:
                self.logger.log_error(
                    event="invalid_state_transition",
                    job_id=self.job_id,
                    data={"from_state": self.current_state.value, "to_state": new_state.value, "error": err_msg}
                )
            raise InvalidStateTransitionError(err_msg)

        from_state = self.current_state
        self.current_state = new_state
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        evt_name = event_name or f"transition_to_{new_state.value.lower()}"

        # 1. Update Job state in database
        if self.db:
            try:
                self.db.update_job(self.job_id, {"state": new_state.value})
                self.db.record_event({
                    "job_id": self.job_id,
                    "test_run_id": self.test_run_id,
                    "timestamp_iso": now_iso,
                    "component": component,
                    "from_state": from_state.value,
                    "to_state": new_state.value,
                    "event_name": evt_name,
                    "details_json": json.dumps(details or {}, default=str),
                })
            except Exception as e:
                if self.logger:
                    self.logger.log_error("db_state_update_failed", job_id=self.job_id, data={"error": str(e)})

        # 2. Emit NDJSON log
        if self.logger:
            self.logger.emit(
                stream="harness",
                event=evt_name,
                level="INFO",
                job_id=self.job_id,
                component=component,
                data={
                    "from_state": from_state.value,
                    "to_state": new_state.value,
                    "details": details or {},
                },
            )

        return self.current_state
