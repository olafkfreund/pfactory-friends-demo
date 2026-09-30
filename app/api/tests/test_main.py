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
