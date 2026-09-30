"""Shared pytest configuration for the MyFriends spec test suite.

Provides:
- auth bypass fixture (all tests run without an X-User-ID header)
- store isolation fixture (fresh in-memory stores for each test)

These are modelled on app/api/tests/conftest.py so both suites behave
consistently.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def _bypass_auth_for_all_tests() -> Generator[None, None, None]:
    """Override require_auth for every test so no X-User-ID header is needed."""
    from app.auth import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: "test-user-id"
    yield
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture(autouse=True)
def _isolated_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset in-memory stores before each test to prevent state bleed."""
    from app import main
    from app.store import ConnectionStore, MessageStore, ProfileStore, ReportStore

    profiles = ProfileStore()
    connections = ConnectionStore(profiles)
    messages = MessageStore(profiles, connections)
    reports = ReportStore()
    monkeypatch.setattr(main, "_profiles", profiles)
    monkeypatch.setattr(main, "_connections", connections)
    monkeypatch.setattr(main, "_messages", messages)
    monkeypatch.setattr(main, "_reports", reports)
