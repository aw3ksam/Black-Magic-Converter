# Black Magic Converter

An automated ingest and high-performance video transcoding suite for Blackmagic RAW (`.braw`) footage. This repository features a cross-platform desktop workstation application built with **Electron Forge + Vite** (Version 4.0) backed by an in-process, zero-copy **Metal GPU 3D LUT + Apple VideoToolbox / FFmpeg** transcoding pipeline, direct **Blackmagic Camera REST & FTP Auto-Ingest** (PYXIS 6K, Cinema Camera 6K, Pocket series), a native macOS SwiftUI desktop app (Version 2), and a legacy DaVinci Resolve Studio engine (Version 1).

---

## ⚡ Architecture & Engine Evolution

* **Version 4.0 (Production - Camera Ingest & Metal Transcoding Suite)**:
  * Integrated **Tool 1 (Auto Video Clip Transfer)** into the main desktop workstation application: connects to Blackmagic cameras (default IP: `192.168.1.118`, FTP: `ftp://PYXIS-6K.local`) over REST & FTP, isolates newly recorded clips via atomic baseline snapshots, detects `recording: false` state, and automatically downloads new `.braw` takes into `00_IN_INGEST`.
  * Integrated **Tool 1 and Tool 2 (Batch Video Recording Generator)** into the comprehensive `debug_tools/` testing suite with 1-hour presets (15s, 30s, 45s, 60s clips) for automated endurance qualification.
  * Direct in-process Metal GPU 3D LUT Compute Shader (`src/native/lut_3d_metal.h`) and `CVPixelBuffer` hardware encoding via Apple VideoToolbox / `AVAssetWriter`.
  * User-configurable camera IP and FTP parameters in both GUI Settings and Debug Dashboard.
* **Version 3.2 (Standalone In-Process Metal + VideoToolbox)**: 
  * Direct in-process Metal GPU 3D LUT Compute Shader and VideoToolbox HEVC pipeline (~38 fps on 6K PYXIS footage, ~60s total for 8GB RAW clip).
* **Version 3.1 (Standalone FFmpeg Pipe Engine)**:
  * Initial DaVinci-independent architecture using `braw_decode` stdout pipe to FFmpeg.
* **Version 2 (macOS SwiftUI GUI)**:
  * Native macOS SwiftUI application (`versions/v2-gui/`) communicating via DaVinci Resolve scripting APIs.
* **Version 1 (Headless DaVinci CLI Daemon)**:
  * Legacy headless Python daemon (`versions/v1-davinci-dependent/`) controlling DaVinci Resolve Studio via local socket IPC.

---

## 📂 Directory Structure & Folder Guide

```text
davinci-braw/
├── package.json        # NPM manifest for Electron Forge cross-platform desktop application (v3.2)
├── forge.config.js     # Electron Forge packaging, extraResource bundling, and DMG/ZIP makers
├── vite.*.config.mjs   # Vite bundler configurations for Main, Preload, and Renderer processes
├── entitlements/       # macOS Hardened Runtime entitlements (.plist)
├── assets/             # Multi-platform icons (.icns, .ico, .png) and 23 bundled Blackmagic 3D LUTs (assets/luts/)
├── bin/                # Compiled native BRAW Metal GPU decoder & transcoder binary (bin/braw_decode)
├── Documents/          # Technical documentation, color science reference, and official Blackmagic RAW SDK
│   ├── Blackmagic Generation 5 Color Science Technical Reference.pdf
│   ├── Blackmagic RAW SDK/     # Official BRAW SDK (Mac, Win, Linux, iPadOS frameworks, headers, & samples)
│   ├── BlackmagicRAW-SDK.pdf   # Official Blackmagic RAW SDK manual
│   └── headless-api.md         # Legacy DaVinci Resolve headless scripting API reference
├── changelog/          # Architecture specifications, changelogs, and deep-dive developer documentation
│   ├── README.md
│   ├── V3_2_NATIVE_VIDEOTOOLBOX_CHANGELOG.md # v3.2 in-process Metal + VideoToolbox engine specifications
│   ├── V3_1_FFMPEG_CHANGELOG.md             # v3.1 standalone engine post-mortem & design
│   ├── V3_ELECTRON_CHANGELOG.md             # v3.0 Electron desktop app overhaul
│   └── V2_GUI_CHANGELOG.md                  # v2.0 native SwiftUI GUI specification
├── config/             # YAML configuration files for render presets, watch folder paths, and LUT presets
│   ├── config.default.yaml
│   └── config.yaml
├── logs/               # Automated runtime logs (also logged to ~/Library/Logs/BlackMagicConverter/main.log)
├── scripts/            # Shell automation scripts to build native decoders, launch daemons, and package GUIs
│   ├── build_decoder.sh        # Compiles native Metal GPU BRAW decoder & VideoToolbox transcoder
│   ├── start_electron.sh       # Developer launcher for Electron Forge app
│   ├── start_gui.sh            # Developer launcher for v2 SwiftUI app
│   └── start_watcher.sh        # Background folder watcher daemon launcher
├── src/                # Core Python automation engine & Electron desktop application
│   ├── native/         # Native Objective-C++ Metal GPU 3D LUT and VideoToolbox engine (braw_decode.mm)
│   ├── electron/       # Electron Forge desktop workstation (Main, Preload, Renderer)
│   ├── common/         # Shared configuration loader, structured logging, and watch-folder stability guards
│   ├── ffmpeg_engine/  # Standalone BRAW decoder bridge, 3D LUT manager, and pipeline router
│   └── cli.py          # Unified CLI for hot-folder watcher, manual transcode, diagnostics, and LUT inspection
├── tests/              # Test suites verifying watcher debounce timers, decoder bridge, LUTs, and transcode pipelines
├── versions/           # Version-specific snapshots and standalone modular packages:
│   ├── v1-davinci-dependent/  # Version 1 CLI/Daemon headless engine with post-mortem & developer guides
│   ├── v2-gui/                # Version 2 Native macOS SwiftUI application source & SwiftPM package
│   ├── v3-electron/           # Version 3 Cross-platform Electron Forge snapshot
│   └── v4-camera-ingest/      # Version 4 Camera Ingest (PYXIS 6K) & Electron Forge snapshot
├── watch_folders/      # Hot-folder lifecycle staging directories for automated drop-in video transcoding
│   ├── 00_IN_INGEST/          # Drop zone for new incoming camera media
│   ├── 01_PROCESSING/         # Active transcoding queue
│   ├── 02_COMPLETED_MP4/      # Finished 10-bit H.265 transcode outputs
│   ├── 03_ARCHIVE_BRAW/       # Archive location for processed source RAW files
│   └── 99_FAILED/             # Error quarantine folder
├── AGENTS.md           # Core architecture rules, security invariants, and build guidelines for developers & AI agents
├── HANDOFF_V3_2_NATIVE_ENGINE.md # Complete project status and developer handoff
└── README.md           # Project overview, folder guide, and quick start documentation
```

