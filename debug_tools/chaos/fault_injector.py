"""
Chaos Simulation & Fault Injection Engine.
Allows stress-testing the resilience of the watchdog supervisor and error recovery pipelines.
"""

import os
import time
import random
import signal
from pathlib import Path
from typing import Optional

from debug_tools.core.logger import MultiStreamLogger


class FaultInjector:
    """
    Simulates real-world failures (SIGKILL, corrupted file inputs, latency hangs) based on probabilities.
    """

    def __init__(
        self,
        enabled: bool = False,
        probability_app_kill: float = 0.0,
        probability_corrupt_input: float = 0.0,
        probability_artificial_delay: float = 0.0,
        logger: Optional[MultiStreamLogger] = None,
    ):
        self.enabled = enabled
        self.probability_app_kill = probability_app_kill
        self.probability_corrupt_input = probability_corrupt_input
        self.probability_artificial_delay = probability_artificial_delay
        self.logger = logger

    def maybe_corrupt_input(self, file_path: Path) -> bool:
        """Randomly corrupts media file bytes to test decode failure handling."""
        if not self.enabled or self.probability_corrupt_input <= 0.0:
            return False

        if random.random() < self.probability_corrupt_input:
            try:
                if self.logger:
                    self.logger.log_watchdog("fault_injection_corrupt_input", data={"file": str(file_path)})
                with open(file_path, "r+b") as f:
                    f.seek(100)
                    f.write(b"\x00\xFF\x00\xFF" * 1024)
                return True
            except Exception as e:
                if self.logger:
                    self.logger.log_error("fault_injection_corrupt_failed", data={"error": str(e)})
        return False

    def maybe_kill_app(self, app_pid: Optional[int]) -> bool:
        """Randomly sends SIGKILL to the application process."""
        if not self.enabled or self.probability_app_kill <= 0.0 or not app_pid:
            return False

        if random.random() < self.probability_app_kill:
            try:
                if self.logger:
                    self.logger.log_watchdog("fault_injection_kill_app", data={"target_pid": app_pid})
                os.kill(app_pid, signal.SIGKILL)
                return True
            except Exception as e:
                if self.logger:
                    self.logger.log_error("fault_injection_kill_failed", data={"error": str(e)})
        return False

    def maybe_delay(self, max_delay_sec: float = 10.0) -> bool:
        """Randomly pauses to test hang/timeout detection."""
        if not self.enabled or self.probability_artificial_delay <= 0.0:
            return False

        if random.random() < self.probability_artificial_delay:
            delay = random.uniform(1.0, max_delay_sec)
            if self.logger:
                self.logger.log_watchdog("fault_injection_delay", data={"delay_sec": delay})
            time.sleep(delay)
            return True
        return False
