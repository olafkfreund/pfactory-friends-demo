"""End-to-end tests for MyFriends Web v2.

These tests simulate the full user flows described in the acceptance criteria,
exercising the API as a client application would (via the FastAPI TestClient,
which drives the full request/response cycle through the same middleware stack
that production traffic would traverse).

AC mapping
----------
AC19 - The web client can perform the whole flow:
         create a profile → toggle availability → see discovery results with scores
         → send a request → accept one → exchange a message → block a person
         → report a person
         Every step uses a different identity to represent two users interacting.

All other ACs are covered by the integration and unit suites; this suite focuses
on the end-to-end composition of those behaviours in the single "happy path"
walkthrough that AC19 mandates.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create(pid: str, age: int = 25, **kwargs: object) -> dict:
    payload = {
        "id": pid,
        "display_name": f"User {pid}",
        "bio": "e2e bio",
        "interests": [],
        "activities": [],
        "age": age,
        "open_to_friends": False,
    }
    payload.update(kwargs)
    resp = client.post("/profiles", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _pass_assurance(pid: str) -> None:
    r = client.post(f"/profiles/{pid}/age-assurance", json={"status": "passed"})
    assert r.status_code == 200, r.text


def _open(pid: str) -> None:
    r = client.patch(f"/profiles/{pid}/availability?open_to_friends=true")
    assert r.status_code == 200, r.text


def _close(pid: str) -> None:
    r = client.patch(f"/profiles/{pid}/availability?open_to_friends=false")
    assert r.status_code == 200, r.text


def _send_request(req: str, rec: str) -> str:
    r = client.post(f"/connections?requester_id={req}&recipient_id={rec}")
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _accept(conn_id: str, acceptor: str) -> None:
    r = client.post(f"/connections/{conn_id}/accept?acceptor_id={acceptor}")
    assert r.status_code == 200, r.text


def _send_message(sender: str, recipient: str, body: str) -> dict:
    r = client.post("/messages", json={"sender_id": sender, "recipient_id": recipient, "body": body})
    assert r.status_code == 201, r.text
    return r.json()


def _block(blocker: str, blocked: str) -> None:
    r = client.post("/blocks", json={"blocker_id": blocker, "blocked_id": blocked})
    assert r.status_code == 204, r.text


def _report(reporter: str, target: str, reason: str = "harassment") -> dict:
    r = client.post(
        "/reports",
        json={
            "reporter_id": reporter,
            "target_id": target,
            "target_kind": "user",
            "reason": reason,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# AC19 — Complete end-to-end user flow
# ---------------------------------------------------------------------------


class TestCompleteUserFlow:
    """AC19: The web client can perform the whole flow against the API."""

    def test_create_profile_step(self) -> None:
        """Step 1: Create a profile."""
        p = _create("e2e-alice", age=25, interests=["hiking", "books"])
        assert p["id"] == "e2e-alice"
        assert p["display_name"] == "User e2e-alice"
        assert "hiking" in p["interests"]

    def test_toggle_availability_step(self) -> None:
        """Step 2: Toggle availability on and off."""
        _create("e2e-av-user", age=25)
        _open("e2e-av-user")
        assert client.get("/profiles/e2e-av-user").json()["open_to_friends"] is True
        _close("e2e-av-user")
        assert client.get("/profiles/e2e-av-user").json()["open_to_friends"] is False

    def test_discovery_with_scores_step(self) -> None:
        """Step 3: See discovery results with their scores."""
        _create("e2e-disc-s", age=25, interests=["a", "b"])
        _pass_assurance("e2e-disc-s")
        _open("e2e-disc-s")
        _create("e2e-disc-c", age=26, interests=["a", "b", "c"])
        _pass_assurance("e2e-disc-c")
        _open("e2e-disc-c")
        resp = client.get("/discovery/e2e-disc-s?radius_km=25")
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1
        r = next(x for x in results if x["profile"]["id"] == "e2e-disc-c")
        assert "score" in r
        assert r["score"] >= 0.0

    def test_send_connection_request_step(self) -> None:
        """Step 4: Send a connection request."""
        _create("e2e-req-a", age=25)
        _create("e2e-req-b", age=25)
        conn_id = _send_request("e2e-req-a", "e2e-req-b")
        assert conn_id is not None

    def test_accept_connection_request_step(self) -> None:
        """Step 5: Accept a connection request."""
        _create("e2e-acc-a", age=25)
        _create("e2e-acc-b", age=25)
        conn_id = _send_request("e2e-acc-a", "e2e-acc-b")
        _accept(conn_id, "e2e-acc-b")
        resp = client.get("/messages/e2e-acc-a/e2e-acc-b")
        assert resp.status_code == 200  # endpoint reachable = connection accepted

    def test_exchange_message_step(self) -> None:
        """Step 6: Exchange messages after connection accepted."""
        _create("e2e-msg-a", age=25)
        _create("e2e-msg-b", age=25)
        conn_id = _send_request("e2e-msg-a", "e2e-msg-b")
        _accept(conn_id, "e2e-msg-b")
        m1 = _send_message("e2e-msg-a", "e2e-msg-b", "Hello!")
        m2 = _send_message("e2e-msg-b", "e2e-msg-a", "Hi back!")
        assert m1["body"] == "Hello!"
        assert m2["body"] == "Hi back!"
        conversation = client.get("/messages/e2e-msg-a/e2e-msg-b").json()
        assert len(conversation) == 2

    def test_block_person_step(self) -> None:
        """Step 7: Block a person."""
        _create("e2e-blk-a", age=25)
        _create("e2e-blk-b", age=25)
        _block("e2e-blk-a", "e2e-blk-b")
        resp = client.get("/blocks/e2e-blk-a/e2e-blk-b")
        assert resp.json()["blocked"] is True

    def test_report_person_step(self) -> None:
        """Step 8: Report a person."""
        _create("e2e-rpt-reporter", age=25)
        _create("e2e-rpt-target", age=25)
        report = _report("e2e-rpt-reporter", "e2e-rpt-target", reason="spam")
        assert report["reporter_id"] == "e2e-rpt-reporter"
        assert report["target_id"] == "e2e-rpt-target"
        assert report["queue_status"] == "accepted"

    def test_full_flow_in_sequence(self) -> None:
        """AC19: All eight steps performed together as one coherent flow."""
        # Step 1: Create profiles
        alice = _create("e2e-full-alice", age=25, interests=["hiking", "books", "travel"])
        bob = _create("e2e-full-bob", age=26, interests=["books", "travel", "coding"])
        carol = _create("e2e-full-carol", age=27, interests=["art"])

        # Step 2: Pass age assurance
        _pass_assurance("e2e-full-alice")
        _pass_assurance("e2e-full-bob")
        _pass_assurance("e2e-full-carol")

        # Step 3: Toggle availability on
        _open("e2e-full-alice")
        _open("e2e-full-bob")
        _open("e2e-full-carol")

        # Step 4: Alice discovers Bob (both adults, both open, both assurance-passed)
        disc_resp = client.get("/discovery/e2e-full-alice?radius_km=25")
        assert disc_resp.status_code == 200
        results = disc_resp.json()
        bob_result = next((r for r in results if r["profile"]["id"] == "e2e-full-bob"), None)
        assert bob_result is not None, "Bob should appear in Alice's discovery"
        assert bob_result["score"] > 0.0  # they share "books" and "travel"
        assert "books" in bob_result["shared_interests"] or "travel" in bob_result["shared_interests"]

        # Step 5: Alice sends a connection request to Bob
        conn_id = _send_request("e2e-full-alice", "e2e-full-bob")

        # Step 6: Bob accepts
        _accept(conn_id, "e2e-full-bob")

        # Step 7: They exchange messages
        msg1 = _send_message("e2e-full-alice", "e2e-full-bob", "Hey Bob, want to be friends?")
        msg2 = _send_message("e2e-full-bob", "e2e-full-alice", "Sure, Alice!")
        assert msg1["body"] == "Hey Bob, want to be friends?"
        assert msg2["body"] == "Sure, Alice!"

        # Step 8: Alice blocks Carol
        _block("e2e-full-alice", "e2e-full-carol")
        carol_resp = client.get("/discovery/e2e-full-alice?radius_km=25")
        carol_ids = [r["profile"]["id"] for r in carol_resp.json()]
        assert "e2e-full-carol" not in carol_ids

        # Step 9: Alice reports Carol
        report = _report("e2e-full-alice", "e2e-full-carol", reason="harassment")
        assert report["queue_status"] == "accepted"
        assert report["reason"] == "harassment"

        # Step 10: Toggle Bob offline — he disappears from Alice's discovery
        _close("e2e-full-bob")
        disc_after = client.get("/discovery/e2e-full-alice?radius_km=25")
        assert not any(r["profile"]["id"] == "e2e-full-bob" for r in disc_after.json())


class TestFullFlowEdgeCases:
    """Additional e2e coverage for AC19's flow transitions and refusals."""

    def test_message_before_connection_refused(self) -> None:
        """Cannot message someone before sending a request."""
        _create("e2e-pre-a", age=25)
        _create("e2e-pre-b", age=25)
        resp = client.post(
            "/messages",
            json={"sender_id": "e2e-pre-a", "recipient_id": "e2e-pre-b", "body": "hi"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "not_connected"

    def test_message_before_acceptance_refused(self) -> None:
        """Cannot message while connection is still pending."""
        _create("e2e-pend-a", age=25)
        _create("e2e-pend-b", age=25)
        _send_request("e2e-pend-a", "e2e-pend-b")
        resp = client.post(
            "/messages",
            json={"sender_id": "e2e-pend-a", "recipient_id": "e2e-pend-b", "body": "hi"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "connection_pending"

    def test_blocked_person_cannot_send_connection_request(self) -> None:
        """After A blocks B, B's request to A returns 'blocked'."""
        _create("e2e-blk2-a", age=25)
        _create("e2e-blk2-b", age=25)
        _block("e2e-blk2-a", "e2e-blk2-b")
        resp = client.post("/connections?requester_id=e2e-blk2-b&recipient_id=e2e-blk2-a")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "blocked"

    def test_discovery_score_with_no_shared_interests(self) -> None:
        """Score is 0 when there are no shared interests, but the result still appears."""
        _create("e2e-sc0-s", age=25, interests=["unique_to_searcher"])
        _pass_assurance("e2e-sc0-s")
        _open("e2e-sc0-s")
        _create("e2e-sc0-c", age=25, interests=["unique_to_candidate"])
        _pass_assurance("e2e-sc0-c")
        _open("e2e-sc0-c")
        results = client.get("/discovery/e2e-sc0-s?radius_km=25").json()
        candidate = next((r for r in results if r["profile"]["id"] == "e2e-sc0-c"), None)
        assert candidate is not None
        assert candidate["score"] == 0.0

    def test_report_enters_accepted_state_and_is_in_queue(self) -> None:
        """Filed report enters queue as 'accepted' and appears in GET /reports/queue."""
        _create("e2e-q-reporter", age=25)
        _create("e2e-q-target", age=25)
        report = _report("e2e-q-reporter", "e2e-q-target", reason="fake_profile")
        assert report["queue_status"] == "accepted"
        queue = client.get("/reports/queue").json()
        assert any(r["id"] == report["id"] for r in queue)

    def test_contact_removal_from_report_resolution_blocks_messages(self) -> None:
        """Resolving a report as contact_removal prevents the reported user from messaging."""
        _create("e2e-cr-bad", age=25)
        _create("e2e-cr-victim", age=25)
        # Establish a connection
        conn_id = _send_request("e2e-cr-bad", "e2e-cr-victim")
        _accept(conn_id, "e2e-cr-victim")
        # File and resolve a report
        report = _report("e2e-cr-victim", "e2e-cr-bad", reason="harassment")
        client.post(f"/reports/{report['id']}/resolve", json={"outcome": "contact_removal"})
        # Now bad user should be blocked from messaging
        resp = client.post(
            "/messages",
            json={"sender_id": "e2e-cr-bad", "recipient_id": "e2e-cr-victim", "body": "still here"},
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "contact_removed"

    def test_deletion_returns_full_audit_trail(self) -> None:
        """DELETE /profiles returns a complete picture of what was removed and retained."""
        _create("e2e-del-u", interests=["a", "b"], activities=["c"])
        _create("e2e-del-v")
        # Connect and exchange messages
        conn_id = _send_request("e2e-del-u", "e2e-del-v")
        _accept(conn_id, "e2e-del-v")
        _send_message("e2e-del-u", "e2e-del-v", "before deletion")
        # Block and report
        _block("e2e-del-u", "e2e-del-v")
        _report("e2e-del-v", "e2e-del-u", reason="spam")
        # Delete
        resp = client.delete("/profiles/e2e-del-u")
        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted_profile_id"] == "e2e-del-u"
        assert body["deleted_interest_tags_count"] == 3   # 2 interests + 1 activity
        assert body["deleted_messages_count"] >= 1
        assert body["retained_blocks_count"] >= 1
        assert body["retained_reports_count"] >= 1
        # Profile no longer accessible
        assert client.get("/profiles/e2e-del-u").status_code == 404
