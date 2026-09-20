"""Authentication: Google Sign-In → app JWT → current_user dependency.

Flow: frontend gets a Google ID token (GIS) → POST /api/auth/google → we verify it with
Google, upsert the user, seed their default studio, and return an app JWT. Every protected
route depends on `current_user`, which decodes that JWT.
"""
from __future__ import annotations

import time

import jwt
from fastapi import Depends, Header, HTTPException

from . import config, database, niches


def _derive_handle(email: str) -> str:
    local = email.split("@", 1)[0]
    return "@" + "".join(c for c in local if c.isalnum() or c in "._")[:28]


def verify_google_token(credential: str) -> dict:
    """Verify a Google ID token; return {sub, email, name, picture}."""
    if not config.GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google sign-in is not configured on the server")
    from google.auth.transport import requests as g_requests
    from google.oauth2 import id_token

    try:
        info = id_token.verify_oauth2_token(
            credential, g_requests.Request(), config.GOOGLE_CLIENT_ID
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(401, f"invalid Google token: {exc}") from exc
    if not info.get("email_verified"):
        raise HTTPException(401, "Google email not verified")
    return {
        "sub": info["sub"],
        "email": info["email"],
        "name": info.get("name", ""),
        "picture": info.get("picture", ""),
    }


def login_or_create(userinfo: dict, ref_code: str = "") -> tuple[dict, str]:
    """Upsert the user, seed their studio on first login, return (user, jwt)."""
    from . import billing

    email = userinfo["email"].lower()
    user = database.upsert_user(
        google_sub=userinfo.get("sub", ""),
        email=email,
        name=userinfo.get("name", ""),
        picture=userinfo.get("picture", ""),
    )
    if database.get_account(user["id"]) is None:  # first login → new user
        acct = niches.default_account(_derive_handle(email))
        database.upsert_account(user["id"], **acct)
        # The owner inherits any pre-existing (migrated) posts, once.
        if config.OWNER_EMAIL and email == config.OWNER_EMAIL:
            database.claim_orphan_posts(user["id"])
        if ref_code:
            try:
                billing.apply_referral(user, ref_code)
            except Exception as exc:  # noqa: BLE001
                print(f"[referral] apply failed: {exc}")
    return user, issue_jwt(user)


def issue_jwt(user: dict) -> str:
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "iat": int(time.time()),
        "exp": int(time.time()) + config.JWT_TTL_SECONDS,
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def issue_oauth_state(user_id: str) -> str:
    """A short-lived signed token round-tripped through a third-party OAuth redirect."""
    payload = {"sub": str(user_id), "purpose": "ig_oauth",
               "iat": int(time.time()), "exp": int(time.time()) + 600}
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def verify_oauth_state(token: str) -> str:
    """Return the user id embedded in a valid ig_oauth state token, else raise."""
    payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
    if payload.get("purpose") != "ig_oauth":
        raise jwt.InvalidTokenError("bad state purpose")
    return payload["sub"]


def current_user(authorization: str = Header(default="")) -> dict:
    """FastAPI dependency: resolve the signed-in user from the Bearer JWT.

    No DB round-trip — the id + email in the signed token are sufficient for every route.
    (Full profile/existence is re-checked on /api/auth/me at app load.)
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(401, f"invalid token: {exc}") from exc
    return {"id": payload["sub"], "email": payload.get("email", "")}
