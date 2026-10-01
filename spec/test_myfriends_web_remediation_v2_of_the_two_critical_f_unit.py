"""Unit tests for MyFriends API remediation v2.

Tests the units (validators, auth dependency, store constants) in isolation.
No HTTP server, no database connection required.

AC coverage:
  AC#6  – display_name validation (blank / whitespace / too-long)
  AC#7  – require_moderator role check
  AC#8  – require_auth rejects missing / malformed Authorization header
  AC#9  – require_auth is the single source of caller identity (returns sub claim)
  AC#5  – DATABASE_URL must be set (store raises RuntimeError when absent)
"""

from __future__ import annotations

import asyncio
import os
import sys

# ---------------------------------------------------------------------------
# Path bootstrap — tests live in spec/, app code in app/api/
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app", "api"))

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# AC#6 – ProfileCreate display_name validator
# ---------------------------------------------------------------------------

class TestProfileCreateDisplayNameValidator:
    """ProfileCreate must reject blank, whitespace-only, and too-long names."""

    def _make(self, display_name, age=25):
        from app.main import ProfileCreate
        return ProfileCreate(display_name=display_name, age=age)

    def test_empty_string_rejected(self):
        from app.main import ProfileCreate
        with pytest.raises(ValidationError) as exc_info:
            ProfileCreate(display_name="", age=25)
        errors = exc_info.value.errors()
        assert any("display_name" in str(e) for e in errors)

    def test_whitespace_only_rejected(self):
        from app.main import ProfileCreate
        with pytest.raises(ValidationError):
            ProfileCreate(display_name="   ", age=25)

    def test_tab_whitespace_rejected(self):
        from app.main import ProfileCreate
        with pytest.raises(ValidationError):
            ProfileCreate(display_name="\t\n", age=25)

    def test_too_long_rejected(self):
        from app.main import ProfileCreate
        from app import store
        too_long = "A" * (store.MAX_DISPLAY_NAME_LENGTH + 1)
        with pytest.raises(ValidationError) as exc_info:
            ProfileCreate(display_name=too_long, age=25)
        assert any("display_name" in str(e) for e in exc_info.value.errors())

    def test_exactly_at_max_length_accepted(self):
        from app.main import ProfileCreate
        from app import store
        at_max = "A" * store.MAX_DISPLAY_NAME_LENGTH
        p = ProfileCreate(display_name=at_max, age=25)
        assert p.display_name == at_max

    def test_valid_name_accepted(self):
        from app.main import ProfileCreate
        p = ProfileCreate(display_name="Alice", age=25)
        assert p.display_name == "Alice"

    def test_name_with_leading_space_accepted(self):
        """Leading/trailing spaces are allowed; only pure-whitespace is rejected."""
        from app.main import ProfileCreate
        p = ProfileCreate(display_name=" Alice ", age=25)
        assert p.display_name == " Alice "


# ---------------------------------------------------------------------------
# AC#6 – ProfileUpdate display_name validator
# ---------------------------------------------------------------------------

class TestProfileUpdateDisplayNameValidator:
    def test_whitespace_only_rejected(self):
        from app.main import ProfileUpdate
        with pytest.raises(ValidationError):
            ProfileUpdate(display_name="  ")

    def test_too_long_rejected(self):
        from app.main import ProfileUpdate
        from app import store
        with pytest.raises(ValidationError):
            ProfileUpdate(display_name="B" * (store.MAX_DISPLAY_NAME_LENGTH + 1))

    def test_none_accepted(self):
        from app.main import ProfileUpdate
        p = ProfileUpdate(display_name=None)
        assert p.display_name is None

    def test_valid_update_accepted(self):
        from app.main import ProfileUpdate
        p = ProfileUpdate(display_name="Bob")
        assert p.display_name == "Bob"


# ---------------------------------------------------------------------------
# AC#6 – ReportCreate reason validator
# ---------------------------------------------------------------------------

class TestReportCreateReasonValidator:
    def test_invalid_reason_rejected(self):
        from app.main import ReportCreate
        with pytest.raises(ValidationError):
            ReportCreate(reported_id="user-2", reason="made_up_reason")

    def test_valid_reason_accepted(self):
        from app.main import ReportCreate
        r = ReportCreate(reported_id="user-2", reason="spam")
        assert r.reason == "spam"


# ---------------------------------------------------------------------------
# AC#6 – ReportResolve status validator
# ---------------------------------------------------------------------------

class TestReportResolveStatusValidator:
    def test_open_rejected_as_new_status(self):
        """'open' is not a valid resolve target status."""
        from app.main import ReportResolve
        with pytest.raises(ValidationError):
            ReportResolve(status="open")

    def test_invalid_status_rejected(self):
        from app.main import ReportResolve
        with pytest.raises(ValidationError):
            ReportResolve(status="not_valid")

    def test_dismissed_accepted(self):
        from app.main import ReportResolve
        r = ReportResolve(status="dismissed")
        assert r.status == "dismissed"

    def test_actioned_accepted(self):
        from app.main import ReportResolve
        r = ReportResolve(status="actioned")
        assert r.status == "actioned"


# ---------------------------------------------------------------------------
# AC#8 – require_auth: missing / malformed Authorization header → 401
# ---------------------------------------------------------------------------

