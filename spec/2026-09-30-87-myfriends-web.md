---
status: draft
issue: 87
intent: intent/2026-09-30-87-myfriends-web.md
---

# Spec: MyFriends as a deployed web application

## What the measurements settled

| Question | Measured answer |
| --- | --- |
| Can the fleet deploy an app? | **Yes.** `run_deploy_lane_via_nix` exists in TFactory, and RFC-0013 deployment-aware planning is live. |
| Can it be published? | **Yes.** One cloudflared tunnel already serves 11 hostnames on `freundcloud.org.uk`; a twelfth is a ConfigMap entry. There is no ingress controller — the tunnel is the only route in. |
| Can a browser flow be tested? | **Yes.** `frameworks/playwright`, `frameworks/cypress` and `frameworks/portal-ui` all exist, and the portal-UI harness is proven against real portals behind Keycloak. |
| Are the toolchains there? | **Yes.** `python` and `typescript`/`node` are both in `_LANG_ATTRS`; the pytest and jest lanes are the fleet's most exercised. |
| Why not the native clients? | iOS needs macOS, which this fleet does not have, and no Swift lane exists (TFactory#1340). Android has no SDK in any toolchain and no emulator. |

## Design

### Shape

Two deployables in this repository, beside the existing `lanes/`:

- **`app/api`** — FastAPI over Postgres. Owns every rule: eligibility,
  discovery, requests, messaging, blocking (**both directions**), reports and
  their moderation queue, age assurance, retention and deletion.
- **`app/web`** — a small React/TypeScript UI over that API. Enough screens to
  perform the brief's flows: profile, availability toggle, discovery list,
  request, accept, message, block, report.

Deployed into the `factory` namespace, published at
`myfriends.freundcloud.org.uk` behind the same oauth2-proxy that fronts
CFactory.

### The rules live in one place

The backend is the single implementation. `lanes/kotlin-core` stays in the
repository as the historical artefact it is — evidence the Kotlin lane executes
— and stops being a second source of truth for the rules. Two implementations of
one compliance rule is exactly the shape that produced #86, where the messaging
path and the connection-request path disagreed about what "blocked" means.

The rules are ported as **specification**, not code: each becomes a FastAPI
handler with its own tests, and the Kotlin tests are read as the description of
intended behaviour. #86's bidirectional block is fixed by construction — one
`may_contact(a, b)` predicate used by requests and messages alike, so the two
paths cannot drift again.

### What "done" means

Four things true at once, each with its own evidence:

1. **Tests pass** — pytest for the API, jest/vitest for the UI.
2. **It is deployed** — the deploy lane reports success against the cluster.
3. **The URL serves it** — an HTTP probe of the published hostname returns the
   app, not a 502.
4. **A browser drove it** — Playwright performs the flows end to end against the
   deployed instance, not a local dev server.

Any one of those alone is the failure mode this iteration exists to avoid.

### Compliance, carried forward

Each rule the gate refused the original brief over becomes an API behaviour with
a test, not a paragraph:

- age-bracket isolation — an adult and a minor are never mutually discoverable;
- age assurance recorded before discovery eligibility;
- blocking symmetric across discovery, requests **and** messaging;
- reports with a fixed reason set, a queue, three outcomes and a notified result;
- retention figures enforced in code (messages 24 months, blocks/reports 24
  months after closure, everything else within 30 days of deletion);
- deletion that reports what it removed and what it retained;
- coarse location never persisted beyond the query that used it.

## Alternatives rejected

- **Kotlin/Ktor backend reusing the core directly.** Reuses tested rules, and
  puts the demo on the fleet's least-exercised JVM service path; the Maven and
  Gradle lanes are new (#1321, #1712) and unit-only.
- **Keep the Kotlin core as the rules engine, called over a boundary.** Two
  deployables, a serialisation layer, and the drift risk that produced #86.
- **In-memory persistence.** Trivially deployable; makes retention and deletion
  criteria unverifiable, which are the ones that mattered to the gate.
- **A stubbed login.** Faster, and it hollows out every criterion about who may
  see or contact whom.
- **Publishing it unauthenticated.** A fictional social product on a real
  domain, indexable, with a working message box. The oauth2-proxy already exists.
- **A static mock-up with no backend.** Showable tomorrow, proves nothing about
  the pipeline, and cannot fail a compliance gate.

## Risks

- **Scope.** This is materially larger than the library: two deployables, a
  database, auth, a deployment and a hostname. The plan must sequence it so an
  early step is already showable, rather than everything landing at once.
- **The verification may still discard its own output.** TFactory#1341 is in
  flight; until it lands, a run's browser tests are rejected wholesale when any
  single test fails. Sequencing must account for that — it is the difference
  between evidence and `triaged_empty`.
- **Auth makes browser testing harder.** The portal-UI harness already drives
  Keycloak logins, so this is a known cost rather than an unknown.
- **A public hostname serving fictional personal data.** Login-gated, clearly
  labelled as a demo, and no real personal data at any point — the app is about
  handling personal data correctly, which makes putting real data in it the one
  unacceptable shortcut.
- **Secrets.** Database credentials and OIDC client secrets come from cluster
  secrets; nothing in the repository, and the repository is public.

## Verification

1. API unit and integration tests, per rule, including the symmetry of blocking
   that #86 got wrong. **Mutation:** revert `may_contact` to a one-directional
   check and the test must fail.
2. Retention and deletion tested against a real Postgres, not a fake.
3. The deploy lane reports success, and `kubectl` shows the rollout complete.
4. An HTTP probe of `https://myfriends.freundcloud.org.uk` returns the app
   through the proxy — checked from outside the cluster.
5. Playwright drives the full flow against that deployed URL: sign in, create a
   profile, toggle availability, discover, request, accept, message, block,
   confirm the block holds in both directions, report, see the outcome.
6. **The browser lane must be able to fail**: with the block check reverted, the
   Playwright flow must go red. A browser test that passes against broken code
   is the thing this iteration is supposed to prove we do not ship.

Gates: ruff, ruff format, the pytest suite, the frontend typecheck and its
tests, and `ratchet_lint.py` where it applies.
