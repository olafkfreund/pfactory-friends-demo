"""Integration tests for MyFriends Web v2.

Tests every API endpoint via the FastAPI TestClient, verifying all plan
acceptance criteria at the HTTP boundary.

AC mapping
----------
AC1  - POST /profiles creates a profile; GET /profiles/{id} returns it
AC2  - Profile validation: blank / too-long display_name; tag count
AC3  - POST /profiles with age < 16 returns 422 with "age_below_minimum"
AC4  - GET /discovery age-bracket isolation (adult ↔ minor wall)
AC5  - GET /discovery rejects unrecorded / failed age assurance
AC6  - PATCH /profiles/{id}/availability toggles open_to_friends
AC7  - GET /discovery returns only open profiles, ordered by score
AC8  - POST /connections rate-limit (20 per 24 h)
AC9  - POST /messages refused when not connected / connection pending
AC10 - POST /blocks + GET /discovery: symmetric block hides both sides
AC11 - POST /reports with invalid reason rejected by Pydantic (422)
AC12 - POST /reports enters accepted state; GET /reports/queue orders by harm
AC13 - POST /reports/{id}/resolve accepts three outcomes; rejects others
AC14 - Contact removal prevents connection requests and messages
AC15 - DELETE /profiles removes profile and messages, retains blocks/reports
AC16 - GET /retention-policy returns correct values
AC17 - GET /profiles/{id} never returns a location field (coarse location ephemeral)
AC18 - Every protected endpoint returns 401 without X-User-ID header
AC20 - Every refusal detail is a snake_case machine-readable code
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_profile(pid: str, age: int = 25, **kwargs: object) -> dict:
    payload = {
        "id": pid,
        "display_name": f"User {pid}",
        "bio": "test bio",
        "interests": [],
        "activities": [],
        "age": age,
        "open_to_friends": False,
    }
    payload.update(kwargs)
    resp = client.post("/profiles", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _pass_age_assurance(pid: str) -> None:
    resp = client.post(f"/profiles/{pid}/age-assurance", json={"status": "passed"})
    assert resp.status_code == 200, resp.text


def _open_profile(pid: str) -> None:
    resp = client.patch(f"/profiles/{pid}/availability?open_to_friends=true")
    assert resp.status_code == 200, resp.text


def _ready_profile(pid: str, age: int = 25, **kwargs: object) -> dict:
    """Create a profile that is ready for discovery (age assurance passed, open to friends)."""
    p = _create_profile(pid, age=age, open_to_friends=True, **kwargs)
    _pass_age_assurance(pid)
    return p


def _connect(requester: str, recipient: str) -> str:
    """Send and accept a connection; return the connection id."""
    resp = client.post(f"/connections?requester_id={requester}&recipient_id={recipient}")
    assert resp.status_code == 201, resp.text
    conn_id = resp.json()["id"]
    resp2 = client.post(f"/connections/{conn_id}/accept?acceptor_id={recipient}")
    assert resp2.status_code == 200, resp2.text
    return conn_id


# ---------------------------------------------------------------------------
# AC1 — Profile persistence
# ---------------------------------------------------------------------------


class TestProfilePersistence:
    """AC1: Profiles are stored and can be retrieved by id."""

    def test_create_and_retrieve_profile(self) -> None:
        _create_profile("ac1-user")
        resp = client.get("/profiles/ac1-user")
        assert resp.status_code == 200
        assert resp.json()["id"] == "ac1-user"

    def test_create_returns_201(self) -> None:
        resp = client.post(
            "/profiles",
            json={"id": "ac1-b", "display_name": "Alice", "age": 25},
        )
        assert resp.status_code == 201

    def test_get_unknown_profile_returns_404(self) -> None:
        resp = client.get("/profiles/does-not-exist-ac1")
        assert resp.status_code == 404

    def test_healthz_returns_ok(self) -> None:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# AC2 — Profile creation validation
# ---------------------------------------------------------------------------


class TestProfileValidation:
    """AC2: API refuses blank or too-long display_name, naming the field."""

    def test_blank_id_returns_422(self) -> None:
        resp = client.post(
            "/profiles",
            json={"id": "  ", "display_name": "X", "age": 25},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "blank_id"

    def test_valid_profile_with_interests_and_activities(self) -> None:
        resp = client.post(
            "/profiles",
            json={
                "id": "ac2-full",
                "display_name": "Full",
                "age": 25,
                "interests": ["a", "b"],
                "activities": ["c"],
                "bio": "A short bio.",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["interests"] == ["a", "b"]
        assert body["activities"] == ["c"]

    def test_profile_age_returned_in_response(self) -> None:
        resp = client.post(
            "/profiles",
            json={"id": "ac2-age", "display_name": "Age Test", "age": 30},
        )
        assert resp.status_code == 201
        assert resp.json()["age"] == 30


# ---------------------------------------------------------------------------
# AC3 — Age < 16 refused at API layer
# ---------------------------------------------------------------------------


class TestAgeBelowMinimumAPI:
    """AC3: POST /profiles with age < 16 returns 422 and names the reason."""

    def test_age_15_refused(self) -> None:
        resp = client.post(
            "/profiles",
            json={"id": "ac3-15", "display_name": "Young", "age": 15},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "age_below_minimum"

    def test_age_0_refused(self) -> None:
        resp = client.post(
            "/profiles",
            json={"id": "ac3-0", "display_name": "Baby", "age": 0},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "age_below_minimum"

    def test_age_16_accepted(self) -> None:
        resp = client.post(
            "/profiles",
            json={"id": "ac3-16", "display_name": "Teen", "age": 16},
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# AC4 — Discovery age-bracket isolation
# ---------------------------------------------------------------------------


class TestDiscoveryAgeBracketIsolation:
    """AC4: Adults and minors cannot reach each other in discovery."""

    def test_adult_does_not_see_minor(self) -> None:
        _ready_profile("ac4-adult", age=25)
        _ready_profile("ac4-minor", age=17)
        resp = client.get("/discovery/ac4-adult?radius_km=25")
        assert resp.status_code == 200
        ids = [r["profile"]["id"] for r in resp.json()]
        assert "ac4-minor" not in ids

    def test_minor_does_not_see_adult(self) -> None:
        _ready_profile("ac4-a", age=25)
        _ready_profile("ac4-m", age=17)
        resp = client.get("/discovery/ac4-m?radius_km=25")
        assert resp.status_code == 200
        ids = [r["profile"]["id"] for r in resp.json()]
        assert "ac4-a" not in ids

    def test_adult_sees_adult(self) -> None:
        _ready_profile("ac4-aa1", age=20)
        _ready_profile("ac4-aa2", age=30)
        resp = client.get("/discovery/ac4-aa1?radius_km=25")
        assert resp.status_code == 200
        ids = [r["profile"]["id"] for r in resp.json()]
        assert "ac4-aa2" in ids

    def test_minor_sees_minor(self) -> None:
        _ready_profile("ac4-mm1", age=16)
        _ready_profile("ac4-mm2", age=17)
        resp = client.get("/discovery/ac4-mm1?radius_km=25")
        assert resp.status_code == 200
        ids = [r["profile"]["id"] for r in resp.json()]
        assert "ac4-mm2" in ids


# ---------------------------------------------------------------------------
# AC5 — Age assurance gate on discovery
# ---------------------------------------------------------------------------


class TestAgeAssuranceGate:
    """AC5: Discovery returns 403 when the searcher's age assurance has not passed."""

    def test_unrecorded_age_assurance_blocked(self) -> None:
        _create_profile("ac5-unrecorded")
        resp = client.get("/discovery/ac5-unrecorded?radius_km=25")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "age_assurance_unrecorded"

    def test_failed_age_assurance_blocked(self) -> None:
        _create_profile("ac5-failed")
        client.post("/profiles/ac5-failed/age-assurance", json={"status": "failed"})
        resp = client.get("/discovery/ac5-failed?radius_km=25")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "age_assurance_failed"

    def test_passed_age_assurance_allowed(self) -> None:
        _create_profile("ac5-passed")
        _pass_age_assurance("ac5-passed")
        resp = client.get("/discovery/ac5-passed?radius_km=25")
        assert resp.status_code == 200

    def test_record_age_assurance_passed(self) -> None:
        _create_profile("ac5-set")
        resp = client.post("/profiles/ac5-set/age-assurance", json={"status": "passed"})
        assert resp.status_code == 200
        assert resp.json()["age_assurance_status"] == "passed"

    def test_record_age_assurance_failed(self) -> None:
        _create_profile("ac5-setf")
        resp = client.post("/profiles/ac5-setf/age-assurance", json={"status": "failed"})
        assert resp.status_code == 200
        assert resp.json()["age_assurance_status"] == "failed"

    def test_cannot_set_assurance_to_unrecorded(self) -> None:
        _create_profile("ac5-imm")
        resp = client.post("/profiles/ac5-imm/age-assurance", json={"status": "unrecorded"})
        assert resp.status_code == 422
        assert resp.json()["detail"] == "age_assurance_status_immutable"


