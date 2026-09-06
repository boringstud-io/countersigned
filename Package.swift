// swift-tools-version: 5.9
import PackageDescription

// At the repository root, not in swift/: SwiftPM resolves a package by cloning a
// repository and reading Package.swift from its top level. A manifest one
// directory down cannot be added from Xcode or referenced by URL at all — the
// sources stay where they are, the manifest points at them.
let package = Package(
    name: "Countersigned",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "Countersigned", targets: ["Countersigned"]),
    ],
    targets: [
        .target(name: "Countersigned", path: "swift/Sources/Countersigned"),
        // The vectors are NOT copied in as a resource: the tests read the file at
        // the repository root through #filePath, so Swift and Python read the same
        // bytes. A copy would drift, and a drifting contract is no contract.
        .testTarget(name: "CountersignedTests", dependencies: ["Countersigned"],
                    path: "swift/Tests/CountersignedTests"),
    ]
)
