# Agent Protocol for Imported Code & Modules (`import/`)

This guide specifies mandatory procedures and architectural constraints for any AI agent tasked with integrating external code, modules, or third-party projects staged inside the `import/` directory.

---

## ⚡ Golden Rule: *Functionality Over Raw Files*

> **CRITICAL DIRECTIVE**: The user will place modules, scripts, or entire repositories into `import/`. Your objective is **NOT** to blindly copy or symlink files into `src/` or `debug_tools/`.
> 
> Your objective is to **extract, adapt, and integrate the requested FUNCTIONALITY** into the existing codebase architecture. You may rewrite any file, translate logic between languages/frameworks, or copy only the minimal essential code required to make the feature work natively.

---

## 🔄 The 4-Phase Integration Lifecycle

Whenever the user asks to "import", "add", or "integrate" code from `import/`, execute the following phases in sequence:

### Phase 1: Discovery & Functional Assessment
1. **Locate & Inspect**:
   - Explore the target subdirectory under `import/<module_or_project>/`.
   - Read manifests (`package.json`, `requirements.txt`, `setup.py`, `Cargo.toml`, etc.) to identify dependencies and assumptions.
   - Trace the entry point and core logic providing the feature requested by the user.
2. **Scope the Extraction**:
   - Distinguish between **core functional logic** (algorithms, codecs, UI components, parsers) and **external scaffolding** (boilerplate, build systems, example apps, demo assets).
   - Identify which dependencies are strictly necessary vs. which can be replaced with existing repository libraries (e.g. Python standard library, existing FFmpeg wrappers, or Electron native APIs).

### Phase 2: Architectural Alignment & Adaptation
Determine which subsystem the functionality belongs to and adapt the code to adhere to that subsystem's specific invariants:

| Target Subsystem | Destination Directory | Architecture Invariants & Rules |
| :--- | :--- | :--- |
| **Electron Renderer (UI)** | `src/electron/renderer/` | • Strict Context Isolation: `nodeIntegration: false`, `sandbox: true`<br>• **NEVER** import `fs`, `path`, or `child_process` in renderer<br>• All system operations must be exposed via `src/electron/preload/index.js`<br>• Use Vanilla CSS/JS; match modern dark-mode aesthetic |
| **Electron Main Process** | `src/electron/main/` | • Externalize Node built-ins; keep main process dependencies zero-external (inline YAML)<br>• Always spawn Python with unbuffered `-u` flag<br>• Graceful teardown: `SIGINT` first, with 3s fallback before `SIGTERM` |
| **Transcoding Engine** | `src/ffmpeg_engine/`, `src/native/`, `src/common/` | • Zero DaVinci Resolve dependency (standalone BRAW SDK + FFmpeg)<br>• Preserve 5 immutable watch folders: `00_IN_INGEST`, `01_PROCESSING`, `02_COMPLETED_MP4`, `03_ARCHIVE_BRAW`, `99_FAILED` |
| **Debug & Test Tools** | `debug_tools/` | • Integrate into supervisor (`supervisor/`), harness (`harness/`), telemetry (`telemetry/`), chaos (`chaos/`), or web dashboard (`dashboard.html` / `serve_dashboard.py`)<br>• Maintain compatibility with `run_endurance.py` |
| **CLI / Automation** | `src/cli.py`, `scripts/` | • Clean argument parsing with structured logging<br>• Support both interactive and non-interactive daemon modes |

### Phase 3: Implementation & Clean Integration
1. **Adapt Code**: Write the adapted code directly into the appropriate destination (`src/` or `debug_tools/`). Re-structure functions, harmonize variable naming, and attach logger instances matching repository conventions.
2. **Dependency Management**:
   - If Python dependencies are genuinely required: check if already in `requirements.txt` or `debug_tools/requirements.txt`. Add only if minimal and compatible.
   - If Node dependencies are required: verify with Electron Forge packaging compatibility before adding to `package.json`.
3. **Tests**: Add unit or integration tests under `tests/` or `debug_tools/tests/` to validate the newly integrated feature.

### Phase 4: Verification & Repository Hygiene
1. **Run Verification Checklist**:
   ```bash
   # Run project tests
   npm test

   # Verify packaging succeeds with new code in place
   npm run package
   ```
2. **Hygiene**:
   - Do **NOT** move foreign `.git`, `.gitignore`, `node_modules`, or virtual environments from `import/` into project root or `src/`.
   - Leave the reference files in `import/` untouched unless the user asks to remove or clean them up.
   - Document any new configuration parameters in `config/config.yaml` or relevant module READMEs.

---

## 🚫 Common Anti-Patterns to Strictly Avoid

* ❌ **Blind Copying**: Copying an entire foreign directory tree into `src/` without adapting paths, imports, and configuration.
* ❌ **Security Violations**: Introducing direct Node.js API calls (`require('fs')`, etc.) into UI files in `src/electron/renderer/`.
* ❌ **Dependency Bloat**: Blindly running `npm install <huge-library>` when 20 lines of native JS can achieve the same function.
* ❌ **Pipeline Drift**: Modifying the 5 immutable watch folder names or bypassing unbuffered Python execution (`-u`).
* ❌ **Abandoning Packaging**: Forgetting to test `npm run package` to ensure the new code bundles cleanly in production Electron ASAR.
