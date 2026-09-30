"""AC#8: A person can send a connection request, and can send at most twenty
in any twenty-four hour period counted from the time of each request rather
than from a calendar boundary.

This targets ``ConnectionStore.send_request`` in app/api/app/store.py, which
tracks each requester's outbound timestamps (``_request_timestamps``) and, on
every call, prunes entries older than ``now - 24h`` before checking whether
the requester is already at the 20-request ceiling
(``MAX_CONNECTION_REQUESTS_PER_DAY``). That prune-then-check shape is what
makes the window "rolling": each timestamp ages out 24 hours after *it* was
recorded, not at the next midnight. These tests control ``time.time()``
directly (rather than sleeping) so they can prove:

1. 20 requests succeed and the 21st is refused with "rate_limit_exceeded".
2. The 24-hour window is counted from each request's own timestamp, so
   staggering requests across a calendar-day boundary does not reset the
   count early.
3. The window is genuinely rolling per-timestamp: once the *oldest* request
   ages past 24 hours, exactly one new slot opens up (not the whole
   window), which a single fixed "reset every midnight" rule could not
   produce.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import app.store as store_module
from app.store import ConnectionStore, MAX_CONNECTION_REQUESTS_PER_DAY, ProfileStore

# The AC's window size, expressed independently of the implementation so the
# test still asserts the stated "twenty-four hour" period even if someone
# changes the internal constant name.
ONE_DAY_SECONDS = 24 * 60 * 60


@pytest.fixture
def fake_clock(monkeypatch: pytest.MonkeyPatch):
    """Replace app.store's time.time() with a controllable fake clock.

    Returns a setter: call it with an epoch-seconds float to move "now".
    """
    state = {"now": 0.0}
    monkeypatch.setattr(store_module.time, "time", lambda: state["now"])

    def _set(epoch_seconds: float) -> None:
        state["now"] = epoch_seconds

    return _set


class TestTwentyRequestsAllowedTwentyFirstRefused:
    """20 requests within the rolling day succeed; the 21st is refused."""

    def test_allows_20_requests_then_refuses_the_21st(self, fake_clock) -> None:
        fake_clock(1_700_000_000.0)
        store = ProfileStore()
        cs = ConnectionStore(store)

        assert MAX_CONNECTION_REQUESTS_PER_DAY == 20

        # Attempt 21 requests to 21 distinct recipients, all at the same
        # instant (well within the 24h window). The first 20 must succeed;
        # the 21st must be refused with "rate_limit_exceeded".
        for i in range(21):
            conn, reason = cs.send_request("alice", f"user-{i}")
            if i < 20:
                assert conn is not None, f"request {i + 1} of 20 should succeed"
                assert reason is None
            else:
                assert conn is None, "the 21st request within 24h must be refused"
                assert reason == "rate_limit_exceeded"


class TestRollingWindowCountedFromEachTimestampNotCalendarDay:
    """Staggering requests across a calendar-day boundary must not reset the
    count early — the window is rolling per-request-timestamp, not aligned
    to midnight."""

    def test_count_survives_crossing_midnight_when_under_24h_elapsed(self, fake_clock) -> None:
        # Start just before a calendar-day boundary (23:50 UTC).
        t0 = datetime(2024, 1, 15, 23, 50, 0, tzinfo=timezone.utc).timestamp()
        fake_clock(t0)
        store = ProfileStore()
        cs = ConnectionStore(store)

        for i in range(20):
            conn, reason = cs.send_request("alice", f"user-{i}")
            assert conn is not None
            assert reason is None

        # Move 20 minutes forward — now it's 00:10 the next calendar day,
        # but only 20 minutes of real time have elapsed, far short of the
        # 24-hour window.
        fake_clock(t0 + 20 * 60)

        conn, reason = cs.send_request("alice", "overflow-after-midnight")
        assert conn is None, (
            "crossing a calendar-day boundary must not reset the rate limit; "
            "only 20 minutes elapsed since the last batch of requests"
        )
        assert reason == "rate_limit_exceeded"


class TestRollingWindowExpiresEachTimestampIndividually:
    """Once the oldest of the 20 timestamps ages past 24 hours, exactly one
    new slot opens — proving the window is counted per-request, not reset
    globally on a fixed schedule."""

    def test_one_slot_frees_when_the_oldest_request_turns_24h_old(self, fake_clock) -> None:
        t0 = 1_700_000_000.0
        fake_clock(t0)
        store = ProfileStore()
        cs = ConnectionStore(store)

        # First request recorded at t0.
        conn, reason = cs.send_request("alice", "first-recipient")
        assert conn is not None
        assert reason is None

        # 19 more requests recorded one second later, so they are all
        # slightly younger than the very first one.
        fake_clock(t0 + 1)
        for i in range(19):
            conn, reason = cs.send_request("alice", f"batch-{i}")
            assert conn is not None
            assert reason is None

        # Now at 20 outstanding requests: the 21st must be refused.
        conn, reason = cs.send_request("alice", "still-blocked")
        assert conn is None
        assert reason == "rate_limit_exceeded"

        # Advance to just after the *oldest* timestamp (t0) turns 24 hours
        # old, but before the 19 later ones do. Exactly one slot should
        # free up.
        fake_clock(t0 + ONE_DAY_SECONDS + 1)

        conn, reason = cs.send_request("alice", "unlocked-recipient")
        assert conn is not None, (
            "the request recorded at t0 is now older than 24h and must be "
            "pruned, freeing exactly one slot"
        )
        assert reason is None

        # But the slot is used up again immediately: the 19 requests from
        # t0 + 1 are still within their own 24h window, so the very next
        # request is refused again.
        conn, reason = cs.send_request("alice", "blocked-again")
        assert conn is None
        assert reason == "rate_limit_exceeded"
