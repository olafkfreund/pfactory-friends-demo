# The "after" run

Same brief. Same constitution. Same deterministic pipeline, no model involved.

Measured on all three changes merged together, because two individually green
branches can still produce a broken combination and only the merge shows it.

**Provenance of these numbers.** The before run in
[BASELINE.md](BASELINE.md) was measured against the live deployed service. The
numbers below were first measured locally on the three branches merged into one
tree, and have since been **re-measured against `origin/dev` at the merge commit
`177a0e8`** — every figure reproduced exactly, so what follows is the merged
code's behaviour rather than a projection from a local combination.

They are still not the *deployed* service: this fleet deploys from `main`, and
the change set currently sits on `dev`. When it reaches production this page will
be measured a third time, and any number that moves will be corrected here rather
than quietly edited.

## The scoreboard

| Lens | Before | After | Blocking |
| --- | --- | --- | --- |
| feasibility | 1.00 | 1.00 | no |
| architecture | 0.90 | 0.90 | no |
| security | 0.70 | 0.70 | no |
| **compliance** | not present | **0.00** | **yes** |
| best-practices | 1.00 | 1.00 | no |
| completeness | 1.00 | 1.00 | no |
| **red-team** | gated off | **0.85** | no |

    plan_type:      feature  ->  mobile-app
    gates_passed:   false    ->  false
    readiness:      11 pass, 6 not_applicable  ->  10 pass, 7 not_applicable, 1 FAIL

The verdict was already `false` before, and it was `false` on a false positive.
It is `false` now for five real reasons.

## What the compliance lens says

Eight findings, five of them blocking, each leading with the customer's own
constitution and citing the regulation second:

| Finding | Severity | Customer clause |
| --- | --- | --- |
| Location data handling not specified | high, blocking | P4.1 |
| User-to-user contact without trust and safety controls | high, blocking | P5.1 |
| No retention or deletion policy stated | high, blocking | P1.2 |
| Store distribution without in-app account deletion | high, blocking | P2.1 |
| No age assurance stated | high, blocking | P3.1 |
| Lawful basis and purpose limitation not stated | medium | — |
| Automated matching without profiling transparency | medium | — |
| Enforceable constitution clauses not machine-checked at plan time | info | P7.1 |

The age finding's first citation is the customer's own sentence — "any feature
reachable by someone under 18 must state its age-assurance" — with COPPA, the UK
Age Appropriate Design Code and GDPR Art. 8 behind it. The machine is not
inventing an obligation. It is holding the author to one they wrote.

## The finding that matters most is the one marked "info"

The before run reported this, and a human would reasonably have read it as
reassurance:

    constitution-grounded -> pass
    18 principle(s); 7 enforced as HARD checks (P1.2, P2.1, P3.1, P4.1, P5.1, P6.1, P7.1)

Nothing was checking any of the seven. "Enforced as HARD checks" described an
intention, not a measurement.

The lens now names the clause it cannot check at plan time. P7 is the
never-overclaim rule — "a verification lane that could not run is reported as not
run, with the reason" — and it belongs to the verification machinery downstream,
not to planning. So the count of enforced clauses now means something, because
the system says which one is outside its reach.

That is the constitution's own P7, applied to the code that reads P7.

## Jurisdictions: the check works in both directions

The published brief carries a `## Markets at launch` section naming the UK, the
EU and California, so P6.1 is satisfied and **no jurisdiction finding is raised**.
Strip that section and re-run the identical pipeline:

    published (has ## Markets at launch):  8 findings, 5 blocking, no jurisdiction finding
    silent   (markets stripped):           9 findings, 6 blocking, jurisdiction finding present

A gate that only ever accuses is not a gate, it is a rubber stamp facing the other
way. This one goes quiet when the obligation is met.

## The plan grew nine acceptance criteria nobody wrote

Selecting `mobile-app` brings the mobile implicit requirements with it:

    acceptance criteria: 12 -> 21  (+9)

Store listing and review policy. In-context permission prompts. Offline and
poor-network behaviour. Deep links from a cold start. Symbolicated crash
reporting. VoiceOver and TalkBack. App size and battery budgets. Staged rollout.
A forced-upgrade path.

Nine, not ten. The tenth — minimum supported OS versions — was **not** injected,
because the brief already says "minimum iOS 16" and "minimum API 29". The
injector recognised the criterion the author did write and did not duplicate it.

## Readiness now fails, and fails honestly

    no-blocking-findings    FAIL    hard=true

The chain runs end to end: the lens raises a blocking finding, the hard readiness
check refuses, and emission is blocked. Before, the same brief reached
`human_review` with nothing in its way but a mis-detected auth criterion.

`service-requirements-covered` also moved from `not_applicable` to `pass`, because
there is now a requirement set for mobile plans to cover. Under the old code that
check returned `not_applicable` for every mobile plan while reporting a clean
completeness score — a hard gate examining nothing, which is the failure this
whole exercise keeps finding.

## What has not changed, and should be said

`security` still scores 0.70 on a false positive: acceptance criterion 11 states
an authenticated API, and the lens's keyword pattern matches the nouns
`authentication` and `authorization` but not the participle. The red-team lens
carries a byte-identical copy of the same regex and produces the same wrong
finding. Filed as
[PFactory#670](https://github.com/olafkfreund/PFactory/issues/670); fixing one
copy would leave the other.

The decomposition is still heuristic. No model runs in this pipeline. Every number
above is reproducible and free.
