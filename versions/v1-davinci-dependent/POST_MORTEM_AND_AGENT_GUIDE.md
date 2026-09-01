# BRAW Video Converter — Version 1 Post-Mortem & Agent Handover Guide

## 1. Executive Summary & Objective

**Version 1** is an automated, hot-folder-driven ingest and transcoding service built for macOS to convert Blackmagic RAW (`.braw`) camera media into **10-bit H.265 (HEVC)** in an **MP4** container with applied **Blackmagic Gen 5 built-in 3D LUTs**, while strictly preserving 1:1 input resolution (e.g. 6K $\to$ 6K, 4K $\to$ 4K, 1080p $\to$ 1080p) and frame rate.

Version 1 achieves immediate, high-fidelity production reliability by leveraging **DaVinci Resolve Studio’s headless scripting API (`-nogui`)** on Apple Silicon macOS.

---

## 2. System Architecture & Components

```text
davinci-braw/
├── config/
│   ├── config.default.yaml          # Template configuration
│   └── config.yaml                  # Active runtime configuration
├── src/
│   ├── common/
│   │   ├── config.py                # Type-safe dataclass config parser
│   │   ├── logger.py                # ANSI color console + rotating file loggers
│   │   └── watcher.py               # Hot folder observer with FileStabilityGuard
│   ├── dvr_engine/
│   │   ├── resolve_client.py        # DVR process lifecycle & headless bridge
│   │   ├── project_manager.py       # Dynamic 1:1 timeline & metadata extractor
│   │   └── render_pipeline.py       # LUT Node 1 injector & H.265 export engine
│   └── cli.py                       # Unified CLI (watch, transcode, list-luts, test-env)
├── scripts/
│   ├── run_headless_dvr.sh          # Standalone headless Resolve starter
│   └── start_watcher.sh             # Watcher launcher with environment exports
└── tests/
    ├── test_config_and_watcher.py   # State-machine & file lock unit tests
    └── test_dvr_mock.py             # Resolution & render settings mock tests
```

### Key Subsystems:
1. **File Stability Guard (`src/common/watcher.py`)**:
   - Camera card offloads can take minutes. To prevent transcoding incomplete files, `FileStabilityGuard` requires $N$ consecutive checks where `st_size` is identical AND attempts non-blocking POSIX locks (`fcntl.flock(LOCK_EX | LOCK_NB)`).
   - Manages state progression: `00_IN_INGEST` $\to$ `01_PROCESSING` $\to$ `02_COMPLETED_MP4` & `03_ARCHIVE_BRAW` (or `99_FAILED`).
2. **DaVinci Resolve Studio Process Manager (`src/dvr_engine/resolve_client.py`)**:
   - Dynamically injects macOS API paths:
     - `RESOLVE_SCRIPT_API="/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"`
     - `RESOLVE_SCRIPT_LIB="/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"`
   - Automatically launches headless Resolve (`Resolve -nogui`) if not already active and monitors connection until ready.
3. **Dynamic 1:1 Project & Timeline Manager (`src/dvr_engine/project_manager.py`)**:
   - Inspects `MediaPoolItem` properties to determine exact pixel dimensions (width/height), frame rate, duration, audio track counts, and camera model.
   - Configures the Project and Timeline to match the input clip 1:1.
4. **Render & LUT Pipeline (`src/dvr_engine/render_pipeline.py`)**:
   - Injects the Blackmagic 3D LUT into Node 1 via `timeline_item.SetLUT(1, lut_path)` (e.g. `Blackmagic Design/Blackmagic Gen 5 Film to Extended Video.cube`).
   - Configures render parameters for `mp4` container, `H265` codec, `Main10` profile, `aac` stereo audio.
   - Dispatches jobs and polls `GetRenderJobStatus(job_id)` until complete.

---

## 3. Chronology of Issues & Post-Mortem

During the development and live verification with real 6K footage (Blackmagic PYXIS 6K, 3.96 GB clip `A001_06201100_C073.braw` and 8.15 GB clip `A001_08071422_C269.braw`), we encountered three critical bugs. Here is what happened, why, and how they were solved:

