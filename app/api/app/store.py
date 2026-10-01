"""MyFriends persistent store — Postgres-backed data layer.

All state lives in Postgres.  Credentials are read from ``DATABASE_URL``
at runtime and appear nowhere in the repository or in any image.

The ``may_contact(a_id, b_id)`` predicate is the single place that decides
whether person *a* may send a request or message to person *b*.  It checks
both directions of the block relationship so that the discovery, request, and
messaging paths cannot disagree — the failure mode that produced issue #86.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

if TYPE_CHECKING:
    import psycopg as _psycopg


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is required but not set. "
            "Set it to a valid PostgreSQL connection string before starting the service."
        )
    return url


@contextmanager
def _conn() -> "Generator[_psycopg.Connection, None, None]":
    """Open a psycopg3 connection and commit/rollback on exit.

    psycopg is imported lazily so the module can be loaded and tested
    without psycopg installed.  At runtime the database connector must be
    present; the ImportError surfaces on first use rather than at startup so
    that the health probe works even while the database is initialising.
    """
    import psycopg  # noqa: PLC0415
    from psycopg.rows import dict_row  # noqa: PLC0415

    with psycopg.connect(_database_url(), row_factory=dict_row) as connection:
        yield connection


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

# DDL is split into individual statements so each runs through psycopg's
# extended-query protocol and is independently transactional.  A single
# multi-statement string works only with the simple-query protocol (no
# parameters), which is an easy foot-gun to leave lying around.
_DDL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS profiles (
        id                   TEXT        PRIMARY KEY,
        display_name         TEXT        NOT NULL,
        bio                  TEXT        NOT NULL DEFAULT '',
        age                  INTEGER     NOT NULL,
        interests            TEXT[]      NOT NULL DEFAULT '{}',
        is_open              BOOLEAN     NOT NULL DEFAULT FALSE,
        age_assurance_passed BOOLEAN     NOT NULL DEFAULT FALSE,
        created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
        deleted_at           TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS connections (
        id           TEXT        PRIMARY KEY,
        requester_id TEXT        NOT NULL REFERENCES profiles(id),
        target_id    TEXT        NOT NULL REFERENCES profiles(id),
        status       TEXT        NOT NULL DEFAULT 'pending',
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (requester_id, target_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id            TEXT        PRIMARY KEY,
        connection_id TEXT        NOT NULL REFERENCES connections(id),
        sender_id     TEXT        NOT NULL REFERENCES profiles(id),
        body          TEXT        NOT NULL,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS blocks (
        id         TEXT        PRIMARY KEY,
        blocker_id TEXT        NOT NULL REFERENCES profiles(id),
        blocked_id TEXT        NOT NULL REFERENCES profiles(id),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (blocker_id, blocked_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reports (
        id          TEXT        PRIMARY KEY,
        reporter_id TEXT        NOT NULL REFERENCES profiles(id),
        reported_id TEXT        NOT NULL,
        reason      TEXT        NOT NULL,
        detail      TEXT        NOT NULL DEFAULT '',
        status      TEXT        NOT NULL DEFAULT 'open',
        resolved_by TEXT,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        resolved_at TIMESTAMPTZ
    )
    """,
)


def bootstrap_schema() -> None:
    """Create all tables if they do not already exist.

    Called once at application startup via the FastAPI lifespan hook.
    Each DDL statement is executed separately so foreign-key ordering is
    explicit and each statement uses the extended-query protocol.
    """
    with _conn() as conn:
        for stmt in _DDL_STATEMENTS:
            conn.execute(stmt)


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

MAX_DISPLAY_NAME_LENGTH = 100
MAX_INTERESTS = 10
MAX_REQUESTS_PER_DAY = 20

VALID_REPORT_REASONS = frozenset({
    "harassment",
    "spam",
    "inappropriate_content",
    "underage",
    "impersonation",
    "other",
})

VALID_REPORT_STATUSES = frozenset({"open", "dismissed", "actioned"})


# ---------------------------------------------------------------------------
# may_contact — single predicate for discovery, requests, and messages
# ---------------------------------------------------------------------------

