import XCTest

// nixpkgs swift 5.10 ships no libIndexStore.so, so SwiftPM's automatic test
// discovery fails (NixOS/nixpkgs#379859). This manifest is the pre-5.4
// convention that replaces it. A test missing from this list silently does not
// run, so every new test must be added here.
extension MatchScoreTests {
    static let __allTests = [
        ("testHalfTheInterestsOverlap", testHalfTheInterestsOverlap),
        ("testEmptyInterestsScoreZeroRatherThanCrashing", testEmptyInterestsScoreZeroRatherThanCrashing),
    ]
}

public func __allDiscoveredTests() -> [XCTestCaseEntry] {
    return [testCase(MatchScoreTests.__allTests)]
}