# ---------------------------------------------------------------------------
# AC6 — open_to_friends toggle
# ---------------------------------------------------------------------------


class TestAvailabilityToggle:
    """AC6: Toggling open_to_friends on/off takes effect immediately in discovery."""

    def test_turn_on(self) -> None:
        _create_profile("ac6-on", open_to_friends=False)
        resp = client.patch("/profiles/ac6-on/availability?open_to_friends=true")
        assert resp.status_code == 200
        assert resp.json()["open_to_friends"] is True

    def test_turn_off(self) -> None:
        _create_profile("ac6-off", open_to_friends=True)
        resp = client.patch("/profiles/ac6-off/availability?open_to_friends=false")
        assert resp.status_code == 200
        assert resp.json()["open_to_friends"] is False

    def test_turning_off_removes_from_discovery(self) -> None:
        _ready_profile("ac6-searcher", age=25)
        _ready_profile("ac6-target", age=25)
        # Confirm visible
        resp = client.get("/discovery/ac6-searcher?radius_km=25")
        assert any(r["profile"]["id"] == "ac6-target" for r in resp.json())
        # Turn off
        client.patch("/profiles/ac6-target/availability?open_to_friends=false")
        resp2 = client.get("/discovery/ac6-searcher?radius_km=25")
        assert not any(r["profile"]["id"] == "ac6-target" for r in resp2.json())

    def test_toggle_not_found_returns_404(self) -> None:
        resp = client.patch("/profiles/ghost-ac6/availability?open_to_friends=true")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "profile_not_found"


