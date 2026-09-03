# Blackmagic Camera Tooling Suite - Architecture Specification

> **Target Audience:** AI Agents, Systems Engineers, and Python Developers integrating camera control, automated ingest, and batch capture capabilities into production or QA pipelines.

---

## 1. Executive Summary

The **Blackmagic Camera Tooling Suite** is a modular Python package and web-based control dashboard developed for automated Blackmagic camera workflows (specifically validated against the **Blackmagic PYXIS 6K**, firmware v10.2). 

It provides two distinct, interoperable operational engines:
1. **Tool 1 (Auto Video Clip Transfer):** Monitors camera recording transitions in real-time via the Blackmagic REST API. Once recording terminates, it automatically detects the newly created clip on disk and streams it over FTP to local storage, strictly ignoring all pre-existing clips on the camera media. Includes retroactive same-day import.
2. **Tool 2 (Batch Video Recording Generator):** Executes automated recording sequences for debug, stress, and test dataset generation. Supports fixed duration presets (15s, 30s, 45s, 60s) targeting ~1 hour of footage or user-specified custom clip counts and durations, with dynamic camera resolution and BRAW bitrate configuration.

---

## 2. System Architecture & Component Diagram

```
+--------------------------------------------------------------------------------------------------+
|                                    Blackmagic PYXIS 6K Camera                                    |
|                                                                                                  |
|   +---------------------------------------------+   +----------------------------------------+   |
|   |          REST API Control (HTTP:80)         |   |            FTP Server (TCP:21)         |   |
|   |  - /control/api/v1/system/product           |   |  - Root: /usb/{volume}/                |   |
|   |  - /control/api/v1/system/format            |   |  - Media directory: e.g. usb/A001/     |   |
|   |  - /control/api/v1/system/supportedFormats  |   |  - Unauthenticated / Anonymous access  |   |
|   |  - /control/api/v1/transports/0/record      |   |  - High-throughput binary file RETR    |   |
|   |  - /control/api/v1/clips                    |   +-------------------+--------------------+   |
|   |  - /control/api/v1/media/workingset         |                       |                        |
|   +----------------------+----------------------+                       |                        |
+--------------------------|----------------------------------------------|------------------------+
                           | HTTP REST                                    | Binary FTP
                           v                                              v
+--------------------------------------------------------------------------------------------------+
|                                      Python Tooling Core (bm_camera)                             |
|                                                                                                  |
|   +-------------------------------+   +-----------------------------+                            |
|   |         CameraClient          |   |          FtpClient          |                            |
|   | (urllib.request JSON wrapper) |   | (ftplib with stream metrics)|                            |
|   +---------------+---------------+   +--------------+--------------+                            |
|                   |                                  |                                           |
|                   +-----------------+----------------+                                           |
|                                     |                                                            |
|         +---------------------------v---------------------------+                                |
|         |                                                       |                                |
|   +-----v------------------------+                     +--------v----------------------+         |
|   |   Tool 1: AutoTransferTool   |                     |  Tool 2: BatchRecorderTool    |         |
|   | - Baseline snapshot baseline |                     | - State machine               |         |
|   | - REST status polling thread |                     | - Preset & custom calculator  |         |
|   | - File closure cooldown      |                     | - Format & codec applicator   |         |
|   | - FIFO transfer worker queue |                     | - Loop controller & cooldown  |         |
|   | - Same-day clip regex filter |                     | - Start / Pause / Abort       |         |
|   +--------------+---------------+                     +----------------+--------------+         |
|                  |                                                      |                        |
|                  +--------------------------+---------------------------+                        |
|                                             | Telemetry Events                                   |
|                                             v                                                    |
|                   +-----------------------------------------------------+                        |
|                   |                    ToolingEngine                    |                        |
|                   |  - Central event broadcaster                        |                        |
|                   |  - Unified system summary                           |                        |
|                   |  - Threaded HTTP Server (REST endpoints)            |                        |
|                   |  - Server-Sent Events (SSE) streaming engine        |                        |
|                   +-------------------------+---------------------------+                        |
+---------------------------------------------|----------------------------------------------------+
                                              | HTTP REST + SSE Stream (/api/events)
                                              v
+--------------------------------------------------------------------------------------------------+
|                                  Dashboard Web UI (dashboard/)                                   |
|                                                                                                  |
|    index.html                         style.css                         app.js                   |
|    - Clean semantic markup            - Dark cinema styling             - SSE Event listener     |
|    - Zero inline scripts              - Responsive 2-column grid        - Real-time DOM updater  |
|    - Real-time telemetry badges       - Glassmorphism panels            - REST action dispatcher |
+--------------------------------------------------------------------------------------------------+
```

