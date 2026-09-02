"""
Multi-Stream Rotating NDJSON Logger for black-magic-converter.
Complies with Section 4.1 & 4.2 of the Reliability & Observability Specification.
Provides structured event logging, automatic rotation with gzip compression, and fallback error isolation.
"""

import os
import sys
import time
import gzip
import json
import logging
import threading
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional


class GzipRotatingFileHandler(RotatingFileHandler):
    """
    RotatingFileHandler that compresses rotated backup log files using gzip.
    """

    def doRollover(self):
        super().doRollover()
        # Compress the most recent rotated file (e.g. filename.1)
        rotated_first = f"{self.baseFilename}.1"
        if os.path.exists(rotated_first):
            gz_path = f"{rotated_first}.gz"
            try:
                with open(rotated_first, "rb") as f_in:
                    with gzip.open(gz_path, "wb") as f_out:
                        f_out.writelines(f_in)
                os.remove(rotated_first)
            except Exception as e:
                sys.stderr.write(f"Warning: Failed to gzip compress rotated log {rotated_first}: {e}\n")


class NDJSONFormatter(logging.Formatter):
    """
    Formats log records as single-line NDJSON matching the specification schema:
    {
      "timestamp_iso": "...",
      "timestamp_mono_ns": ...,
      "test_run_id": "...",
      "job_id": "...",
      "component": "...",
      "event": "...",
      "level": "...",
      "pid": ...,
      "thread_id": ...,
      "data": { ... }
    }
    """

    def __init__(self, default_component: str = "application"):
        super().__init__()
        self.default_component = default_component

    def format(self, record: logging.LogRecord) -> str:
        now_utc = datetime.now(timezone.utc)
        iso_ts = now_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        mono_ns = getattr(record, "timestamp_mono_ns", time.monotonic_ns())

        test_run_id = getattr(record, "test_run_id", None)
        job_id = getattr(record, "job_id", None)
        component = getattr(record, "component", self.default_component)
        event = getattr(record, "event", getattr(record, "event_name", "log_message"))

        # Extract structured data payload
        data = getattr(record, "data", {})
        if not isinstance(data, dict):
            data = {"message": str(data)}
        else:
            data = dict(data)

        # Include standard record message if not explicitly in data
        if "message" not in data and record.getMessage():
            data["message"] = record.getMessage()

        # Include exception/stacktrace info if present
        if record.exc_info:
            data["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else "Exception"
            data["stack_trace"] = self.formatException(record.exc_info)
        elif record.exc_text:
            data["stack_trace"] = record.exc_text

        entry = {
            "timestamp_iso": iso_ts,
            "timestamp_mono_ns": mono_ns,
            "test_run_id": test_run_id,
            "job_id": job_id,
            "component": component,
            "event": event,
            "level": record.levelname,
            "pid": os.getpid(),
            "thread_id": threading.get_native_id() if hasattr(threading, "get_native_id") else threading.get_ident(),
            "data": data,
        }

        try:
            return json.dumps(entry, default=str)
        except Exception as e:
            return json.dumps({
                "timestamp_iso": iso_ts,
                "timestamp_mono_ns": mono_ns,
                "test_run_id": test_run_id,
                "job_id": job_id,
                "component": component,
                "event": "log_serialization_error",
                "level": "ERROR",
                "pid": os.getpid(),
                "thread_id": threading.get_ident(),
                "data": {"error": str(e), "raw_message": str(record.msg)},
            })


class MultiStreamLogger:
    """
    Central logger providing access to dedicated multi-stream logs:
    - application.log
    - errors.log
    - transcodes.log
    - performance.log
    - harness.log
    - watchdog.log
    - results.jsonl
    """

    STREAM_NAMES = [
        "application",
        "errors",
        "transcodes",
        "performance",
        "harness",
        "watchdog",
        "results",
    ]

    _instances: Dict[str, "MultiStreamLogger"] = {}
    _lock = threading.Lock()

    def __init__(
        self,
        logs_dir: str = "./logs",
        test_run_id: Optional[str] = None,
        component: str = "application",
        max_bytes: int = 50 * 1024 * 1024,  # 50 MB
        backup_count: int = 10,
        echo_console: bool = False,
    ):
        self.logs_dir = Path(logs_dir).resolve()
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.test_run_id = test_run_id
        self.component = component
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.echo_console = echo_console

        self.handlers: Dict[str, logging.Handler] = {}
        self._init_streams()

    def _init_streams(self):
        formatter = NDJSONFormatter(default_component=self.component)

        for stream in self.STREAM_NAMES:
            ext = ".jsonl" if stream == "results" else ".log"
            log_path = self.logs_dir / f"{stream}{ext}"
            try:
                handler = GzipRotatingFileHandler(
                    filename=str(log_path),
                    maxBytes=self.max_bytes,
                    backupCount=self.backup_count,
                    encoding="utf-8",
                )
                handler.setFormatter(formatter)
                self.handlers[stream] = handler
            except Exception as e:
                sys.stderr.write(f"Warning: Failed to init log stream handler for {stream}: {e}\n")

    def set_test_run_id(self, test_run_id: str):
        self.test_run_id = test_run_id

    def emit(
        self,
        stream: str,
        event: str,
        level: str = "INFO",
        job_id: Optional[str] = None,
        component: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        exc_info: Any = None,
    ):
        """
        Emits a structured event into the designated stream and automatically
        mirrors WARNING/ERROR/CRITICAL to errors.log.
        """
        try:
            lvl_num = getattr(logging, level.upper(), logging.INFO)
            record = logging.LogRecord(
                name=f"stream.{stream}",
                level=lvl_num,
                pathname="",
                lineno=0,
                msg="",
                args=(),
                exc_info=exc_info,
            )
            record.timestamp_mono_ns = time.monotonic_ns()
            record.test_run_id = self.test_run_id
            record.job_id = job_id
            record.component = component or self.component
            record.event = event
            record.data = data or {}

            # Emit to target stream handler
            if stream in self.handlers:
                self.handlers[stream].handle(record)

            # Auto-route errors to errors.log if not already the errors stream
            if lvl_num >= logging.WARNING and stream != "errors" and "errors" in self.handlers:
                self.handlers["errors"].handle(record)

            # Optional console mirror
            if self.echo_console:
                prefix = f"[{level.upper()}] [{record.component}] [{event}]"
                if job_id:
                    prefix += f" [job:{job_id}]"
                print(f"{prefix} {data}")

        except Exception as e:
            # Defensive logging: failure in logging must never break callers
            sys.stderr.write(f"MultiStreamLogger Error emitting to {stream}: {e}\n")

    # Shortcut convenience methods
    def log_app(self, event: str, level: str = "INFO", job_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None, exc_info: Any = None):
        self.emit("application", event, level=level, job_id=job_id, data=data, exc_info=exc_info)

    def log_error(self, event: str, level: str = "ERROR", job_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None, exc_info: Any = None):
        self.emit("errors", event, level=level, job_id=job_id, data=data, exc_info=exc_info)

    def log_transcode(self, event: str, level: str = "INFO", job_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None):
        self.emit("transcodes", event, level=level, job_id=job_id, data=data)

    def log_performance(self, event: str = "telemetry_sample", data: Optional[Dict[str, Any]] = None, job_id: Optional[str] = None):
        self.emit("performance", event, level="DEBUG", job_id=job_id, data=data)

    def log_harness(self, event: str, level: str = "INFO", job_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None, exc_info: Any = None):
        self.emit("harness", event, level=level, job_id=job_id, data=data, exc_info=exc_info)

    def log_watchdog(self, event: str, level: str = "INFO", job_id: Optional[str] = None, data: Optional[Dict[str, Any]] = None, exc_info: Any = None):
        self.emit("watchdog", event, level=level, job_id=job_id, data=data, exc_info=exc_info)

    def log_result(self, job_id: str, result_record: Dict[str, Any]):
        self.emit("results", "job_finished", level="INFO", job_id=job_id, data=result_record)

    def close(self):
        for handler in self.handlers.values():
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass


def get_logger(
    logs_dir: str = "./logs",
    test_run_id: Optional[str] = None,
    component: str = "application",
    echo_console: bool = False,
) -> MultiStreamLogger:
    """Singleton getter for MultiStreamLogger per logs_dir + component."""
    key = f"{logs_dir}::{component}"
    with MultiStreamLogger._lock:
        if key not in MultiStreamLogger._instances:
            MultiStreamLogger._instances[key] = MultiStreamLogger(
                logs_dir=logs_dir,
                test_run_id=test_run_id,
                component=component,
                echo_console=echo_console,
            )
        else:
            if test_run_id:
                MultiStreamLogger._instances[key].set_test_run_id(test_run_id)
        return MultiStreamLogger._instances[key]
