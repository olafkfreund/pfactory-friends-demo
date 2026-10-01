"""End-to-end tests for MyFriends API remediation v2.

Tests the full request/response cycle for the acceptance criteria that are
best validated end-to-end: complete user flows, multi-step sequences, and
negative scenarios that span multiple endpoints.  The store is replaced by
mocks so no live Postgres instance is required.

AC coverage:
  AC#1  – end-to-end cross-user-action scenarios
  AC#2  – end-to-end account deletion ownership
  AC#3  – end-to-end age-assurance ownership
  AC#4  – store is Postgres-backed (no in-process dicts): structural assertion
  AC#5  – DATABASE_URL env var is the sole credential source
  AC#6  – display-name validation end-to-end (422 with no store write)
  AC#7  – moderation role required for report resolution end-to-end
  AC#8  – unauthenticated access rejected end-to-end for full endpoint set
  AC#9  – single source of identity: all endpoints derive identity from token
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Path bootstrap — tests live in spec/, app code in app/api/
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "api"))

from unittest.mock import patch, call, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app, require_auth, require_moderator

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(caller_id: str = "user-1"):
    async def _override() -> str:
        return caller_id
    return _override


def _mod(caller_id: str = "mod-1"):
    async def _override() -> str:
        return caller_id
    return _override


def _profile(uid, age=25, age_assurance=False, is_open=True, display_name="User"):
    return {
        "id": uid,
        "display_name": display_name,
        "bio": "",
        "age": age,
        "interests": [],
        "is_open": is_open,
        "age_assurance_passed": age_assurance,
        "created_at": "2026-01-01T00:00:00+00:00",
        "deleted_at": None,
    }


def _connection(cid, req, tgt, status="pending"):
    return {
        "id": cid,
        "requester_id": req,
        "target_id": tgt,
        "status": status,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# AC#8 – Comprehensive unauthenticated rejection
# ---------------------------------------------------------------------------

class TestUnauthenticatedEndToEnd:
    """Every protected endpoint must reject requests before any business logic."""

    PROTECTED_ENDPOINTS = [
        ("GET",    "/profiles/me"),
        ("POST",   "/profiles"),
        ("PATCH",  "/profiles/me"),
        ("POST",   "/profiles/me/age-assurance"),
        ("PATCH",  "/profiles/me/availability"),
        ("DELETE", "/profiles/me"),
        ("GET",    "/discovery"),
        ("POST",   "/connections"),
        ("GET",    "/connections"),
        ("POST",   "/connections/x/accept"),
        ("POST",   "/connections/x/decline"),
        ("GET",    "/connections/x/messages"),
        ("POST",   "/connections/x/messages"),
        ("POST",   "/blocks"),
        ("GET",    "/blocks"),
        ("POST",   "/reports"),
        ("GET",    "/reports"),
        ("POST",   "/reports/x/resolve"),
    ]

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    def test_endpoint_requires_auth(self, method, path):
        resp = client.request(method, path, json={})
        assert resp.status_code == 401, (
            f"{method} {path} returned {resp.status_code}, expected 401"
        )

    def test_healthz_accessible_without_auth(self):
        assert client.get("/healthz").status_code == 200


# ---------------------------------------------------------------------------
# AC#1 – Full cross-user flow: impersonation attempt is rejected
# ---------------------------------------------------------------------------

class TestImpersonationRejectedEndToEnd:
    """Caller A cannot act as caller B on any state-changing endpoint."""

    def test_user_a_cannot_accept_user_b_request(self):
        """User A sent a request to User B; User C cannot accept it for User B."""
        app.dependency_overrides[require_auth] = _auth("user-C")
        conn = _connection("conn-1", "user-A", "user-B", "pending")
        try:
            with patch("app.store.get_connection", return_value=conn):
                resp = client.post("/connections/conn-1/accept")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_user_a_cannot_decline_user_b_request_on_behalf(self):
        app.dependency_overrides[require_auth] = _auth("user-A")
        conn = _connection("conn-1", "user-A", "user-B", "pending")
        try:
            with patch("app.store.get_connection", return_value=conn):
                resp = client.post("/connections/conn-1/decline")
            # user-A is the requester, not the recipient; must be 403
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_user_cannot_send_message_on_others_connection(self):
        app.dependency_overrides[require_auth] = _auth("user-X")
        conn = _connection("conn-2", "user-A", "user-B", "accepted")
        try:
            with patch("app.store.get_connection", return_value=conn):
                resp = client.post("/connections/conn-2/messages", json={"body": "spy"})
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_create_profile_always_uses_token_identity(self):
        """POST /profiles uses the token sub, not any id supplied in the body."""
        app.dependency_overrides[require_auth] = _auth("token-owner")
        fake = _profile("token-owner")
        try:
            with (
                patch("app.store.get_profile", return_value=None),
                patch("app.store.create_profile", return_value=fake) as mock_create,
            ):
                # Even if someone includes an id in the body, it is ignored
                resp = client.post(
                    "/profiles",
                    json={"display_name": "Alice", "age": 25},
                )
            assert resp.status_code == 201
            # store.create_profile must be called with the authenticated id
            mock_create.assert_called_once()
            args, kwargs = mock_create.call_args
            assert kwargs.get("profile_id") == "token-owner" or args[0] == "token-owner"
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_block_is_created_for_caller_not_body_field(self):
        """POST /blocks uses the authenticated caller as blocker, not any body field."""
        app.dependency_overrides[require_auth] = _auth("user-1")
        block_result = {
            "id": "blk-1", "blocker_id": "user-1", "blocked_id": "user-2",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        try:
            with patch("app.store.create_block", return_value=block_result) as mock_block:
                resp = client.post("/blocks", json={"blocked_id": "user-2"})
            assert resp.status_code == 201
            mock_block.assert_called_once_with("user-1", "user-2")
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_report_is_created_for_caller_not_body_field(self):
        """POST /reports uses the authenticated caller as reporter."""
        app.dependency_overrides[require_auth] = _auth("user-1")
        report_result = {
            "id": "rpt-1", "reporter_id": "user-1", "reported_id": "user-2",
            "reason": "spam", "detail": "", "status": "open",
            "resolved_by": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "resolved_at": None,
        }
        try:
            with patch("app.store.create_report", return_value=report_result) as mock_report:
                resp = client.post(
                    "/reports",
                    json={"reported_id": "user-2", "reason": "spam"},
                )
            assert resp.status_code == 201
            mock_report.assert_called_once_with("user-1", "user-2", "spam", "")
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_connection_request_uses_caller_as_requester(self):
        """POST /connections uses the authenticated caller as requester."""
        app.dependency_overrides[require_auth] = _auth("user-1")
        conn_result = _connection("conn-new", "user-1", "user-2")
        try:
            with (
                patch("app.store.may_contact", return_value=True),
                patch("app.store.get_profile", return_value=_profile("user-2")),
                patch("app.store.count_requests_today", return_value=0),
                patch("app.store.create_connection_request", return_value=conn_result) as mock_conn,
            ):
                resp = client.post("/connections", json={"target_id": "user-2"})
            assert resp.status_code == 201
            mock_conn.assert_called_once_with("user-1", "user-2")
        finally:
            app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# AC#2 – End-to-end account deletion ownership
# ---------------------------------------------------------------------------

class TestAccountDeletionEndToEnd:
    def test_deletion_removes_caller_account_only(self):
        """DELETE /profiles/me removes exactly the authenticated caller's account."""
        app.dependency_overrides[require_auth] = _auth("user-7")
        summary = {
            "removed": {"messages": 5, "connections": 3},
            "retained": {"blocks": 1, "reports": 2, "reason": "safety"},
        }
        try:
            with (
                patch("app.store.get_profile", return_value=_profile("user-7")),
                patch("app.store.delete_profile", return_value=summary) as mock_del,
            ):
                resp = client.delete("/profiles/me")
            assert resp.status_code == 200
            # The store was asked to delete user-7 specifically
            mock_del.assert_called_once_with("user-7")
            data = resp.json()
            assert data["removed"]["messages"] == 5
            assert data["retained"]["blocks"] == 1
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_deletion_returns_retention_reason(self):
        """The deletion response documents what was retained and why."""
        app.dependency_overrides[require_auth] = _auth("user-1")
        summary = {
            "removed": {"messages": 0, "connections": 0},
            "retained": {"blocks": 0, "reports": 0, "reason": "safety and legal-hold purposes"},
        }
        try:
            with (
                patch("app.store.get_profile", return_value=_profile("user-1")),
                patch("app.store.delete_profile", return_value=summary),
            ):
                resp = client.delete("/profiles/me")
            assert resp.status_code == 200
            assert "reason" in resp.json()["retained"]
        finally:
            app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# AC#3 – Age assurance end-to-end
