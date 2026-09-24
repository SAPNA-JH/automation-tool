"""FastAPI backend — multi-tenant JSON API. Every /api route is authenticated and
scoped to the signed-in user. The frontend (Vite SPA) is deployed separately."""
from __future__ import annotations

import gc
import random
import threading
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))  # all automation schedules are in IST

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, billing, composer, config, crypto, database, generator, instagram, niches

STATIC_DIR = config.BASE_DIR / "app" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.assert_production_safe()  # refuse to boot with insecure prod config
    database.init_db()
    niches.seed()  # populate the niche_presets table from code (idempotent)
    # Render previews + synth music AFTER boot, staggered with GC, so a small
    # instance doesn't spike from doing it all at once during startup.
    threading.Thread(target=_warmup, daemon=True).start()
    threading.Thread(target=_instagram_worker, daemon=True).start()
    yield
    database.close_pool()


def _warmup() -> None:
    try:
        default_brand = niches.default_account("@studio")["brand"]
        composer.render_previews(default_brand)
        gc.collect()
        from .video import music, templates as video_templates
        video_templates.render_video_previews(default_brand)
        gc.collect()
        music.ensure_music()
        gc.collect()
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] preview/music warmup failed: {exc}")


app = FastAPI(
    title="Postpilot API",
    lifespan=lifespan,
    docs_url="/docs" if config.ENABLE_DOCS else None,
    redoc_url="/redoc" if config.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if config.ENABLE_DOCS else None,
)

if config.FRONTEND_ORIGINS:
    app.add_middleware(
        CORSMiddleware, allow_origins=config.FRONTEND_ORIGINS,
        allow_methods=["*"], allow_headers=["*"],
    )

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --------------------------------------------------------------------------
# Async generation jobs (per user)
# --------------------------------------------------------------------------

_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
# Cap concurrent renders — PIL/ffmpeg/numpy are memory-heavy, so serialize by
# default to keep peak RSS low on small instances.
_gen_sem = threading.Semaphore(config.GEN_CONCURRENCY)


