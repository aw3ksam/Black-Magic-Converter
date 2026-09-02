#!/usr/bin/env python3
"""
Unified Entry Point for Black Magic Converter Endurance Testing & Observability Suite.
Executes unattended endurance test runs, supervises subprocesses, captures dense telemetry,
and generates self-contained visual and machine-readable reports.
"""

import os
import sys
import time
import argparse
import signal
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

# Ensure workspace root is in sys.path when invoked directly as a script
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required for the endurance testing toolkit.")
    print("Install with: pip3 install PyYAML")
    sys.exit(1)

from debug_tools.core.database import DatabaseManager
from debug_tools.core.logger import get_logger
from debug_tools.supervisor.watchdog import WatchdogSupervisor
from debug_tools.harness.test_runner import EnduranceTestRunner
from debug_tools.reporting.report_generator import ReportGenerator


def load_yaml_config(path: str) -> dict:
    p = Path(path).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"Configuration file not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def main():
    parser = argparse.ArgumentParser(
        description="Production-Grade Endurance Testing & Observability Suite for black-magic-converter"
    )
    parser.add_argument(
        "-c", "--config",
        type=str,
        default="debug_tools/config/endurance_config.yaml",
        help="Path to endurance configuration YAML file",
    )
    parser.add_argument(
        "-d", "--duration",
        type=float,
        default=None,
        help="Test duration in minutes (overrides config)",
    )
    parser.add_argument(
        "--order",
        type=str,
        choices=["sequential", "alphabetical", "random", "seeded_random", "loop"],
        default=None,
        help="Video sequencing order",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for deterministic seeded_random mode",
    )
    parser.add_argument(
        "--fault-injection",
        action="store_true",
        help="Enable fault injection & chaos simulation",
    )
    parser.add_argument(
        "--no-app-spawn",
        action="store_true",
        help="Do not spawn the transcoding application (assume already running externally)",
    )

    args = parser.parse_args()

    config = load_yaml_config(args.config)

    # CLI Overrides
    if args.duration is not None:
        config.setdefault("endurance_test", {})["test_duration_minutes"] = args.duration
    if args.order is not None:
        config.setdefault("endurance_test", {})["video_order"] = args.order
    if args.seed is not None:
        config.setdefault("endurance_test", {})["random_seed"] = args.seed
    if args.fault_injection:
        config.setdefault("fault_injection", {})["enabled"] = True

    test_run_id = f"tr_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{os.urandom(3).hex()}"
    logs_dir = config.get("directories", {}).get("logs_dir", "./logs")
    db_path = config.get("directories", {}).get("db_path", "./database/test_runs.db")
    reports_dir = config.get("directories", {}).get("reports_dir", "./reports")
    failures_dir = config.get("directories", {}).get("failure_artifacts_dir", "./failures")

    logger = get_logger(logs_dir=logs_dir, test_run_id=test_run_id, component="harness", echo_console=True)
    db = DatabaseManager(db_path=db_path)

    print("\n" + "=" * 70)
    print(" Black Magic Converter — Production Endurance Testing Suite")
    print("=" * 70)
    print(f"• Test Run ID:        {test_run_id}")
    print(f"• Target Duration:    {config.get('endurance_test', {}).get('test_duration_minutes', 60)} minutes")
    print(f"• Video Order:        {config.get('endurance_test', {}).get('video_order', 'seeded_random')}")
    print(f"• Database Store:     {db_path}")
    print(f"• Multi-Stream Logs:  {logs_dir}")
    print(f"• Reports Output:     {reports_dir}")
    print("=" * 70 + "\n")

    supervisor: Optional[WatchdogSupervisor] = None

    if not args.no_app_spawn:
        app_cmd = config.get("application", {}).get("command", ["python3", "-u", "-m", "src.cli", "watch"])
        health_ep = config.get("application", {}).get("health_endpoint", "http://127.0.0.1:8765")
        working_dir = config.get("application", {}).get("working_dir", ".")
        hang_timeout = float(config.get("timeouts", {}).get("hang_timeout_sec", 45))
        max_restarts = int(config.get("thresholds", {}).get("max_consecutive_restarts", 5))

        supervisor = WatchdogSupervisor(
            app_command=app_cmd,
            test_run_id=test_run_id,
            db=db,
            logger=logger,
            health_endpoint=health_ep,
            max_consecutive_restarts=max_restarts,
            hang_timeout_sec=hang_timeout,
            failures_dir=failures_dir,
            logs_dir=logs_dir,
            working_dir=working_dir,
        )
        print("Launching supervised transcoding application process...")
        if not supervisor.start_application():
            print("ERROR: Failed to launch transcoding application.")
            sys.exit(1)

        # Allow application to bind health port
        time.sleep(2.0)

    # Initialize and execute test harness
    runner = EnduranceTestRunner(
        config=config,
        test_run_id=test_run_id,
        db=db,
        logger=logger,
    )
    runner.supervisor = supervisor

    if supervisor and supervisor.app_process:
        runner.telemetry.set_app_pid(supervisor.app_process.pid)
        runner._supervisor_pid = supervisor.app_process.pid

    def handle_shutdown(signum, frame):
        print("\nShutdown requested. Finalizing active jobs and generating reports...")
        runner._interrupted = True
        runner.running = False

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    try:
        runner_summary = runner.run_endurance_loop()
    finally:
        if supervisor:
            print("Shutting down supervised application...")
            supervisor.stop()

    # Generate Reports
    print("\nGenerating final machine-readable summaries and visual dashboard...")
    reporter = ReportGenerator(db=db, reports_dir=reports_dir)
    report_paths = reporter.generate_all_reports(test_run_id)

    print("\n" + "=" * 70)
    print(" Endurance Test Completed Successfully")
    print("=" * 70)
    print(f"• Total Jobs Submitted: {runner.total_submitted}")
    print(f"• Completed (Success):  {runner.total_completed}")
    print(f"• Failed:               {runner.total_failed}")
    print(f"• Crashes / Recoveries: {runner.total_crashes}")
    print(f"• HTML Dashboard:       {report_paths['html']}")
    print(f"• JSON Summary:         {report_paths['json']}")
    print(f"• CSV Summary:          {report_paths['csv']}")
    print("=" * 70 + "\n")

    db.close()
    logger.close()


if __name__ == "__main__":
    main()
