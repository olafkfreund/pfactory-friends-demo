"""MyFriends API — rules implemented (plan step 3).

Walking skeleton (plan step 1): GET /healthz and GET /profiles/me.
Rules (plan step 3): profile upsert, availability toggle, discovery,
connection requests, accept, messaging, blocking, and reports. Each
endpoint has a test; the key invariant — bidirectional blocking — is
the fix for #86.

Persistence is in-memory (plan step 3). Postgres-backed repositories
replace these stores in plan step 2 once the schema migration is in place.
Auth (Keycloak via oauth2-proxy) is wired in plan step 3 at the deployment
layer; header parsing is left as a TODO here so the tests can run without a
live Keycloak instance.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .domain import (
    VALID_SEARCH_RADII,
    AgeAssuranceStatus,
    GeoLocation,
    Profile,
    Report,
    ReportReason,
    ReportResolutionOutcome,
    ReportTargetKind,
)
from .store import (
    ConnectionStore,
    MessageStore,
    ProfileStore,
    ReportStore,
    discover,
    may_contact,
)

app = FastAPI(title="MyFriends API")

# ---------------------------------------------------------------------------
# Application state — in-memory stores (plan step 3 placeholder).
# Replaced by Postgres-backed stores in plan step 2.
# ---------------------------------------------------------------------------

_profiles = ProfileStore()
_connections = ConnectionStore(_profiles)
_messages = MessageStore(_profiles, _connections)
_reports = ReportStore()


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------


class ProfileIn(BaseModel):
    id: str
    display_name: str
    bio: str = ""
    interests: list[str] = Field(default_factory=list)
    activities: list[str] = Field(default_factory=list)
    age: int = 18
    open_to_friends: bool = False
    lat: float | None = None
    lon: float | None = None


class ProfileOut(BaseModel):
    id: str
    display_name: str
    bio: str
    interests: list[str]
    activities: list[str]
    age: int
    open_to_friends: bool
    age_assurance_status: str  # AC#5: surface the status so callers can act on it


class ConnectionOut(BaseModel):
    id: str
    requester_id: str
    recipient_id: str
    status: str


class MessageIn(BaseModel):
    sender_id: str
    recipient_id: str
    body: str


class MessageOut(BaseModel):
    id: str
    sender_id: str
    recipient_id: str
    body: str


class BlockIn(BaseModel):
    blocker_id: str
    blocked_id: str


class ReportIn(BaseModel):
    reporter_id: str
    target_id: str
    target_kind: ReportTargetKind
    reason: ReportReason
    additional_text: str = ""
    immediate_harm: bool = False  # AC#12: flag for immediate risk of harm priority


class ReportOut(BaseModel):
    id: str
    reporter_id: str
    target_id: str
    target_kind: str
    reason: str
    additional_text: str
    immediate_harm: bool  # AC#12
    queue_status: str  # AC#12: "accepted" on creation; "resolved" after resolution (AC#13)
    resolution_outcome: str | None = None  # AC#13: set when resolved
    resolved_at: float | None = None  # AC#13: epoch-seconds timestamp of resolution


class ResolveReportIn(BaseModel):
    """Request body for resolving a report (AC#13).

    Exactly three outcomes are accepted: no_action, warning, contact_removal.
    Any other value is refused before storage.
    """

    outcome: ReportResolutionOutcome


class ContactStatusOut(BaseModel):
    """Contact removal status for a profile (AC#14)."""

    contact_removed: bool
    reason: str | None = None  # machine-readable reason when contact_removed is True


class DiscoveryResultOut(BaseModel):
    profile: ProfileOut
    score: float
    shared_interests: list[str]
    shared_activities: list[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile_out(p: Profile) -> ProfileOut:
    return ProfileOut(
        id=p.id,
        display_name=p.display_name,
        bio=p.bio,
        interests=p.interests,
        activities=p.activities,
        age=p.age,
        open_to_friends=p.open_to_friends,
        age_assurance_status=p.age_assurance_status.value,
    )


# ---------------------------------------------------------------------------
# Healthz
# ---------------------------------------------------------------------------


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


@app.get("/profiles/me")
def profile_me() -> dict[str, str]:
    # ponytail: hardcoded placeholder until auth (step 3) supplies a real
    # user id. The ProfileStore already supports real lookups via /profiles/{id}.
    return {
        "id": "placeholder",
        "display_name": "Demo Friend",
        "bio": "This profile is a placeholder until step 2 adds persistence.",
    }


@app.post("/profiles", status_code=status.HTTP_201_CREATED, response_model=ProfileOut)
def create_profile(body: ProfileIn) -> ProfileOut:
    """Create or update a profile (upsert)."""
    location = (
        GeoLocation(lat=body.lat, lon=body.lon)
        if body.lat is not None and body.lon is not None
        else None
    )
    profile = Profile(
        id=body.id,
        display_name=body.display_name,
        bio=body.bio,
        interests=body.interests,
        activities=body.activities,
        age=body.age,
        open_to_friends=body.open_to_friends,
        location=location,
    )
    try:
        _profiles.save(profile)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _profile_out(profile)


@app.get("/profiles/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: str) -> ProfileOut:
    profile = _profiles.find(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    return _profile_out(profile)


@app.patch("/profiles/{profile_id}/availability", response_model=ProfileOut)
def toggle_availability(profile_id: str, open_to_friends: bool) -> ProfileOut:
    """Toggle the 'open to new friends' status (AC#6).

    Turning it off removes the profile from every other person's discovery
    results on the next query (the discover() function filters open_to_friends).
    All other profile fields — including age_assurance_status — are preserved.
    """
    profile = _profiles.find(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    updated = Profile(
        id=profile.id,
        display_name=profile.display_name,
        bio=profile.bio,
        interests=profile.interests,
        activities=profile.activities,
        age=profile.age,
        open_to_friends=open_to_friends,
        location=profile.location,
        age_assurance_status=profile.age_assurance_status,  # AC#6: preserve assurance status
    )
    _profiles.save(updated)
    return _profile_out(updated)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


@app.get("/discovery/{searcher_id}", response_model=list[DiscoveryResultOut])
def discovery(searcher_id: str, radius_km: int = 25) -> list[DiscoveryResultOut]:
    """Return profiles the searcher may discover (AC#2, AC#3, AC#4, AC#5, AC#7).

    Filters applied: age assurance passed (AC#5), open_to_friends=True,
    age-bracket isolation, may_contact (bidirectional block check — the #86
    fix), radius.

    Returns 403 with a machine-readable reason when the searcher's own age
    assurance has not passed, naming whether the status is 'unrecorded' or
    'failed' so the client can present the right message (AC#5).
    """
    if radius_km not in VALID_SEARCH_RADII:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"radius_km must be one of {sorted(VALID_SEARCH_RADII)}",
        )
    searcher = _profiles.find(searcher_id)
    if searcher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="searcher not found")
    # AC#5: searcher must have passed age assurance to use discovery.
    if searcher.age_assurance_status == AgeAssuranceStatus.UNRECORDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="age_assurance_unrecorded",
        )
    if searcher.age_assurance_status == AgeAssuranceStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="age_assurance_failed",
        )
    results = discover(_profiles, searcher, radius_km=radius_km)
    return [
        DiscoveryResultOut(
            profile=_profile_out(r.profile),
            score=r.score,
            shared_interests=r.shared_interests,
            shared_activities=r.shared_activities,
        )
        for r in results
    ]


# ---------------------------------------------------------------------------
# Age assurance
# ---------------------------------------------------------------------------


class AgeAssuranceIn(BaseModel):
    status: AgeAssuranceStatus


@app.post("/profiles/{profile_id}/age-assurance", response_model=ProfileOut)
def record_age_assurance(profile_id: str, body: AgeAssuranceIn) -> ProfileOut:
    """Record the age assurance result for a profile (AC#5).

    Accepted statuses: 'passed', 'failed'.  (Setting to 'unrecorded' is not
    a valid operation — that is the initial state on creation.)
    """
    profile = _profiles.find(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile not found")
    if body.status == AgeAssuranceStatus.UNRECORDED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="cannot set age_assurance_status to 'unrecorded' via this endpoint",
        )
    _profiles.set_age_assurance(profile_id, body.status)
    updated = _profiles.find(profile_id)
    assert updated is not None
    return _profile_out(updated)


# ---------------------------------------------------------------------------
# Connection requests
# ---------------------------------------------------------------------------


@app.post("/connections", status_code=status.HTTP_201_CREATED, response_model=ConnectionOut)
def send_connection_request(requester_id: str, recipient_id: str) -> ConnectionOut:
    """Send a connection request (AC#5, AC#7)."""
    conn, reason = _connections.send_request(requester_id, recipient_id)
    if conn is None:
        code = {
            "blocked": status.HTTP_403_FORBIDDEN,
            "contact_removed": status.HTTP_403_FORBIDDEN,  # AC#14
            "rate_limit_exceeded": status.HTTP_429_TOO_MANY_REQUESTS,
        }.get(reason or "", status.HTTP_422_UNPROCESSABLE_ENTITY)
        raise HTTPException(status_code=code, detail=reason)
    return ConnectionOut(
        id=conn.id,
        requester_id=conn.requester_id,
        recipient_id=conn.recipient_id,
        status=conn.status.value,
    )


@app.post("/connections/{connection_id}/accept", response_model=ConnectionOut)
def accept_connection(connection_id: str, acceptor_id: str) -> ConnectionOut:
    """Accept a pending connection request (AC#6)."""
    ok = _connections.accept_request(connection_id, acceptor_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="connection not found, wrong acceptor, or not pending",
        )
    conn = _connections.get_connection(connection_id)
    assert conn is not None
    return ConnectionOut(
        id=conn.id,
        requester_id=conn.requester_id,
        recipient_id=conn.recipient_id,
        status=conn.status.value,
    )


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------


@app.post("/messages", status_code=status.HTTP_201_CREATED, response_model=MessageOut)
def send_message(body: MessageIn) -> MessageOut:
    """Send a message (AC#9, AC#7).

    Refused with a machine-readable reason when the connection is in any state
    other than ACCEPTED:
    - "not_connected": no connection exists between sender and recipient.
    - "connection_pending": a connection exists but has not yet been accepted.
    - "blocked": one party has blocked the other.
    """
    msg, reason = _messages.send(body.sender_id, body.recipient_id, body.body)
    if msg is None:
        code = {
            "blocked": status.HTTP_403_FORBIDDEN,
            "not_connected": status.HTTP_403_FORBIDDEN,
            "connection_pending": status.HTTP_403_FORBIDDEN,
            "contact_removed": status.HTTP_403_FORBIDDEN,  # AC#14
        }.get(reason or "", status.HTTP_422_UNPROCESSABLE_ENTITY)
        raise HTTPException(status_code=code, detail=reason)
    return MessageOut(
        id=msg.id, sender_id=msg.sender_id, recipient_id=msg.recipient_id, body=msg.body
    )


@app.get("/messages/{user1_id}/{user2_id}", response_model=list[MessageOut])
def get_messages(user1_id: str, user2_id: str) -> list[MessageOut]:
    """Return all messages exchanged between two users (AC#6)."""
    return [
        MessageOut(id=m.id, sender_id=m.sender_id, recipient_id=m.recipient_id, body=m.body)
        for m in _messages.get_messages(user1_id, user2_id)
    ]


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


@app.post("/blocks", status_code=status.HTTP_204_NO_CONTENT)
def block_user(body: BlockIn) -> None:
    """Block a user (AC#7 / P5)."""
    if not body.blocker_id.strip() or not body.blocked_id.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="blank id")
    _profiles.block(body.blocker_id, body.blocked_id)


@app.get("/blocks/{blocker_id}/{blocked_id}")
def check_block(blocker_id: str, blocked_id: str) -> dict[str, bool]:
    """Check whether blocker_id has blocked blocked_id."""
    return {"blocked": _profiles.is_blocked(blocker_id, blocked_id)}


@app.get("/may-contact/{a_id}/{b_id}")
def check_may_contact(a_id: str, b_id: str) -> dict[str, bool]:
    """Check whether a and b may contact each other (bidirectional block check).

    Returns False if either party has blocked the other — the #86 fix.
    """
    return {"may_contact": may_contact(_profiles, a_id, b_id)}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _report_out(report: Report) -> ReportOut:
    return ReportOut(
        id=report.id,
        reporter_id=report.reporter_id,
        target_id=report.target_id,
        target_kind=report.target_kind.value,
        reason=report.reason.value,
        additional_text=report.additional_text,
        immediate_harm=report.immediate_harm,
        queue_status=report.queue_status.value,
        resolution_outcome=(
            report.resolution_outcome.value if report.resolution_outcome is not None else None
        ),
        resolved_at=report.resolved_at,
    )


@app.post("/reports", status_code=status.HTTP_201_CREATED, response_model=ReportOut)
def submit_report(body: ReportIn) -> ReportOut:
    """Submit a report (AC#8, AC#12 / P5).

    The report enters the review queue in the 'accepted' state.
    Setting immediate_harm=True places the report ahead of all non-harm reports
    in the queue, regardless of when each was submitted (AC#12).
    """
    report = _reports.submit(
        reporter_id=body.reporter_id,
        target_id=body.target_id,
        target_kind=body.target_kind,
        reason=body.reason,
        additional_text=body.additional_text,
        immediate_harm=body.immediate_harm,
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid report (blank id or additional_text too long)",
        )
    return _report_out(report)


@app.get("/reports/queue", response_model=list[ReportOut])
def get_review_queue() -> list[ReportOut]:
    """Return all reports in review-queue order (AC#12).

    Reports citing an immediate risk of harm appear first; within each
    tier reports are ordered by submission time (oldest first).
    All reports are in the 'accepted' state on entry.
    """
    return [_report_out(r) for r in _reports.get_queue()]


@app.post("/reports/{report_id}/resolve", response_model=ReportOut)
def resolve_report(report_id: str, body: ResolveReportIn) -> ReportOut:
    """Resolve a report with one of the three permitted outcomes (AC#13).

    Accepted outcomes: no_action, warning, contact_removal.
    Any other value is rejected (Pydantic validation refuses it before this
    handler runs, so only the three enum values ever reach the store).

    On success, records the outcome and the resolution timestamp on the report
    and returns the updated report.  The report moves from queue_status
    'accepted' to 'resolved'.

    Refusals:
    - 404 when no report with report_id exists.
    - 409 when the report has already been resolved (idempotent resolution is
      not permitted; a resolved report is immutable).
    """
    report, reason = _reports.resolve(report_id, body.outcome)
    if report is None:
        code = {
            "not_found": status.HTTP_404_NOT_FOUND,
            "already_resolved": status.HTTP_409_CONFLICT,
        }.get(reason or "", status.HTTP_422_UNPROCESSABLE_ENTITY)
        raise HTTPException(status_code=code, detail=reason)
    # AC#14: contact_removal outcome flags the reported person so they cannot
    # send connection requests or messages to anyone from this point forward.
    if body.outcome == ReportResolutionOutcome.CONTACT_REMOVAL:
        if report.target_kind == ReportTargetKind.USER:
            _profiles.set_contact_removed(report.target_id)
        else:
            # Report is against a message — flag the message's sender.
            msg = _messages.find(report.target_id)
            if msg is not None:
                _profiles.set_contact_removed(msg.sender_id)
    return _report_out(report)


@app.get("/profiles/{profile_id}/contact-status", response_model=ContactStatusOut)
def get_contact_status(profile_id: str) -> ContactStatusOut:
    """Return the contact removal status for a profile (AC#14).

    When contact_removed is True the reason field carries the machine-readable
    reason ("contact_removal") so callers can present an accurate message and
    auditors can trace the decision.
    """
    removed = _profiles.is_contact_removed(profile_id)
    return ContactStatusOut(
        contact_removed=removed,
        reason="contact_removal" if removed else None,
    )