def _spawn_job(user_id: int, label: str, fn) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _jobs_lock:
        _jobs[job_id] = {
            "id": job_id, "user_id": user_id, "label": label, "status": "running",
            "post_id": None, "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    def run():
        try:
            with _gen_sem:  # one render at a time (memory) unless GEN_CONCURRENCY raised
                post_id = fn()
            with _jobs_lock:
                _jobs[job_id].update(status="done", post_id=post_id)
        except Exception as exc:  # noqa: BLE001
            with _jobs_lock:
                _jobs[job_id].update(status="error", error=str(exc)[:300])
        finally:
            gc.collect()  # release PIL/numpy buffers promptly after each render

    threading.Thread(target=run, daemon=True).start()
    return job_id


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------

class GoogleBody(BaseModel):
    credential: str
    ref_code: str = Field("", max_length=32)


class DevLoginBody(BaseModel):
    email: str
    name: str = "Dev User"
    ref_code: str = Field("", max_length=32)


class ReferralBody(BaseModel):
    code: str = Field("", max_length=32)


class AutomationBody(BaseModel):
    mode: str | None = Field(None, max_length=10)  # 'auto' | 'semi' | 'manual'
    auto_niche: str | None = Field(None, max_length=60)  # '' = random, else a niche key


class GenerateBody(BaseModel):
    category: str | None = Field(None, max_length=120)
    template: str | None = Field(None, max_length=60)
    theme: str | None = Field(None, max_length=300)
    count: int = Field(1, ge=1, le=5)


class PostPatch(BaseModel):
    caption: str | None = Field(None, max_length=4000)
    hashtags: str | None = Field(None, max_length=1000)
    status: str | None = Field(None, max_length=20)
    theme: str | None = Field(None, max_length=300)


class SettingsBody(BaseModel):
    handle: str | None = Field(None, max_length=40)
    accent: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    weights: dict[str, int] | None = None


class NicheBody(BaseModel):
    preset: str | None = Field(None, max_length=60)
    topic: str | None = Field(None, max_length=120)


class InstagramSettings(BaseModel):
    auto_post: bool | None = None
    post_hour: int | None = Field(None, ge=0, le=23)
    post_minute: int | None = Field(None, ge=0, le=59)
    frequency: str | None = Field(None, max_length=20)
    posts_per_day: int | None = Field(None, ge=1, le=5)
    post_slots: list[str] | None = Field(None, max_length=6)  # ["HH:MM", ...] in IST


class InstagramConfig(BaseModel):
    app_id: str = Field("", max_length=64)
    app_secret: str = Field("", max_length=200)  # blank on edit = keep existing secret
    redirect_uri: str = Field("", max_length=300)


def _account(user: dict) -> dict:
    acct = database.get_account(user["id"])
    if not acct:
        seed = niches.default_account("@" + user["email"].split("@")[0])
        database.upsert_account(user["id"], **seed)
        acct = {"user_id": user["id"], **seed}
    return acct


def _public_user(user: dict) -> dict:
    return {"id": user["id"], "email": user["email"], "name": user["name"],
            "picture": user["picture"]}


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

@app.post("/api/auth/google")
def auth_google(body: GoogleBody):
    info = auth.verify_google_token(body.credential)
    user, token = auth.login_or_create(info, ref_code=body.ref_code)
    return {"token": token, "user": _public_user(user)}


@app.post("/api/auth/dev-login")
def auth_dev_login(body: DevLoginBody):
    if not config.ALLOW_DEV_LOGIN:
        raise HTTPException(403, "dev login disabled")
    user, token = auth.login_or_create(
        {"sub": f"dev-{body.email}", "email": body.email, "name": body.name, "picture": ""},
        ref_code=body.ref_code,
    )
    return {"token": token, "user": _public_user(user)}


@app.get("/api/auth/me")
def auth_me(user: dict = Depends(auth.current_user)):
    full = database.get_user(user["id"])  # verifies the user still exists + full profile
    if not full:
        raise HTTPException(401, "user not found")
    return _public_user(full)

@app.api_route("/api/cron/run", methods=["GET", "POST"])
def api_cron_run(key: str = ""):
    """External-cron entry point. Runs the scheduler tick once. Point an always-on cron
    (cron-job.org, UptimeRobot, GitHub Actions) at this every ~5 min so posting works
    reliably even when a free instance sleeps between requests."""
    if not config.CRON_SECRET or key != config.CRON_SECRET:
        raise HTTPException(403, "forbidden")
    _instagram_tick()
    return {"ok": True, "ran_at": datetime.now(IST).isoformat(timespec="seconds")}


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    # HEAD is included so uptime monitors (UptimeRobot defaults to HEAD) get 200, not 405.
    return {"status": "Healthy", "message": "The API is running smoothly.", "status_code": 200}

# --------------------------------------------------------------------------
# Meta / content (all authenticated + user-scoped)
# --------------------------------------------------------------------------

@app.get("/api/meta")
def api_meta(user: dict = Depends(auth.current_user)):
    acct = _account(user)
    brand = acct["brand"]
    return {
        "brand": {"handle": brand.get("handle", ""), "accent": brand.get("accent", "#a855f7"),
                  "niche": brand.get("niche", "")},
        "categories": [{"name": c.get("name", ""), "weight": c.get("weight", 1),
                        "description": c.get("description", "")} for c in acct["categories"]],
        "templates": generator.template_names(acct),
        "families": generator.FAMILIES,
        "preview_designs": [d for fam in generator.FAMILIES for d in fam["designs"]],
        "caption_provider": config.caption_provider(),
        "image_provider": config.image_provider(),
    }


@app.get("/api/stats")
def api_stats(user: dict = Depends(auth.current_user)):
    return database.stats(user["id"])


@app.get("/api/posts")
def api_posts(status: str = "", category: str = "", template: str = "", q: str = "",
              user: dict = Depends(auth.current_user)):
    return database.list_posts(user["id"], status=status or None, category=category or None,
                               post_type=template or None, q=q or None)


@app.patch("/api/posts/{post_id}")
def api_patch_post(post_id: int, body: PostPatch, user: dict = Depends(auth.current_user)):
    if not database.get_post(user["id"], post_id):
        raise HTTPException(404, "post not found")
    try:
        database.update_fields(user["id"], post_id, **body.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return database.get_post(user["id"], post_id)


@app.delete("/api/posts/{post_id}")
def api_delete_post(post_id: int, user: dict = Depends(auth.current_user)):
    if not database.get_post(user["id"], post_id):
        raise HTTPException(404, "post not found")
    image_file = database.delete_post(user["id"], post_id)
    if image_file:
        try:
            (config.IMAGES_DIR / image_file).unlink(missing_ok=True)
        except OSError:
            pass
    return {"ok": True}


def _check_rate_limit(user_id: int, adding: int) -> None:
    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
    recent = database.count_recent_posts(user_id, since)
    if recent + adding > config.RATE_LIMIT_PER_HOUR:
        raise HTTPException(429, f"hourly generation limit reached "
                                 f"({config.RATE_LIMIT_PER_HOUR}/hr). Try again later.")


@app.post("/api/generate")
def api_generate(body: GenerateBody, user: dict = Depends(auth.current_user)):
    count = max(1, min(body.count, 5))
    _check_rate_limit(user["id"], count)
    full = database.get_user(user["id"]) or user
    is_reel = bool(body.template and body.template in generator.VIDEO_DESIGNS)
    try:
        billing.check_generate(full, count=count, is_reel=is_reel)
    except billing.PlanLimitError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    allow_video = billing.allows_reels(full)
    acct = _account(user)
    uid = user["id"]
    label = f"{body.template or 'auto'} · {body.theme or body.category or 'any category'}"
    theme = (body.theme or "").strip() or None
    cat = body.category or None
    tmpl = body.template or None
    jobs = [
        _spawn_job(uid, label, lambda u=uid, a=acct: generator.generate_post(
            u, a, category_name=cat, template=tmpl, theme=theme, allow_video=allow_video))
        for _ in range(count)
    ]
    return {"job_ids": jobs}


@app.post("/api/posts/{post_id}/regenerate")
def api_regenerate(post_id: int, user: dict = Depends(auth.current_user)):
    if not database.get_post(user["id"], post_id):
        raise HTTPException(404, "post not found")
    _check_rate_limit(user["id"], 1)
    acct = _account(user)
    uid = user["id"]
    job_id = _spawn_job(uid, f"regen #{post_id}",
                        lambda: (generator.regenerate_post(uid, acct, post_id), post_id)[1])
    return {"job_ids": [job_id]}


@app.get("/api/jobs")
def api_jobs(user: dict = Depends(auth.current_user)):
    with _jobs_lock:
        jobs = [j for j in _jobs.values() if j["user_id"] == user["id"]]
    return sorted(jobs, key=lambda j: j["started_at"], reverse=True)[:30]


@app.get("/api/settings")
def api_settings(user: dict = Depends(auth.current_user)):
    acct = _account(user)
    return {
        "brand": acct["brand"],
        "categories": [{"name": c.get("name", ""), "weight": c.get("weight", 1)}
                       for c in acct["categories"]],
        "formats": acct["formats"],
    }


@app.put("/api/settings")
def api_put_settings(body: SettingsBody, user: dict = Depends(auth.current_user)):
    acct = _account(user)
    brand = dict(acct["brand"])
    if body.handle is not None:
        brand["handle"] = body.handle.strip()
    if body.accent is not None:
        brand["accent"] = body.accent.strip()
    categories = [dict(c) for c in acct["categories"]]
    if body.weights:
        for c in categories:
            if c["name"] in body.weights:
                c["weight"] = max(0, int(body.weights[c["name"]]))
    database.upsert_account(user["id"], brand=brand, categories=categories,
                            formats=acct["formats"])
    return {"ok": True}


@app.get("/api/niches")
def api_niches(user: dict = Depends(auth.current_user)):
    return niches.preset_list()


@app.post("/api/niche")
def api_apply_niche(body: NicheBody, user: dict = Depends(auth.current_user)):
    if body.preset:
        niche = niches.get_preset(body.preset)  # from the niche_presets DB table
        if not niche:
            raise HTTPException(404, f"unknown preset: {body.preset}")
    elif body.topic and body.topic.strip():
        try:
            niche = niches.generate_niche(body.topic.strip())
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"AI niche generation failed: {exc}") from exc
    else:
        raise HTTPException(422, "provide `preset` or `topic`")

    acct = _account(user)
    handle = acct["brand"].get("handle", "")  # keep the user's handle across niche swaps
    brand = niches.niche_to_brand(niche, handle, preset_key=body.preset or "custom")
    categories = [dict(c) for c in niche["categories"]]
    database.upsert_account(user["id"], brand=brand, categories=categories,
                            formats=acct["formats"])
    return {"ok": True, "brand": brand, "categories": [c["name"] for c in categories]}


# --------------------------------------------------------------------------
# Plans & referrals
# --------------------------------------------------------------------------

@app.get("/api/plan")
def api_plan(user: dict = Depends(auth.current_user)):
    full = database.get_user(user["id"])
    if not full:
        raise HTTPException(401, "user not found")
    if not full.get("referral_code"):  # backfill for pre-referral users
        database.ensure_referral_code(full["id"])
        full = database.get_user(user["id"])
    return billing.status(full)


@app.post("/api/referral/apply")
def api_referral_apply(body: ReferralBody, user: dict = Depends(auth.current_user)):
    full = database.get_user(user["id"])
    if not full:
        raise HTTPException(401, "user not found")
    if full.get("referred_by"):
        raise HTTPException(400, "a referral code has already been applied to this account")
    if not billing.apply_referral(full, body.code):
        raise HTTPException(400, "invalid referral code")
    return billing.status(database.get_user(user["id"]))


# --------------------------------------------------------------------------
# Automation mode (fully-automatic / semi / manual) — the app's master switch
# --------------------------------------------------------------------------

MODES = ("auto", "semi", "manual")


def _automation_status(user_id: str) -> dict:
    a = database.get_automation(user_id)
    mode = a["mode"]
    return {
        "mode": mode,
        "auto_generate": mode == "auto",
        "auto_approve": mode == "auto",
        "auto_post": mode in ("auto", "semi"),
        "auto_niche": a["auto_niche"],  # '' = random
    }


@app.get("/api/automation")
def api_automation_get(user: dict = Depends(auth.current_user)):
    return _automation_status(user["id"])


@app.put("/api/automation")
def api_automation_set(body: AutomationBody, user: dict = Depends(auth.current_user)):
    if body.mode is not None:
        mode = body.mode if body.mode in MODES else "manual"
        if mode in ("auto", "semi"):  # both auto-post to Instagram → Pro
            full = database.get_user(user["id"])
            if not full or not billing.limits(full)["auto_post"]:
                raise HTTPException(403, "Automatic posting is a Pro feature — upgrade to enable it.")
        database.set_automation(user["id"], mode=mode)
    if body.auto_niche is not None:
        key = body.auto_niche.strip()
        if key and not database.get_niche(key):
            raise HTTPException(404, f"unknown niche: {key}")
        database.set_automation(user["id"], auto_niche=key)
    return _automation_status(user["id"])


# --------------------------------------------------------------------------
# Instagram connection + publishing
# --------------------------------------------------------------------------

def _ig_creds(user_id: str) -> dict | None:
    """Per-user Meta app credentials (App ID + secret). Redirect is canonical, added separately."""
    cfg = database.get_instagram_config(user_id)
    if cfg and cfg.get("app_id") and cfg.get("app_secret_enc"):
        secret = crypto.decrypt(cfg["app_secret_enc"])
        if secret:
            return {"app_id": cfg["app_id"], "app_secret": secret}
    if config.INSTAGRAM_APP_ID and config.INSTAGRAM_APP_SECRET:
        return {"app_id": config.INSTAGRAM_APP_ID, "app_secret": config.INSTAGRAM_APP_SECRET}
    return None


def _canonical_redirect(request: Request) -> str:
    """The single OAuth redirect URI every user registers in their own Meta app.

    Prefers the explicit env value (set on deploy); otherwise derives it from the
    incoming request, upgrading to https for non-local hosts (Render sits behind a
    TLS-terminating proxy that reports http).
    """
    if config.INSTAGRAM_REDIRECT_URI:
        return config.INSTAGRAM_REDIRECT_URI
    base = str(request.base_url).rstrip("/")
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        base = "https://" + base[len("http://"):]
    return f"{base}/api/instagram/callback"


def _instagram_status(user_id: str, redirect_uri: str) -> dict:
    cfg = database.get_instagram_config(user_id) or {}
    ig = database.get_instagram(user_id)
    base = {
        "configured": _ig_creds(user_id) is not None,
        "connected": False,
        "app_id": cfg.get("app_id") or config.INSTAGRAM_APP_ID,
        "redirect_uri": redirect_uri,
        "has_secret": bool(cfg.get("app_secret_enc") or config.INSTAGRAM_APP_SECRET),
    }
    if not ig:
        return base
    base.update(
        connected=True,
        username=ig["username"],
        ig_user_id=ig["ig_user_id"],
        token_expires=ig["token_expires"],
        auto_post=bool(ig["auto_post"]),
        post_hour=ig["post_hour"],
        post_minute=ig["post_minute"],
        frequency=ig.get("frequency", "daily"),
        posts_per_day=ig.get("posts_per_day", 1),
        post_slots=_slot_strings(ig),
        last_posted=ig["last_posted"],
        connected_at=ig["connected_at"],
    )
    return base


def _slot_strings(ig: dict) -> list[str]:
    """The account's posting times as ["HH:MM"] (IST). Falls back to the single time."""
    raw = ig.get("post_slots") or ""
    try:
        slots = database._loads(raw) or []
    except Exception:  # noqa: BLE001
        slots = []
    if not slots:
        slots = [f"{int(ig.get('post_hour', 10)):02d}:{int(ig.get('post_minute', 0)):02d}"]
    return sorted(slots)


def _publish_post_row(ig_row: dict, post: dict) -> str:
    """Decrypt the token and publish one post to Instagram. Raises on failure."""
    token = crypto.decrypt(ig_row["token_enc"])
    if not token:
        raise ValueError("stored Instagram token is invalid — please reconnect")
    media_url = post.get("media_url") or ""
    if not media_url.startswith("http"):
        raise ValueError(
            "post media isn't hosted at a public URL — Instagram can't fetch it. "
            "Make sure Cloudinary is configured so posts get a public media_url.")
    caption = "\n\n".join(
        x for x in [(post.get("caption") or "").strip(), (post.get("hashtags") or "").strip()] if x
    )
    media_id = instagram.publish(
        ig_row["ig_user_id"], token, post["media_url"], caption,
        post.get("media_kind") == "video",
    )
    database.mark_post_published(ig_row["user_id"], int(post["id"]), media_id)
    database.mark_instagram_posted(ig_row["user_id"], database._now())
    return media_id


@app.get("/api/instagram/status")
def api_ig_status(request: Request, user: dict = Depends(auth.current_user)):
    return _instagram_status(user["id"], _canonical_redirect(request))


@app.put("/api/instagram/config")
def api_ig_config(body: InstagramConfig, request: Request,
                  user: dict = Depends(auth.current_user)):
    app_id = body.app_id.strip()
    if not app_id:
        raise HTTPException(422, "App ID is required")
    existing = database.get_instagram_config(user["id"])
    secret = body.app_secret.strip()
    if secret:
        secret_enc = crypto.encrypt(secret)
    elif existing and existing.get("app_secret_enc"):
        secret_enc = existing["app_secret_enc"]  # left blank on edit → keep current secret
    else:
        raise HTTPException(422, "App secret is required")
    redirect = _canonical_redirect(request)  # fixed for everyone; stored for reference
    database.save_instagram_config(user["id"], app_id=app_id, app_secret_enc=secret_enc,
                                   redirect_uri=redirect)
    return _instagram_status(user["id"], redirect)


@app.get("/api/instagram/verify")
def api_ig_verify(user: dict = Depends(auth.current_user)):
    """Hot test: confirm the stored token works and report account + quota."""
    ig = database.get_instagram(user["id"])
    if not ig:
        raise HTTPException(404, "no Instagram account connected")
    token = crypto.decrypt(ig["token_enc"])
    if not token:
        raise HTTPException(400, "stored token is invalid — please reconnect")
    try:
        account = instagram.account_info(token)
    except instagram.InstagramError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"ok": True, "account": account,
            "publishing_limit": instagram.publishing_limit(ig["ig_user_id"], token)}


