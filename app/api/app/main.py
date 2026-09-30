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

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .auth import require_auth
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
from .retention import RETENTION_POLICY
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


class AccountDeletionOut(BaseModel):
    """Response body returned when an account is deleted (AC#15).

    Reports what was removed and what was retained so the caller and any
    auditor can confirm exactly what happened — no silent side-effects.
    """

    deleted_profile_id: str
    deleted_interest_tags_count: int  # interests + activities removed with the profile
    deleted_messages_count: int       # messages removed (not subject to retention)
    retained_blocks_count: int        # block records kept per 24-month retention policy
    retained_reports_count: int       # report records kept per 24-month retention policy


class RetentionPolicyOut(BaseModel):
    """Data-retention policy response (C16).

    All durations readable from this one endpoint — the backend's single
    source of truth for how long each category of data is kept.
    """

    messages_months: int
    blocks_months: int
    reports_months: int
    other_days: int
    description: dict[str, str]


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


@app.get("/profiles/me", dependencies=[Depends(require_auth)])
def profile_me() -> dict[str, str]:
    # ponytail: hardcoded placeholder until auth (step 3) supplies a real
    # user id. The ProfileStore already supports real lookups via /profiles/{id}.
    return {
        "id": "placeholder",
        "display_name": "Demo Friend",
        "bio": "This profile is a placeholder until step 2 adds persistence.",
    }


@app.post("/profiles", status_code=status.HTTP_201_CREATED, response_model=ProfileOut, dependencies=[Depends(require_auth)])
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


@app.get("/profiles/{profile_id}", response_model=ProfileOut, dependencies=[Depends(require_auth)])
def get_profile(profile_id: str) -> ProfileOut:
    profile = _profiles.find(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile_not_found")
    return _profile_out(profile)


@app.patch("/profiles/{profile_id}/availability", response_model=ProfileOut, dependencies=[Depends(require_auth)])
def toggle_availability(profile_id: str, open_to_friends: bool) -> ProfileOut:
    """Toggle the 'open to new friends' status (AC#6).

    Turning it off removes the profile from every other person's discovery
    results on the next query (the discover() function filters open_to_friends).
    All other profile fields — including age_assurance_status — are preserved.
    """
    profile = _profiles.find(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile_not_found")
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


@app.get("/discovery/{searcher_id}", response_model=list[DiscoveryResultOut], dependencies=[Depends(require_auth)])
def discovery(
    searcher_id: str,
    radius_km: int = 25,
    lat: float | None = None,
    lon: float | None = None,
) -> list[DiscoveryResultOut]:
    """Return profiles the searcher may discover (AC#2, AC#3, AC#4, AC#5, AC#7, AC#17).

    Filters applied: age assurance passed (AC#5), open_to_friends=True,
    age-bracket isolation, may_contact (bidirectional block check — the #86
    fix), radius.

    Returns 403 with a machine-readable reason when the searcher's own age
    assurance has not passed, naming whether the status is 'unrecorded' or
    'failed' so the client can present the right message (AC#5).

    AC#17 — coarse location privacy:
    ``lat`` and ``lon`` are optional query parameters that supply a coarse
    location for this query only.  They are used transiently for the radius
    filter and are never written to any durable table and never returned by
    any read endpoint.  The searcher's stored profile is not modified.
    """
    if radius_km not in VALID_SEARCH_RADII:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_radius",
        )
    searcher = _profiles.find(searcher_id)
    if searcher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile_not_found")
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
    # AC#17: build a transient GeoLocation from the query params when both are
    # present.  This object is NEVER written to the store — it exists only for
    # the duration of this request.
    query_location: GeoLocation | None = (
        GeoLocation(lat=lat, lon=lon) if lat is not None and lon is not None else None
    )
    results = discover(_profiles, searcher, radius_km=radius_km, query_location=query_location)
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


@app.post("/profiles/{profile_id}/age-assurance", response_model=ProfileOut, dependencies=[Depends(require_auth)])
def record_age_assurance(profile_id: str, body: AgeAssuranceIn) -> ProfileOut:
    """Record the age assurance result for a profile (AC#5).

    Accepted statuses: 'passed', 'failed'.  (Setting to 'unrecorded' is not
    a valid operation — that is the initial state on creation.)
    """
    profile = _profiles.find(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile_not_found")
    if body.status == AgeAssuranceStatus.UNRECORDED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="age_assurance_status_immutable",
        )
    _profiles.set_age_assurance(profile_id, body.status)
    updated = _profiles.find(profile_id)
    assert updated is not None
    return _profile_out(updated)


# ---------------------------------------------------------------------------
# Connection requests
# ---------------------------------------------------------------------------


@app.post("/connections", status_code=status.HTTP_201_CREATED, response_model=ConnectionOut, dependencies=[Depends(require_auth)])
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


@app.post("/connections/{connection_id}/accept", response_model=ConnectionOut, dependencies=[Depends(require_auth)])
def accept_connection(connection_id: str, acceptor_id: str) -> ConnectionOut:
    """Accept a pending connection request (AC#6)."""
    ok, reason = _connections.accept_request(connection_id, acceptor_id)
    if not ok:
        code = {
            "connection_not_found": status.HTTP_404_NOT_FOUND,
            "wrong_acceptor": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "connection_not_pending": status.HTTP_409_CONFLICT,
        }.get(reason or "", status.HTTP_422_UNPROCESSABLE_ENTITY)
        raise HTTPException(status_code=code, detail=reason)
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


@app.post("/messages", status_code=status.HTTP_201_CREATED, response_model=MessageOut, dependencies=[Depends(require_auth)])
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


@app.get("/messages/{user1_id}/{user2_id}", response_model=list[MessageOut], dependencies=[Depends(require_auth)])
def get_messages(user1_id: str, user2_id: str) -> list[MessageOut]:
    """Return all messages exchanged between two users (AC#6)."""
    return [
        MessageOut(id=m.id, sender_id=m.sender_id, recipient_id=m.recipient_id, body=m.body)
        for m in _messages.get_messages(user1_id, user2_id)
    ]


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------


@app.post("/blocks", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_auth)])
def block_user(body: BlockIn) -> None:
    """Block a user (AC#7 / P5)."""
    if not body.blocker_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="blank_blocker_id"
        )
    if not body.blocked_id.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="blank_blocked_id"
        )
    _profiles.block(body.blocker_id, body.blocked_id)


