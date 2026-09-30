"""Authentication and authorisation gate for the MyFriends API (C18).

Two concerns live here and are intentionally kept together so there is one
place to audit how callers are admitted and how per-person decisions are made:

1. **Authentication** — ``require_auth`` is a FastAPI dependency used on every
   endpoint that reads or writes a person's data.  It reads the ``X-User-ID``
   header injected by the deployment-layer oauth2-proxy after it validates the
   caller's Keycloak token.  A request that arrives without that header (i.e.
   one that bypassed the proxy, or a raw unauthenticated call) is rejected with
   HTTP 401 before any business logic runs.

2. **Authorisation** — whether a given *authenticated* caller may see, contact
   or message a specific other person is decided exclusively by the
   ``may_contact`` predicate in ``store.py``.  That single predicate is shared
   by discovery, connection requests, and messaging so that no two surfaces can
   give different answers about the same pair of people.  This design is the
   fix for issue #86, where the messaging path and the connection-request path
   previously disagreed about the meaning of "blocked".

   ``require_auth`` is intentionally limited to the authentication concern only.
   Do not add per-person authorisation logic here; route it through
   ``may_contact`` instead so the single-predicate guarantee holds.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, status


def require_auth(x_user_id: str | None = Header(default=None)) -> str:
    """FastAPI dependency — require an authenticated caller (C18).

    Reads the ``X-User-ID`` header that the deployment-layer oauth2-proxy
    injects after validating the caller's Keycloak token.  A missing or blank
    header means the request was not routed through the proxy, which is treated
    as unauthenticated.

    Returns the caller's user ID string on success.

    Raises:
        HTTPException: HTTP 401 with ``detail="unauthenticated"`` when the
            header is absent or blank.
    """
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return x_user_id
