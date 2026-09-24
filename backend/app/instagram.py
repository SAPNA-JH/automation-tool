"""Instagram Content Publishing via the "Instagram API with Instagram Login" flow.

This is the July-2024 direct-login path: a Business/Creator account authorizes the
app WITHOUT a linked Facebook Page. Scopes: instagram_business_basic +
instagram_business_content_publish. Tokens are long-lived (60 days) and refreshable.

Publishing is two steps: create a media container from a PUBLIC media URL (our posts
are already hosted on Cloudinary), then publish the container.

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing/
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from . import config

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH = "https://graph.instagram.com"
SCOPES = "instagram_business_basic,instagram_business_content_publish"


class InstagramError(RuntimeError):
    pass


class RateLimitError(InstagramError):
    """Meta throttled us — NEVER retry these; retrying deepens the block."""


# Meta rate-limit / throttle error codes (app, user, and BUC limits).
_RATE_LIMIT_CODES = {4, 17, 32, 341, 613}


def _base() -> str:
    return f"{GRAPH}/{config.IG_GRAPH_VERSION}"


def _error(resp: httpx.Response) -> tuple[int | None, str]:
    """(error_code, message) from a Graph API error response."""
    msg = resp.text[:200]
    code = None
    try:
        err = resp.json().get("error", {})
        msg = err.get("message") or msg
        code = err.get("code")
    except Exception:  # noqa: BLE001
        pass
    return code, msg


# Highest recent rate-limit usage % per IG account (from Meta's usage headers), so
# the scheduler can cool down BEFORE hitting a hard 429.
_usage: dict[str, float] = {}


def _pct(d: dict) -> float:
    try:
        return max(float(d.get(k, 0)) for k in ("call_count", "total_cputime", "total_time"))
    except Exception:  # noqa: BLE001
        return 0.0


def note_usage(resp: httpx.Response, ig_user_id: str | None = None) -> float:
    """Parse Meta's X-App-Usage / X-Business-Use-Case-Usage headers → highest % used."""
    import json
    top = 0.0
    for hdr in ("x-app-usage", "x-business-use-case-usage"):
        raw = resp.headers.get(hdr)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if not isinstance(data, dict):
            continue
        vals: list[float] = []
        for v in data.values():  # BUC usage is {id: [ {..} ]}; app-usage is a flat dict
            if isinstance(v, list):
                vals += [_pct(x) for x in v if isinstance(x, dict)]
        top = max(top, max(vals) if vals else _pct(data))
    if ig_user_id and top:
        _usage[ig_user_id] = top
    return top


def usage_pct(ig_user_id: str) -> float:
    """Last-seen rate-limit usage % for an account (0 if unknown)."""
    return _usage.get(ig_user_id, 0.0)


def _expires_at(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=int(seconds or 0))).isoformat(
        timespec="seconds")


def auth_url(state: str, *, app_id: str, redirect_uri: str) -> str:
    """The consent URL to send the user to (opens Instagram's authorize screen)."""
    return AUTHORIZE_URL + "?" + urlencode({
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
    })


def exchange_code(code: str, *, app_id: str, app_secret: str, redirect_uri: str) -> dict:
    """Turn an OAuth code into a long-lived token + account identity.

    Returns {ig_user_id, username, access_token, expires_at}.
    """
    with httpx.Client(timeout=30) as client:
        # 1) code -> short-lived token (+ app-scoped user id)
        short = client.post(TOKEN_URL, data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        })
        _raise(short, "token exchange")
        short_token = short.json().get("access_token")
        if not short_token:
            raise InstagramError("no access_token in token response")

        # 2) short-lived -> long-lived (60 days)
        longr = client.get(f"{GRAPH}/access_token", params={
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": short_token,
        })
        _raise(longr, "long-lived exchange")
        lj = longr.json()
        token = lj.get("access_token", short_token)
        expires_at = _expires_at(lj.get("expires_in", 60 * 24 * 3600))

        # 3) identity
        me = client.get(f"{GRAPH}/me", params={
            "fields": "user_id,username,account_type",
            "access_token": token,
        })
        _raise(me, "account lookup")
        mj = me.json()
    return {
        "ig_user_id": str(mj.get("user_id") or mj.get("id") or ""),
        "username": mj.get("username", ""),
        "account_type": mj.get("account_type", ""),
        "access_token": token,
        "expires_at": expires_at,
    }


def refresh_token(token: str) -> dict:
    """Extend a long-lived token by another 60 days. Returns {access_token, expires_at}."""
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{GRAPH}/refresh_access_token", params={
            "grant_type": "ig_refresh_token",
            "access_token": token,
        })
        _raise(r, "token refresh")
        j = r.json()
    return {"access_token": j.get("access_token", token),
            "expires_at": _expires_at(j.get("expires_in", 60 * 24 * 3600))}


