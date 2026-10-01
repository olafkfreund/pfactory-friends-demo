# AC#6: POST /profiles with invalid display_name is rejected and no profile is written.
#
# Spec (verbatim): "Saving a profile whose display name is blank, or is only
# whitespace, or is longer than the documented maximum, is rejected with the
# documented reason and no profile is written."
#
# store.MAX_DISPLAY_NAME_LENGTH == 100
# All three cases must return HTTP 422 Unprocessable Entity.

from __future__ import annotations

import base64
import json
import os
import uuid

import pytest
import requests


# ---------------------------------------------------------------------------
# Helper — build a minimal JWT usable with ALLOW_UNVERIFIED_TOKENS=1
# ---------------------------------------------------------------------------

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_test_token(sub: str = "test-display-name-ac6") -> str:
    """Return a minimal JWT accepted when ALLOW_UNVERIFIED_TOKENS=1.

    The server decodes with ``verify_signature=False`` in that mode, so the
    signature field is ignored — any non-empty string keeps the three-part
    structure intact.
    """
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(
        json.dumps({"sub": sub, "aud": "myfriends-api"}).encode()
    )
    return f"{header}.{payload}.fakesig"


# ---------------------------------------------------------------------------
# Parametrised: all invalid display_name values must return 422
# ---------------------------------------------------------------------------

INVALID_DISPLAY_NAMES = [
    ("empty_string",      ""),
    ("single_space",      " "),
    ("multiple_spaces",   "   "),
    ("tab_only",          "\t"),
    ("newline_only",      "\n"),
    ("mixed_whitespace",  " \t\n "),
    ("exceeds_100_chars", "x" * 101),
]


@pytest.mark.parametrize(
    "display_name",
    [v for _, v in INVALID_DISPLAY_NAMES],
    ids=[k for k, _ in INVALID_DISPLAY_NAMES],
)
def test_create_profile_invalid_display_name_returns_422(display_name: str) -> None:
    """POST /profiles with an invalid display_name must return 422."""
    base_url = os.environ["TFACTORY_TARGET_URL"]
    token = _make_test_token(sub=f"ac6-user-{uuid.uuid4()}")

    resp = requests.post(
        f"{base_url}/profiles",
        json={
            "display_name": display_name,
            "bio": "test bio",
            "age": 25,
            "interests": [],
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    assert resp.status_code == 422, (
        f"Expected 422 for display_name={display_name!r}, got {resp.status_code}. "
        f"Body: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Boundary: display_name at the documented maximum (100) must be accepted
# ---------------------------------------------------------------------------

def test_create_profile_display_name_at_max_length_succeeds() -> None:
    """POST /profiles with display_name of exactly 100 characters must not return 422."""
    base_url = os.environ["TFACTORY_TARGET_URL"]
    unique_sub = f"ac6-max-{uuid.uuid4()}"
    token = _make_test_token(sub=unique_sub)

    resp = requests.post(
        f"{base_url}/profiles",
        json={
            "display_name": "a" * 100,
            "bio": "",
            "age": 20,
            "interests": [],
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    # 422 must not be returned for an exactly-100-character name.
    # (201 Created or 409 Conflict if the profile already exists are both fine.)
    assert resp.status_code != 422, (
        f"display_name of 100 characters should not be rejected with 422. "
        f"Got {resp.status_code}. Body: {resp.text}"
    )
