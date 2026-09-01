import Foundation

@MainActor
public class ProcessRunner {
    public static let shared = ProcessRunner()
    
    private var process: Process?
    private var stdoutPipe: Pipe?
    private var stderrPipe: Pipe?
    
    public var isRunning: Bool {
        return process != nil && process!.isRunning
    }
    
    private init() {}
    
    /// Starts the Python Hot Folder Watcher process with live log piping.
    public func startWatcher(appState: AppState) {
        guard !isRunning else { return }
        
        let rootFolder = appState.rootFolder
        // 1. Ensure folder structure exists
        FolderManager.shared.validateAndProvision(rootFolder: rootFolder)
        
        // 2. Write dynamic runtime YAML configuration
        let yamlContent = appState.config.generateYAML(forRootFolder: rootFolder)
        let configPath = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("braw_gui_config.yaml")
        try? yamlContent.write(to: configPath, atomically: true, encoding: .utf8)
        
        // 3. Locate Python3 binary
        let pythonPath = resolvePythonPath()
        
        // 4. Locate Project Working Directory (contains src/ and config/)
        let projectDir = resolveProjectWorkingDir()
        
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: pythonPath)
        proc.currentDirectoryURL = projectDir
        proc.arguments = ["-u", "-m", "src.cli", "watch", "--config", configPath.path]
        
        // 5. Environment Variables for DaVinci Resolve Scripting
        var env = ProcessInfo.processInfo.environment
        let scriptAPI = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
        let scriptLib = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
        env["RESOLVE_SCRIPT_API"] = scriptAPI
        env["RESOLVE_SCRIPT_LIB"] = scriptLib
        env["PYTHONPATH"] = "\(env["PYTHONPATH"] ?? ""):\(scriptAPI)/Modules/:\(projectDir.path)"
        proc.environment = env
        
        // 6. Setup asynchronous stdout & stderr pipes
        let outPipe = Pipe()
        let errPipe = Pipe()
        proc.standardOutput = outPipe
        proc.standardError = errPipe
        
        self.stdoutPipe = outPipe
        self.stderrPipe = errPipe
        self.process = proc
        
        Task { @MainActor in
            appState.serviceState = .starting
            appState.statusMessage = "Starting DaVinci Resolve Engine..."
            appState.addLogLine("[GUI] Initializing BRAW Watcher on: \(rootFolder.path)")
            appState.addLogLine("[GUI] Codec: \(appState.config.codec), Profile: \(appState.config.encodingProfile), LUT: \(appState.config.selectedLUT.name)")
        }
        
        outPipe.fileHandleForReading.readabilityHandler = { [weak appState] handle in
            let data = handle.availableData
            guard !data.isEmpty, let output = String(data: data, encoding: .utf8) else { return }
            let lines = output.components(separatedBy: "\n")
            for line in lines where !line.isEmpty {
                Task { @MainActor [weak appState] in
                    appState?.addLogLine(line)
                }
            }
        }
        
        errPipe.fileHandleForReading.readabilityHandler = { [weak appState] handle in
            let data = handle.availableData
            guard !data.isEmpty, let output = String(data: data, encoding: .utf8) else { return }
            let lines = output.components(separatedBy: "\n")
            for line in lines where !line.isEmpty {
                Task { @MainActor [weak appState] in
                    appState?.addLogLine(line)
                }
            }
        }
        
        proc.terminationHandler = { [weak appState, weak self] _ in
            Task { @MainActor [weak appState, weak self] in
                appState?.serviceState = .stopped
                appState?.statusMessage = "Watcher Stopped."
                appState?.currentClipName = nil
                appState?.transcodeProgress = 0.0
                appState?.addLogLine("[GUI] Background process terminated cleanly.")
                appState?.refreshSubfolders()
                self?.cleanupPipes()
            }
        }
        
        do {
            try proc.run()
        } catch {
            Task { @MainActor [weak self] in
                appState.serviceState = .error
                appState.statusMessage = "Failed to launch process: \(error.localizedDescription)"
                appState.addLogLine("[ERROR] Could not start watcher: \(error.localizedDescription)")
                self?.cleanupPipes()
            }
        }
    }
    
    /// Stops the running background process cleanly.
    public func stopWatcher(appState: AppState) {
        guard let proc = process, proc.isRunning else { return }
        appState.statusMessage = "Stopping service..."
        appState.addLogLine("[GUI] Sending graceful stop signal to engine...")
        
        proc.interrupt() // SIGINT
        
        Task {
            try? await Task.sleep(nanoseconds: 3_000_000_000)
            if let proc = self.process, proc.isRunning {
                proc.terminate() // SIGTERM fallback
            }
        }
    }
    
    private func cleanupPipes() {
        stdoutPipe?.fileHandleForReading.readabilityHandler = nil
        stderrPipe?.fileHandleForReading.readabilityHandler = nil
        stdoutPipe = nil
        stderrPipe = nil
        process = nil
    }
    
    private func resolvePythonPath() -> String {
        let candidates = [
            "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3"
        ]
        for path in candidates {
            if FileManager.default.fileExists(atPath: path) {
                return path
            }
        }
        return "/usr/bin/python3"
    }
    
    private func resolveProjectWorkingDir() -> URL {
        let current = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        
        // If running inside versions/v2-gui
        if current.lastPathComponent == "v2-gui" {
            return current
        }
        
        let v2Dir = current.appendingPathComponent("versions").appendingPathComponent("v2-gui")
        if FileManager.default.fileExists(atPath: v2Dir.path) {
            return v2Dir
        }
        
        return current
    }
}
