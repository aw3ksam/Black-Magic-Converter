# Project Changelogs & Architectural Documentation

This directory contains changelogs, post-mortems, and developer specifications for all versions of the BRAW Video Converter project:

| Document | Scope & Key Changes |
| :--- | :--- |
| [`V4_CAMERA_INGEST_CHANGELOG.md`](./V4_CAMERA_INGEST_CHANGELOG.md) | **Version 4.0**: Blackmagic Camera Tooling (PYXIS 6K) integration, Tool 1 Auto Ingest into `00_IN_INGEST`, and Tool 2 Batch Recording Generator. |
| [`V3_2_NATIVE_VIDEOTOOLBOX_CHANGELOG.md`](./V3_2_NATIVE_VIDEOTOOLBOX_CHANGELOG.md) | **Version 3.2**: Zero-Copy Metal GPU 3D LUT Compute Shader & In-Process VideoToolbox HEVC Engine (5.7x speedup, eliminating CPU LUT bottlenecks). |
| [`V3_1_FFMPEG_CHANGELOG.md`](./V3_1_FFMPEG_CHANGELOG.md) | **Version 3.1**: Decoupled standalone transcoding engine using Blackmagic RAW SDK + FFmpeg pipeline. |
| [`V3_ELECTRON_CHANGELOG.md`](./V3_ELECTRON_CHANGELOG.md) | **Version 3.0**: Electron Forge + Vite desktop application and UI architecture overhaul. |

* 🤖 **[`../AGENTS.md`](../AGENTS.md)**: Developer & AI Agent Guide covering Electron Forge standards, security invariants, build commands, and pipeline rules.
* 📄 **[`V2_GUI_CHANGELOG.md`](./V2_GUI_CHANGELOG.md)**: Complete architectural changelog, inner workings, data flow diagrams, Swift 6 concurrency specifications, UI design hierarchy, and critical invariants for the **Version 2 macOS Native Swift/SwiftUI GUI Application (`versions/v2-gui/`)**.
* 📄 **[`../versions/v1-davinci-dependent/POST_MORTEM_AND_AGENT_GUIDE.md`](../versions/v1-davinci-dependent/POST_MORTEM_AND_AGENT_GUIDE.md)**: Complete post-mortem, issue analysis, and developer guide for the **Version 1 DaVinci Resolve CLI Engine (`versions/v1-davinci-dependent/`)**.
