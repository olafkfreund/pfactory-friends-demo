"""An unconfigured deployment must refuse, never accept (demo#127).

The first implementation treated a missing ``OIDC_JWKS_URI`` as permission to
decode with ``verify_signature: False``. Every endpoint correctly compares the
authenticated caller to the resource owner -- but with verification off the
caller is attacker-chosen, so all of those checks are defeated from
underneath. The only deployment manifest in the repo had no ``env`` block, so
that path was the shipped configuration.

These tests call ``_decode_token`` directly rather than through the app,
because the build's own suite overrides ``require_auth`` wholesale and so never
executes this function at all -- which is exactly why the defect survived 177
passing tests.
"""

import base64
import json

import pytest
from fastapi import HTTPException

from app.main import _decode_token


def _unsigned_token(sub: str = "attacker") -> str:
    """A token with a valid shape and a garbage signature."""
    def seg(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    return f"{seg({'alg': 'HS256', 'typ': 'JWT'})}.{seg({'sub': sub})}.not-a-signature"


def test_missing_jwks_uri_refuses(monkeypatch):
    """With OIDC_JWKS_URI unset and no explicit opt-in, the request is refused."""
    monkeypatch.delenv("OIDC_JWKS_URI", raising=False)
    monkeypatch.delenv("ALLOW_UNVERIFIED_TOKENS", raising=False)

    with pytest.raises(HTTPException) as exc:
        _decode_token(_unsigned_token())

    # 500, not 401: this is a deployment fault, not a bad client.
    assert exc.value.status_code == 500
    assert "OIDC_JWKS_URI" in str(exc.value.detail)


def test_missing_jwks_uri_does_not_return_a_subject(monkeypatch):
    """The failure mode that matters: it must not hand back an identity.

    A regression here would not necessarily restore the 500 -- it would return
    a payload. Asserting on the exception alone would miss that, so this
    asserts no claims are produced for an unsigned token.
    """
    monkeypatch.delenv("OIDC_JWKS_URI", raising=False)
    monkeypatch.delenv("ALLOW_UNVERIFIED_TOKENS", raising=False)

    result = None
    try:
        result = _decode_token(_unsigned_token("victim"))
    except HTTPException:
        pass
    assert result is None, (
        "an unsigned token yielded claims with verification unconfigured; "
        "any caller could then act as any user"
    )


def test_explicit_opt_in_still_allows_local_development(monkeypatch):
    """The dev path remains reachable, but only when asked for by name."""
    monkeypatch.delenv("OIDC_JWKS_URI", raising=False)
    monkeypatch.setenv("ALLOW_UNVERIFIED_TOKENS", "1")
    monkeypatch.setenv("_DEV_JWKS_SECRET", "")

    payload = _decode_token(_unsigned_token("dev-user"))
    assert payload["sub"] == "dev-user"


def test_opt_in_must_be_exactly_one(monkeypatch):
    """A truthy-looking value is not an opt-in; only "1" is.

    Guards against the guard being softened to a truthiness check, which would
    make ALLOW_UNVERIFIED_TOKENS=false enable the unverified path.
    """
    monkeypatch.delenv("OIDC_JWKS_URI", raising=False)
    monkeypatch.setenv("ALLOW_UNVERIFIED_TOKENS", "false")

    with pytest.raises(HTTPException) as exc:
        _decode_token(_unsigned_token())
    assert exc.value.status_code == 500
