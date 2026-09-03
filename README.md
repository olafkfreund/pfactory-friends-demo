# MyFriends: a plan PFactory wrote, and the things it refused to let through

This repository is a public demonstration. It contains a real product brief for a
mobile app that does not exist, and everything [PFactory](https://github.com/olafkfreund/PFactory)
produced when asked to plan it.

The interesting output is not the plan. It is the list of things the brief did not
say.

## The question this answers

Anyone can get a language model to write a plausible project plan. The question a
buyer actually has is narrower and harder:

> If I hand this thing a real product brief, will it produce a plan I would be
> willing to sign my name to — including the parts I forgot to write down, and the
> parts that are the law?

MyFriends was chosen because it is unforgiving. It is a social app, so people can
reach each other. It is location-based, so it processes sensitive data. It ships
on the App Store and Google Play, so platform policy is a hard requirement rather
than an opinion. It launches in the UK, the EU and California, so three different
regulatory regimes apply at once. And it is open to 16 and 17 year olds, so
children's data rules are in scope from day one.

A planning tool that produces a clean, confident plan for MyFriends without
mentioning any of that is not being helpful. It is being dangerous.

## What is in here

| Path | What it is |
| --- | --- |
| `specs/myfriends.md` | The input. A product brief written the way a founder actually writes one. |
| `.factory/constitution.md` | The customer's own engineering policy. PFactory reads this and turns the clauses marked enforceable into hard gates. |
| `docs/plan/` | The plan PFactory emitted, and every review finding with its citation. |
| `docs/audit/` | The governance record: source document, findings, human approval, signed task contract, verification verdict. |
| `lanes/swift-core/` | A minimal Swift package. Proof that the Swift verification lane actually executes. |
| `lanes/kotlin-core/` | A minimal Kotlin module. Proof that the Kotlin verification lane actually executes. |

## The brief is deliberately incomplete

`specs/myfriends.md` is not a strawman, and it is not padded with mistakes. It is
a competent brief: twelve concrete, testable acceptance criteria, a named stack,
named launch markets, and an explicit statement that location is only read in the
foreground.

What it never mentions is how long any of the data is kept, how a person deletes
their account, how the app knows whether someone is 16 or 26, or what happens
after a person taps "report". Those omissions are the point. They are exactly the
omissions real briefs contain, because they are not features anyone is excited to
build.

The customer's own constitution, sitting in `.factory/constitution.md`, forbids
all four. So the demo is not a machine second-guessing a human. It is a machine
holding a human to a policy the human wrote.

## What the factory does with it

PFactory ingests the brief, decomposes it, and runs it through review lenses in
parallel — architecture, security, feasibility, best practices, completeness, an
adversarial red team, and a compliance lens that reads the brief for the classes
of data it implies. Every finding that asks for a change has to cite a source the
engineer can go and read. A finding without a citation is not allowed to demand
anything.

One human approves. The approval is bound to a hash of the plan, so changing the
plan invalidates the signature rather than silently carrying it forward.

The approved plan becomes a signed task contract that AIFactory builds against
and TFactory verifies against, so an obligation raised during review travels all
the way to the test suite instead of stopping at a document.

## The honest part

MyFriends is native Swift and native Kotlin, and this fleet runs on Linux.

**Kotlin verifies.** Android builds are Linux-native, and the lane runs here for
real: `gradle test` on `lanes/kotlin-core` reports `tests=2 failures=0 errors=0`
in its JUnit XML. Not "BUILD SUCCESSFUL" — the actual count, because a Gradle
build that collects zero tests prints the same success line.

**Swift half-verifies, and we say which half.** `swift build` compiles both the
library and the test target. `swift test` does not run at all: the nixpkgs Swift
5.10.1 toolchain is missing `libIndexStore.so`, which test discovery requires. The
full sequence of attempts, and the check confirming the library is absent from the
Nix store rather than merely off the search path, is in
[`lanes/swift-core/NOTES.md`](lanes/swift-core/NOTES.md).

**SwiftUI tests, the iOS simulator, `xcodebuild` and the `.ipa` do not run at
all.** They require macOS, and there is no macOS machine in this fleet. There
never was.

So each of those lanes is reported as **not run, with its specific reason
attached**. None is marked passed, and none is quietly left out of the report.
That behaviour is not a gap in the demo — it is the single most important thing in
it. A verification system that cannot say "I did not check this" is a verification
system whose green ticks mean nothing.

It would have been easy to write this section claiming Swift works, and to be
wrong. The first draft did. It was corrected because the command was actually run.

## Reproducing it

The plan in `docs/` was produced by the commands recorded in `docs/plan/RUN.md`,
against the live PFactory API. Nothing here was written by hand after the fact.

## Licence

The brief, the constitution and the emitted artefacts are published so they can be
read, quoted and argued with. The app does not exist.
