import XCTest
@testable import BRAWConverterGUI

final class FolderManagerTests: XCTestCase {
    var tempDirectory: URL!
    
    override func setUp() {
        super.setUp()
        tempDirectory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try? FileManager.default.createDirectory(at: tempDirectory, withIntermediateDirectories: true)
    }
    
    override func tearDown() {
        try? FileManager.default.removeItem(at: tempDirectory)
        super.tearDown()
    }
    
    func testValidateAndProvisionCreatesAllRequiredSubfolders() {
        let manager = FolderManager()
        let customRoot = tempDirectory.appendingPathComponent("MyCameraOffloadFolder")
        
        let subfolders = manager.validateAndProvision(rootFolder: customRoot)
        
        // Must contain all 5 required subdirectories
        XCTAssertEqual(subfolders.count, 5)
        
        let expectedNames = [
            "00_IN_INGEST",
            "01_PROCESSING",
            "02_COMPLETED_MP4",
            "03_ARCHIVE_BRAW",
            "99_FAILED"
        ]
        
        for name in expectedNames {
            let path = customRoot.appendingPathComponent(name).path
            XCTAssertTrue(FileManager.default.fileExists(atPath: path), "Folder \(name) should exist at \(path)")
        }
    }
    
    func testValidateAndProvisionPreservesExistingFiles() {
        let manager = FolderManager()
        let customRoot = tempDirectory.appendingPathComponent("ExistingMediaRoot")
        
        // Pre-create an archive folder with a file
        let archiveFolder = customRoot.appendingPathComponent("03_ARCHIVE_BRAW")
        try? FileManager.default.createDirectory(at: archiveFolder, withIntermediateDirectories: true)
        let sampleFile = archiveFolder.appendingPathComponent("Archived_Clip.braw")
        try? "DUMMY BRAW".write(to: sampleFile, atomically: true, encoding: .utf8)
        
        // Run validation
        let subfolders = manager.validateAndProvision(rootFolder: customRoot)
        
        // Verify that archive folder still contains the file
        let archiveInfo = subfolders.first(where: { $0.name == "03_ARCHIVE_BRAW" })
        XCTAssertNotNil(archiveInfo)
        XCTAssertEqual(archiveInfo?.fileCount, 1)
        XCTAssertTrue(FileManager.default.fileExists(atPath: sampleFile.path))
    }
    
    func testCustomRootNameFlexibility() {
        let manager = FolderManager()
        let arbitraryNameRoot = tempDirectory.appendingPathComponent("Custom_SSD_Project_2026")
        
        let subfolders = manager.validateAndProvision(rootFolder: arbitraryNameRoot)
        XCTAssertEqual(subfolders.count, 5)
        XCTAssertTrue(FileManager.default.fileExists(atPath: arbitraryNameRoot.path))
    }
}
