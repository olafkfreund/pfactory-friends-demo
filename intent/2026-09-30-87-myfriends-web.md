---
status: draft
issue: 87
author: olafkfreund
---

# Intent: MyFriends is an app you can open

## Problem

The first iteration produced a correct Kotlin domain library and nothing anyone
can look at. 12 source files, 259 passing tests, 11,436 lines — and no screen,
no URL, no running process.

That was my scoping decision, not a failure of the build: the brief I wrote said
"a plain Kotlin module … no Android framework, no UI, no network", chosen so the
deliverable was verifiable in-cluster. It proved the pipeline and left no
product.

Two consequences, both measured:

1. **Nothing to show.** The acceptance criteria are satisfied by pure functions.
   There is no artefact a person can be shown other than test output.
2. **Three quarters of the verification never ran.** The TFactory run executed
   the `unit` lane; `api`, `integration` and `browser` all stayed `pending`,
   because a library exposes nothing to call or click. So the strongest claim
   available today is "some pure functions pass their tests".

And the product as originally specified cannot close that gap here:

- **iOS**: SwiftUI and `xcodebuild` require macOS. There is no Mac in this
  fleet, and no Swift lane exists at all (TFactory#1340).
- **Android**: no Android SDK in `_LANG_ATTRS` and no emulator, so a build would
  produce an APK nothing could run.

## Proposed outcome

MyFriends is a running web application on the cluster: a backend API over the
domain rules and a browser UI over that API, published on a hostname, that a
person can open and use — create a profile, toggle availability, discover
people, send and accept a request, exchange messages, block, report.

"Done" means all four of these are true at once:
its tests pass, it is deployed, the URL serves it, and a browser-driven test
drove the real UI against the real deployment.

## Affected users and systems

- A new application in this repository (backend + frontend), alongside the
  existing `lanes/kotlin-core`, which stays as the reference implementation of
  the rules.
- PFactory's planner, AIFactory's build, and TFactory's `api`, `integration` and
  `browser` lanes — three of which have never run for this product.
- The cluster: a deployment, a service, and one hostname added to the existing
  cloudflared tunnel ConfigMap (which already publishes 11).
- Not the Kotlin core: it is not deleted or ported away. What happens to it is
  an open question below.

## Constraints

- **It must be genuinely deployed and reachable**, not "deployable in
  principle". A demo that needs a local `docker run` to see is the same failure
  as the library, one step further along.
- **The compliance rules survive.** Age-bracket isolation, the 30-day deletion
  path, retention periods, blocking in **both** directions (the defect found in
  the first iteration, #86), moderation with a response path, and the explicit
  refusal reasons are product requirements, not library details. They are what
  PFactory's compliance gate refused the original brief over.
- **No secrets in the repository.** A deployed app needs configuration and
  probably a database; those come from cluster secrets, never from committed
  files.
- **The verification must be honest.** A browser lane that loads a page and
  asserts nothing is worse than no browser lane. Passing means it drove the real
  flows against the real deployment.
- **It must not depend on fixes that have not landed.** TFactory#1341 is
  currently in flight; until it does, a verification run discards its own
  output, so the sequencing has to account for that rather than hope.

## Open questions

1. **Backend language: Python/FastAPI or Kotlin/Ktor?** Ktor reuses the existing
   domain core directly — the rules are already written, tested, and one of
   them was found wrong by independent verification, which is worth keeping.
   FastAPI is the fleet's most exercised path (pytest lane, api lane, deploy
   lane all heavily used) and the one least likely to hit a toolchain gap. My
   recommendation is **FastAPI, with the Kotlin core as the specification** of
   each rule rather than as a dependency: the demo's value is the governed
   pipeline, not code reuse, and a Ktor build is the riskier of the two here.
2. **Persistence: Postgres or in-memory?** In-memory is trivially deployable and
   makes retention and deletion criteria untestable in any meaningful way.
   Postgres exists in the cluster and makes the compliance ACs real. I lean
   Postgres, accepting it costs a migration path.
3. **Authentication: real or stubbed?** The brief requires an authenticated API
   and the rules are about *who* may see and contact *whom*, so a stub makes the
   central criteria unverifiable. Keycloak is already deployed and fronts
   CFactory. Using it is more setup; not using it weakens exactly what the
   compliance gate cared about.
4. **Does the Kotlin core stay?** Options: keep it as the reference and accept
   two implementations that can drift; port the backend to call it (only if
   Ktor); or retire it. Two sources of truth for a compliance rule is the shape
   that produced #86 in the first place.
5. **How public?** The tunnel publishes to the internet. A demo app holding
   fictional profile data is still a public service on a real domain — it may
   want the same oauth2-proxy front that CFactory has, or a robots exclusion, or
   simply a name that cannot be mistaken for a real product.
