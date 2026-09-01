# Black Magic Converter — Version 3 (Electron Forge Desktop Workstation)

## Overview

**Version 3 (`versions/v3-electron/` & project root)** is the modern cross-platform desktop workstation application built with **Electron** and **Electron Forge** (utilizing Vite for high-performance frontend bundling, process isolation, and hardened macOS runtime capabilities).

It provides complete feature parity with the Version 2 native SwiftUI interface while unlocking true multi-platform support across **macOS (Apple Silicon & Intel)**, **Windows 10/11**, and **Linux (Debian/RPM)**.

---

## Key Features

1. **Modern Electron Forge & Vite Pipeline**:
   - Bundled with `@electron-forge/plugin-vite` separating Main, Preload, and Renderer contexts.
   - Built-in multi-platform makers:
     - macOS: `MakerZIP`, `MakerDMG` (with hardened runtime entitlements).
     - Windows: `MakerSquirrel`.
     - Linux: `MakerDeb`, `MakerRpm`.
2. **Hardened Security Model**:
   - `contextIsolation: true`
   - `nodeIntegration: false`
   - `sandbox: true`
   - Strict `contextBridge` communication via `window.electronAPI`.
3. **5-Stage Pipeline Telemetry & Provisioning**:
   - Hot-folder inspector for `00_IN_INGEST`, `01_PROCESSING`, `02_COMPLETED_MP4`, `03_ARCHIVE_BRAW`, and `99_FAILED`.
   - Dynamic folder selection with automatic provisioning of missing stages without altering existing media.
4. **Real-Time Telemetry & Transcode Meter**:
   - Animated progress tracking with active clip label and real-time FPS encoding throughput.
5. **Interactive ANSI Console**:
   - Real-time unbuffered stream capturing all CLI and DaVinci Resolve engine logs with ANSI color parsing, auto-scroll, and one-click clipboard copying.
6. **Dynamic Preset Management**:
   - Real-time configuration of Blackmagic Gen 5 3D LUT transforms, H.265 / H.264 / ProRes codecs, Main10 bit-depth profiles, and folder debounce timers.

---

## Quick Start & Build Commands

### 1. Run in Development
```bash
npm start
# Or via script:
./scripts/start_electron.sh
```

### 2. Package App (Local Binary)
```bash
npm run package
```

### 3. Make Distributables (DMG, ZIP, Squirrel, Deb, RPM)
```bash
npm run make
```