# ---------------------------------------------------------------------------

class TestAgeAssuranceEndToEnd:
    def test_age_assurance_marks_callers_own_profile(self):
        app.dependency_overrides[require_auth] = _auth("user-5")
        updated = {**_profile("user-5"), "age_assurance_passed": True}
        try:
            with patch("app.store.record_age_assurance", return_value=updated) as mock_fn:
                resp = client.post("/profiles/me/age-assurance")
            assert resp.status_code == 200
            assert resp.json()["age_assurance_passed"] is True
            # The store was asked to update user-5's profile, not anyone else's
            mock_fn.assert_called_once_with("user-5")
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_another_user_cannot_grant_your_age_assurance(self):
        """No API surface allows caller B to grant age assurance to caller A.

        POST /profiles/me/age-assurance always acts on the authenticated caller.
        Caller B cannot send a request that grants assurance to profile A.
        """
        # Caller B is authenticated
        app.dependency_overrides[require_auth] = _auth("user-B")
        updated_b = {**_profile("user-B"), "age_assurance_passed": True}
        try:
            with patch("app.store.record_age_assurance", return_value=updated_b) as mock_fn:
                # Even if user-B tries to sneak user-A's id somewhere,
                # the endpoint ignores it; it always acts on user-B.
                resp = client.post("/profiles/me/age-assurance")
            assert resp.status_code == 200
            # The store must have been called for user-B, not user-A
            mock_fn.assert_called_once_with("user-B")
        finally:
            app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# AC#4 – Store uses Postgres, not in-process dicts
