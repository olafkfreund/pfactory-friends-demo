---
status: draft
issue: 87
spec: spec/2026-09-30-87-myfriends-web.md
---

# Plan: MyFriends as a deployed web application

## Approved decisions (self-contained)

- **Why.** The first iteration produced a correct Kotlin library and nothing
  anyone can open, and only the `unit` lane ran — `api`, `integration` and
  `browser` stayed pending because a library exposes nothing to call or click.
- **FastAPI + Postgres + React/TypeScript**, deployed into the `factory`
  namespace and published at `myfriends.freundcloud.org.uk` behind the same
  oauth2-proxy that fronts CFactory. Auth is real Keycloak: the rules are about
  who may see and contact whom.
- **One implementation of the rules.** The backend owns them; `lanes/kotlin-core`
  stays as the historical artefact proving the Kotlin lane executes and stops
  being a second source of truth. Blocking is one `may_contact(a, b)` predicate
  used by discovery, requests and messaging alike, so the paths cannot disagree
  the way #86 did.
- **Done means four things at once**: tests pass, it is deployed, the URL serves
  it, and a browser drove the real deployment. Any one alone is the failure this
  iteration exists to remove.
- **The browser lane must be able to fail.** With the block check reverted, the
  Playwright flow must go red — a browser test that passes against broken code
  is what this is meant to prove we do not ship.
- **No real personal data, ever.** The app is about handling personal data
  correctly; putting real data in it is the one unacceptable shortcut.

## Steps

Ordered so something is showable early rather than everything landing at once.

1. **Walking skeleton, deployed.** `app/api` with one real endpoint (`GET
   /healthz` and `GET /profiles/me`), `app/web` with one screen that calls it,
   a Dockerfile each, a Deployment + Service, and the hostname added to the
   cloudflared ConfigMap.
   → verify: the deploy lane succeeds; `kubectl rollout status` is complete; an
   HTTP probe **from outside the cluster** returns the app through the proxy.
   This step alone is showable, and it retires the deployment risk first.
2. **Schema and persistence.** Postgres tables for profiles, connections,
   messages, blocks, reports; migrations; credentials from a cluster secret,
   nothing in the repository.
   → verify: migrations run against a real Postgres in CI, not a fake.
3. **The rules, with `may_contact` first.** Eligibility, discovery, requests,
   messaging, blocking, reports — each an endpoint with tests.
   → verify: blocking is symmetric across all three surfaces.
   **Mutation:** revert `may_contact` to a one-directional check; the test must
   fail. This is #86, fixed by construction.
4. **Compliance behaviours.** Age-bracket isolation, age assurance before
   discovery eligibility, the report queue with three outcomes and a notified
   result, retention figures enforced in code, deletion reporting what it
   removed and what it retained, coarse location never persisted past its query.
   → verify: each has a test that fails without it; retention and deletion run
   against real Postgres.
5. **The UI flows.** Profile, availability toggle, discovery list, request,
   accept, message, block, report — enough to perform the brief, no more.
   → verify: frontend typecheck and component tests pass.
6. **Playwright against the deployed URL.** Sign in through Keycloak, then the
   full flow: create profile, toggle availability, discover, request, accept,
   message, block, confirm the block holds **both ways**, report, see the
   outcome.
   → verify: it runs against `https://myfriends.freundcloud.org.uk`, not a local
   dev server. **Mutation:** revert the block check and this flow must go red.
7. **Run it through the factory.** The brief through PFactory, the contract to
   AIFactory, verification by TFactory — the pipeline this repository exists to
   demonstrate, now with three lanes that can actually execute.
   → verify: `api`, `integration` and `browser` all report, not `pending`.
8. **Gates:** ruff, ruff format, pytest, the frontend typecheck and tests, and
   `ratchet_lint.py` where it applies.
9. **PR** carrying the deploy evidence and the Playwright run; close #87.

## Sequencing note

Step 7 depends on **TFactory#1341**. Until it lands, a verification run rejects
every generated test when any one fails, so the browser tests would be discarded
wholesale and the run would report `triaged_empty`. Steps 1–6 do not depend on
it and produce their own evidence directly; step 7 is what turns that into a
factory-run demonstration.

## Tests

```sh
# api
apps/api/.venv/bin/python -m pytest tests/ -q
apps/api/.venv/bin/ruff check app tests
# web
npm --prefix app/web run typecheck && npm --prefix app/web test
# deployed
curl -sSf https://myfriends.freundcloud.org.uk/healthz
npx playwright test --config app/web/playwright.deployed.config.ts
```

Expected: each new test fails before its step and passes after; both mutations
(one-directional `may_contact`, and the same revert seen through the browser)
fail loudly.

## Rollback

Revert the PR and remove the hostname from the tunnel ConfigMap, the Deployment
and the Service; drop the database. Nothing else in the repository depends on
the app — `lanes/kotlin-core` is untouched throughout, and the existing demo
artefacts under `docs/` describe the first iteration and stay accurate.
