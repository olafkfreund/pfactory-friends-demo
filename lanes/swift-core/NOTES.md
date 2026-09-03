# The Swift lane on Linux: it works, and the way it fails is the interesting part

This package exists to answer one question with evidence rather than opinion: can
this fleet, which runs on Linux, verify the Swift half of a native iOS app?

**Yes, for library code.** Measured on 2026-09-03 against nixpkgs `swift` 5.10.1:

    Test Suite 'MatchScoreTests' started
    Test Case 'MatchScoreTests.testHalfTheInterestsOverlap' passed (0.001 seconds)
    Test Case 'MatchScoreTests.testEmptyInterestsScoreZeroRatherThanCrashing' passed
    Executed 2 tests, with 0 failures (0 unexpected)

and, with the implementation mutated to `return 1.0`:

    Executed 2 tests, with 1 failure (0 unexpected)

A lane that only ever passes proves nothing, so both directions were run.

SwiftUI and UIKit tests, the iOS simulator, `xcodebuild` and the `.ipa` remain
out of reach. They need macOS, and there is no macOS machine in this fleet.

## Getting there took four wrong answers

An earlier version of this file concluded the lane was impossible. That was
wrong, and the sequence matters, because each step fixed the previous error and
revealed the next.

1. `nix shell nixpkgs#swift -c swift test`

       swift: line 35: exec: swift-test: not found

   The nixpkgs `swift` attribute is compiler and driver only. SwiftPM is a
   separate derivation, `swiftpm`.

2. Adding `swiftpm`:

       Invalid manifest ... swift-core-manifest: error while loading shared
       libraries: libdispatch.so: cannot open shared object file

   The manifest is compiled and then executed, so libdispatch must be on the
   runtime library path before SwiftPM has even read `Package.swift`.

3. A shell carrying `swiftPackages.{swift,swiftpm,Dispatch,Foundation,XCTest}`
   with those libraries on `LD_LIBRARY_PATH`. Both targets now compile, and test
   discovery fails:

       error: open(".../swift-5.10.1-lib/lib/libIndexStore.so: cannot open
       shared object file: No such file or directory")
       [10/19] .../MyFriendsCorePackageDiscoveredTests.derived/all-discovered-tests.swift

   `swift test --disable-index-store` fails identically, and the library is
   absent from the entire Nix store, not merely off the search path.

4. **This is where the earlier conclusion stopped, and it was premature.**
   nixpkgs ships no `libIndexStore.so` (NixOS/nixpkgs#379859), so SwiftPM's
   *automatic* test discovery cannot work — but automatic discovery is not the
   only mechanism. The pre-5.4 convention still works: an explicit
   `Tests/LinuxMain.swift` plus `Tests/MyFriendsCoreTests/XCTestManifests.swift`
   listing the tests. Add those two files and `swift test` builds, runs, reports
   per-test results, and fails when the code is wrong.

The lesson is not about Swift. It is that "the obvious path is broken" and "the
capability is unavailable" are different claims, and the first was mistaken for
the second.

## The trap this leaves behind

A test that is not listed in `XCTestManifests.swift` **does not run, and nothing
says so.** Deleting one entry from the manifest and re-running:

    Test Suite 'All tests' started
    Executed 1 test, with 0 failures (0 unexpected)
    Test Suite 'All tests' passed
    exit 0

Green. Passing. Exit zero. One of the two tests simply was not there, and the
only trace is the count: `Executed 1 test` where it should say 2.

This is the exact failure this project keeps finding in other guises — a result
that passed because it examined less than it should have, wearing the same face
as one that examined everything. Anything generating Swift tests must emit the
manifest entry alongside every test it writes, and anything reading the result
must read the executed count, not the verdict.

## A note on reading exit codes

The failing runs above were piped to `tail`. A shell pipeline reports the exit
status of its **last** stage, so every one of them reported success while
failing. The real status came from `PIPESTATUS`. If you reproduce this, capture
it, or you will record a failure as a pass — which is how three of the four wrong
answers above nearly went unnoticed.

## Reproducing

    nix develop <shell with swift, swiftpm, Dispatch, Foundation, XCTest>
    swift test

The provisioning is declared in the Factory hub at
`contracts/languages/swift.yaml`, including the `LD_LIBRARY_PATH` requirement and
the manifest convention, so a generated flake carries both without anyone having
to rediscover the sequence above.
