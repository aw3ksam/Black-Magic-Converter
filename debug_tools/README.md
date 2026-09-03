# Black Magic Converter — Reliability, Observability & Endurance Testing Suite

This directory contains the production-grade debugging, observability, and automated endurance testing toolkit for `black-magic-converter`.

---

## Quick Start

### 1. Launch the Interactive Debug & Telemetry Dashboard
```bash
python3 debug_tools/serve_dashboard.py --open
```
Or open `debug_tools/dashboard.html` directly in any web browser, or navigate to `http://127.0.0.1:8765/dashboard` when the transcoder or watch daemon is running.

### 2. Run a 60-Minute Endurance Test
```bash
python3 debug_tools/run_endurance.py --config debug_tools/config/endurance_config.yaml --duration 60
```

### 3. Run a Quick 5-Minute Smoke Test with Seeded Random Video Ingestion
```bash
python3 debug_tools/run_endurance.py --duration 5 --order seeded_random --seed 42
```

### 4. Run with Fault Injection (Chaos Simulation)
```bash
python3 debug_tools/run_endurance.py --duration 10 --fault-injection
```

### 5. Control Blackmagic Camera (PYXIS 6K) & Automated Ingest
- **Dashboard Web UI**: Launch `python3 debug_tools/serve_dashboard.py --open` and switch to the **Blackmagic Camera Lab** tab.
- **Tool 1 (Auto Video Clip Transfer)**: Toggle active to snapshot baseline and download newly shot clips over FTP (`ftp://PYXIS-6K.local`) directly to `00_IN_INGEST`.
- **Tool 2 (Batch Recording Generator)**: Select a 1-hour preset (15s x 240, 30s x 120, 45s x 80, 60s x 60) or custom sequence and trigger automatic camera recording.
- **Run Endurance with Live Camera Batches**:
```bash
python3 debug_tools/run_endurance.py --duration 30 --camera-batch --camera-ip 192.168.1.118 --camera-clip-duration 30
```

---

## Directory Architecture

```
debug_tools/
├── config/
│   └── endurance_config.yaml  # Central YAML configuration
├── core/
│   ├── database.py            # SQLite schema manager in WAL mode (test_runs.db)
│   ├── health_server.py       # Embedded localhost HTTP status API (:8765)
│   ├── logger.py              # Multi-stream rotating NDJSON logger with gzip backups
│   └── state_machine.py       # Formal 13-state Job State Machine
├── harness/
│   ├── queue_manager.py       # Video discovery, SHA-256 hashing, and deterministic ordering
│   ├── staging.py             # Atomic ingestion (.tmp -> fsync -> rename) and /ready sync
│   └── test_runner.py         # Main endurance test orchestration loop
├── validation/
│   ├── media_inspector.py     # ffprobe extraction and metadata parser
│   └── bitstream_validator.py # Full null-mux decode pass (-f null -) and 18 failure classifiers
├── telemetry/
│   ├── collector.py           # psutil + GPU live metrics sampler
│   └── leak_analyzer.py       # RAM regression slope, handle leak, and thermal throttling detector
├── supervisor/
│   ├── watchdog.py            # Independent process supervisor and exponential restart backoff
│   ├── heartbeat.py           # Cross-process heartbeat probe
│   └── artifact_packager.py   # Crash and failure bundle creator (failures/<job_id>/)
├── reporting/
│   └── report_generator.py    # Generates summary.json, summary.csv, and standalone report.html
├── chaos/
│   └── fault_injector.py      # Chaos simulation (SIGKILL, input corruption, artificial delay)
├── tests/                     # Automated unit and integration test suite
└── run_endurance.py           # Unified CLI entry point
```

---

## Running the Unit Test Suite

```bash
python3 -m unittest discover -s debug_tools/tests -p "test_*.py"
```
