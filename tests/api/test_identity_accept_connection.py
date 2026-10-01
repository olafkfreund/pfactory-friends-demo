"""
AC#1: accepting or declining a connection as a different person is rejected with 403.

Concrete check: POST /connections/{id}/accept returns 403 when the JWT subject
is NOT the recipient (target_id) of that connection.

Implementation note: the subtask description refers to "PATCH /connections/{id}/accept"
but app/api/app/main.py declares the route as @app.post; the tests call POST to match
the running application.
"""

import base64
import json
import os
import uuid

import requests


# ---------------------------------------------------------------------------
# JWT helper for ALLOW_UNVERIFIED_TOKENS=1 test environments
# ---------------------------------------------------------------------------

def _make_dev_token(sub: str, audience: str = "myfriends-api") -> str:
    """Build a minimally valid JWT for test environments running with ALLOW_UNVERIFIED_TOKENS=1.

    python-jose skips signature verification when that flag is set, so the
    signature component is a fixed placeholder. The payload carries only the
    claims the app actually reads: ``sub`` and ``aud``.
    """
    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header_b64 = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload_b64 = _b64url(json.dumps({"sub": sub, "aud": audience}).encode())
    sig_b64 = _b64url(b"placeholder")
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Shared setup helper
# ---------------------------------------------------------------------------

def _create_pending_connection(base_url: str) -> tuple[str, str, str, str]:
    """Create two profiles and a pending connection request from A to B.

    Returns ``(connection_id, token_a, user_b_id, token_b)`` so callers can
    act as either party (or neither) when exercising the accept endpoint.
    """
    user_a = f"user-a-{uuid.uuid4().hex}"
    user_b = f"user-b-{uuid.uuid4().hex}"
    token_a = _make_dev_token(user_a)
    token_b = _make_dev_token(user_b)

    resp = requests.post(
        f"{base_url}/profiles",
        json={"display_name": "User A", "bio": "", "age": 25, "interests": []},
        headers=_bearer(token_a),
        timeout=10,
    )
    assert resp.status_code == 201, f"profile A creation failed ({resp.status_code}): {resp.text}"

    resp = requests.post(
        f"{base_url}/profiles",
        json={"display_name": "User B", "bio": "", "age": 25, "interests": []},
        headers=_bearer(token_b),
        timeout=10,
    )
    assert resp.status_code == 201, f"profile B creation failed ({resp.status_code}): {resp.text}"

    resp = requests.post(
        f"{base_url}/connections",
        json={"target_id": user_b},
        headers=_bearer(token_a),
        timeout=10,
    )
    assert resp.status_code == 201, f"connection request failed ({resp.status_code}): {resp.text}"

    connection_id = resp.json()["id"]
    return connection_id, token_a, user_b, token_b


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_accept_connection_non_recipient_returns_403():
    """POST /connections/{id}/accept returns 403 when the caller is not the recipient.

    AC#1: accepting a connection as a different person is rejected with 403.

    Setup: user_a sends a connection request to user_b.
    Action: user_c (a third party — neither requester nor recipient) calls accept.
    Expected: 403 Forbidden.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]
    connection_id, _token_a, _user_b, _token_b = _create_pending_connection(base_url)

    # user_c is a completely independent identity: not the requester, not the recipient.
    user_c = f"user-c-{uuid.uuid4().hex}"
    token_c = _make_dev_token(user_c)

    resp = requests.post(
        f"{base_url}/connections/{connection_id}/accept",
        headers=_bearer(token_c),
        timeout=10,
    )
    assert resp.status_code == 403


def test_accept_connection_recipient_is_not_forbidden():
    """POST /connections/{id}/accept does NOT return 403 when the caller is the recipient.

    Happy-path counterpart to the identity-enforcement check: confirms that the
    correct user (user_b, the recipient) is accepted rather than also blocked.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]
    connection_id, _token_a, _user_b, token_b = _create_pending_connection(base_url)

    resp = requests.post(
        f"{base_url}/connections/{connection_id}/accept",
        headers=_bearer(token_b),
        timeout=10,
    )
    assert resp.status_code == 200
