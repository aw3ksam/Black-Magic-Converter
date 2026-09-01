import SwiftUI

public struct MainWindowView: View {
    @StateObject private var appState = AppState()
    @State private var showSettings: Bool = false
    
    public init() {}
    
    public var body: some View {
        VStack(spacing: 12) {
            // Top Status & Header Bar
            HeaderStatusView(appState: appState, showSettings: $showSettings)
            
            // 5-Folder Visual Pipeline Inspector
            FolderInspectorView(appState: appState)
            
            // Active Transcode Progress Indicator
            TranscodeProgressBarView(appState: appState)
            
            // Live Terminal Console Stream
            TerminalLogView(appState: appState)
        }
        .frame(minWidth: 780, minHeight: 620)
        .sheet(isPresented: $showSettings) {
            SettingsSheetView(appState: appState)
        }
    }
}
