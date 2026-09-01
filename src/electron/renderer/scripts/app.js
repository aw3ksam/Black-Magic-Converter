// Black Magic Converter - Renderer Application Logic

document.addEventListener('DOMContentLoaded', async () => {
  const electron = window.electronAPI;

  if (!electron) {
    console.error('Electron API not available on window.electronAPI');
    return;
  }

  // UI Element Selectors
  const rootPathEl = document.getElementById('display-root-path');
  const btnSelectRoot = document.getElementById('btn-select-root');
  const servicePill = document.getElementById('service-status-pill');
  const serviceStatusText = document.getElementById('service-status-text');
  const btnToggleService = document.getElementById('btn-toggle-service');
  const btnToggleLabel = document.getElementById('btn-toggle-label');
  const playIcon = btnToggleService.querySelector('.play-icon');
  const stopIcon = btnToggleService.querySelector('.stop-icon');

  const progressContainer = document.getElementById('progress-container');
  const currentClipLabel = document.getElementById('current-clip-name');
  const telemetryFps = document.getElementById('telemetry-fps');
  const telemetryPercent = document.getElementById('telemetry-percent');
  const progressFill = document.getElementById('progress-bar-fill');

  const terminalStream = document.getElementById('terminal-stream');
  const chkAutoScroll = document.getElementById('chk-autoscroll');
  const btnCopyLogs = document.getElementById('btn-copy-logs');
  const btnClearLogs = document.getElementById('btn-clear-logs');

  // Modal Selectors
  const btnOpenSettings = document.getElementById('btn-open-settings');
  const modalSettings = document.getElementById('modal-settings');
  const btnCloseSettings = document.getElementById('btn-close-settings');
  const btnCancelSettings = document.getElementById('btn-cancel-settings');
  const btnSaveSettings = document.getElementById('btn-save-settings');

  const cfgLut = document.getElementById('cfg-lut');
  const cfgCodec = document.getElementById('cfg-codec');
  const cfgProfile = document.getElementById('cfg-profile');
  const cfgAudio = document.getElementById('cfg-audio');
  const cfgInterval = document.getElementById('cfg-interval');
  const cfgChecks = document.getElementById('cfg-checks');
  const cfgDelay = document.getElementById('cfg-delay');

  // Application State
  let isRunning = false;
  let currentServiceState = 'idle'; // 'idle' | 'starting' | 'watching' | 'transcoding' | 'stopping' | 'error'
  let activeConfig = {};

  // Initialize
  try {
    const initialState = await electron.getInitialState();
    if (initialState) {
      updateRootDisplay(initialState.rootFolder);
      updateFolderCounts(initialState.counts);
      activeConfig = initialState.config || {};
      populateSettingsForm(activeConfig);
      if (initialState.isRunning) {
        setServiceState('watching');
      } else {
        setServiceState('idle');
      }
    }
  } catch (err) {
    appendLogLine(`[ERROR] Failed to load initial state: ${err.message}`, 'error');
  }

  // Periodic Folder Count Polling (every 3 seconds)
  setInterval(async () => {
    try {
      const counts = await electron.scanFolderCounts();
      updateFolderCounts(counts);
    } catch (e) {
      // ignore
    }
  }, 3000);

  // Event Listeners from Main Process
  electron.onLog((line) => {
    let type = 'info';
    if (line.includes('[ERROR]') || line.includes('Error:')) type = 'error';
    else if (line.includes('[WARNING]') || line.includes('Warning:')) type = 'warn';
    else if (line.includes('[GUI]') || line.includes('[SYSTEM]') || line.includes('[READY]')) type = 'system';
    else if (line.includes('Progress:') || line.includes('Render') || line.includes('Speed:')) type = 'render';
    else if (line.includes('Found new clip') || line.includes('Stable file')) type = 'file';

    appendLogLine(line, type);
  });

  electron.onStatus((status) => {
    if (status.state) {
      setServiceState(status.state);
    }
    if (status.currentClip) {
      currentClipLabel.textContent = status.currentClip;
      progressContainer.classList.add('visible');
    } else if (status.state === 'watching' || status.state === 'idle' || status.state === 'stopped') {
      progressContainer.classList.remove('visible');
    }
  });

  electron.onProgress((data) => {
    if (data && typeof data.progress === 'number') {
      progressFill.style.width = `${data.progress}%`;
      telemetryPercent.textContent = `${data.progress}%`;
      progressContainer.classList.add('visible');
    }
  });

  electron.onSpeed((data) => {
    if (data && typeof data.fps === 'number') {
      telemetryFps.textContent = `${data.fps.toFixed(1)} fps`;
    }
  });

  electron.onFolderCounts((counts) => {
    updateFolderCounts(counts);
  });

  // UI Handlers
  btnSelectRoot.addEventListener('click', async () => {
    if (isRunning) {
      alert('Please stop the active watcher before changing the watch folder.');
      return;
    }
    const res = await electron.selectDirectory();
    if (res && res.path) {
      updateRootDisplay(res.path);
      updateFolderCounts(res.counts);
      appendLogLine(`[GUI] Watch root updated to: ${res.path}`, 'system');
    }
  });

  // Reveal buttons for each of the 5 folders
  document.querySelectorAll('.reveal-btn').forEach((btn) => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      const folder = btn.getAttribute('data-folder');
      await electron.revealInFinder(folder);
    });
  });

  // Service Start / Stop Toggle
  btnToggleService.addEventListener('click', async () => {
    if (isRunning) {
      setServiceState('stopping');
      await electron.stopWatcher();
    } else {
      setServiceState('starting');
      const res = await electron.startWatcher();
      if (res && !res.success) {
        setServiceState('error');
        appendLogLine(`[ERROR] Start failed: ${res.message}`, 'error');
      } else {
        setServiceState('watching');
      }
    }
  });

  // Terminal actions
  btnCopyLogs.addEventListener('click', () => {
    const text = terminalStream.innerText;
    navigator.clipboard.writeText(text);
    btnCopyLogs.textContent = 'Copied!';
    setTimeout(() => {
      btnCopyLogs.innerHTML = `<svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> Copy`;
    }, 1500);
  });

  btnClearLogs.addEventListener('click', () => {
    terminalStream.innerHTML = '';
  });

  // Settings Modal Handlers
  btnOpenSettings.addEventListener('click', () => {
    populateSettingsForm(activeConfig);
    modalSettings.classList.remove('hidden');
  });

  btnCloseSettings.addEventListener('click', () => {
    modalSettings.classList.add('hidden');
  });

  btnCancelSettings.addEventListener('click', () => {
    modalSettings.classList.add('hidden');
  });

  btnSaveSettings.addEventListener('click', async () => {
    activeConfig.apply_lut = cfgLut.value;
    activeConfig.codec = cfgCodec.value;
    activeConfig.encoder = cfgProfile.value;
    activeConfig.audio_codec = cfgAudio.value;
    activeConfig.scan_interval_seconds = parseInt(cfgInterval.value, 10) || 5;
    activeConfig.stability_checks = parseInt(cfgChecks.value, 10) || 3;
    activeConfig.stability_delay_seconds = parseInt(cfgDelay.value, 10) || 2;

    await electron.saveConfig(activeConfig);
    appendLogLine(`[GUI] Configuration updated: LUT='${activeConfig.apply_lut}', Codec='${activeConfig.codec}', Profile='${activeConfig.encoder}'`, 'system');
    modalSettings.classList.add('hidden');
  });

  // Helper Functions
  function updateRootDisplay(pathStr) {
    if (pathStr) {
      rootPathEl.textContent = pathStr;
      rootPathEl.title = pathStr;
    }
  }

  function updateFolderCounts(counts) {
    if (!counts) return;
    for (const [key, val] of Object.entries(counts)) {
      const el = document.getElementById(`count-${key}`);
      if (el) {
        el.textContent = val;
      }
    }
  }

  function populateSettingsForm(cfg) {
    if (cfg.apply_lut) cfgLut.value = cfg.apply_lut;
    if (cfg.codec) cfgCodec.value = cfg.codec;
    if (cfg.encoder) cfgProfile.value = cfg.encoder;
    if (cfg.audio_codec) cfgAudio.value = cfg.audio_codec;
    if (cfg.scan_interval_seconds) cfgInterval.value = cfg.scan_interval_seconds;
    if (cfg.stability_checks) cfgChecks.value = cfg.stability_checks;
    if (cfg.stability_delay_seconds) cfgDelay.value = cfg.stability_delay_seconds;
  }

  function setServiceState(state) {
    currentServiceState = state;
    servicePill.className = `service-pill ${state}`;

    switch (state) {
      case 'idle':
      case 'stopped':
        isRunning = false;
        serviceStatusText.textContent = 'Idle';
        btnToggleLabel.textContent = 'Start Watcher';
        btnToggleService.classList.remove('active-running');
        playIcon.classList.remove('hidden');
        stopIcon.classList.add('hidden');
        progressContainer.classList.remove('visible');
        break;

      case 'starting':
        isRunning = true;
        serviceStatusText.textContent = 'Starting...';
        btnToggleLabel.textContent = 'Stop Watcher';
        btnToggleService.classList.add('active-running');
        playIcon.classList.add('hidden');
        stopIcon.classList.remove('hidden');
        break;

      case 'watching':
        isRunning = true;
        serviceStatusText.textContent = 'Watching Folder';
        btnToggleLabel.textContent = 'Stop Watcher';
        btnToggleService.classList.add('active-running');
        playIcon.classList.add('hidden');
        stopIcon.classList.remove('hidden');
        break;

      case 'transcoding':
        isRunning = true;
        serviceStatusText.textContent = 'Transcoding';
        btnToggleLabel.textContent = 'Stop Watcher';
        btnToggleService.classList.add('active-running');
        playIcon.classList.add('hidden');
        stopIcon.classList.remove('hidden');
        progressContainer.classList.add('visible');
        break;

      case 'stopping':
        isRunning = false;
        serviceStatusText.textContent = 'Stopping...';
        btnToggleLabel.textContent = 'Start Watcher';
        break;

      case 'error':
        isRunning = false;
        serviceStatusText.textContent = 'Engine Error';
        btnToggleLabel.textContent = 'Retry Start';
        btnToggleService.classList.remove('active-running');
        playIcon.classList.remove('hidden');
        stopIcon.classList.add('hidden');
        break;
    }
  }

  function appendLogLine(text, type = 'info') {
    const line = document.createElement('div');
    line.className = `log-line log-${type}`;
    line.textContent = text;
    terminalStream.appendChild(line);

    if (chkAutoScroll.checked) {
      terminalStream.scrollTop = terminalStream.scrollHeight;
    }
  }
});
