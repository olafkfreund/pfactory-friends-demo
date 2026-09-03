# The "before" run

Before any of the mobile or compliance work described in the README, the
MyFriends brief was put through PFactory exactly as it shipped, so the demo has an
honest starting point rather than a claimed one.

Session `011-myfriends`, PFactory 0.6.16, 2026-09-03. The brief parsed cleanly:
twelve acceptance criteria in, fourteen child issues out, in 3.5 seconds.

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

## The constitution is read, and it changes nothing

A first attempt passed the target repository to `/process`, where the parameter
is silently ignored — it belongs on `/ingest-text`. Without it the run is
greenfield, nine checks return `not_applicable` and the policy below is never
read at all. Corrected, reconnaissance executes and the repository's own policy
is picked up:

    constitution-grounded -> pass
    18 principle(s); 7 enforced as HARD checks (P1.2, P2.1, P3.1, P4.1, P5.1, P6.1, P7.1)

Those seven clauses require a stated retention period for anything held about a
person, in-app account deletion built alongside the feature that creates the
data, a stated age-assurance mechanism for anything a minor can reach, location
read only with explicit consent at minimum precision, blocking and reporting and
a response path on any person-to-person surface, named jurisdictions, and no
claiming a verification lane that did not run.

The brief satisfies **none of them**. The review output is byte-for-byte the same
three findings, the same scores, the same verdict. Readiness improves to eleven
passing and six not applicable, and `constitution-grounded` reports `pass`.

So the customer's own written policy is parsed, hash-bound to the plan, and shown
to the approver as "7 enforced as HARD checks" — and not one of the seven
produces a finding. The machinery to carry a policy end to end already works.
What is missing is the thing that reads the plan against it.

## Two more things the run reveals

- `plan_type` came out as **feature**. There is no mobile plan type to select,
  and this brief does not even reach `software-service`.
- `target_language` came out as **None**. The brief names Swift and Kotlin in
  prose. `TargetKind` is `software | non-software | undetermined` — there is no
  platform axis in the model at all.

## And the decomposition is heuristic, not reasoned

`decompose_method: heuristic`. The default pipeline is entirely deterministic:
the process route injects no model, so the prompt builder that would inject the
constitution into planning is never called. That is not a criticism — a
deterministic gate is reproducible, auditable and free, which is exactly what a
governance layer should be. But it does mean the constitution's only live effect
today is its appearance in the readiness report, and that anything intended to
influence the plan has to be code, not a prompt.

## Six of seventeen readiness checks examined nothing

The readiness gate ran seventeen checks. Eleven passed. The other six returned
`not_applicable`, and five of those are marked `hard`:

| Check | hard | Reason given |
| --- | --- | --- |
| service-requirements-covered | yes | Not a deployable software service — runtime ACs don't apply |
| access-granted | yes | No access requirements were derived for this plan |
| env-buildable | yes | No local-cluster probe ran for this plan |
| deployment-pipeline-present | yes | No deployment dimension — nothing to ship |
| enrichment-integrity | yes | No infra adapters ran (disabled / air-gapped) |
| access-verified | no | No access requirements were derived for this plan |

Each of those is a defensible individual answer, and to the gate's credit each
one states its reason rather than passing silently. But five hard checks in a row
concluding that they had nothing to look at is the shape of problem this project
has spent a long time learning to distrust: in a summary, a gate that passed
because it examined nothing is indistinguishable from a gate that examined
something and found it clean.

## Why publish the bad run

Because the "after" is only worth something next to it, and because a demo that
only shows the good run is a brochure.
