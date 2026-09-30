# MyFriends Web: remediation

The MyFriends web application exists and is deployed, but independent review
found that two of its foundations are missing rather than imperfect: it has no
database, and it makes no authorisation decisions at all. This brief exists to
close those gaps and the two lesser ones found alongside them.

It is a remediation brief, so it is written differently from a feature brief.
Each acceptance criterion below names **the thing that must be prevented**, not
the feature that must exist. A test that only demonstrates the happy path
satisfies none of them.

## What is wrong now

`app/api/app/main.py` declares `dependencies=[Depends(require_auth)]` on every
endpoint. That form of the dependency **discards its return value** — the
authenticated caller's own id — and every endpoint then takes the acting
identity from the request instead: `body.id`, `requester_id`, `sender_id`,
`blocker_id`, `profile_id`, `reporter_id`. The caller supplies who they are.

`app/api/app/store.py` holds every profile, connection, message and report in
plain Python dicts and lists in the web process. `app/api/pyproject.toml`
declares no database dependency of any kind.

## Users

Unchanged from the original brief: adults 18 and over, and 16-17 year olds as a
protected minority whose data is separated from adults'.

## Platform

Unchanged: FastAPI backend, React/TypeScript frontend, deployed into the
cluster. No new services, no new languages. Postgres is already available in the
cluster; the application must use it rather than ship its own.

## Acceptance Criteria

- A caller authenticated as one person cannot act as another person: for every
  endpoint that changes state, a request whose authenticated identity is person
  A and whose acting identity in the path or body is person B is rejected with
  403 and changes nothing. This holds for creating and updating a profile,
  toggling availability, recording age assurance, sending a connection request,
  accepting or declining one, sending a message, blocking, reporting, and
  deleting an account.
- Deleting an account requires that the authenticated caller owns that account;
  a caller cannot delete anyone else's account by naming its id.
- Marking a profile's age assurance as passed requires that the authenticated
  caller owns that profile, so no caller can grant another person's age
  assurance.
- Profiles, connections, messages, blocks and reports are stored in Postgres and
  survive a restart of the service: data written before the process is restarted
  is readable after it, with no in-process dictionary holding the only copy.
- Database credentials are read from the environment at runtime and appear
  nowhere in the repository or in any image.
- Saving a profile whose display name is blank, or is only whitespace, or is
  longer than the documented maximum, is rejected with the documented reason and
  no profile is written.
- Resolving a report requires the moderation role; a caller who is authenticated
  but not a moderator is rejected with 403, and in particular cannot impose a
  contact removal on another person.
- An unauthenticated call to any endpoint other than the health check is
  rejected before any authorisation or business logic runs.
- The authenticated caller's own identity is available to endpoint code from a
  single source, so that no endpoint can determine the acting identity by a
  different route than any other endpoint.
