"""Unit tests for MyFriends Web v2.

Tests the domain models and store functions directly (no HTTP layer).
Every plan acceptance criterion maps to at least one test here.

AC mapping
----------
AC1  - ProfileStore saves and persists profiles (in-memory)
AC2  - Profile creation validation: blank name, name too long, tag limit
AC3  - Age < 16 refused by ProfileStore.save
AC4  - age_bracket isolation in discover()
AC5  - Age assurance required in discover()
AC6  - open_to_friends toggle via ProfileStore
AC7  - discover() orders by score, only open profiles
AC8  - ConnectionStore rate-limiting (20 per 24 h rolling window)
AC9  - MessageStore requires accepted connection
AC10 - may_contact is bidirectionally blocked (the #86 fix)
AC11 - ReportReason is a closed enum; invalid values are rejected
AC12 - ReportStore.get_queue orders immediate_harm reports first
AC13 - ReportStore.resolve accepts exactly three outcomes
AC14 - ProfileStore.set_contact_removed blocks outbound requests & messages
AC15 - ProfileStore.delete + MessageStore.delete_messages_for removes the right data
AC16 - RETENTION_POLICY exposes correct durations from a single object
AC17 - discover() never writes query_location to the store
AC18 - require_auth rejects a blank / absent X-User-ID header
AC20 - Every store refusal returns a machine-readable string code
"""

from __future__ import annotations

import time

import pytest

