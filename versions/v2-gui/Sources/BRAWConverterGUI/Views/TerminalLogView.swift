import SwiftUI
import AppKit

public struct TerminalLogView: View {
    @ObservedObject var appState: AppState
    @State private var autoScroll: Bool = true
    
    public init(appState: AppState) {
        self.appState = appState
    }
    
    public var body: some View {
        VStack(spacing: 0) {
            // Console Toolbar Header
            HStack {
                HStack(spacing: 6) {
                    Circle().fill(Color.red.opacity(0.8)).frame(width: 10, height: 10)
                    Circle().fill(Color.yellow.opacity(0.8)).frame(width: 10, height: 10)
                    Circle().fill(Color.green.opacity(0.8)).frame(width: 10, height: 10)
                    
                    Text("Live Engine Terminal & Ingest Log Stream")
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                        .foregroundColor(.gray)
                        .padding(.leading, 6)
                }
                
                Spacer()
                
                Toggle("Auto-scroll", isOn: $autoScroll)
                    .toggleStyle(.checkbox)
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
                
                Button(action: copyLogsToClipboard) {
                    HStack(spacing: 4) {
                        Image(systemName: "doc.on.doc")
                        Text("Copy")
                    }
                    .font(.system(size: 11))
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
                
                Button(action: { appState.clearLogs() }) {
                    HStack(spacing: 4) {
                        Image(systemName: "trash")
                        Text("Clear")
                    }
                    .font(.system(size: 11))
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(Color(red: 0.12, green: 0.13, blue: 0.15))
            
            Divider().background(Color.black)
            
            // Console Scroll Area
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 3) {
                        if appState.logs.isEmpty {
                            Text("Ready. Background logs and transcode events will stream here live...")
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundColor(.gray)
                                .padding(12)
                        } else {
                            ForEach(appState.logs) { entry in
                                LogRowView(entry: entry)
                                    .id(entry.id)
                            }
                        }
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .background(Color(red: 0.08, green: 0.09, blue: 0.10))
                .onChange(of: appState.logs.count) { _ in
                    if autoScroll, let last = appState.logs.last {
                        withAnimation(.easeOut(duration: 0.15)) {
                            proxy.scrollTo(last.id, anchor: .bottom)
                        }
                    }
                }
            }
        }
        .cornerRadius(10)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color.gray.opacity(0.2), lineWidth: 1)
        )
        .padding(.horizontal, 16)
        .padding(.bottom, 14)
    }
    
    private func copyLogsToClipboard() {
        let allText = appState.logs.map { $0.rawText }.joined(separator: "\n")
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(allText, forType: .string)
    }
}

struct LogRowView: View {
    let entry: LogEntry
    
    var body: some View {
        HStack(alignment: .top, spacing: 6) {
            Text(entry.rawText)
                .font(.system(size: 11, design: .monospaced))
                .foregroundColor(colorForLine(entry.rawText))
                .textSelection(.enabled)
        }
    }
    
    private func colorForLine(_ text: String) -> Color {
        if text.contains("[ERROR]") {
            return Color(red: 1.0, green: 0.4, blue: 0.4)
        } else if text.contains("[WARNING]") {
            return Color(red: 1.0, green: 0.8, blue: 0.2)
        } else if text.contains("[GUI]") {
            return Color(red: 0.6, green: 0.8, blue: 1.0)
        } else if text.contains("Transcode Progress:") || text.contains("Render completed") {
            return Color(red: 0.4, green: 0.9, blue: 0.5)
        } else if text.contains("File stabilized") || text.contains("Discovered new candidate") {
            return Color(red: 0.5, green: 0.9, blue: 1.0)
        } else {
            return Color(red: 0.85, green: 0.87, blue: 0.90)
        }
    }
}
