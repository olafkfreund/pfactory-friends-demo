# EU AI Act Audit Pack — MyFriends

> This audit pack is a descriptive evidence bundle assembled from PFactory's planning record. The EU AI Act article/heading references are navigational labels indicating where each artifact may be relevant; they are NOT an assertion of EU AI Act conformity for the system, model, or plan. Conformity determinations require a qualified legal / conformity assessment. PFactory makes no conformity claim.

- Plan id: `011-myfriends`
- Generated: 2026-09-03T10:36:07.768565+00:00
- Schema: `audit-pack/v0`

## Cross-reference

| Artifact | Present | EU AI Act headings (descriptive) |
| --- | --- | --- |
| Honoured source document | yes | Technical documentation (Art. 11 / Annex IV) |
| Review-gate findings & citations | yes | Risk management (Art. 9); Technical documentation (Art. 11 / Annex IV) |
| Human approval record | no | Human oversight (Art. 14); Record-keeping & logging (Art. 12) |
| Signed Task Contract (RFC-0002) | no | Technical documentation (Art. 11 / Annex IV); Record-keeping & logging (Art. 12) |
| Completion & correlation timeline | no | Record-keeping & logging (Art. 12) |
| TFactory verification verdict | no | Technical documentation (Art. 11 / Annex IV); Risk management (Art. 9) |

## Evidence

### Honoured source document

_The plan as ingested: 'MyFriends' (12 stated acceptance criteria)._

