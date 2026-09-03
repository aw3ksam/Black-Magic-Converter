# Import Staging Directory (`import/`)

This directory is the staging and ingestion ground for importing external modules, libraries, reference scripts, and third-party projects into **Black Magic Converter** and its **Debug Tools**.

---

## 🎯 Purpose & Philosophy: *Functionality Over Files*

> **Key Rule**: The purpose of this folder is **NOT** simply to dump files into the project. The goal is to **integrate the functionality** of the requested program or module.

When you place a project or code snippet here and ask an AI agent to add it:
1. **Adaptive Integration**: The agent will read and understand the source code, then write or adapt only the necessary logic, classes, functions, or UI elements so they natively fit this codebase.
2. **Architecture Compliance**: Any code adapted into the main application or debug tools must respect our strict architectural rules (Electron Forge + Vite, context isolation, hardened preload bridge, zero-dependency ASAR, unbuffered Python streaming, and the 5 immutable watch folders).
3. **Clean Codebase**: Raw third-party repo clutter (e.g. extra docs, irrelevant configs, incompatible dependencies, test mockups) will **not** be blindly copied into `src/` or `debug_tools/`.

---

## 📂 How to Use This Directory

1. **Drop Your Source**:
   Create a subfolder inside `import/` for each project or module you want to incorporate:
   ```text
   import/
   ├── custom-transcoder/       # An external FFmpeg or transcoding script
   ├── ui-color-picker/         # A UI component or library
   ├── camera-metadata-tool/    # A helper script or CLI utility
   └── README.md
   ```

2. **Instruct the Agent**:
   Tell the AI agent what you want to achieve with the imported files. Examples:
   * *"I placed a ProRes encoder script in `import/custom-transcoder`. Please adapt its bitrate calculation logic into `src/ffmpeg_engine/transcoder.py`."*
   * *"Integrate the UI widgets from `import/ui-color-picker` into our Electron renderer settings panel."*
   * *"Take the stress-testing loop from `import/stress-test` and port it into `debug_tools/chaos/` as a new endurance test module."*

---

## 🤖 Instructions for AI Agents

When handling requests involving `import/`, refer to [AGENTS.md](AGENTS.md) in this directory and the root [AGENTS.md](../AGENTS.md). Always follow the **4-Phase Integration Lifecycle**:
1. **Analyze & Extract**: Read the imported source to identify the core algorithmic/functional logic.
2. **Adapt & Rewrite**: Re-implement or translate the code to match project standards and security invariants.
3. **Verify**: Ensure unit tests and packaging (`npm test`, `npm run package`) pass without regression.
4. **Preserve Integrity**: Do not commit foreign binaries, `.git` trees, or foreign `node_modules`.
