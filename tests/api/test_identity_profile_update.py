# AC#1: a request whose authenticated identity is person A and acting identity is
# person B is rejected with 403.
#
# Subtask: identity-enforced-profile-update-api
# Target:  app/api/app/main.py::update_my_profile  (PATCH /profiles/me)
# Criterion (as written): Verify that PUT /profiles/{id} returns 403 when the JWT
# subject differs from the path id.
#
# Note on endpoint shape: the remediation replaced PUT /profiles/{id} with
# PATCH /profiles/me, binding the acting identity to the JWT subject so that
# cross-identity updates are architecturally impossible. This file asserts:
#   (a) PUT /profiles/{id} with a mismatched JWT subject returns 403 — the stated
#       criterion; if the route is gone the test will fail and surface that.
#   (b) PATCH /profiles/me with person A's JWT cannot modify person B's profile
#       data, demonstrating that the identity enforcement holds end-to-end.

from __future__ import annotations

import base64
import json
import os
import time
import uuid

import requests


# ---------------------------------------------------------------------------
# Helper: craft a JWT accepted when ALLOW_UNVERIFIED_TOKENS=1 is set on the server
# ---------------------------------------------------------------------------

def _make_unverified_jwt(sub: str, aud: str = "myfriends-api") -> str:
    """Return a compact JWT whose signature is a placeholder.

    The server's _decode_token skips signature verification when
    ALLOW_UNVERIFIED_TOKENS=1; expiry is set one hour ahead to pass the
    'exp' claim check that jose still performs in that mode.
    """

    def _b64u(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = _b64u({"alg": "HS256", "typ": "JWT"})
    payload = _b64u(
        {
            "sub": sub,
            "aud": aud,
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        }
    )
    return f"{header}.{payload}.placeholder"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_put_profile_by_id_with_different_jwt_subject_returns_403():
    """AC#1: PUT /profiles/{id} with a JWT whose 'sub' differs from {id} must return 403.

    The criterion states the status code is 403. If the implementation has
    removed the PUT /profiles/{id} route in favour of PATCH /profiles/me, the
    response will be 404 or 405 and this test will fail, surfacing that gap.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]

    # Two distinct subjects so person A and person B are different identities.
    person_a_id = f"test-person-a-{uuid.uuid4().hex[:12]}"
    person_b_id = f"test-person-b-{uuid.uuid4().hex[:12]}"

    person_a_jwt = _make_unverified_jwt(person_a_id)
    person_b_jwt = _make_unverified_jwt(person_b_id)

    # Ensure person B's profile exists so the resource is present.
    setup = requests.post(
        f"{base_url}/profiles",
        json={"display_name": "Person B Setup", "bio": "setup", "age": 25, "interests": []},
        headers={"Authorization": f"Bearer {person_b_jwt}"},
        timeout=10,
    )
    assert setup.status_code in (201, 409), (
        f"Failed to set up person B's profile for test: {setup.status_code} {setup.text}"
    )

    # Person A attempts to update person B's profile via PUT /profiles/{person_b_id}.
    # The JWT subject is person_a_id — this differs from the path id person_b_id.
    # AC#1 requires this to be rejected with 403.
    resp = requests.put(
        f"{base_url}/profiles/{person_b_id}",
        json={"display_name": "Tampered By A", "bio": "tampered", "age": 25},
        headers={"Authorization": f"Bearer {person_a_jwt}"},
        timeout=10,
    )

    assert resp.status_code == 403


def test_patch_profiles_me_with_foreign_jwt_does_not_modify_target_profile():
    """AC#1: calling PATCH /profiles/me with person A's JWT cannot overwrite person B's data.

    The endpoint PATCH /profiles/me derives the profile to update exclusively
    from the JWT's 'sub' claim. This test proves that person A's token cannot
    reach person B's profile regardless of the payload supplied.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]

    person_a_id = f"test-person-a-{uuid.uuid4().hex[:12]}"
    person_b_id = f"test-person-b-{uuid.uuid4().hex[:12]}"

    person_a_jwt = _make_unverified_jwt(person_a_id)
    person_b_jwt = _make_unverified_jwt(person_b_id)

    # Person B creates their profile with a known, unique bio.
    original_bio = f"original-bio-{uuid.uuid4().hex[:16]}"
    create_resp = requests.post(
        f"{base_url}/profiles",
        json={
            "display_name": "Person B Immutable",
            "bio": original_bio,
            "age": 30,
            "interests": [],
        },
        headers={"Authorization": f"Bearer {person_b_jwt}"},
        timeout=10,
    )
    assert create_resp.status_code == 201, (
        f"Could not create person B's profile (needed for isolation check): "
        f"{create_resp.status_code} {create_resp.text}"
    )

    # Person A calls PATCH /profiles/me — their JWT sets caller_id to person_a_id,
    # so the update targets person A's (non-existent or separate) profile, not person B's.
    requests.patch(
        f"{base_url}/profiles/me",
        json={"bio": "INJECTED BY PERSON A — SHOULD NOT APPEAR IN PERSON B"},
        headers={"Authorization": f"Bearer {person_a_jwt}"},
        timeout=10,
    )

    # Read person B's profile back; the bio must be the original value.
    read_resp = requests.get(
        f"{base_url}/profiles/me",
        headers={"Authorization": f"Bearer {person_b_jwt}"},
        timeout=10,
    )
    assert read_resp.status_code == 200, (
        f"Could not read person B's profile after person A's PATCH: "
        f"{read_resp.status_code} {read_resp.text}"
    )
    assert read_resp.json()["bio"] == original_bio
