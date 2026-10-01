# AC#7: Resolving a report requires the moderation role; a caller who is authenticated
# but not a moderator is rejected with 403, and in particular cannot impose a contact
# removal on another person.
#
# Subtask: resolve-report-non-mod-forbidden-api
# Target:  app/api/app/main.py::ReportResolve
# Criterion (as written): Verify that PATCH /reports/{id}/resolve returns 403 when
# the authenticated caller has no moderator role.
#
# NOTE — HTTP method discrepancy: the subtask criterion specifies "PATCH
# /reports/{id}/resolve", but the implementation registers the route at
# POST /reports/{report_id}/resolve (see app/api/app/main.py line 648:
# `@app.post("/reports/{report_id}/resolve")`).
# The first test asserts the criterion exactly as written (PATCH → 403); it will
# fail with a 404 or 405 if that method is not registered, surfacing the gap.
# The remaining tests verify the authorisation control on the POST route that the
# implementation actually provides, proving the spirit of AC#7 holds.
#
# Authorisation enforcement:
# The endpoint uses `caller_id: Annotated[str, Depends(require_moderator)]`.
# FastAPI resolves this dependency before the handler body runs, so 403 is
# returned before any report lookup — a fake report_id suffices.

from __future__ import annotations

import base64
import json
import os
import time
import uuid

import requests


# ---------------------------------------------------------------------------
# JWT helper
# ---------------------------------------------------------------------------

def _make_jwt(sub, roles=None, include_realm_access=True, aud="myfriends-api"):
    """Return a compact JWT accepted when ALLOW_UNVERIFIED_TOKENS=1.

    ``roles`` is placed in ``realm_access.roles`` (standard Keycloak placement).
    Pass ``include_realm_access=False`` to omit the claim entirely.
    Signature is a placeholder — verification is skipped in dev mode.
    """
    def _b64u(obj):
        raw = json.dumps(obj, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    payload = {
        "sub": sub,
        "aud": aud,
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    if include_realm_access:
        payload["realm_access"] = {"roles": roles if roles is not None else []}

    header = _b64u({"alg": "HS256", "typ": "JWT"})
    body_enc = _b64u(payload)
    return f"{header}.{body_enc}.placeholder"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_resolve_report_patch_non_moderator_returns_403():
    """AC#7 criterion (as written): PATCH /reports/{id}/resolve returns 403 for
    an authenticated caller who has no moderator role.

    The criterion specifies the PATCH method.  If the route is not registered at
    PATCH the response will be 404 or 405 — not 403 — and this test will fail,
    surfacing the method discrepancy between the criterion and the implementation.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]
    user_id = f"non-mod-patch-{uuid.uuid4().hex[:12]}"
    # Authenticated token with an explicit empty roles list — no myfriends-moderator.
    token = _make_jwt(user_id, roles=[], include_realm_access=True)

    report_id = str(uuid.uuid4())
    resp = requests.patch(
        f"{base_url}/reports/{report_id}/resolve",
        json={"status": "dismissed"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    assert resp.status_code == 403


def test_resolve_report_post_non_moderator_empty_roles_returns_403():
    """AC#7: POST /reports/{id}/resolve returns 403 when the caller's token has
    realm_access.roles present but empty (no myfriends-moderator role).
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]
    user_id = f"non-mod-empty-{uuid.uuid4().hex[:12]}"
    token = _make_jwt(user_id, roles=[], include_realm_access=True)

    # A fake report_id is sufficient: require_moderator fires before any DB lookup.
    report_id = str(uuid.uuid4())
    resp = requests.post(
        f"{base_url}/reports/{report_id}/resolve",
        json={"status": "dismissed"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    assert resp.status_code == 403


def test_resolve_report_post_non_moderator_no_realm_access_returns_403():
    """AC#7: POST /reports/{id}/resolve returns 403 when the caller's token has
    no realm_access claim at all.

    require_moderator guards against the absent claim via
    `(payload.get("realm_access") or {}).get("roles", [])`.
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]
    user_id = f"non-mod-noralm-{uuid.uuid4().hex[:12]}"
    # Token with no realm_access key at all.
    token = _make_jwt(user_id, include_realm_access=False)

    report_id = str(uuid.uuid4())
    resp = requests.post(
        f"{base_url}/reports/{report_id}/resolve",
        json={"status": "dismissed"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    assert resp.status_code == 403


def test_resolve_report_post_non_moderator_other_roles_returns_403():
    """AC#7: POST /reports/{id}/resolve returns 403 when the caller holds roles
    other than myfriends-moderator (e.g. admin, user, editor).
    """
    base_url = os.environ["TFACTORY_TARGET_URL"]
    user_id = f"non-mod-otherrole-{uuid.uuid4().hex[:12]}"
    token = _make_jwt(user_id, roles=["admin", "user", "editor"], include_realm_access=True)

    report_id = str(uuid.uuid4())
    resp = requests.post(
        f"{base_url}/reports/{report_id}/resolve",
        json={"status": "actioned"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )

    assert resp.status_code == 403
