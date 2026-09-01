# BRAW Video Converter — Version 1 (DaVinci Resolve Dependent)

Automated hot-folder ingest and video transcoding service for Blackmagic RAW footage using DaVinci Resolve Studio Headless Engine (`-nogui`) on macOS.

## Key Features
- **Hot-Folder File Ingest State Machine**: `00_IN_INGEST` $\to$ `01_PROCESSING` $\to$ `02_COMPLETED_MP4` & `03_ARCHIVE_BRAW`.
- **File Stability Guard**: Prevents partial transcode runs during camera card file transfers with consecutive size stability checks and POSIX file locks.
- **1:1 Resolution Matching**: Preserves source clip dimensions dynamically (e.g. 6K $\to$ 6K, 4K $\to$ 4K, 1080p $\to$ 1080p).
- **Blackmagic Gen 5 Built-in 3D LUT**: Automatically applied to Node 1.
- **H.265 (HEVC) Main10**: 10-bit hardware accelerated video export with synchronized stereo AAC audio.
- **Graceful Headless Control**: Manages headless background Resolve instances with clean shutdown.

## How to Run

### Start Watcher
```bash
./scripts/start_watcher.sh
```

### Manual CLI Transcode
```bash
python3 -m src.cli transcode /path/to/clip.braw --output-dir ./watch_folders/02_COMPLETED_MP4
```

### List Installed Blackmagic LUTs
```bash
python3 -m src.cli list-luts
```
