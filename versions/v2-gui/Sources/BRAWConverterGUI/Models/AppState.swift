import Foundation
import SwiftUI
import Combine

public enum ServiceState {
    case stopped
    case starting
    case watching
    case transcoding
    case error
    
    public var title: String {
        switch self {
        case .stopped: return "Watcher Stopped"
        case .starting: return "Connecting Engine..."
        case .watching: return "Active (Watching Ingest)"
        case .transcoding: return "Transcoding Footage"
        case .error: return "Engine Error"
        }
    }
    
    public var color: Color {
        switch self {
        case .stopped: return .gray
        case .starting: return .orange
        case .watching: return .green
        case .transcoding: return .blue
        case .error: return .red
        }
    }
}

public struct LogEntry: Identifiable {
    public let id = UUID()
    public let timestamp: Date
    public let rawText: String
    public let level: String
    public let message: String
    
    public init(rawText: String) {
        self.timestamp = Date()
        self.rawText = rawText
        
        // Extract level if present (e.g. [INFO], [ERROR], [WARNING])
        if rawText.contains("[ERROR]") {
            self.level = "ERROR"
            self.message = rawText
        } else if rawText.contains("[WARNING]") {
            self.level = "WARN"
            self.message = rawText
        } else if rawText.contains("[INFO]") {
            self.level = "INFO"
            self.message = rawText
        } else {
            self.level = "DEBUG"
            self.message = rawText
        }
    }
}

@MainActor
public class AppState: ObservableObject {
    @Published public var rootFolder: URL {
        didSet {
            FolderManager.shared.saveRootFolder(rootFolder)
            refreshSubfolders()
        }
    }
    
    @Published public var subfolders: [SubfolderInfo] = []
    @Published public var serviceState: ServiceState = .stopped
    @Published public var statusMessage: String = "Ready. Select an ingest folder and start the watcher."
    
    // Live Transcode Status
    @Published public var currentClipName: String? = nil
    @Published public var transcodeProgress: Double = 0.0 // 0.0 to 1.0
    @Published public var transcodeFps: Double = 0.0
    
    // Terminal Logs
    @Published public var logs: [LogEntry] = []
    
    // Settings
    @Published public var config = TranscodeConfigModel()
    
    private var timer: AnyCancellable?
    
    public init() {
        let initialRoot = FolderManager.shared.resolveInitialRootFolder()
        self.rootFolder = initialRoot
        refreshSubfolders()
        
        // Periodic file count refresh
        timer = Timer.publish(every: 2.0, on: .main, in: .common)
            .autoconnect()
            .sink { [weak self] _ in
                self?.refreshSubfolders()
            }
    }
    
    public func refreshSubfolders() {
        self.subfolders = FolderManager.shared.validateAndProvision(rootFolder: rootFolder)
    }
    
    public func addLogLine(_ line: String) {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        
        let entry = LogEntry(rawText: trimmed)
        logs.append(entry)
        
        // Limit logs buffer to last 1500 entries
        if logs.count > 1500 {
            logs.removeFirst(logs.count - 1500)
        }
        
        // Parse progress and status updates
        parseLogLine(trimmed)
    }
    
    private func parseLogLine(_ line: String) {
        // e.g. "Starting transcode job for: A001_06201100_C073.braw"
        if line.contains("Starting transcode job for:") {
            if let name = line.components(separatedBy: "Starting transcode job for:").last?.trimmingCharacters(in: .whitespaces) {
                self.currentClipName = name
                self.serviceState = .transcoding
                self.transcodeProgress = 0.0
                self.statusMessage = "Transcoding \(name)..."
            }
        }
        
        // e.g. "Transcode Progress: 45% | Speed: 42.1 fps"
        if line.contains("Transcode Progress:") {
            let pattern = #"Transcode Progress:\s*(\d+)%"#
            if let regex = try? NSRegularExpression(pattern: pattern),
               let match = regex.firstMatch(in: line, range: NSRange(line.startIndex..., in: line)),
               let range = Range(match.range(at: 1), in: line),
               let percent = Double(line[range]) {
                self.transcodeProgress = percent / 100.0
            }
            
            let fpsPattern = #"Speed:\s*([\d\.]+)\s*fps"#
            if let regex = try? NSRegularExpression(pattern: fpsPattern),
               let match = regex.firstMatch(in: line, range: NSRange(line.startIndex..., in: line)),
               let range = Range(match.range(at: 1), in: line),
               let fps = Double(line[range]) {
                self.transcodeFps = fps
            }
        }
        
        // e.g. "Render completed successfully in 12.1 seconds!"
        if line.contains("Render completed successfully") {
            self.transcodeProgress = 1.0
            self.statusMessage = "Render complete for \(self.currentClipName ?? "clip")!"
            DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) { [weak self] in
                if self?.serviceState == .transcoding {
                    self?.serviceState = .watching
                    self?.currentClipName = nil
                    self?.transcodeProgress = 0.0
                    self?.statusMessage = "Watching for new clips..."
                }
                self?.refreshSubfolders()
            }
        }
        
        if line.contains("Hot Folder Watcher is running") {
            self.serviceState = .watching
            self.statusMessage = "Watching folder: \(rootFolder.lastPathComponent)/00_IN_INGEST"
        }
        
        if line.contains("Transcode failed") {
            self.serviceState = .watching
            self.statusMessage = "Last clip failed. Quarantined in 99_FAILED."
            refreshSubfolders()
        }
    }
    
    public func clearLogs() {
        logs.removeAll()
    }
}