_ig_profile_cache: dict[str, tuple[float, dict]] = {}  # user_id -> (fetched_at, data)


@app.get("/api/instagram/profile")
def api_ig_profile(user: dict = Depends(auth.current_user)):
    """Real profile + recent media for the Feed Preview (cached 5 min per user)."""
    ig = database.get_instagram(user["id"])
    if not ig:
        return {"connected": False}
    cached = _ig_profile_cache.get(user["id"])
    if cached and time.time() - cached[0] < 300:
        return cached[1]
    token = crypto.decrypt(ig["token_enc"])
    if not token:
        return {"connected": True, "error": "stored token invalid — reconnect"}
    try:
        data = {"connected": True, "profile": instagram.profile(token),
                "media": instagram.recent_media(token, limit=12)}
    except instagram.InstagramError as exc:
        return {"connected": True, "error": str(exc)}
    _ig_profile_cache[user["id"]] = (time.time(), data)
    return data


@app.get("/api/instagram/auth-url")
def api_ig_auth_url(request: Request, user: dict = Depends(auth.current_user)):
    creds = _ig_creds(user["id"])
    if not creds:
        raise HTTPException(400, "add your Meta app credentials first")
    state = auth.issue_oauth_state(user["id"])
    return {"url": instagram.auth_url(state, app_id=creds["app_id"],
                                      redirect_uri=_canonical_redirect(request))}


