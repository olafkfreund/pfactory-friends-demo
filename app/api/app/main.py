"""MyFriends API — walking skeleton (plan step 1).

Only two endpoints exist here on purpose: healthz for the deploy probe, and a
placeholder profile so app/web has something real to call. Persistence
(plan step 2) and auth (plan step 3) are deliberately not stubbed — adding
them later means writing the real thing once, not un-stubbing a fake one.
"""

from fastapi import FastAPI

app = FastAPI(title="MyFriends API")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/profiles/me")
def profile_me() -> dict[str, str]:
    # ponytail: hardcoded placeholder, no database yet.
    # Replaced by a real lookup against Postgres in plan step 2
    # (spec/2026-09-30-87-myfriends-web.md, "Schema and persistence").
    return {
        "id": "placeholder",
        "display_name": "Demo Friend",
        "bio": "This profile is a placeholder until step 2 adds persistence.",
    }
