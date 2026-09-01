# Black Magic Converter

An automated ingest and high-performance video transcoding suite for Blackmagic RAW (`.braw`) footage. This repository features both a headless DaVinci Resolve Studio engine (Python/CLI) and a native macOS SwiftUI desktop workstation application (Swift 6).

---

## 📂 Directory Structure & Folder Guide

```text
davinci-braw/
├── BRAW SDK/          # Official Blackmagic RAW SDK libraries, headers, docs, and samples (macOS, Win, Linux, iPadOS)
├── Documents/         # Reference manuals, Gen 5 Color Science guide, and DaVinci Resolve headless API documentation
├── changelog/         # Architecture specifications, changelogs, and deep-dive developer documentation
├── config/            # YAML configuration files for render presets, watch folder paths, stability guards, and LUTs
├── logs/              # Runtime log outputs for CLI, background daemon, project manager, and render pipeline
├── scripts/           # Shell automation scripts to launch headless Resolve, watcher daemons, and the native GUI
├── src/               # Core Python automation engine (CLI, watcher, DaVinci Resolve Scripting API client)
├── tests/             # Pytest test suites and mock unit tests for configuration parsing, watcher logic, and render engine
├── versions/          # Version-specific snapshots and standalone modular packages:
│   ├── v1-davinci-dependent/  # Version 1 CLI/Daemon headless engine with post-mortem & developer guides
│   └── v2-gui/                # Version 2 Native macOS SwiftUI application source & SwiftPM package
└── watch_folders/     # Hot-folder lifecycle staging directories for automated drop-in video transcoding
```

### Detailed Folder Breakdown

* **[`BRAW SDK/`](file:///Users/studio/Documents/Sandbox/davinci-braw/BRAW%20SDK)**: Contains Blackmagic Design's official Blackmagic RAW SDK (v4.x) frameworks, C++/Metal sample implementations, header definitions, and cross-platform native binaries (macOS, Windows, Linux, iPadOS).
* **[`Documents/`](file:///Users/studio/Documents/Sandbox/davinci-braw/Documents)**: Technical references including Blackmagic Generation 5 Color Science whitepapers, SDK documentation, and DaVinci Resolve headless API notes.
* **[`changelog/`](file:///Users/studio/Documents/Sandbox/davinci-braw/changelog)**: Detailed engineering specifications, concurrency models, state machine flowcharts, and version-by-version architectural logs.
* **[`config/`](file:///Users/studio/Documents/Sandbox/davinci-braw/config)**: Config templates (`config.default.yaml`) and active runtime configurations (`config.yaml`) defining export codecs (H.265/HEVC Main10), render quality, LUT paths, and watch folder timing thresholds.
* **[`logs/`](file:///Users/studio/Documents/Sandbox/davinci-braw/logs)**: Standardized rotation and execution log files for watcher processes, project setup, resolve client connections, and render progress.
* **[`scripts/`](file:///Users/studio/Documents/Sandbox/davinci-braw/scripts)**: Helper launch scripts:
  * `run_headless_dvr.sh`: Launches DaVinci Resolve in background headless mode (`-nogui`).
  * `start_watcher.sh`: Launches the automated folder monitor daemon.
  * `start_gui.sh`: Builds and launches the native SwiftUI macOS workstation application.
* **[`src/`](file:///Users/studio/Documents/Sandbox/davinci-braw/src)**: Python core engine:
  * `common/`: Configuration validation, rotating logger, and file watcher with stability-guard checking.
  * `dvr_engine/`: Resolve Studio client connector, automated project manager, timeline builder, 3D LUT applier, and render job monitoring.
  * `cli.py`: Command-line interface for manual single/batch transcodes, healthchecks, and LUT discovery.
* **[`tests/`](file:///Users/studio/Documents/Sandbox/davinci-braw/tests)**: Comprehensive test suite validating config schemas, watcher debounce/locking logic, and mock DaVinci Resolve API interactions without requiring hardware Resolve instances.
* **[`versions/`](file:///Users/studio/Documents/Sandbox/davinci-braw/versions)**:
  * `v1-davinci-dependent/`: Standalone package of the initial CLI/Watcher engine along with post-mortem analysis and troubleshooting guides.
  * `v2-gui/`: Native macOS SwiftUI workstation app built with Swift Package Manager, featuring real-time folder telemetry, interactive log views, custom transcode configurations, and process runner management.
* **[`watch_folders/`](file:///Users/studio/Documents/Sandbox/davinci-braw/watch_folders)**: Structured workflow directories that drive the automated ingest pipeline:
  * `00_IN_INGEST/`: Drop-in target for newly transferred `.braw` camera files.
  * `01_PROCESSING/`: Staging directory for clips actively rendering.
  * `02_COMPLETED_MP4/`: Destination directory for finished 10-bit H.265 MP4 files.
  * `03_ARCHIVE_BRAW/`: Safe archive for original `.braw` source files after successful export.
  * `99_FAILED/`: Isolation folder for corrupt, unstable, or failed clips.

---

## 🚀 Quick Start

### 1. Requirements
* macOS Sonoma 14+ or macOS Sequoia 15+ (Apple Silicon recommended)
* DaVinci Resolve Studio (with Scripting API enabled under *Preferences > System > General > External scripting using Local*)
* Python 3.10+
* Xcode 15+ or Swift 6 toolchain (for native SwiftUI GUI)

### 2. Install Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml pytest
```

### 3. Running the Automated Watcher Daemon
```bash
./scripts/start_watcher.sh
```
Or run the Python module directly:
```bash
python3 -m src.cli watch
```

### 4. Manual CLI Transcode
```bash
python3 -m src.cli transcode /path/to/clip.braw --output-dir ./watch_folders/02_COMPLETED_MP4
```

### 5. Running the Native macOS GUI (Version 2)
```bash
./scripts/start_gui.sh
```
Or build with SwiftPM:
```bash
cd versions/v2-gui
swift run
```

---

## ⚙️ Configuration

Settings can be customized in [`config/config.yaml`](file:///Users/studio/Documents/Sandbox/davinci-braw/config/config.yaml):

```yaml
watcher:
  scan_interval_seconds: 5
  stability_checks: 3
  stability_delay_seconds: 2

render:
  format: "mp4"
  codec: "H265"
  encoder: "Main10"
  resolution_match_source: true
  apply_lut: "Blackmagic Gen 5 to Extended Video"
  audio_codec: "AAC"
```

---

## 📄 License
Internal proprietary / Apache 2.0 (refer to project LICENSE if applicable). Blackmagic RAW SDK is subject to Blackmagic Design's SDK License Agreement.