@app.get("/api/instagram/callback")
def api_ig_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    front = config.FRONTEND_ORIGINS[0] if config.FRONTEND_ORIGINS else "http://localhost:5173"
    dest = f"{front}/connect"
    if error or not code or not state:
        return RedirectResponse(f"{dest}?ig=error", status_code=303)
    try:
        user_id = auth.verify_oauth_state(state)
        creds = _ig_creds(user_id)
        if not creds:
            raise ValueError("Meta app credentials are missing")
        data = instagram.exchange_code(code, app_id=creds["app_id"],
                                       app_secret=creds["app_secret"],
                                       redirect_uri=_canonical_redirect(request))
        if not data["ig_user_id"]:
            raise ValueError("could not resolve the Instagram account")
        database.save_instagram(
            user_id, ig_user_id=data["ig_user_id"], username=data["username"],
            token_enc=crypto.encrypt(data["access_token"]), token_expires=data["expires_at"],
        )
        return RedirectResponse(f"{dest}?ig=connected", status_code=303)
    except Exception as exc:  # noqa: BLE001
        print(f"[instagram] callback failed: {exc}")
        return RedirectResponse(f"{dest}?ig=error", status_code=303)


@app.post("/api/instagram/settings")
def api_ig_settings(body: InstagramSettings, request: Request,
                    user: dict = Depends(auth.current_user)):
    if not database.get_instagram(user["id"]):
        raise HTTPException(404, "no Instagram account connected")
    full = database.get_user(user["id"]) or user
    cap = billing.max_posts_per_day(full)
    if body.auto_post and not billing.limits(full)["auto_post"]:
        raise HTTPException(403, "Auto-posting to Instagram is a Pro feature.")
    if body.posts_per_day is not None and body.posts_per_day > cap:
        raise HTTPException(403, f"Your plan allows up to {cap} post(s)/day.")
    if body.post_slots is not None and len(body.post_slots) > cap:
        raise HTTPException(403, f"Your plan allows up to {cap} posting time(s) per day.")
    database.update_instagram_settings(
        user["id"], auto_post=body.auto_post,
        post_hour=body.post_hour, post_minute=body.post_minute,
        frequency=body.frequency, posts_per_day=body.posts_per_day,
        post_slots=body.post_slots,
    )
    return _instagram_status(user["id"], _canonical_redirect(request))