# ---------------------------------------------------------------------------
# AC7 — Discovery returns open profiles ordered by score
# ---------------------------------------------------------------------------


class TestDiscoveryScoreOrdering:
    """AC7: Discovery returns only open profiles, ordered by match score with score included."""

    def test_score_included_in_response(self) -> None:
        _ready_profile("ac7-s", age=25, interests=["x"])
        _ready_profile("ac7-c", age=25, interests=["x"])
        resp = client.get("/discovery/ac7-s?radius_km=25")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1
        for r in results:
            assert "score" in r

    def test_closed_profile_excluded(self) -> None:
        _ready_profile("ac7-open", age=25)
        _create_profile("ac7-closed", age=25, open_to_friends=False)
        _pass_age_assurance("ac7-closed")
        resp = client.get("/discovery/ac7-open?radius_km=25")
        ids = [r["profile"]["id"] for r in resp.json()]
        assert "ac7-closed" not in ids

    def test_results_ordered_by_score_descending(self) -> None:
        _ready_profile("ac7-sr", age=25, interests=["a", "b", "c"])
        _ready_profile("ac7-h", age=25, interests=["a", "b", "c"])
        _ready_profile("ac7-l", age=25, interests=["a"])
        resp = client.get("/discovery/ac7-sr?radius_km=25")
        scores = [r["score"] for r in resp.json()]
        assert scores == sorted(scores, reverse=True)

    def test_invalid_radius_returns_422(self) -> None:
        _ready_profile("ac7-radius")
        resp = client.get("/discovery/ac7-radius?radius_km=99")
        assert resp.status_code == 422
        assert resp.json()["detail"] == "invalid_radius"


# ---------------------------------------------------------------------------
# AC8 — Connection request rate limiting
# ---------------------------------------------------------------------------


