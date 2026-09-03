# The Swift lane, and exactly how far it gets on Linux

This package exists to answer one question with evidence rather than opinion: can
this fleet, which runs on Linux, verify the Swift half of a native iOS app?

The answer as measured on 2026-09-03, against nixpkgs `swift` 5.10.1:

| Step | Result |
| --- | --- |
| `swift build` | **works** — both the library and the test target compile |
| `swift test` | **fails** — the toolchain is missing `libIndexStore.so` |
| SwiftUI / UIKit tests, iOS simulator, `xcodebuild`, `.ipa` | not attempted; these require macOS and there is no macOS machine in this fleet |

## What was tried, in order

Each step fixed the previous error and revealed the next, so the failure below is
not a missing flag or a wrong invocation.

1. `nix shell nixpkgs#swift -c swift test`

       swift: line 35: exec: swift-test: not found

   The nixpkgs `swift` attribute is the compiler and driver only. SwiftPM is a
   separate derivation, `swiftpm`.

2. Adding `swiftpm`:

       error: 'swift-core': Invalid manifest ...
       swift-core-manifest: error while loading shared libraries: libdispatch.so:
       cannot open shared object file: No such file or directory

   The manifest is compiled and executed, so libdispatch has to be on the runtime
   library path.

3. A `mkShell` carrying `swiftPackages.{swift, swiftpm, Dispatch, Foundation, XCTest}`
   with those libraries on `LD_LIBRARY_PATH`. `XCTest` now resolves and **both
   targets compile**:

       [4/15] Compiling MyFriendsCore MatchScore.swift
       [8/18] Compiling MyFriendsCoreTests MatchScoreTests.swift

   Then test discovery fails:

       error: open("/nix/store/...-swift-5.10.1-lib/lib/libIndexStore.so:
       cannot open shared object file: No such file or directory")
       [10/19] .../MyFriendsCorePackageDiscoveredTests.derived/all-discovered-tests.swift
       error: fatalError

4. `swift test --disable-index-store` fails identically.

5. The library is genuinely absent, not merely unfound:

       $ ls /nix/store/...-swift-5.10.1-lib/lib/
       swift
       libswiftDemangle.so

       $ find /nix/store -maxdepth 3 -name 'libIndexStore.so*' -path '*swift*'
       (no output)

## Why this is in the demo rather than hidden

A verification system that cannot say "I did not check this" produces green ticks
that mean nothing. The Swift unit lane is therefore declared unavailable **with
this reason attached**, and any plan that depends on it is marked as unverified at
that level rather than passed.

The alternative — quietly omitting the lane, or letting the absence of failures
read as success — is the specific failure this fleet has spent months rooting out.
An empty measurement and a clean pass must not look the same.

## A note on reading exit codes

Every command above was piped to `tail`. A shell pipeline reports the exit status
of its **last** stage, so all of these runs reported success while failing. The
real status came from `PIPESTATUS`. If you reproduce this, capture it, or you will
record a failure as a pass.
