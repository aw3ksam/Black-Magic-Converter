"""
Durable State Storage Engine for black-magic-converter test runs.
Complies with Section 4.3 of the Reliability & Observability Specification.
Operates with SQLite 3 in WAL mode with full ACID durability across process crashes.
"""

import os
import sys
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DDL_SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS test_runs (
    test_run_id TEXT PRIMARY KEY,
    start_time_iso TEXT NOT NULL,
    end_time_iso TEXT,
    requested_duration_sec INTEGER NOT NULL,
    actual_duration_sec REAL,
    video_order_mode TEXT NOT NULL,
    random_seed INTEGER,
    app_version TEXT,
    git_commit TEXT,
    host_os TEXT NOT NULL,
    cpu_model TEXT,
    ram_total_bytes INTEGER,
    gpu_model TEXT,
    total_submitted INTEGER DEFAULT 0,
    total_completed INTEGER DEFAULT 0,
    total_failed INTEGER DEFAULT 0,
    total_crashes INTEGER DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('RUNNING', 'COMPLETED', 'FAILED', 'INTERRUPTED'))
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    test_run_id TEXT NOT NULL REFERENCES test_runs(test_run_id),
    source_filename TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    submitted_filename TEXT NOT NULL,
    output_filename TEXT,
    state TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0,
    start_time_iso TEXT,
    end_time_iso TEXT,
    source_duration_sec REAL,
    output_duration_sec REAL,
    wall_time_sec REAL,
    avg_fps REAL,
    min_fps REAL,
    max_fps REAL,
    realtime_factor REAL,
    peak_cpu_percent REAL,
    peak_ram_bytes INTEGER,
    peak_gpu_percent REAL,
    result TEXT CHECK(result IN ('SUCCESS', 'FAILED', 'SKIPPED')),
    failure_category TEXT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT REFERENCES jobs(job_id),
    test_run_id TEXT NOT NULL REFERENCES test_runs(test_run_id),
    timestamp_iso TEXT NOT NULL,
    component TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT,
    event_name TEXT NOT NULL,
    details_json TEXT
);

CREATE TABLE IF NOT EXISTS telemetry_samples (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_run_id TEXT NOT NULL REFERENCES test_runs(test_run_id),
    job_id TEXT REFERENCES jobs(job_id),
    timestamp_iso TEXT NOT NULL,
    cpu_total_percent REAL,
    app_cpu_percent REAL,
    app_ram_rss_bytes INTEGER,
    app_ram_vms_bytes INTEGER,
    gpu_util_percent REAL,
    gpu_mem_bytes INTEGER,
    disk_read_mbs REAL,
    disk_write_mbs REAL,
    disk_free_bytes INTEGER,
    active_thread_count INTEGER,
    open_file_handles INTEGER
);