```json
{
  "title": "MyFriends",
  "description": "A mobile app for finding and connecting with people nearby who are open to making\nnew friends. Not dating. The premise is that adults and older teenagers who move\nto a new city, change jobs, or come out of a long relationship have no good way to\nmeet people platonically, and existing apps either optimise for romance or for\nprofessional networking.\n\n## Product\n\nA person installs the app, creates a profile, and sets themselves as open to new\nfriends. The app shows other people nearby who are also open, ordered by how well\ntheir stated interests and availability match. Either person can send a connection\nrequest; when both accept, they can message each other in the app.\n\nThe distinguishing feature is the \"open to new friends\" toggle. Discovery only\nsurfaces people who have deliberately turned it on, so nobody appears in anyone\nelse's results by default.\n\n## Users\n\n- Adults aged 18 and over, the primary audience.\n- Older teenagers aged 16 and 17, who we expect to be a meaningful minority of\n  signups and who we do not want to exclude.\n\n## Platforms\n\nNative on both platforms, no cross-platform framework.\n\n- iOS: Swift, SwiftUI, minimum iOS 16.\n- Android: Kotlin, Jetpack Compose, minimum API 29.\n- A shared backend serving both clients.\n\nThe business logic that decides matching and eligibility should be testable\nindependently of the UI on each platform.\n\n## Markets at launch\n\nUnited Kingdom, the European Union (starting with Ireland, Germany and the\nNetherlands), and the United States (California first).",
  "target_kind": "software",
  "plan_type": "feature",
  "acceptance_criteria": [
    {
      "id": "AC#1",
      "text": "A person can create an account and a profile containing a display name, a photo, an age, a short bio, and up to ten interest tags."
    },
    {
      "id": "AC#2",
      "text": "A person can turn \"open to new friends\" on and off, and turning it off removes them from every other person's discovery results within one minute."
    },
    {
      "id": "AC#3",
      "text": "Discovery returns only people who currently have \"open to new friends\" turned on and who are within the searching person's chosen radius, which can be set to 1, 5, 10 or 25 kilometres."
    },
    {
      "id": "AC#4",
      "text": "Discovery results are ordered by a match score computed from shared interest tags and overlapping stated availability, and the app shows the person why each result was surfaced."
    },
    {
      "id": "AC#5",
      "text": "A person can send a connection request to someone in their discovery results, and can send at most twenty requests in any twenty-four hour period."
    },
    {
      "id": "AC#6",
      "text": "Two people can exchange messages in the app only after both have accepted the connection."
    },
    {
      "id": "AC#7",
      "text": "A person can block another person, and a blocked person can never appear in their discovery results, send them a request, or message them."
    },
    {
      "id": "AC#8",
      "text": "A person can report another person or a message, choosing from a fixed list of reasons and optionally adding free text."
    },
    {
      "id": "AC#9",
      "text": "The app works with no network connection to the extent of showing the person's own profile and their existing accepted connections and previously loaded messages."
    },
    {
      "id": "AC#10",
      "text": "The iOS and Android clients share a single definition of the match score, so the same two profiles produce the same score on both platforms."
    },
    {
      "id": "AC#11",
      "text": "The backend exposes the discovery, request, and messaging operations over an authenticated API, and rejects any unauthenticated call."
    },
    {
      "id": "AC#12",
      "text": "Location is only read while the person is actively using the app."
    }
  ],
  "content_hash": "b404294c7cbfb6efd3b673802c519d4f",
  "raw_text": "# MyFriends\n\nA mobile app for finding and connecting with people nearby who are open to making\nnew friends. Not dating. The premise is that adults and older teenagers who move\nto a new city, change jobs, or come out of a long relationship have no good way to\nmeet people platonically, and existing apps either optimise for romance or for\nprofessional networking.\n\n## Product\n\nA person installs the app, creates a profile, and sets themselves as open to new\nfriends. The app shows other people nearby who are also open, ordered by how well\ntheir stated interests and availability match. Either person can send a connection\nrequest; when both accept, they can message each other in the app.\n\nThe distinguishing feature is the \"open to new friends\" toggle. Discovery only\nsurfaces people who have deliberately turned it on, so nobody appears in anyone\nelse's results by default.\n\n## Users\n\n- Adults aged 18 and over, the primary audience.\n- Older teenagers aged 16 and 17, who we expect to be a meaningful minority of\n  signups and who we do not want to exclude.\n\n## Platforms\n\nNative on both platforms, no cross-platform framework.\n\n- iOS: Swift, SwiftUI, minimum iOS 16.\n- Android: Kotlin, Jetpack Compose, minimum API 29.\n- A shared backend serving both clients.\n\nThe business logic that decides matching and eligibility should be testable\nindependently of the UI on each platform.\n\n## Markets at launch\n\nUnited Kingdom, the European Union (starting with Ireland, Germany and the\nNetherlands), and the United States (California first).\n\n## Acceptance Criteria\n\n- A person can create an account and a profile containing a display name, a photo, an age, a short bio, and up to ten interest tags.\n- A person can turn \"open to new friends\" on and off, and turning it off removes them from every other person's discovery results within one minute.\n- Discovery returns only people who currently have \"open to new friends\" turned on and who are within the searching person's chosen radius, which can be set to 1, 5, 10 or 25 kilometres.\n- Discovery results are ordered by a match score computed from shared interest tags and overlapping stated availability, and the app shows the person why each result was surfaced.\n- A person can send a connection request to someone in their discovery results, and can send at most twenty requests in any twenty-four hour period.\n- Two people can exchange messages in the app only after both have accepted the connection.\n- A person can block another person, and a blocked person can never appear in their discovery results, send them a request, or message them.\n- A person can report another person or a message, choosing from a fixed list of reasons and optionally adding free text.\n- The app works with no network connection to the extent of showing the person's own profile and their existing accepted connections and previously loaded messages.\n- The iOS and Android clients share a single definition of the match score, so the same two profiles produce the same score on both platforms.\n- The backend exposes the discovery, request, and messaging operations over an authenticated API, and rejects any unauthenticated call.\n- Location is only read while the person is actively using the app.\n"
}
```

### Review-gate findings & citations

_Multi-lens review: aggregate 0.92, gates_passed=False._