@app.get("/blocks/{blocker_id}/{blocked_id}", dependencies=[Depends(require_auth)])
def check_block(blocker_id: str, blocked_id: str) -> dict[str, bool]:
    """Check whether blocker_id has blocked blocked_id."""
    return {"blocked": _profiles.is_blocked(blocker_id, blocked_id)}


@app.get("/may-contact/{a_id}/{b_id}", dependencies=[Depends(require_auth)])
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


@app.post("/reports", status_code=status.HTTP_201_CREATED, response_model=ReportOut, dependencies=[Depends(require_auth)])
def submit_report(body: ReportIn) -> ReportOut:
    """Submit a report (AC#8, AC#12 / P5).

    The report enters the review queue in the 'accepted' state.
    Setting immediate_harm=True places the report ahead of all non-harm reports
    in the queue, regardless of when each was submitted (AC#12).
    """
    report, reason = _reports.submit(
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
            detail=reason,
        )
    return _report_out(report)


@app.get("/reports/queue", response_model=list[ReportOut], dependencies=[Depends(require_auth)])
def get_review_queue() -> list[ReportOut]:
    """Return all reports in review-queue order (AC#12).

    Reports citing an immediate risk of harm appear first; within each
    tier reports are ordered by submission time (oldest first).
    All reports are in the 'accepted' state on entry.
    """
    return [_report_out(r) for r in _reports.get_queue()]


@app.post("/reports/{report_id}/resolve", response_model=ReportOut, dependencies=[Depends(require_auth)])
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


@app.get("/profiles/{profile_id}/contact-status", response_model=ContactStatusOut, dependencies=[Depends(require_auth)])
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


# ---------------------------------------------------------------------------
# Account deletion
# ---------------------------------------------------------------------------


@app.delete("/profiles/{profile_id}", response_model=AccountDeletionOut, dependencies=[Depends(require_auth)])
def delete_account(profile_id: str) -> AccountDeletionOut:
    """Delete an account and report exactly what was removed and what was retained (AC#15).

    Deleted (not subject to retention):
    - Profile row (display name, bio, age, open_to_friends flag, …)
    - Interest tags (interests + activities fields)
    - Messages sent by or addressed to this account

    Retained per the 24-month post-closure retention policy:
    - Block records (either direction) — necessary to keep a blocked person blocked
    - Reports filed by or against this account — necessary for trust and safety audit

    The response names every category so the caller and any auditor can
    confirm that nothing was silently kept or silently discarded (AC#15,
    data-retention policy).
    """
    profile = _profiles.find(profile_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="profile_not_found")

    # Count interest tags (interests list + activities list) before deletion.
    tags_count = len(profile.interests) + len(profile.activities)

    # Count block records that will be retained (both directions).
    blocks_count = _profiles.get_blocks_count(profile_id)

    # Count reports that will be retained (filed by or against this account).
    reports_against_ids = {r.id for r in _reports.get_reports_against(profile_id)}
    reports_by_ids = {r.id for r in _reports.get_reports_by(profile_id)}
    reports_count = len(reports_against_ids | reports_by_ids)

    # Delete messages first (while the profile still exists for reference).
    messages_deleted = _messages.delete_messages_for(profile_id)

    # Delete the profile (blocks and reports are deliberately preserved).
    _profiles.delete(profile_id)

    return AccountDeletionOut(
        deleted_profile_id=profile_id,
        deleted_interest_tags_count=tags_count,
        deleted_messages_count=messages_deleted,
        retained_blocks_count=blocks_count,
        retained_reports_count=reports_count,
    )


# ---------------------------------------------------------------------------
# Retention policy (C16)
# ---------------------------------------------------------------------------


@app.get("/retention-policy", response_model=RetentionPolicyOut)
def get_retention_policy() -> RetentionPolicyOut:
    """Return the platform data-retention policy (C16).

    All retention durations are defined in app/retention.py and surfaced here.
    This is the single place in the backend where the policy is readable:

    - Messages: kept for 24 months from account closure.
    - Blocks:   kept for 24 months after closure.
    - Reports:  kept for 24 months after closure.
    - Other:    profile, interest tags, connections and everything else is
                purged within 30 days of account deletion.
    """
    return RetentionPolicyOut(
        messages_months=RETENTION_POLICY.messages_months,
        blocks_months=RETENTION_POLICY.blocks_months,
        reports_months=RETENTION_POLICY.reports_months,
        other_days=RETENTION_POLICY.other_days,
        description={
            "messages": (
                f"Kept for {RETENTION_POLICY.messages_months} months from account closure."
            ),
            "blocks": (
                f"Kept for {RETENTION_POLICY.blocks_months} months after closure."
            ),
            "reports": (
                f"Kept for {RETENTION_POLICY.reports_months} months after closure."
            ),
            "other": (
                f"Profile, tags, connections and all other personal data purged "
                f"within {RETENTION_POLICY.other_days} days of deletion."
            ),
        },
    )
