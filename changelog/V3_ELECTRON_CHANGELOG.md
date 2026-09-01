# BRAW Video Converter — Version 3 (Electron Forge) Architectural Changelog & Developer Specification

## 1. Overview & System Mission

**Version 3 (`versions/v3-electron/` & root codebase)** upgrades the BRAW Video Converter into a modern, cross-platform desktop application built with **Electron Forge** and **Vite**.

Version 3 supersedes Version 2's macOS-only Swift/SwiftUI architecture by providing complete cross-platform support across macOS (Apple Silicon & Intel), Windows, and Linux, while maintaining 100% feature parity with the DaVinci Resolve automated transcoding pipeline and 5-stage hot-folder staging model:

1. **Cross-Platform Electron Forge Build Matrix**: Native installer generation for macOS (`.dmg`, `.zip`), Windows (`.exe` Squirrel), and Linux (`.deb`, `.rpm`).
2. **Vite Fast Bundling & HMR**: Modular Vite pipeline configured with `@electron-forge/plugin-vite` to bundle Main, Preload, and Renderer environments with maximum speed and tree-shaking.
3. **Hardened Security Architecture**: Full context isolation (`contextIsolation: true`), disabled Node.js integration in renderer (`nodeIntegration: false`), and enabled sandboxing (`sandbox: true`) using a secure `contextBridge` contract (`window.electronAPI`).
4. **Dynamic Root Watch Folder Management & Safe Auto-Provisioning**: Support for arbitrary root folder locations with automatic provisioning of the 5 required pipeline subdirectories (`00_IN_INGEST`, `01_PROCESSING`, `02_COMPLETED_MP4`, `03_ARCHIVE_BRAW`, `99_FAILED`) without modifying existing archived assets.
5. **Interactive Watcher Controls & State Machine**: One-click Start/Stop toggle with visual service state indicators (`idle`, `starting`, `watching`, `transcoding`, `stopping`, `error`).
6. **Real-time Transcoding Telemetry**: Live progress percentage, active clip name badge, and FPS throughput meter extracted from unbuffered Python stdout streams.
7. **Live ANSI Console Stream**: Dark-mode terminal with ANSI color classification, auto-scrolling, clear buffer, and clipboard export.
8. **Dynamic LUT & Codec Configuration**: Modal for runtime configuration of Blackmagic Gen 5 LUTs, H.265 Main10 / ProRes codecs, audio streams, and stability debounce timers.

---

## 2. Directory Layout & Module Structure

```text
davinci-braw/
├── package.json                                       # Root NPM package manifest (scripts, devDependencies, Electron Forge)
├── forge.config.js                                    # Electron Forge configuration (PackagerConfig, Makers, Plugins, Fuses)
├── vite.main.config.mjs                               # Vite bundler configuration for Main Process
├── vite.preload.config.mjs                            # Vite bundler configuration for Preload Script
├── vite.renderer.config.mjs                            # Vite bundler configuration for Renderer UI
├── build/
│   ├── entitlements.mac.plist                        # macOS Hardened Runtime entitlements
│   └── entitlements.mac.inherit.plist                # macOS child process inherit entitlements
├── assets/
│   └── icons/
│       ├── icon.png                                  # 1024x1024 Master icon
│       ├── icon.icns                                 # macOS Icon bundle
│       └── icon.ico                                  # Windows Icon bundle
├── src/
│   ├── electron/
│   │   ├── main/
│   │   │   └── index.js                              # Main Process: Window lifecycle, IPC handlers, subprocess spawning
│   │   ├── preload/
│   │   │   └── index.js                              # Preload Script: Hardened contextBridge API exposure
│   │   └── renderer/
│   │       ├── index.html                            # Semantic HTML5 UI layout
│   │       ├── styles/
│   │       │   └── app.css                           # Workstation dark theme styles & animations
│   │       └── scripts/
│   │           └── app.js                            # UI state machine, event listeners & telemetry updates
│   ├── common/                                       # Shared Python config, logger & stability guards
│   ├── dvr_engine/                                   # DaVinci Resolve API client & render pipeline
│   └── cli.py                                        # Python CLI & watch daemon entry point
├── scripts/
│   ├── start_electron.sh                             # Development launcher script
│   ├── start_gui.sh                                  # V2 Swift GUI launcher
│   ├── start_watcher.sh                              # Background watcher launcher
│   └── run_headless_dvr.sh                           # Headless DaVinci Resolve launcher
├── changelog/
│   ├── README.md                                     # Changelog index
│   ├── V2_GUI_CHANGELOG.md                           # Version 2 Swift GUI specification
│   └── V3_ELECTRON_CHANGELOG.md                      # Version 3 Electron Forge specification
└── versions/
    ├── v1-davinci-dependent/                         # Version 1 CLI/Daemon headless engine
    ├── v2-gui/                                       # Version 2 Native macOS SwiftUI application
    └── v3-electron/                                  # Version 3 Documentation & package spec
```