def may_contact(a_id: str, b_id: str) -> bool:
    """Return *True* if person *a* may contact person *b*.

    Checks both directions of the block relationship so that no caller path can
    reach a different conclusion than any other — the asymmetric-block defect
    from issue #86 is fixed by construction.
    """
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT NOT EXISTS (
                SELECT 1 FROM blocks
                WHERE (blocker_id = %s AND blocked_id = %s)
                   OR (blocker_id = %s AND blocked_id = %s)
            ) AS allowed
            """,
            (a_id, b_id, b_id, a_id),
        ).fetchone()
    return bool(row and row["allowed"])


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def create_profile(
    profile_id: str,
    display_name: str,
    bio: str,
    age: int,
    interests: list[str],
) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """
            INSERT INTO profiles (id, display_name, bio, age, interests)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (profile_id, display_name, bio, age, interests),
        ).fetchone()
    return dict(row)


def get_profile(profile_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE id = %s AND deleted_at IS NULL",
            (profile_id,),
        ).fetchone()
    return dict(row) if row else None


def update_profile(
    profile_id: str,
    *,
    display_name: str | None = None,
    bio: str | None = None,
    interests: list[str] | None = None,
) -> dict | None:
    """Partially update a profile; only supplied fields are changed."""
    clauses: list[str] = []
    values: list = []
    if display_name is not None:
        clauses.append("display_name = %s")
        values.append(display_name)
    if bio is not None:
        clauses.append("bio = %s")
        values.append(bio)
    if interests is not None:
        clauses.append("interests = %s")
        values.append(interests)
    if not clauses:
        return get_profile(profile_id)
    values.append(profile_id)
    with _conn() as conn:
        row = conn.execute(
            f"UPDATE profiles SET {', '.join(clauses)} WHERE id = %s AND deleted_at IS NULL RETURNING *",
            values,
        ).fetchone()
    return dict(row) if row else None


def set_availability(profile_id: str, is_open: bool) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "UPDATE profiles SET is_open = %s WHERE id = %s AND deleted_at IS NULL RETURNING *",
            (is_open, profile_id),
        ).fetchone()
    return dict(row) if row else None


