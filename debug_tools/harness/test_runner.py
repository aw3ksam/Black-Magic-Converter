"""
Automated Endurance Test Orchestrator & Harness Loop.
Complies with Section 5.1-5.6 of the Reliability & Observability Specification.
Executes unattended endurance test runs, coordinates atomic ingestion, validations, and telemetry.
"""

import os
import sys
import time
import signal
import shutil
import platform
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    psutil = None
    _HAS_PSUTIL = False

from debug_tools.core.database import DatabaseManager
from debug_tools.core.logger import MultiStreamLogger
from debug_tools.core.state_machine import JobStateMachine, JobState
from debug_tools.harness.queue_manager import QueueManager, QueueItem
from debug_tools.harness.staging import VideoStagingHandler, StagingError
from debug_tools.validation.media_inspector import MediaInspector, MediaMetadata
from debug_tools.validation.bitstream_validator import BitstreamValidator, FailureCategory, ValidationResult
from debug_tools.telemetry.collector import TelemetryCollector
from debug_tools.supervisor.artifact_packager import ArtifactPackager
from debug_tools.chaos.fault_injector import FaultInjector


class EnduranceTestRunner:
    """
    Main endurance testing harness.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        test_run_id: Optional[str] = None,
        db: Optional[DatabaseManager] = None,
        logger: Optional[MultiStreamLogger] = None,
    ):
        self.config = config
        self.test_run_id = test_run_id or f"tr_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        endurance_cfg = config.get("endurance_test", {})
        dir_cfg = config.get("directories", {})
        timeout_cfg = config.get("timeouts", {})
        tolerance_cfg = config.get("tolerances", {})
        threshold_cfg = config.get("thresholds", {})
        fault_cfg = config.get("fault_injection", {})
        app_cfg = config.get("application", {})

        self.duration_sec = float(endurance_cfg.get("test_duration_minutes", 60)) * 60.0
        self.video_order = str(endurance_cfg.get("video_order", "seeded_random"))
        self.random_seed = endurance_cfg.get("random_seed", 42)
        self.max_retries = int(endurance_cfg.get("max_retries_per_job", 1))

        self.source_dir = Path(dir_cfg.get("test_video_source_dir", "./test-videos")).resolve()
        self.watch_dir = Path(dir_cfg.get("watch_dir", "./watch_folders/00_IN_INGEST")).resolve()
        self.output_dir = Path(dir_cfg.get("output_dir", "./watch_folders/02_COMPLETED_MP4")).resolve()
        self.archive_dir = Path(dir_cfg.get("archive_dir", "./watch_folders/03_ARCHIVE_BRAW")).resolve()
        self.failures_dir = Path(dir_cfg.get("failure_artifacts_dir", "./failures")).resolve()
        self.logs_dir = Path(dir_cfg.get("logs_dir", "./logs")).resolve()
        self.reports_dir = Path(dir_cfg.get("reports_dir", "./reports")).resolve()
        self.db_path = Path(dir_cfg.get("db_path", "./database/test_runs.db")).resolve()

        self.startup_timeout = float(timeout_cfg.get("startup_timeout_sec", 30))
        self.max_job_timeout = float(timeout_cfg.get("max_job_timeout_sec", 600))
        self.hang_timeout = float(timeout_cfg.get("hang_timeout_sec", 45))
        self.health_endpoint = str(app_cfg.get("health_endpoint", "http://127.0.0.1:8765"))

        self.disk_free_threshold_bytes = int(threshold_cfg.get("disk_free_space_threshold_mb", 2048)) * 1024 * 1024
        self.min_acceptable_fps = float(tolerance_cfg.get("min_acceptable_fps", 15.0))

        # Initialize core services
        self.db = db or DatabaseManager(str(self.db_path))
        self.logger = logger or MultiStreamLogger(logs_dir=str(self.logs_dir), test_run_id=self.test_run_id)

        self.queue_mgr = QueueManager(
            source_dir=str(self.source_dir),
            order_mode=self.video_order,
            random_seed=self.random_seed,
        )
        self.staging_handler = VideoStagingHandler(
            watch_dir=str(self.watch_dir),
            health_endpoint=self.health_endpoint,
            logger=self.logger,
        )
        self.inspector = MediaInspector()
        self.validator = BitstreamValidator(
            duration_tolerance_sec=float(tolerance_cfg.get("duration_diff_tolerance_sec", 0.5)),
            fps_tolerance_percent=float(tolerance_cfg.get("fps_tolerance_percent", 1.0)),
            allow_missing_audio=bool(tolerance_cfg.get("allow_missing_audio", False)),
        )
        self.packager = ArtifactPackager(
            failures_dir=str(self.failures_dir),
            logs_dir=str(self.logs_dir),
            db=self.db,
        )
        self.telemetry = TelemetryCollector(
            test_run_id=self.test_run_id,
            db=self.db,
            logger=self.logger,
            sample_interval_sec=float(timeout_cfg.get("telemetry_sample_interval_sec", 2)),
            monitored_dir=str(self.output_dir),
        )
        self.fault_injector = FaultInjector(
            enabled=bool(fault_cfg.get("enabled", False)),
            probability_app_kill=float(fault_cfg.get("probability_app_kill", 0.0)),
            probability_corrupt_input=float(fault_cfg.get("probability_corrupt_input", 0.0)),
            probability_artificial_delay=float(fault_cfg.get("probability_artificial_delay", 0.0)),
            logger=self.logger,
        )

        self.supervisor = None
        self._supervisor_pid: Optional[int] = None
        self.total_submitted = 0
        self.total_completed = 0
        self.total_failed = 0
        self.total_crashes = 0
        self.running = False
        self._interrupted = False

    def setup_test_run(self):
        """Registers the test run in SQLite and begins telemetry sampling."""
        for d in [self.watch_dir, self.output_dir, self.archive_dir, self.failures_dir, self.logs_dir, self.reports_dir]:
            d.mkdir(parents=True, exist_ok=True)

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        run_record = {
            "test_run_id": self.test_run_id,
            "start_time_iso": now_iso,
            "requested_duration_sec": int(self.duration_sec),
            "video_order_mode": self.video_order,
            "random_seed": self.random_seed,
            "app_version": "3.1.0",
            "host_os": sys.platform,
            "status": "RUNNING",
            "cpu_model": platform.processor() or platform.machine(),
            "ram_total_bytes": psutil.virtual_memory().total if _HAS_PSUTIL else None,
            "gpu_model": platform.machine(),
        }

        # Attempt to capture git commit
        try:
            git_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if git_result.returncode == 0:
                run_record["git_commit"] = git_result.stdout.strip()
        except Exception:
            pass

        self.db.create_test_run(run_record)
        self.logger.log_harness("test_run_started", data=run_record)
        self.telemetry.start()

    def run_job(self, item: QueueItem) -> bool:
        """Executes the full lifecycle of a single transcoding job."""
        job_id = item.job_id
        self.total_submitted += 1
        self.telemetry.set_active_job_id(job_id)
        job_start_time = time.time()
        job_start_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Create Job in DB
        self.db.create_job({
            "job_id": job_id,
            "test_run_id": self.test_run_id,
            "source_filename": item.source.filename,
            "source_sha256": item.source.sha256,
            "submitted_filename": item.submitted_filename,
            "state": JobState.DISCOVERED.value,
            "start_time_iso": job_start_iso,
        })

        sm = JobStateMachine(
            job_id=job_id,
            test_run_id=self.test_run_id,
            initial_state=JobState.DISCOVERED,
            db=self.db,
            logger=self.logger,
        )

        source_meta: Optional[MediaMetadata] = None

        try:
            # 0. Pre-flight disk space check
            try:
                usage = shutil.disk_usage(str(self.output_dir))
                if usage.free < self.disk_free_threshold_bytes:
                    err = (
                        f"Disk free space ({usage.free // (1024*1024)} MB) below "
                        f"threshold ({self.disk_free_threshold_bytes // (1024*1024)} MB)"
                    )
                    sm.transition_to(JobState.FAILED, details={
                        "failure_category": FailureCategory.DISK_FULL.value,
                        "error": err,
                    })
                    self._record_failure(job_id, FailureCategory.DISK_FULL, err, source_meta)
                    return False
            except Exception:
                pass

            # 1. PREPARING -> SOURCE_ANALYZED
            sm.transition_to(JobState.PREPARING)
            try:
                source_meta = self.inspector.inspect(item.source.path)
            except Exception as e:
                self.logger.log_error("source_inspection_failed", job_id=job_id, data={"error": str(e)})

            sm.transition_to(JobState.SOURCE_ANALYZED, details={"duration_sec": source_meta.duration_sec if source_meta else 0})

            # 2. Wait for application readiness (GET /ready)
            ready = self.staging_handler.check_app_ready(timeout_sec=self.startup_timeout)
            if not ready:
                self.logger.log_error("app_not_ready_for_job", job_id=job_id, data={"timeout": self.startup_timeout})

            # 3. COPYING_TO_WATCH -> SUBMITTED
            sm.transition_to(JobState.COPYING_TO_WATCH)
            staged_path = self.staging_handler.stage_job(item)

            # Fault injection: optionally corrupt staged file bytes
            if self.fault_injector.enabled:
                self.fault_injector.maybe_corrupt_input(staged_path)

            sm.transition_to(JobState.SUBMITTED, details={"staged_path": str(staged_path)})

            # 4. Wait for application to detect the file (pickup from watch_dir)
            detected = False
            t0 = time.time()
            while time.time() - t0 < self.startup_timeout:
                if not staged_path.exists():
                    detected = True
                    break
                time.sleep(0.5)

            if not detected:
                # File was not picked up
                err = f"Input file was not detected/moved by watcher within {self.startup_timeout}s"
                sm.transition_to(JobState.FAILED, details={"failure_category": FailureCategory.INPUT_NOT_DETECTED.value, "error": err})
                self._record_failure(job_id, FailureCategory.INPUT_NOT_DETECTED, err, source_meta)
                return False

            sm.transition_to(JobState.DETECTED)
            sm.transition_to(JobState.TRANSCODING)

            # 5. Wait for output file to appear in output_dir
            stem = Path(item.submitted_filename).stem
            expected_mp4 = self.output_dir / f"{stem}.mp4"
            expected_mov = self.output_dir / f"{stem}.mov"
            output_file: Optional[Path] = None

            t_transcode_start = time.time()
            while time.time() - t_transcode_start < self.max_job_timeout:
                if self._interrupted:
                    sm.transition_to(JobState.INTERRUPTED)
                    return False

                # Check watchdog supervisor for application crashes or hangs
                if self.supervisor:
                    if not self.supervisor.check_and_recover(active_job_id=job_id):
                        err = "Application crash loop exceeded max restarts"
                        sm.transition_to(JobState.FAILED, details={
                            "failure_category": FailureCategory.APP_CRASH.value,
                            "error": err,
                        })
                        self._record_failure(job_id, FailureCategory.APP_CRASH, err, source_meta)
                        self.total_crashes += 1
                        return False

                if expected_mp4.is_file() and expected_mp4.stat().st_size > 0:
                    # Give it a moment to ensure write complete
                    time.sleep(1.0)
                    output_file = expected_mp4
                    break
                elif expected_mov.is_file() and expected_mov.stat().st_size > 0:
                    time.sleep(1.0)
                    output_file = expected_mov
                    break

                time.sleep(1.0)

            if not output_file:
                err = f"Transcode timed out after {self.max_job_timeout}s (output not created)"
                sm.transition_to(JobState.FAILED, details={"failure_category": FailureCategory.TRANSCODE_TIMEOUT.value, "error": err})
                self._record_failure(job_id, FailureCategory.TRANSCODE_TIMEOUT, err, source_meta)
                return False

            sm.transition_to(JobState.OUTPUT_DETECTED, details={"output_file": str(output_file)})

            # 6. VALIDATING -> COMPLETED
            sm.transition_to(JobState.VALIDATING)
            val_res: ValidationResult = self.validator.validate(
                output_file=output_file,
                source_meta=source_meta,
                run_full_decode=bool(self.config.get("tolerances", {}).get("run_full_decode_validation", True)),
            )

            wall_time = time.time() - job_start_time
            src_dur = source_meta.duration_sec if source_meta else 0.0
            out_dur = val_res.output_meta.duration_sec if val_res.output_meta else 0.0
            rtf = (src_dur / wall_time) if (wall_time > 0 and src_dur > 0) else 0.0
            avg_fps = (val_res.output_meta.primary_video.frame_count / wall_time) if (val_res.output_meta and val_res.output_meta.primary_video and val_res.output_meta.primary_video.frame_count and wall_time > 0) else 0.0

            if not val_res.is_valid:
                sm.transition_to(JobState.FAILED, details={"failure_category": val_res.failure_category.value, "error": val_res.error_message})
                self._record_failure(job_id, val_res.failure_category, val_res.error_message, source_meta, val_res.output_meta)
                return False

            if avg_fps > 0 and avg_fps < self.min_acceptable_fps:
                self.logger.log_harness(
                    "performance_below_threshold",
                    level="WARNING",
                    job_id=job_id,
                    data={"avg_fps": round(avg_fps, 2), "threshold": self.min_acceptable_fps},
                )

            # Compute peak telemetry metrics during this job
            peak_data: Dict[str, Any] = {}
            try:
                job_telemetry = self.db.get_telemetry_for_job(job_id)
                if job_telemetry:
                    peak_data["peak_cpu_percent"] = max(
                        float(s.get("app_cpu_percent", 0) or 0) for s in job_telemetry
                    )
                    peak_data["peak_ram_bytes"] = max(
                        int(s.get("app_ram_rss_bytes", 0) or 0) for s in job_telemetry
                    )
                    gpus = [s.get("gpu_util_percent") for s in job_telemetry if s.get("gpu_util_percent") is not None]
                    if gpus:
                        peak_data["peak_gpu_percent"] = max(float(g) for g in gpus)
            except Exception:
                pass

            # Mark Completed
            sm.transition_to(JobState.COMPLETED)
            self.total_completed += 1
            now_end_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

            job_update = {
                "state": JobState.COMPLETED.value,
                "result": "SUCCESS",
                "output_filename": output_file.name,
                "end_time_iso": now_end_iso,
                "source_duration_sec": round(src_dur, 2),
                "output_duration_sec": round(out_dur, 2),
                "wall_time_sec": round(wall_time, 2),
                "avg_fps": round(avg_fps, 2),
                "realtime_factor": round(rtf, 2),
                **peak_data,
            }
            self.db.update_job(job_id, job_update)
            self.logger.log_result(job_id, job_update)
            return True

        except Exception as e:
            err_msg = f"Unexpected harness error during job {job_id}: {e}"
            self.logger.log_error("job_exception", job_id=job_id, data={"error": err_msg}, exc_info=True)
            if sm.can_transition_to(JobState.FAILED):
                sm.transition_to(JobState.FAILED, details={"failure_category": FailureCategory.UNKNOWN_FAILURE.value, "error": err_msg})
            self._record_failure(job_id, FailureCategory.UNKNOWN_FAILURE, err_msg, source_meta)
            return False
        finally:
            self.telemetry.set_active_job_id(None)

    def _record_failure(
        self,
        job_id: str,
        category: FailureCategory,
        error_msg: str,
        source_meta: Optional[MediaMetadata] = None,
        output_meta: Optional[MediaMetadata] = None,
    ):
        self.total_failed += 1
        now_end_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        self.db.update_job(job_id, {
            "state": JobState.FAILED.value,
            "result": "FAILED",
            "failure_category": category.value,
            "error_message": error_msg,
            "end_time_iso": now_end_iso,
        })

        # Bundle failure artifacts
        try:
            self.packager.package_failure_bundle(
                job_id=job_id,
                test_run_id=self.test_run_id,
                failure_category=category.value,
                error_message=error_msg,
                source_ffprobe=source_meta.raw_ffprobe if source_meta else None,
                output_ffprobe=output_meta.raw_ffprobe if output_meta else None,
                config_snapshot=self.config,
            )
        except Exception as e:
            self.logger.log_error("failure_bundle_error", job_id=job_id, data={"error": str(e)})

    def run_endurance_loop(self) -> Dict[str, Any]:
        """Main endurance test execution loop."""
        self.setup_test_run()
        self.running = True
        start_time = time.time()

        self.logger.log_harness(
            event="endurance_loop_started",
            data={"duration_sec": self.duration_sec, "order": self.video_order, "seed": self.random_seed}
        )

        def handle_signal(sig, frame):
            self.logger.log_harness("interruption_signal_received")
            self._interrupted = True
            self.running = False

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        try:
            while self.running and (time.time() - start_time < self.duration_sec):
                item = self.queue_mgr.next_item()
                if not item:
                    if self.video_order == "loop":
                        self.queue_mgr.reset()
                        continue
                    else:
                        self.logger.log_harness("all_queue_videos_exhausted")
                        break

                self.run_job(item)

                if self._interrupted:
                    break

                # Post-job watchdog health check and crash recovery
                if self.supervisor:
                    if not self.supervisor.check_and_recover(active_job_id=None):
                        self.logger.log_error("watchdog_recovery_failed_post_job", data={
                            "consecutive_restarts": self.supervisor.consecutive_restarts
                        })
                        break

                # Chaos injection: randomly kill app or inject artificial latency
                if self.fault_injector.enabled and self._supervisor_pid:
                    self.fault_injector.maybe_kill_app(self._supervisor_pid)
                    self.fault_injector.maybe_delay()

                # Periodic in-flight resource leak assessment (every 10 jobs)
                if self.total_submitted > 0 and self.total_submitted % 10 == 0:
                    try:
                        from debug_tools.telemetry.leak_analyzer import LeakAnalyzer
                        analyzer = LeakAnalyzer()
                        telemetry_data = self.db.get_telemetry_for_run(self.test_run_id)
                        jobs_data = self.db.get_jobs_for_run(self.test_run_id)
                        sample_dt = float(self.config.get("timeouts", {}).get("telemetry_sample_interval_sec", 2.0))
                        leak_rep = analyzer.analyze_telemetry_and_jobs(
                            telemetry_data, jobs_data, sample_interval_sec=sample_dt
                        )
                        if leak_rep.warnings:
                            for w in leak_rep.warnings:
                                self.logger.log_harness("live_leak_warning", level="WARNING", data={"warning": w})
                    except Exception:
                        pass

        finally:
            self.telemetry.stop()
            actual_dur = time.time() - start_time
            end_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            status = "INTERRUPTED" if self._interrupted else "COMPLETED"

            summary = {
                "test_run_id": self.test_run_id,
                "end_time_iso": end_iso,
                "actual_duration_sec": round(actual_dur, 2),
                "total_submitted": self.total_submitted,
                "total_completed": self.total_completed,
                "total_failed": self.total_failed,
                "total_crashes": self.total_crashes,
                "status": status,
            }
            self.db.update_test_run(self.test_run_id, summary)
            self.logger.log_harness("test_run_finished", data=summary)

        return summary
