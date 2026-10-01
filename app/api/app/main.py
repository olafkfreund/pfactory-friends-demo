"""MyFriends API.

Auth contract
-------------
Every endpoint except ``GET /healthz`` requires a valid Bearer JWT.
``require_auth`` is the **single source** of the caller's identity: it
validates the token and returns the subject claim (``sub``).  No endpoint
may obtain the acting identity by any other route — not from the request
body, not from the URL, not from a header.  This closes the defect in the
previous implementation where ``dependencies=[Depends(require_auth)]``
discarded the return value and endpoints read ``body.id``, ``sender_id``,
etc. from untrusted input.

Authorisation contract
----------------------
Every state-changing endpoint compares the authenticated ``caller_id``
against the resource owner embedded in the path or body, and returns 403
(never 404) when they differ.  The distinction matters: a 404 would reveal
whether the resource exists to the wrong caller.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, field_validator

from app import store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — schema bootstrap
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI):
    store.bootstrap_schema()
    yield


# ---------------------------------------------------------------------------
# Authentication dependency
# ---------------------------------------------------------------------------

def _decode_token(token: str) -> dict:
    """Decode and verify a JWT, returning its claims.

    Verification requires ``OIDC_JWKS_URI``.  Its **absence is an error**, not
    a mode: if it is unset the request is refused.  Skipping signature
    verification has to be asked for explicitly, by setting
    ``ALLOW_UNVERIFIED_TOKENS=1``, and that is only for local development.

    This is deliberately the opposite of the first implementation, which
    treated a missing ``OIDC_JWKS_URI`` as permission to decode with
    ``verify_signature: False`` (demo#127).  An unconfigured deployment then
    accepted any token bearing any ``sub``, which defeats every ownership
    check in this module from underneath -- the endpoints correctly compare
    the caller to the resource owner, but the caller became attacker-chosen.
    The only deployment manifest in the repository had no ``env`` block at
    all, so the fail-open path was the shipped configuration rather than a
    hypothetical one.

    ``_database_url`` in ``store.py`` already treats its missing variable as
    an error.  Authentication now behaves the same way: unconfigured means
    refuse, never means allow.
    """
    # JOSEError, not JWTError. JWKError is NOT a subclass of JWTError (checked:
    # both derive from JOSEError independently), so a token whose `alg` does not
    # match the JWKS key type raised JWKError straight past the handler and
    # became a 500. Measured against the deployed service with a forged
    # `alg: HS256` token: "JWKError: Incorrect key type. Expected: 'oct',
    # Received: RSA". A rejection must read as a rejection.
    from jose import jwt as jose_jwt
    from jose.exceptions import JOSEError

    jwks_uri = os.environ.get("OIDC_JWKS_URI")
    audience = os.environ.get("OIDC_AUDIENCE", "myfriends-api")
    issuer = os.environ.get("OIDC_ISSUER")
    allow_unverified = os.environ.get("ALLOW_UNVERIFIED_TOKENS") == "1"

    if not jwks_uri and not allow_unverified:
        logger.error(
            "OIDC_JWKS_URI is not set and ALLOW_UNVERIFIED_TOKENS is not '1'; "
            "refusing the request. Signature verification cannot be skipped "
            "implicitly (demo#127)."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Token verification is not configured: OIDC_JWKS_URI is unset. "
                "This is a deployment error, not a client error."
            ),
        )

    try:
        if jwks_uri:
            import httpx
            jwks = httpx.get(jwks_uri, timeout=10).json()
            options: dict = {}
            # RS256 only when verifying against a JWKS. Accepting HS256 here
            # as well is algorithm confusion: the JWKS publishes RSA PUBLIC
            # keys, and an HMAC algorithm invites a caller to sign a token
            # with that public key as the shared secret. python-jose happens
            # to raise JWKError rather than verify in that case, so this path
            # was not exploitable -- but the allowance is wrong on its own
            # terms and nothing should depend on that library detail.
            algorithms = ["RS256"]
        else:
            # Only reachable with ALLOW_UNVERIFIED_TOKENS=1 set deliberately.
            logger.warning(
                "ALLOW_UNVERIFIED_TOKENS=1: decoding without signature "
                "verification. Local development only -- any token bearing "
                "any 'sub' will be accepted."
            )
            jwks = os.environ.get("_DEV_JWKS_SECRET", "")
            options = {"verify_signature": False}
            algorithms = ["RS256", "HS256"]

        payload: dict = jose_jwt.decode(
            token,
            jwks,
            algorithms=algorithms,
            audience=audience,
            issuer=issuer,
            options=options,
        )
        return payload
    except JOSEError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc


async def require_auth(
    request: Request,
    authorization: Annotated[str, Header(alias="authorization")] = "",
) -> str:
    """Validate the Bearer JWT and return the caller's subject ID.

    This is the **only** permitted source of the caller's identity.  All
    endpoints that change state receive ``caller_id`` via this dependency.

    The decoded token payload is stored on ``request.state.token_payload``
    so that downstream dependencies (e.g. ``require_moderator``) can inspect
    claims without decoding the token a second time.
    """
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is missing or is not a Bearer token.",
        )
    token = authorization[7:]  # strip "Bearer "
    payload = _decode_token(token)
    caller_id: str | None = payload.get("sub")
    if not caller_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing the 'sub' claim.",
        )
    request.state.token_payload = payload
    return caller_id


async def require_moderator(
    request: Request,
    caller_id: Annotated[str, Depends(require_auth)],
) -> str:
    """Extend ``require_auth`` by also asserting the moderator role.

    The moderator role is carried in the ``realm_access.roles`` claim
    (standard Keycloak placement) as ``myfriends-moderator``.
    """
    payload: dict = getattr(request.state, "token_payload", {})
    roles: list[str] = (payload.get("realm_access") or {}).get("roles", [])
    if "myfriends-moderator" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The moderator role is required for this operation.",
        )
    return caller_id


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ProfileCreate(BaseModel):
    display_name: str
    bio: str = ""
    age: int
    interests: list[str] = []

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("display_name must not be blank or whitespace.")
        if len(v) > store.MAX_DISPLAY_NAME_LENGTH:
            raise ValueError(
                f"display_name must not exceed {store.MAX_DISPLAY_NAME_LENGTH} characters."
            )
        return v

    @field_validator("age")
    @classmethod
    def age_in_range(cls, v: int) -> int:
        if v < 13 or v > 120:
            raise ValueError("age must be between 13 and 120.")
        return v

    @field_validator("interests")
    @classmethod
    def interests_within_limit(cls, v: list[str]) -> list[str]:
        if len(v) > store.MAX_INTERESTS:
            raise ValueError(f"interests must not exceed {store.MAX_INTERESTS} items.")
        return v


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    bio: str | None = None
    interests: list[str] | None = None

    @field_validator("display_name")
    @classmethod
    def display_name_not_blank(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not v.strip():
            raise ValueError("display_name must not be blank or whitespace.")
        if len(v) > store.MAX_DISPLAY_NAME_LENGTH:
            raise ValueError(
                f"display_name must not exceed {store.MAX_DISPLAY_NAME_LENGTH} characters."
            )
        return v

    @field_validator("interests")
    @classmethod
    def interests_within_limit(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) > store.MAX_INTERESTS:
            raise ValueError(f"interests must not exceed {store.MAX_INTERESTS} items.")
        return v


class AvailabilityUpdate(BaseModel):
    is_open: bool


class ConnectionRequest(BaseModel):
    target_id: str


class MessageSend(BaseModel):
    body: str


class BlockCreate(BaseModel):
    blocked_id: str


class ReportCreate(BaseModel):
    reported_id: str
    reason: str
    detail: str = ""

    @field_validator("reason")
    @classmethod
    def reason_is_valid(cls, v: str) -> str:
        if v not in store.VALID_REPORT_REASONS:
            raise ValueError(
                f"reason must be one of: {', '.join(sorted(store.VALID_REPORT_REASONS))}"
            )
        return v


class ReportResolve(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def status_is_valid(cls, v: str) -> str:
        valid = store.VALID_REPORT_STATUSES - {"open"}
        if v not in valid:
            raise ValueError(f"status must be one of: {', '.join(sorted(valid))}")
        return v


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(title="MyFriends API", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe — no auth required."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

@app.post("/profiles", status_code=status.HTTP_201_CREATED)
def create_profile(
    body: ProfileCreate,
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    """Create a profile owned by the authenticated caller.

    The profile ID is always the caller's own subject ID; the caller cannot
    create a profile on behalf of anyone else.
    """
    existing = store.get_profile(caller_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A profile already exists for this account.",
        )
    return store.create_profile(
        profile_id=caller_id,
        display_name=body.display_name,
        bio=body.bio,
        age=body.age,
        interests=body.interests,
    )


@app.get("/profiles/me")
def get_my_profile(
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    profile = store.get_profile(caller_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found for this account.",
        )
    return profile


@app.patch("/profiles/me")
def update_my_profile(
    body: ProfileUpdate,
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    result = store.update_profile(
        caller_id,
        display_name=body.display_name,
        bio=body.bio,
        interests=body.interests,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found for this account.",
        )
    return result


@app.post("/profiles/me/age-assurance")
def record_age_assurance(
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    """Mark the caller's own age assurance as passed.

    Only the authenticated profile owner may record their own age assurance.
    No caller can grant age assurance on behalf of another person.
    """
    result = store.record_age_assurance(caller_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found for this account.",
        )
    return result


@app.patch("/profiles/me/availability")
def set_availability(
    body: AvailabilityUpdate,
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    result = store.set_availability(caller_id, body.is_open)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found for this account.",
        )
    return result


@app.delete("/profiles/me", status_code=status.HTTP_200_OK)
def delete_my_account(
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    """Delete the caller's own account.

    The caller cannot delete anyone else's account by naming its ID.
    Returns a summary of what was removed and what was retained.
    """
    profile = store.get_profile(caller_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found for this account.",
        )
    return store.delete_profile(caller_id)


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

@app.get("/discovery")
def discover(
    caller_id: Annotated[str, Depends(require_auth)],
) -> list[dict]:
    """Return open, eligible profiles visible to the caller.

    Age-bracket isolation is enforced: adults never appear for minors and
    vice versa.  Only callers whose own age assurance has been recorded are
    eligible to search.
    """
    caller = store.get_profile(caller_id)
    if caller is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found for this account.",
        )
    if not caller["age_assurance_passed"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Age assurance must be recorded before using discovery.",
        )
    return store.discover(caller_id, caller["age"])


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

@app.post("/connections", status_code=status.HTTP_201_CREATED)
def send_connection_request(
    body: ConnectionRequest,
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    """Send a connection request from the authenticated caller to ``target_id``."""
    if caller_id == body.target_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot send a connection request to yourself.",
        )
    if not store.may_contact(caller_id, body.target_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A block relationship prevents this connection request.",
        )
    target = store.get_profile(body.target_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target profile not found.",
        )
    if store.count_requests_today(caller_id) >= store.MAX_REQUESTS_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"You may send at most {store.MAX_REQUESTS_PER_DAY} requests per 24 hours.",
        )
    return store.create_connection_request(caller_id, body.target_id)


@app.get("/connections")
def list_connections(
    caller_id: Annotated[str, Depends(require_auth)],
) -> list[dict]:
    return store.list_connections(caller_id)


@app.post("/connections/{connection_id}/accept")
def accept_connection(
    connection_id: str,
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    """Accept a pending connection request addressed to the caller."""
    conn = store.get_connection(connection_id)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    if conn["target_id"] != caller_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the request recipient may accept it.",
        )
    if conn["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connection is already '{conn['status']}'.",
        )
    result = store.update_connection_status(connection_id, "accepted")
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    return result


@app.post("/connections/{connection_id}/decline")
def decline_connection(
    connection_id: str,
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    """Decline a pending connection request addressed to the caller."""
    conn = store.get_connection(connection_id)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    if conn["target_id"] != caller_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the request recipient may decline it.",
        )
    if conn["status"] != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connection is already '{conn['status']}'.",
        )
    result = store.update_connection_status(connection_id, "declined")
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    return result


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@app.get("/connections/{connection_id}/messages")
def list_messages(
    connection_id: str,
    caller_id: Annotated[str, Depends(require_auth)],
) -> list[dict]:
    """Return messages for a connection the caller is a party to."""
    conn = store.get_connection(connection_id)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    if caller_id not in (conn["requester_id"], conn["target_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a party to this connection.",
        )
    return store.list_messages(connection_id)


@app.post("/connections/{connection_id}/messages", status_code=status.HTTP_201_CREATED)
def send_message(
    connection_id: str,
    body: MessageSend,
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    """Send a message on an accepted connection the caller is a party to."""
    conn = store.get_connection(connection_id)
    if conn is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found.")
    if caller_id not in (conn["requester_id"], conn["target_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a party to this connection.",
        )
    if conn["status"] != "accepted":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Messages can only be sent on accepted connections.",
        )
    other_id = conn["target_id"] if caller_id == conn["requester_id"] else conn["requester_id"]
    if not store.may_contact(caller_id, other_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A block relationship prevents sending this message.",
        )
    return store.send_message(connection_id, caller_id, body.body)


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

@app.post("/blocks", status_code=status.HTTP_201_CREATED)
def create_block(
    body: BlockCreate,
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    """Block another person on behalf of the authenticated caller."""
    if caller_id == body.blocked_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot block yourself.",
        )
    return store.create_block(caller_id, body.blocked_id)


@app.get("/blocks")
def list_blocks(
    caller_id: Annotated[str, Depends(require_auth)],
) -> list[dict]:
    return store.list_blocks(caller_id)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

@app.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report(
    body: ReportCreate,
    caller_id: Annotated[str, Depends(require_auth)],
) -> dict:
    """File a report from the authenticated caller."""
    if caller_id == body.reported_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="You cannot report yourself.",
        )
    return store.create_report(caller_id, body.reported_id, body.reason, body.detail)


@app.get("/reports", dependencies=[Depends(require_moderator)])
def list_reports(
    status_filter: str | None = None,
) -> list[dict]:
    """List reports — moderator role required."""
    if status_filter and status_filter not in store.VALID_REPORT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status_filter must be one of: {', '.join(sorted(store.VALID_REPORT_STATUSES))}",
        )
    return store.list_reports(status_filter)


@app.post("/reports/{report_id}/resolve")
def resolve_report(
    report_id: str,
    body: ReportResolve,
    caller_id: Annotated[str, Depends(require_moderator)],
) -> dict:
    """Resolve a report — moderator role required.

    A caller who is authenticated but not a moderator is rejected with 403.
    In particular, no non-moderator caller can impose a contact removal on
    another person.
    """
    result = store.resolve_report(report_id, caller_id, body.status)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")
    return result
