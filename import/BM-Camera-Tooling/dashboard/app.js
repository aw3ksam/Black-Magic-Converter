/**
 * Blackmagic Camera Tooling Suite - Dashboard Application Controller
 * Handles real-time telemetry, tool state management, and user interactions.
 */

// State
let appState = {
  connected: false,
  product: {},
  recording: false,
  active_disk: {},
  tool1: { active: false, dest_dir: "./transfers", history: [] },
  tool2: {
    is_active: false,
    state: "idle",
    clip_duration: 60,
    target_clips: 60,
    current_clip_index: 0,
    current_clip_elapsed: 0,
    elapsed_total_seconds: 0,
  },
  supportedFormats: [],
  durationPresets: [],
};

// DOM Elements
const el = {
  cameraBadge: document.getElementById("camera-model-badge"),
  recIndicator: document.getElementById("rec-indicator"),
  recStatusText: document.getElementById("rec-status-text"),
  connBadge: document.getElementById("conn-badge"),
  connText: document.getElementById("conn-text"),
  diskName: document.getElementById("disk-name"),
  diskSpace: document.getElementById("disk-space"),
  diskProgress: document.getElementById("disk-progress"),

  // Tool 1
  tool1Toggle: document.getElementById("tool1-toggle"),
  tool1DestDir: document.getElementById("tool1-dest-dir"),
  btnSaveDest: document.getElementById("btn-save-dest"),
  btnImportToday: document.getElementById("btn-import-today"),
  activeTransferBox: document.getElementById("active-transfer-box"),
  activeFilename: document.getElementById("active-filename"),
  activeProgressBar: document.getElementById("active-progress-bar"),
  activeTransferred: document.getElementById("active-transferred"),
  activeSpeed: document.getElementById("active-speed"),
  activeEta: document.getElementById("active-eta"),
  tool1StatsCounter: document.getElementById("tool1-stats-counter"),
  transfersTbody: document.getElementById("transfers-tbody"),

  // Tool 2
  tool2StateBadge: document.getElementById("tool2-state-badge"),
  presetGrid: document.getElementById("duration-preset-grid"),
  tool2ClipCount: document.getElementById("tool2-clip-count"),
  tool2DurationInput: document.getElementById("tool2-duration-input"),
  batchTotalCalc: document.getElementById("batch-total-calc"),
  tool2ResolutionSelect: document.getElementById("tool2-resolution-select"),
  tool2CodecSelect: document.getElementById("tool2-codec-select"),
  btnStartBatch: document.getElementById("btn-start-batch"),
  btnPauseBatch: document.getElementById("btn-pause-batch"),
  btnStopBatch: document.getElementById("btn-stop-batch"),
  batchClipCounter: document.getElementById("batch-clip-counter"),
  batchTimeElapsed: document.getElementById("batch-time-elapsed"),
  batchTotalProgress: document.getElementById("batch-total-progress"),
  batchClipCountdown: document.getElementById("batch-clip-countdown"),
  batchClipProgress: document.getElementById("batch-clip-progress"),

  // Logs
  logsConsole: document.getElementById("logs-console"),
  btnClearLogs: document.getElementById("btn-clear-logs"),
};

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  initEventListeners();
  loadSupportedFormats();
  fetchInitialStatus();
  connectEventStream();
});

// Logs Helper
function addLog(message, type = "info") {
  const time = new Date().toLocaleTimeString();
  const div = document.createElement("div");
  div.className = `log-entry log-${type}`;
  div.textContent = `[${time}] ${message}`;
  el.logsConsole.appendChild(div);
  el.logsConsole.scrollTop = el.logsConsole.scrollHeight;
}

// Server Event Stream (SSE)
function connectEventStream() {
  const evtSource = new EventSource("/api/events");

  evtSource.onopen = () => {
    addLog("Connected to live camera telemetry stream", "succ");
  };

  evtSource.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      handleServerEvent(msg);
    } catch (err) {
      console.error("SSE parse error", err);
    }
  };

  evtSource.onerror = () => {
    el.connBadge.classList.add("disconnected");
    el.connText.textContent = "Reconnecting...";
  };
}

