# AC#2: Deleting an account requires that the authenticated caller owns that account;
# a caller cannot delete anyone else's account by naming its id.
#
# Subtask:  delete-account-own-only-api
# Target:   app/api/app/main.py::delete_my_account
# Criterion: DELETE /profiles/{id} returns 403 when the JWT subject does not match
#            the path id.
#
# Implementation note:
#   The current implementation exposes DELETE /profiles/me (not DELETE /profiles/{id}).
#   The acting identity is taken exclusively from the JWT subject; there is no path
#   parameter for the target profile ID. Consequently, a request to
#   DELETE /profiles/{other_user_id} will return 404 (no route), not 403.
#   This test asserts the criterion as written (403). If the implementation diverges
#   from the criterion the test will fail and surface the discrepancy — amending an
#   acceptance criterion is a human decision.

from __future__ import annotations

import base64
import json
import os
import uuid

import pytest
import requests


# ---------------------------------------------------------------------------
# JWT helper — works with ALLOW_UNVERIFIED_TOKENS=1 (no OIDC_JWKS_URI)
# ---------------------------------------------------------------------------

def _make_dev_jwt(sub: str, aud: str = "myfriends-api") -> str:
    """Build a minimal JWT accepted under ALLOW_UNVERIFIED_TOKENS=1.

    The server sets verify_signature=False in that mode so only valid
    base64url-encoded header and payload segments are required; the
    signature part may be any non-empty value.
    """
    def _b64url(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = _b64url({"alg": "HS256", "typ": "JWT"})
    payload = _b64url({"sub": sub, "aud": aud})
    sig = base64.urlsafe_b64encode(b"devonly").rstrip(b"=").decode()
    return f"{header}.{payload}.{sig}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_delete_profile_by_other_user_id_returns_403():
    """AC#2: DELETE /profiles/{id} returns 403 when JWT subject != path id.

    Caller authenticates as user_b but names user_a's id in the URL path.
    The server must reject this with 403 and must not reveal whether
    user_a's profile exists (returning 404 would leak that information).
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]
    user_a_id = f"user-a-{uuid.uuid4()}"
    user_b_id = f"user-b-{uuid.uuid4()}"

    token_b = _make_dev_jwt(sub=user_b_id)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # user_b names user_a's id in the path — must be rejected with 403
    resp = requests.delete(
        f"{base_url}/profiles/{user_a_id}",
        headers=headers_b,
        timeout=10,
    )
    assert resp.status_code == 403


def test_owner_can_delete_own_account_via_profiles_me():
    """AC#2 happy path: the authenticated caller can delete their own account.

    A caller authenticated as user_c calls DELETE /profiles/me, which is
    the endpoint that deletes the caller's own account (identity from JWT).
    The endpoint must return 200 and confirm the deletion.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]
    user_c_id = f"user-c-{uuid.uuid4()}"
    token_c = _make_dev_jwt(sub=user_c_id)
    headers_c = {"Authorization": f"Bearer {token_c}"}

    # Create the profile so the delete has something to act on
    create_resp = requests.post(
        f"{base_url}/profiles",
        headers=headers_c,
        json={
            "display_name": "Ownership Test User",
            "bio": "AC#2 happy-path setup",
            "age": 25,
            "interests": [],
        },
        timeout=10,
    )
    assert create_resp.status_code == 201, (
        f"Test setup failed: could not create profile for user_c "
        f"(status={create_resp.status_code}, body={create_resp.text!r})"
    )

    # Owner deletes their own account — must succeed
    delete_resp = requests.delete(
        f"{base_url}/profiles/me",
        headers=headers_c,
        timeout=10,
    )
    assert delete_resp.status_code == 200


@pytest.mark.parametrize(
    "path_id,jwt_sub",
    [
        ("user-x-static", "user-y-static"),
        ("account-111", "account-222"),
    ],
    ids=["x-vs-y", "111-vs-222"],
)
def test_delete_profile_by_mismatched_id_returns_403_parametrized(
    path_id: str,
    jwt_sub: str,
) -> None:
    """AC#2: 403 is returned for any mismatch between path id and JWT subject.

    Parametrised to confirm the ownership check is not sensitive to the
    specific id values involved.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]

    token = _make_dev_jwt(sub=jwt_sub)
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.delete(
        f"{base_url}/profiles/{path_id}",
        headers=headers,
        timeout=10,
    )
    assert resp.status_code == 403
