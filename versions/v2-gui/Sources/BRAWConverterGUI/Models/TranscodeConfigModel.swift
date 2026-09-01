import Foundation

public struct BlackmagicLUTOption: Identifiable, Hashable {
    public let id: String
    public let name: String
    public let relativePath: String
}

public class TranscodeConfigModel: ObservableObject {
    @Published public var selectedLUT: BlackmagicLUTOption
    @Published public var encodingProfile: String = "Main10" // Main10 or Main
    @Published public var container: String = "mp4"
    @Published public var codec: String = "H265"
    @Published public var videoQuality: String = "Best"
    @Published public var bitrateMbps: Int = 0 // 0 = Auto
    
    public static let availableLUTs: [BlackmagicLUTOption] = [
        BlackmagicLUTOption(
            id: "gen5_ext_video",
            name: "Blackmagic Gen 5 Film to Extended Video (Recommended)",
            relativePath: "Blackmagic Design/Blackmagic Gen 5 Film to Extended Video.cube"
        ),
        BlackmagicLUTOption(
            id: "gen5_video",
            name: "Blackmagic Gen 5 Film to Video (Rec.709 High Contrast)",
            relativePath: "Blackmagic Design/Blackmagic Gen 5 Film to Video.cube"
        ),
        BlackmagicLUTOption(
            id: "pocket6k_ext_video_v4",
            name: "Blackmagic Pocket 6K Film to Extended Video v4",
            relativePath: "Blackmagic Design/Blackmagic Pocket 6K Film to Extended Video v4.cube"
        ),
        BlackmagicLUTOption(
            id: "pocket6k_video_v4",
            name: "Blackmagic Pocket 6K Film to Video v4",
            relativePath: "Blackmagic Design/Blackmagic Pocket 6K Film to Video v4.cube"
        ),
        BlackmagicLUTOption(
            id: "pocket4k_ext_video_v4",
            name: "Blackmagic Pocket 4K Film to Extended Video v4",
            relativePath: "Blackmagic Design/Blackmagic Pocket 4K Film to Extended Video v4.cube"
        ),
        BlackmagicLUTOption(
            id: "film_ext_video_v4",
            name: "Blackmagic Film to Extended Video v4",
            relativePath: "Blackmagic Design/Blackmagic Film to Extended Video v4.cube"
        )
    ]
    
    public init() {
        self.selectedLUT = TranscodeConfigModel.availableLUTs[0]
    }
    
    /// Generates a YAML configuration string for the Python transcode bridge.
    public func generateYAML(forRootFolder rootFolder: URL) -> String {
        let ingest = rootFolder.appendingPathComponent("00_IN_INGEST").path
        let processing = rootFolder.appendingPathComponent("01_PROCESSING").path
        let completed = rootFolder.appendingPathComponent("02_COMPLETED_MP4").path
        let archive = rootFolder.appendingPathComponent("03_ARCHIVE_BRAW").path
        let failed = rootFolder.appendingPathComponent("99_FAILED").path
        
        return """
        storage:
          ingest_dir: "\(ingest)"
          processing_dir: "\(processing)"
          completed_dir: "\(completed)"
          archive_dir: "\(archive)"
          failed_dir: "\(failed)"

        watcher:
          poll_interval: 2.0
          stability_checks: 3
          stability_delay: 2.0
          extensions:
            - ".braw"
          include_sidecars: true

        transcode:
          container: "\(container)"
          codec: "\(codec)"
          encoding_profile: "\(encodingProfile)"
          video_quality: "\(videoQuality)"
          bitrate_mbps: \(bitrateMbps)
          resolution: "source"
          frame_rate: "source"
          audio:
            codec: "aac"
            sample_rate: 48000
            bit_depth: 16
            bitrate_kbps: 320
          color:
            mode: "lut"
            lut_path: "\(selectedLUT.relativePath)"
            fallback_lut_path: "Blackmagic Design/Blackmagic Film to Extended Video v4.cube"

        davinci:
          app_path: "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/MacOS/Resolve"
          auto_start_headless: true
          launch_timeout: 45
          project_name_prefix: "BRAW_GUI_Job"
          cleanup_projects_after_render: true
        """
    }
}