function handleServerEvent(event) {
  const { type, data } = event;

  if (type === "init") {
    updateSystemState(data);
  } else if (type === "tool1_status") {
    appState.tool1.active = data.active;
    el.tool1Toggle.checked = data.active;
    addLog(`Tool 1 (Auto Transfer) ${data.active ? "ACTIVATED" : "DEACTIVATED"}`, data.active ? "succ" : "warn");
  } else if (type === "camera_record_started") {
    appState.recording = true;
    updateRecIndicator(true);
    addLog("Camera started recording clip", "info");
  } else if (type === "camera_record_stopped") {
    appState.recording = false;
    updateRecIndicator(false);
    addLog("Camera stopped recording. Finalizing file...", "info");
  } else if (type === "tool1_transfer_progress") {
    updateActiveTransferUI(data);
  } else if (type === "tool1_transfer_completed") {
    addLog(`Transferred ${data.file_name} (${formatBytes(data.file_size)}) in ${data.duration_seconds}s @ ${data.speed_mbps} MB/s`, "succ");
    el.activeTransferBox.style.display = "none";
    fetchInitialStatus();
  } else if (type === "tool1_transfer_failed") {
    addLog(`Transfer FAILED for ${data.file_name}: ${data.error}`, "err");
    el.activeTransferBox.style.display = "none";
    fetchInitialStatus();
  } else if (type === "tool1_import_today") {
    addLog(`Import Today: Queued ${data.queued_count} clips for transfer`, "succ");
  } else if (type === "tool2_batch_started") {
    appState.tool2 = data;
    updateTool2UI();
    addLog(`Batch recording started: ${data.target_clips} clips x ${data.clip_duration}s`, "succ");
  } else if (type === "tool2_batch_progress") {
    appState.tool2 = data;
    updateTool2UI();
  } else if (type === "tool2_batch_paused") {
    appState.tool2 = data;
    updateTool2UI();
    addLog("Batch recording paused", "warn");
  } else if (type === "tool2_batch_resumed") {
    appState.tool2 = data;
    updateTool2UI();
    addLog("Batch recording resumed", "info");
  } else if (type === "tool2_batch_completed") {
    appState.tool2 = data;
    updateTool2UI();
    addLog("Batch recording successfully completed all clips!", "succ");
  } else if (type === "tool2_batch_stopped") {
    appState.tool2 = data;
    updateTool2UI();
    addLog("Batch recording stopped by user", "warn");
  } else if (type === "tool2_batch_error") {
    appState.tool2 = data;
    updateTool2UI();
    addLog(`Batch error: ${data.error_message}`, "err");
  }
}

// Fetch Initial Status
async function fetchInitialStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    updateSystemState(data);
  } catch (err) {
    console.error("Failed to fetch status", err);
  }
}

