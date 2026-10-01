# AC#3: no caller can grant another person's age assurance.
# Subtask: age-assurance-own-only-api
# Target:  app/api/app/main.py::record_age_assurance
# Criterion: POST /profiles/{id}/age-assurance returns 403 when the JWT
#            subject differs from the path id.
#
# NOTE — path discrepancy between criterion and implementation:
# The subtask description specifies POST /profiles/{id}/age-assurance with
# a caller-supplied path id. The deployed implementation delivers AC#3 by a
# different URL shape: POST /profiles/me/age-assurance (no path id — the
# caller's identity is taken exclusively from the JWT subject claim, so there
# is no path parameter to supply a different id through). A request to
# POST /profiles/{some_id}/age-assurance will therefore find no matching route
# and should return 404 or 405, not 403 as the criterion states. The test below
# asserts 403 as written; it will fail until either (a) the implementation
# adds the /profiles/{id}/age-assurance route with ownership enforcement, or
# (b) the criterion is updated to reflect the /profiles/me/age-assurance design.

from __future__ import annotations

import base64
import json
import os

import requests


def _make_bearer_token(sub: str) -> str:
    """Build a minimal unsigned JWT accepted by the app under ALLOW_UNVERIFIED_TOKENS=1.

    The app's _decode_token path for ALLOW_UNVERIFIED_TOKENS=1 calls
    jose.jwt.decode with options={"verify_signature": False}, so any
    structurally valid JWT (three base64url segments) is accepted regardless
    of the signature bytes.
    """

    def _b64url(data: dict) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = _b64url({"alg": "HS256", "typ": "JWT"})
    payload = _b64url({"sub": sub, "aud": "myfriends-api"})
    sig = base64.urlsafe_b64encode(b"fake-sig").rstrip(b"=").decode()
    return f"{header}.{payload}.{sig}"


def test_age_assurance_cross_identity_returns_403():
    """POST /profiles/{id}/age-assurance returns 403 when JWT sub != path id.

    AC#3: no caller can grant another person's age assurance.

    Caller A (sub="caller-a-001") sends a request to record age assurance for
    profile "other-person-b-002". The server must reject this with 403 because
    the acting identity in the path does not match the authenticated identity.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]
    caller_id = "caller-a-001"
    target_id = "other-person-b-002"

    token = _make_bearer_token(caller_id)
    resp = requests.post(
        f"{base_url}/profiles/{target_id}/age-assurance",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert resp.status_code == 403
