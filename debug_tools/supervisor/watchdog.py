"""
Independent Watchdog Supervisor & Crash Recovery Daemon.
Complies with Section 5.5 of the Reliability & Observability Specification.
Supervises transcoding application lifecycles with rate-limited exponential backoff and forensic preservation.
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

from debug_tools.core.database import DatabaseManager
from debug_tools.core.logger import MultiStreamLogger
from debug_tools.supervisor.heartbeat import HeartbeatMonitor
from debug_tools.supervisor.artifact_packager import ArtifactPackager


class WatchdogSupervisor:
    """
    Supervises the transcoding application subprocess with automatic restart,
    exponential backoff, hang detection, and crash bundle packaging.
    """

    BACKOFF_DELAYS = [0.0, 2.0, 5.0, 15.0, 30.0]

    def __init__(
        self,
        app_command: List[str],
        test_run_id: str,
        db: DatabaseManager,
        logger: Optional[MultiStreamLogger] = None,
        health_endpoint: str = "http://127.0.0.1:8765",
        max_consecutive_restarts: int = 5,
        hang_timeout_sec: float = 45.0,
        failures_dir: str = "./failures",
        logs_dir: str = "./logs",
        working_dir: str = ".",
    ):
        self.app_command = app_command
        self.test_run_id = test_run_id
        self.db = db
        self.logger = logger
        self.health_endpoint = health_endpoint
        self.max_consecutive_restarts = max_consecutive_restarts
        self.hang_timeout_sec = hang_timeout_sec
        self.working_dir = Path(working_dir).resolve()

        self.heartbeat = HeartbeatMonitor(
            health_endpoint=health_endpoint,
            hang_timeout_sec=hang_timeout_sec,
            logger=logger,
        )
        self.packager = ArtifactPackager(
            failures_dir=failures_dir,
            logs_dir=logs_dir,
            db=db,
        )

        self.app_process: Optional[subprocess.Popen] = None
        self.consecutive_restarts = 0
        self.total_crashes = 0
        self.running = False
        self._stderr_buffer: List[str] = []

    def start_application(self) -> bool:
        """Launches the application subprocess with unbuffered output."""
        try:
            if self.app_process:
                self._terminate_process(self.app_process)
                self.app_process = None

            if self.logger:
                self.logger.log_watchdog(
                    event="spawning_application",
                    data={"command": self.app_command, "cwd": str(self.working_dir)}
                )

            # Ensure unbuffered python execution if python command
            cmd = list(self.app_command)
            if "python" in cmd[0] and "-u" not in cmd:
                cmd.insert(1, "-u")

            self.app_process = subprocess.Popen(
                cmd,
                cwd=str(self.working_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            if self.logger:
                self.logger.log_watchdog(
                    event="application_spawned",
                    data={"pid": self.app_process.pid}
                )

            # Wait briefly for health endpoint to respond
            time.sleep(1.0)
            return True

        except Exception as e:
            if self.logger:
                self.logger.log_error("spawn_application_failed", data={"error": str(e)}, exc_info=True)
            return False

    def check_and_recover(self, active_job_id: Optional[str] = None) -> bool:
        """
        Probes application health and status.
        If process has terminated or hung:
        1. Captures exit code / stderr
        2. Records crash and failure bundle
        3. Marks active job FAILED
        4. Performs exponential backoff restart
        Returns True if application is healthy or recovered, False if restart limits exceeded.
        """
        if not self.app_process:
            return self.start_application()

        exit_code = self.app_process.poll()
        is_hung = False

        if exit_code is None:
            health_status = self.heartbeat.check_health()
            if health_status.is_healthy and health_status.state == "TRANSCODING":
                self.heartbeat.check_status_progress()
                frame_stalled = (time.time() - self.heartbeat.last_frame_progress_time) > self.hang_timeout_sec
                is_hung = self.heartbeat.is_hung() or frame_stalled
            else:
                is_hung = self.heartbeat.is_hung()

        if exit_code is not None or is_hung:
            self.total_crashes += 1
            self.consecutive_restarts += 1

            # Read remaining stderr
            stderr_snippet = ""
            if self.app_process.stderr:
                try:
                    stderr_snippet = self.app_process.stderr.read() or ""
                except Exception:
                    pass

            reason = "APPLICATION_HANG" if is_hung else "APP_CRASH"

            if self.logger:
                self.logger.log_error(
                    event="application_failure_detected",
                    job_id=active_job_id,
                    data={
                        "reason": reason,
                        "exit_code": exit_code,
                        "consecutive_restarts": self.consecutive_restarts,
                        "total_crashes": self.total_crashes,
                        "stderr_tail": stderr_snippet[-500:] if stderr_snippet else "",
                    }
                )

            # If hung, gracefully terminate then force kill
            if is_hung and exit_code is None:
                self._terminate_process(self.app_process)

            # Record crash in DB
            bundle_dir = ""
            if active_job_id:
                bundle_path = self.packager.package_failure_bundle(
                    job_id=active_job_id,
                    test_run_id=self.test_run_id,
                    failure_category=reason,
                    error_message=f"Application crashed/hung with exit code {exit_code}",
                    exit_code=exit_code,
                    stderr_snippet=stderr_snippet,
                )
                bundle_dir = str(bundle_path)

                # Update job in DB
                self.db.update_job(active_job_id, {
                    "state": "FAILED",
                    "result": "FAILED",
                    "failure_category": reason,
                    "error_message": f"Crash exit code: {exit_code}",
                })

            self.db.record_crash({
                "test_run_id": self.test_run_id,
                "job_id": active_job_id,
                "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "crashed_component": "application",
                "exit_code": exit_code,
                "signal_name": f"SIG_{abs(exit_code)}" if exit_code and exit_code < 0 else None,
                "stderr_snippet": stderr_snippet[-2000:] if stderr_snippet else None,
                "artifact_directory": bundle_dir,
            })

            # Check crash loop threshold
            if self.consecutive_restarts >= self.max_consecutive_restarts:
                if self.logger:
                    self.logger.log_error(
                        event="max_consecutive_restarts_exceeded",
                        data={"restarts": self.consecutive_restarts, "max_allowed": self.max_consecutive_restarts}
                    )
                return False

            # Exponential backoff delay
            delay_idx = min(self.consecutive_restarts - 1, len(self.BACKOFF_DELAYS) - 1)
            backoff_sec = self.BACKOFF_DELAYS[delay_idx]
            if self.logger:
                self.logger.log_watchdog(
                    event="restart_backoff",
                    data={"attempt": self.consecutive_restarts, "backoff_sec": backoff_sec}
                )
            if backoff_sec > 0:
                time.sleep(backoff_sec)

            # Respawn application
            return self.start_application()

        else:
            # Application running smoothly, reset consecutive restarts count after sustained liveness
            if self.consecutive_restarts > 0:
                self.consecutive_restarts = 0

            return True

    def _terminate_process(self, proc: subprocess.Popen, grace_period_sec: float = 3.0):
        """Sends SIGINT first, waits grace period, then SIGTERM/SIGKILL."""
        try:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
                start = time.time()
                while time.time() - start < grace_period_sec:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)

                # Fallback to SIGTERM
                if proc.poll() is None:
                    proc.terminate()
                    time.sleep(1.0)

                # Force kill if still lingering
                if proc.poll() is None:
                    proc.kill()
                    time.sleep(0.5)

            if proc.stdout:
                try:
                    proc.stdout.close()
                except Exception:
                    pass
            if proc.stderr:
                try:
                    proc.stderr.close()
                except Exception:
                    pass
        except Exception:
            pass

    def stop(self):
        """Stops application and cleans up."""
        self.running = False
        if self.app_process:
            if self.app_process.poll() is None and self.logger:
                self.logger.log_watchdog(event="stopping_supervised_application", data={"pid": self.app_process.pid})
            self._terminate_process(self.app_process)
            self.app_process = None