// Update Unified System State
function updateSystemState(data) {
  appState.connected = data.connected;
  appState.product = data.product || {};
  appState.recording = data.recording || false;
  appState.active_disk = data.active_disk || {};
  appState.tool1 = data.tool1 || appState.tool1;
  appState.tool2 = data.tool2 || appState.tool2;

  // Connection Badge
  if (data.connected) {
    el.connBadge.classList.remove("disconnected");
    el.connText.textContent = `${data.camera_ip} (Online)`;
    const prod = data.product;
    el.cameraBadge.textContent = `${prod.productName || "PYXIS 6K"} (v${prod.softwareVersion || "10.2"})`;
  } else {
    el.connBadge.classList.add("disconnected");
    el.connText.textContent = "Camera Disconnected";
    el.cameraBadge.textContent = "Offline - Check IP connection";
  }

  // Recording State
  updateRecIndicator(appState.recording);

  // Storage Info
  const disk = appState.active_disk;
  if (disk && disk.volume) {
    const totalGB = (disk.totalSpace / (1024 ** 3)).toFixed(1);
    const freeGB = (disk.remainingSpace / (1024 ** 3)).toFixed(1);
    const usedPct = disk.totalSpace > 0 ? (((disk.totalSpace - disk.remainingSpace) / disk.totalSpace) * 100).toFixed(0) : 0;
    el.diskName.textContent = `Disk: ${disk.volume} (${disk.clipCount || 0} clips)`;
    el.diskSpace.textContent = `${freeGB} GB Free / ${totalGB} GB`;
    el.diskProgress.style.width = `${usedPct}%`;
  } else {
    el.diskName.textContent = "No Storage Disk";
    el.diskSpace.textContent = "--";
    el.diskProgress.style.width = "0%";
  }

  // Tool 1 UI
  el.tool1Toggle.checked = appState.tool1.active;
  if (appState.tool1.dest_dir) {
    el.tool1DestDir.value = appState.tool1.dest_dir;
  }
  el.tool1StatsCounter.textContent = `${appState.tool1.total_files || 0} transferred (${formatBytes(appState.tool1.total_bytes || 0)})`;

  if (appState.tool1.active_transfer) {
    updateActiveTransferUI(appState.tool1.active_transfer);
  } else {
    el.activeTransferBox.style.display = "none";
  }

  renderTransfersTable(appState.tool1.history || []);

  // Tool 2 UI
  updateTool2UI();
}

function updateRecIndicator(isRecording) {
  if (isRecording) {
    el.recIndicator.classList.add("recording");
    el.recStatusText.textContent = "REC";
  } else {
    el.recIndicator.classList.remove("recording");
    el.recStatusText.textContent = "STANDBY";
  }
}

function updateActiveTransferUI(data) {
  el.activeTransferBox.style.display = "flex";
  el.activeFilename.textContent = data.file_name;
  el.activeProgressBar.style.width = `${data.percent || 0}%`;
  el.activeTransferred.textContent = `${formatBytes(data.transferred_bytes || 0)} / ${formatBytes(data.total_bytes || 0)} (${data.percent || 0}%)`;
  el.activeSpeed.textContent = `${data.speed_mbps || 0} MB/s`;
  el.activeEta.textContent = data.eta_seconds > 0 ? `ETA: ${data.eta_seconds}s` : "Finalizing...";
}

function renderTransfersTable(history) {
  if (!history || history.length === 0) {
    el.transfersTbody.innerHTML = `
      <tr class="empty-row">
        <td colspan="5">No files transferred yet. Activate Tool 1 to begin.</td>
      </tr>`;
    return;
  }

  el.transfersTbody.innerHTML = history.map((item) => {
    const isSuccess = item.status === "completed";
    const statusBadge = isSuccess
      ? `<span class="status-tag tag-success">Completed</span>`
      : `<span class="status-tag tag-failed">Failed</span>`;
    const time = item.completed_at ? new Date(item.completed_at).toLocaleTimeString() : "--";
    const speed = item.speed_mbps ? `${item.speed_mbps} MB/s` : "--";

    return `
      <tr>
        <td title="${item.file_name}">${item.file_name}</td>
        <td>${formatBytes(item.file_size || 0)}</td>
        <td>${speed}</td>
        <td>${statusBadge}</td>
        <td>${time}</td>
      </tr>
    `;
  }).join("");
}

