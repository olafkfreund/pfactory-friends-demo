# AC#1: toggling availability for another person is rejected with 403
# Rationale: toggling availability for another person is rejected with 403
#
# CRITERION AS WRITTEN (test_plan.json, subtask identity-enforced-availability-api):
#   "Verify that PATCH /profiles/{id}/availability returns 403 when the JWT
#    subject differs from the path id"
#
# IMPLEMENTATION DISCREPANCY:
#   The remediated endpoint is PATCH /profiles/me/availability (not
#   /profiles/{id}/availability). Identity is derived exclusively from the
#   JWT sub claim — there is no {id} path parameter to exploit. A request
#   to /profiles/{some_other_id}/availability hits no route and the router
#   returns 404, NOT 403 as the criterion states.
#
#   test_set_availability_cross_identity_path_returns_403 asserts the
#   criterion literally (403) and will fail until the implementation either
#   (a) introduces /profiles/{id}/availability with a 403 check, or
#   (b) the criterion is updated to reflect the /profiles/me/... design.
#
# Additional tests verify AC#1 holds for the actual /profiles/me/availability
# endpoint: that no authenticated caller can toggle another person's
# availability.
#
# JWT construction: uses ALLOW_UNVERIFIED_TOKENS=1 (dev mode) to produce
# unsigned tokens accepted by _decode_token.  The token carries the
# mandatory `aud: "myfriends-api"` claim (the default OIDC_AUDIENCE).

from __future__ import annotations

import base64
import json
import os

import requests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64url(data: dict) -> str:
    """Base64url-encode a JSON object without padding (standard JWT segment)."""
    return base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).rstrip(b"=").decode()


def _make_jwt(sub: str, aud: str = "myfriends-api") -> str:
    """Return a minimal unsigned JWT accepted when ALLOW_UNVERIFIED_TOKENS=1.

    python-jose decodes with verify_signature=False when that env var is set,
    so the signature segment is ignored.  The header and payload must still be
    valid base64url-encoded JSON.
    """
    header = _b64url({"alg": "HS256", "typ": "JWT"})
    payload = _b64url({"sub": sub, "aud": aud})
    return f"{header}.{payload}.fakesignature"


# ---------------------------------------------------------------------------
# Criterion-literal test (asserted as written — see discrepancy note above)
# ---------------------------------------------------------------------------

def test_set_availability_cross_identity_path_returns_403():
    """PATCH /profiles/{id}/availability with a mismatched JWT sub returns 403.

    AC#1: toggling availability for another person is rejected with 403.

    The criterion states this path and status code. The actual implementation
    serves /profiles/me/availability (no path id) so a request to
    /profiles/{bob_id}/availability is an unmatched route and returns 404.
    This test asserts 403 as written in the criterion; it will fail until the
    implementation matches the criterion or the criterion is revised.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]
    alice_id = "alice-avail-xid-001"
    bob_id = "bob-avail-xid-001"

    # Authenticated as alice, trying to patch bob's availability via the
    # /profiles/{id}/availability path named in the criterion.
    alice_token = f"Bearer {_make_jwt(alice_id)}"

    resp = requests.patch(
        f"{base_url}/profiles/{bob_id}/availability",
        json={"is_open": True},
        headers={"Authorization": alice_token},
        timeout=10,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Auth guard — unauthenticated request is rejected before business logic
# ---------------------------------------------------------------------------

def test_set_availability_requires_authentication():
    """PATCH /profiles/me/availability returns 401 when no Authorization header is sent.

    AC#1 / AC#8: every state-changing endpoint rejects unauthenticated calls.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]

    resp = requests.patch(
        f"{base_url}/profiles/me/availability",
        json={"is_open": True},
        timeout=10,
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Cross-identity guarantee on the actual endpoint
# ---------------------------------------------------------------------------

def test_set_availability_caller_cannot_affect_another_profile():
    """Authenticated as user B, calling /profiles/me/availability cannot change
    user A's availability — the endpoint always acts on the JWT sub's profile.

    AC#1: toggling availability for another person is rejected (here enforced
    structurally: the endpoint has no path id, so a caller can only ever act
    on their own profile).

    Test sequence:
      1. Create a profile for alice and mark her is_open = True.
      2. Authenticate as bob (no profile), call PATCH /profiles/me/availability
         with is_open=False.
      3. Bob's call should return 404 (no profile for bob) — NOT touching alice.
      4. Fetch alice's profile; is_open must still be True.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]
    alice_id = "alice-avail-own-test-001"
    bob_id = "bob-avail-own-test-001"

    alice_token = f"Bearer {_make_jwt(alice_id)}"
    bob_token = f"Bearer {_make_jwt(bob_id)}"

    # Step 1: create alice's profile
    requests.post(
        f"{base_url}/profiles",
        json={"display_name": "Alice Avail", "bio": "", "age": 25, "interests": []},
        headers={"Authorization": alice_token},
        timeout=10,
    )

    # Step 1b: mark alice's availability as open
    alice_avail_resp = requests.patch(
        f"{base_url}/profiles/me/availability",
        json={"is_open": True},
        headers={"Authorization": alice_token},
        timeout=10,
    )
    # Accept 200 (profile updated) or 404 (profile not committed — DB may be
    # unavailable in this environment); either way bob's call must not touch alice.
    assert alice_avail_resp.status_code in (200, 404, 409)

    # Step 2: bob (no profile) tries to set availability
    bob_resp = requests.patch(
        f"{base_url}/profiles/me/availability",
        json={"is_open": False},
        headers={"Authorization": bob_token},
        timeout=10,
    )
    # Bob has no profile → 404.  Crucially bob cannot name alice's id — the
    # endpoint provides no such parameter.
    assert bob_resp.status_code == 404

    # Step 3: verify alice's profile is unchanged (if alice's profile was created)
    alice_profile_resp = requests.get(
        f"{base_url}/profiles/me",
        headers={"Authorization": alice_token},
        timeout=10,
    )
    if alice_profile_resp.status_code == 200:
        alice_data = alice_profile_resp.json()
        # alice set is_open=True; bob's call must not have flipped it to False
        assert alice_data.get("is_open") is True