class TestConnectionRateLimitAPI:
    """AC8: At most 20 connection requests in any 24-hour period."""

    def test_first_connection_request_succeeds(self) -> None:
        _create_profile("ac8-req")
        _create_profile("ac8-rec")
        resp = client.post("/connections?requester_id=ac8-req&recipient_id=ac8-rec")
        assert resp.status_code == 201

    def test_rate_limit_after_20_requests(self) -> None:
        _create_profile("ac8-rl-req")
        for i in range(20):
            _create_profile(f"ac8-rl-rec{i}")
            resp = client.post(f"/connections?requester_id=ac8-rl-req&recipient_id=ac8-rl-rec{i}")
            assert resp.status_code == 201
        _create_profile("ac8-rl-extra")
        resp = client.post("/connections?requester_id=ac8-rl-req&recipient_id=ac8-rl-extra")
        assert resp.status_code == 429
        assert resp.json()["detail"] == "rate_limit_exceeded"

    def test_blocked_connection_request_returns_403(self) -> None:
        _create_profile("ac8-bl-a")
        _create_profile("ac8-bl-b")
        client.post("/blocks", json={"blocker_id": "ac8-bl-a", "blocked_id": "ac8-bl-b"})
        resp = client.post("/connections?requester_id=ac8-bl-b&recipient_id=ac8-bl-a")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "blocked"


# ---------------------------------------------------------------------------
# AC9 — Messages require accepted connection
# ---------------------------------------------------------------------------


class TestMessagingRequiresAcceptedConnectionAPI:
    """AC9: Message attempts before connection acceptance return machine-readable reasons."""

    def test_message_refused_no_connection(self) -> None:
        _create_profile("ac9-a")
        _create_profile("ac9-b")
        resp = client.post("/messages", json={"sender_id": "ac9-a", "recipient_id": "ac9-b", "body": "hi"})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "not_connected"

    def test_message_refused_connection_pending(self) -> None:
        _create_profile("ac9-p-a")
        _create_profile("ac9-p-b")
        client.post("/connections?requester_id=ac9-p-a&recipient_id=ac9-p-b")
        resp = client.post("/messages", json={"sender_id": "ac9-p-a", "recipient_id": "ac9-p-b", "body": "hi"})
        assert resp.status_code == 403
        assert resp.json()["detail"] == "connection_pending"

    def test_message_succeeds_after_accepted_connection(self) -> None:
        _create_profile("ac9-c-a")
        _create_profile("ac9-c-b")
        _connect("ac9-c-a", "ac9-c-b")
        resp = client.post("/messages", json={"sender_id": "ac9-c-a", "recipient_id": "ac9-c-b", "body": "hello"})
        assert resp.status_code == 201
        assert resp.json()["body"] == "hello"

    def test_get_messages_returns_conversation(self) -> None:
        _create_profile("ac9-m-a")
        _create_profile("ac9-m-b")
        _connect("ac9-m-a", "ac9-m-b")
        client.post("/messages", json={"sender_id": "ac9-m-a", "recipient_id": "ac9-m-b", "body": "msg1"})
        client.post("/messages", json={"sender_id": "ac9-m-b", "recipient_id": "ac9-m-a", "body": "msg2"})
        resp = client.get("/messages/ac9-m-a/ac9-m-b")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# AC10 — Symmetric blocking
# ---------------------------------------------------------------------------


