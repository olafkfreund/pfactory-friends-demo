# Product decisions

The plan for "Create Profile" left 13 items marked `DECISION REQUIRED` and 5
open questions marked blocking — the plan's own words were that they must be
answered before development starts. They were not, and the first acceptance
criterion built without them produced three behaviours nobody had chosen
(issue #36).

These are the answers. An issue in this repository inherits them: where an
acceptance criterion and this file disagree, this file is the requirement.

Decided 2026-09-08 by the product owner.

## The five blocking questions

| # | Question | Decision |
|---|---|---|
| 1 | Minimum age to create a profile | **16+** |
| 2 | Is a profile photo mandatory for MVP | **Mandatory** |
| 3 | Location precision shown to other users | **Town/city only** — never a distance, never coordinates |
| 4 | Are Interests and Activities/Hobbies one field or two | **Two separate fields** |
| 5 | Is an incomplete/draft profile visible to others | **Hidden until complete** |

### Notes that follow from these

**16+ (1).** 16- and 17-year-olds are children in law, so the ICO's Age
Appropriate Design Code applies to this service. Two of its standards cut
against features this app is built on: geolocation should default to off for
children, and profiling should default to off. This is a location-based app
with automated matching.

**This is a known and accepted gap, not an oversight.** It is recorded here so
that it is visible rather than discovered later. Closing it means age-gating
the features — under-18 accounts defaulting geolocation and matching-profiling
to off, with explicit opt-in — and that work is not in the current 33 issues.
Revisit before any public launch.

**Mandatory photo (2).** This reverses assumption A6 in the plan, which argued a
required photo is a signup barrier. Consequences: photo upload and validation
are on the critical path for every new profile, and a profile cannot be
complete — and therefore cannot be visible, per (5) — without one.

**Town/city only (3).** Chosen over distance bands because repeated distance
readings from different points can be trilaterated back to a home address. A
town/city label cannot. No exact coordinate may leave the backend
(this is NFR-002 in the plan).

**Two fields (4).** Keeps the plan's assumption A5. Each field needs its own
selection limits; those limits are still undecided (see below).

## Still undecided

These remain `DECISION REQUIRED`. Code that needs one should use a single named
constant, marked as a placeholder, and say so in its PR — the pattern used for
`MAX_DISPLAY_NAME_LENGTH` in PR #35.

- Maximum display name length, **and its unit** (see #36 — "50 characters" is
  ambiguous between code units, code points and grapheme clusters)
- Maximum "About Me" biography length
- Maximum age / plausibility upper bound
- Maximum number of interests selectable
- Maximum number of activities/hobbies selectable
- Minimum number required to count a profile as complete
- Supported profile photo formats and maximum file size
- Retention and handling of removed photos and edited-out data (constitution P1
  makes stating this mandatory for any feature that stores personal data)
- Permitted characters in a display name (see #36 — newlines are currently
  accepted)