```json
{
  "aggregate_score": 0.92,
  "threshold": 0.75,
  "gates_passed": false,
  "lenses": [
    {
      "lens": "feasibility",
      "score": 1.0,
      "findings": []
    },
    {
      "lens": "architecture",
      "score": 0.9,
      "findings": [
        {
          "title": "Vague titles",
          "detail": "Unclear titles on: epic.",
          "severity": "low",
          "source": "architecture",
          "blocking": false,
          "citations": []
        }
      ]
    },
    {
      "lens": "security",
      "score": 0.7,
      "findings": [
        {
          "title": "No authentication/authorization criteria",
          "detail": "A software plan has no acceptance criterion covering auth; confirm access control is in scope or explicitly out.",
          "severity": "medium",
          "source": "security",
          "blocking": false,
          "citations": []
        }
      ]
    },
    {
      "lens": "best-practices",
      "score": 1.0,
      "findings": [
        {
          "title": "Golden-path guidance available",
          "detail": "8 knowledge reference(s) surfaced from 1 source(s) (e.g. TFactory, NixOS Module (flake-based service module + agenix-ready), COSMIC Desktop Applet (libcosmic + flake)); confirm the plan follows them.",
          "severity": "info",
          "source": "best-practices",
          "blocking": false,
          "citations": [
            {
              "title": "TFactory",
              "uri": "https://backstage.freundcloud.org.uk/catalog/default/component/tfactory",
              "why": "Surfaced from your org's knowledge sources \u2014 the plan should follow it."
            },
            {
              "title": "NixOS Module (flake-based service module + agenix-ready)",
              "uri": "https://backstage.freundcloud.org.uk/catalog/default/template/nixos-module",
              "why": "Surfaced from your org's knowledge sources \u2014 the plan should follow it."
            },
            {
              "title": "COSMIC Desktop Applet (libcosmic + flake)",
              "uri": "https://backstage.freundcloud.org.uk/catalog/default/template/cosmic-applet",
              "why": "Surfaced from your org's knowledge sources \u2014 the plan should follow it."
            },
            {
              "title": "Tailscale sidecar pattern (factory cluster)",
              "uri": "https://backstage.freundcloud.org.uk/catalog/default/resource/tailscale-sidecar-pattern",
              "why": "Surfaced from your org's knowledge sources \u2014 the plan should follow it."
            },
            {
              "title": "Factory Agent-Skills Manifest (RFC-0019)",
              "uri": "https://backstage.freundcloud.org.uk/catalog/default/api/factory-agent-skills-manifest",
              "why": "Surfaced from your org's knowledge sources \u2014 the plan should follow it."
            },
            {
              "title": "Backstage Portal",
              "uri": "https://backstage.freundcloud.org.uk/catalog/default/component/backstage",
              "why": "Surfaced from your org's knowledge sources \u2014 the plan should follow it."
            },
            {
              "title": "Python Service (FastAPI + uv + flake)",
              "uri": "https://backstage.freundcloud.org.uk/catalog/default/template/python-service",
              "why": "Surfaced from your org's knowledge sources \u2014 the plan should follow it."
            },
            {
              "title": "AIFactory",
              "uri": "https://backstage.freundcloud.org.uk/catalog/default/component/aifactory",
              "why": "Surfaced from your org's knowledge sources \u2014 the plan should follow it."
            }
          ]
        }
      ]
    },
    {
      "lens": "completeness",
      "score": 1.0,
      "findings": []
    }
  ]
}
```

### Human approval record

_No valid human approval recorded._

Not present in this plan's record.

### Signed Task Contract (RFC-0002)

_No Task Contract emitted for this plan._

Not present in this plan's record.

### Completion & correlation timeline

_Plan has not been emitted — no correlation chain yet._

Not present in this plan's record.

### TFactory verification verdict

_No TFactory verdict on this plan record (verified downstream in TFactory)._

Not present in this plan's record.
