const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');
const os = require('os');

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) {
  app.quit();
}

let mainWindow = null;
let watcherProcess = null;
let currentConfig = {
  scan_interval_seconds: 5,
  stability_checks: 3,
  stability_delay_seconds: 2,
  format: 'mp4',
  codec: 'H265',
  encoder: 'Main10',
  resolution_match_source: true,
  apply_lut: 'Blackmagic Gen 5 to Extended Video',
  audio_codec: 'AAC'
};

const REQUIRED_SUBDIRECTORIES = [
  '00_IN_INGEST',
  '01_PROCESSING',
  '02_COMPLETED_MP4',
  '03_ARCHIVE_BRAW',
  '99_FAILED'
];

function resolveDefaultRootFolder() {
  const defaultWatch = path.join(app.getAppPath(), 'watch_folders');
  if (fs.existsSync(defaultWatch)) {
    return defaultWatch;
  }
  return path.join(process.cwd(), 'watch_folders');
}

let activeRootFolder = resolveDefaultRootFolder();

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 760,
    minWidth: 860,
    minHeight: 600,
    title: 'Black Magic Converter',
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#0f1117',
    icon: path.join(__dirname, '../../../assets/icons/icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  // Load Vite Dev Server URL or bundled index.html
  if (MAIN_WINDOW_VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(MAIN_WINDOW_VITE_DEV_SERVER_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, `../renderer/${MAIN_WINDOW_VITE_NAME}/index.html`));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
    stopWatcherProcess();
  });
}

function validateAndProvisionDirectories(rootFolder) {
  if (!fs.existsSync(rootFolder)) {
    fs.mkdirSync(rootFolder, { recursive: true });
  }
  for (const sub of REQUIRED_SUBDIRECTORIES) {
    const subPath = path.join(rootFolder, sub);
    if (!fs.existsSync(subPath)) {
      fs.mkdirSync(subPath, { recursive: true });
    }
  }
}

function countFilesInDirectory(dirPath) {
  try {
    if (!fs.existsSync(dirPath)) return 0;
    const items = fs.readdirSync(dirPath);
    return items.filter(f => !f.startsWith('.')).length;
  } catch (err) {
    return 0;
  }
}

function scanAllFolderCounts(rootFolder) {
  const counts = {};
  for (const sub of REQUIRED_SUBDIRECTORIES) {
    counts[sub] = countFilesInDirectory(path.join(rootFolder, sub));
  }
  return counts;
}

function resolvePythonBinary() {
  const candidates = [
    process.env.PYTHON_PATH,
    '/Library/Frameworks/Python.framework/Versions/3.12/bin/python3',
    '/Library/Frameworks/Python.framework/Versions/3.11/bin/python3',
    '/opt/homebrew/bin/python3',
    '/usr/local/bin/python3',
    '/usr/bin/python3',
    'python3',
    'python'
  ].filter(Boolean);

  for (const p of candidates) {
    if (p.includes('/') && fs.existsSync(p)) {
      return p;
    }
  }
  return 'python3';
}

function resolveProjectRootDir() {
  let cur = app.getAppPath();
  if (fs.existsSync(path.join(cur, 'src', 'cli.py'))) {
    return cur;
  }
  if (fs.existsSync(path.join(process.cwd(), 'src', 'cli.py'))) {
    return process.cwd();
  }
  // Try parent directories
  let parent = path.dirname(cur);
  if (fs.existsSync(path.join(parent, 'src', 'cli.py'))) {
    return parent;
  }
  return process.cwd();
}

function dumpSimpleYaml(obj, indent = 0) {
  let lines = [];
  const pad = ' '.repeat(indent);
  for (const [key, value] of Object.entries(obj)) {
    if (value === null || value === undefined) {
      lines.push(`${pad}${key}: null`);
    } else if (typeof value === 'object' && !Array.isArray(value)) {
      lines.push(`${pad}${key}:`);
      lines.push(dumpSimpleYaml(value, indent + 2));
    } else if (Array.isArray(value)) {
      lines.push(`${pad}${key}: [${value.map(v => JSON.stringify(v)).join(', ')}]`);
    } else if (typeof value === 'string') {
      lines.push(`${pad}${key}: "${value.replace(/"/g, '\\"')}"`);
    } else {
      lines.push(`${pad}${key}: ${value}`);
    }
  }
  return lines.join('\n');
}