// Tool 2 UI Update
function updateTool2UI() {
  const t2 = appState.tool2;
  const state = t2.state || "idle";

  // State Badge
  el.tool2StateBadge.className = `batch-status-badge badge-${state}`;
  el.tool2StateBadge.textContent = state.toUpperCase();

  // Progress calculations
  const totalClips = t2.target_clips || 60;
  const currentClip = t2.current_clip_index || 0;
  const clipDuration = t2.clip_duration || 60;
  const clipElapsed = t2.current_clip_elapsed || 0;
  const totalElapsed = t2.elapsed_total_seconds || 0;
  const totalTargetSec = totalClips * clipDuration;

  el.batchClipCounter.textContent = `Clip ${currentClip} / ${totalClips}`;
  el.batchTimeElapsed.textContent = `${formatSeconds(totalElapsed)} / ${formatSeconds(totalTargetSec)}`;

  const totalPct = totalClips > 0 ? ((currentClip / totalClips) * 100).toFixed(1) : 0;
  el.batchTotalProgress.style.width = `${totalPct}%`;

  const clipPct = clipDuration > 0 ? ((clipElapsed / clipDuration) * 100).toFixed(1) : 0;
  el.batchClipProgress.style.width = `${clipPct}%`;
  el.batchClipCountdown.textContent = `${clipElapsed.toFixed(1)}s / ${clipDuration}s`;

  // Button States
  const isRunning = t2.is_active && (state === "recording" || state === "cooldown" || state === "starting");
  const isPaused = t2.is_active && state === "paused";

  el.btnStartBatch.disabled = isRunning || isPaused;
  el.btnPauseBatch.disabled = !isRunning;
  el.btnPauseBatch.innerHTML = isPaused ? `<span class="btn-icon">▶</span> Resume` : `<span class="btn-icon">⏸</span> Pause`;
  el.btnStopBatch.disabled = !t2.is_active;
}

// Load Camera Formats for Tool 2
async function loadSupportedFormats() {
  try {
    const res = await fetch("/api/formats");
    const data = await res.json();
    if (data.success) {
      appState.supportedFormats = data.resolutions || [];
      appState.durationPresets = data.duration_presets || [];

      // Populate Resolutions
      el.tool2ResolutionSelect.innerHTML = appState.supportedFormats.map((r, i) => {
        return `<option value="${i}">${r.label}</option>`;
      }).join("");

      // Populate Codecs for initial resolution
      updateCodecDropdown(0);

      // Match current format if available
      if (data.current_format) {
        const curRes = data.current_format.recordResolution;
        if (curRes) {
          const matchIdx = appState.supportedFormats.findIndex(
            (f) => f.width === curRes.width && f.height === curRes.height
          );
          if (matchIdx >= 0) {
            el.tool2ResolutionSelect.value = matchIdx;
            updateCodecDropdown(matchIdx);
          }
        }
        if (data.current_format.codec) {
          el.tool2CodecSelect.value = data.current_format.codec;
        }
      }
    }
  } catch (err) {
    console.error("Failed to load formats", err);
  }
}

function updateCodecDropdown(resolutionIndex) {
  const selected = appState.supportedFormats[resolutionIndex];
  if (!selected) return;

  el.tool2CodecSelect.innerHTML = selected.codecs.map((c) => {
    return `<option value="${c}">${c.replace("BRaw:", "Blackmagic RAW ")}</option>`;
  }).join("");
}

