# AC#8: An unauthenticated call to any endpoint other than the health check is
# rejected before any authorisation or business logic runs.
#
# Rationale: require_auth in app/api/app/main.py raises HTTP 401 immediately
# when the Authorization header is absent or is not a Bearer token.  These
# tests drive real HTTP calls against the running app (TFACTORY_TARGET_URL) to
# confirm that every state-changing endpoint honours that contract, and that
# /healthz remains publicly accessible.
#
# Note: path-parametrised endpoints (e.g. /connections/{id}/accept) use a
# dummy UUID.  Auth is checked before the path parameter is resolved against
# any store, so a 401 must be returned even for non-existent resource IDs.

import os

import pytest
import requests

DUMMY_ID = "00000000-0000-0000-0000-000000000000"

# State-changing endpoints that MUST require authentication.
# Each entry is (method, path_template).
STATE_CHANGING_ENDPOINTS = [
    ("POST",   "/profiles"),
    ("PATCH",  "/profiles/me"),
    ("POST",   "/profiles/me/age-assurance"),
    ("PATCH",  "/profiles/me/availability"),
    ("DELETE", "/profiles/me"),
    ("POST",   "/connections"),
    ("POST",   f"/connections/{DUMMY_ID}/accept"),
    ("POST",   f"/connections/{DUMMY_ID}/decline"),
    ("POST",   f"/connections/{DUMMY_ID}/messages"),
    ("POST",   "/blocks"),
    ("POST",   "/reports"),
    ("POST",   f"/reports/{DUMMY_ID}/resolve"),
]

# Read-only endpoints that are still guarded by require_auth.
READ_ONLY_AUTHENTICATED_ENDPOINTS = [
    ("GET",  "/profiles/me"),
    ("GET",  "/discovery"),
    ("GET",  "/connections"),
    ("GET",  f"/connections/{DUMMY_ID}/messages"),
    ("GET",  "/blocks"),
    ("GET",  "/reports"),
]


@pytest.mark.parametrize(
    "method,path",
    STATE_CHANGING_ENDPOINTS,
    ids=[f"{m}_{p.replace('/', '_').strip('_')}" for m, p in STATE_CHANGING_ENDPOINTS],
)
def test_state_changing_endpoint_returns_401_without_auth(method: str, path: str) -> None:
    """AC#8: state-changing endpoint returns 401 when Authorization header is absent."""
    base_url = os.environ["TFACTORY_TARGET_URL"]
    resp = requests.request(method, f"{base_url}{path}", timeout=10)
    assert resp.status_code == 401, (
        f"{method} {path} returned {resp.status_code}, expected 401. "
        f"Response body: {resp.text!r}"
    )


@pytest.mark.parametrize(
    "method,path",
    READ_ONLY_AUTHENTICATED_ENDPOINTS,
    ids=[f"{m}_{p.replace('/', '_').strip('_')}" for m, p in READ_ONLY_AUTHENTICATED_ENDPOINTS],
)
def test_read_only_authenticated_endpoint_returns_401_without_auth(method: str, path: str) -> None:
    """AC#8: read-only authenticated endpoints also return 401 when Authorization header is absent."""
    base_url = os.environ["TFACTORY_TARGET_URL"]
    resp = requests.request(method, f"{base_url}{path}", timeout=10)
    assert resp.status_code == 401, (
        f"{method} {path} returned {resp.status_code}, expected 401. "
        f"Response body: {resp.text!r}"
    )


def test_healthz_returns_200_without_auth() -> None:
    """AC#8: the health check endpoint /healthz is exempt from the authentication requirement."""
    base_url = os.environ["TFACTORY_TARGET_URL"]
    resp = requests.get(f"{base_url}/healthz", timeout=10)
    assert resp.status_code == 200, (
        f"GET /healthz returned {resp.status_code}, expected 200. "
        f"Response body: {resp.text!r}"
    )


def test_unauthenticated_call_returns_401_not_403() -> None:
    """AC#8: unauthenticated requests must be rejected with 401, not 403 (auth precedes authz)."""
    base_url = os.environ["TFACTORY_TARGET_URL"]
    # Use POST /profiles as a representative state-changing endpoint.
    resp = requests.post(f"{base_url}/profiles", timeout=10)
    assert resp.status_code == 401, (
        f"POST /profiles without auth returned {resp.status_code}; "
        "expected 401 (Unauthorized), not 403 (Forbidden). "
        "Authentication must be checked before authorisation logic runs."
    )


def test_unauthenticated_call_does_not_return_500() -> None:
    """AC#8: absence of Authorization header does not trigger an unhandled server error."""
    base_url = os.environ["TFACTORY_TARGET_URL"]
    resp = requests.post(f"{base_url}/profiles", timeout=10)
    assert resp.status_code != 500, (
        f"POST /profiles without auth returned 500; require_auth should handle "
        "the missing header gracefully and return 401."
    )