def record_age_assurance(profile_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            """
            UPDATE profiles
            SET age_assurance_passed = TRUE
            WHERE id = %s AND deleted_at IS NULL
            RETURNING *
            """,
            (profile_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_profile(profile_id: str) -> dict:
    """Soft-delete the profile and cascade-remove transactional data.

    Returns a summary of what was removed and what is retained, as required by
    the deletion-transparency rule.  Blocks and reports are retained for legal
    and safety purposes per the data-retention policy.
    """
    with _conn() as conn:
        conn.execute(
            "UPDATE profiles SET deleted_at = now(), is_open = FALSE WHERE id = %s",
            (profile_id,),
        )
        msgs_deleted = conn.execute(
            """
            DELETE FROM messages
            WHERE sender_id = %s
               OR connection_id IN (
                   SELECT id FROM connections
                   WHERE requester_id = %s OR target_id = %s
               )
            RETURNING id
            """,
            (profile_id, profile_id, profile_id),
        ).fetchall()
        conns_deleted = conn.execute(
            "DELETE FROM connections WHERE requester_id = %s OR target_id = %s RETURNING id",
            (profile_id, profile_id),
        ).fetchall()
        blocks_retained = conn.execute(
            "SELECT count(*) AS n FROM blocks WHERE blocker_id = %s OR blocked_id = %s",
            (profile_id, profile_id),
        ).fetchone()["n"]
        reports_retained = conn.execute(
            "SELECT count(*) AS n FROM reports WHERE reporter_id = %s OR reported_id = %s",
            (profile_id, profile_id),
        ).fetchone()["n"]
    return {
        "removed": {
            "messages": len(msgs_deleted),
            "connections": len(conns_deleted),
        },
        "retained": {
            "blocks": int(blocks_retained),
            "reports": int(reports_retained),
            "reason": (
                "Blocks and reports are retained for safety and legal-hold purposes "
                "per the 24-month post-closure retention policy."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover(caller_id: str, caller_age: int) -> list[dict]:
    """Return open, eligible profiles visible to the caller.

    Age-bracket isolation is enforced here: adults (18+) are never shown to
    minors (16-17), and minors are never shown to adults.  This is a compliance
    requirement, not a preference — the predicate must hold in both directions.
    """
    caller_is_minor = caller_age < 18
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT p.*
            FROM profiles p
            WHERE p.id <> %s
              AND p.deleted_at IS NULL
              AND p.is_open = TRUE
              AND p.age_assurance_passed = TRUE
              AND (
                  (%s AND p.age < 18)
                  OR (NOT %s AND p.age >= 18)
              )
              AND NOT EXISTS (
                  SELECT 1 FROM blocks b
                  WHERE (b.blocker_id = %s AND b.blocked_id = p.id)
                     OR (b.blocker_id = p.id AND b.blocked_id = %s)
              )
            ORDER BY cardinality(p.interests) DESC
            LIMIT 50
            """,
            (caller_id, caller_is_minor, caller_is_minor, caller_id, caller_id),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

def count_requests_today(requester_id: str) -> int:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT count(*) AS n FROM connections
            WHERE requester_id = %s
              AND created_at >= now() - INTERVAL '24 hours'
            """,
            (requester_id,),
        ).fetchone()
    return int(row["n"])


def create_connection_request(requester_id: str, target_id: str) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """
            INSERT INTO connections (id, requester_id, target_id, status)
            VALUES (%s, %s, %s, 'pending')
            RETURNING *
            """,
            (str(uuid.uuid4()), requester_id, target_id),
        ).fetchone()
    return dict(row)


def get_connection(connection_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM connections WHERE id = %s",
            (connection_id,),
        ).fetchone()
    return dict(row) if row else None


def update_connection_status(connection_id: str, new_status: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            """
            UPDATE connections
            SET status = %s, updated_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (new_status, connection_id),
        ).fetchone()
    return dict(row) if row else None


def list_connections(profile_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM connections
            WHERE (requester_id = %s OR target_id = %s)
              AND status = 'accepted'
            ORDER BY updated_at DESC
            """,
            (profile_id, profile_id),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def send_message(connection_id: str, sender_id: str, body: str) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """
            INSERT INTO messages (id, connection_id, sender_id, body)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (str(uuid.uuid4()), connection_id, sender_id, body),
        ).fetchone()
    return dict(row)


def list_messages(connection_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE connection_id = %s ORDER BY created_at",
            (connection_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

def create_block(blocker_id: str, blocked_id: str) -> dict:
    block_id = str(uuid.uuid4())
    with _conn() as conn:
        row = conn.execute(
            """
            INSERT INTO blocks (id, blocker_id, blocked_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (blocker_id, blocked_id) DO UPDATE SET blocker_id = EXCLUDED.blocker_id
            RETURNING *
            """,
            (block_id, blocker_id, blocked_id),
        ).fetchone()
    return dict(row)


def list_blocks(blocker_id: str) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM blocks WHERE blocker_id = %s ORDER BY created_at DESC",
            (blocker_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def create_report(
    reporter_id: str,
    reported_id: str,
    reason: str,
    detail: str,
) -> dict:
    with _conn() as conn:
        row = conn.execute(
            """
            INSERT INTO reports (id, reporter_id, reported_id, reason, detail)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (str(uuid.uuid4()), reporter_id, reported_id, reason, detail),
        ).fetchone()
    return dict(row)


def list_reports(status_filter: str | None = None) -> list[dict]:
    with _conn() as conn:
        if status_filter:
            rows = conn.execute(
                "SELECT * FROM reports WHERE status = %s ORDER BY created_at",
                (status_filter,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reports ORDER BY created_at",
            ).fetchall()
    return [dict(r) for r in rows]


def resolve_report(report_id: str, resolved_by: str, new_status: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            """
            UPDATE reports
            SET status = %s, resolved_by = %s, resolved_at = now()
            WHERE id = %s
            RETURNING *
            """,
            (new_status, resolved_by, report_id),
        ).fetchone()
    return dict(row) if row else None
