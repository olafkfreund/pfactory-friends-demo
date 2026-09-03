# The audit pack

`baseline-audit-pack.md` and `baseline-audit-pack.json` are the governance record
PFactory exported for session `011-myfriends`, unedited. Both are the same bundle
in two forms: the markdown is for reading, the JSON for machines.

## What it contains

The source document as ingested, the review-gate scoreboard with every finding and
its citations, and — where they exist — the human approval record, the signed task
contract, the completion timeline, and the verification verdict.

Each artefact is cross-referenced to the EU AI Act heading it may be relevant to:
technical documentation under Article 11 and Annex IV, risk management under
Article 9, human oversight under Article 14, record-keeping under Article 12.

## The disclaimer is the point, not the small print

The pack opens with this, and it is worth reading rather than skipping:

> The EU AI Act article/heading references are navigational labels indicating
> where each artifact may be relevant; they are NOT an assertion of EU AI Act
> conformity for the system, model, or plan. Conformity determinations require a
> qualified legal / conformity assessment. PFactory makes no conformity claim.

A tool that emits a document headed "EU AI Act" and lets the reader infer
compliance from it would be worse than useful. This one states what it is: an
evidence bundle, assembled from a real planning record, organised so a human
assessor can find things. The assessment remains a human's job.

## And it says what it does not have

The cross-reference table in this export reads:

| Artifact | Present |
| --- | --- |
| Honoured source document | yes |
| Review-gate findings and citations | yes |
| Human approval record | **no** |
| Signed Task Contract | **no** |
| Completion and correlation timeline | **no** |
| TFactory verification verdict | **no** |

Four of six are absent, because this session was processed and never approved,
emitted or built. The pack does not quietly omit those rows, and it does not
present four empty sections as though they were complete. It lists them and marks
them missing.

That is the same principle as the constitution's P7 and the verification lanes'
VAL-0: **an artefact that could not be produced is reported as absent, with the
reason, never as a blank that reads like a pass.** In a governance document that
distinction is the whole value — an auditor's first question is what is missing,
and a bundle that cannot answer it is decoration.

## Reproducing

    curl -s -A "Mozilla/5.0" -H "Authorization: Bearer $TOKEN" \
      "$BASE/api/plan/sessions/011-myfriends/audit-pack?format=markdown"

`format=json` returns the machine-readable form.

## What is not here yet

This is the **baseline** pack — the one produced before the mobile plan type and
the compliance lens landed. It records a plan scored by five lenses with three
findings, two of which were wrong.

The corresponding pack from the improved pipeline will be added once the change
set is merged and deployed, so the two can be read side by side. See
[../plan/AFTER.md](../plan/AFTER.md) for what that run produces.