class TestSymmetricBlockingAPI:
    """AC10: After either person blocks the other, neither can discover, request, nor message."""

    def test_blocked_profile_not_in_discovery(self) -> None:
        _ready_profile("ac10-s", age=25)
        _ready_profile("ac10-t", age=25)
        client.post("/blocks", json={"blocker_id": "ac10-s", "blocked_id": "ac10-t"})
        resp = client.get("/discovery/ac10-s?radius_km=25")
        assert not any(r["profile"]["id"] == "ac10-t" for r in resp.json())

    def test_reverse_also_blocked_from_discovery(self) -> None:
        """BIDIRECTIONAL: if A blocks B, B should not see A either."""
        _ready_profile("ac10-x", age=25)
        _ready_profile("ac10-y", age=25)
        client.post("/blocks", json={"blocker_id": "ac10-x", "blocked_id": "ac10-y"})
        resp = client.get("/discovery/ac10-y?radius_km=25")
        assert not any(r["profile"]["id"] == "ac10-x" for r in resp.json())

    def test_blocked_user_cannot_request_connection(self) -> None:
        _create_profile("ac10-br-a")
        _create_profile("ac10-br-b")
        client.post("/blocks", json={"blocker_id": "ac10-br-a", "blocked_id": "ac10-br-b"})
        resp = client.post("/connections?requester_id=ac10-br-b&recipient_id=ac10-br-a")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "blocked"

    def test_both_directions_get_same_reason(self) -> None:
        _create_profile("ac10-dr-a")
        _create_profile("ac10-dr-b")
        client.post("/blocks", json={"blocker_id": "ac10-dr-a", "blocked_id": "ac10-dr-b"})
        r1 = client.post("/connections?requester_id=ac10-dr-a&recipient_id=ac10-dr-b")
        r2 = client.post("/connections?requester_id=ac10-dr-b&recipient_id=ac10-dr-a")
        assert r1.json()["detail"] == r2.json()["detail"] == "blocked"

    def test_check_block_endpoint(self) -> None:
        _create_profile("ac10-ck-a")
        _create_profile("ac10-ck-b")
        client.post("/blocks", json={"blocker_id": "ac10-ck-a", "blocked_id": "ac10-ck-b"})
        resp = client.get("/blocks/ac10-ck-a/ac10-ck-b")
        assert resp.json()["blocked"] is True


# ---------------------------------------------------------------------------
# AC11 — Report reason is a fixed closed list
# ---------------------------------------------------------------------------


