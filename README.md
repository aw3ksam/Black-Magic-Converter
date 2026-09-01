# Black Magic Converter

An automated ingest and high-performance video transcoding suite for Blackmagic RAW (`.braw`) footage. This repository features a cross-platform desktop workstation application built with **Electron Forge + Vite** (Version 3.1) backed by a standalone transcoding pipeline using the official **Blackmagic RAW SDK** and **FFmpeg**, a native macOS SwiftUI desktop app (Version 2), and a legacy DaVinci Resolve Studio engine (Version 1).

---

## 📂 Directory Structure & Folder Guide

```text
davinci-braw/
├── package.json        # NPM manifest for Electron Forge cross-platform desktop application (v3.1)
├── forge.config.js     # Electron Forge packaging, makers (DMG, ZIP, Squirrel, Deb, RPM), and Vite config
├── vite.*.config.mjs   # Vite bundler configurations for Main, Preload, and Renderer processes
├── build/              # macOS Hardened Runtime entitlements
├── assets/             # Multi-platform icons (.icns, .ico, .png) and bundled Blackmagic 3D LUTs (assets/luts/)
├── bin/                # Compiled native BRAW decoder binary (bin/braw_decode)
├── Documents/          # Technical documentation, color science reference, and official Blackmagic RAW SDK
│   ├── Blackmagic Generation 5 Color Science Technical Reference.pdf
│   ├── Blackmagic RAW SDK/     # Official BRAW SDK (Mac, Win, Linux, iPadOS frameworks, headers, & samples)
│   ├── BlackmagicRAW-SDK.pdf   # Official Blackmagic RAW SDK manual
│   └── headless-api.md         # Legacy DaVinci Resolve headless scripting API reference
├── changelog/          # Architecture specifications, changelogs, and deep-dive developer documentation
│   ├── README.md
│   ├── V2_GUI_CHANGELOG.md
│   └── V3_ELECTRON_CHANGELOG.md
├── config/             # YAML configuration files for render presets, watch folder paths, stability guards, and LUTs
│   ├── config.default.yaml
│   └── config.yaml
├── logs/               # Runtime log outputs for CLI, background daemon, and transcoding pipeline
├── scripts/            # Shell automation scripts to build native decoders, launch daemons, and package GUIs
│   ├── build_decoder.sh        # Compiles native Metal/CPU BRAW decoder (src/native/braw_decode.mm)
│   ├── start_electron.sh
│   ├── start_gui.sh
│   └── start_watcher.sh
├── src/                # Core Python automation engine & Electron desktop application
│   ├── native/         # Native C++/Objective-C Metal GPU accelerated BRAW frame extractor (braw_decode.mm)
│   ├── electron/       # Electron Forge desktop workstation (Main, Preload, Renderer)
│   ├── common/         # Shared configuration loader, structured logging, and watch-folder stability guards
│   ├── ffmpeg_engine/  # Standalone BRAW decoder bridge, 3D LUT manager, and FFmpeg transcoding pipeline
│   └── cli.py          # Unified CLI for hot-folder watcher, manual transcode, diagnostics, and LUT inspection
├── tests/              # Test suites verifying watcher debounce timers, decoder bridge, LUTs, and transcode pipelines
├── versions/           # Version-specific snapshots and standalone modular packages:
│   ├── v1-davinci-dependent/  # Version 1 CLI/Daemon headless engine with post-mortem & developer guides
│   ├── v2-gui/                # Version 2 Native macOS SwiftUI application source & SwiftPM package
│   └── v3-electron/           # Version 3 Cross-platform Electron Forge documentation & spec
├── watch_folders/      # Hot-folder lifecycle staging directories for automated drop-in video transcoding
│   ├── 00_IN_INGEST/          # Drop zone for new incoming camera media
│   ├── 01_PROCESSING/         # Active transcoding queue
│   ├── 02_COMPLETED_MP4/      # Finished 10-bit H.265 transcode outputs
│   ├── 03_ARCHIVE_BRAW/       # Archive location for processed source RAW files
│   └── 99_FAILED/             # Error quarantine folder
├── .gitignore          # Exclusions for OS artifacts, builds, logs, and media binaries
└── README.md           # Project overview, folder guide, and quick start documentation
```

### Detailed Folder Breakdown