### Issue 1: CLI `--config` Flag Rejection
* **Symptom**: Running `./scripts/start_watcher.sh` failed immediately with:
  ```text
  usage: cli.py [-h] [-c CONFIG] {watch,transcode,list-luts,test-env} ...
  cli.py: error: unrecognized arguments: --config config/config.yaml
  ```
* **Root Cause**: `argparse` was configured with `-c/--config` on the root parser only. When subcommands like `watch` were invoked, arguments specified after the subcommand were rejected.
* **Fix**: Created a parent parser (`config_parser = argparse.ArgumentParser(add_help=False)`) and passed `parents=[config_parser]` to all subparsers so `--config` can be positioned before or after any subcommand.

### Issue 2: DaVinci Resolve `SetRenderSettings` Validation Rejection
* **Symptom**: During live transcode of `A001_06201100_C073.braw`, Resolve reported:
  ```text
  [ERROR] braw_cli: Failed to configure render settings.
  [ERROR] braw_watcher: Transcode failed. Moving to: .../99_FAILED/...
  ```
* **Root Cause Investigation**: Isolated each parameter passed to `project.SetRenderSettings(dict)`:
  - `VideoQuality`: Was passed as the string `"Best"`. In Resolve's H.265 macOS encoder, `VideoQuality` strictly expects an integer (`0` for Automatic, or an integer bitrate in Kbps).
  - `FrameRate`: Was redundantly passed in `SetRenderSettings`. For MP4 H.265, Resolve enforces that the timeline frame rate defines the render frame rate; providing `FrameRate` in `SetRenderSettings` failed validation.
  - `ReplaceExistingFilesInPlace`: Unsupported key for this render mode.
* **Fix**:
  - Mapped `VideoQuality` to `0` (or integer bitrate if specified).
  - Removed unsupported and redundant keys.
  - Added a defensive fallback: if bulk dictionary assignment fails, keys are applied individually so core settings are never lost.

### Issue 3: Fairlight `SIGABRT` Crash Dialog on Watcher Shutdown
* **Symptom**: When stopping the watcher via `Ctrl+C`, macOS generated an application crash report for DaVinci Resolve (`EXC_CRASH (SIGABRT)` in `libFairlightPage.dylib` / `libggml-base.0.dylib` on Thread 93).
* **Root Cause**: Python's `resolve_client.close()` was immediately calling `subprocess.terminate()` (`SIGTERM`) while Resolve's Fairlight background audio engine threads were active. Abruptly killing the process caused Fairlight threads to trap `abort()`.
* **Fix**: Updated `resolve_client.close()` to issue `resolve.Quit()` through the scripting API first, allowing Resolve to shut down its audio threads cleanly before terminating the subprocess.

---

## 4. Live Verification Data (PYXIS 6K BRAW Footage)

Tested against live camera clips on Apple Silicon:

| File | Raw Dimensions | Output Dimensions | Codec | Render Time | Speed | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `A001_06201100_C073.braw` (3.96 GB) | **6048 $\times$ 4032** @ 29.97 fps | **6048 $\times$ 4032** | H.265 Main10 | 12.1s (540 frames) | ~45 fps | **Success** |
| `A001_08071422_C269.braw` (8.15 GB) | **6048 $\times$ 4032** @ 29.97 fps | **6048 $\times$ 4032** | H.265 Main10 | 26.2s (1170 frames) | ~45 fps | **Success** |

---

## 5. Agent Handover & Quick-Start Guide

For any developer or AI agent continuing this work:

1. **How to run tests**:
   ```bash
   python3 -m unittest discover tests
   ```
2. **How to run the watcher**:
   ```bash
   ./scripts/start_watcher.sh
   # Or: python3 -m src.cli watch --config config/config.yaml
   ```
3. **How to transcode manually**:
   ```bash
   python3 -m src.cli transcode "/path/to/clip.braw" --output-dir "/path/to/output"
   ```
4. **How to list installed LUTs**:
   ```bash
   python3 -m src.cli list-luts
   ```
5. **Key Invariants**:
   - The 5 hot folder subdirectories must maintain their exact names:
     `00_IN_INGEST`, `01_PROCESSING`, `02_COMPLETED_MP4`, `03_ARCHIVE_BRAW`, `99_FAILED`.
   - The root watch folder can be named anything and reside anywhere.
