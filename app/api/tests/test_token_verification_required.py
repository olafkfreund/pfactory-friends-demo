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


def test_jwk_error_is_a_401_not_a_500(monkeypatch):
    """A JWKS whose key type cannot serve the token's `alg` must give 401.

    ``JWKError`` is NOT a subclass of ``JWTError`` -- verified directly:

        issubclass(JWKError, JWTError)  -> False
        issubclass(JWKError, JOSEError) -> True

    so a handler catching only ``JWTError`` lets it through as a 500. Found on
    the deployed service, where a forged token produced "JWKError: Incorrect
    key type. Expected: 'oct', Received: RSA".

    The input matters. An ``HS256`` token now hits "The specified alg value is
    not allowed" (a plain ``JWTError``, already caught) because this code
    restricts the JWKS path to RS256 -- so testing with one would pass whether
    or not the fix is present. Measured: with ``except JWTError`` restored, an
    HS256 token still gave 401 and the test was vacuous. An ``RS256`` token
    against a non-RSA JWKS is what reaches ``JWKError``, and is realistic: a
    realm serving EC keys, or a key rotated to a different type.
    """

    class _FakeResponse:
        @staticmethod
        def json() -> dict:
            # kty the RS256 path cannot use.
            return {"keys": [{"kty": "oct", "kid": "k1", "k": "AAAA"}]}

    import httpx

    monkeypatch.setattr(httpx, "get", lambda url, timeout=10: _FakeResponse())  # noqa: ARG005
    monkeypatch.setenv("OIDC_JWKS_URI", "https://example.invalid/certs")
    monkeypatch.delenv("ALLOW_UNVERIFIED_TOKENS", raising=False)
    monkeypatch.delenv("OIDC_ISSUER", raising=False)

    def seg(d: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    rs256_token = (
        f"{seg({'alg': 'RS256', 'typ': 'JWT', 'kid': 'k1'})}."
        f"{seg({'sub': 'attacker'})}.not-a-signature"
    )

    with pytest.raises(HTTPException) as exc:
        _decode_token(rs256_token)

    assert exc.value.status_code == 401, (
        f"expected 401, got {exc.value.status_code}: a token that cannot be "
        "verified is an unauthorised client, not a server fault"
    )


def test_jwks_path_offers_only_rs256(monkeypatch):
    """The JWKS path must pass RS256 alone to the decoder.

    A JWKS publishes RSA *public* keys. Offering HS256 alongside RS256 is
    algorithm confusion: it invites a caller to sign a token using that public
    key as a shared HMAC secret.

    This asserts on the ``algorithms`` argument rather than on a status code,
    and that is deliberate. A behavioural test here is VACUOUS: with both
    algorithms allowed, python-jose raises ``JWKError``, which this module now
    converts to 401 -- so the response is 401 whether the restriction is
    present or not. Measured: re-adding "HS256" left all six tests green. The
    decision being made is which algorithms are offered, so that is what is
    checked.
    """

    class _FakeResponse:
        @staticmethod
        def json() -> dict:
            return {"keys": [{"kty": "RSA", "kid": "k1", "n": "abc", "e": "AQAB"}]}

    import httpx
    from jose import jwt as jose_jwt

    seen: dict = {}

    def _spy(token, key, algorithms=None, **kwargs):  # noqa: ARG001
        seen["algorithms"] = algorithms
        return {"sub": "whoever"}

    monkeypatch.setattr(httpx, "get", lambda url, timeout=10: _FakeResponse())  # noqa: ARG005
    monkeypatch.setattr(jose_jwt, "decode", _spy)
    monkeypatch.setenv("OIDC_JWKS_URI", "https://example.invalid/certs")
    monkeypatch.delenv("ALLOW_UNVERIFIED_TOKENS", raising=False)

    _decode_token(_unsigned_token())

    assert seen["algorithms"] == ["RS256"], (
        f"JWKS path offered {seen['algorithms']}; an HMAC algorithm against an "
        "RSA JWKS is algorithm confusion"
    )


def test_dev_path_still_offers_hs256(monkeypatch):
    """The explicit dev path keeps HS256, so the restriction is scoped.

    Without this, narrowing the JWKS path could be "fixed" by narrowing
    everywhere, silently breaking local development.
    """
    from jose import jwt as jose_jwt

    seen: dict = {}

    def _spy(token, key, algorithms=None, **kwargs):  # noqa: ARG001
        seen["algorithms"] = algorithms
        return {"sub": "dev"}

    monkeypatch.setattr(jose_jwt, "decode", _spy)
    monkeypatch.delenv("OIDC_JWKS_URI", raising=False)
    monkeypatch.setenv("ALLOW_UNVERIFIED_TOKENS", "1")

    _decode_token(_unsigned_token())
    assert "HS256" in seen["algorithms"]
