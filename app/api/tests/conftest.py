"""Shared pytest configuration for the MyFriends API test suite.

Auth bypass (C18): every test in this suite runs with the ``require_auth``
dependency overridden to return a fixed test caller ID.  This lets existing
tests exercise endpoint logic without carrying an ``X-User-ID`` header.

Tests that specifically assert on authentication behaviour (e.g. C18 tests
that expect HTTP 401) should use the ``_without_auth_bypass`` fixture defined
in ``test_main.py``, which pops this override for the duration of that one test.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def _bypass_auth_for_all_tests() -> Generator[None, None, None]:
    """Install a no-op auth override so tests run without auth headers (C18).

    Scoped to the test session so it applies to every test across every file.
    The ``_isolated_app`` fixture in ``test_main.py`` complements this by
    resetting the in-memory stores between tests.
    """
    from app.auth import require_auth
    from app.main import app

    app.dependency_overrides[require_auth] = lambda: "test-user-id"
    yield
    app.dependency_overrides.pop(require_auth, None)