---

## 3. Process Architecture & Security Data Flow

```mermaid
flowchart TD
    subgraph RENDERER_LAYER [Renderer Process (Sandboxed Browser Context)]
        UI[index.html + app.css]
        APP[app.js (Reactive UI State Controller)]
        UI --- APP
    end

    subgraph PRELOAD_LAYER [Preload Script (contextBridge Boundary)]
        CB["window.electronAPI (contextBridge.exposeInMainWorld)"]
    end

    subgraph MAIN_PROCESS [Main Process (Node.js & Electron Core)]
        MAIN[main/index.js]
        IPC_H[ipcMain.handle Dispatcher]
        DIR_MGR[Directory Provisioner & Counter]
        CFG_GEN[Dynamic YAML Config Generator]
        CHILD[Child Process Manager]
    end

    subgraph BACKEND_ENGINE [Python / DaVinci Resolve CLI]
        PY["python3 -u -m src.cli watch --config /tmp/braw_electron_config.yaml"]
        DVR[DaVinci Resolve Studio Headless Engine -nogui]
    end

    APP -->|Invoke IPC| CB
    CB -->|IPC Request| IPC_H
    IPC_H --> MAIN
    
    MAIN --> DIR_MGR
    MAIN --> CFG_GEN
    MAIN --> CHILD
    
    CHILD -->|Spawn Process (unbuffered)| PY
    PY -->|Automate Timelines & Renders| DVR
    
    PY -->|Stdout / Stderr Stream| CHILD
    CHILD -->|parseStreamLine & Regex| MAIN
    MAIN -->|webContents.send Events| PRELOAD_LAYER
    PRELOAD_LAYER -->|Event Callbacks (onLog, onProgress, onStatus)| APP
    APP -->|DOM Updates & Telemetry Meters| UI
```

---

## 4. Electron Forge Configuration Details

### 4.1 Packager Config (`packagerConfig`)
* `name`: `"Black Magic Converter"`
* `executableName`: `"BlackMagicConverter"`
* `appBundleId`: `"com.blackmagic.converter"`
* `appCategoryType`: `"public.app-category.video"`
* `icon`: `"./assets/icons/icon"` (auto-resolves `.icns` on macOS, `.ico` on Windows, `.png` on Linux)
* `asar`: `true`
* `osxSign`: Hardened runtime enabled with entitlements from `build/entitlements.mac.plist`.
* `osxNotarize`: Ready for Apple Notarization with `APPLE_ID`, `APPLE_PASSWORD`, and `APPLE_TEAM_ID` environment injection.