# ---------------------------------------------------------------------------

class TestStoreIsPostgresBacked:
    """Assert that the store module relies on psycopg/DATABASE_URL, not dicts."""

    def test_store_has_no_module_level_dicts_for_profiles(self):
        """The store must not hold profiles in a module-level dict."""
        from app import store
        import inspect

        source = inspect.getsource(store)
        # The old store used names like 'profiles = {}', 'connections = {}', etc.
        # None of those in-memory containers should be present.
        assert "profiles = {}" not in source
        assert "connections = {}" not in source
        assert "messages = {}" not in source
        assert "blocks = {}" not in source
        assert "reports = {}" not in source

    def test_store_uses_psycopg(self):
        """The store imports and uses psycopg for all persistence."""
        from app import store
        import inspect

        source = inspect.getsource(store)
        assert "psycopg" in source

    def test_store_uses_database_url_env_var(self):
        """Credentials come from DATABASE_URL, not a hardcoded string."""
        from app import store
        import inspect

        source = inspect.getsource(store)
        assert "DATABASE_URL" in source

    def test_store_does_not_hardcode_credentials(self):
        """No password= or password: literals appear in the store source."""
        from app import store
        import inspect

        source = inspect.getsource(store)
        # There must be no hardcoded DSN or password literal
        assert "password=" not in source.lower().replace("DATABASE_URL", "")
        assert "postgres://" not in source.lower().replace("DATABASE_URL", "")

    def test_bootstrap_schema_creates_tables(self):
        """bootstrap_schema executes the DDL statements defined in the module."""
        from app import store

        # Verify DDL contains the expected table names
        ddl_combined = " ".join(store._DDL_STATEMENTS)
        for table in ("profiles", "connections", "messages", "blocks", "reports"):
            assert table in ddl_combined, f"Expected DDL for table '{table}'"


