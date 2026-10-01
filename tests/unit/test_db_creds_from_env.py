# AC#5: Database credentials are read from the environment at runtime and appear
# nowhere in the repository or in any image.
#
# Target:  app/api/app/store.py::_database_url
# Rationale: AC#5 — database credentials are read from the environment at
#            runtime and appear nowhere in the repository.
#
# _database_url() must:
#   - return the exact value of DATABASE_URL when the variable is set
#   - raise RuntimeError when DATABASE_URL is absent (not set at all)
#   - raise RuntimeError when DATABASE_URL is set to an empty string
#   - never return a hardcoded credential — only the injected env value

import pytest

from app.store import _database_url


def test_database_url_returns_env_value_when_set(monkeypatch):
    """Happy path: _database_url returns the DATABASE_URL value exactly as injected."""
    expected = "postgresql://user:secret@db.example.com:5432/myfriends"
    monkeypatch.setenv("DATABASE_URL", expected)

    result = _database_url()

    assert result == expected


def test_database_url_raises_runtime_error_when_variable_absent(monkeypatch):
    """_database_url raises RuntimeError when DATABASE_URL is not set in the environment."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError):
        _database_url()


def test_database_url_raises_runtime_error_when_variable_empty(monkeypatch):
    """_database_url raises RuntimeError when DATABASE_URL is set to an empty string."""
    monkeypatch.setenv("DATABASE_URL", "")

    with pytest.raises(RuntimeError):
        _database_url()


def test_database_url_does_not_hardcode_credentials(monkeypatch):
    """_database_url reads from DATABASE_URL exclusively — injected sentinel is returned verbatim.

    AC#5: credentials appear nowhere in the repository; only the runtime
    environment variable value is returned.  If any hardcoded value were
    substituted instead, this assertion would fail.
    """
    sentinel = "postgresql://sentinel-creds:hunter2@sentinel-host:9999/sentinel-db"
    monkeypatch.setenv("DATABASE_URL", sentinel)

    result = _database_url()

    assert result == sentinel


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://a:b@localhost/testdb",
        "postgresql://user:p%40ss@host:5432/db",
        "postgres://u:p@host/db?sslmode=require",
    ],
    ids=["basic", "encoded-password", "postgres-scheme-with-sslmode"],
)
def test_database_url_returns_any_valid_connection_string(monkeypatch, url):
    """_database_url returns whatever valid connection string is in DATABASE_URL.

    AC#5: the value is read from the environment without modification,
    regardless of its form.
    """
    monkeypatch.setenv("DATABASE_URL", url)

    result = _database_url()

    assert result == url
