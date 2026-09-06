// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Countersigned",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "Countersigned", targets: ["Countersigned"]),
    ],
    targets: [
        .target(name: "Countersigned"),
        // The vectors are NOT copied in as a resource: the tests read the file at
        // the repository root through #filePath, so Swift and Python read the same
        // bytes. A copy would drift, and a drifting contract is no contract.
        .testTarget(name: "CountersignedTests", dependencies: ["Countersigned"]),
    ]
)
