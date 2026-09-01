import Foundation
import AppKit

public struct SubfolderInfo: Identifiable {
    public let id: String
    public let name: String
    public let path: URL
    public var fileCount: Int
    public let description: String
    public let iconName: String
    public let colorName: String
}

public class FolderManager {
    public static let shared = FolderManager()
    
    public static let userDefaultsKey = "braw_root_watch_folder_path"
    
    public static let requiredFolderNames: [String] = [
        "00_IN_INGEST",
        "01_PROCESSING",
        "02_COMPLETED_MP4",
        "03_ARCHIVE_BRAW",
        "99_FAILED"
    ]
    
    private let folderMetadata: [String: (description: String, icon: String, color: String)] = [
        "00_IN_INGEST": ("Drop incoming camera BRAW footage here", "arrow.down.doc.fill", "blue"),
        "01_PROCESSING": ("In-flight files actively undergoing transcode", "gearshape.arrow.triangle.2.circlepath", "orange"),
        "02_COMPLETED_MP4": ("Finished H.265 MP4 exports at 1:1 resolution", "checkmark.rectangle.stack.fill", "green"),
        "03_ARCHIVE_BRAW": ("Original BRAW clips safely stored here after export", "archivebox.fill", "purple"),
        "99_FAILED": ("Quarantined clips that encountered an error", "exclamationmark.triangle.fill", "red")
    ]
    
    public init() {}
    
    /// Resolves the initial root watch folder from UserDefaults, falling back to a default sandbox path.
    public func resolveInitialRootFolder() -> URL {
        if let savedPath = UserDefaults.standard.string(forKey: FolderManager.userDefaultsKey),
           !savedPath.isEmpty {
            let url = URL(fileURLWithPath: savedPath)
            if FileManager.default.fileExists(atPath: url.path) {
                return url
            }
        }
        
        // Default to workspace watch_folders
        let currentDir = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        let defaultWatch = currentDir.appendingPathComponent("watch_folders")
        return defaultWatch
    }
    
    /// Persists root folder path in UserDefaults.
    public func saveRootFolder(_ url: URL) {
        UserDefaults.standard.set(url.path, forKey: FolderManager.userDefaultsKey)
    }
    
    /// Validates that all 5 required subdirectories exist inside the root folder.
    /// Missing folders are created safely; existing folders and archives are left completely untouched.
    @discardableResult
    public func validateAndProvision(rootFolder: URL) -> [SubfolderInfo] {
        let fm = FileManager.default
        
        // 1. Ensure root directory exists
        if !fm.fileExists(atPath: rootFolder.path) {
            try? fm.createDirectory(at: rootFolder, withIntermediateDirectories: true)
        }
        
        var subfolders: [SubfolderInfo] = []
        
        for name in FolderManager.requiredFolderNames {
            let subURL = rootFolder.appendingPathComponent(name)
            
            // Check if subfolder exists; if missing, create it
            if !fm.fileExists(atPath: subURL.path) {
                try? fm.createDirectory(at: subURL, withIntermediateDirectories: true)
            }
            
            // Count files in directory
            let count = countFilesInDirectory(subURL)
            let meta = folderMetadata[name] ?? ("Directory", "folder.fill", "gray")
            
            subfolders.append(SubfolderInfo(
                id: name,
                name: name,
                path: subURL,
                fileCount: count,
                description: meta.description,
                iconName: meta.icon,
                colorName: meta.color
            ))
        }
        
        return subfolders
    }
    
    /// Counts files (excluding .DS_Store and directories) in a folder.
    public func countFilesInDirectory(_ folder: URL) -> Int {
        let fm = FileManager.default
        guard let contents = try? fm.contentsOfDirectory(at: folder, includingPropertiesForKeys: [.isDirectoryKey], options: [.skipsHiddenFiles]) else {
            return 0
        }
        return contents.filter { url in
            let isDir = (try? url.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) ?? false
            return !isDir && url.lastPathComponent != ".DS_Store"
        }.count
    }
    
    /// Reveals a folder or file in macOS Finder.
    public func revealInFinder(_ url: URL) {
        NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: url.path)
    }
}
