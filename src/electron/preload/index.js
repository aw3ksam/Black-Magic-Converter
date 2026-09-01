const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Directory & OS dialogs
  selectDirectory: () => ipcRenderer.invoke('dialog:selectDirectory'),
  revealInFinder: (subfolder) => ipcRenderer.invoke('dialog:revealInFinder', subfolder),

  // Engine state & control
  getInitialState: () => ipcRenderer.invoke('engine:getInitialState'),
  scanFolderCounts: () => ipcRenderer.invoke('engine:scanFolderCounts'),
  saveConfig: (config) => ipcRenderer.invoke('engine:saveConfig', config),
  startWatcher: () => ipcRenderer.invoke('engine:startWatcher'),
  stopWatcher: () => ipcRenderer.invoke('engine:stopWatcher'),
  openExternal: (url) => ipcRenderer.invoke('system:openExternal', url),

  // Event listeners
  onLog: (callback) => {
    const listener = (_event, logLine) => callback(logLine);
    ipcRenderer.on('engine:log', listener);
    return () => ipcRenderer.removeListener('engine:log', listener);
  },
  onStatus: (callback) => {
    const listener = (_event, status) => callback(status);
    ipcRenderer.on('engine:status', listener);
    return () => ipcRenderer.removeListener('engine:status', listener);
  },
  onProgress: (callback) => {
    const listener = (_event, data) => callback(data);
    ipcRenderer.on('engine:progress', listener);
    return () => ipcRenderer.removeListener('engine:progress', listener);
  },
  onSpeed: (callback) => {
    const listener = (_event, data) => callback(data);
    ipcRenderer.on('engine:speed', listener);
    return () => ipcRenderer.removeListener('engine:speed', listener);
  },
  onFolderCounts: (callback) => {
    const listener = (_event, counts) => callback(counts);
    ipcRenderer.on('engine:folderCounts', listener);
    return () => ipcRenderer.removeListener('engine:folderCounts', listener);
  }
});