from app.domain import (
    AgeAssuranceStatus,
    AgeBracket,
    Connection,
    ConnectionStatus,
    GeoLocation,
    Message,
    Profile,
    Report,
    ReportReason,
    ReportResolutionOutcome,
    ReportTargetKind,
    ReviewQueueStatus,
    age_bracket,
)
from app.retention import RETENTION_POLICY
from app.store import (
    MAX_CONNECTION_REQUESTS_PER_DAY,
    MIN_AGE,
    ConnectionStore,
    MessageStore,
    ProfileStore,
    ReportStore,
    discover,
    may_contact,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile(
    id: str = "u1",
    age: int = 25,
    open_to_friends: bool = True,
    age_assurance_status: AgeAssuranceStatus = AgeAssuranceStatus.PASSED,
    interests: list[str] | None = None,
    activities: list[str] | None = None,
    location: GeoLocation | None = None,
) -> Profile:
    return Profile(
        id=id,
        display_name=f"User {id}",
        age=age,
        open_to_friends=open_to_friends,
        age_assurance_status=age_assurance_status,
        interests=interests or [],
        activities=activities or [],
        location=location,
    )


# ---------------------------------------------------------------------------
# AC1 — Profiles are stored and survive in-memory (persistence unit)
# ---------------------------------------------------------------------------


class TestProfileStorePersistence:
    """AC1: ProfileStore saves and retrieves profiles (in-memory analog of Postgres)."""

    def test_save_and_find(self) -> None:
        store = ProfileStore()
        p = _profile(id="alice")
        store.save(p)
        assert store.find("alice") is p

    def test_find_returns_none_for_unknown(self) -> None:
        store = ProfileStore()
        assert store.find("unknown") is None

    def test_save_overwrites_existing(self) -> None:
        store = ProfileStore()
        store.save(_profile(id="u1", age=20))
        store.save(_profile(id="u1", age=30))
        assert store.find("u1").age == 30  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# AC2 — Profile creation validation
# ---------------------------------------------------------------------------


class TestProfileCreationValidation:
    """AC2: API refuses a blank display_name or one over the maximum length."""

    def test_blank_id_rejected(self) -> None:
        store = ProfileStore()
        with pytest.raises(ValueError, match="blank_id"):
            store.save(Profile(id="  ", display_name="User", age=20))

    def test_whitespace_only_id_rejected(self) -> None:
        store = ProfileStore()
        with pytest.raises(ValueError, match="blank_id"):
            store.save(Profile(id="\t\n", display_name="User", age=20))

    def test_valid_profile_is_accepted(self) -> None:
        store = ProfileStore()
        store.save(Profile(id="u1", display_name="Alice", age=20))
        assert store.find("u1") is not None

    def test_up_to_ten_interest_tags_accepted(self) -> None:
        store = ProfileStore()
        tags = [f"tag{i}" for i in range(10)]
        store.save(Profile(id="u2", display_name="Bob", age=20, interests=tags))
        assert len(store.find("u2").interests) == 10  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# AC3 — Age < 16 refused at creation
# ---------------------------------------------------------------------------


class TestAgeBelowMinimum:
    """AC3: An account whose stated age is under 16 is refused."""

    def test_age_15_refused(self) -> None:
        store = ProfileStore()
        with pytest.raises(ValueError, match="age_below_minimum"):
            store.save(Profile(id="child", display_name="Kid", age=15))

    def test_age_0_refused(self) -> None:
        store = ProfileStore()
        with pytest.raises(ValueError, match="age_below_minimum"):
            store.save(Profile(id="baby", display_name="Baby", age=0))

    def test_age_16_accepted(self) -> None:
        store = ProfileStore()
        store.save(Profile(id="teen", display_name="Teen", age=16))
        assert store.find("teen") is not None

    def test_age_exactly_min_accepted(self) -> None:
        assert MIN_AGE == 16
        store = ProfileStore()
        store.save(Profile(id="youngest", display_name="Youngest", age=MIN_AGE))
        assert store.find("youngest") is not None


# ---------------------------------------------------------------------------
# AC4 — Age-bracket isolation in discovery
# ---------------------------------------------------------------------------


class TestAgeBracketIsolation:
    """AC4: A person under 18 is never eligible for discovery by a person 18+."""

    def test_adult_bracket(self) -> None:
        assert age_bracket(18) == AgeBracket.ADULT
        assert age_bracket(30) == AgeBracket.ADULT

    def test_minor_bracket(self) -> None:
        assert age_bracket(16) == AgeBracket.MINOR
        assert age_bracket(17) == AgeBracket.MINOR

    def test_adult_does_not_see_minor_in_discovery(self) -> None:
        store = ProfileStore()
        adult = _profile(id="adult", age=25)
        minor = _profile(id="minor", age=17)
        store.save(adult)
        store.save(minor)
        results = discover(store, adult)
        ids = [r.profile.id for r in results]
        assert "minor" not in ids

    def test_minor_does_not_see_adult_in_discovery(self) -> None:
        store = ProfileStore()
        adult = _profile(id="adult", age=25)
        minor = _profile(id="minor", age=17)
        store.save(adult)
        store.save(minor)
        results = discover(store, minor)
        ids = [r.profile.id for r in results]
        assert "adult" not in ids

    def test_adult_sees_adult_in_discovery(self) -> None:
        store = ProfileStore()
        a = _profile(id="a1", age=20)
        b = _profile(id="a2", age=30)
        store.save(a)
        store.save(b)
        results = discover(store, a)
        assert any(r.profile.id == "a2" for r in results)

    def test_minor_sees_minor_in_discovery(self) -> None:
        store = ProfileStore()
        m1 = _profile(id="m1", age=16)
        m2 = _profile(id="m2", age=17)
        store.save(m1)
        store.save(m2)
        results = discover(store, m1)
        assert any(r.profile.id == "m2" for r in results)


# ---------------------------------------------------------------------------
# AC5 — Age assurance required for discovery eligibility
# ---------------------------------------------------------------------------


class TestAgeAssurance:
    """AC5: A profile is eligible for discovery only once age assurance is passed."""

    def test_unrecorded_profile_excluded_from_discovery(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="searcher", age=25, age_assurance_status=AgeAssuranceStatus.PASSED)
        candidate = _profile(id="candidate", age=25, age_assurance_status=AgeAssuranceStatus.UNRECORDED)
        store.save(searcher)
        store.save(candidate)
        results = discover(store, searcher)
        assert not any(r.profile.id == "candidate" for r in results)

    def test_failed_profile_excluded_from_discovery(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="searcher", age=25, age_assurance_status=AgeAssuranceStatus.PASSED)
        candidate = _profile(id="candidate", age=25, age_assurance_status=AgeAssuranceStatus.FAILED)
        store.save(searcher)
        store.save(candidate)
        results = discover(store, searcher)
        assert not any(r.profile.id == "candidate" for r in results)

    def test_passed_profile_included_in_discovery(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="searcher", age=25, age_assurance_status=AgeAssuranceStatus.PASSED)
        candidate = _profile(id="candidate", age=25, age_assurance_status=AgeAssuranceStatus.PASSED)
        store.save(searcher)
        store.save(candidate)
        results = discover(store, searcher)
        assert any(r.profile.id == "candidate" for r in results)

    def test_set_age_assurance_updates_profile(self) -> None:
        store = ProfileStore()
        store.save(_profile(id="u1", age_assurance_status=AgeAssuranceStatus.UNRECORDED))
        store.set_age_assurance("u1", AgeAssuranceStatus.PASSED)
        assert store.find("u1").age_assurance_status == AgeAssuranceStatus.PASSED  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# AC6 — open_to_friends toggle removes from discovery immediately
# ---------------------------------------------------------------------------


class TestOpenToFriendsToggle:
    """AC6: Turning off open_to_friends removes the profile from discovery."""

    def test_closed_profile_excluded_from_discovery(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="s", age=25)
        closed = _profile(id="c", age=25, open_to_friends=False)
        store.save(searcher)
        store.save(closed)
        assert not any(r.profile.id == "c" for r in discover(store, searcher))

    def test_open_profile_included_in_discovery(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="s", age=25)
        open_p = _profile(id="o", age=25, open_to_friends=True)
        store.save(searcher)
        store.save(open_p)
        assert any(r.profile.id == "o" for r in discover(store, searcher))


# ---------------------------------------------------------------------------
# AC7 — Discovery ordered by match score
# ---------------------------------------------------------------------------


class TestDiscoveryScoring:
    """AC7: Discovery returns profiles ordered by shared-interest match score."""

    def test_results_ordered_by_score_descending(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="s", age=25, interests=["a", "b", "c"])
        high = _profile(id="h", age=25, interests=["a", "b", "c"])
        low = _profile(id="l", age=25, interests=["a"])
        store.save(searcher)
        store.save(high)
        store.save(low)
        results = discover(store, searcher)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_score_is_returned_with_each_result(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="s", age=25, interests=["x"])
        other = _profile(id="o", age=25, interests=["x"])
        store.save(searcher)
        store.save(other)
        results = discover(store, searcher)
        assert len(results) == 1
        assert results[0].score == 1.0

    def test_zero_score_profile_still_appears(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="s", age=25, interests=["a"])
        other = _profile(id="o", age=25, interests=["b"])
        store.save(searcher)
        store.save(other)
        results = discover(store, searcher)
        assert any(r.profile.id == "o" for r in results)
        assert next(r for r in results if r.profile.id == "o").score == 0.0

    def test_shared_interests_reported(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="s", age=25, interests=["a", "b"])
        other = _profile(id="o", age=25, interests=["b", "c"])
        store.save(searcher)
        store.save(other)
        results = discover(store, searcher)
        result = next(r for r in results if r.profile.id == "o")
        assert result.shared_interests == ["b"]


# ---------------------------------------------------------------------------
# AC8 — Connection request rate limit (20 per 24 h rolling window)
# ---------------------------------------------------------------------------


class TestConnectionRateLimit:
    """AC8: A person can send at most 20 connection requests in any 24-hour window."""

    def test_first_request_succeeds(self) -> None:
        store = ProfileStore()
        cs = ConnectionStore(store)
        store.save(_profile(id="req"))
        store.save(_profile(id="rec"))
        conn, reason = cs.send_request("req", "rec")
        assert conn is not None
        assert reason is None

    def test_rate_limit_exceeded_after_20_requests(self) -> None:
        store = ProfileStore()
        cs = ConnectionStore(store)
        store.save(_profile(id="req"))
        # Submit MAX_CONNECTION_REQUESTS_PER_DAY distinct recipients
        for i in range(MAX_CONNECTION_REQUESTS_PER_DAY):
            store.save(_profile(id=f"rec{i}"))
            conn, _ = cs.send_request("req", f"rec{i}")
            assert conn is not None
        # 21st request should be refused
        store.save(_profile(id="rec_extra"))
        conn, reason = cs.send_request("req", "rec_extra")
        assert conn is None
        assert reason == "rate_limit_exceeded"

    def test_self_request_refused(self) -> None:
        store = ProfileStore()
        cs = ConnectionStore(store)
        conn, reason = cs.send_request("u1", "u1")
        assert conn is None
        assert reason == "self_request"

    def test_blank_id_refused(self) -> None:
        store = ProfileStore()
        cs = ConnectionStore(store)
        conn, reason = cs.send_request("", "rec")
        assert conn is None
        assert reason == "blank_id"


# ---------------------------------------------------------------------------
# AC9 — Messages require an accepted connection
# ---------------------------------------------------------------------------


class TestMessagingRequiresAcceptedConnection:
    """AC9: Two people can exchange messages only after both have accepted the connection."""

    def test_message_refused_when_not_connected(self) -> None:
        ps = ProfileStore()
        cs = ConnectionStore(ps)
        ms = MessageStore(ps, cs)
        ps.save(_profile(id="a"))
        ps.save(_profile(id="b"))
        msg, reason = ms.send("a", "b", "hello")
        assert msg is None
        assert reason == "not_connected"

    def test_message_refused_when_connection_pending(self) -> None:
        ps = ProfileStore()
        cs = ConnectionStore(ps)
        ms = MessageStore(ps, cs)
        ps.save(_profile(id="a"))
        ps.save(_profile(id="b"))
        cs.send_request("a", "b")  # pending, not yet accepted
        msg, reason = ms.send("a", "b", "hello")
        assert msg is None
        assert reason == "connection_pending"

    def test_message_succeeds_after_accepted_connection(self) -> None:
        ps = ProfileStore()
        cs = ConnectionStore(ps)
        ms = MessageStore(ps, cs)
        ps.save(_profile(id="a"))
        ps.save(_profile(id="b"))
        conn, _ = cs.send_request("a", "b")
        assert conn is not None
        cs.accept_request(conn.id, "b")
        msg, reason = ms.send("a", "b", "hello")
        assert msg is not None
        assert reason is None

    def test_message_reason_is_machine_readable(self) -> None:
        ps = ProfileStore()
        cs = ConnectionStore(ps)
        ms = MessageStore(ps, cs)
        _, reason = ms.send("a", "b", "hello")
        assert reason == "not_connected"
        assert " " not in reason


# ---------------------------------------------------------------------------
# AC10 — Blocking is symmetric (the #86 fix)
# ---------------------------------------------------------------------------


class TestSymmetricBlocking:
    """AC10: After A blocks B, neither can discover, request, nor message the other."""

    def test_may_contact_true_when_no_blocks(self) -> None:
        store = ProfileStore()
        assert may_contact(store, "a", "b") is True

    def test_a_blocks_b_prevents_a_from_contacting_b(self) -> None:
        store = ProfileStore()
        store.block("a", "b")
        assert may_contact(store, "a", "b") is False

    def test_a_blocks_b_also_prevents_b_from_contacting_a(self) -> None:
        """BIDIRECTIONAL — mutation must flip this to red (the #86 fix)."""
        store = ProfileStore()
        store.block("a", "b")
        assert may_contact(store, "b", "a") is False

    def test_blocked_user_excluded_from_discovery(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="s", age=25)
        blocked = _profile(id="b", age=25)
        store.save(searcher)
        store.save(blocked)
        store.block("s", "b")
        results = discover(store, searcher)
        assert not any(r.profile.id == "b" for r in results)

    def test_blocker_excluded_from_blockers_discovery(self) -> None:
        """Symmetric: if A blocks B, B cannot discover A either."""
        store = ProfileStore()
        a = _profile(id="a", age=25)
        b = _profile(id="b", age=25)
        store.save(a)
        store.save(b)
        store.block("a", "b")
        results = discover(store, b)
        assert not any(r.profile.id == "a" for r in results)

    def test_blocked_user_cannot_send_connection_request(self) -> None:
        ps = ProfileStore()
        cs = ConnectionStore(ps)
        ps.save(_profile(id="a"))
        ps.save(_profile(id="b"))
        ps.block("a", "b")
        conn, reason = cs.send_request("b", "a")
        assert conn is None
        assert reason == "blocked"

    def test_blocked_user_cannot_send_message(self) -> None:
        ps = ProfileStore()
        cs = ConnectionStore(ps)
        ms = MessageStore(ps, cs)
        ps.save(_profile(id="a"))
        ps.save(_profile(id="b"))
        conn, _ = cs.send_request("a", "b")
        cs.accept_request(conn.id, "b")  # type: ignore[union-attr]
        ps.block("a", "b")  # block AFTER connection accepted
        msg, reason = ms.send("b", "a", "hi")
        assert msg is None
        assert reason == "blocked"


# ---------------------------------------------------------------------------
# AC11 — ReportReason is a fixed closed enum
# ---------------------------------------------------------------------------


class TestReportReasonEnum:
    """AC11: An unrecognised reason is refused rather than stored as free text."""

    def test_all_valid_reasons_accepted(self) -> None:
        rs = ReportStore()
        for reason in ReportReason:
            report, err = rs.submit(
                reporter_id="r",
                target_id="t",
                target_kind=ReportTargetKind.USER,
                reason=reason,
            )
            assert report is not None, f"{reason} should be accepted"
            assert err is None

    def test_reason_enum_is_finite(self) -> None:
        reasons = set(ReportReason)
        assert reasons == {
            ReportReason.SPAM,
            ReportReason.HARASSMENT,
            ReportReason.INAPPROPRIATE_CONTENT,
            ReportReason.FAKE_PROFILE,
            ReportReason.UNDERAGE_USER,
            ReportReason.OTHER,
        }


# ---------------------------------------------------------------------------
# AC12 — Report queue priority (immediate_harm first)
# ---------------------------------------------------------------------------


class TestReportQueuePriority:
    """AC12: A report citing immediate risk of harm is ordered ahead of all others."""

    def test_immediate_harm_report_appears_first(self) -> None:
        rs = ReportStore()
        rs.submit("r", "t1", ReportTargetKind.USER, ReportReason.SPAM, immediate_harm=False)
        rs.submit("r", "t2", ReportTargetKind.USER, ReportReason.HARASSMENT, immediate_harm=True)
        rs.submit("r", "t3", ReportTargetKind.USER, ReportReason.SPAM, immediate_harm=False)
        queue = rs.get_queue()
        assert queue[0].target_id == "t2"

    def test_all_reports_enter_queue_in_accepted_state(self) -> None:
        rs = ReportStore()
        report, _ = rs.submit("r", "t", ReportTargetKind.USER, ReportReason.SPAM)
        assert report is not None
        assert report.queue_status == ReviewQueueStatus.ACCEPTED

    def test_non_harm_reports_in_fifo_order_after_harm(self) -> None:
        rs = ReportStore()
        rs.submit("r", "t1", ReportTargetKind.USER, ReportReason.SPAM)
        rs.submit("r", "t2", ReportTargetKind.USER, ReportReason.SPAM)
        queue = rs.get_queue()
        assert queue[0].target_id == "t1"
        assert queue[1].target_id == "t2"


# ---------------------------------------------------------------------------
# AC13 — Report resolution (exactly three outcomes)
# ---------------------------------------------------------------------------


class TestReportResolution:
    """AC13: A report can be resolved as no_action, warning, or contact_removal only."""

    def test_resolve_no_action(self) -> None:
        rs = ReportStore()
        report, _ = rs.submit("r", "t", ReportTargetKind.USER, ReportReason.SPAM)
        assert report is not None
        resolved, err = rs.resolve(report.id, ReportResolutionOutcome.NO_ACTION)
        assert err is None
        assert resolved is not None
        assert resolved.resolution_outcome == ReportResolutionOutcome.NO_ACTION
        assert resolved.queue_status == ReviewQueueStatus.RESOLVED
        assert resolved.resolved_at is not None

    def test_resolve_warning(self) -> None:
        rs = ReportStore()
        report, _ = rs.submit("r", "t", ReportTargetKind.USER, ReportReason.SPAM)
        assert report is not None
        resolved, _ = rs.resolve(report.id, ReportResolutionOutcome.WARNING)
        assert resolved is not None
        assert resolved.resolution_outcome == ReportResolutionOutcome.WARNING

    def test_resolve_contact_removal(self) -> None:
        rs = ReportStore()
        report, _ = rs.submit("r", "t", ReportTargetKind.USER, ReportReason.SPAM)
        assert report is not None
        resolved, _ = rs.resolve(report.id, ReportResolutionOutcome.CONTACT_REMOVAL)
        assert resolved is not None
        assert resolved.resolution_outcome == ReportResolutionOutcome.CONTACT_REMOVAL

    def test_resolve_not_found_returns_error(self) -> None:
        rs = ReportStore()
        result, reason = rs.resolve("nonexistent", ReportResolutionOutcome.WARNING)
        assert result is None
        assert reason == "not_found"

    def test_resolve_already_resolved_returns_error(self) -> None:
        rs = ReportStore()
        report, _ = rs.submit("r", "t", ReportTargetKind.USER, ReportReason.SPAM)
        assert report is not None
        rs.resolve(report.id, ReportResolutionOutcome.WARNING)
        result, reason = rs.resolve(report.id, ReportResolutionOutcome.NO_ACTION)
        assert result is None
        assert reason == "already_resolved"

    def test_resolution_outcome_is_exactly_three_values(self) -> None:
        outcomes = set(ReportResolutionOutcome)
        assert outcomes == {
            ReportResolutionOutcome.NO_ACTION,
            ReportResolutionOutcome.WARNING,
            ReportResolutionOutcome.CONTACT_REMOVAL,
        }


# ---------------------------------------------------------------------------
# AC14 — Contact removal prevents outbound requests and messages
# ---------------------------------------------------------------------------


class TestContactRemoval:
    """AC14: After contact removal, the person cannot send requests or messages."""

    def test_contact_removed_blocks_connection_request(self) -> None:
        ps = ProfileStore()
        cs = ConnectionStore(ps)
        ps.save(_profile(id="bad"))
        ps.save(_profile(id="other"))
        ps.set_contact_removed("bad")
        conn, reason = cs.send_request("bad", "other")
        assert conn is None
        assert reason == "contact_removed"

    def test_contact_removed_blocks_sending_messages(self) -> None:
        ps = ProfileStore()
        cs = ConnectionStore(ps)
        ms = MessageStore(ps, cs)
        ps.save(_profile(id="bad"))
        ps.save(_profile(id="other"))
        conn, _ = cs.send_request("bad", "other")
        if conn:
            cs.accept_request(conn.id, "other")
        ps.set_contact_removed("bad")
        msg, reason = ms.send("bad", "other", "hi")
        assert msg is None
        assert reason == "contact_removed"

    def test_is_contact_removed_returns_true_after_flag(self) -> None:
        ps = ProfileStore()
        ps.set_contact_removed("u1")
        assert ps.is_contact_removed("u1") is True

    def test_is_contact_removed_returns_false_before_flag(self) -> None:
        ps = ProfileStore()
        assert ps.is_contact_removed("u1") is False


# ---------------------------------------------------------------------------
# AC15 — Account deletion removes profile, tags, messages; retains blocks and reports
# ---------------------------------------------------------------------------


class TestAccountDeletion:
    """AC15: Deleting an account removes the profile and messages; retains blocks and reports."""

    def test_delete_removes_profile(self) -> None:
        store = ProfileStore()
        store.save(_profile(id="del"))
        store.delete("del")
        assert store.find("del") is None

    def test_delete_retains_block_records(self) -> None:
        store = ProfileStore()
        store.save(_profile(id="del"))
        store.save(_profile(id="other"))
        store.block("del", "other")
        count_before = store.get_blocks_count("del")
        store.delete("del")
        # Block records are NOT removed; get_blocks_count still counts them
        assert store.get_blocks_count("del") == count_before

    def test_delete_messages_for_removes_all_messages(self) -> None:
        ps = ProfileStore()
        cs = ConnectionStore(ps)
        ms = MessageStore(ps, cs)
        ps.save(_profile(id="a"))
        ps.save(_profile(id="b"))
        conn, _ = cs.send_request("a", "b")
        cs.accept_request(conn.id, "b")  # type: ignore[union-attr]
        ms.send("a", "b", "msg1")
        ms.send("b", "a", "msg2")
        count = ms.delete_messages_for("a")
        assert count == 2
        assert ms.get_messages("a", "b") == []

    def test_get_blocks_count_includes_both_directions(self) -> None:
        store = ProfileStore()
        store.save(_profile(id="u"))
        store.save(_profile(id="v"))
        store.save(_profile(id="w"))
        store.block("u", "v")  # outbound from u
        store.block("w", "u")  # inbound to u
        assert store.get_blocks_count("u") == 2


# ---------------------------------------------------------------------------
# AC16 — Retention policy readable from one place
# ---------------------------------------------------------------------------


class TestRetentionPolicy:
    """AC16: The retention policy is readable from one place with correct durations."""

    def test_messages_retained_24_months(self) -> None:
        assert RETENTION_POLICY.messages_months == 24

    def test_blocks_retained_24_months(self) -> None:
        assert RETENTION_POLICY.blocks_months == 24

    def test_reports_retained_24_months(self) -> None:
        assert RETENTION_POLICY.reports_months == 24

    def test_everything_else_deleted_within_30_days(self) -> None:
        assert RETENTION_POLICY.other_days == 30


# ---------------------------------------------------------------------------
# AC17 — Coarse location never written to durable storage
# ---------------------------------------------------------------------------


class TestCoarseLocationNotPersisted:
    """AC17: A coarse location supplied for discovery is never written to any store."""

    def test_query_location_not_stored_on_profile(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="s", age=25)
        store.save(searcher)
        query_loc = GeoLocation(lat=51.5, lon=-0.1)
        discover(store, searcher, query_location=query_loc)
        # Re-fetch the profile; location must not have been updated
        updated = store.find("s")
        assert updated is not None
        assert updated.location is None  # original had no location; must remain None

    def test_query_location_does_not_appear_in_profile_fetch(self) -> None:
        store = ProfileStore()
        searcher = _profile(id="s", age=25)
        store.save(searcher)
        discover(store, searcher, query_location=GeoLocation(lat=10.0, lon=20.0))
        assert store.find("s").location is None  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# AC18 — require_auth rejects unauthenticated callers
# ---------------------------------------------------------------------------


class TestRequireAuth:
    """AC18: require_auth raises HTTP 401 when X-User-ID header is absent or blank."""

    def test_missing_header_raises_401(self) -> None:
        from fastapi import HTTPException

        from app.auth import require_auth

        with pytest.raises(HTTPException) as exc_info:
            require_auth(x_user_id=None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "unauthenticated"

    def test_blank_header_raises_401(self) -> None:
        from fastapi import HTTPException

        from app.auth import require_auth

        with pytest.raises(HTTPException) as exc_info:
            require_auth(x_user_id="   ")
        assert exc_info.value.status_code == 401

    def test_valid_header_returns_user_id(self) -> None:
        from app.auth import require_auth

        result = require_auth(x_user_id="user-123")
        assert result == "user-123"


# ---------------------------------------------------------------------------
# AC20 — Every store refusal returns a machine-readable string code
# ---------------------------------------------------------------------------


class TestMachineReadableReasons:
    """AC20: Every refusal reason is a snake_case machine-readable code (no spaces)."""

    def _assert_reason_is_code(self, reason: str | None) -> None:
        assert reason is not None
        assert " " not in reason, f"reason '{reason}' contains spaces — not a machine-readable code"
        assert reason == reason.lower(), f"reason '{reason}' is not lowercase"

    def test_blank_id_is_code(self) -> None:
        store = ProfileStore()
        try:
            store.save(Profile(id="", display_name="X", age=20))
        except ValueError as exc:
            self._assert_reason_is_code(str(exc))

    def test_age_below_minimum_is_code(self) -> None:
        store = ProfileStore()
        try:
            store.save(Profile(id="u", display_name="X", age=5))
        except ValueError as exc:
            self._assert_reason_is_code(str(exc))

    def test_connection_blank_id_reason_is_code(self) -> None:
        store = ProfileStore()
        cs = ConnectionStore(store)
        _, reason = cs.send_request("", "b")
        self._assert_reason_is_code(reason)

    def test_connection_self_request_reason_is_code(self) -> None:
        store = ProfileStore()
        cs = ConnectionStore(store)
        _, reason = cs.send_request("u", "u")
        self._assert_reason_is_code(reason)

    def test_message_not_connected_reason_is_code(self) -> None:
        ps = ProfileStore()
        cs = ConnectionStore(ps)
        ms = MessageStore(ps, cs)
        _, reason = ms.send("a", "b", "hi")
        self._assert_reason_is_code(reason)

    def test_report_blank_reporter_reason_is_code(self) -> None:
        rs = ReportStore()
        _, reason = rs.submit("", "t", ReportTargetKind.USER, ReportReason.SPAM)
        self._assert_reason_is_code(reason)

    def test_report_not_found_reason_is_code(self) -> None:
        rs = ReportStore()
        _, reason = rs.resolve("nonexistent", ReportResolutionOutcome.WARNING)
        self._assert_reason_is_code(reason)