CREATE TABLE IF NOT EXISTS crashes (
    crash_id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_run_id TEXT NOT NULL REFERENCES test_runs(test_run_id),
    job_id TEXT REFERENCES jobs(job_id),
    timestamp_iso TEXT NOT NULL,
    crashed_component TEXT NOT NULL,
    exit_code INTEGER,
    signal_name TEXT,
    stderr_snippet TEXT,
    artifact_directory TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_run ON jobs(test_run_id);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS idx_telemetry_job ON telemetry_samples(job_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_run ON telemetry_samples(test_run_id);
CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(test_run_id);
CREATE INDEX IF NOT EXISTS idx_crashes_run ON crashes(test_run_id);
"""


class DatabaseManager:
    """
    Thread-safe SQLite Database Manager for test run lifecycle.
    """

    def __init__(self, db_path: str = "./database/test_runs.db"):
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=60.0,
                check_same_thread=False,
                isolation_level=None,  # autocommit mode, manage transactions explicitly or per query
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA foreign_keys = ON;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path), timeout=60.0)
        try:
            conn.executescript(DDL_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def close(self):
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None

    # --- Test Run Operations ---

    def create_test_run(self, run_data: Dict[str, Any]) -> str:
        conn = self._get_connection()
        cols = [
            "test_run_id", "start_time_iso", "end_time_iso", "requested_duration_sec",
            "actual_duration_sec", "video_order_mode", "random_seed", "app_version",
            "git_commit", "host_os", "cpu_model", "ram_total_bytes", "gpu_model",
            "total_submitted", "total_completed", "total_failed", "total_crashes", "status"
        ]
        present_cols = [c for c in cols if c in run_data]
        placeholders = ", ".join(["?"] * len(present_cols))
        col_names = ", ".join(present_cols)
        values = [run_data[c] for c in present_cols]

        query = f"INSERT INTO test_runs ({col_names}) VALUES ({placeholders});"
        conn.execute(query, values)
        return run_data["test_run_id"]

    def update_test_run(self, test_run_id: str, updates: Dict[str, Any]):
        conn = self._get_connection()
        set_clauses = [f"{k} = ?" for k in updates.keys()]
        query = f"UPDATE test_runs SET {', '.join(set_clauses)} WHERE test_run_id = ?;"
        values = list(updates.values()) + [test_run_id]
        conn.execute(query, values)

    def get_test_run(self, test_run_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM test_runs WHERE test_run_id = ?;", (test_run_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    # --- Job Operations ---

    def create_job(self, job_data: Dict[str, Any]) -> str:
        conn = self._get_connection()
        cols = [
            "job_id", "test_run_id", "source_filename", "source_sha256",
            "submitted_filename", "output_filename", "state", "retry_count",
            "start_time_iso", "end_time_iso", "source_duration_sec", "output_duration_sec",
            "wall_time_sec", "avg_fps", "min_fps", "max_fps", "realtime_factor",
            "peak_cpu_percent", "peak_ram_bytes", "peak_gpu_percent", "result",
            "failure_category", "error_message"
        ]
        present_cols = [c for c in cols if c in job_data]
        placeholders = ", ".join(["?"] * len(present_cols))
        col_names = ", ".join(present_cols)
        values = [job_data[c] for c in present_cols]

        query = f"INSERT INTO jobs ({col_names}) VALUES ({placeholders});"
        conn.execute(query, values)
        return job_data["job_id"]

    def update_job(self, job_id: str, updates: Dict[str, Any]):
        conn = self._get_connection()
        set_clauses = [f"{k} = ?" for k in updates.keys()]
        query = f"UPDATE jobs SET {', '.join(set_clauses)} WHERE job_id = ?;"
        values = list(updates.values()) + [job_id]
        conn.execute(query, values)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM jobs WHERE job_id = ?;", (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_jobs_for_run(self, test_run_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM jobs WHERE test_run_id = ? ORDER BY created_at ASC;", (test_run_id,))
        return [dict(r) for r in cur.fetchall()]

    def get_last_active_job(self, test_run_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute(
            "SELECT * FROM jobs WHERE test_run_id = ? AND state NOT IN ('COMPLETED', 'FAILED') ORDER BY created_at DESC LIMIT 1;",
            (test_run_id,)
        )
        row = cur.fetchone()
        return dict(row) if row else None

    # --- Event Operations ---

    def record_event(self, event_data: Dict[str, Any]):
        conn = self._get_connection()
        query = """
        INSERT INTO events (job_id, test_run_id, timestamp_iso, component, from_state, to_state, event_name, details_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        values = (
            event_data.get("job_id"),
            event_data["test_run_id"],
            event_data["timestamp_iso"],
            event_data["component"],
            event_data.get("from_state"),
            event_data.get("to_state"),
            event_data["event_name"],
            event_data.get("details_json"),
        )
        conn.execute(query, values)

    def get_events_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM events WHERE job_id = ? ORDER BY event_id ASC;", (job_id,))
        return [dict(r) for r in cur.fetchall()]

    def get_events_for_run(self, test_run_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM events WHERE test_run_id = ? ORDER BY event_id ASC;", (test_run_id,))
        return [dict(r) for r in cur.fetchall()]

    # --- Telemetry Operations ---

    def insert_telemetry(self, s: Dict[str, Any]):
        conn = self._get_connection()
        query = """
        INSERT INTO telemetry_samples (
            test_run_id, job_id, timestamp_iso, cpu_total_percent, app_cpu_percent,
            app_ram_rss_bytes, app_ram_vms_bytes, gpu_util_percent, gpu_mem_bytes,
            disk_read_mbs, disk_write_mbs, disk_free_bytes, active_thread_count, open_file_handles
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        values = (
            s["test_run_id"],
            s.get("job_id"),
            s["timestamp_iso"],
            s.get("cpu_total_percent"),
            s.get("app_cpu_percent"),
            s.get("app_ram_rss_bytes"),
            s.get("app_ram_vms_bytes"),
            s.get("gpu_util_percent"),
            s.get("gpu_mem_bytes"),
            s.get("disk_read_mbs"),
            s.get("disk_write_mbs"),
            s.get("disk_free_bytes"),
            s.get("active_thread_count"),
            s.get("open_file_handles"),
        )
        conn.execute(query, values)

    def get_telemetry_for_job(self, job_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM telemetry_samples WHERE job_id = ? ORDER BY sample_id ASC;", (job_id,))
        return [dict(r) for r in cur.fetchall()]

    def get_telemetry_for_run(self, test_run_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM telemetry_samples WHERE test_run_id = ? ORDER BY sample_id ASC;", (test_run_id,))
        return [dict(r) for r in cur.fetchall()]

    # --- Crash Operations ---

    def record_crash(self, crash_data: Dict[str, Any]) -> int:
        conn = self._get_connection()
        query = """
        INSERT INTO crashes (
            test_run_id, job_id, timestamp_iso, crashed_component,
            exit_code, signal_name, stderr_snippet, artifact_directory
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        values = (
            crash_data["test_run_id"],
            crash_data.get("job_id"),
            crash_data["timestamp_iso"],
            crash_data["crashed_component"],
            crash_data.get("exit_code"),
            crash_data.get("signal_name"),
            crash_data.get("stderr_snippet"),
            crash_data.get("artifact_directory"),
        )
        cur = conn.execute(query, values)
        return cur.lastrowid

    def get_crashes_for_run(self, test_run_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cur = conn.execute("SELECT * FROM crashes WHERE test_run_id = ? ORDER BY crash_id ASC;", (test_run_id,))
        return [dict(r) for r in cur.fetchall()]
