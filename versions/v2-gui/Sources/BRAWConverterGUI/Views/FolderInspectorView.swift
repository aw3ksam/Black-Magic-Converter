import SwiftUI
import AppKit

public struct FolderInspectorView: View {
    @ObservedObject var appState: AppState
    
    public init(appState: AppState) {
        self.appState = appState
    }
    
    public var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Text("Ingest & Processing Pipeline Hierarchy")
                    .font(.system(size: 12, weight: .bold))
                    .foregroundColor(.secondary)
                
                Spacer()
                
                Button(action: {
                    FolderManager.shared.revealInFinder(appState.rootFolder)
                }) {
                    HStack(spacing: 4) {
                        Image(systemName: "folder")
                        Text("Open Root in Finder")
                    }
                    .font(.system(size: 11))
                }
                .buttonStyle(.link)
            }
            .padding(.horizontal, 16)
            
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 12) {
                    ForEach(appState.subfolders) { folder in
                        FolderCardView(folder: folder)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 6)
            }
        }
    }
}

struct FolderCardView: View {
    let folder: SubfolderInfo
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: folder.iconName)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(colorForName(folder.colorName))
                
                Spacer()
                
                // File count badge
                Text("\(folder.fileCount) \(folder.fileCount == 1 ? "file" : "files")")
                    .font(.system(size: 10, weight: .bold))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(colorForName(folder.colorName).opacity(0.15))
                    .foregroundColor(colorForName(folder.colorName))
                    .cornerRadius(4)
            }
            
            Text(folder.name)
                .font(.system(size: 13, weight: .bold, design: .monospaced))
                .foregroundColor(.primary)
            
            Text(folder.description)
                .font(.system(size: 10))
                .foregroundColor(.secondary)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
            
            Spacer(minLength: 4)
            
            Button(action: {
                FolderManager.shared.revealInFinder(folder.path)
            }) {
                HStack(spacing: 4) {
                    Image(systemName: "arrow.up.forward.app")
                    Text("Reveal in Finder")
                }
                .font(.system(size: 10, weight: .medium))
                .frame(maxWidth: .infinity)
                .padding(.vertical, 4)
                .background(Color(NSColor.separatorColor).opacity(0.2))
                .cornerRadius(4)
            }
            .buttonStyle(.plain)
        }
        .padding(10)
        .frame(width: 175, height: 135)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(10)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color(NSColor.separatorColor).opacity(0.4), lineWidth: 1)
        )
    }
    
    private func colorForName(_ name: String) -> Color {
        switch name {
        case "blue": return .blue
        case "orange": return .orange
        case "green": return .green
        case "purple": return .purple
        case "red": return .red
        default: return .gray
        }
    }
}
