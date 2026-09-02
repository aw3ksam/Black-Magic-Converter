"""
Atomic Ingestion and Watch Folder Staging Handler.
Complies with Section 5.2 of the Reliability & Observability Specification.
Guarantees zero partial file reads and synchronization via embedded Health API /ready.
"""

import os
import sys
import time
import shutil
import urllib.request
import urllib.error
import json
from pathlib import Path
from typing import Optional

from debug_tools.harness.queue_manager import QueueItem
from debug_tools.core.logger import MultiStreamLogger


class StagingError(Exception):
    """Raised when staging or atomic copying fails."""
    pass


class VideoStagingHandler:
    """
    Handles atomic copying of test videos into the watch folder and polls health readiness.
    """

    def __init__(
        self,
        watch_dir: str,
        health_endpoint: str = "http://127.0.0.1:8765",
        logger: Optional[MultiStreamLogger] = None,
    ):
        self.watch_dir = Path(watch_dir).resolve()
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.health_endpoint = health_endpoint.rstrip("/")
        self.logger = logger

    def check_app_ready(self, timeout_sec: float = 30.0, poll_interval: float = 0.5) -> bool:
        """
        Polls GET /ready until application returns HTTP 200 (IDLE state) or timeout expires.
        """
        start = time.time()
        url = f"{self.health_endpoint}/ready"

        while time.time() - start < timeout_sec:
            try:
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status == 200:
                        return True
            except (urllib.error.URLError, ConnectionRefusedError, OSError):
                # Server might be starting or busy
                pass
            time.sleep(poll_interval)

        return False

    def stage_job(self, item: QueueItem, copy_buffer_size: int = 1024 * 1024) -> Path:
        """
        Executes 3-step atomic ingestion:
        1. Write copy to <watch_dir>/.incoming_<job_id>.tmp
        2. Flush file descriptors with os.fsync
        3. Atomic rename (os.replace) to <watch_dir>/<submitted_filename>
        """
        if not item.source.path.exists():
            raise StagingError(f"Source video missing: {item.source.path}")

        temp_target = self.watch_dir / f".incoming_{item.job_id}.tmp"
        final_target = self.watch_dir / item.submitted_filename

        try:
            if self.logger:
                self.logger.log_harness(
                    event="staging_started",
                    job_id=item.job_id,
                    data={"source": str(item.source.path), "temp_target": str(temp_target)}
                )

            # Step 1: Stream copy
            with open(item.source.path, "rb") as f_in:
                with open(temp_target, "wb") as f_out:
                    while True:
                        chunk = f_in.read(copy_buffer_size)
                        if not chunk:
                            break
                        f_out.write(chunk)
                    # Step 2: Flush and sync to disk
                    f_out.flush()
                    os.fsync(f_out.fileno())

            # Also copy sidecar if exists
            sidecar_src = item.source.path.with_suffix(".sidecar")
            if sidecar_src.exists():
                sidecar_dest = final_target.with_suffix(".sidecar")
                shutil.copy2(str(sidecar_src), str(sidecar_dest))

            # Step 3: Atomic rename
            os.replace(temp_target, final_target)

            if self.logger:
                self.logger.log_harness(
                    event="staging_completed",
                    job_id=item.job_id,
                    data={"final_target": str(final_target), "size_bytes": final_target.stat().st_size}
                )

            return final_target

        except Exception as e:
            if temp_target.exists():
                try:
                    temp_target.unlink()
                except Exception:
                    pass
            if self.logger:
                self.logger.log_error(
                    event="staging_failed",
                    job_id=item.job_id,
                    data={"error": str(e), "source": str(item.source.path)},
                    exc_info=True
                )
            raise StagingError(f"Atomic staging failed for {item.job_id}: {e}") from e