function generateRuntimeYaml(rootFolder, config) {
  const configObj = {
    storage: {
      ingest_dir: path.join(rootFolder, '00_IN_INGEST'),
      processing_dir: path.join(rootFolder, '01_PROCESSING'),
      completed_dir: path.join(rootFolder, '02_COMPLETED_MP4'),
      archive_dir: path.join(rootFolder, '03_ARCHIVE_BRAW'),
      failed_dir: path.join(rootFolder, '99_FAILED')
    },
    watcher: {
      poll_interval: config.scan_interval_seconds || 2.0,
      stability_checks: config.stability_checks || 3,
      stability_delay: config.stability_delay_seconds || 2.0,
      extensions: ['.braw'],
      include_sidecars: true
    },
    transcode: {
      container: config.format || 'mp4',
      codec: config.codec || 'H265',
      encoding_profile: config.encoder || 'Main10',
      video_quality: 'Best',
      bitrate_mbps: 0,
      resolution: config.resolution_match_source !== false ? 'source' : '1080p',
      frame_rate: 'source',
      audio: {
        codec: (config.audio_codec || 'aac').toLowerCase(),
        sample_rate: 48000,
        bit_depth: 16,
        bitrate_kbps: 320
      },
      color: {
        mode: 'lut',
        lut_path: config.apply_lut || 'Blackmagic Gen 5 Film to Extended Video.cube',
        fallback_lut_path: 'Blackmagic Film to Extended Video v4.cube'
      }
    },
    engine: {
      type: 'ffmpeg',
      ffmpeg_path: 'ffmpeg',
      decoder_path: 'bin/braw_decode',
      hardware_acceleration: true
    }
  };

  const yamlStr = dumpSimpleYaml(configObj);
  const tempPath = path.join(os.tmpdir(), 'braw_electron_config.yaml');
  fs.writeFileSync(tempPath, yamlStr, 'utf8');
  return tempPath;
}

function parseStreamLine(rawLine) {
  if (!mainWindow || !rawLine) return;

  // Strip ANSI terminal color codes (e.g. \x1b[32m ... \x1b[0m)
  const line = rawLine.replace(/[\u001b\x1b]\[[0-9;]*[a-zA-Z]/g, '').trim();
  if (!line) return;

  mainWindow.webContents.send('engine:log', line);

  // Parse starting transcode
  const transcodeMatch = line.match(/Starting transcode job for:\s*(.+)$/i);
  if (transcodeMatch) {
    mainWindow.webContents.send('engine:status', {
      state: 'transcoding',
      currentClip: transcodeMatch[1].trim(),
      message: `Transcoding ${transcodeMatch[1].trim()}`
    });
  }

  // Parse progress percentage and speed from decoder/pipeline logs
  const transcodeProgMatch = line.match(/Transcode Progress:\s*([\d\.]+)%\s*\(Frame\s*\d+\/\d+\)\s*Speed:\s*([\d\.]+)\s*fps/i);
  const oldProgMatch = line.match(/Progress:\s*frame\s*\d+\/\d+\s*\(([\d\.]+)%\)\s*@\s*([\d\.]+)\s*fps/i);
  const jsonProgMatch = line.match(/PROGRESS:\{.*"percent":([\d\.]+).*,"fps":([\d\.]+).*\}/i);

  if (transcodeProgMatch) {
    const pct = Math.round(parseFloat(transcodeProgMatch[1]));
    const fps = parseFloat(transcodeProgMatch[2]);
    mainWindow.webContents.send('engine:progress', { progress: pct });
    mainWindow.webContents.send('engine:speed', { fps });
  } else if (oldProgMatch) {
    const pct = Math.round(parseFloat(oldProgMatch[1]));
    const fps = parseFloat(oldProgMatch[2]);
    mainWindow.webContents.send('engine:progress', { progress: pct });
    mainWindow.webContents.send('engine:speed', { fps });
  } else if (jsonProgMatch) {
    const pct = Math.round(parseFloat(jsonProgMatch[1]));
    const fps = parseFloat(jsonProgMatch[2]);
    mainWindow.webContents.send('engine:progress', { progress: pct });
    mainWindow.webContents.send('engine:speed', { fps });
  }

  // Parse completion
  if (line.includes('Transcode succeeded for') || line.includes('Render completed successfully') || line.includes('Finished transcode')) {
    mainWindow.webContents.send('engine:progress', { progress: 100 });
    mainWindow.webContents.send('engine:status', {
      state: 'watching',
      currentClip: null,
      message: 'Transcode completed. Watching folder for new clips...'
    });
    mainWindow.webContents.send('engine:folderCounts', scanAllFolderCounts(activeRootFolder));
  }

  // Parse failure
  if (line.includes('Transcode failed') || line.includes('[ERROR]')) {
    mainWindow.webContents.send('engine:status', {
      message: 'Notice/Error encountered during execution.'
    });
    mainWindow.webContents.send('engine:folderCounts', scanAllFolderCounts(activeRootFolder));
  }
}

function stopWatcherProcess() {
  if (watcherProcess) {
    try {
      watcherProcess.kill('SIGINT');
      const procRef = watcherProcess;
      setTimeout(() => {
        try {
          if (procRef && !procRef.killed) {
            procRef.kill('SIGTERM');
          }
        } catch (e) {
          // ignore
        }
      }, 3000);
    } catch (err) {
      console.error('Error stopping watcher process:', err);
    }
    watcherProcess = null;
  }
}

// IPC Handlers
ipcMain.handle('dialog:selectDirectory', async () => {
  if (!mainWindow) return null;
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory', 'createDirectory'],
    defaultPath: activeRootFolder,
    title: 'Select BRAW Watch Directory'
  });

  if (!result.canceled && result.filePaths.length > 0) {
    const selected = result.filePaths[0];
    activeRootFolder = selected;
    validateAndProvisionDirectories(activeRootFolder);
    return {
      path: activeRootFolder,
      counts: scanAllFolderCounts(activeRootFolder)
    };
  }
  return null;
});