---

## 3. Communication Protocols & Camera Interfaces

### 3.1 Blackmagic REST API (v1)
The camera exposes a REST API at `http://<camera_ip>/control/api/v1/`.

| Endpoint | Method | Payload / Params | Description |
| :--- | :--- | :--- | :--- |
| `/system/product` | `GET` | *None* | Returns `deviceName`, `productName`, `softwareVersion`. |
| `/system/supportedFormats` | `GET` | *None* | Returns array of supported formats (width, height, codecs, framerates). |
| `/system/format` | `GET` | *None* | Current format (active codec, resolution, framerate). |
| `/system/format` | `PUT` | `{"codec": str, "recordResolution": {...}, "frameRate": str}` | Configures active recording format on camera hardware. |
| `/transports/0/record` | `GET` | *None* | Returns `{"recording": bool}` indicating transport status. |
| `/transports/0/record` | `POST`| `{"clipName": str}` (optional) | Initiates camera recording. |
| `/transports/0/record` | `PUT` | `{"recording": false}` | Stops camera recording. |
| `/clips` | `GET` | *None* | Lists all clips on active disk (`clipUniqueId`, `filePath`, `fileSize`, etc.). |
| `/media/workingset` | `GET` | *None* | Disk info (`volume`, `remainingSpace`, `totalSpace`, `clipCount`). |

### 3.2 Camera FTP Server
- **Host:** `<camera_ip>` (e.g. `192.168.8.133`) or mDNS hostname `PYXIS-6K.local`.
- **Port:** `21` (Standard FTP).
- **Authentication:** Anonymous / empty credentials accepted by camera.
- **Directory Hierarchy:**
  - `/usb/`
    - `/{volume}/` (e.g., `A001/`)
      - `/{filename}.braw` or `/{filename}.mov`
      - `/Proxy/`
      - `/Stills/`
- **Throughput Profile:** Over gigabit local network, observed throughput ranges from **85 MB/s to 98 MB/s**.

---

## 4. Module Breakdown & Internal Mechanics

### 4.1 `bm_camera/camera_client.py`
Lightweight, thread-safe HTTP client wrapping Python's `urllib.request`.
- **Zero Third-Party Dependencies:** Does not require `requests` or `httpx`, avoiding version conflicts when imported into other environments.
- **Error Normalization:** Catches `urllib.error.HTTPError` and `urllib.error.URLError`, decoding JSON error payloads into explicit Python exceptions (`RuntimeError`, `ConnectionError`).

### 4.2 `bm_camera/ftp_client.py`
FTP file transfer client with progressive callback metrics.
- **`ProgressCallback` Class:** Intercepts byte chunks during `RETR` operations. Calculates:
  - Instantaneous throughput (`speed_mbps`)
  - Percent completion (`percent`)
  - Estimated Time to Arrival (`eta_seconds`)
- **Atomic Downloads:** Writes to `<filename>.braw.downloading` and atomically renames the file upon completion only after byte-size verification against the camera's `fileSize` metadata.

