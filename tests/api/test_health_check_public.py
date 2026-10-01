# AC#8: the health check endpoint is exempt from the authentication requirement.
# "An unauthenticated call to any endpoint other than the health check is
# rejected before any authorisation or business logic runs."
# This test verifies the positive side of that exemption: GET /healthz returns
# 200 even when no Authorization header is present.

import os

import requests


def test_healthz_without_auth_header_returns_200():
    """GET /healthz with no Authorization header must return HTTP 200."""
    base_url = os.environ["TFACTORY_TARGET_URL"]
    resp = requests.get(f"{base_url}/healthz", timeout=10)
    assert resp.status_code == 200


def test_healthz_without_auth_header_returns_ok_status():
    """GET /healthz response body must contain status 'ok'."""
    base_url = os.environ["TFACTORY_TARGET_URL"]
    resp = requests.get(f"{base_url}/healthz", timeout=10)
    assert resp.json().get("status") == "ok"
