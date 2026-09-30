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

from fastapi.testclient import TestClient

from app.domain import GeoLocation, Profile, ReportReason, ReportTargetKind
from app.main import app
from app.store import (
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
            "/profiles",
            json={"id": "minor-disc", "display_name": "Minor", "age": 17, "open_to_friends": True},
        )
        resp = client.get("/discovery/adult-disc?radius_km=25")
        assert resp.status_code == 200
        ids = [r["profile"]["id"] for r in resp.json()]
        assert "minor-disc" not in ids
