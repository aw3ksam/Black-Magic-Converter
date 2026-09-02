"""
Resource Leak & Performance Degradation Anomaly Analyzer.
Complies with Section 5.4 of the Reliability & Observability Specification.
Computes linear regression slopes for memory, thread, and file handle growth, and detects thermal/FPS decay.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class LeakAnalysisReport:
    total_samples: int
    ram_growth_slope_mb_per_hr: float
    is_suspected_ram_leak: bool
    thread_growth_slope_per_hr: float
    is_suspected_thread_leak: bool
    fd_growth_slope_per_hr: float
    is_suspected_fd_leak: bool
    initial_fps_avg: float
    final_fps_avg: float
    fps_degradation_percent: float
    is_suspected_thermal_throttling: bool
    warnings: List[str] = field(default_factory=list)


class LeakAnalyzer:
    """
    Analyzes time-series telemetry samples and job records to detect leak slopes and anomalies.
    """

    def __init__(
        self,
        ram_leak_threshold_mb_hr: float = 50.0,
        thread_leak_threshold_hr: float = 5.0,
        fd_leak_threshold_hr: float = 5.0,
        fps_degradation_threshold_pct: float = 20.0,
    ):
        self.ram_leak_threshold_mb_hr = ram_leak_threshold_mb_hr
        self.thread_leak_threshold_hr = thread_leak_threshold_hr
        self.fd_leak_threshold_hr = fd_leak_threshold_hr
        self.fps_degradation_threshold_pct = fps_degradation_threshold_pct

    @staticmethod
    def _linear_regression_slope(x_vals: List[float], y_vals: List[float]) -> float:
        """
        Calculates the slope (beta) of standard ordinary least squares linear regression.
        y = alpha + beta * x
        """
        n = len(x_vals)
        if n < 2:
            return 0.0

        mean_x = sum(x_vals) / n
        mean_y = sum(y_vals) / n

        num = sum((x_vals[i] - mean_x) * (y_vals[i] - mean_y) for i in range(n))
        den = sum((x_vals[i] - mean_x) ** 2 for i in range(n))

        if abs(den) < 1e-9:
            return 0.0

        return num / den

    def analyze_telemetry_and_jobs(
        self,
        telemetry_samples: List[Dict[str, Any]],
        jobs: List[Dict[str, Any]],
        sample_interval_sec: float = 2.0,
    ) -> LeakAnalysisReport:
        """
        Analyzes telemetry samples and completed jobs for resource leakage and FPS degradation.
        """
        warnings: List[str] = []
        n_samples = len(telemetry_samples)

        if n_samples < 2:
            return LeakAnalysisReport(
                total_samples=n_samples,
                ram_growth_slope_mb_per_hr=0.0,
                is_suspected_ram_leak=False,
                thread_growth_slope_per_hr=0.0,
                is_suspected_thread_leak=False,
                fd_growth_slope_per_hr=0.0,
                is_suspected_fd_leak=False,
                initial_fps_avg=0.0,
                final_fps_avg=0.0,
                fps_degradation_percent=0.0,
                is_suspected_thermal_throttling=False,
                warnings=["Insufficient telemetry data points for regression analysis"],
            )

        # 1. RAM RSS Analysis (convert to MB and hours)
        # We index samples by time in hours (using sample index * sample_dt or timestamps)
        time_hours = [i * (sample_interval_sec / 3600.0) for i in range(n_samples)]
        ram_mb = [float(s.get("app_ram_rss_bytes", 0) or 0) / (1024.0 * 1024.0) for s in telemetry_samples]
        threads = [float(s.get("active_thread_count", 0) or 0) for s in telemetry_samples]
        fds = [float(s.get("open_file_handles", 0) or 0) for s in telemetry_samples]

        ram_slope = self._linear_regression_slope(time_hours, ram_mb)
        thread_slope = self._linear_regression_slope(time_hours, threads)
        fd_slope = self._linear_regression_slope(time_hours, fds)

        is_ram_leak = ram_slope > self.ram_leak_threshold_mb_hr
        if is_ram_leak:
            warnings.append(f"Suspected Memory Leak: App RAM RSS is growing at {ram_slope:.2f} MB/hour.")

        is_thread_leak = thread_slope > self.thread_leak_threshold_hr
        if is_thread_leak:
            warnings.append(f"Suspected Thread Leak: Active threads growing at {thread_slope:.1f} threads/hour.")

        is_fd_leak = fd_slope > self.fd_leak_threshold_hr
        if is_fd_leak:
            warnings.append(f"Suspected File Handle Leak: Open FDs growing at {fd_slope:.1f} handles/hour.")

        # 2. FPS Degradation Analysis across completed jobs
        valid_fps_jobs = [j["avg_fps"] for j in jobs if j.get("avg_fps") and j["avg_fps"] > 0]
        initial_fps = 0.0
        final_fps = 0.0
        fps_deg_pct = 0.0
        is_thermal = False

        if len(valid_fps_jobs) >= 4:
            quarter = max(1, len(valid_fps_jobs) // 4)
            initial_fps = sum(valid_fps_jobs[:quarter]) / quarter
            final_fps = sum(valid_fps_jobs[-quarter:]) / quarter

            if initial_fps > 0:
                fps_deg_pct = max(0.0, (initial_fps - final_fps) / initial_fps * 100.0)
                if fps_deg_pct >= self.fps_degradation_threshold_pct:
                    is_thermal = True
                    warnings.append(
                        f"Suspected Thermal/Pipeline Degradation: Average transcode speed dropped "
                        f"from {initial_fps:.1f} FPS to {final_fps:.1f} FPS ({fps_deg_pct:.1f}% reduction)."
                    )
        elif valid_fps_jobs:
            initial_fps = valid_fps_jobs[0]
            final_fps = valid_fps_jobs[-1]

        return LeakAnalysisReport(
            total_samples=n_samples,
            ram_growth_slope_mb_per_hr=round(ram_slope, 2),
            is_suspected_ram_leak=is_ram_leak,
            thread_growth_slope_per_hr=round(thread_slope, 2),
            is_suspected_thread_leak=is_thread_leak,
            fd_growth_slope_per_hr=round(fd_slope, 2),
            is_suspected_fd_leak=is_fd_leak,
            initial_fps_avg=round(initial_fps, 2),
            final_fps_avg=round(final_fps, 2),
            fps_degradation_percent=round(fps_deg_pct, 2),
            is_suspected_thermal_throttling=is_thermal,
            warnings=warnings,
        )