def account_info(token: str) -> dict:
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{GRAPH}/me", params={
            "fields": "user_id,username,account_type,media_count",
            "access_token": token,
        })
        _raise(r, "account info")
        return r.json()


def profile(token: str) -> dict:
    """Full public profile for the Feed Preview (counts, bio, avatar)."""
    fields = ("user_id,username,account_type,media_count,followers_count,"
              "follows_count,profile_picture_url,biography,name")
    with httpx.Client(timeout=30) as client:
        r = client.get(f"{GRAPH}/me", params={"fields": fields, "access_token": token})
        _raise(r, "profile")
        return r.json()


def recent_media(token: str, limit: int = 12) -> list[dict]:
    """The account's real recent posts. Returns [] on any failure (best-effort)."""
    fields = "id,media_type,media_url,thumbnail_url,permalink,caption,timestamp"
    try:
        with httpx.Client(timeout=30) as client:
            r = client.get(f"{GRAPH}/me/media", params={
                "fields": fields, "limit": limit, "access_token": token,
            })
            if r.status_code >= 400:
                return []
            return r.json().get("data", []) or []
    except Exception:  # noqa: BLE001
        return []


def publishing_limit(ig_user_id: str, token: str) -> dict | None:
    """How many of the 24h publishing quota are used. None if unavailable."""
    try:
        with httpx.Client(timeout=20) as client:
            r = client.get(f"{_base()}/{ig_user_id}/content_publishing_limit", params={
                "access_token": token,
            })
            if r.status_code == 200:
                data = r.json().get("data") or [{}]
                return data[0] if data else None
    except Exception:  # noqa: BLE001
        pass
    return None


def publish(ig_user_id: str, token: str, media_url: str, caption: str,
            is_video: bool) -> str:
    """Create + publish a media container. Returns the published Instagram media id."""
    with httpx.Client(timeout=120) as client:
        # 1) container
        params = {"caption": caption or "", "access_token": token}
        if is_video:
            params["media_type"] = "REELS"
            params["video_url"] = media_url
        else:
            params["image_url"] = media_url
        create = client.post(f"{_base()}/{ig_user_id}/media", data=params)
        _raise(create, "create container")
        creation_id = create.json().get("id")
        if not creation_id:
            raise InstagramError("no creation id returned")

        # 2) wait until the container is FINISHED — for IMAGES too. Publishing before
        #    processing completes is what triggers "Media ID is not available".
        _await_container(client, creation_id, token, is_video=is_video)

        # 3) publish (retry through the brief post-finish propagation window)
        return _publish_container(client, ig_user_id, creation_id, token)


def _await_container(client: httpx.Client, creation_id: str, token: str, *,
                     is_video: bool) -> None:
    # Gentle polling — every GET counts toward the 200 calls/user/hour limit.
    tries, delay = (30, 5.0) if is_video else (10, 3.0)
    for _ in range(tries):
        r = client.get(f"{_base()}/{creation_id}", params={
            "fields": "status_code,status", "access_token": token,
        })
        _raise(r, "container status")  # raises RateLimitError on throttle → no retry
        status = r.json().get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise InstagramError(
                f"Instagram couldn't process the media ({status}). "
                f"Check that the media URL is public: {r.json().get('status', '')}")
        time.sleep(delay)  # IN_PROGRESS / not-yet-reported
    raise InstagramError("container did not finish processing in time")


def _publish_container(client: httpx.Client, ig_user_id: str, creation_id: str,
                       token: str, tries: int = 3) -> str:
    last = "unknown error"
    for attempt in range(tries):
        pub = client.post(f"{_base()}/{ig_user_id}/media_publish", data={
            "creation_id": creation_id, "access_token": token,
        })
        note_usage(pub, ig_user_id)  # track rate-limit headroom
        if pub.status_code < 400:
            media_id = pub.json().get("id")
            if media_id:
                return str(media_id)
            last = "no media id after publish"
        else:
            code, msg = _error(pub)
            if pub.status_code == 429 or code in _RATE_LIMIT_CODES:
                raise RateLimitError(f"rate limited during publish (code {code}): {msg}")
            # only the "not available yet" case is transient; anything else is fatal
            if "not available" not in (msg or "").lower():
                raise InstagramError(f"publish container failed ({pub.status_code}): {msg}")
            last = msg
        if attempt < tries - 1:
            time.sleep(2 * (2 ** attempt))  # exponential backoff: 2s, 4s
    raise InstagramError(f"publish failed after retries: {last}")


def _raise(resp: httpx.Response, step: str) -> None:
    if resp.status_code < 400:
        return
    code, msg = _error(resp)
    if resp.status_code == 429 or code in _RATE_LIMIT_CODES:
        raise RateLimitError(
            f"Instagram rate limit hit during {step} (code {code}) — backing off. {msg}")
    raise InstagramError(f"{step} failed ({resp.status_code}): {msg}")
