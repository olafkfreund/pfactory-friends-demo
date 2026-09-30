import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthz() -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_profile_me_returns_placeholder() -> None:
    resp = client.get("/profiles/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "placeholder"
    assert "display_name" in body


# ---------------------------------------------------------------------------
# Helpers — reused across tests
# ---------------------------------------------------------------------------

def _make_profile(client: TestClient, profile_id: str, **overrides: object) -> dict:
    """Create a profile and return the response body."""
    payload = {
        "id": profile_id,
        "display_name": "Test User",
        "bio": "hello",
        "interests": [],
        "activities": [],
        "age": 25,
        "open_to_friends": False,
    }
    payload.update(overrides)
    resp = client.post("/profiles", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _pass_age_assurance(client: TestClient, profile_id: str) -> None:
    resp = client.post(
        f"/profiles/{profile_id}/age-assurance",
        json={"status": "passed"},
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# C6 — "open to new friends" toggle
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the in-memory stores for each test so state doesn't bleed across."""
    from app import main
    from app.store import ConnectionStore, MessageStore, ProfileStore, ReportStore

    new_profiles = ProfileStore()
    new_connections = ConnectionStore(new_profiles)
    new_messages = MessageStore(new_profiles, new_connections)
    new_reports = ReportStore()
    monkeypatch.setattr(main, "_profiles", new_profiles)
    monkeypatch.setattr(main, "_connections", new_connections)
    monkeypatch.setattr(main, "_messages", new_messages)
    monkeypatch.setattr(main, "_reports", new_reports)


def test_toggle_availability_turn_on() -> None:
    """PATCH /availability?open_to_friends=true sets the flag."""
    _make_profile(client, "user-toggle-on", open_to_friends=False)
    resp = client.patch("/profiles/user-toggle-on/availability?open_to_friends=true")
    assert resp.status_code == 200
    assert resp.json()["open_to_friends"] is True


def test_toggle_availability_turn_off() -> None:
    """PATCH /availability?open_to_friends=false clears the flag."""
    _make_profile(client, "user-toggle-off", open_to_friends=True)
    resp = client.patch("/profiles/user-toggle-off/availability?open_to_friends=false")
    assert resp.status_code == 200
    assert resp.json()["open_to_friends"] is False


def test_toggle_availability_not_found() -> None:
    """PATCH /availability on an unknown profile returns 404."""
    resp = client.patch("/profiles/nonexistent/availability?open_to_friends=true")
    assert resp.status_code == 404


def test_toggle_availability_preserves_age_assurance_status() -> None:
    """Toggling availability must not reset age_assurance_status (C6 / AC#5)."""
    _make_profile(client, "user-aa-preserve")
    _pass_age_assurance(client, "user-aa-preserve")

    # Confirm age assurance is PASSED
    profile_resp = client.get("/profiles/user-aa-preserve")
    assert profile_resp.json()["age_assurance_status"] == "passed"

    # Toggle availability; age_assurance_status must remain 'passed'
    resp = client.patch("/profiles/user-aa-preserve/availability?open_to_friends=true")
    assert resp.status_code == 200
    assert resp.json()["age_assurance_status"] == "passed"


def test_turning_off_removes_from_discovery() -> None:
    """Turning open_to_friends off removes the person from discovery on the next query (AC#6)."""
    # Create searcher and candidate, both adults with passed age assurance
    _make_profile(client, "searcher-c6", age=25, interests=["music"])
    _pass_age_assurance(client, "searcher-c6")

    _make_profile(client, "candidate-c6", age=28, open_to_friends=True, interests=["music"])
    _pass_age_assurance(client, "candidate-c6")

    # Candidate is discoverable while open_to_friends=True
    resp = client.get("/discovery/searcher-c6?radius_km=25")
    assert resp.status_code == 200
    ids = [r["profile"]["id"] for r in resp.json()]
    assert "candidate-c6" in ids

    # Turn off — candidate is no longer discoverable on the next query
    client.patch("/profiles/candidate-c6/availability?open_to_friends=false")

    resp2 = client.get("/discovery/searcher-c6?radius_km=25")
    assert resp2.status_code == 200
    ids2 = [r["profile"]["id"] for r in resp2.json()]
    assert "candidate-c6" not in ids2


def test_turning_on_adds_to_discovery() -> None:
    """Turning open_to_friends on makes the person discoverable on the next query."""
    _make_profile(client, "searcher-c6b", age=25)
    _pass_age_assurance(client, "searcher-c6b")

    _make_profile(client, "candidate-c6b", age=28, open_to_friends=False)
    _pass_age_assurance(client, "candidate-c6b")

    # Not discoverable while off
    resp = client.get("/discovery/searcher-c6b?radius_km=25")
    assert resp.status_code == 200
    ids = [r["profile"]["id"] for r in resp.json()]
    assert "candidate-c6b" not in ids

    # Turn on — now discoverable
    client.patch("/profiles/candidate-c6b/availability?open_to_friends=true")

    resp2 = client.get("/discovery/searcher-c6b?radius_km=25")
    assert resp2.status_code == 200
    ids2 = [r["profile"]["id"] for r in resp2.json()]
    assert "candidate-c6b" in ids2


# ---------------------------------------------------------------------------
# C8 — Connection requests with rolling 24-hour rate limit
# ---------------------------------------------------------------------------


def test_c8_send_connection_request_success() -> None:
    """POST /connections creates a pending connection (C8)."""
    _make_profile(client, "c8-req", age=25)
    _make_profile(client, "c8-rec", age=26)
    resp = client.post("/connections?requester_id=c8-req&recipient_id=c8-rec")
    assert resp.status_code == 201
    body = resp.json()
    assert body["requester_id"] == "c8-req"
    assert body["recipient_id"] == "c8-rec"
    assert body["status"] == "pending"


def test_c8_self_request_refused() -> None:
    """Cannot send a connection request to yourself (C8)."""
    _make_profile(client, "c8-self", age=25)
    resp = client.post("/connections?requester_id=c8-self&recipient_id=c8-self")
    assert resp.status_code == 422
    assert "self_request" in resp.json()["detail"]


def test_c8_duplicate_request_refused() -> None:
    """A duplicate connection request for the same pair is refused (C8)."""
    _make_profile(client, "c8-dup-req", age=25)
    _make_profile(client, "c8-dup-rec", age=26)
    client.post("/connections?requester_id=c8-dup-req&recipient_id=c8-dup-rec")
    resp = client.post("/connections?requester_id=c8-dup-req&recipient_id=c8-dup-rec")
    assert resp.status_code == 422
    assert "already_exists" in resp.json()["detail"]


def test_c8_blocked_pair_request_refused() -> None:
    """A person cannot send a connection request to someone they blocked (C8)."""
    _make_profile(client, "c8-blk-a", age=25)
    _make_profile(client, "c8-blk-b", age=26)
    client.post("/blocks", json={"blocker_id": "c8-blk-a", "blocked_id": "c8-blk-b"})
    resp = client.post("/connections?requester_id=c8-blk-a&recipient_id=c8-blk-b")
    assert resp.status_code == 403
    assert "blocked" in resp.json()["detail"]


def test_c8_blocked_pair_reverse_request_refused() -> None:
    """The blocked person also cannot send a connection request back (C8, bidirectional)."""
    _make_profile(client, "c8-blk-c", age=25)
    _make_profile(client, "c8-blk-d", age=26)
    # c blocks d
    client.post("/blocks", json={"blocker_id": "c8-blk-c", "blocked_id": "c8-blk-d"})
    # d tries to request c — bidirectional block check must refuse
    resp = client.post("/connections?requester_id=c8-blk-d&recipient_id=c8-blk-c")
    assert resp.status_code == 403
    assert "blocked" in resp.json()["detail"]


def test_c8_rate_limit_twenty_requests_per_rolling_window() -> None:
    """At most 20 connection requests per 24-hour rolling window, 21st returns 429 (C8)."""
    _make_profile(client, "c8-rl-req", age=25)
    for i in range(20):
        _make_profile(client, f"c8-rl-rec-{i}", age=26)
        resp = client.post(
            f"/connections?requester_id=c8-rl-req&recipient_id=c8-rl-rec-{i}"
        )
        assert resp.status_code == 201, f"request {i} failed: {resp.text}"
    # 21st request must be rate-limited
    _make_profile(client, "c8-rl-overflow", age=26)
    resp = client.post("/connections?requester_id=c8-rl-req&recipient_id=c8-rl-overflow")
    assert resp.status_code == 429
    assert "rate_limit_exceeded" in resp.json()["detail"]


def test_c8_accept_connection_request() -> None:
    """POST /connections/{id}/accept upgrades the connection to ACCEPTED (C8)."""
    _make_profile(client, "c8-acc-req", age=25)
    _make_profile(client, "c8-acc-rec", age=26)
    send_resp = client.post("/connections?requester_id=c8-acc-req&recipient_id=c8-acc-rec")
    assert send_resp.status_code == 201
    conn_id = send_resp.json()["id"]
    accept_resp = client.post(f"/connections/{conn_id}/accept?acceptor_id=c8-acc-rec")
    assert accept_resp.status_code == 200
    assert accept_resp.json()["status"] == "accepted"


def test_c8_accept_by_wrong_person_fails() -> None:
    """Only the recipient can accept a connection request (C8)."""
    _make_profile(client, "c8-wr-req", age=25)
    _make_profile(client, "c8-wr-rec", age=26)
    _make_profile(client, "c8-wr-other", age=27)
    send_resp = client.post("/connections?requester_id=c8-wr-req&recipient_id=c8-wr-rec")
    conn_id = send_resp.json()["id"]
    resp = client.post(f"/connections/{conn_id}/accept?acceptor_id=c8-wr-other")
    assert resp.status_code == 422


def test_c8_rate_limit_response_carries_machine_readable_reason() -> None:
    """The 429 rate-limit response carries the machine-readable reason 'rate_limit_exceeded' (C8, AC#20)."""
    _make_profile(client, "c8-mr-req", age=25)
    for i in range(20):
        _make_profile(client, f"c8-mr-rec-{i}", age=26)
        client.post(f"/connections?requester_id=c8-mr-req&recipient_id=c8-mr-rec-{i}")
    _make_profile(client, "c8-mr-overflow", age=26)
    resp = client.post("/connections?requester_id=c8-mr-req&recipient_id=c8-mr-overflow")
    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail == "rate_limit_exceeded"


# ---------------------------------------------------------------------------
# C9 — Messages require an accepted connection
# ---------------------------------------------------------------------------


def test_c9_message_refused_when_not_connected() -> None:
    """POST /messages is refused with 'not_connected' when there is no connection (C9)."""
    _make_profile(client, "c9-nc-a", age=25)
    _make_profile(client, "c9-nc-b", age=26)
    resp = client.post(
        "/messages", json={"sender_id": "c9-nc-a", "recipient_id": "c9-nc-b", "body": "hi"}
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "not_connected"


def test_c9_message_refused_when_connection_pending() -> None:
    """POST /messages is refused with 'connection_pending' when the connection has not been accepted (C9)."""
    _make_profile(client, "c9-pend-a", age=25)
    _make_profile(client, "c9-pend-b", age=26)
    client.post("/connections?requester_id=c9-pend-a&recipient_id=c9-pend-b")
    resp = client.post(
        "/messages",
        json={"sender_id": "c9-pend-a", "recipient_id": "c9-pend-b", "body": "hi"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "connection_pending"


def test_c9_message_allowed_after_accepted_connection() -> None:
    """POST /messages succeeds after both parties have accepted the connection (C9)."""
    _make_profile(client, "c9-ok-a", age=25)
    _make_profile(client, "c9-ok-b", age=26)
    send_resp = client.post("/connections?requester_id=c9-ok-a&recipient_id=c9-ok-b")
    conn_id = send_resp.json()["id"]
    client.post(f"/connections/{conn_id}/accept?acceptor_id=c9-ok-b")
    resp = client.post(
        "/messages",
        json={"sender_id": "c9-ok-a", "recipient_id": "c9-ok-b", "body": "hello"},
    )
    assert resp.status_code == 201
    assert resp.json()["body"] == "hello"


# ---------------------------------------------------------------------------
# C10 — Symmetric blocking: neither party can discover, request, nor message
# ---------------------------------------------------------------------------


def _setup_connected_pair(
    id_a: str, id_b: str, age_a: int = 25, age_b: int = 26
) -> str:
    """Create two profiles, send and accept a connection, return the connection id."""
    _make_profile(client, id_a, age=age_a)
    _make_profile(client, id_b, age=age_b)
    send_resp = client.post(f"/connections?requester_id={id_a}&recipient_id={id_b}")
    assert send_resp.status_code == 201, send_resp.text
    conn_id = send_resp.json()["id"]
    accept_resp = client.post(f"/connections/{conn_id}/accept?acceptor_id={id_b}")
    assert accept_resp.status_code == 200, accept_resp.text
    return conn_id


def test_c10_block_endpoint_records_block() -> None:
    """POST /blocks creates a block (C10)."""
    _make_profile(client, "c10-blk-a", age=25)
    _make_profile(client, "c10-blk-b", age=26)
    resp = client.post("/blocks", json={"blocker_id": "c10-blk-a", "blocked_id": "c10-blk-b"})
    assert resp.status_code == 204


def test_c10_check_block_endpoint() -> None:
    """GET /blocks confirms the block is recorded in both relevant directions (C10)."""
    _make_profile(client, "c10-chk-a", age=25)
    _make_profile(client, "c10-chk-b", age=26)
    client.post("/blocks", json={"blocker_id": "c10-chk-a", "blocked_id": "c10-chk-b"})
    # The block was set a→b; the symmetric check is via may-contact
    resp_ab = client.get("/blocks/c10-chk-a/c10-chk-b")
    assert resp_ab.status_code == 200
    assert resp_ab.json()["blocked"] is True


def test_c10_may_contact_is_false_for_both_directions_after_block() -> None:
    """GET /may-contact returns False for both a→b and b→a after a blocks b (C10)."""
    _make_profile(client, "c10-mc-a", age=25)
    _make_profile(client, "c10-mc-b", age=26)
    client.post("/blocks", json={"blocker_id": "c10-mc-a", "blocked_id": "c10-mc-b"})
    resp_ab = client.get("/may-contact/c10-mc-a/c10-mc-b")
    assert resp_ab.json()["may_contact"] is False
    resp_ba = client.get("/may-contact/c10-mc-b/c10-mc-a")
    assert resp_ba.json()["may_contact"] is False


def test_c10_blocked_person_cannot_send_request_to_blocker() -> None:
    """After A blocks B, B cannot send a connection request to A (C10 — symmetric)."""
    _make_profile(client, "c10-req-a", age=25)
    _make_profile(client, "c10-req-b", age=26)
    client.post("/blocks", json={"blocker_id": "c10-req-a", "blocked_id": "c10-req-b"})
    resp = client.post("/connections?requester_id=c10-req-b&recipient_id=c10-req-a")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "blocked"


def test_c10_blocker_cannot_send_request_to_blocked_person() -> None:
    """After A blocks B, A cannot send a connection request to B (C10)."""
    _make_profile(client, "c10-req-c", age=25)
    _make_profile(client, "c10-req-d", age=26)
    client.post("/blocks", json={"blocker_id": "c10-req-c", "blocked_id": "c10-req-d"})
    resp = client.post("/connections?requester_id=c10-req-c&recipient_id=c10-req-d")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "blocked"


def test_c10_block_reason_same_in_both_request_directions() -> None:
    """The reason code 'blocked' is identical regardless of which party sends the request (C10, AC#20)."""
    _make_profile(client, "c10-sym-req-a", age=25)
    _make_profile(client, "c10-sym-req-b", age=26)
    client.post("/blocks", json={"blocker_id": "c10-sym-req-a", "blocked_id": "c10-sym-req-b"})
    resp_ab = client.post("/connections?requester_id=c10-sym-req-a&recipient_id=c10-sym-req-b")
    resp_ba = client.post("/connections?requester_id=c10-sym-req-b&recipient_id=c10-sym-req-a")
    assert resp_ab.json()["detail"] == resp_ba.json()["detail"] == "blocked"


def test_c10_blocked_person_cannot_message_blocker() -> None:
    """After A blocks B (post-connection), B cannot send a message to A (C10 — symmetric)."""
    _setup_connected_pair("c10-msg-a", "c10-msg-b")
    client.post("/blocks", json={"blocker_id": "c10-msg-a", "blocked_id": "c10-msg-b"})
    resp = client.post(
        "/messages",
        json={"sender_id": "c10-msg-b", "recipient_id": "c10-msg-a", "body": "hi from b"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "blocked"


def test_c10_blocker_cannot_message_blocked_person() -> None:
    """After A blocks B (post-connection), A cannot send a message to B (C10)."""
    _setup_connected_pair("c10-msg-c", "c10-msg-d")
    client.post("/blocks", json={"blocker_id": "c10-msg-c", "blocked_id": "c10-msg-d"})
    resp = client.post(
        "/messages",
        json={"sender_id": "c10-msg-c", "recipient_id": "c10-msg-d", "body": "hi from c"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "blocked"


def test_c10_block_reason_same_in_both_message_directions() -> None:
    """The reason code 'blocked' is identical regardless of which party sends the message (C10, AC#20)."""
    _setup_connected_pair("c10-sym-msg-a", "c10-sym-msg-b")
    client.post(
        "/blocks", json={"blocker_id": "c10-sym-msg-a", "blocked_id": "c10-sym-msg-b"}
    )
    resp_ab = client.post(
        "/messages",
        json={"sender_id": "c10-sym-msg-a", "recipient_id": "c10-sym-msg-b", "body": "x"},
    )
    resp_ba = client.post(
        "/messages",
        json={"sender_id": "c10-sym-msg-b", "recipient_id": "c10-sym-msg-a", "body": "y"},
    )
    assert resp_ab.json()["detail"] == resp_ba.json()["detail"] == "blocked"


def test_c10_blocked_person_absent_from_blocker_discovery() -> None:
    """After A blocks B, B does not appear in A's discovery results (C10)."""
    _make_profile(
        client, "c10-disc-a", age=25, open_to_friends=True, interests=["hiking"]
    )
    _make_profile(
        client, "c10-disc-b", age=26, open_to_friends=True, interests=["hiking"]
    )
    _pass_age_assurance(client, "c10-disc-a")
    _pass_age_assurance(client, "c10-disc-b")
    # Without block, b appears in a's discovery
    resp_before = client.get("/discovery/c10-disc-a?radius_km=25")
    assert any(r["profile"]["id"] == "c10-disc-b" for r in resp_before.json())
    # Block: a blocks b
    client.post("/blocks", json={"blocker_id": "c10-disc-a", "blocked_id": "c10-disc-b"})
    resp_after = client.get("/discovery/c10-disc-a?radius_km=25")
    assert not any(r["profile"]["id"] == "c10-disc-b" for r in resp_after.json())


def test_c10_blocker_absent_from_blocked_persons_discovery() -> None:
    """After A blocks B, A does not appear in B's discovery results either (C10 — symmetric)."""
    _make_profile(
        client, "c10-disc-c", age=25, open_to_friends=True, interests=["hiking"]
    )
    _make_profile(
        client, "c10-disc-d", age=26, open_to_friends=True, interests=["hiking"]
    )
    _pass_age_assurance(client, "c10-disc-c")
    _pass_age_assurance(client, "c10-disc-d")
    # Without block, c appears in d's discovery
    resp_before = client.get("/discovery/c10-disc-d?radius_km=25")
    assert any(r["profile"]["id"] == "c10-disc-c" for r in resp_before.json())
    # Block: c blocks d
    client.post("/blocks", json={"blocker_id": "c10-disc-c", "blocked_id": "c10-disc-d"})
    # c (the blocker) must also be absent from d's results
    resp_after = client.get("/discovery/c10-disc-d?radius_km=25")
    assert not any(r["profile"]["id"] == "c10-disc-c" for r in resp_after.json())


# ---------------------------------------------------------------------------
# C11 — Abuse reports: fixed reason list, unrecognised reason refused
# ---------------------------------------------------------------------------


def test_c11_submit_user_report_with_valid_reason() -> None:
    """POST /reports succeeds with a valid reason targeting a user (C11)."""
    resp = client.post(
        "/reports",
        json={
            "reporter_id": "c11-reporter",
            "target_id": "c11-target-user",
            "target_kind": "user",
            "reason": "harassment",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["reason"] == "harassment"
    assert body["target_kind"] == "user"
    assert body["reporter_id"] == "c11-reporter"


def test_c11_submit_message_report_with_valid_reason() -> None:
    """POST /reports succeeds with a valid reason targeting a message (C11)."""
    resp = client.post(
        "/reports",
        json={
            "reporter_id": "c11-reporter-msg",
            "target_id": "msg-42",
            "target_kind": "message",
            "reason": "inappropriate_content",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["reason"] == "inappropriate_content"
    assert body["target_kind"] == "message"


def test_c11_all_valid_reasons_accepted() -> None:
    """Every reason in the fixed list is accepted by the API (C11)."""
    valid_reasons = [
        "spam",
        "harassment",
        "inappropriate_content",
        "fake_profile",
        "underage_user",
        "other",
    ]
    for reason in valid_reasons:
        resp = client.post(
            "/reports",
            json={
                "reporter_id": "c11-all-reasons",
                "target_id": "c11-target",
                "target_kind": "user",
                "reason": reason,
            },
        )
        assert resp.status_code == 201, f"reason '{reason}' was rejected unexpectedly"
        assert resp.json()["reason"] == reason


def test_c11_unrecognised_reason_refused_with_422() -> None:
    """POST /reports with an unrecognised reason returns 422 — never stored as free text (C11)."""
    resp = client.post(
        "/reports",
        json={
            "reporter_id": "c11-bad-reason",
            "target_id": "c11-target",
            "target_kind": "user",
            "reason": "custom_free_text_reason",
        },
    )
    assert resp.status_code == 422


def test_c11_unrecognised_target_kind_refused_with_422() -> None:
    """POST /reports with an unrecognised target_kind returns 422 (C11)."""
    resp = client.post(
        "/reports",
        json={
            "reporter_id": "c11-bad-kind",
            "target_id": "c11-target",
            "target_kind": "post",  # not a valid target kind
            "reason": "spam",
        },
    )
    assert resp.status_code == 422


def test_c11_report_with_optional_additional_text() -> None:
    """POST /reports with additional text stores the trimmed text (C11)."""
    resp = client.post(
        "/reports",
        json={
            "reporter_id": "c11-text-reporter",
            "target_id": "c11-text-target",
            "target_kind": "user",
            "reason": "other",
            "additional_text": "  extra context  ",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["additional_text"] == "extra context"  # trimmed


# ---------------------------------------------------------------------------
# C14 — Contact removal: reported person cannot send requests or messages
# ---------------------------------------------------------------------------


def _submit_report_and_resolve(
    reporter_id: str,
    target_id: str,
    target_kind: str,
    outcome: str,
) -> None:
    """Helper: submit a report against target_id then resolve it with outcome."""
    submit_resp = client.post(
        "/reports",
        json={
            "reporter_id": reporter_id,
            "target_id": target_id,
            "target_kind": target_kind,
            "reason": "harassment",
        },
    )
    assert submit_resp.status_code == 201, submit_resp.text
    report_id = submit_resp.json()["id"]
    resolve_resp = client.post(
        f"/reports/{report_id}/resolve",
        json={"outcome": outcome},
    )
    assert resolve_resp.status_code == 200, resolve_resp.text


def test_c14_contact_removal_prevents_connection_request() -> None:
    """A user reported and resolved as contact_removal cannot send connection requests (C14)."""
    _make_profile(client, "c14-req-a", age=25)  # will be contact-removed
    _make_profile(client, "c14-req-b", age=26)
    _submit_report_and_resolve(
        reporter_id="c14-reporter-req",
        target_id="c14-req-a",
        target_kind="user",
        outcome="contact_removal",
    )
    resp = client.post("/connections?requester_id=c14-req-a&recipient_id=c14-req-b")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "contact_removed"


def test_c14_contact_removal_prevents_sending_message() -> None:
    """A user resolved as contact_removal cannot send messages (C14)."""
    _make_profile(client, "c14-msg-a", age=25)  # will be contact-removed
    _make_profile(client, "c14-msg-b", age=26)
    # Establish accepted connection first so the only barrier is contact removal
    conn_resp = client.post("/connections?requester_id=c14-msg-b&recipient_id=c14-msg-a")
    assert conn_resp.status_code == 201
    conn_id = conn_resp.json()["id"]
    client.post(f"/connections/{conn_id}/accept?acceptor_id=c14-msg-a")
    # Apply contact removal to c14-msg-a
    _submit_report_and_resolve(
        reporter_id="c14-reporter-msg",
        target_id="c14-msg-a",
        target_kind="user",
        outcome="contact_removal",
    )
    resp = client.post(
        "/messages",
        json={"sender_id": "c14-msg-a", "recipient_id": "c14-msg-b", "body": "hi"},
    )
    assert resp.status_code == 403
    assert resp.json()["detail"] == "contact_removed"


def test_c14_contact_removal_reason_is_machine_readable() -> None:
    """The refusal reason for contact_removal is the string 'contact_removed' (C14, AC#20)."""
    _make_profile(client, "c14-mr-a", age=25)
    _make_profile(client, "c14-mr-b", age=26)
    _submit_report_and_resolve(
        reporter_id="c14-reporter-mr",
        target_id="c14-mr-a",
        target_kind="user",
        outcome="contact_removal",
    )
    resp = client.post("/connections?requester_id=c14-mr-a&recipient_id=c14-mr-b")
    assert resp.json()["detail"] == "contact_removed"


def test_c14_no_action_does_not_restrict_contact() -> None:
    """Resolving a report as no_action leaves the reported person able to send requests (C14)."""
    _make_profile(client, "c14-na-a", age=25)
    _make_profile(client, "c14-na-b", age=26)
    _submit_report_and_resolve(
        reporter_id="c14-reporter-na",
        target_id="c14-na-a",
        target_kind="user",
        outcome="no_action",
    )
    resp = client.post("/connections?requester_id=c14-na-a&recipient_id=c14-na-b")
    assert resp.status_code == 201


def test_c14_warning_does_not_restrict_contact() -> None:
    """Resolving a report as warning leaves the reported person able to send requests (C14)."""
    _make_profile(client, "c14-warn-a", age=25)
    _make_profile(client, "c14-warn-b", age=26)
    _submit_report_and_resolve(
        reporter_id="c14-reporter-warn",
        target_id="c14-warn-a",
        target_kind="user",
        outcome="warning",
    )
    resp = client.post("/connections?requester_id=c14-warn-a&recipient_id=c14-warn-b")
    assert resp.status_code == 201


def test_c14_contact_status_endpoint_reports_removed_state() -> None:
    """GET /profiles/{id}/contact-status returns contact_removed=True with reason after resolution (C14)."""
    _make_profile(client, "c14-status-a", age=25)
    _submit_report_and_resolve(
        reporter_id="c14-reporter-status",
        target_id="c14-status-a",
        target_kind="user",
        outcome="contact_removal",
    )
    resp = client.get("/profiles/c14-status-a/contact-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contact_removed"] is True
    assert body["reason"] == "contact_removal"


def test_c14_contact_status_endpoint_reports_not_removed_by_default() -> None:
    """GET /profiles/{id}/contact-status returns contact_removed=False for a normal profile (C14)."""
    _make_profile(client, "c14-status-ok", age=25)
    resp = client.get("/profiles/c14-status-ok/contact-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contact_removed"] is False
    assert body["reason"] is None


# ---------------------------------------------------------------------------
# C16 — Retention policy endpoint (single readable source of truth)
# ---------------------------------------------------------------------------


def test_c16_retention_policy_endpoint_returns_200() -> None:
    """GET /retention-policy returns HTTP 200 (C16)."""
    resp = client.get("/retention-policy")
    assert resp.status_code == 200


def test_c16_retention_policy_messages_24_months() -> None:
    """Retention policy specifies messages are kept for 24 months (C16)."""
    resp = client.get("/retention-policy")
    assert resp.status_code == 200
    body = resp.json()
    assert body["messages_months"] == 24


def test_c16_retention_policy_blocks_24_months() -> None:
    """Retention policy specifies blocks are kept for 24 months after closure (C16)."""
    resp = client.get("/retention-policy")
    body = resp.json()
    assert body["blocks_months"] == 24


def test_c16_retention_policy_reports_24_months() -> None:
    """Retention policy specifies reports are kept for 24 months after closure (C16)."""
    resp = client.get("/retention-policy")
    body = resp.json()
    assert body["reports_months"] == 24


def test_c16_retention_policy_other_30_days() -> None:
    """Retention policy specifies everything else is purged within 30 days of deletion (C16)."""
    resp = client.get("/retention-policy")
    body = resp.json()
    assert body["other_days"] == 30


def test_c16_retention_policy_has_description() -> None:
    """Retention policy response includes human-readable description for each category (C16)."""
    resp = client.get("/retention-policy")
    body = resp.json()
    desc = body["description"]
    assert "messages" in desc
    assert "blocks" in desc
    assert "reports" in desc
    assert "other" in desc
    # Descriptions mention the specific durations
    assert "24" in desc["messages"]
    assert "24" in desc["blocks"]
    assert "24" in desc["reports"]
    assert "30" in desc["other"]


def test_c16_retention_policy_source_of_truth_matches_constants() -> None:
    """The endpoint values match the RETENTION_POLICY constants in retention.py (C16)."""
    from app.retention import RETENTION_POLICY

    resp = client.get("/retention-policy")
    body = resp.json()
    assert body["messages_months"] == RETENTION_POLICY.messages_months
    assert body["blocks_months"] == RETENTION_POLICY.blocks_months
    assert body["reports_months"] == RETENTION_POLICY.reports_months
    assert body["other_days"] == RETENTION_POLICY.other_days