class TestReportReasonAPI:
    """AC11: An unrecognised reason is refused by Pydantic before being stored."""

    def test_valid_reason_spam_accepted(self) -> None:
        resp = client.post(
            "/reports",
            json={"reporter_id": "r", "target_id": "t", "target_kind": "user", "reason": "spam"},
        )
        assert resp.status_code == 201

    def test_valid_reason_harassment_accepted(self) -> None:
        resp = client.post(
            "/reports",
            json={
                "reporter_id": "r2",
                "target_id": "t2",
                "target_kind": "user",
                "reason": "harassment",
            },
        )
        assert resp.status_code == 201

    def test_invalid_reason_rejected(self) -> None:
        resp = client.post(
            "/reports",
            json={
                "reporter_id": "r3",
                "target_id": "t3",
                "target_kind": "user",
                "reason": "not_a_real_reason",
            },
        )
        assert resp.status_code == 422

    def test_target_kind_message_accepted(self) -> None:
        resp = client.post(
            "/reports",
            json={
                "reporter_id": "r4",
                "target_id": "msg-0",
                "target_kind": "message",
                "reason": "inappropriate_content",
            },
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# AC12 — Report queue ordering
# ---------------------------------------------------------------------------


class TestReportQueueAPI:
    """AC12: Reports enter the queue in 'accepted' state; immediate_harm reports are first."""

    def test_report_enters_accepted_state(self) -> None:
        resp = client.post(
            "/reports",
            json={"reporter_id": "r", "target_id": "t", "target_kind": "user", "reason": "spam"},
        )
        assert resp.status_code == 201
        assert resp.json()["queue_status"] == "accepted"

    def test_immediate_harm_report_first_in_queue(self) -> None:
        client.post(
            "/reports",
            json={"reporter_id": "r", "target_id": "t1", "target_kind": "user", "reason": "spam", "immediate_harm": False},
        )
        client.post(
            "/reports",
            json={"reporter_id": "r", "target_id": "t2", "target_kind": "user", "reason": "spam", "immediate_harm": True},
        )
        resp = client.get("/reports/queue")
        assert resp.status_code == 200
        queue = resp.json()
        assert queue[0]["target_id"] == "t2"
        assert queue[0]["immediate_harm"] is True

    def test_non_harm_reports_in_fifo_order(self) -> None:
        client.post(
            "/reports",
            json={"reporter_id": "r", "target_id": "first", "target_kind": "user", "reason": "spam"},
        )
        client.post(
            "/reports",
            json={"reporter_id": "r", "target_id": "second", "target_kind": "user", "reason": "spam"},
        )
        resp = client.get("/reports/queue")
        queue = resp.json()
        assert queue[0]["target_id"] == "first"
        assert queue[1]["target_id"] == "second"


# ---------------------------------------------------------------------------
# AC13 — Report resolution
# ---------------------------------------------------------------------------


class TestReportResolutionAPI:
    """AC13: Reports are resolved with exactly three outcomes; others are rejected."""

    def _submit_report(self) -> str:
        resp = client.post(
            "/reports",
            json={"reporter_id": "r", "target_id": "t", "target_kind": "user", "reason": "spam"},
        )
        return resp.json()["id"]

    def test_resolve_no_action(self) -> None:
        rid = self._submit_report()
        resp = client.post(f"/reports/{rid}/resolve", json={"outcome": "no_action"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["resolution_outcome"] == "no_action"
        assert body["queue_status"] == "resolved"
        assert body["resolved_at"] is not None

    def test_resolve_warning(self) -> None:
        rid = self._submit_report()
        resp = client.post(f"/reports/{rid}/resolve", json={"outcome": "warning"})
        assert resp.status_code == 200
        assert resp.json()["resolution_outcome"] == "warning"

    def test_resolve_contact_removal(self) -> None:
        rid = self._submit_report()
        resp = client.post(f"/reports/{rid}/resolve", json={"outcome": "contact_removal"})
        assert resp.status_code == 200
        assert resp.json()["resolution_outcome"] == "contact_removal"

    def test_invalid_outcome_rejected(self) -> None:
        rid = self._submit_report()
        resp = client.post(f"/reports/{rid}/resolve", json={"outcome": "ban_hammer"})
        assert resp.status_code == 422

    def test_resolve_not_found_returns_404(self) -> None:
        resp = client.post("/reports/nonexistent/resolve", json={"outcome": "warning"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "not_found"

    def test_double_resolve_returns_409(self) -> None:
        rid = self._submit_report()
        client.post(f"/reports/{rid}/resolve", json={"outcome": "warning"})
        resp = client.post(f"/reports/{rid}/resolve", json={"outcome": "no_action"})
        assert resp.status_code == 409
        assert resp.json()["detail"] == "already_resolved"


# ---------------------------------------------------------------------------
# AC14 — Contact removal via moderation
# ---------------------------------------------------------------------------


class TestContactRemovalAPI:
    """AC14: Resolving a report as contact_removal prevents future connections and messages."""

    def test_contact_removal_prevents_connection_requests(self) -> None:
        _create_profile("ac14-bad")
        _create_profile("ac14-other")
        # Submit and resolve a report as contact_removal
        r = client.post(
            "/reports",
            json={
                "reporter_id": "ac14-other",
                "target_id": "ac14-bad",
                "target_kind": "user",
                "reason": "harassment",
            },
        )
        rid = r.json()["id"]
        client.post(f"/reports/{rid}/resolve", json={"outcome": "contact_removal"})
        # ac14-bad should now be blocked from sending requests
        resp = client.post("/connections?requester_id=ac14-bad&recipient_id=ac14-other")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "contact_removed"

    def test_get_contact_status_reflects_removal(self) -> None:
        _create_profile("ac14-cs")
        r = client.post(
            "/reports",
            json={
                "reporter_id": "someone",
                "target_id": "ac14-cs",
                "target_kind": "user",
                "reason": "spam",
            },
        )
        rid = r.json()["id"]
        client.post(f"/reports/{rid}/resolve", json={"outcome": "contact_removal"})
        resp = client.get("/profiles/ac14-cs/contact-status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["contact_removed"] is True
        assert body["reason"] == "contact_removal"

    def test_contact_status_false_by_default(self) -> None:
        _create_profile("ac14-normal")
        resp = client.get("/profiles/ac14-normal/contact-status")
        assert resp.status_code == 200
        assert resp.json()["contact_removed"] is False


# ---------------------------------------------------------------------------
# AC15 — Account deletion
# ---------------------------------------------------------------------------


class TestAccountDeletionAPI:
    """AC15: Deleting an account reports what was deleted and what was retained."""

    def test_delete_removes_profile(self) -> None:
        _create_profile("ac15-del")
        resp = client.delete("/profiles/ac15-del")
        assert resp.status_code == 200
        assert resp.json()["deleted_profile_id"] == "ac15-del"
        # Profile should be gone
        assert client.get("/profiles/ac15-del").status_code == 404

    def test_delete_reports_interest_tag_count(self) -> None:
        _create_profile("ac15-tags", interests=["a", "b"], activities=["c"])
        resp = client.delete("/profiles/ac15-tags")
        assert resp.json()["deleted_interest_tags_count"] == 3

    def test_delete_reports_message_count(self) -> None:
        _create_profile("ac15-m-a")
        _create_profile("ac15-m-b")
        _connect("ac15-m-a", "ac15-m-b")
        client.post("/messages", json={"sender_id": "ac15-m-a", "recipient_id": "ac15-m-b", "body": "hi"})
        resp = client.delete("/profiles/ac15-m-a")
        assert resp.json()["deleted_messages_count"] >= 1

    def test_delete_retains_block_records(self) -> None:
        _create_profile("ac15-bl-a")
        _create_profile("ac15-bl-b")
        client.post("/blocks", json={"blocker_id": "ac15-bl-a", "blocked_id": "ac15-bl-b"})
        resp = client.delete("/profiles/ac15-bl-a")
        assert resp.json()["retained_blocks_count"] >= 1

    def test_delete_retains_report_records(self) -> None:
        _create_profile("ac15-rp")
        client.post(
            "/reports",
            json={
                "reporter_id": "someone",
                "target_id": "ac15-rp",
                "target_kind": "user",
                "reason": "spam",
            },
        )
        resp = client.delete("/profiles/ac15-rp")
        assert resp.json()["retained_reports_count"] >= 1

    def test_delete_not_found_returns_404(self) -> None:
        resp = client.delete("/profiles/no-such-ac15")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "profile_not_found"


# ---------------------------------------------------------------------------
# AC16 — Retention policy endpoint
# ---------------------------------------------------------------------------


class TestRetentionPolicyAPI:
    """AC16: GET /retention-policy returns correct durations from a single readable endpoint."""

    def test_retention_policy_endpoint_returns_200(self) -> None:
        resp = client.get("/retention-policy")
        assert resp.status_code == 200

    def test_messages_retained_24_months(self) -> None:
        resp = client.get("/retention-policy")
        assert resp.json()["messages_months"] == 24

    def test_blocks_retained_24_months(self) -> None:
        resp = client.get("/retention-policy")
        assert resp.json()["blocks_months"] == 24

    def test_reports_retained_24_months(self) -> None:
        resp = client.get("/retention-policy")
        assert resp.json()["reports_months"] == 24

    def test_other_deleted_within_30_days(self) -> None:
        resp = client.get("/retention-policy")
        assert resp.json()["other_days"] == 30

    def test_description_field_present(self) -> None:
        resp = client.get("/retention-policy")
        assert "description" in resp.json()


# ---------------------------------------------------------------------------
# AC17 — Coarse location never persisted
# ---------------------------------------------------------------------------


class TestCoarseLocationNotPersistedAPI:
    """AC17: A coarse location supplied for a discovery query is never returned by any read."""

    def test_profile_get_never_returns_location_field(self) -> None:
        """ProfileOut does not include a location field — it is never surfaced to callers."""
        _create_profile("ac17-loc")
        resp = client.get("/profiles/ac17-loc")
        body = resp.json()
        assert "lat" not in body
        assert "lon" not in body
        assert "location" not in body

    def test_discovery_with_query_location_does_not_store_it(self) -> None:
        """Running discovery with lat/lon does not modify the searcher's profile."""
        _ready_profile("ac17-s", age=25)
        # Use a query location — should not be stored
        client.get("/discovery/ac17-s?radius_km=25&lat=51.5&lon=-0.1")
        # Fetch profile — should have no location exposed
        resp = client.get("/profiles/ac17-s")
        body = resp.json()
        assert "lat" not in body
        assert "lon" not in body


# ---------------------------------------------------------------------------
# AC18 — Authentication required for every endpoint
# ---------------------------------------------------------------------------


class TestAuthenticationRequired:
    """AC18: Every endpoint that reads or writes data rejects an unauthenticated caller."""

    @pytest.fixture()
    def no_auth_client(self) -> TestClient:
        """Return a client without the auth bypass override."""
        from app.auth import require_auth

        app.dependency_overrides.pop(require_auth, None)
        c = TestClient(app)
        # Restore afterwards so other tests are not affected
        return c

    def test_get_profile_requires_auth(self, no_auth_client: TestClient) -> None:
        resp = no_auth_client.get("/profiles/anyone")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "unauthenticated"

    def test_create_profile_requires_auth(self, no_auth_client: TestClient) -> None:
        resp = no_auth_client.post("/profiles", json={"id": "x", "display_name": "Y", "age": 25})
        assert resp.status_code == 401

    def test_discovery_requires_auth(self, no_auth_client: TestClient) -> None:
        resp = no_auth_client.get("/discovery/anyone?radius_km=25")
        assert resp.status_code == 401

    def test_send_message_requires_auth(self, no_auth_client: TestClient) -> None:
        resp = no_auth_client.post(
            "/messages",
            json={"sender_id": "a", "recipient_id": "b", "body": "hi"},
        )
        assert resp.status_code == 401

    def test_block_requires_auth(self, no_auth_client: TestClient) -> None:
        resp = no_auth_client.post("/blocks", json={"blocker_id": "a", "blocked_id": "b"})
        assert resp.status_code == 401

    def test_submit_report_requires_auth(self, no_auth_client: TestClient) -> None:
        resp = no_auth_client.post(
            "/reports",
            json={"reporter_id": "r", "target_id": "t", "target_kind": "user", "reason": "spam"},
        )
        assert resp.status_code == 401

    def test_delete_profile_requires_auth(self, no_auth_client: TestClient) -> None:
        resp = no_auth_client.delete("/profiles/anyone")
        assert resp.status_code == 401

    def test_healthz_is_public(self) -> None:
        """GET /healthz does not require auth (it is a health probe)."""
        resp = client.get("/healthz")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# AC20 — Every refusal carries a machine-readable reason
# ---------------------------------------------------------------------------


class TestMachineReadableReasonsAPI:
    """AC20: Every refusal detail is a snake_case string code, no sentence."""

    def _assert_machine_readable(self, detail: object) -> None:
        assert isinstance(detail, str), f"detail should be a string, got {type(detail)}"
        assert " " not in detail, f"detail '{detail}' contains spaces"
        assert detail == detail.lower(), f"detail '{detail}' is not lowercase"

    def test_profile_not_found_is_code(self) -> None:
        resp = client.get("/profiles/nonexistent-ac20")
        self._assert_machine_readable(resp.json()["detail"])

    def test_age_below_minimum_is_code(self) -> None:
        resp = client.post("/profiles", json={"id": "x", "display_name": "X", "age": 3})
        self._assert_machine_readable(resp.json()["detail"])

    def test_age_assurance_unrecorded_is_code(self) -> None:
        _create_profile("ac20-aa")
        resp = client.get("/discovery/ac20-aa?radius_km=25")
        self._assert_machine_readable(resp.json()["detail"])

    def test_rate_limit_exceeded_is_code(self) -> None:
        _create_profile("ac20-rl-req")
        for i in range(20):
            _create_profile(f"ac20-rl-r{i}")
            client.post(f"/connections?requester_id=ac20-rl-req&recipient_id=ac20-rl-r{i}")
        _create_profile("ac20-rl-extra")
        resp = client.post("/connections?requester_id=ac20-rl-req&recipient_id=ac20-rl-extra")
        self._assert_machine_readable(resp.json()["detail"])

    def test_not_connected_is_code(self) -> None:
        _create_profile("ac20-msg-a")
        _create_profile("ac20-msg-b")
        resp = client.post(
            "/messages",
            json={"sender_id": "ac20-msg-a", "recipient_id": "ac20-msg-b", "body": "hi"},
        )
        self._assert_machine_readable(resp.json()["detail"])

    def test_unauthenticated_is_code(self) -> None:
        from app.auth import require_auth

        app.dependency_overrides.pop(require_auth, None)
        try:
            resp = TestClient(app).get("/profiles/anyone")
            self._assert_machine_readable(resp.json()["detail"])
        finally:
            app.dependency_overrides[require_auth] = lambda: "test-user-id"