### 4.2 Makers Config (`makers`)
1. **`@electron-forge/maker-zip`**: Produces standard portable zips for macOS, Windows, and Linux.
2. **`@electron-forge/maker-dmg`**: Generates clean macOS DMG disk images with custom background and bundle styling.
3. **`@electron-forge/maker-squirrel`**: Generates Windows install packages (`.exe`) with auto-updater readiness.
4. **`@electron-forge/maker-deb` & `@electron-forge/maker-rpm`**: Produces native Linux distribution packages categorized under `AudioVideo` and `Video`.

### 4.3 Plugins Config (`plugins`)
1. **`@electron-forge/plugin-vite`**:
   - `main`: Configured via `vite.main.config.mjs` targeting `src/electron/main/index.js`.
   - `preload`: Configured via `vite.preload.config.mjs` targeting `src/electron/preload/index.js`.
   - `renderer`: Configured via `vite.renderer.config.mjs` targeting `src/electron/renderer/index.html`.
2. **`FusesPlugin`**: Disables `RunAsNode`, enables `EnableCookieEncryption`, disables `EnableNodeOptionsEnvironmentVariable`, and enforces `OnlyLoadAppFromAsar` for tamper-resistant production security.

---

## 5. IPC Contract Specification

| Channel | Type | Payload / Parameters | Return / Emitted Data | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `dialog:selectDirectory` | `handle` | None | `{ path: string, counts: object }` | Opens native directory picker dialog |
| `dialog:revealInFinder` | `handle` | `subfolder: string` | `boolean` | Opens directory in OS file manager |
| `engine:getInitialState` | `handle` | None | Initial state object | Returns initial settings, root path, folder counts |
| `engine:scanFolderCounts`| `handle` | None | `{ 00_IN_INGEST: n, ... }` | Scans current file counts across the 5 subfolders |
| `engine:saveConfig` | `handle` | `newConfig: object` | `updatedConfig: object` | Saves modified transcode presets |
| `engine:startWatcher` | `handle` | None | `{ success: boolean, message?: string }` | Provisions folders, generates YAML, spawns Python |
| `engine:stopWatcher` | `handle` | None | `{ success: boolean }` | Sends graceful `SIGINT` to Python watcher |
| `engine:log` | `send` | `logLine: string` | N/A | Broadcasts log line to Renderer console |
| `engine:status` | `send` | `{ state, currentClip, message }` | N/A | Broadcasts state transitions |
| `engine:progress` | `send` | `{ progress: number }` (0-100) | N/A | Updates transcode progress bar |
| `engine:speed` | `send` | `{ fps: number }` | N/A | Updates encoding throughput meter |
| `engine:folderCounts` | `send` | `{ 00_IN_INGEST: n, ... }` | N/A | Broadcasts refreshed stage file counts |

---

## 6. Critical Invariants for Developers & Future Agents

> [!IMPORTANT]
> **Preserve the Following Invariants:**
> 
> 1. **5 Subdirectory Names Must Remain Exact**:
>    `00_IN_INGEST`, `01_PROCESSING`, `02_COMPLETED_MP4`, `03_ARCHIVE_BRAW`, and `99_FAILED`.
> 2. **Never Remove `-u` Flag When Spawning Python**:
>    The `-u` flag prevents Python from block-buffering `stdout`. Without it, log streaming and transcode progress parsing will lag until the process finishes.
> 3. **Preserve Sandboxing & Context Isolation**:
>    Never enable `nodeIntegration: true` or disable `contextIsolation`. All OS-level operations must remain in the Main process behind `ipcMain.handle`.
> 4. **Graceful `SIGINT` Teardown**:
>    When stopping the background process, always issue `SIGINT` first so the Python client can invoke `resolve.Quit()` before issuing a `SIGTERM` fallback after 3 seconds.

---

## 7. Verification & Build Commands

### Run in Development
```bash
npm start
# Or using the launcher script:
./scripts/start_electron.sh
```

### Build Package Locally
```bash
npm run package
```

### Generate Production Distribution Makers
```bash
npm run make
```

### Run Backend Pytest Suite
```bash
pytest tests/
```