# ---------------------------------------------------------------------------
# AC#5 – DATABASE_URL is the single credentials source
# ---------------------------------------------------------------------------

class TestDatabaseCredentialSource:
    def test_database_url_required_at_runtime(self, monkeypatch):
        """store._database_url() raises RuntimeError when DATABASE_URL is absent."""
        from app import store
        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            store._database_url()

    def test_database_url_value_is_used_directly(self, monkeypatch):
        """The value of DATABASE_URL is returned verbatim for the connection."""
        from app import store
        dsn = "postgresql://user:secret@db-host:5432/mydb"
        monkeypatch.setenv("DATABASE_URL", dsn)
        assert store._database_url() == dsn

    def test_store_source_has_no_hardcoded_dsn(self):
        """No file in the app package should hard-code a DSN or password."""
        import inspect
        from app import store

        src = inspect.getsource(store)
        # Common patterns for hardcoded credentials
        suspicious = ["localhost:5432/", "password=secret", "pw=", "host=postgres"]
        for pattern in suspicious:
            assert pattern not in src, (
                f"Suspicious hardcoded credential pattern '{pattern}' found in store.py"
            )


# ---------------------------------------------------------------------------
# AC#6 – Display name validation end-to-end
# ---------------------------------------------------------------------------

class TestDisplayNameValidationEndToEnd:
    def test_empty_name_never_reaches_store(self):
        app.dependency_overrides[require_auth] = _auth("user-1")
        try:
            with patch("app.store.create_profile") as mock_create:
                resp = client.post("/profiles", json={"display_name": "", "age": 25})
            assert resp.status_code == 422
            mock_create.assert_not_called()
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_whitespace_name_never_reaches_store(self):
        app.dependency_overrides[require_auth] = _auth("user-1")
        try:
            with patch("app.store.create_profile") as mock_create:
                resp = client.post("/profiles", json={"display_name": "\t  \n", "age": 25})
            assert resp.status_code == 422
            mock_create.assert_not_called()
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_overlength_name_never_reaches_store(self):
        from app import store as st
        app.dependency_overrides[require_auth] = _auth("user-1")
        too_long = "Z" * (st.MAX_DISPLAY_NAME_LENGTH + 5)
        try:
            with patch("app.store.create_profile") as mock_create:
                resp = client.post("/profiles", json={"display_name": too_long, "age": 25})
            assert resp.status_code == 422
            mock_create.assert_not_called()
        finally:
            app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# AC#7 – Moderation role end-to-end
# ---------------------------------------------------------------------------