// Event Listeners
function initEventListeners() {
  // Tool 1 Toggle
  el.tool1Toggle.addEventListener("change", async (e) => {
    const active = e.target.checked;
    try {
      const res = await fetch("/api/tool1/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active }),
      });
      const data = await res.json();
      if (!data.success) {
        e.target.checked = !active;
        addLog(`Failed to toggle Tool 1: ${data.message || data.error}`, "err");
      }
    } catch (err) {
      e.target.checked = !active;
      addLog(`Tool 1 toggle network error: ${err}`, "err");
    }
  });

  // Save Destination Directory
  el.btnSaveDest.addEventListener("click", async () => {
    const dest = el.tool1DestDir.value.trim();
    if (!dest) return;
    try {
      const res = await fetch("/api/tool1/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dest_dir: dest }),
      });
      const data = await res.json();
      if (data.success) {
        addLog(`Destination directory updated: ${data.dest_dir}`, "succ");
      }
    } catch (err) {
      addLog(`Failed to save destination: ${err}`, "err");
    }
  });

  // Import Today's Clips
  el.btnImportToday.addEventListener("click", async () => {
    try {
      el.btnImportToday.disabled = true;
      el.btnImportToday.textContent = "Scanning...";
      const res = await fetch("/api/tool1/import-today", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        addLog(`Import Today complete: ${data.queued_count} clips queued for download.`, "succ");
      } else {
        addLog(`Import Today error: ${data.error}`, "err");
      }
    } catch (err) {
      addLog(`Import Today error: ${err}`, "err");
    } finally {
      el.btnImportToday.disabled = false;
      el.btnImportToday.innerHTML = `<span class="btn-icon">⚡</span> Import Today's Clips`;
    }
  });

  // Tool 2 Preset Selection
  el.presetGrid.addEventListener("click", (e) => {
    const btn = e.target.closest(".preset-btn");
    if (!btn) return;
    document.querySelectorAll(".preset-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const duration = parseInt(btn.dataset.duration, 10);
    const clips = parseInt(btn.dataset.clips, 10);
    el.tool2DurationInput.value = duration;
    el.tool2ClipCount.value = clips;
    updateBatchCalculation();
  });

  // Tool 2 Custom Clip Count Change
  el.tool2ClipCount.addEventListener("input", () => {
    updateBatchCalculation();
  });

  // Tool 2 Duration Input Change
  el.tool2DurationInput.addEventListener("input", () => {
    updateBatchCalculation();
  });

  // Tool 2 Resolution Change
  el.tool2ResolutionSelect.addEventListener("change", (e) => {
    updateCodecDropdown(parseInt(e.target.value, 10));
  });

  // Tool 2 Start Batch
  el.btnStartBatch.addEventListener("click", async () => {
    const resIdx = parseInt(el.tool2ResolutionSelect.value, 10);
    const selectedRes = appState.supportedFormats[resIdx];
    const selectedCodec = el.tool2CodecSelect.value;
    const duration = parseInt(el.tool2DurationInput.value, 10) || appState.tool2.clip_duration || 60;
    const clips = parseInt(el.tool2ClipCount.value, 10) || appState.tool2.target_clips || 60;

    const payload = {
      clip_duration: duration,
      custom_clip_count: clips,
      codec: selectedCodec,
      record_resolution: selectedRes ? { width: selectedRes.width, height: selectedRes.height } : null,
      frame_rate: selectedRes && selectedRes.frameRates.length ? selectedRes.frameRates[0] : null,
    };

    try {
      const res = await fetch("/api/tool2/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!data.success) {
        addLog(`Failed to start batch: ${data.error}`, "err");
      }
    } catch (err) {
      addLog(`Error starting batch: ${err}`, "err");
    }
  });

  // Tool 2 Pause / Resume
  el.btnPauseBatch.addEventListener("click", async () => {
    const isPaused = appState.tool2.state === "paused";
    const endpoint = isPaused ? "/api/tool2/resume" : "/api/tool2/pause";
    try {
      await fetch(endpoint, { method: "POST" });
    } catch (err) {
      addLog(`Error pausing/resuming batch: ${err}`, "err");
    }
  });

  // Tool 2 Stop Batch
  el.btnStopBatch.addEventListener("click", async () => {
    try {
      await fetch("/api/tool2/stop", { method: "POST" });
    } catch (err) {
      addLog(`Error stopping batch: ${err}`, "err");
    }
  });

  // Clear Logs
  el.btnClearLogs.addEventListener("click", () => {
    el.logsConsole.innerHTML = "";
  });
}

function updateBatchCalculation() {
  const clips = parseInt(el.tool2ClipCount?.value, 10) || 1;
  const duration = parseInt(el.tool2DurationInput?.value, 10) || 1;
  appState.tool2.target_clips = clips;
  appState.tool2.clip_duration = duration;

  const totalSec = clips * duration;
  const totalHrs = (totalSec / 3600).toFixed(1);

  if (el.batchTotalCalc) {
    el.batchTotalCalc.textContent = `Total: ${clips} clips x ${duration}s = ${formatSeconds(totalSec)} (${totalHrs}h)`;
  }
  updateTool2UI();
}

// Helpers
function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

function formatSeconds(sec) {
  const total = Math.floor(sec);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