### 4.3 `bm_camera/tool_auto_transfer.py` (Tool 1)
Automated ingest pipeline operating via two dedicated background threads:
- **Baseline Snapshotting:**
  When `activate()` is invoked, queries `/clips` and indexes all existing `clipUniqueId` and `filePath` values into memory (`known_clip_ids`, `known_file_names`). Any files recorded before activation are ignored.
- **Monitor Thread (`_monitor_loop`):**
  Polls `/transports/0/record` at a configurable interval (default `0.5s`). Detects falling edge transition (`recording: True -> False`).
- **File Finalization Guard:**
  Upon detecting recording stop, sleeps for `1.5s` to allow the camera OS to flush buffers, finalize container headers, and update the `/clips` directory.
- **Transfer Worker Thread (`_worker_loop`):**
  Reads from a thread-safe `queue.Queue`. Executes downloads sequentially to avoid network interface contention. Emits progress events throughout the transfer.
- **Same-Day Import (`import_same_day_clips`):**
  Scans camera clips matching filename date stamp regex (`_(\d{4})\d{4}_` matching current `MMDD`, e.g., `_0902...._`) and queues any clips not currently present on local storage.

### 4.4 `bm_camera/tool_batch_recorder.py` (Tool 2)
State machine engine for batch debug recording:
- **Preset & Custom Calculator:**
  - Presets: 15s (240 clips), 30s (120 clips), 45s (80 clips), 60s (60 clips) targeting 3,600s (1 hour).
  - Custom: Accepts any `custom_clip_count` and `clip_duration`.
- **Execution Loop (`_batch_worker_loop`):**
  1. Sets camera format via `PUT /system/format` if requested.
  2. For clip `1` to `N`:
     - Triggers record via `POST /transports/0/record`.
     - Polls elapsed clip time until target duration reached.
     - Stops record via `PUT /transports/0/record` (`recording: False`).
     - Waits for a cooldown period (`2.5s`) to allow disk buffers to settle.
  3. Supports clean pause, resume, and abort controls.

### 4.5 `bm_camera/server.py`
Embedded web server serving the frontend dashboard and API endpoints:
- **Threaded Architecture:** Inherits from `socketserver.ThreadingMixIn` and `http.server.HTTPServer`.
- **Server-Sent Events (SSE):** Exposes `/api/events`. Maintains client queues in `sse_subscribers` and broadcasts tool telemetry, progress bars, and logs with zero client-side polling overhead.
- **Benign Disconnect Handling:** Overrides `handle_error` to suppress noisy `ConnectionResetError` [Errno 54] when browser tabs close.

### 4.6 `dashboard/` (Frontend Architecture)
- **Strict Separation of Concerns:**
  - `index.html`: Clean HTML5 semantic layout. Contains **no inline `<script>` tags** to comply with CSP and enterprise packaging rules.
  - `style.css`: Dark cinema UI theme (`#0b0e14` background, glassmorphism cards, glowing status pills, responsive layout).
  - `app.js`: Pure JavaScript event controller listening to the SSE stream and updating the DOM reactively.

---

## 5. API Data Contracts & Schemas

### 5.1 System Summary (`GET /api/status`)
```json
{
  "connected": true,
  "camera_ip": "192.168.8.133",
  "ftp_host": "192.168.8.133",
  "product": {
    "deviceName": "PYXIS 6K",
    "productName": "PYXIS 6K",
    "softwareVersion": "10.2"
  },
  "recording": false,
  "active_disk": {
    "volume": "A001",
    "deviceName": "usb512",
    "remainingSpace": 650712621056,
    "totalSpace": 2000394739712,
    "clipCount": 272
  },
  "tool1": {
    "active": true,
    "activation_time": "2026-09-02T11:41:52.000",
    "dest_dir": "/Users/studio/Downloads/PYXIS",
    "queue_size": 0,
    "active_transfer": null,
    "history": [],
    "total_files": 60,
    "total_bytes": 156020346420
  },
  "tool2": {
    "is_active": false,
    "state": "idle",
    "clip_duration": 60,
    "target_clips": 60,
    "current_clip_index": 60,
    "current_clip_elapsed": 0.0,
    "elapsed_total_seconds": 3600.0,
    "total_target_seconds": 3600,
    "percent": 100.0
  }
}
```

