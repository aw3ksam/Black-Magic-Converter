"""
Standalone Visual & Machine-Readable Report Generator.
Complies with Section 5.7 of the Reliability & Observability Specification.
Generates comprehensive JSON, CSV, and self-contained single-file HTML5 dashboards.
"""

import os
import sys
import csv
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from debug_tools.core.database import DatabaseManager
from debug_tools.telemetry.leak_analyzer import LeakAnalyzer, LeakAnalysisReport


HTML_DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Black Magic Converter — Endurance Test Report: __TEST_RUN_ID__</title>
<style>
  :root {
    --bg-primary: #0f172a;
    --bg-card: #1e293b;
    --bg-card-hover: #334155;
    --border-color: #334155;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --accent-blue: #38bdf8;
    --accent-green: #4ade80;
    --accent-red: #f87171;
    --accent-yellow: #facc15;
    --accent-purple: #c084fc;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  body { background: var(--bg-primary); color: var(--text-primary); padding: 24px; line-height: 1.5; }
  .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 16px; margin-bottom: 24px; }
  .header h1 { font-size: 24px; font-weight: 700; color: var(--text-primary); display: flex; align-items: center; gap: 10px; }
  .header .badge { font-size: 13px; font-weight: 600; padding: 4px 10px; border-radius: 9999px; }
  .badge-success { background: rgba(74, 222, 128, 0.2); color: var(--accent-green); border: 1px solid var(--accent-green); }
  .badge-failed { background: rgba(248, 113, 113, 0.2); color: var(--accent-red); border: 1px solid var(--accent-red); }
  .grid-kpi { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 18px; }
  .card .label { font-size: 13px; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; }
  .card .value { font-size: 26px; font-weight: 700; margin-top: 6px; }
  .section-title { font-size: 18px; font-weight: 600; margin: 28px 0 14px 0; color: var(--text-primary); }
  .chart-container { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 10px; padding: 20px; margin-bottom: 24px; }
  .warning-box { background: rgba(250, 204, 21, 0.1); border: 1px solid var(--accent-yellow); border-radius: 8px; padding: 14px; margin-bottom: 20px; color: var(--accent-yellow); font-size: 14px; }
  .success-box { background: rgba(74, 222, 128, 0.1); border: 1px solid var(--accent-green); border-radius: 8px; padding: 14px; margin-bottom: 20px; color: var(--accent-green); font-size: 14px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
  th { background: #0b1120; color: var(--text-secondary); font-weight: 600; padding: 12px 14px; border-bottom: 1px solid var(--border-color); }
  td { padding: 12px 14px; border-bottom: 1px solid var(--border-color); color: var(--text-primary); }
  tr:hover { background: var(--bg-card-hover); }
  .status-tag { padding: 3px 8px; border-radius: 6px; font-weight: 600; font-size: 11px; }
  .tag-success { background: rgba(74, 222, 128, 0.2); color: var(--accent-green); }
  .tag-failed { background: rgba(248, 113, 113, 0.2); color: var(--accent-red); }
  .tag-running { background: rgba(56, 189, 248, 0.2); color: var(--accent-blue); }
  .search-box { width: 100%; padding: 10px 14px; border-radius: 6px; border: 1px solid var(--border-color); background: #0b1120; color: var(--text-primary); margin-bottom: 12px; font-size: 14px; }
  svg.sparkline { width: 100%; height: 160px; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1>Black Magic Converter — Endurance Test Run</h1>
    <div style="color: var(--text-secondary); font-size: 13px; margin-top: 4px;">
      Run ID: <strong>__TEST_RUN_ID__</strong> | Started: __START_TIME__ | Host OS: __HOST_OS__
    </div>
  </div>
  <div>
    <span class="badge __STATUS_BADGE_CLASS__">__STATUS__</span>
  </div>
</div>

<div class="grid-kpi">
  <div class="card">
    <div class="label">Total Jobs</div>
    <div class="value" style="color: var(--accent-blue);">__TOTAL_SUBMITTED__</div>
  </div>
  <div class="card">
    <div class="label">Pass Rate</div>
    <div class="value" style="color: var(--accent-green);">__PASS_RATE__%</div>
  </div>
  <div class="card">
    <div class="label">Completed / Failed</div>
    <div class="value">__TOTAL_COMPLETED__ / <span style="color: var(--accent-red);">__TOTAL_FAILED__</span></div>
  </div>
  <div class="card">
    <div class="label">Crashes & Recoveries</div>
    <div class="value" style="color: __CRASH_COLOR__;">__TOTAL_CRASHES__</div>
  </div>
  <div class="card">
    <div class="label">Mean Transcode Speed</div>
    <div class="value" style="color: var(--accent-purple);">__MEAN_FPS__ FPS</div>
  </div>
  <div class="card">
    <div class="label">Mean Realtime Factor</div>
    <div class="value" style="color: var(--accent-yellow);">__MEAN_RTF__x</div>
  </div>
</div>

__DIAGNOSTIC_ALERTS__

<div class="section-title">Telemetry Utilization Curves</div>
<div class="chart-container">
  <div style="display: flex; justify-content: space-between; margin-bottom: 12px; font-size: 13px; color: var(--text-secondary);">
    <span>App Memory RSS (MB) & CPU Utilization (%) over Time</span>
    <span>__SAMPLE_COUNT__ Telemetry Samples</span>
  </div>
  <svg class="sparkline" id="telemetryChart" viewBox="0 0 800 160" preserveAspectRatio="none">
    __CHART_SVG_PATHS__
  </svg>
  <div style="display: flex; gap: 20px; margin-top: 10px; font-size: 12px; color: var(--text-secondary);">
    <div style="display: flex; align-items: center; gap: 6px;"><span style="width: 12px; height: 3px; background: #38bdf8; display: inline-block;"></span> CPU %</div>
    <div style="display: flex; align-items: center; gap: 6px;"><span style="width: 12px; height: 3px; background: #c084fc; display: inline-block;"></span> RAM RSS MB</div>
    <div style="display: flex; align-items: center; gap: 6px;"><span style="width: 12px; height: 3px; background: #4ade80; display: inline-block;"></span> Disk Write MB/s</div>
  </div>
</div>

<div class="section-title">Job Execution Log & Bitstream Validation</div>
<div class="card" style="padding: 0; overflow-x: auto;">
  <div style="padding: 16px 16px 0 16px;">
    <input type="text" id="jobFilter" class="search-box" placeholder="Filter jobs by ID, filename, state, or failure category..." onkeyup="filterTable()">
  </div>
  <table id="jobsTable">
    <thead>
      <tr>
        <th>Job ID</th>
        <th>Source Clip</th>
        <th>Duration</th>
        <th>Wall Time</th>
        <th>Avg Speed</th>
        <th>RTF</th>
        <th>Status</th>
        <th>Failure Category / Message</th>
      </tr>
    </thead>
    <tbody>
      __TABLE_ROWS__
    </tbody>
  </table>
</div>

<script>
function filterTable() {
  var input = document.getElementById("jobFilter");
  var filter = input.value.toUpperCase();
  var table = document.getElementById("jobsTable");
  var tr = table.getElementsByTagName("tr");
  for (var i = 1; i < tr.length; i++) {
    var text = tr[i].textContent || tr[i].innerText;
    if (text.toUpperCase().indexOf(filter) > -1) {
      tr[i].style.display = "";
    } else {
      tr[i].style.display = "none";
    }
  }
}
</script>

</body>
</html>
"""


class ReportGenerator:
    """
    Generates summary.json, summary.csv, and standalone interactive HTML5 dashboard.
    """

    def __init__(self, db: DatabaseManager, reports_dir: str = "./reports"):
        self.db = db
        self.reports_dir = Path(reports_dir).resolve()
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.leak_analyzer = LeakAnalyzer()

    def generate_all_reports(self, test_run_id: str, sample_interval_sec: float = 2.0) -> Dict[str, Path]:
        """
        Creates JSON, CSV, and HTML reports for test_run_id.
        """
        run = self.db.get_test_run(test_run_id)
        if not run:
            raise ValueError(f"Test run not found in database: {test_run_id}")

        jobs = self.db.get_jobs_for_run(test_run_id)
        telemetry = self.db.get_telemetry_for_run(test_run_id)
        crashes = self.db.get_crashes_for_run(test_run_id)
        leak_report = self.leak_analyzer.analyze_telemetry_and_jobs(
            telemetry, jobs, sample_interval_sec=sample_interval_sec
        )

        json_path = self._generate_json(run, jobs, telemetry, crashes, leak_report)
        csv_path = self._generate_csv(run, jobs)
        html_path = self._generate_html(run, jobs, telemetry, crashes, leak_report)

        return {
            "json": json_path,
            "csv": csv_path,
            "html": html_path,
        }

    def _generate_json(
        self,
        run: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        telemetry: List[Dict[str, Any]],
        crashes: List[Dict[str, Any]],
        leak_report: LeakAnalysisReport,
    ) -> Path:
        target = self.reports_dir / f"{run['test_run_id']}_summary.json"
        data = {
            "test_run": run,
            "leak_analysis": leak_report.__dict__,
            "total_jobs": len(jobs),
            "total_telemetry_samples": len(telemetry),
            "total_crashes": len(crashes),
            "jobs": jobs,
            "crashes": crashes,
        }
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return target

    def _generate_csv(self, run: Dict[str, Any], jobs: List[Dict[str, Any]]) -> Path:
        target = self.reports_dir / f"{run['test_run_id']}_summary.csv"
        fieldnames = [
            "job_id", "test_run_id", "source_filename", "submitted_filename",
            "output_filename", "state", "result", "source_duration_sec",
            "output_duration_sec", "wall_time_sec", "avg_fps", "realtime_factor",
            "failure_category", "error_message"
        ]
        with open(target, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for j in jobs:
                writer.writerow(j)
        return target

    def _generate_html(
        self,
        run: Dict[str, Any],
        jobs: List[Dict[str, Any]],
        telemetry: List[Dict[str, Any]],
        crashes: List[Dict[str, Any]],
        leak_report: LeakAnalysisReport,
    ) -> Path:
        target = self.reports_dir / f"{run['test_run_id']}_report.html"

        total_sub = run.get("total_submitted", len(jobs))
        total_comp = run.get("total_completed", sum(1 for j in jobs if j.get("result") == "SUCCESS"))
        total_fail = run.get("total_failed", sum(1 for j in jobs if j.get("result") == "FAILED"))
        total_crash = run.get("total_crashes", len(crashes))

        pass_rate = round((total_comp / total_sub * 100.0), 1) if total_sub > 0 else 0.0

        valid_fps = [j["avg_fps"] for j in jobs if j.get("avg_fps") and j["avg_fps"] > 0]
        mean_fps = round(sum(valid_fps) / len(valid_fps), 1) if valid_fps else 0.0

        valid_rtf = [j["realtime_factor"] for j in jobs if j.get("realtime_factor") and j["realtime_factor"] > 0]
        mean_rtf = round(sum(valid_rtf) / len(valid_rtf), 2) if valid_rtf else 0.0

        status = run.get("status", "COMPLETED")
        badge_class = "badge-success" if status == "COMPLETED" and total_fail == 0 else "badge-failed"

        # Diagnostic alerts
        alerts_html = ""
        if leak_report.warnings:
            alerts_html = "<div class='warning-box'><strong>System Diagnostic Alerts:</strong><ul style='margin-top: 6px; padding-left: 20px;'>"
            for w in leak_report.warnings:
                alerts_html += f"<li>{w}</li>"
            alerts_html += "</ul></div>"
        else:
            alerts_html = "<div class='success-box'>✓ No resource leaks (RAM/Handles/Threads) or performance degradation anomalies detected.</div>"

        # Generate SVG Sparklines from Telemetry
        svg_paths = ""
        if len(telemetry) > 1:
            n = len(telemetry)
            cpu_pts = []
            ram_pts = []
            disk_pts = []

            max_ram = max(float(s.get("app_ram_rss_bytes", 0) or 0) / (1024 * 1024) for s in telemetry) or 1.0
            max_disk = max(float(s.get("disk_write_mbs", 0) or 0) for s in telemetry) or 1.0

            for i, s in enumerate(telemetry):
                x = (i / (n - 1)) * 800.0
                cpu = float(s.get("cpu_total_percent", 0) or 0)
                ram_mb = float(s.get("app_ram_rss_bytes", 0) or 0) / (1024 * 1024)
                disk = float(s.get("disk_write_mbs", 0) or 0)

                y_cpu = 150.0 - (min(cpu, 100.0) / 100.0 * 140.0)
                y_ram = 150.0 - (ram_mb / max_ram * 140.0)
                y_disk = 150.0 - (disk / max_disk * 140.0)

                cpu_pts.append(f"{x:.1f},{y_cpu:.1f}")
                ram_pts.append(f"{x:.1f},{y_ram:.1f}")
                disk_pts.append(f"{x:.1f},{y_disk:.1f}")

            svg_paths = f"""
            <polyline fill="none" stroke="#38bdf8" stroke-width="2" points="{' '.join(cpu_pts)}" />
            <polyline fill="none" stroke="#c084fc" stroke-width="2" points="{' '.join(ram_pts)}" />
            <polyline fill="none" stroke="#4ade80" stroke-width="1.5" stroke-dasharray="4" points="{' '.join(disk_pts)}" />
            """

        # Table rows
        table_rows = ""
        for j in jobs:
            tag_class = "tag-success" if j.get("result") == "SUCCESS" else "tag-failed"
            fail_desc = f"<strong>{j.get('failure_category', '')}</strong>: {j.get('error_message', '')}" if j.get("result") == "FAILED" else "-"
            table_rows += f"""
            <tr>
              <td><code>{j.get('job_id', '')}</code></td>
              <td>{j.get('source_filename', '')}</td>
              <td>{j.get('source_duration_sec', 0.0)}s</td>
              <td>{j.get('wall_time_sec', 0.0)}s</td>
              <td>{j.get('avg_fps', 0.0)} fps</td>
              <td>{j.get('realtime_factor', 0.0)}x</td>
              <td><span class="status-tag {tag_class}">{j.get('result', j.get('state'))}</span></td>
              <td>{fail_desc}</td>
            </tr>
            """

        html_content = HTML_DASHBOARD_TEMPLATE
        replacements = {
            "__TEST_RUN_ID__": str(run["test_run_id"]),
            "__START_TIME__": str(run.get("start_time_iso", "")),
            "__HOST_OS__": str(run.get("host_os", "")),
            "__STATUS__": str(status),
            "__STATUS_BADGE_CLASS__": badge_class,
            "__TOTAL_SUBMITTED__": str(total_sub),
            "__PASS_RATE__": str(pass_rate),
            "__TOTAL_COMPLETED__": str(total_comp),
            "__TOTAL_FAILED__": str(total_fail),
            "__TOTAL_CRASHES__": str(total_crash),
            "__CRASH_COLOR__": "var(--accent-red)" if total_crash > 0 else "var(--text-primary)",
            "__MEAN_FPS__": str(mean_fps),
            "__MEAN_RTF__": str(mean_rtf),
            "__DIAGNOSTIC_ALERTS__": alerts_html,
            "__SAMPLE_COUNT__": str(len(telemetry)),
            "__CHART_SVG_PATHS__": svg_paths,
            "__TABLE_ROWS__": table_rows,
        }

        for k, v in replacements.items():
            html_content = html_content.replace(k, v)

        with open(target, "w", encoding="utf-8") as f:
            f.write(html_content)

        return target
