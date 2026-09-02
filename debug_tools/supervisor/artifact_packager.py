"""
Failure Artifact Packager & Crash Evidence Collector.
Complies with Section 5.6 of the Reliability & Observability Specification.
Bundles isolated forensic artifact folders under failures/<job_id>/.
"""

import os
import sys
import csv
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from debug_tools.core.database import DatabaseManager


class ArtifactPackager:
    """
    Assembles complete diagnostic evidence folders upon job failures or crashes.
    """

    def __init__(
        self,
        failures_dir: str = "./failures",
        logs_dir: str = "./logs",
        db: Optional[DatabaseManager] = None,
    ):
        self.failures_dir = Path(failures_dir).resolve()
        self.failures_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir = Path(logs_dir).resolve()
        self.db = db

    def package_failure_bundle(
        self,
        job_id: str,
        test_run_id: str,
        failure_category: str,
        error_message: Optional[str] = None,
        exit_code: Optional[int] = None,
        signal_name: Optional[str] = None,
        stderr_snippet: Optional[str] = None,
        source_ffprobe: Optional[Dict[str, Any]] = None,
        output_ffprobe: Optional[Dict[str, Any]] = None,
        config_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Creates and populates failures/<job_id>/ bundle directory.
        """
        bundle_dir = self.failures_dir / job_id
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # 1. metadata.json
        metadata = {
            "job_id": job_id,
            "test_run_id": test_run_id,
            "timestamp_iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "failure_category": failure_category,
            "error_message": error_message,
            "host_os": sys.platform,
            "python_version": sys.version,
            "config": config_snapshot or {},
        }
        with open(bundle_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, default=str)

        # 2. crash.json & stderr.txt
        crash_data = {
            "exit_code": exit_code,
            "signal_name": signal_name,
            "stderr_snippet": stderr_snippet,
            "timestamp_iso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }
        with open(bundle_dir / "crash.json", "w", encoding="utf-8") as f:
            json.dump(crash_data, f, indent=2, default=str)

        with open(bundle_dir / "stderr.txt", "w", encoding="utf-8") as f:
            f.write(stderr_snippet or "")

        # 3. source_ffprobe.json & output_ffprobe.json
        if source_ffprobe:
            with open(bundle_dir / "source_ffprobe.json", "w", encoding="utf-8") as f:
                json.dump(source_ffprobe, f, indent=2, default=str)

        if output_ffprobe:
            with open(bundle_dir / "output_ffprobe.json", "w", encoding="utf-8") as f:
                json.dump(output_ffprobe, f, indent=2, default=str)

        # 4. extracted_logs.jsonl
        self._extract_job_logs(job_id, bundle_dir / "extracted_logs.jsonl")

        # 5. telemetry.csv
        if self.db:
            self._export_job_telemetry_csv(job_id, bundle_dir / "telemetry.csv")

        return bundle_dir

    def _extract_job_logs(self, job_id: str, target_file: Path):
        """Scans log files in logs_dir and extracts lines matching job_id."""
        extracted_lines = []
        if self.logs_dir.exists():
            log_files = list(self.logs_dir.glob("*.log*")) + list(self.logs_dir.glob("*.jsonl"))
            for log_file in log_files:
                if log_file.suffix == ".gz":
                    continue
                try:
                    with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            if job_id in line:
                                extracted_lines.append(line.strip())
                except Exception:
                    pass

        with open(target_file, "w", encoding="utf-8") as f:
            for line in extracted_lines:
                f.write(f"{line}\n")

    def _export_job_telemetry_csv(self, job_id: str, target_file: Path):
        """Fetches telemetry for job_id from SQLite and writes telemetry.csv."""
        try:
            samples = self.db.get_telemetry_for_job(job_id)
            if not samples:
                return

            fieldnames = [
                "sample_id", "timestamp_iso", "cpu_total_percent", "app_cpu_percent",
                "app_ram_rss_bytes", "app_ram_vms_bytes", "gpu_util_percent", "gpu_mem_bytes",
                "disk_read_mbs", "disk_write_mbs", "disk_free_bytes", "active_thread_count",
                "open_file_handles"
            ]

            with open(target_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for s in samples:
                    writer.writerow(dict(s))
        except Exception:
            pass
