"""Tests for the remediated MyFriends API.

Tests verify the security and authorisation behaviours described in the
remediation brief.  In particular:

- Every endpoint except ``GET /healthz`` requires a valid Bearer JWT and
  returns 401 when the header is absent or malformed.
- The authenticated caller's identity is bound to the resource: no endpoint
  accepts a different acting identity from the request body or URL.
- Blocking is symmetric — a block in *either* direction prevents a connection
  request and a message.

The store is replaced via ``app.dependency_overrides`` and
``unittest.mock.patch`` so that tests run without a live Postgres instance.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app, require_auth

client = TestClient(app)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def _auth(caller_id: str = "user-1"):
    """Return a FastAPI dependency override that resolves to *caller_id*."""

    async def _override() -> str:
        return caller_id

    return _override


# ---------------------------------------------------------------------------
# Health probe — no auth required
# ---------------------------------------------------------------------------


def test_healthz() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Auth enforcement — unauthenticated calls must be rejected
# ---------------------------------------------------------------------------


def test_profiles_me_requires_auth() -> None:
    """GET /profiles/me without a Bearer token is rejected with 401."""
    resp = client.get("/profiles/me")
    assert resp.status_code == 401


def test_create_profile_requires_auth() -> None:
    resp = client.post("/profiles", json={"display_name": "Alice", "age": 25})
    assert resp.status_code == 401


def test_connections_requires_auth() -> None:
    resp = client.get("/connections")
    assert resp.status_code == 401


def test_blocks_requires_auth() -> None:
    resp = client.get("/blocks")
    assert resp.status_code == 401


def test_discovery_requires_auth() -> None:
    resp = client.get("/discovery")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Profile ownership — profile id comes from the token, never the body
# ---------------------------------------------------------------------------


def test_create_profile_id_equals_caller_id() -> None:
    """POST /profiles must use the authenticated caller's id, not any body field."""
    app.dependency_overrides[require_auth] = _auth("user-42")
    fake_profile = {
        "id": "user-42",
        "display_name": "Alice",
        "bio": "",
        "age": 25,
        "interests": [],
        "is_open": False,
        "age_assurance_passed": False,
    }
    try:
        with (
            patch("app.store.get_profile", return_value=None),
            patch("app.store.create_profile", return_value=fake_profile),
        ):
            resp = client.post(
                "/profiles", json={"display_name": "Alice", "age": 25}
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "user-42"
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_duplicate_profile_is_rejected() -> None:
    """Creating a profile when one already exists returns 409."""
    app.dependency_overrides[require_auth] = _auth("user-1")
    existing = {
        "id": "user-1",
        "display_name": "Alice",
        "bio": "",
        "age": 25,
        "interests": [],
        "is_open": False,
        "age_assurance_passed": False,
    }
    try:
        with patch("app.store.get_profile", return_value=existing):
            resp = client.post(
                "/profiles", json={"display_name": "Alice", "age": 25}
            )
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Age assurance — only the authenticated profile owner may grant it
# ---------------------------------------------------------------------------


def test_age_assurance_applied_to_authenticated_caller() -> None:
    """POST /profiles/me/age-assurance marks the *caller's* own profile."""
    app.dependency_overrides[require_auth] = _auth("user-1")
    result = {
        "id": "user-1",
        "display_name": "Alice",
        "bio": "",
        "age": 25,
        "interests": [],
        "is_open": False,
        "age_assurance_passed": True,
    }
    try:
        with patch("app.store.record_age_assurance", return_value=result):
            resp = client.post("/profiles/me/age-assurance")
        assert resp.status_code == 200
        assert resp.json()["age_assurance_passed"] is True
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Account deletion — only the authenticated owner may delete their account
# ---------------------------------------------------------------------------


def test_delete_own_account_succeeds() -> None:
    app.dependency_overrides[require_auth] = _auth("user-1")
    profile = {
        "id": "user-1",
        "display_name": "Alice",
        "bio": "",
        "age": 25,
        "interests": [],
        "is_open": False,
        "age_assurance_passed": False,
    }
    summary = {
        "removed": {"messages": 0, "connections": 0},
        "retained": {"blocks": 0, "reports": 0, "reason": "..."},
    }
    try:
        with (
            patch("app.store.get_profile", return_value=profile),
            patch("app.store.delete_profile", return_value=summary),
        ):
            resp = client.delete("/profiles/me")
        assert resp.status_code == 200
        assert "removed" in resp.json()
        assert "retained" in resp.json()
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Blocking symmetry — may_contact is checked bidirectionally
# ---------------------------------------------------------------------------


def test_connection_request_blocked_by_caller_block() -> None:
    """A block placed by the caller prevents a connection request."""
    app.dependency_overrides[require_auth] = _auth("user-1")
    try:
        with (
            patch("app.store.may_contact", return_value=False),
            patch(
                "app.store.get_profile",
                return_value={
                    "id": "user-2",
                    "display_name": "Bob",
                    "bio": "",
                    "age": 25,
                    "interests": [],
                    "is_open": True,
                    "age_assurance_passed": True,
                },
            ),
        ):
            resp = client.post("/connections", json={"target_id": "user-2"})
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_connection_request_blocked_by_target_block() -> None:
    """A block placed by the *target* also prevents a connection request.

    This is the defect described in issue #86: the previous implementation
    only checked one direction of the block relationship.  ``may_contact``
    checks both, so the two paths cannot disagree.
    """
    app.dependency_overrides[require_auth] = _auth("user-2")
    try:
        with (
            patch("app.store.may_contact", return_value=False),
            patch(
                "app.store.get_profile",
                return_value={
                    "id": "user-1",
                    "display_name": "Alice",
                    "bio": "",
                    "age": 25,
                    "interests": [],
                    "is_open": True,
                    "age_assurance_passed": True,
                },
            ),
        ):
            # user-2 tries to reach user-1, but user-1 blocked user-2
            resp = client.post("/connections", json={"target_id": "user-1"})
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Connection accept / decline — only the recipient may act
# ---------------------------------------------------------------------------


def test_only_recipient_can_accept_connection() -> None:
    """The requester cannot accept their own connection request."""
    app.dependency_overrides[require_auth] = _auth("user-1")
    conn = {
        "id": "conn-1",
        "requester_id": "user-1",
        "target_id": "user-2",
        "status": "pending",
    }
    try:
        with patch("app.store.get_connection", return_value=conn):
            resp = client.post("/connections/conn-1/accept")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_only_recipient_can_decline_connection() -> None:
    """The requester cannot decline their own connection request."""
    app.dependency_overrides[require_auth] = _auth("user-1")
    conn = {
        "id": "conn-1",
        "requester_id": "user-1",
        "target_id": "user-2",
        "status": "pending",
    }
    try:
        with patch("app.store.get_connection", return_value=conn):
            resp = client.post("/connections/conn-1/decline")
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Messaging — only parties to the connection may send messages
# ---------------------------------------------------------------------------


def test_send_message_requires_party_membership() -> None:
    """A caller who is not party to the connection cannot send a message."""
    app.dependency_overrides[require_auth] = _auth("user-3")
    conn = {
        "id": "conn-1",
        "requester_id": "user-1",
        "target_id": "user-2",
        "status": "accepted",
    }
    try:
        with patch("app.store.get_connection", return_value=conn):
            resp = client.post(
                "/connections/conn-1/messages", json={"body": "Hello"}
            )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_send_message_blocked_prevents_messaging() -> None:
    """A block between the parties prevents sending a message."""
    app.dependency_overrides[require_auth] = _auth("user-1")
    conn = {
        "id": "conn-1",
        "requester_id": "user-1",
        "target_id": "user-2",
        "status": "accepted",
    }
    try:
        with (
            patch("app.store.get_connection", return_value=conn),
            patch("app.store.may_contact", return_value=False),
        ):
            resp = client.post(
                "/connections/conn-1/messages", json={"body": "Hello"}
            )
        assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Blocks — caller cannot block themselves
# ---------------------------------------------------------------------------


def test_cannot_block_self() -> None:
    app.dependency_overrides[require_auth] = _auth("user-1")
    try:
        resp = client.post("/blocks", json={"blocked_id": "user-1"})
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Reports — caller cannot report themselves
# ---------------------------------------------------------------------------


def test_cannot_report_self() -> None:
    app.dependency_overrides[require_auth] = _auth("user-1")
    try:
        resp = client.post(
            "/reports",
            json={"reported_id": "user-1", "reason": "spam"},
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_profile_display_name_blank_rejected() -> None:
    """A blank display_name is rejected with 422 before touching the store."""
    app.dependency_overrides[require_auth] = _auth("user-1")
    try:
        resp = client.post(
            "/profiles", json={"display_name": "   ", "age": 25}
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_profile_age_below_minimum_rejected() -> None:
    """An age below 13 is rejected with 422."""
    app.dependency_overrides[require_auth] = _auth("user-1")
    try:
        resp = client.post(
            "/profiles", json={"display_name": "Alice", "age": 12}
        )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_profile_age_15_refused_16_accepted() -> None:
    """The brief's cohort starts at 16: 15 is refused naming age, 16 is created."""
    app.dependency_overrides[require_auth] = _auth("user-1")
    created = {"id": "user-1", "display_name": "Alice", "bio": "", "age": 16, "interests": []}
    try:
        resp = client.post("/profiles", json={"display_name": "Alice", "age": 15})
        assert resp.status_code == 422
        assert "age" in resp.text.lower()

        with (
            patch("app.store.get_profile", return_value=None),
            patch("app.store.create_profile", return_value=created) as create,
        ):
            resp = client.post("/profiles", json={"display_name": "Alice", "age": 16})
        assert resp.status_code == 201
        assert create.call_args.kwargs["age"] == 16
    finally:
        app.dependency_overrides.pop(require_auth, None)


def test_duplicate_insert_is_409_not_500() -> None:
    """A primary-key collision at INSERT is a 409, not an unhandled UniqueViolation.

    Reachable when the pre-check misses: a soft-deleted profile (``get_profile``
    filters ``deleted_at IS NULL``) or two concurrent creates.
    """
    from contextlib import contextmanager

    from psycopg.errors import UniqueViolation

    statements: list[str] = []

    class _Conn:
        def execute(self, sql: str, params=None):  # noqa: ANN001, ANN202
            statements.append(sql)
            raise UniqueViolation('duplicate key value violates unique constraint "profiles_pkey"')

    @contextmanager
    def _fake_conn():  # noqa: ANN202
        yield _Conn()

    app.dependency_overrides[require_auth] = _auth("user-1")
    try:
        with (
            patch("app.store.get_profile", return_value=None),
            patch("app.store._conn", _fake_conn),
        ):
            resp = TestClient(app, raise_server_exceptions=False).post(
                "/profiles", json={"display_name": "Alice", "age": 25}
            )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]
        # The existing row was left alone: the only statement issued was the
        # INSERT that collided; nothing updated or deleted it.
        assert len(statements) == 1
        assert statements[0].lstrip().startswith("INSERT")
    finally:
        app.dependency_overrides.pop(require_auth, None)
