# Debugging, Observability & Endurance Testing Toolkit — Implementation Notes

## Overview
This document records every file created, modified, or instrumented as part of the production-grade reliability and observability suite for `black-magic-converter`.

---

## Files Created

### 1. Core Framework (`debug_tools/core/`)
- `debug_tools/core/__init__.py`: Package initialization.
- `debug_tools/core/logger.py`: Multi-stream rotating NDJSON logger supporting 7 discrete streams (`application.log`, `errors.log`, `transcodes.log`, `performance.log`, `harness.log`, `watchdog.log`, `results.jsonl`), gzip compression of rotated backups (50 MB limit, 10 backups), and strict schema formatting.
- `debug_tools/core/health_server.py`: Lightweight embedded HTTP server (`127.0.0.1:8765`) providing `/health`, `/status`, `/ready`, and `/shutdown`.
- `debug_tools/core/database.py`: Thread-safe SQLite engine running in WAL mode (`test_runs.db`), managing tables `test_runs`, `jobs`, `events`, `telemetry_samples`, `crashes`, and corresponding indices.
- `debug_tools/core/state_machine.py`: Formal 13-state Job State Machine enforcing the transition matrix and logging all transition events to SQLite and NDJSON.

### 2. Video Ingestion & Test Harness (`debug_tools/harness/`)
- `debug_tools/harness/__init__.py`: Package initialization.
- `debug_tools/harness/queue_manager.py`: Test video discovery, SHA-256 chunked hashing, and sequencing (`sequential`, `alphabetical`, `random`, `seeded_random`, `loop`).
- `debug_tools/harness/staging.py`: 3-step atomic ingestion handler (`.incoming_<job_id>.tmp` -> `os.fsync` -> `os.replace`) with `/ready` health synchronization.
- `debug_tools/harness/test_runner.py`: Main endurance loop managing job execution, timeout guards (`startup_timeout_sec`, `max_job_timeout_sec`, `hang_timeout_sec`), and output detection.

### 3. Media Inspection & Validation (`debug_tools/validation/`)
- `debug_tools/validation/__init__.py`: Package initialization.
- `debug_tools/validation/media_inspector.py`: `ffprobe` JSON stream inspection extracting resolution, FPS, duration, color space, transfer characteristics, and audio stream layout.
- `debug_tools/validation/bitstream_validator.py`: Bitstream null-mux decode pass (`ffmpeg -v error -i <output> -f null -`), duration/FPS tolerance checks, and 18-category failure classification.

### 4. Telemetry & Resource Analysis (`debug_tools/telemetry/`)
- `debug_tools/telemetry/__init__.py`: Package initialization.
- `debug_tools/telemetry/collector.py`: Background daemon sampling CPU, RAM RSS/VMS, GPU util/VRAM, Disk I/O MB/s, free space, thread count, and open FDs into `telemetry_samples` and `performance.log`.
- `debug_tools/telemetry/leak_analyzer.py`: Linear regression slope calculator for RAM growth (MB/hr), thread growth, FD growth, and moving-average FPS degradation / thermal throttling.

### 5. Supervisor & Crash Recovery (`debug_tools/supervisor/`)
- `debug_tools/supervisor/__init__.py`: Package initialization.
- `debug_tools/supervisor/heartbeat.py`: Multi-process liveness and HTTP health status probe.
- `debug_tools/supervisor/artifact_packager.py`: Crash and failure evidence packager (`failures/<job_id>/` with `metadata.json`, `source_ffprobe.json`, `output_ffprobe.json`, `extracted_logs.jsonl`, `telemetry.csv`, `stderr.txt`, `crash.json`).
- `debug_tools/supervisor/watchdog.py`: Independent process supervisor with exponential backoff (`0s`, `2s`, `5s`, `15s`, `30s`), crash-loop limiter (max 5 consecutive restarts), and state reconciliation.

### 6. Reporting Engine (`debug_tools/reporting/`)
- `debug_tools/reporting/__init__.py`: Package initialization.
- `debug_tools/reporting/report_generator.py`: Generates `summary.json`, `summary.csv`, and zero-external-dependency, self-contained interactive single-file `report.html` with dark mode, KPI cards, SVG sparklines, and filterable job logs.

### 7. Chaos & CLI Entry Point
- `debug_tools/chaos/__init__.py`: Package initialization.
- `debug_tools/chaos/fault_injector.py`: Fault injection engine simulating SIGKILL, media corruption, and latency delays.
- `debug_tools/config/endurance_config.yaml`: Central YAML configuration.
- `debug_tools/run_endurance.py`: Unified single-command CLI entry point.
- `debug_tools/README.md`: Usage guide and CLI documentation.

---

## Core Application Instrumentation (`src/`)

- `src/common/watcher.py`:
  - Added non-invasive integration with `global_app_state` (`set_stabilizing`, `set_transcoding`, `set_idle`).
  - Wrapped candidate processing in defensive exception guards so logger/telemetry errors never crash the core watcher.
- `src/cli.py`:
  - Added embedded Health API startup on `watch` command.
  - Added `--health-port` parameter (default `8765`).
- `src/ffmpeg_engine/ffmpeg_pipeline.py`:
  - Added progress reporting to `global_app_state.update_progress()` across both in-process Metal and fallback pipe transcode routes.

---

## Verification Results
- All unit tests in `debug_tools/tests/` pass.
- All core application tests in `tests/` (`npm test`) pass with zero regressions.