ipcMain.handle('dialog:revealInFinder', async (_event, subfolderName) => {
  const target = subfolderName 
    ? path.join(activeRootFolder, subfolderName)
    : activeRootFolder;

  if (fs.existsSync(target)) {
    shell.openPath(target);
    return true;
  }
  return false;
});

ipcMain.handle('engine:getInitialState', () => {
  validateAndProvisionDirectories(activeRootFolder);
  return {
    rootFolder: activeRootFolder,
    counts: scanAllFolderCounts(activeRootFolder),
    config: currentConfig,
    isRunning: watcherProcess !== null,
    subdirectories: REQUIRED_SUBDIRECTORIES
  };
});

ipcMain.handle('engine:scanFolderCounts', () => {
  return scanAllFolderCounts(activeRootFolder);
});

ipcMain.handle('engine:saveConfig', (_event, newConfig) => {
  currentConfig = { ...currentConfig, ...newConfig };
  return currentConfig;
});

ipcMain.handle('engine:startWatcher', async () => {
  if (watcherProcess) {
    return { success: false, message: 'Watcher is already running.' };
  }

  try {
    validateAndProvisionDirectories(activeRootFolder);
    const configFilePath = generateRuntimeYaml(activeRootFolder, currentConfig);
    const pythonBin = resolvePythonBinary();
    const projectDir = resolveProjectRootDir();

    const env = {
      ...process.env,
      PYTHONPATH: `${process.env.PYTHONPATH || ''}:${projectDir}`,
      PYTHONUNBUFFERED: '1'
    };

    const args = ['-u', '-m', 'src.cli', 'watch', '--config', configFilePath];

    if (mainWindow) {
      mainWindow.webContents.send('engine:log', `[GUI] Launching Python Watcher: ${pythonBin} ${args.join(' ')}`);
      mainWindow.webContents.send('engine:log', `[GUI] Target Watch Folder: ${activeRootFolder}`);
      mainWindow.webContents.send('engine:status', {
        state: 'starting',
        message: 'Initializing Standalone FFmpeg + BRAW Engine...'
      });
    }

    watcherProcess = spawn(pythonBin, args, {
      cwd: projectDir,
      env: env
    });

    watcherProcess.stdout.on('data', (data) => {
      const lines = data.toString().split('\n');
      for (const line of lines) {
        if (line.trim().length > 0) {
          parseStreamLine(line);
        }
      }
    });

    watcherProcess.stderr.on('data', (data) => {
      const lines = data.toString().split('\n');
      for (const line of lines) {
        if (line.trim().length > 0) {
          parseStreamLine(line);
        }
      }
    });

    watcherProcess.on('close', (code) => {
      watcherProcess = null;
      if (mainWindow) {
        mainWindow.webContents.send('engine:log', `[GUI] Process exited with code ${code}`);
        mainWindow.webContents.send('engine:status', {
          state: 'stopped',
          currentClip: null,
          message: 'Watcher service stopped.'
        });
        mainWindow.webContents.send('engine:folderCounts', scanAllFolderCounts(activeRootFolder));
      }
    });

    watcherProcess.on('error', (err) => {
      watcherProcess = null;
      if (mainWindow) {
        mainWindow.webContents.send('engine:log', `[ERROR] Process failed to spawn: ${err.message}`);
        mainWindow.webContents.send('engine:status', {
          state: 'error',
          currentClip: null,
          message: `Process error: ${err.message}`
        });
      }
    });

    return { success: true };
  } catch (err) {
    return { success: false, message: err.message };
  }
});

ipcMain.handle('engine:stopWatcher', async () => {
  if (!watcherProcess) {
    return { success: true };
  }
  if (mainWindow) {
    mainWindow.webContents.send('engine:log', '[GUI] Sending graceful SIGINT stop signal to transcoder...');
    mainWindow.webContents.send('engine:status', {
      state: 'stopping',
      message: 'Stopping engine gracefully...'
    });
  }
  stopWatcherProcess();
  return { success: true };
});

ipcMain.handle('system:openExternal', async (_event, url) => {
  if (url && (url.startsWith('https://') || url.startsWith('http://'))) {
    await shell.openExternal(url);
    return true;
  }
  return false;
});

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  stopWatcherProcess();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  stopWatcherProcess();
});