def _require_ig_posting(user_id: str) -> None:
    full = database.get_user(user_id)
    if not full or not billing.limits(full)["auto_post"]:
        raise HTTPException(403, "Publishing to Instagram is a Pro feature — upgrade to post.")


@app.post("/api/instagram/publish/{post_id}")
def api_ig_publish(post_id: int, user: dict = Depends(auth.current_user)):
    _require_ig_posting(user["id"])
    ig = database.get_instagram(user["id"])
    if not ig:
        raise HTTPException(404, "no Instagram account connected")
    post = database.get_post(user["id"], post_id)
    if not post:
        raise HTTPException(404, "post not found")
    try:
        media_id = _publish_post_row(ig, post)
    except instagram.InstagramError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "ig_media_id": media_id}


@app.post("/api/instagram/test-post")
def api_ig_test_post(user: dict = Depends(auth.current_user)):
    """Real end-to-end test: publish the next approved post to Instagram right now."""
    _require_ig_posting(user["id"])
    ig = database.get_instagram(user["id"])
    if not ig:
        raise HTTPException(404, "no Instagram account connected")
    post = database.next_publishable_post(user["id"])
    if not post:
        raise HTTPException(400, "no approved post is ready — approve one on the Posts page first")
    try:
        media_id = _publish_post_row(ig, post)
    except instagram.InstagramError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "ig_media_id": media_id, "post_id": post["id"],
            "theme": post.get("theme", "")}


