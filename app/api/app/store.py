"""In-memory repositories with the domain rules (plan step 3).

Ported from lanes/kotlin-core as the specification of each rule.

The rules live in one place: the backend. lanes/kotlin-core is the historical
reference; this module is the single source of truth for the backend rules.

Two implementations of one compliance rule is the shape that produced #86,
where the messaging path and the connection-request path disagreed about what
"blocked" means. The fix is a single `may_contact(a, b)` predicate used by
discovery, connection requests, and messaging alike.

ponytail: persistence is in-memory here (plan step 3). Step 2 replaces this
with Postgres-backed repositories — one change per file, not a scatter of
stubs to undo.
"""

from __future__ import annotations

import time

from .domain import (
    AgeAssuranceStatus,
    Connection,
    ConnectionStatus,
    DiscoveryResult,
    Message,
    Profile,
    Report,
    ReportReason,
    ReportTargetKind,
    age_bracket,
)

# --- Limits (single source of truth) ---

MAX_CONNECTION_REQUESTS_PER_DAY: int = 20  # AC#5
MAX_MESSAGE_LENGTH: int = 2_000  # placeholder; no validated product decision yet
MAX_FREE_TEXT_LENGTH: int = 1_000  # placeholder; no validated product decision yet
MIN_AGE: int = 16  # AC#1 — "Older teenagers aged 16 and 17"
_MILLIS_PER_DAY: int = 24 * 60 * 60 * 1_000


# ---------------------------------------------------------------------------
# Profile store (with blocking)
# ---------------------------------------------------------------------------


