# Engineering constitution

The governing principles for every plan and every build in this repository.
PFactory reads this file during planning, surfaces it for human approval, and
turns the clauses marked enforceable into hard checks.

Principles are numbered. A principle marked **(enforceable)** is not advice: a
plan that violates it does not pass the gates, and the only way past is a
recorded waiver with a named approver.

## P1: The person owns their data

- **P1 (enforceable):** every feature that stores information about a person must state how long it is kept and what deletes it. "Indefinitely" is an answer, but it has to be written down.

## P2: Deletion is a feature, not a support ticket

- **P2 (enforceable):** a person can delete their account and their content from inside the app, without contacting anyone, and the deletion path is built in the same phase as the feature that creates the data.

## P3: We know who is a child

- **P3 (enforceable):** any feature reachable by someone under 18 must state its age-assurance mechanism and what changes for a minor. Collecting a birth date is not an age-assurance mechanism.

## P4: Location is borrowed, never taken

- **P4 (enforceable):** location is read only with explicit consent, only at the precision the feature actually needs, and never in the background unless the plan says why and the person was told.

## P5: Every place people can reach each other needs a way out

- **P5 (enforceable):** any person-to-person surface ships with blocking, reporting, and a stated response path in the same phase. A social feature without moderation is not shippable.

## P6: The plan names its jurisdictions

- **P6 (enforceable):** a plan that processes personal data names the markets it launches in, because the obligations differ and we cannot infer them.

## P7: We do not claim what we did not test

- **P7 (enforceable):** a verification lane that could not run is reported as not run, with the reason. It is never reported as passed and never quietly omitted.

## P8: The store is part of the product

- Apple App Review and Google Play policy are requirements, not paperwork at the end. Anything that would be rejected is a defect found late.

## P9: Both platforms behave the same

- Where iOS and Android implement the same rule, the rule has one definition and one set of tests. Two implementations of the same logic will diverge.

## P10: Accessibility is in the acceptance criteria

- VoiceOver and TalkBack are part of "done" for any screen, not a later pass.
