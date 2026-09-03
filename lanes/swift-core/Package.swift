// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "MyFriendsCore",
    products: [.library(name: "MyFriendsCore", targets: ["MyFriendsCore"])],
    targets: [
        .target(name: "MyFriendsCore"),
        .testTarget(name: "MyFriendsCoreTests", dependencies: ["MyFriendsCore"]),
    ]
)