@app.delete("/api/instagram/disconnect")
def api_ig_disconnect(user: dict = Depends(auth.current_user)):
    database.delete_instagram(user["id"])
    return {"ok": True}


# --- background publisher: refresh tokens + auto-post one approved post/day ----

def _maybe_refresh(ig: dict) -> None:
    exp = ig.get("token_expires", "")
    if not exp:
        return
    try:
        expires = datetime.fromisoformat(exp)
    except ValueError:
        return
    if expires - datetime.now(timezone.utc) > timedelta(days=10):
        return  # still comfortably valid
    token = crypto.decrypt(ig["token_enc"])
    if not token:
        return
    try:
        r = instagram.refresh_token(token)
        database.set_instagram_token(
            ig["user_id"], crypto.encrypt(r["access_token"]), r["expires_at"])
        print(f"[instagram] refreshed token for @{ig['username']}")
    except Exception as exc:  # noqa: BLE001
        print(f"[instagram] token refresh failed for @{ig.get('username')}: {exc}")


_MIN_GAP_MINUTES = 30  # guard so one slot isn't posted twice across ticks
_ig_backoff: dict[str, float] = {}  # user_id -> epoch until which to pause (rate-limit backoff)


def _is_active_day(ig: dict, now_ist: datetime) -> bool:
    """Whether today (IST) is a posting day for this account's frequency."""
    freq = ig.get("frequency", "daily")
    if freq == "weekdays":
        return now_ist.weekday() < 5
    if freq in ("every_2_days", "every_3_days", "weekly"):
        try:
            start = datetime.fromisoformat(ig["connected_at"]).astimezone(IST).date()
        except (ValueError, KeyError, TypeError):
            return True
        span = {"every_2_days": 2, "every_3_days": 3, "weekly": 7}[freq]
        return (now_ist.date() - start).days % span == 0
    return True  # daily / unknown


