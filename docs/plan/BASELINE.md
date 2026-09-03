# The "before" run

Before any of the mobile or compliance work described in the README, the
MyFriends brief was put through PFactory exactly as it shipped, so the demo has an
honest starting point rather than a claimed one.

Session `010-myfriends`, PFactory 0.6.16, 2026-09-03. The brief parsed cleanly:
twelve acceptance criteria in, fourteen child issues out, in 0.58 seconds.

## The scoreboard

| Lens | Score | Blocking | Findings |
| --- | --- | --- | --- |
| feasibility | 1.00 | no | 0 |
| architecture | 0.90 | no | 1 |
| security | 0.70 | no | 1 |
| best-practices | 1.00 | no | 1 |
| completeness | 1.00 | no | 0 |

Gates did not pass, because every lens has to clear 0.75 individually and
security did not. The mean was 0.92 and played no part in that, which is correct
and worth saying plainly: this system does not average away a failure.

## The three findings, in full

1. **Vague titles** (low) — "Unclear titles on: epic."
2. **No authentication/authorization criteria** (medium) — "A software plan has no
   acceptance criterion covering auth."
3. **Golden-path guidance available** (info) — eight knowledge references
   surfaced, among them a NixOS service module and a COSMIC Desktop applet.

That is the complete output for a location-based social product, open to sixteen
year olds, launching in the UK, the EU and California.

## What is not in it

Nothing about personal data. Nothing about location being sensitive. Nothing
about minors or age assurance. Nothing about how long anything is kept or how a
person deletes it. Nothing about moderation, blocking or reporting obligations.
Nothing about App Store or Play policy. No mention of a jurisdiction.

## And two of the three findings are wrong

**Finding 2 is a false positive**, and it is the one that failed the gate.
Acceptance criterion 11 reads:

> The backend exposes the discovery, request, and messaging operations over an
> authenticated API, and rejects any unauthenticated call.

The lens's keyword pattern matches `authentication` and `authorization`, the
nouns, but its `\b` boundary means bare `auth` cannot match inside
`authenticated`, and neither participle is listed. So the most natural English
phrasing of an auth requirement reads as an absent one. Filed as
[PFactory#670](https://github.com/olafkfreund/PFactory/issues/670).

**Finding 3 is irrelevant.** A NixOS module and a desktop applet are not golden
paths for a native mobile app. The knowledge retrieval had nothing mobile to
offer, so it offered what it had.

## Three more things the run reveals

- `plan_type` came out as **feature**. There is no mobile plan type to select.
- `target_language` came out as **None**. The brief names Swift and Kotlin in
  prose; the pipeline did not carry that forward.
- `constitution_md` was **absent**. The repository's own
  `.factory/constitution.md` was never read, so the seven enforceable clauses the
  brief violates were never applied.

## Nine of seventeen readiness checks examined nothing

The readiness gate ran seventeen checks. Eight passed. The other nine returned
`not_applicable`, and four of those are marked `hard`:

| Check | hard | Reason given |
| --- | --- | --- |
| service-requirements-covered | yes | Not a deployable software service |
| access-granted | yes | No access requirements were derived |
| env-buildable | yes | No local-cluster probe ran |
| deployment-pipeline-present | yes | No deployment dimension |
| enrichment-integrity | yes | No infra adapters ran |
| language-reconciled | no | Greenfield, nothing to reconcile |
| constitution-grounded | no | No constitution found |
| change-footprint-surfaced | no | Greenfield |
| access-verified | no | No access requirements derived |

Each of those is a defensible individual answer. Together they are the shape of
problem this project has spent a long time learning to distrust: a gate that
passes because it looked at nothing is indistinguishable, in a summary, from a
gate that looked and found nothing wrong.

## Why publish the bad run

Because the "after" is only worth something next to it, and because a demo that
only shows the good run is a brochure.
