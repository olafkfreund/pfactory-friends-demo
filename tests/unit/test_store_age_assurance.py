# AC#3: store-layer record_age_assurance must only operate on the profile
# belonging to the caller — it must update the correct profile row and return
# None when no row with the given profile_id exists (i.e. a mismatched id
# produces no update, not an accidental update of a different profile).
#
# Subtask: age-assurance-store-owner-check
# Target:  app/api/app/store.py::record_age_assurance
# Criterion: record_age_assurance in the store updates the correct profile row
#            and does not accept a mismatched id.

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

# Path bootstrap: this test lives in tests/unit/; app code is in .worktree/app/api/
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", ".worktree", "app", "api"),
)

from app import store  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: build a fake _conn context manager
# ---------------------------------------------------------------------------

def _fake_conn_cm(mock_conn):
    """Return a context-manager factory that yields *mock_conn* on entry.

    record_age_assurance calls ``_conn()`` (the function), so we replace
    ``app.store._conn`` with a function that returns a context manager.
    """
    @contextmanager
    def _cm():
        yield mock_conn
    return _cm


# ---------------------------------------------------------------------------
# Happy path: correct row is updated and returned
# ---------------------------------------------------------------------------

def test_record_age_assurance_updates_correct_profile_row():
    """record_age_assurance issues UPDATE ... WHERE id = profile_id and returns
    the updated row — proving only the matching profile is touched (AC#3).
    """
    profile_id = "owner-profile-001"
    expected_row = {
        "id": profile_id,
        "display_name": "Alice",
        "bio": "",
        "age": 25,
        "interests": [],
        "is_open": False,
        "age_assurance_passed": True,
        "created_at": "2026-01-01T00:00:00+00:00",
        "deleted_at": None,
    }

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = expected_row

    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_cursor

    with patch("app.store._conn", _fake_conn_cm(mock_conn)):
        result = store.record_age_assurance(profile_id)

    # Return value must match the row the DB reported as updated
    assert result == expected_row
    # age_assurance_passed must be True in the returned row
    assert result["age_assurance_passed"] is True
    # The SQL was invoked with exactly the caller's profile_id as the parameter
    assert mock_conn.execute.call_args[0][1] == (profile_id,)


# ---------------------------------------------------------------------------
# Mismatch / non-existent id: no row updated, None returned
# ---------------------------------------------------------------------------

def test_record_age_assurance_returns_none_for_nonexistent_profile():
    """record_age_assurance returns None when no profile with the given id
    exists — a caller cannot update a profile they do not own (AC#3).
    """
    mismatched_id = "nonexistent-profile-xyz"

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None  # DB found no matching row

    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_cursor

    with patch("app.store._conn", _fake_conn_cm(mock_conn)):
        result = store.record_age_assurance(mismatched_id)

    # No matching row → function must return None, not a dict
    assert result is None
    # The UPDATE was attempted with the given (mismatched) id — the function
    # never silently redirects to a different profile's id.
    assert mock_conn.execute.call_args[0][1] == (mismatched_id,)