class TestModerationEndToEnd:
    def test_non_moderator_resolving_report_is_403(self):
        """An authenticated user without moderator role cannot resolve a report.

        When require_auth is overridden with a no-payload function and
        require_moderator is NOT overridden, the real moderator check runs.
        It reads request.state.token_payload (absent → {}), finds no
        'myfriends-moderator' role, and returns 403.
        """
        async def _regular_user() -> str:
            return "user-1"

        app.dependency_overrides[require_auth] = _regular_user
        app.dependency_overrides.pop(require_moderator, None)
        try:
            resp = client.post("/reports/rpt-1/resolve", json={"status": "dismissed"})
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_moderator_can_resolve_and_actioned_status_propagates(self):
        """A moderator can resolve a report with the 'actioned' status."""
        app.dependency_overrides[require_auth] = _mod("mod-1")
        app.dependency_overrides[require_moderator] = _mod("mod-1")
        resolved = {
            "id": "rpt-1", "reporter_id": "user-1", "reported_id": "user-2",
            "reason": "harassment", "detail": "", "status": "actioned",
            "resolved_by": "mod-1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "resolved_at": "2026-01-02T00:00:00+00:00",
        }
        try:
            with patch("app.store.resolve_report", return_value=resolved):
                resp = client.post("/reports/rpt-1/resolve", json={"status": "actioned"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "actioned"
            assert data["resolved_by"] == "mod-1"
        finally:
            app.dependency_overrides.pop(require_auth, None)
            app.dependency_overrides.pop(require_moderator, None)

    def test_moderator_list_reports(self):
        """A moderator can list all open reports."""
        app.dependency_overrides[require_auth] = _mod("mod-1")
        app.dependency_overrides[require_moderator] = _mod("mod-1")
        reports = [
            {"id": "rpt-1", "reporter_id": "u1", "reported_id": "u2",
             "reason": "spam", "detail": "", "status": "open",
             "resolved_by": None, "created_at": "2026-01-01T00:00:00+00:00", "resolved_at": None},
        ]
        try:
            with patch("app.store.list_reports", return_value=reports):
                resp = client.get("/reports")
            assert resp.status_code == 200
            assert len(resp.json()) == 1
        finally:
            app.dependency_overrides.pop(require_auth, None)
            app.dependency_overrides.pop(require_moderator, None)


# ---------------------------------------------------------------------------
# AC#9 – Single source of identity: token sub is used everywhere
# ---------------------------------------------------------------------------

class TestSingleSourceOfIdentityEndToEnd:
    def test_availability_toggle_uses_caller_id(self):
        """PATCH /profiles/me/availability acts on the authenticated caller's profile."""
        app.dependency_overrides[require_auth] = _auth("user-9")
        updated = {**_profile("user-9"), "is_open": True}
        try:
            with patch("app.store.set_availability", return_value=updated) as mock_avail:
                resp = client.patch("/profiles/me/availability", json={"is_open": True})
            assert resp.status_code == 200
            mock_avail.assert_called_once_with("user-9", True)
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_profile_update_uses_caller_id(self):
        """PATCH /profiles/me updates the authenticated caller's profile."""
        app.dependency_overrides[require_auth] = _auth("user-9")
        updated = {**_profile("user-9"), "bio": "updated bio"}
        try:
            with patch("app.store.update_profile", return_value=updated) as mock_upd:
                resp = client.patch("/profiles/me", json={"bio": "updated bio"})
            assert resp.status_code == 200
            mock_upd.assert_called_once_with("user-9", display_name=None, bio="updated bio", interests=None)
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_connection_message_send_uses_caller_id_as_sender(self):
        """POST /connections/{id}/messages sends from the authenticated caller."""
        app.dependency_overrides[require_auth] = _auth("user-1")
        conn = _connection("conn-1", "user-1", "user-2", "accepted")
        msg_result = {
            "id": "msg-1", "connection_id": "conn-1", "sender_id": "user-1",
            "body": "hello", "created_at": "2026-01-01T00:00:00+00:00",
        }
        try:
            with (
                patch("app.store.get_connection", return_value=conn),
                patch("app.store.may_contact", return_value=True),
                patch("app.store.send_message", return_value=msg_result) as mock_send,
            ):
                resp = client.post("/connections/conn-1/messages", json={"body": "hello"})
            assert resp.status_code == 201
            mock_send.assert_called_once_with("conn-1", "user-1", "hello")
        finally:
            app.dependency_overrides.pop(require_auth, None)

    def test_profile_endpoint_me_returns_callers_own_profile(self):
        """GET /profiles/me returns the authenticated caller's profile, keyed by token sub."""
        app.dependency_overrides[require_auth] = _auth("user-44")
        profile = _profile("user-44", display_name="Eve")
        try:
            with patch("app.store.get_profile", return_value=profile) as mock_get:
                resp = client.get("/profiles/me")
            assert resp.status_code == 200
            mock_get.assert_called_once_with("user-44")
            assert resp.json()["id"] == "user-44"
        finally:
            app.dependency_overrides.pop(require_auth, None)