### 5.2 Tool 1 Toggle (`POST /api/tool1/toggle`)
**Request:**
```json
{
  "active": true,
  "import_today": false
}
```
**Response:**
```json
{
  "success": true,
  "active": true,
  "activation_time": "2026-09-02T11:41:52.000",
  "baseline_clips_ignored": 272
}
```

### 5.3 Tool 2 Start Batch (`POST /api/tool2/start`)
**Request:**
```json
{
  "clip_duration": 60,
  "custom_clip_count": 10,
  "codec": "BRaw:8_1",
  "record_resolution": { "width": 4096, "height": 2304 },
  "frame_rate": "29.97"
}
```

---

## 6. How Another Agent / Project Can Implement This

### Option A: Headless Integration (Python Library)
To integrate the camera tools directly into an existing Python program (without running the dashboard server):

```python
from pathlib import Path
from bm_camera import CameraClient, FtpClient, AutoTransferTool, BatchRecorderTool

# 1. Initialize Clients
camera = CameraClient(host="192.168.8.133")
ftp = FtpClient(host="192.168.8.133")

# 2. Setup Tool 1 (Auto Transfer)
def on_transfer_event(event):
    # event["type"] in ["tool1_transfer_progress", "tool1_transfer_completed", ...]
    print(f"Transfer Event: {event['type']} -> {event['data']}")

tool1 = AutoTransferTool(
    camera_client=camera,
    ftp_client=ftp,
    dest_dir=Path("./ingest"),
    on_event_cb=on_transfer_event
)

# Start auto-transfer (ignores old clips on camera)
tool1.activate()

# 3. Setup Tool 2 (Batch Recorder)
def on_batch_event(event):
    print(f"Batch Event: {event['type']} -> {event['data']}")

tool2 = BatchRecorderTool(
    camera_client=camera,
    on_event_cb=on_batch_event
)

# Run a custom batch: 5 clips of 30 seconds
tool2.start_batch(
    clip_duration=30,
    custom_clip_count=5,
    codec="BRaw:8_1",
    record_resolution={"width": 4096, "height": 2304}
)
```

### Option B: Embedding the Dashboard Server into an Application
If the target program needs to launch the web dashboard alongside its own services:

```python
from pathlib import Path
from bm_camera.server import start_server

server = start_server(
    host="0.0.0.0",
    port=8080,
    camera_ip="192.168.8.133",
    dest_dir="./transfers"
)

# Runs in background thread or standalone
# server.serve_forever()
```

### Option C: Adding to an Existing Web Framework (FastAPI / Flask)
The `CameraClient`, `FtpClient`, `AutoTransferTool`, and `BatchRecorderTool` instances can be injected into any dependency container:
- Route `POST /camera/record/start` -> `camera.start_record()`
- Route `POST /camera/record/stop` -> `camera.stop_record()`
- Route `GET /camera/clips` -> `camera.get_clips()`

---

## 7. Resource & Dependency Requirements

| Requirement | Specification | Notes |
| :--- | :--- | :--- |
| **Python Runtime** | Python 3.9+ | Tested & validated on Python 3.14 on macOS. |
| **Dependencies** | Standard Library Only | Uses `urllib.request`, `ftplib`, `http.server`, `threading`, `queue`, `json`. No external wheels required. |
| **Memory Footprint** | ~35 MB RSS | Streams file transfers in chunks (1MB blocksize); never buffers whole video files into RAM. |
| **Network Bandwidth** | 1 Gbps recommended | Video files range from 500 MB to 10 GB+; gigabit ethernet yields ~85–98 MB/s transfer speeds. |
| **Camera Network** | Subnet accessible | Camera must have static or DHCP IP on the same physical subnet or routed network. |
