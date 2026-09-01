import SwiftUI

public struct TranscodeProgressBarView: View {
    @ObservedObject var appState: AppState
    
    public init(appState: AppState) {
        self.appState = appState
    }
    
    public var body: some View {
        if appState.serviceState == .transcoding || appState.transcodeProgress > 0 {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Image(systemName: "film")
                        .foregroundColor(.blue)
                    
                    Text("Transcoding: \(appState.currentClipName ?? "Active Clip")")
                        .font(.system(size: 12, weight: .bold))
                        .lineLimit(1)
                    
                    Spacer()
                    
                    if appState.transcodeFps > 0 {
                        Text("\(String(format: "%.1f", appState.transcodeFps)) fps")
                            .font(.system(size: 11, weight: .semibold, design: .monospaced))
                            .foregroundColor(.secondary)
                    }
                    
                    Text("\(Int(appState.transcodeProgress * 100))%")
                        .font(.system(size: 12, weight: .bold, design: .monospaced))
                        .foregroundColor(.blue)
                }
                
                ProgressView(value: appState.transcodeProgress, total: 1.0)
                    .progressViewStyle(.linear)
                    .accentColor(.blue)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .background(Color.blue.opacity(0.08))
            .cornerRadius(8)
            .padding(.horizontal, 16)
        }
    }
}
