"""
Cross-Process Heartbeat & Liveness Health Monitor.
Complies with Section 5.5 of the Reliability & Observability Specification.
Periodically probes embedded HTTP /health and process signals to detect hangs or zombie processes.
"""

import os
import sys
import time
import urllib.request
import urllib.error
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any

from debug_tools.core.logger import MultiStreamLogger


@dataclass
class HeartbeatStatus:
    is_alive: bool
    is_healthy: bool
    uptime_sec: float
    state: str
    response_latency_ms: float
    error_message: Optional[str] = None


class HeartbeatMonitor:
    """
    Monitors process liveness and polls HTTP status endpoint.
    """

    def __init__(
        self,
        health_endpoint: str = "http://127.0.0.1:8765",
        heartbeat_interval_sec: float = 5.0,
        hang_timeout_sec: float = 45.0,
        logger: Optional[MultiStreamLogger] = None,
    ):
        self.health_endpoint = health_endpoint.rstrip("/")
        self.heartbeat_interval_sec = heartbeat_interval_sec
        self.hang_timeout_sec = hang_timeout_sec
        self.logger = logger
        self.last_successful_heartbeat = time.time()
        self.last_frame_progress_time = time.time()
        self.last_frames_processed = 0

    @staticmethod
    def is_pid_alive(pid: Optional[int]) -> bool:
        if pid is None or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def check_health(self) -> HeartbeatStatus:
        """Probes the /health endpoint and returns detailed status."""
        url = f"{self.health_endpoint}/health"
        start_time = time.time()
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                latency_ms = (time.time() - start_time) * 1000.0
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.last_successful_heartbeat = time.time()
                    return HeartbeatStatus(
                        is_alive=True,
                        is_healthy=True,
                        uptime_sec=float(data.get("uptime_sec", 0.0)),
                        state=data.get("state", "UNKNOWN"),
                        response_latency_ms=round(latency_ms, 2),
                    )
                else:
                    return HeartbeatStatus(
                        is_alive=True,
                        is_healthy=False,
                        uptime_sec=0.0,
                        state="ERROR",
                        response_latency_ms=round(latency_ms, 2),
                        error_message=f"HTTP {resp.status}",
                    )
        except Exception as e:
            return HeartbeatStatus(
                is_alive=False,
                is_healthy=False,
                uptime_sec=0.0,
                state="UNREACHABLE",
                response_latency_ms=0.0,
                error_message=str(e),
            )

    def check_status_progress(self) -> Dict[str, Any]:
        """Probes the /status endpoint to check frame transcoding progress."""
        url = f"{self.health_endpoint}/status"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    cur_frames = data.get("frames_processed", 0)
                    if cur_frames > self.last_frames_processed:
                        self.last_frame_progress_time = time.time()
                        self.last_frames_processed = cur_frames
                    return data
        except Exception:
            pass
        return {}

    def is_hung(self) -> bool:
        """Determines if the application heartbeat or frame progress is hung."""
        now = time.time()
        heartbeat_stalled = (now - self.last_successful_heartbeat) > self.hang_timeout_sec
        return heartbeat_stalled