class ProfileStore:
    """In-memory storage for profiles and block records.

    Ported from lanes/kotlin-core/src/main/kotlin/ProfileRepository.kt.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, Profile] = {}
        # blocked_by[blocker_id] = set of blocked_ids
        self._blocked_by: dict[str, set[str]] = {}

    def save(self, profile: Profile) -> None:
        """Persist profile (upsert semantics)."""
        if not profile.id.strip():
            raise ValueError("profile id must not be blank")
        if profile.age < MIN_AGE:
            raise ValueError(f"age must be at least {MIN_AGE}")
        self._profiles[profile.id] = profile

    def find(self, profile_id: str) -> Profile | None:
        return self._profiles.get(profile_id)

    def block(self, blocker_id: str, blocked_id: str) -> None:
        """Record that blocker_id has blocked blocked_id (AC#7 / P5)."""
        self._blocked_by.setdefault(blocker_id, set()).add(blocked_id)

    def is_blocked(self, blocker_id: str, blocked_id: str) -> bool:
        """Return True if blocker_id has blocked blocked_id."""
        return blocked_id in self._blocked_by.get(blocker_id, set())

    def set_age_assurance(self, profile_id: str, status: AgeAssuranceStatus) -> None:
        """Record the age assurance result for an existing profile (AC#5).

        The status is written directly to the stored Profile object; callers
        should re-fetch the profile to observe the change.
        """
        profile = self._profiles.get(profile_id)
        if profile is not None:
            profile.age_assurance_status = status

    def delete(self, profile_id: str) -> None:
        """Delete the profile and all block records it owns (P1, P2)."""
        self._profiles.pop(profile_id, None)
        self._blocked_by.pop(profile_id, None)


# ---------------------------------------------------------------------------
# may_contact — the single predicate used by all three contact surfaces
# ---------------------------------------------------------------------------


def may_contact(store: ProfileStore, a: str, b: str) -> bool:
    """Return True only when neither party has blocked the other.

    This is the single predicate used by discovery, connection requests, and
    messaging alike. Using one check on all three surfaces is the fix for #86,
    where the messaging path and the connection-request path disagreed about
    what "blocked" means.

    AC#7 / constitution P5 (enforceable): a blocked person can never appear
    in discovery results, send a request, or message the person who blocked
    them. Blocking is symmetric: if A blocks B, B cannot contact A either.

    Mutation target: if this is reverted to a one-directional check
    (`not store.is_blocked(a, b)` only), the symmetry tests must go red.
    That is the check this implementation is here to pass.
    """
    return not (
        store.is_blocked(blocker_id=a, blocked_id=b) or store.is_blocked(blocker_id=b, blocked_id=a)
    )


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _match_score(
    my_interests: set[str],
    their_interests: set[str],
    my_activities: set[str],
    their_activities: set[str],
) -> float:
    """Compute match score (ported from lanes/kotlin-core MatchScore.kt).

    Interest-only: fraction of searcher's interests the candidate also holds.
    Combined: mean of interest and activity fractions when the searcher carries
    stated availability.
    """
    interest_score = (
        len(my_interests & their_interests) / len(my_interests) if my_interests else 0.0
    )
    if not my_activities:
        return interest_score
    activity_score = (
        len(my_activities & their_activities) / len(my_activities) if my_activities else 0.0
    )
    return (interest_score + activity_score) / 2.0


def discover(
    store: ProfileStore,
    searcher: Profile,
    radius_km: int = 25,
) -> list[DiscoveryResult]:
    """Return profiles the searcher may discover, ordered by match score.

    Rules applied (plan step 3 / spec):
    - Only profiles with open_to_friends=True are included (AC#2).
    - Age-bracket isolation: an adult and a minor are never mutually
      discoverable (spec: compliance / age assurance before eligibility).
    - may_contact check: blocked profiles are excluded on both sides (AC#7, P5,
      the #86 fix — one predicate, three surfaces).
    - Radius filter: only profiles within radius_km km when both parties have
      a known location (AC#3).
    - Results are sorted by match score descending (AC#4).
    """
    results: list[DiscoveryResult] = []
    searcher_bracket = age_bracket(searcher.age)
    searcher_interests = set(searcher.interests)
    searcher_activities = set(searcher.activities)

    for profile in store._profiles.values():
        if profile.id == searcher.id:
            continue
        if not profile.open_to_friends:
            continue
        # Age assurance (AC#5): only profiles with PASSED age assurance are
        # eligible to appear in discovery results.
        if profile.age_assurance_status != AgeAssuranceStatus.PASSED:
            continue
        # Age-bracket isolation (compliance — adults and minors never meet in
        # discovery).
        if age_bracket(profile.age) != searcher_bracket:
            continue
        # Single may_contact predicate: the #86 fix.
        if not may_contact(store, searcher.id, profile.id):
            continue
        # Radius filter (only applied when both locations are known).
        if (
            searcher.location is not None
            and profile.location is not None
            and searcher.location.distance_to(profile.location) > radius_km
        ):
            continue

        their_interests = set(profile.interests)
        their_activities = set(profile.activities)
        shared_interests = sorted(searcher_interests & their_interests)
        shared_activities = sorted(searcher_activities & their_activities)
        score = _match_score(
            searcher_interests, their_interests, searcher_activities, their_activities
        )

        results.append(
            DiscoveryResult(
                profile=profile,
                score=score,
                shared_interests=shared_interests,
                shared_activities=shared_activities,
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Connection store
# ---------------------------------------------------------------------------


class ConnectionStore:
    """In-memory repository for connections with rate limiting.

    Ported from lanes/kotlin-core/src/main/kotlin/MessagingRepository.kt.
    """

    def __init__(self, profile_store: ProfileStore) -> None:
        self._profile_store = profile_store
        self._connections: dict[str, Connection] = {}
        # request_timestamps[requester_id] = list of epoch-ms timestamps
        self._request_timestamps: dict[str, list[int]] = {}

    def _canonical_id(self, id1: str, id2: str) -> str:
        """Stable symmetric key for a connection between two users."""
        a, b = (id1, id2) if id1 <= id2 else (id2, id1)
        return f"{a}::{b}"

    def send_request(
        self, requester_id: str, recipient_id: str
    ) -> tuple[Connection | None, str | None]:
        """Return (connection, None) on success, (None, reason) on refusal.

        Refusal reasons match DomainOutcome.kt:
        - "blank_id": either id is blank.
        - "self_request": requester and recipient are the same.
        - "blocked": one party has blocked the other (may_contact check).
        - "already_exists": a connection for this pair already exists.
        - "rate_limit_exceeded": requester has hit the daily limit (AC#5).
        """
        if not requester_id.strip() or not recipient_id.strip():
            return None, "blank_id"
        if requester_id == recipient_id:
            return None, "self_request"
        # Single may_contact predicate — same check as discovery and messaging.
        if not may_contact(self._profile_store, requester_id, recipient_id):
            return None, "blocked"
        conn_id = self._canonical_id(requester_id, recipient_id)
        if conn_id in self._connections:
            return None, "already_exists"
        now_ms = int(time.time() * 1_000)
        window_start_ms = now_ms - _MILLIS_PER_DAY
        timestamps = self._request_timestamps.setdefault(requester_id, [])
        # Prune expired entries so the list does not grow without bound.
        self._request_timestamps[requester_id] = [ts for ts in timestamps if ts >= window_start_ms]
        if len(self._request_timestamps[requester_id]) >= MAX_CONNECTION_REQUESTS_PER_DAY:
            return None, "rate_limit_exceeded"
        conn = Connection(
            id=conn_id,
            requester_id=requester_id,
            recipient_id=recipient_id,
        )
        self._connections[conn_id] = conn
        self._request_timestamps[requester_id].append(now_ms)
        return conn, None

    def accept_request(self, connection_id: str, acceptor_id: str) -> bool:
        """Accept a pending connection request on behalf of acceptor_id (AC#6)."""
        conn = self._connections.get(connection_id)
        if conn is None:
            return False
        if conn.recipient_id != acceptor_id:
            return False
        if conn.status != ConnectionStatus.PENDING:
            return False
        self._connections[connection_id] = Connection(
            id=conn.id,
            requester_id=conn.requester_id,
            recipient_id=conn.recipient_id,
            status=ConnectionStatus.ACCEPTED,
        )
        return True

    def are_connected(self, user1: str, user2: str) -> bool:
        """Return True when user1 and user2 hold an accepted connection (AC#6)."""
        conn_id = self._canonical_id(user1, user2)
        conn = self._connections.get(conn_id)
        return conn is not None and conn.status == ConnectionStatus.ACCEPTED

    def get_connection(self, connection_id: str) -> Connection | None:
        return self._connections.get(connection_id)


# ---------------------------------------------------------------------------
# Message store
# ---------------------------------------------------------------------------


class MessageStore:
    """In-memory repository for messages.

    Ported from lanes/kotlin-core/src/main/kotlin/MessagingRepository.kt.
    """

    def __init__(self, profile_store: ProfileStore, connection_store: ConnectionStore) -> None:
        self._profile_store = profile_store
        self._connection_store = connection_store
        self._messages: list[Message] = []
        self._next_id = 0

    def send(
        self, sender_id: str, recipient_id: str, body: str
    ) -> tuple[Message | None, str | None]:
        """Return (message, None) on success, (None, reason) on refusal.

        Refusal reasons match DomainOutcome.kt:
        - "not_connected": no accepted connection between sender and recipient.
        - "blocked": one party has blocked the other.
        - "blank_body": body is blank or whitespace-only.
        - "body_too_long": body exceeds MAX_MESSAGE_LENGTH.
        """
        # AC#6: the pair must hold an ACCEPTED connection.
        if not self._connection_store.are_connected(sender_id, recipient_id):
            return None, "not_connected"
        # Single may_contact predicate — same check as discovery and requests.
        if not may_contact(self._profile_store, sender_id, recipient_id):
            return None, "blocked"
        if not body.strip():
            return None, "blank_body"
        if len(body) > MAX_MESSAGE_LENGTH:
            return None, "body_too_long"
        msg = Message(
            id=f"msg-{self._next_id}",
            sender_id=sender_id,
            recipient_id=recipient_id,
            body=body,
        )
        self._next_id += 1
        self._messages.append(msg)
        return msg, None

    def get_messages(self, user1: str, user2: str) -> list[Message]:
        """Return all messages between user1 and user2 in chronological order."""
        return [
            m
            for m in self._messages
            if (m.sender_id == user1 and m.recipient_id == user2)
            or (m.sender_id == user2 and m.recipient_id == user1)
        ]


# ---------------------------------------------------------------------------
# Report store
# ---------------------------------------------------------------------------


class ReportStore:
    """In-memory repository for reports.

    Ported from lanes/kotlin-core/src/main/kotlin/ReportRepository.kt.

    P5 (constitution, enforceable): every person-to-person surface ships with
    reporting in the same phase as the feature that creates the data.
    """

    def __init__(self) -> None:
        self._reports: list[Report] = []
        self._next_id = 0

    def submit(
        self,
        reporter_id: str,
        target_id: str,
        target_kind: ReportTargetKind,
        reason: ReportReason,
        additional_text: str = "",
    ) -> Report | None:
        """Submit a report; return None when validation fails."""
        if not reporter_id.strip() or not target_id.strip():
            return None
        trimmed = additional_text.strip()
        if len(trimmed) > MAX_FREE_TEXT_LENGTH:
            return None
        report = Report(
            id=f"report-{self._next_id}",
            reporter_id=reporter_id,
            target_id=target_id,
            target_kind=target_kind,
            reason=reason,
            additional_text=trimmed,
        )
        self._next_id += 1
        self._reports.append(report)
        return report

    def get_reports_against(self, target_id: str) -> list[Report]:
        return [r for r in self._reports if r.target_id == target_id]

    def get_reports_by(self, reporter_id: str) -> list[Report]:
        return [r for r in self._reports if r.reporter_id == reporter_id]