def _auto_generate_approved(user_id: str) -> int | None:
    """Fully-automatic mode: generate one post + auto-approve it. Uses the chosen
    niche if set, else a random one. Images only (video is memory-heavy)."""
    acct = database.get_account(user_id)
    if not acct:
        return None
    chosen = database.get_automation(user_id).get("auto_niche") or ""
    n = database.get_niche(chosen) if chosen else None
    if n is None:
        niche_rows = database.list_niches()
        if not niche_rows:
            return None
        n = random.choice(niche_rows)
    handle = acct["brand"].get("handle", "")
    brand = niches.niche_to_brand(
        {"key": n["key"], "name": n["name"], "emoji": n["emoji"], "tagline": n["tagline"],
         "accent": n["accent"], "brand": n["brand"], "categories": n["categories"]},
        handle, preset_key=n["key"])
    transient = {"brand": brand, "categories": n["categories"], "formats": acct["formats"]}
    with _gen_sem:  # respect the render-concurrency cap
        post_id = generator.generate_post(user_id, transient, allow_video=False)
    if post_id:
        database.set_status(user_id, post_id, "approved")
        print(f"[automation] auto-generated + approved post {post_id} "
              f"(niche: {n['key']}) for {user_id}")
    return post_id


def _instagram_tick() -> None:
    now_ist = datetime.now(IST)
    now_utc = datetime.now(timezone.utc)
    start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_ist.astimezone(timezone.utc).isoformat(timespec="seconds")
    for ig in database.list_connected_instagram():
        try:
            uid = ig["user_id"]
            if time.time() < _ig_backoff.get(uid, 0):
                continue  # rate-limited earlier → skip until backoff expires
            if instagram.usage_pct(ig["ig_user_id"]) >= 90:  # proactive cool-down near the cap
                _ig_backoff[uid] = time.time() + 900
                print(f"[instagram] usage high for @{ig.get('username')} — cooling down 15m")
                continue
            mode = database.get_automation_mode(uid)
            if mode not in ("auto", "semi"):
                continue  # manual → nothing automatic
            owner = database.get_user(uid)
            plan_limits = billing.limits(owner) if owner else {"auto_post": False, "posts_per_day": 1}
            if not plan_limits["auto_post"]:
                continue  # Free / expired Pro — no auto-posting
            _maybe_refresh(ig)
            if not _is_active_day(ig, now_ist):
                continue
            # How many of today's scheduled slots (IST) are already due?
            slots = _slot_strings(ig)
            due = sum(1 for s in slots
                      if now_ist >= now_ist.replace(hour=int(s[:2]), minute=int(s[3:]),
                                                     second=0, microsecond=0))
            if due == 0:
                continue  # earliest slot not reached yet
            cap = int(plan_limits["posts_per_day"])
            allowed_today = min(due, cap)
            if database.count_published_since(uid, start_utc) >= allowed_today:
                continue  # all due slots already posted (or plan cap hit)
            last = ig.get("last_posted", "")
            if last:  # guard against double-posting a single slot across ticks
                try:
                    if now_utc - datetime.fromisoformat(last) < timedelta(minutes=_MIN_GAP_MINUTES):
                        continue
                except ValueError:
                    pass
            post = database.next_publishable_post(uid)
            if not post and mode == "auto":
                pid = _auto_generate_approved(uid)  # nothing queued → make one
                post = database.get_post(uid, pid) if pid else None
            if not post:
                continue  # semi mode with an empty approved queue, or generation failed
            fresh = database.get_instagram(uid) or ig  # pick up a refreshed token
            media_id = _publish_post_row(fresh, post)
            print(f"[instagram] auto-posted post {post['id']} → {media_id} for @{ig['username']}")
        except instagram.RateLimitError as exc:
            _ig_backoff[ig["user_id"]] = time.time() + 3600  # pause this account 1h
            print(f"[instagram] rate limited for @{ig.get('username')} — backing off 1h: {exc}")
        except Exception as exc:  # noqa: BLE001
            print(f"[instagram] auto-post failed for @{ig.get('username')}: {exc}")