class TestRequireAuth:
    """require_auth must reject any call that lacks a valid Bearer token."""

    def test_missing_header_raises_401(self):
        from fastapi import HTTPException
        from starlette.requests import Request
        from app.main import require_auth

        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)

        async def _run():
            with pytest.raises(HTTPException) as exc_info:
                await require_auth(request, authorization="")
            assert exc_info.value.status_code == 401

        asyncio.run(_run())

    def test_non_bearer_scheme_raises_401(self):
        from fastapi import HTTPException
        from starlette.requests import Request
        from app.main import require_auth

        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)

        async def _run():
            with pytest.raises(HTTPException) as exc_info:
                await require_auth(request, authorization="Basic dXNlcjpwYXNz")
            assert exc_info.value.status_code == 401

        asyncio.run(_run())

    def test_bearer_without_sub_raises_401(self):
        """A token that decodes successfully but has no 'sub' claim is rejected."""
        from fastapi import HTTPException
        from starlette.requests import Request
        from unittest.mock import patch
        from app.main import require_auth

        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)

        async def _run():
            with patch("app.main._decode_token", return_value={"email": "x@y.com"}):
                with pytest.raises(HTTPException) as exc_info:
                    await require_auth(request, authorization="Bearer fake.token.here")
            assert exc_info.value.status_code == 401

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# AC#9 – require_auth returns the sub claim (single source of identity)
# ---------------------------------------------------------------------------

class TestRequireAuthReturnsSub:
    def test_returns_sub_claim(self):
        """require_auth returns the token's 'sub' claim as the caller's identity."""
        from starlette.requests import Request
        from unittest.mock import patch
        from app.main import require_auth

        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)

        async def _run():
            with patch("app.main._decode_token", return_value={"sub": "user-99"}):
                caller_id = await require_auth(request, authorization="Bearer fake.token")
            assert caller_id == "user-99"

        asyncio.run(_run())

    def test_payload_stored_on_request_state(self):
        """Token payload is stored on request.state for downstream dependencies."""
        from starlette.requests import Request
        from unittest.mock import patch
        from app.main import require_auth

        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)
        payload = {"sub": "user-99", "realm_access": {"roles": ["myfriends-moderator"]}}

        async def _run():
            with patch("app.main._decode_token", return_value=payload):
                await require_auth(request, authorization="Bearer fake.token")
            assert request.state.token_payload == payload

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# AC#7 – require_moderator: non-moderator raises 403
# ---------------------------------------------------------------------------

class TestRequireModerator:
    def test_no_moderator_role_raises_403(self):
        """A valid user without the moderator role is rejected with 403."""
        from fastapi import HTTPException
        from starlette.requests import Request
        from app.main import require_moderator

        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)
        request.state.token_payload = {"sub": "user-1", "realm_access": {"roles": []}}

        async def _run():
            with pytest.raises(HTTPException) as exc_info:
                await require_moderator(request, caller_id="user-1")
            assert exc_info.value.status_code == 403

        asyncio.run(_run())

    def test_moderator_role_passes(self):
        """A token with 'myfriends-moderator' role is accepted."""
        from starlette.requests import Request
        from app.main import require_moderator

        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)
        request.state.token_payload = {
            "sub": "mod-1",
            "realm_access": {"roles": ["myfriends-moderator"]},
        }

        async def _run():
            result = await require_moderator(request, caller_id="mod-1")
            assert result == "mod-1"

        asyncio.run(_run())

    def test_missing_realm_access_raises_403(self):
        """A token with no realm_access claim at all is rejected."""
        from fastapi import HTTPException
        from starlette.requests import Request
        from app.main import require_moderator

        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)
        request.state.token_payload = {"sub": "user-1"}

        async def _run():
            with pytest.raises(HTTPException) as exc_info:
                await require_moderator(request, caller_id="user-1")
            assert exc_info.value.status_code == 403

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# AC#5 – DATABASE_URL must be present; absence raises immediately
# ---------------------------------------------------------------------------

class TestDatabaseUrl:
    def test_missing_database_url_raises_runtime_error(self, monkeypatch):
        """store._database_url() raises RuntimeError when DATABASE_URL is unset."""
        from app import store

        monkeypatch.delenv("DATABASE_URL", raising=False)
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            store._database_url()

    def test_present_database_url_returned(self, monkeypatch):
        """store._database_url() returns the value when the variable is set."""
        from app import store

        monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/testdb")
        result = store._database_url()
        assert result == "postgresql://test:test@localhost/testdb"


# ---------------------------------------------------------------------------
# AC#1 / AC#4 – Store constants: only known report reasons are accepted
# ---------------------------------------------------------------------------

class TestStoreConstants:
    def test_valid_report_reasons_nonempty(self):
        from app import store
        assert len(store.VALID_REPORT_REASONS) > 0

    def test_max_display_name_length_positive(self):
        from app import store
        assert store.MAX_DISPLAY_NAME_LENGTH > 0

    def test_valid_report_statuses_contains_open(self):
        from app import store
        assert "open" in store.VALID_REPORT_STATUSES

    def test_valid_report_statuses_contains_terminal_states(self):
        from app import store
        assert "dismissed" in store.VALID_REPORT_STATUSES
        assert "actioned" in store.VALID_REPORT_STATUSES
