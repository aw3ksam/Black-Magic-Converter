# Blackmagic Camera Tooling Suite (PYXIS 6K)

Modular Python toolkit and single-screen web dashboard for Blackmagic cameras.

## Features

- **Tool 1: Auto Video Clip Transfer**
  - **On/Off Activation Switch**: Snapshots existing storage to ignore pre-existing clips and only auto-transfers files recorded while active.
  - **REST API State Tracking**: Monitors recording state (`recording: true -> false`), verifies file closure, and begins download.
  - **FTP Transfer Engine**: Downloads `.braw` / `.mov` files directly from `ftp://PYXIS-6K.local` (or `192.168.8.133`), displaying speed (MB/s), ETA, and verifying file sizes.
  - **Same-Day Import**: One-click retroactive import for all clips recorded on the current date in case activation was delayed.
- **Tool 2: Batch Video Recording Generator**
  - **Debug Batch Runner**: Generates series of clips for program debugging with presets for 15s (240 clips), 30s (120 clips), 45s (80 clips), or 60s (60 clips) totaling ~1 hour of footage, or **any custom target clip count & duration**.
  - **Resolution & Codec Controller**: Dynamically fetches and applies camera formats (e.g., 6K Open Gate, 6K DCI, 4K 16:9, 1080p HD, and BRaw Q0–Q5 / 3:1–12:1).
  - **Live Progress Visualizer & Real-Time Calculation**: Displays batch clip counter, per-clip recording countdown timer, elapsed total time, and live calculation badge (`Total: X clips x Ys = Zm (H.Hh)`).
- **Modern Dashboard UI**:
  - Semantic HTML5 structure with zero inline scripts.
  - Dark cinema aesthetics with glassmorphism, live status indicators, and Server-Sent Events (SSE) telemetry.

---

## Directory Structure

```
BM-Camera-Tooling/
├── bm_camera/                      # Core Python Package (Ready for embedding)
│   ├── __init__.py                 # Package exports (CameraClient, FtpClient, Tools)
│   ├── camera_client.py            # Blackmagic REST API Client
│   ├── ftp_client.py               # Robust FTP client with progress callbacks
│   ├── tool_auto_transfer.py       # Tool 1: Auto Transfer logic
│   ├── tool_batch_recorder.py      # Tool 2: Batch Recorder logic
│   └── server.py                   # Embedded HTTP & SSE server
├── dashboard/                      # Web Dashboard Frontend
│   ├── index.html                  # Semantic HTML (No inline scripts)
│   ├── style.css                   # Dark theme styling
│   └── app.js                      # UI controller & event stream client
├── Documents/                      # Blackmagic REST API Reference & Demo
│   ├── RESTAPIforBlackmagicCameras.md
│   └── RESTControlDemo.html
├── run.py                          # CLI runner
├── ARCHITECTURE.md                 # Full system architecture & integration guide
└── README.md
```

> **For AI Agents & Developers:** See [ARCHITECTURE.md](file:///Users/studio/Documents/Sandbox/BM-Camera-Tooling/ARCHITECTURE.md) for full protocol specs, internal mechanics, data schemas, and copy-paste integration examples.

---

## Quick Start (Standalone Dashboard)

Run the server on default port `8080`:

```bash
python3 run.py --camera-ip 192.168.8.133 --port 8080
```

Open your browser to:
```
http://localhost:8080
```

---

## Integrating into Another Python Application

All tools and clients are modular and can be imported directly into any Python program:

```python
from bm_camera import CameraClient, FtpClient, AutoTransferTool, BatchRecorderTool

# 1. Initialize Clients
camera = CameraClient(host="192.168.8.133")
ftp = FtpClient(host="192.168.8.133")

# 2. Tool 1: Auto Transfer
tool1 = AutoTransferTool(
    camera_client=camera,
    ftp_client=ftp,
    dest_dir="/Users/studio/Downloads/PYXIS",
    on_event_cb=lambda evt: print("Tool 1 Event:", evt),
)
# Activate (ignores pre-existing clips)
tool1.activate()

# Import same-day clips retroactively
tool1.import_same_day_clips()

# Deactivate
# tool1.deactivate()

# 3. Tool 2: Batch Recording Generator
tool2 = BatchRecorderTool(
    camera_client=camera,
    on_event_cb=lambda evt: print("Tool 2 Event:", evt),
)

# Start 1-hour debug batch (60 clips x 60 seconds in 4K 16:9 BRaw 8:1)
tool2.start_batch(
    clip_duration=60,
    custom_clip_count=60,
    codec="BRaw:8_1",
    record_resolution={"width": 4096, "height": 2304},
    frame_rate="29.97",
)
```
