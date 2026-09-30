"""Tests for the MyFriends domain rules (plan step 3).

Each test targets one rule; a comment marks the acceptance criterion or
constitution clause it covers.

The key invariant verified here is bidirectional blocking — the fix for #86:
    "the messaging path and the connection-request path disagreed about what
    'blocked' means"
All three surfaces (discovery, connection requests, messages) must check
may_contact, which returns False when *either* party has blocked the other.

Mutation target (plan, step 3): if may_contact is reverted to a one-directional
check (`not store.is_blocked(a, b)` only), the tests marked
    # BIDIRECTIONAL — mutation must flip this to red
must fail.  That is what this test suite is here to prove.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain import (
    AgeAssuranceStatus,
    AgeBracket,
    GeoLocation,
    Profile,
    ReportReason,
    ReportTargetKind,
    age_bracket,
)
from app.main import app
from app.store import (
    MIN_AGE,
    ConnectionStore,
    MessageStore,
    ProfileStore,
    ReportStore,
    discover,
    may_contact,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(**kwargs) -> Profile:  # type: ignore[no-untyped-def]
    defaults = {"id": "u1", "display_name": "User One", "age": 25, "open_to_friends": True}
    defaults.update(kwargs)
    return Profile(**defaults)


# ---------------------------------------------------------------------------
# may_contact (the #86 fix)
# ---------------------------------------------------------------------------


class TestMayContact:
    def test_both_unblocked(self) -> None:
        """Two strangers may contact each other."""
        store = ProfileStore()
        store.save(_make_profile(id="alice"))
        store.save(_make_profile(id="bob"))
        assert may_contact(store, "alice", "bob") is True

    def test_a_blocks_b_prevents_a_contacting_b(self) -> None:
        """If A blocks B, A cannot contact B."""
        store = ProfileStore()
        store.block("alice", "bob")
        assert may_contact(store, "alice", "bob") is False

    def test_a_blocks_b_prevents_b_contacting_a(
        self,
    ) -> None:  # BIDIRECTIONAL — mutation must flip this to red
        """If A blocks B, B cannot contact A either (the #86 fix)."""
        store = ProfileStore()
        store.block("alice", "bob")
        assert may_contact(store, "bob", "alice") is False  # symmetric

    def test_b_blocks_a_prevents_a_contacting_b(
        self,
    ) -> None:  # BIDIRECTIONAL — mutation must flip this to red
        """If B blocks A, A cannot contact B (symmetric in both argument orders)."""
        store = ProfileStore()
        store.block("bob", "alice")
        assert may_contact(store, "alice", "bob") is False


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class TestDiscovery:
    def test_includes_open_profile(self) -> None:
        """A profile with open_to_friends=True appears in discovery."""
        store = ProfileStore()
        searcher = _make_profile(id="s", open_to_friends=True, age=25)
        candidate = _make_profile(id="c", open_to_friends=True, age=30)
        store.save(searcher)
        store.save(candidate)
        store.set_age_assurance("c", AgeAssuranceStatus.PASSED)
        results = discover(store, searcher)
        assert any(r.profile.id == "c" for r in results)

    def test_excludes_closed_profile(self) -> None:
        """A profile with open_to_friends=False is excluded from discovery (AC#2)."""
        store = ProfileStore()
        searcher = _make_profile(id="s", open_to_friends=True, age=25)
        candidate = _make_profile(id="c", open_to_friends=False, age=30)
        store.save(searcher)
        store.save(candidate)
        results = discover(store, searcher)
        assert not any(r.profile.id == "c" for r in results)

    def test_excludes_blocked_profile_when_searcher_blocked(
        self,
    ) -> None:  # BIDIRECTIONAL — mutation must flip this to red
        """A profile blocked by the searcher is excluded from discovery (AC#7)."""
        store = ProfileStore()
        searcher = _make_profile(id="s", open_to_friends=True, age=25)
        candidate = _make_profile(id="c", open_to_friends=True, age=30)
        store.save(searcher)
        store.save(candidate)
        store.block("s", "c")
        results = discover(store, searcher)
        assert not any(r.profile.id == "c" for r in results)

    def test_excludes_blocked_profile_when_candidate_blocked_searcher(
        self,
    ) -> None:  # BIDIRECTIONAL — mutation must flip this to red
        """A profile that has blocked the searcher is also excluded (AC#7, P5 — the #86 fix)."""
        store = ProfileStore()
        searcher = _make_profile(id="s", open_to_friends=True, age=25)
        candidate = _make_profile(id="c", open_to_friends=True, age=30)
        store.save(searcher)
        store.save(candidate)
        store.block("c", "s")  # candidate blocks searcher
        results = discover(store, searcher)
        assert not any(r.profile.id == "c" for r in results)

    def test_age_bracket_isolation_adult_cannot_see_minor(self) -> None:
        """An adult never discovers a minor (spec: compliance / age assurance)."""
        store = ProfileStore()
        adult = _make_profile(id="adult", open_to_friends=True, age=25)
        minor = _make_profile(id="minor", open_to_friends=True, age=17)
        store.save(adult)
        store.save(minor)
        results = discover(store, adult)
        assert not any(r.profile.id == "minor" for r in results)

    def test_age_bracket_isolation_minor_cannot_see_adult(self) -> None:
        """A minor never discovers an adult (spec: compliance / age assurance)."""
        store = ProfileStore()
        minor = _make_profile(id="minor", open_to_friends=True, age=16)
        adult = _make_profile(id="adult", open_to_friends=True, age=30)
        store.save(minor)
        store.save(adult)
        results = discover(store, minor)
        assert not any(r.profile.id == "adult" for r in results)

    def test_age_bracket_isolation_minors_discover_each_other(self) -> None:
        """Two minors can discover each other (age bracket isolation, not exclusion)."""
        store = ProfileStore()
        m1 = _make_profile(id="m1", open_to_friends=True, age=16)
        m2 = _make_profile(id="m2", open_to_friends=True, age=17)
        store.save(m1)
        store.save(m2)
        store.set_age_assurance("m2", AgeAssuranceStatus.PASSED)
        results = discover(store, m1)
        assert any(r.profile.id == "m2" for r in results)

    def test_radius_filter(self) -> None:
        """Profiles beyond the chosen radius are excluded (AC#3)."""
        store = ProfileStore()
        searcher = _make_profile(
            id="s",
            open_to_friends=True,
            age=25,
        )
        searcher.location = GeoLocation(lat=51.5, lon=-0.1)  # London

        nearby = _make_profile(id="nearby", open_to_friends=True, age=26)
        nearby.location = GeoLocation(lat=51.51, lon=-0.1)  # ~1 km away

        far = _make_profile(id="far", open_to_friends=True, age=27)
        far.location = GeoLocation(lat=53.48, lon=-2.24)  # Manchester, ~270 km

        store.save(searcher)
        store.save(nearby)
        store.save(far)
        # Both candidates need PASSED age assurance to be eligible; the radius
        # filter is what removes "far" from results.
        store.set_age_assurance("nearby", AgeAssuranceStatus.PASSED)
        store.set_age_assurance("far", AgeAssuranceStatus.PASSED)
        results = discover(store, searcher, radius_km=5)
        ids = {r.profile.id for r in results}
        assert "nearby" in ids
        assert "far" not in ids

    def test_results_sorted_by_score_descending(self) -> None:
        """Discovery results are ordered by match score descending (AC#4)."""
        store = ProfileStore()
        searcher = _make_profile(id="s", open_to_friends=True, age=25, interests=["a", "b", "c"])
        good_match = _make_profile(
            id="good", open_to_friends=True, age=26, interests=["a", "b", "c"]
        )
        poor_match = _make_profile(id="poor", open_to_friends=True, age=27, interests=["x"])
        store.save(searcher)
        store.save(good_match)
        store.save(poor_match)
        store.set_age_assurance("good", AgeAssuranceStatus.PASSED)
        store.set_age_assurance("poor", AgeAssuranceStatus.PASSED)
        results = discover(store, searcher)
        ids = [r.profile.id for r in results]
        assert ids.index("good") < ids.index("poor")


# ---------------------------------------------------------------------------
# Connection requests
# ---------------------------------------------------------------------------


class TestConnectionRequests:
    def test_successful_request(self) -> None:
        """A valid connection request creates a pending connection (AC#5)."""
        store = ProfileStore()
        cs = ConnectionStore(store)
        conn, reason = cs.send_request("alice", "bob")
        assert conn is not None
        assert reason is None
        assert conn.requester_id == "alice"
        assert conn.recipient_id == "bob"

    def test_blocked_prevents_request(
        self,
    ) -> None:  # BIDIRECTIONAL — mutation must flip this to red
        """A blocked pair cannot send connection requests in either direction (AC#7)."""
        store = ProfileStore()
        store.block("alice", "bob")
        cs = ConnectionStore(store)
        # Alice → Bob (alice blocked bob)
        conn, reason = cs.send_request("alice", "bob")
        assert conn is None
        assert reason == "blocked"
        # Bob → Alice (bidirectional — the #86 fix)
        conn, reason = cs.send_request("bob", "alice")
        assert conn is None
        assert reason == "blocked"

    def test_self_request_refused(self) -> None:
        """A person cannot send a connection request to themselves."""
        store = ProfileStore()
        cs = ConnectionStore(store)
        conn, reason = cs.send_request("alice", "alice")
        assert conn is None
        assert reason == "self_request"

    def test_duplicate_request_refused(self) -> None:
        """A duplicate connection request is refused."""
        store = ProfileStore()
        cs = ConnectionStore(store)
        cs.send_request("alice", "bob")
        conn, reason = cs.send_request("alice", "bob")
        assert conn is None
        assert reason == "already_exists"

    def test_rate_limit(self) -> None:
        """At most 20 connection requests per day (AC#5)."""
        store = ProfileStore()
        cs = ConnectionStore(store)
        for i in range(20):
            conn, _ = cs.send_request("alice", f"user-{i}")
            assert conn is not None
        conn, reason = cs.send_request("alice", "user-overflow")
        assert conn is None
        assert reason == "rate_limit_exceeded"

    def test_accept_enables_messaging(self) -> None:
        """Accepting a connection enables messaging (AC#6)."""
        store = ProfileStore()
        cs = ConnectionStore(store)
        conn, _ = cs.send_request("alice", "bob")
        assert conn is not None
        assert not cs.are_connected("alice", "bob")
        ok = cs.accept_request(conn.id, "bob")
        assert ok is True
        assert cs.are_connected("alice", "bob")


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------


class TestMessaging:
    def _connected_pair(self) -> tuple[ProfileStore, ConnectionStore, MessageStore]:
        store = ProfileStore()
        cs = ConnectionStore(store)
        ms = MessageStore(store, cs)
        conn, _ = cs.send_request("alice", "bob")
        assert conn is not None
        cs.accept_request(conn.id, "bob")
        return store, cs, ms

    def test_message_after_connection_accepted(self) -> None:
        """Two connected users can exchange messages (AC#6)."""
        _store, _cs, ms = self._connected_pair()
        msg, reason = ms.send("alice", "bob", "hello")
        assert msg is not None
        assert reason is None

    def test_message_before_connection_refused(self) -> None:
        """Messaging is refused when no accepted connection exists (AC#6)."""
        store = ProfileStore()
        cs = ConnectionStore(store)
        ms = MessageStore(store, cs)
        msg, reason = ms.send("alice", "bob", "hello")
        assert msg is None
        assert reason == "not_connected"

    def test_blocked_prevents_messaging_by_blocker(self) -> None:
        """A user cannot message someone they have blocked (AC#7)."""
        store, _cs, ms = self._connected_pair()
        store.block("alice", "bob")
        msg, reason = ms.send("alice", "bob", "hello")
        assert msg is None
        assert reason == "blocked"

    def test_blocked_prevents_messaging_by_blocked_party(
        self,
    ) -> None:  # BIDIRECTIONAL — mutation must flip this to red
        """A blocked user cannot message the person who blocked them (AC#7, P5 — the #86 fix)."""
        store, _cs, ms = self._connected_pair()
        store.block("alice", "bob")  # Alice blocks Bob
        msg, reason = ms.send("bob", "alice", "hello")  # Bob tries to message Alice
        assert msg is None
        assert reason == "blocked"

    def test_blank_body_refused(self) -> None:
        """A blank message body is refused."""
        _store, _cs, ms = self._connected_pair()
        msg, reason = ms.send("alice", "bob", "   ")
        assert msg is None
        assert reason == "blank_body"


# ---------------------------------------------------------------------------
# Reports (AC#8 / P5)
# ---------------------------------------------------------------------------


class TestReports:
    def test_submit_user_report(self) -> None:
        """A person can report another person with a fixed reason (AC#8)."""
        rs = ReportStore()
        report = rs.submit("alice", "bob", ReportTargetKind.USER, ReportReason.SPAM)
        assert report is not None
        assert report.reason == ReportReason.SPAM

    def test_submit_message_report(self) -> None:
        """A person can report a message (AC#8)."""
        rs = ReportStore()
        report = rs.submit("alice", "msg-1", ReportTargetKind.MESSAGE, ReportReason.HARASSMENT)
        assert report is not None
        assert report.target_kind == ReportTargetKind.MESSAGE

    def test_report_with_optional_text(self) -> None:
        """A report can include optional free text (AC#8)."""
        rs = ReportStore()
        report = rs.submit(
            "alice", "bob", ReportTargetKind.USER, ReportReason.OTHER, "more context"
        )
        assert report is not None
        assert report.additional_text == "more context"

    def test_blank_reporter_id_rejected(self) -> None:
        """A report with a blank reporter id is rejected."""
        rs = ReportStore()
        report = rs.submit("", "bob", ReportTargetKind.USER, ReportReason.SPAM)
        assert report is None

    def test_free_text_trimmed(self) -> None:
        """Free text is trimmed before storage."""
        rs = ReportStore()
        report = rs.submit("alice", "bob", ReportTargetKind.USER, ReportReason.OTHER, "  trimmed  ")
        assert report is not None
        assert report.additional_text == "trimmed"


# ---------------------------------------------------------------------------
# Profile age validation (C3)
# ---------------------------------------------------------------------------


class TestProfileAgeValidation:
    """C3: An account whose stated age is under 16 is refused at creation,
    and the refusal names age as the reason.

    MIN_AGE is the single source of truth for the minimum allowed age (store.py).
    The enforcement point is ProfileStore.save(), re-raised as HTTP 422 by the
    create_profile endpoint in main.py.
    """

    def test_store_refuses_age_below_minimum(self) -> None:
        """ProfileStore.save raises ValueError naming 'age' when age < MIN_AGE."""
        store = ProfileStore()
        profile = _make_profile(id="underage", age=MIN_AGE - 1)
        with pytest.raises(ValueError, match="age"):
            store.save(profile)

    def test_store_refuses_age_zero(self) -> None:
        """Age 0 is also below the minimum and must be refused."""
        store = ProfileStore()
        profile = _make_profile(id="zero-age", age=0)
        with pytest.raises(ValueError, match="age"):
            store.save(profile)

    def test_store_accepts_minimum_age(self) -> None:
        """ProfileStore.save accepts age == MIN_AGE (boundary value)."""
        store = ProfileStore()
        profile = _make_profile(id="just-min", age=MIN_AGE)
        store.save(profile)  # must not raise

    def test_store_accepts_adult_age(self) -> None:
        """ProfileStore.save accepts age 18 (adult bracket)."""
        store = ProfileStore()
        profile = _make_profile(id="adult", age=18)
        store.save(profile)  # must not raise

    def test_api_refuses_age_below_minimum(self) -> None:
        """POST /profiles with age=15 returns 422 and the detail names 'age' (C3)."""
        resp = client.post(
            "/profiles",
            json={"id": "underage-c3", "display_name": "Too Young", "age": MIN_AGE - 1},
        )
        assert resp.status_code == 422
        detail = str(resp.json().get("detail", ""))
        assert "age" in detail.lower()

    def test_api_refuses_age_zero(self) -> None:
        """POST /profiles with age=0 returns 422 and the detail names 'age' (C3)."""
        resp = client.post(
            "/profiles",
            json={"id": "zero-age-c3", "display_name": "Zero Age", "age": 0},
        )
        assert resp.status_code == 422
        detail = str(resp.json().get("detail", ""))
        assert "age" in detail.lower()

    def test_api_accepts_minimum_age(self) -> None:
        """POST /profiles with age=MIN_AGE is accepted (boundary value — C3)."""
        resp = client.post(
            "/profiles",
            json={"id": "min-age-c3", "display_name": "Just Sixteen", "age": MIN_AGE},
        )
        assert resp.status_code == 201

    def test_api_accepts_adult_age(self) -> None:
        """POST /profiles with age=25 is accepted (normal adult case — C3)."""
        resp = client.post(
            "/profiles",
            json={"id": "adult-c3", "display_name": "Adult User", "age": 25},
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Age bracket isolation (C4)
# ---------------------------------------------------------------------------


class TestAgeBracketIsolation:
    """C4: A person under 18 is never eligible for discovery by a person 18
    or over, and a person 18 or over is never eligible for discovery by a
    person under 18, so adults and minors cannot reach each other at all.

    The boundary is age < 18 → MINOR, age >= 18 → ADULT (domain.py).
    The single enforcement point is the age-bracket check in store.discover().
    """

    def test_boundary_17_is_minor(self) -> None:
        """age_bracket(17) returns MINOR — the boundary just below 18 (C4)."""
        assert age_bracket(17) == AgeBracket.MINOR

    def test_boundary_18_is_adult(self) -> None:
        """age_bracket(18) returns ADULT — the boundary at 18 (C4)."""
        assert age_bracket(18) == AgeBracket.ADULT

    def test_adult_cannot_discover_minor_at_boundary(self) -> None:
        """An 18-year-old (ADULT) never discovers a 17-year-old (MINOR) (C4)."""
        store = ProfileStore()
        adult = _make_profile(id="adult-c4-a", open_to_friends=True, age=18)
        minor = _make_profile(id="minor-c4-a", open_to_friends=True, age=17)
        store.save(adult)
        store.save(minor)
        results = discover(store, adult)
        assert not any(r.profile.id == "minor-c4-a" for r in results)

    def test_minor_cannot_discover_adult_at_boundary(self) -> None:
        """A 17-year-old (MINOR) never discovers an 18-year-old (ADULT) (C4)."""
        store = ProfileStore()
        adult = _make_profile(id="adult-c4-b", open_to_friends=True, age=18)
        minor = _make_profile(id="minor-c4-b", open_to_friends=True, age=17)
        store.save(adult)
        store.save(minor)
        results = discover(store, minor)
        assert not any(r.profile.id == "adult-c4-b" for r in results)

    def test_adults_can_discover_each_other(self) -> None:
        """Two adults (both 18+) can discover each other — isolation is between groups, not total (C4)."""
        store = ProfileStore()
        a1 = _make_profile(id="adult-c4-c1", open_to_friends=True, age=18)
        a2 = _make_profile(id="adult-c4-c2", open_to_friends=True, age=25)
        store.save(a1)
        store.save(a2)
        store.set_age_assurance("adult-c4-c2", AgeAssuranceStatus.PASSED)
        results = discover(store, a1)
        assert any(r.profile.id == "adult-c4-c2" for r in results)

    def test_minors_can_discover_each_other(self) -> None:
        """Two minors (both under 18) can discover each other — isolation is between groups (C4)."""
        store = ProfileStore()
        m1 = _make_profile(id="minor-c4-d1", open_to_friends=True, age=16)
        m2 = _make_profile(id="minor-c4-d2", open_to_friends=True, age=17)
        store.save(m1)
        store.save(m2)
        store.set_age_assurance("minor-c4-d2", AgeAssuranceStatus.PASSED)
        results = discover(store, m1)
        assert any(r.profile.id == "minor-c4-d2" for r in results)

    def test_isolation_is_symmetric_adult_to_minor(self) -> None:
        """Isolation works both ways: adult cannot see minor even when minor is open (C4).

        Both profiles are given PASSED age assurance so that only the age-bracket
        rule causes the exclusion — the test directly verifies that rule.
        """
        store = ProfileStore()
        adult = _make_profile(id="adult-c4-sym", open_to_friends=True, age=30)
        minor = _make_profile(id="minor-c4-sym", open_to_friends=True, age=16)
        store.save(adult)
        store.save(minor)
        store.set_age_assurance("adult-c4-sym", AgeAssuranceStatus.PASSED)
        store.set_age_assurance("minor-c4-sym", AgeAssuranceStatus.PASSED)
        adult_sees = [r.profile.id for r in discover(store, adult)]
        minor_sees = [r.profile.id for r in discover(store, minor)]
        assert "minor-c4-sym" not in adult_sees
        assert "adult-c4-sym" not in minor_sees


# ---------------------------------------------------------------------------
# API-level tests (via TestClient)
# ---------------------------------------------------------------------------


class TestAPI:
    def test_healthz(self) -> None:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_profile_me_returns_placeholder(self) -> None:
        resp = client.get("/profiles/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "placeholder"
        assert "display_name" in body

    def test_create_and_get_profile(self) -> None:
        resp = client.post(
            "/profiles",
            json={
                "id": "test-user-api",
                "display_name": "Test User",
                "age": 25,
                "open_to_friends": True,
            },
        )
        assert resp.status_code == 201
        resp2 = client.get("/profiles/test-user-api")
        assert resp2.status_code == 200
        assert resp2.json()["display_name"] == "Test User"

    def test_block_endpoint(self) -> None:
        resp = client.post("/blocks", json={"blocker_id": "alice-api", "blocked_id": "bob-api"})
        assert resp.status_code == 204

    def test_may_contact_endpoint_after_block(self) -> None:
        client.post("/blocks", json={"blocker_id": "x-api", "blocked_id": "y-api"})
        resp = client.get("/may-contact/x-api/y-api")
        assert resp.status_code == 200
        assert resp.json()["may_contact"] is False
        # Bidirectional
        resp2 = client.get("/may-contact/y-api/x-api")
        assert resp2.status_code == 200
        assert resp2.json()["may_contact"] is False

    def test_submit_report_endpoint(self) -> None:
        resp = client.post(
            "/reports",
            json={
                "reporter_id": "reporter-api",
                "target_id": "target-api",
                "target_kind": "user",
                "reason": "spam",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["reason"] == "spam"

    def test_discovery_age_bracket_isolation(self) -> None:
        """Discovery API excludes profiles in the wrong age bracket."""
        client.post(
            "/profiles",
            json={"id": "adult-disc", "display_name": "Adult", "age": 30, "open_to_friends": True},
        )
        client.post(
            "/profiles/adult-disc/age-assurance",
            json={"status": "passed"},
        )
        client.post(
            "/profiles",
            json={"id": "minor-disc", "display_name": "Minor", "age": 17, "open_to_friends": True},
        )
        resp = client.get("/discovery/adult-disc?radius_km=25")
        assert resp.status_code == 200
        ids = [r["profile"]["id"] for r in resp.json()]
        assert "minor-disc" not in ids


# ---------------------------------------------------------------------------
# Age assurance (C5)
# ---------------------------------------------------------------------------


class TestAgeAssurance:
    """C5: An account is eligible for discovery only once age assurance is
    recorded as passed; an account with age assurance unrecorded or failed is
    ineligible, and the API says which.

    The default AgeAssuranceStatus is UNRECORDED. The store's discover()
    filters out any candidate whose status is not PASSED. The discovery
    endpoint refuses a searcher whose own status is not PASSED, naming
    whether it is 'unrecorded' or 'failed' in the response detail.
    """

    # --- Domain / store tests ---

    def test_new_profile_has_unrecorded_status(self) -> None:
        """A freshly saved profile defaults to UNRECORDED age assurance (C5)."""
        store = ProfileStore()
        p = _make_profile(id="aa-new", open_to_friends=True, age=25)
        store.save(p)
        assert store.find("aa-new").age_assurance_status == AgeAssuranceStatus.UNRECORDED  # type: ignore[union-attr]

    def test_set_age_assurance_passed(self) -> None:
        """set_age_assurance() records PASSED for an existing profile (C5)."""
        store = ProfileStore()
        p = _make_profile(id="aa-pass", open_to_friends=True, age=25)
        store.save(p)
        store.set_age_assurance("aa-pass", AgeAssuranceStatus.PASSED)
        assert store.find("aa-pass").age_assurance_status == AgeAssuranceStatus.PASSED  # type: ignore[union-attr]

    def test_set_age_assurance_failed(self) -> None:
        """set_age_assurance() records FAILED for an existing profile (C5)."""
        store = ProfileStore()
        p = _make_profile(id="aa-fail", open_to_friends=True, age=25)
        store.save(p)
        store.set_age_assurance("aa-fail", AgeAssuranceStatus.FAILED)
        assert store.find("aa-fail").age_assurance_status == AgeAssuranceStatus.FAILED  # type: ignore[union-attr]

    def test_unrecorded_candidate_excluded_from_discovery(self) -> None:
        """A candidate with UNRECORDED age assurance is excluded from discovery results (C5)."""
        store = ProfileStore()
        searcher = _make_profile(id="aa-s1", open_to_friends=True, age=25)
        store.save(searcher)
        store.set_age_assurance("aa-s1", AgeAssuranceStatus.PASSED)
        candidate = _make_profile(id="aa-c1", open_to_friends=True, age=30)
        store.save(candidate)
        # candidate retains UNRECORDED (default)
        results = discover(store, searcher)
        assert not any(r.profile.id == "aa-c1" for r in results)

    def test_failed_candidate_excluded_from_discovery(self) -> None:
        """A candidate with FAILED age assurance is excluded from discovery results (C5)."""
        store = ProfileStore()
        searcher = _make_profile(id="aa-s2", open_to_friends=True, age=25)
        store.save(searcher)
        store.set_age_assurance("aa-s2", AgeAssuranceStatus.PASSED)
        candidate = _make_profile(id="aa-c2", open_to_friends=True, age=30)
        store.save(candidate)
        store.set_age_assurance("aa-c2", AgeAssuranceStatus.FAILED)
        results = discover(store, searcher)
        assert not any(r.profile.id == "aa-c2" for r in results)

    def test_passed_candidate_appears_in_discovery(self) -> None:
        """A candidate with PASSED age assurance appears in discovery results (C5)."""
        store = ProfileStore()
        searcher = _make_profile(id="aa-s3", open_to_friends=True, age=25)
        store.save(searcher)
        store.set_age_assurance("aa-s3", AgeAssuranceStatus.PASSED)
        candidate = _make_profile(id="aa-c3", open_to_friends=True, age=30)
        store.save(candidate)
        store.set_age_assurance("aa-c3", AgeAssuranceStatus.PASSED)
        results = discover(store, searcher)
        assert any(r.profile.id == "aa-c3" for r in results)

    # --- API-level tests ---

    def test_api_discovery_refuses_unrecorded_searcher_with_reason(self) -> None:
        """GET /discovery/{id} returns 403 and names 'unrecorded' when searcher has no age assurance (C5)."""
        client.post(
            "/profiles",
            json={"id": "aa-api-s1", "display_name": "S1", "age": 25, "open_to_friends": True},
        )
        # No age-assurance call — status remains UNRECORDED
        resp = client.get("/discovery/aa-api-s1?radius_km=25")
        assert resp.status_code == 403
        assert "unrecorded" in resp.json()["detail"]

    def test_api_discovery_refuses_failed_searcher_with_reason(self) -> None:
        """GET /discovery/{id} returns 403 and names 'failed' when searcher's age assurance failed (C5)."""
        client.post(
            "/profiles",
            json={"id": "aa-api-s2", "display_name": "S2", "age": 25, "open_to_friends": True},
        )
        client.post("/profiles/aa-api-s2/age-assurance", json={"status": "failed"})
        resp = client.get("/discovery/aa-api-s2?radius_km=25")
        assert resp.status_code == 403
        assert "failed" in resp.json()["detail"]

    def test_api_discovery_succeeds_when_searcher_passed(self) -> None:
        """GET /discovery/{id} succeeds (200) when searcher's age assurance is PASSED (C5)."""
        client.post(
            "/profiles",
            json={"id": "aa-api-s3", "display_name": "S3", "age": 25, "open_to_friends": True},
        )
        client.post("/profiles/aa-api-s3/age-assurance", json={"status": "passed"})
        resp = client.get("/discovery/aa-api-s3?radius_km=25")
        assert resp.status_code == 200

    def test_api_discovery_excludes_candidate_without_age_assurance(self) -> None:
        """Discovery results omit candidates whose age assurance has not passed (C5)."""
        client.post(
            "/profiles",
            json={"id": "aa-api-s4", "display_name": "S4", "age": 25, "open_to_friends": True},
        )
        client.post("/profiles/aa-api-s4/age-assurance", json={"status": "passed"})
        client.post(
            "/profiles",
            json={"id": "aa-api-c4", "display_name": "C4", "age": 26, "open_to_friends": True},
        )
        # candidate has UNRECORDED status — must not appear
        resp = client.get("/discovery/aa-api-s4?radius_km=25")
        assert resp.status_code == 200
        ids = [r["profile"]["id"] for r in resp.json()]
        assert "aa-api-c4" not in ids

    def test_api_discovery_includes_candidate_with_passed_assurance(self) -> None:
        """Discovery results include candidates whose age assurance is PASSED (C5)."""
        client.post(
            "/profiles",
            json={"id": "aa-api-s5", "display_name": "S5", "age": 25, "open_to_friends": True},
        )
        client.post("/profiles/aa-api-s5/age-assurance", json={"status": "passed"})
        client.post(
            "/profiles",
            json={"id": "aa-api-c5", "display_name": "C5", "age": 26, "open_to_friends": True},
        )
        client.post("/profiles/aa-api-c5/age-assurance", json={"status": "passed"})
        resp = client.get("/discovery/aa-api-s5?radius_km=25")
        assert resp.status_code == 200
        ids = [r["profile"]["id"] for r in resp.json()]
        assert "aa-api-c5" in ids

    def test_api_record_age_assurance_returns_updated_profile(self) -> None:
        """POST /profiles/{id}/age-assurance returns the profile with the new status (C5)."""
        client.post(
            "/profiles",
            json={"id": "aa-api-rec", "display_name": "Rec", "age": 25},
        )
        resp = client.post("/profiles/aa-api-rec/age-assurance", json={"status": "passed"})
        assert resp.status_code == 200
        assert resp.json()["age_assurance_status"] == "passed"

    def test_api_record_age_assurance_unknown_profile_404(self) -> None:
        """POST /profiles/{id}/age-assurance returns 404 for a missing profile (C5)."""
        resp = client.post(
            "/profiles/no-such-profile/age-assurance", json={"status": "passed"}
        )
        assert resp.status_code == 404

    def test_api_record_age_assurance_refuses_unrecorded_status(self) -> None:
        """POST /profiles/{id}/age-assurance rejects 'unrecorded' as a target status (C5)."""
        client.post(
            "/profiles",
            json={"id": "aa-api-unr", "display_name": "Unr", "age": 25},
        )
        resp = client.post(
            "/profiles/aa-api-unr/age-assurance", json={"status": "unrecorded"}
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# C7: Discovery with match score ordered by shared interest tags
# ---------------------------------------------------------------------------


class TestC7DiscoveryMatchScore:
    """C7: Discovery returns only people who currently have 'open to new friends'
    turned on, ordered by a match score computed from shared interest tags, and
    the API returns the score with each result.

    Three requirements:
    1. Only open_to_friends=True candidates appear in results.
    2. The match score is computed from shared interest tags; a candidate who
       shares more tags ranks higher than one who shares fewer.
    3. The score field is present in every DiscoveryResult returned by the API.
    """

    # --- Domain / store tests ---

    def test_only_open_profiles_in_results(self) -> None:
        """discover() excludes profiles with open_to_friends=False (C7 / AC#2)."""
        store = ProfileStore()
        searcher = _make_profile(
            id="c7-s1", open_to_friends=True, age=25, interests=["reading"]
        )
        open_p = _make_profile(
            id="c7-open", open_to_friends=True, age=30, interests=["reading"]
        )
        closed_p = _make_profile(
            id="c7-closed", open_to_friends=False, age=30, interests=["reading"]
        )
        store.save(searcher)
        store.save(open_p)
        store.save(closed_p)
        store.set_age_assurance("c7-open", AgeAssuranceStatus.PASSED)
        store.set_age_assurance("c7-closed", AgeAssuranceStatus.PASSED)
        results = discover(store, searcher)
        ids = [r.profile.id for r in results]
        assert "c7-open" in ids
        assert "c7-closed" not in ids

    def test_score_is_fraction_of_shared_interests(self) -> None:
        """Score equals the fraction of the searcher's interests shared by the
        candidate when the searcher carries no activities (C7)."""
        store = ProfileStore()
        searcher = _make_profile(
            id="c7-s2", open_to_friends=True, age=25, interests=["a", "b", "c"]
        )
        # Candidate shares 2 of 3 interests → score = 2/3 ≈ 0.667
        candidate = _make_profile(
            id="c7-c2", open_to_friends=True, age=30, interests=["a", "b", "z"]
        )
        store.save(searcher)
        store.save(candidate)
        store.set_age_assurance("c7-c2", AgeAssuranceStatus.PASSED)
        results = discover(store, searcher)
        assert len(results) == 1
        expected_score = 2 / 3
        assert abs(results[0].score - expected_score) < 1e-9

    def test_shared_interests_populated_in_result(self) -> None:
        """shared_interests in DiscoveryResult lists the common interest tags (C7)."""
        store = ProfileStore()
        searcher = _make_profile(
            id="c7-s3", open_to_friends=True, age=25, interests=["hiking", "reading", "cooking"]
        )
        candidate = _make_profile(
            id="c7-c3", open_to_friends=True, age=30, interests=["hiking", "cooking", "gaming"]
        )
        store.save(searcher)
        store.save(candidate)
        store.set_age_assurance("c7-c3", AgeAssuranceStatus.PASSED)
        results = discover(store, searcher)
        assert len(results) == 1
        shared = sorted(results[0].shared_interests)
        assert shared == ["cooking", "hiking"]

    def test_results_ordered_by_interest_score_descending(self) -> None:
        """Higher interest overlap ranks first in discovery results (C7)."""
        store = ProfileStore()
        searcher = _make_profile(
            id="c7-s4", open_to_friends=True, age=25, interests=["a", "b", "c", "d"]
        )
        # best: shares 4/4 → score 1.0
        best = _make_profile(
            id="c7-best", open_to_friends=True, age=26, interests=["a", "b", "c", "d"]
        )
        # middle: shares 2/4 → score 0.5
        middle = _make_profile(
            id="c7-mid", open_to_friends=True, age=27, interests=["a", "b", "x", "y"]
        )
        # worst: shares 0/4 → score 0.0
        worst = _make_profile(
            id="c7-worst", open_to_friends=True, age=28, interests=["p", "q", "r", "s"]
        )
        store.save(searcher)
        store.save(best)
        store.save(middle)
        store.save(worst)
        for pid in ("c7-best", "c7-mid", "c7-worst"):
            store.set_age_assurance(pid, AgeAssuranceStatus.PASSED)
        results = discover(store, searcher)
        ids = [r.profile.id for r in results]
        assert ids.index("c7-best") < ids.index("c7-mid")
        assert ids.index("c7-mid") < ids.index("c7-worst")

    def test_zero_score_when_no_shared_interests(self) -> None:
        """Score is 0.0 when no interest tags overlap (C7)."""
        store = ProfileStore()
        searcher = _make_profile(
            id="c7-s5", open_to_friends=True, age=25, interests=["a", "b"]
        )
        candidate = _make_profile(
            id="c7-c5", open_to_friends=True, age=30, interests=["x", "y"]
        )
        store.save(searcher)
        store.save(candidate)
        store.set_age_assurance("c7-c5", AgeAssuranceStatus.PASSED)
        results = discover(store, searcher)
        assert len(results) == 1
        assert results[0].score == 0.0

    def test_full_score_when_all_interests_shared(self) -> None:
        """Score is 1.0 when the candidate shares all of the searcher's interests (C7)."""
        store = ProfileStore()
        searcher = _make_profile(
            id="c7-s6", open_to_friends=True, age=25, interests=["hiking", "cooking"]
        )
        candidate = _make_profile(
            id="c7-c6", open_to_friends=True, age=30, interests=["hiking", "cooking", "extra"]
        )
        store.save(searcher)
        store.save(candidate)
        store.set_age_assurance("c7-c6", AgeAssuranceStatus.PASSED)
        results = discover(store, searcher)
        assert len(results) == 1
        assert results[0].score == 1.0

    # --- API-level tests ---

    def test_api_score_field_present_in_each_result(self) -> None:
        """Each discovery result JSON object carries a 'score' key (C7)."""
        # Searcher
        client.post(
            "/profiles",
            json={"id": "c7-api-s1", "display_name": "Searcher", "age": 25,
                  "open_to_friends": True, "interests": ["music", "sport"]},
        )
        client.post("/profiles/c7-api-s1/age-assurance", json={"status": "passed"})
        # Candidate
        client.post(
            "/profiles",
            json={"id": "c7-api-c1", "display_name": "Candidate", "age": 26,
                  "open_to_friends": True, "interests": ["music"]},
        )
        client.post("/profiles/c7-api-c1/age-assurance", json={"status": "passed"})
        resp = client.get("/discovery/c7-api-s1?radius_km=25")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1
        for r in results:
            assert "score" in r
            assert isinstance(r["score"], float)

    def test_api_score_value_reflects_shared_interests(self) -> None:
        """The score returned by the API equals the interest-overlap fraction (C7)."""
        client.post(
            "/profiles",
            json={"id": "c7-api-s2", "display_name": "Searcher2", "age": 25,
                  "open_to_friends": True, "interests": ["a", "b", "c"]},
        )
        client.post("/profiles/c7-api-s2/age-assurance", json={"status": "passed"})
        # Candidate shares 1 of 3 → score ≈ 0.333
        client.post(
            "/profiles",
            json={"id": "c7-api-c2", "display_name": "Candidate2", "age": 26,
                  "open_to_friends": True, "interests": ["a", "x", "y"]},
        )
        client.post("/profiles/c7-api-c2/age-assurance", json={"status": "passed"})
        resp = client.get("/discovery/c7-api-s2?radius_km=25")
        assert resp.status_code == 200
        results = {r["profile"]["id"]: r for r in resp.json()}
        assert "c7-api-c2" in results
        expected = 1 / 3
        assert abs(results["c7-api-c2"]["score"] - expected) < 1e-9

    def test_api_results_ordered_by_score_descending(self) -> None:
        """The API returns results with the highest score first (C7)."""
        client.post(
            "/profiles",
            json={"id": "c7-api-s3", "display_name": "Searcher3", "age": 25,
                  "open_to_friends": True, "interests": ["a", "b", "c"]},
        )
        client.post("/profiles/c7-api-s3/age-assurance", json={"status": "passed"})
        # High-match candidate: shares 3/3
        client.post(
            "/profiles",
            json={"id": "c7-api-high", "display_name": "HighMatch", "age": 26,
                  "open_to_friends": True, "interests": ["a", "b", "c"]},
        )
        client.post("/profiles/c7-api-high/age-assurance", json={"status": "passed"})
        # Low-match candidate: shares 0/3
        client.post(
            "/profiles",
            json={"id": "c7-api-low", "display_name": "LowMatch", "age": 27,
                  "open_to_friends": True, "interests": ["x", "y", "z"]},
        )
        client.post("/profiles/c7-api-low/age-assurance", json={"status": "passed"})
        resp = client.get("/discovery/c7-api-s3?radius_km=25")
        assert resp.status_code == 200
        results = resp.json()
        scores = [r["score"] for r in results]
        # Verify non-increasing order
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1]

    def test_api_closed_profile_excluded_score_not_affected(self) -> None:
        """A closed profile is excluded; remaining open results still include scores (C7)."""
        client.post(
            "/profiles",
            json={"id": "c7-api-s4", "display_name": "Searcher4", "age": 25,
                  "open_to_friends": True, "interests": ["hiking"]},
        )
        client.post("/profiles/c7-api-s4/age-assurance", json={"status": "passed"})
        # Open candidate — should appear
        client.post(
            "/profiles",
            json={"id": "c7-api-open", "display_name": "OpenUser", "age": 26,
                  "open_to_friends": True, "interests": ["hiking"]},
        )
        client.post("/profiles/c7-api-open/age-assurance", json={"status": "passed"})
        # Closed candidate — must not appear
        client.post(
            "/profiles",
            json={"id": "c7-api-closed2", "display_name": "ClosedUser", "age": 27,
                  "open_to_friends": False, "interests": ["hiking"]},
        )
        client.post("/profiles/c7-api-closed2/age-assurance", json={"status": "passed"})
        resp = client.get("/discovery/c7-api-s4?radius_km=25")
        assert resp.status_code == 200
        results = resp.json()
        ids = [r["profile"]["id"] for r in results]
        assert "c7-api-open" in ids
        assert "c7-api-closed2" not in ids
        # All returned results have a score
        for r in results:
            assert "score" in r
