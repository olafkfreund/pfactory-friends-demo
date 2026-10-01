# AC#5: Database credentials are read from the environment at runtime and appear
# nowhere in the repository or in any image.
#
# _database_url() must:
#   - return the value of DATABASE_URL when the variable is set
#   - raise RuntimeError when DATABASE_URL is absent or empty
#
# Rationale: AC#5 — database credentials are read from the environment at
# runtime and appear nowhere in the repository.

import os
import pytest

from app.store import _database_url


class TestDatabaseUrlFromEnv:
    """Verify that _database_url reads from DATABASE_URL env var and raises when absent."""

    def test_database_url_returns_value_when_set(self, monkeypatch):
        """Happy path: _database_url returns the DATABASE_URL value exactly as set."""
        expected = "postgresql://user:pass@localhost:5432/myfriends"
        monkeypatch.setenv("DATABASE_URL", expected)

        result = _database_url()

        assert result == expected

    def test_database_url_raises_when_variable_absent(self, monkeypatch):
        """_database_url raises RuntimeError when DATABASE_URL is not set."""
        monkeypatch.delenv("DATABASE_URL", raising=False)

        with pytest.raises(RuntimeError):
            _database_url()

    def test_database_url_raises_when_variable_empty(self, monkeypatch):
        """_database_url raises RuntimeError when DATABASE_URL is set to an empty string."""
        monkeypatch.setenv("DATABASE_URL", "")

        with pytest.raises(RuntimeError):
            _database_url()

    def test_database_url_does_not_hardcode_credentials(self, monkeypatch):
        """_database_url reads from the env var, not from a hardcoded literal in code."""
        sentinel = "postgresql://sentinel-user:sentinel-pass@sentinel-host/sentinel-db"
        monkeypatch.setenv("DATABASE_URL", sentinel)

        result = _database_url()

        # The value returned must be exactly what was injected via the environment —
        # if any hardcoded value were returned instead, this assertion would fail.
        assert result == sentinel
