// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "BRAWConverterGUI",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "BRAWConverterGUI", targets: ["BRAWConverterGUI"])
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "BRAWConverterGUI",
            dependencies: [],
            path: "Sources/BRAWConverterGUI"
        ),
        .testTarget(
            name: "BRAWConverterGUITests",
            dependencies: ["BRAWConverterGUI"],
            path: "Tests/BRAWConverterGUITests"
        )
    ]
)
