# MyFriends

A mobile app for finding and connecting with people nearby who are open to making
new friends. Not dating. The premise is that adults and older teenagers who move
to a new city, change jobs, or come out of a long relationship have no good way to
meet people platonically, and existing apps either optimise for romance or for
professional networking.

## Product

A person installs the app, creates a profile, and sets themselves as open to new
friends. The app shows other people nearby who are also open, ordered by how well
their stated interests and availability match. Either person can send a connection
request; when both accept, they can message each other in the app.

The distinguishing feature is the "open to new friends" toggle. Discovery only
surfaces people who have deliberately turned it on, so nobody appears in anyone
else's results by default.

## Users

- Adults aged 18 and over, the primary audience.
- Older teenagers aged 16 and 17, who we expect to be a meaningful minority of
  signups and who we do not want to exclude.

## Platforms

Native on both platforms, no cross-platform framework.

- iOS: Swift, SwiftUI, minimum iOS 16.
- Android: Kotlin, Jetpack Compose, minimum API 29.
- A shared backend serving both clients.

The business logic that decides matching and eligibility should be testable
independently of the UI on each platform.

## Markets at launch

United Kingdom, the European Union (starting with Ireland, Germany and the
Netherlands), and the United States (California first).

## Acceptance Criteria

- A person can create an account and a profile containing a display name, a photo, an age, a short bio, and up to ten interest tags.
- A person can turn "open to new friends" on and off, and turning it off removes them from every other person's discovery results within one minute.
- Discovery returns only people who currently have "open to new friends" turned on and who are within the searching person's chosen radius, which can be set to 1, 5, 10 or 25 kilometres.
- Discovery results are ordered by a match score computed from shared interest tags and overlapping stated availability, and the app shows the person why each result was surfaced.
- A person can send a connection request to someone in their discovery results, and can send at most twenty requests in any twenty-four hour period.
- Two people can exchange messages in the app only after both have accepted the connection.
- A person can block another person, and a blocked person can never appear in their discovery results, send them a request, or message them.
- A person can report another person or a message, choosing from a fixed list of reasons and optionally adding free text.
- The app works with no network connection to the extent of showing the person's own profile and their existing accepted connections and previously loaded messages.
- The iOS and Android clients share a single definition of the match score, so the same two profiles produce the same score on both platforms.
- The backend exposes the discovery, request, and messaging operations over an authenticated API, and rejects any unauthenticated call.
- Location is only read while the person is actively using the app.