---

## 🚀 Quick Start

### 1. Requirements
* macOS Sonoma 14+ / macOS Sequoia 15+, Windows 10/11, or Linux (x64 / arm64)
* Python 3.10+
* Node.js 18+ (Node 20+ recommended)
* Optional: FFmpeg (used for audio muxing & container tagging)

### 2. Install Dependencies & Build Native Engine

```bash
# 1. Install Node/Electron dependencies
npm install

# 2. Build the Native Metal GPU BRAW Decoder & In-Process Transcoder
npm run build:decoder
```

### 3. Launching Version 3 Desktop Workstation (Electron)

```bash
npm start
# Or using the launcher script:
./scripts/start_electron.sh
```

### 4. Packaging Standalone Application & DMG Installer

```bash
# Package standalone macOS application (.app)
npm run package

# Build DMG and ZIP distributables
npm run make
```

* **Packaged App**: `out/Black Magic Converter-darwin-arm64/Black Magic Converter.app`
* **DMG Installer**: `out/make/BlackMagicConverter.dmg`

### 5. CLI Transcoding & Watcher Commands

```bash
# Transcode a single clip directly with in-process Metal GPU engine
python3 -m src.cli transcode "samples/A001_08071422_C269.braw" -o "output_dir"

# Start the automated hot-folder watcher daemon
python3 -m src.cli watch

# List all bundled 3D LUT presets
python3 -m src.cli list-luts
```

---

## ⚙️ Configuration

Runtime settings are managed in [`config/config.yaml`](file:///Users/studio/Documents/Sandbox/davinci-braw/config/config.yaml):

```yaml
storage:
  ingest_dir: "watch_folders/00_IN_INGEST"
  processing_dir: "watch_folders/01_PROCESSING"
  completed_dir: "watch_folders/02_COMPLETED_MP4"
  archive_dir: "watch_folders/03_ARCHIVE_BRAW"
  failed_dir: "watch_folders/99_FAILED"

watcher:
  poll_interval: 2.0
  stability_checks: 3
  stability_delay: 2.0
  extensions: [".braw"]
  include_sidecars: true

transcode:
  container: "mp4"
  codec: "H265"
  encoding_profile: "Main10"
  bitrate_mbps: 50
  resolution: "source"
  audio:
    codec: "aac"
    sample_rate: 48000
    bitrate_kbps: 320
  color:
    mode: "lut"
    lut_path: "Blackmagic Gen 5 Film to Extended Video.cube"

engine:
  type: "native"
  hardware_acceleration: true
```

---

## 🧪 Testing & Verification

```bash
# Run unit & integration test suite
npm test
```

---

## 📄 License
Internal proprietary / Apache 2.0. Blackmagic RAW SDK is subject to Blackmagic Design's SDK License Agreement.
