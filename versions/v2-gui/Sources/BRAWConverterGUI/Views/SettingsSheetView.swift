import SwiftUI

public struct SettingsSheetView: View {
    @ObservedObject var appState: AppState
    @Environment(\.dismiss) var dismiss
    
    public init(appState: AppState) {
        self.appState = appState
    }
    
    public var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            // Header
            HStack {
                Text("Transcode & LUT Settings")
                    .font(.system(size: 16, weight: .bold))
                
                Spacer()
                
                Button("Done") {
                    dismiss()
                }
                .keyboardShortcut(.defaultAction)
            }
            
            Divider()
            
            Form {
                Section(header: Text("Color Management & 3D LUT").font(.headline)) {
                    Picker("Blackmagic 3D LUT:", selection: $appState.config.selectedLUT) {
                        ForEach(TranscodeConfigModel.availableLUTs) { lut in
                            Text(lut.name).tag(lut)
                        }
                    }
                    .pickerStyle(.menu)
                    
                    Text("The selected Blackmagic 3D LUT is automatically applied to Node 1 of each clip during transcode.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Section(header: Text("Video & Codec Configuration").font(.headline)) {
                    Picker("Output Format:", selection: $appState.config.container) {
                        Text("MP4 (.mp4)").tag("mp4")
                        Text("QuickTime (.mov)").tag("mov")
                    }
                    .pickerStyle(.segmented)
                    
                    Picker("Video Codec:", selection: $appState.config.codec) {
                        Text("H.265 / HEVC").tag("H265")
                        Text("H.264 / AVC").tag("H264")
                    }
                    .pickerStyle(.segmented)
                    
                    Picker("Encoding Profile:", selection: $appState.config.encodingProfile) {
                        Text("Main10 (10-bit HDR/Wide Color)").tag("Main10")
                        Text("Main (8-bit SDR)").tag("Main")
                    }
                    .pickerStyle(.menu)
                    
                    Picker("Resolution & Frame Rate:", selection: .constant("source")) {
                        Text("1:1 Source Preservation (6K->6K, 4K->4K, 1080p->1080p)").tag("source")
                    }
                    .disabled(true)
                }
                
                Section(header: Text("Audio Configuration").font(.headline)) {
                    HStack {
                        Text("Audio Codec:")
                        Spacer()
                        Text("AAC Stereo 48kHz (320 kbps)")
                            .foregroundColor(.secondary)
                    }
                }
            }
            .formStyle(.grouped)
            
            Spacer()
        }
        .padding(20)
        .frame(width: 520, height: 480)
    }
}