* **[`Documents/`](file:///Users/studio/Documents/Sandbox/davinci-braw/Documents)**: Repository documentation and vendor references:
  * **`Blackmagic RAW SDK/`**: Official Blackmagic Design SDK frameworks (v4.x), Metal/C++ decoder libraries, sample projects, and header definitions across macOS, Windows, Linux, and iPadOS.
  * **`Blackmagic Generation 5 Color Science Technical Reference.pdf`**: Deep-dive technical whitepaper on Blackmagic Gen 5 color science curves and transforms.
  * **`BlackmagicRAW-SDK.pdf`**: Official SDK programming guide and API documentation.
  * **`headless-api.md`**: Guide for invoking DaVinci Resolve Studio in headless background mode (`-nogui`) and interacting via Python scripting APIs.
* **[`changelog/`](file:///Users/studio/Documents/Sandbox/davinci-braw/changelog)**: Engineering records, concurrency patterns, UI/UX architecture notes, and deep-dive technical changelogs (including [`V2_GUI_CHANGELOG.md`](file:///Users/studio/Documents/Sandbox/davinci-braw/changelog/V2_GUI_CHANGELOG.md)).
* **[`config/`](file:///Users/studio/Documents/Sandbox/davinci-braw/config)**: Configuration files for the transcoding system:
  * `config.default.yaml`: Base template and fallback settings.
  * `config.yaml`: Active runtime configuration setting export codecs (H.265 Main10), render quality, LUT presets, audio parameters, and file stability timers.
* **[`logs/`](file:///Users/studio/Documents/Sandbox/davinci-braw/logs)**: Automated runtime log rotation directory capturing trace messages from watcher daemons, DaVinci Resolve API calls, project management, and render status.
* **[`scripts/`](file:///Users/studio/Documents/Sandbox/davinci-braw/scripts)**: Executable shell entry points:
  * `run_headless_dvr.sh`: Launches DaVinci Resolve Studio with `-nogui` background execution.
  * `start_watcher.sh`: Starts the automated background hot-folder monitoring daemon.
  * `start_gui.sh`: Compiles and launches the Version 2 native macOS SwiftUI desktop app.
* **[`src/`](file:///Users/studio/Documents/Sandbox/davinci-braw/src)**: Primary Python automation and integration codebase:
  * `common/`: Config parsing/validation (`config.py`), logging setup (`logger.py`), and directory watcher with multi-step file stability checks (`watcher.py`).
  * `dvr_engine/`: Resolve client socket connection (`resolve_client.py`), timeline/project creation (`project_manager.py`), node LUT application, and render job queue management (`render_pipeline.py`).
  * `cli.py`: Unified CLI interface for running batch transcodes, watching directories, checking Resolve connectivity, and querying available LUTs.
* **[`tests/`](file:///Users/studio/Documents/Sandbox/davinci-braw/tests)**: Pytest suite verifying watcher debounce timers, POSIX file locking, configuration loading, and mocked DaVinci Resolve API pipelines.
* **[`versions/`](file:///Users/studio/Documents/Sandbox/davinci-braw/versions)**: Version packages:
  * `v1-davinci-dependent/`: Complete archive and post-mortem guide of the Version 1 CLI/Daemon workflow.
  * `v2-gui/`: Native macOS SwiftUI application built with Swift Package Manager (Swift 6), featuring real-time folder telemetry, live log stream, transcode queue controls, and customizable export settings.
* **[`watch_folders/`](file:///Users/studio/Documents/Sandbox/davinci-braw/watch_folders)**: Multi-stage hot-folder pipeline:
  * `00_IN_INGEST/`: Ingest drop directory for newly imported `.braw` camera clips.
  * `01_PROCESSING/`: Lock-stage directory where files are moved during active transcode.
  * `02_COMPLETED_MP4/`: Target output folder for finished 10-bit H.265 MP4 exports.
  * `03_ARCHIVE_BRAW/`: Storage location for original RAW files following successful export.
  * `99_FAILED/`: Quarantine directory for corrupt or aborted transcode attempts.

---

## 🚀 Quick Start

### 1. Requirements
* macOS Sonoma 14+ / macOS Sequoia 15+, Windows 10/11, or Linux (x64 / arm64)
* DaVinci Resolve Studio (with Scripting API enabled under *Preferences > System > General > External scripting using Local*)
* Python 3.10+
* Node.js 18+ (Node 20+ recommended)

### 2. Install Dependencies

#### Node / Electron Dependencies
```bash
npm install
```

#### Python Transcoding Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml pytest
```

### 3. Launching Version 3 Desktop Workstation (Electron Forge)
```bash
npm start
# Or using the launcher script:
./scripts/start_electron.sh
```

### 4. Packaging & Distributable Binaries (Electron Forge)
```bash
# Package local application binary
npm run package

# Build installers (DMG, ZIP, Squirrel, Deb, RPM)
npm run make
```

### 5. Running the Automated Watcher Daemon (CLI)
```bash
./scripts/start_watcher.sh
# Or directly:
python3 -m src.cli watch
```

### 6. Running the Native macOS SwiftUI GUI (Version 2)
```bash
./scripts/start_gui.sh
# Or via SwiftPM:
cd versions/v2-gui && swift run
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
