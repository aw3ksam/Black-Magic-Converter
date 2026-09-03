# Version 4.0: Blackmagic Camera Tooling & Automated Ingest Architecture

**Release Version**: v4.0.0  
**Date**: September 2026  
**Primary Platforms**: macOS (Apple Silicon & Intel), Windows, Linux  
**Target Hardware**: Blackmagic PYXIS 6K, Cinema Camera 6K, URSA Cine, Pocket Cinema Cameras  

---

## 1. Executive Summary

**Version 4.0** upgrades the Blackmagic RAW (BRAW) Video Converter from a purely local hot-folder watcher into a complete **hardware-integrated ingest and transcoding pipeline**.

By integrating **Tool 1 (Auto Video Clip Transfer)** natively into the main Electron application and **both Tool 1 and Tool 2 (Batch Recording Generator)** into the debugging tools suite, the converter can now connect directly to Blackmagic cameras over Ethernet or Wi-Fi to capture clips as they are shot and transcode them in real time.

---

## 2. Core Functional Additions

### Tool 1: Automated Video Clip Ingest (Main App & Debug Tools)
- **On/Off Activation with Baseline Isolation**:
  Upon activation, the system takes an atomic baseline snapshot of all existing clip IDs and file names on the camera storage. Only clips recorded **after** activation are automatically ingested, preventing unwanted historical syncs.
- **Hardware State Detection via REST API**:
  Continuously monitors `/control/api/v1/transports/0/record` for `recording: true -> false` state transitions. When recording finishes, waits 1.5s for the camera OS to finalize filesystem handles and refresh the `/clips` index.
- **Atomic FTP Ingest**:
  Transfers newly finalized `.braw` clips directly into `00_IN_INGEST` using temporary `.downloading` files with atomic rename and post-transfer byte verification.
- **Seamless Pipeline Handoff**:
  As soon as the file lands in `00_IN_INGEST`, the hot-folder engine moves it to `01_PROCESSING`, performs hardware-accelerated Apple Silicon Metal GPU 3D LUT grading and VideoToolbox HEVC encoding, delivers the final MP4 to `02_COMPLETED_MP4`, and archives the original BRAW to `03_ARCHIVE_BRAW`.
- **Retroactive Same-Day Import**:
  One-click button scans the camera for all clips recorded on the current calendar date and queues any missing ones for download.

### Tool 2: Batch Video Recording Generator (Debug Tools Suite)
- **Automated Stress Testing**:
  Generates calibrated series of camera recordings to feed the endurance test harness and benchmark pipeline stability.
- **1-Hour Debug Presets**:
  - `15 seconds` (240 clips ~ 1 hour)
  - `30 seconds` (120 clips ~ 1 hour)
  - `45 seconds` (80 clips ~ 1 hour)
  - `60 seconds` (60 clips ~ 1 hour)
  - Plus arbitrary custom clip counts and durations.
- **Camera Configuration over REST**:
  Dynamically queries camera supported resolutions and codecs (e.g. 6K Open Gate, 4K 16:9, BRaw 8:1, 5:1, 3:1, Q0, Q5) and sets the camera sensor format via `PUT /system/format`.
- **Full Sequence Controls**:
  Start, pause, resume, and stop controls with real-time countdown, batch progress visualizer, and calculation summary.

---

## 3. Network & Configuration Invariants

- **Default Camera IP**: `192.168.1.118` (User configurable via Settings modal or debug dashboard).
- **Default Camera FTP**: `ftp://PYXIS-6K.local` (User configurable via Settings modal or debug dashboard).
- **Zero Third-Party Dependencies**: All network operations use standard Python library modules (`urllib.request`, `ftplib`, `threading`, `json`).
- **Security & Sandboxing**: Electron renderer operates in full sandbox mode with `contextIsolation: true`, communicating via hardened IPC in `src/electron/preload/index.js`.
- **Unbuffered Execution**: Background Python processes are spawned with `-u` and stream line-delimited telemetry to the UI in real time.
