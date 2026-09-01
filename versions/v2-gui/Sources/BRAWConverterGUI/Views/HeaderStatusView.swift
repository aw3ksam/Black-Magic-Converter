import SwiftUI
import AppKit

public struct HeaderStatusView: View {
    @ObservedObject var appState: AppState
    @Binding var showSettings: Bool
    
    public init(appState: AppState, showSettings: Binding<Bool>) {
        self.appState = appState
        self._showSettings = showSettings
    }
    
    public var body: some View {
        VStack(spacing: 14) {
            HStack(alignment: .center, spacing: 16) {
                // App Branding & Icon
                ZStack {
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .fill(
                            LinearGradient(
                                colors: [Color.orange.opacity(0.8), Color.red.opacity(0.9)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                        .frame(width: 44, height: 44)
                    
                    Image(systemName: "film.stack.fill")
                        .font(.system(size: 22, weight: .bold))
                        .foregroundColor(.white)
                }
                
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 8) {
                        Text("BRAW Video Converter")
                            .font(.system(size: 18, weight: .bold))
                        
                        Text("v2.0 (GUI)")
                            .font(.system(size: 11, weight: .semibold))
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.blue.opacity(0.15))
                            .foregroundColor(.blue)
                            .cornerRadius(4)
                    }
                    
                    Text("Automated Ingest & H.265 Transcoder for Blackmagic RAW")
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                }
                
                Spacer()
                
                // Settings button
                Button(action: { showSettings = true }) {
                    Image(systemName: "slider.horizontal.3")
                        .font(.system(size: 14, weight: .medium))
                        .padding(7)
                        .background(Color(NSColor.controlBackgroundColor))
                        .cornerRadius(8)
                }
                .buttonStyle(.plain)
                .help("Transcode & LUT Settings")
                
                // Start / Stop Master Button
                Button(action: toggleWatcher) {
                    HStack(spacing: 8) {
                        Image(systemName: isRunning ? "stop.fill" : "play.fill")
                            .font(.system(size: 13, weight: .bold))
                        Text(isRunning ? "Stop Watcher" : "Start Watcher")
                            .font(.system(size: 13, weight: .semibold))
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .foregroundColor(.white)
                    .background(isRunning ? Color.red : Color.green)
                    .cornerRadius(8)
                    .shadow(color: (isRunning ? Color.red : Color.green).opacity(0.3), radius: 4, y: 2)
                }
                .buttonStyle(.plain)
            }
            
            Divider()
            
            // Watch Folder Selector & Status Row
            HStack(spacing: 12) {
                // Root Folder Box
                HStack(spacing: 8) {
                    Image(systemName: "folder.badge.gearshape")
                        .foregroundColor(.accentColor)
                        .font(.system(size: 14))
                    
                    VStack(alignment: .leading, spacing: 1) {
                        Text("Root Ingest Directory:")
                            .font(.system(size: 10, weight: .semibold))
                            .foregroundColor(.secondary)
                        
                        Text(appState.rootFolder.path)
                            .font(.system(size: 12, design: .monospaced))
                            .lineLimit(1)
                            .truncationMode(.middle)
                    }
                    
                    Spacer()
                    
                    Button("Change Root...") {
                        selectCustomRootFolder()
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .disabled(isRunning)
                }
                .padding(8)
                .background(Color(NSColor.controlBackgroundColor).opacity(0.7))
                .cornerRadius(8)
                
                // Live Status Badge
                HStack(spacing: 6) {
                    Circle()
                        .fill(appState.serviceState.color)
                        .frame(width: 10, height: 10)
                    
                    Text(appState.serviceState.title)
                        .font(.system(size: 12, weight: .medium))
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
                .background(appState.serviceState.color.opacity(0.12))
                .cornerRadius(8)
            }
        }
        .padding(.horizontal, 16)
        .padding(.top, 14)
        .padding(.bottom, 6)
    }
    
    private var isRunning: Bool {
        appState.serviceState == .watching || appState.serviceState == .transcoding || appState.serviceState == .starting
    }
    
    private func toggleWatcher() {
        if isRunning {
            ProcessRunner.shared.stopWatcher(appState: appState)
        } else {
            ProcessRunner.shared.startWatcher(appState: appState)
        }
    }
    
    private func selectCustomRootFolder() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = true
        panel.prompt = "Set Ingest Root"
        panel.directoryURL = appState.rootFolder
        
        if panel.runModal() == .OK, let selectedURL = panel.url {
            appState.rootFolder = selectedURL
            FolderManager.shared.validateAndProvision(rootFolder: selectedURL)
            appState.refreshSubfolders()
            appState.addLogLine("[GUI] Root Watch Folder updated to: \(selectedURL.path)")
        }
    }
}