def _instagram_worker() -> None:
    # small startup delay so the DB/pool is warm before the first tick
    time.sleep(20)
    while True:
        try:
            _instagram_tick()
        except Exception as exc:  # noqa: BLE001
            print(f"[instagram] worker error: {exc}")
        time.sleep(60)


# --------------------------------------------------------------------------
# Media serving (fallback for local dev; production serves via Cloudinary media_url)
# --------------------------------------------------------------------------

@app.get("/posts/{post_id}/image")
def post_image(post_id: int):
    # Public by necessity: <img>/<video> tags can't send an Authorization header, and this
    # is public social-media content (in production it's served straight from the Cloudinary
    # media_url). Sensitive data (captions, post lists, settings) stays authenticated.
    with database._connect() as conn:
        row = conn.execute(database._q(
            "SELECT image_file, media_kind, media_url FROM posts WHERE id = ?"),
            (post_id,)).fetchone()
    post = dict(row) if row else None
    if not post or not post["image_file"]:
        return RedirectResponse("/static/missing.png", status_code=303)
    if post.get("media_url"):
        return RedirectResponse(post["media_url"], status_code=302)
    sub = "videos" if post.get("media_kind") == "video" else "images"
    path = config.DATA_DIR / sub / post["image_file"]
    if path.exists():
        return FileResponse(path, media_type="video/mp4" if sub == "videos" else None)
    return RedirectResponse("/static/missing.png", status_code=303)


@app.get("/")
def root():
    return {"service": "running", "ok": True}
