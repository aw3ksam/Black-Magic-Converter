import SwiftUI

@main
struct BRAWConverterGUIApp: App {
    var body: some Scene {
        WindowGroup {
            MainWindowView()
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified)
        .defaultSize(width: 820, height: 660)
    }
}
