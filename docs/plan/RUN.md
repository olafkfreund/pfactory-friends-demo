# How the artefacts in this repository were produced

Nothing under `docs/` was written by hand. Every file is the output of a command
recorded here, run against the live PFactory API.

## Prerequisites

    BASE=https://pfactory.freundcloud.org.uk
    TOKEN=<the shared APP_API_TOKEN>

PFactory sits behind Cloudflare, which rejects the default Python user agent. Send
a normal one on every call. curl's default is fine.

## 1. Ingest the brief

    curl -s -A "Mozilla/5.0" -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -X POST "$BASE/api/plan/sessions/ingest-text" \
      -d @ingest.json

where `ingest.json` carries the title, the category, and the full text of
`specs/myfriends.md`. The response returns a `session_id`.

The brief must contain an `## Acceptance Criteria` section with bullet items.
PFactory's parser rejects a document without one rather than guessing.

## 2. Run the pipeline

    curl -s -A "Mozilla/5.0" -H "Authorization: Bearer $TOKEN" \
      -X POST "$BASE/api/plan/sessions/$SID/process"

This enriches the plan, decomposes it into an epic and child issues, runs the
feasibility stage, and scores it through every review lens. The response is the
scoreboard plus every finding with its citations.

Gates pass only when **every** lens individually clears the threshold and no lens
carries a blocking finding. The mean score across lenses is recorded for humans
and plays no part in the verdict.

## 3. Human approval

    curl -s -A "Mozilla/5.0" -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -X POST "$BASE/api/plan/sessions/$SID/approve" \
      -d '{"approver":"<name>"}'

The approval is bound to the plan's content hash. Editing the plan afterwards
invalidates it rather than carrying the signature forward.

## 4. Emit the signed contract

    curl -s -A "Mozilla/5.0" -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -X POST "$BASE/api/plan/sessions/$SID/emit-contract" \
      -d '{"repo":"olafkfreund/pfactory-friends-demo","project_id":"<pid>","dry_run":false}'

A response containing `"fallback": true` means the signed contract was **rejected**
and the downstream service re-planned from scratch. That is a failure to
investigate, not a success.

## 5. Export the audit pack

    curl -s -A "Mozilla/5.0" -H "Authorization: Bearer $TOKEN" \
      "$BASE/api/plan/sessions/$SID/audit-pack?format=markdown"

## Running the verification-lane fixtures yourself

Kotlin, on Linux:

    cd lanes/kotlin-core
    nix shell nixpkgs#gradle nixpkgs#jdk21 -c gradle test --no-daemon --console=plain

Read `build/test-results/test/*.xml` afterwards and check the `tests=` attribute.
"BUILD SUCCESSFUL" with zero tests collected looks identical to a real pass in the
console output, and is not one.

Swift, on Linux — see `lanes/swift-core/NOTES.md` for the current state of that
lane and exactly what does and does not work off macOS.
