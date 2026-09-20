"""Central configuration, loaded from the environment (.env)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# --- Paths ---  (BASE_DIR = backend/)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
DB_PATH = DATA_DIR / "posts.db"

# Load backend/.env explicitly so it works regardless of the process cwd.
load_dotenv(BASE_DIR / ".env")

DATA_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# --- Deployment ---
# Postgres connection string (e.g. from Neon/Render). Empty = local SQLite.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Production when ENVIRONMENT=production OR when running on Render (which always sets
# RENDER=true). The latter fails safe: a Render deploy is secured even if someone forgets
# to set ENVIRONMENT — docs, dev-login, and the config safety-check all switch on.
IS_PRODUCTION = (
    os.getenv("ENVIRONMENT", "development").strip().lower() == "production"
    or os.getenv("RENDER", "").strip().lower() == "true"
)

# --- Auth ---
_DEFAULT_JWT_SECRET = "dev-insecure-change-me"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
JWT_SECRET = os.getenv("JWT_SECRET", _DEFAULT_JWT_SECRET).strip()
JWT_TTL_SECONDS = _get_int("JWT_TTL_SECONDS", 60 * 60 * 24 * 7)  # 7 days
# The owner email that inherits pre-existing (orphan) posts on first login.
OWNER_EMAIL = os.getenv("OWNER_EMAIL", "").strip().lower()
# Header-based dev login (no Google) — ONLY outside production.
ALLOW_DEV_LOGIN = _get_bool("ALLOW_DEV_LOGIN", not IS_PRODUCTION) and not IS_PRODUCTION
# Interactive API docs (/docs, /redoc, /openapi.json) — off in production by default.
ENABLE_DOCS = _get_bool("ENABLE_DOCS", not IS_PRODUCTION)
# Per-user generation rate limit (posts started per rolling hour).
RATE_LIMIT_PER_HOUR = _get_int("RATE_LIMIT_PER_HOUR", 60)


def assert_production_safe() -> None:
    """Refuse to boot in production with insecure defaults."""
    if not IS_PRODUCTION:
        return
    problems = []
    if JWT_SECRET == _DEFAULT_JWT_SECRET or len(JWT_SECRET) < 32:
        problems.append("JWT_SECRET must be set to a strong random value (>=32 chars)")
    if not GOOGLE_CLIENT_ID:
        problems.append("GOOGLE_CLIENT_ID must be set (Google sign-in)")
    if not DATABASE_URL:
        problems.append("DATABASE_URL must be set (Postgres) in production")
    if not FRONTEND_ORIGINS:
        problems.append("FRONTEND_ORIGINS must list your frontend URL(s)")
    if ALLOW_DEV_LOGIN:  # already forced False in prod; asserted here as defense-in-depth
        problems.append("ALLOW_DEV_LOGIN must be disabled in production")
    if problems:
        raise RuntimeError("Unsafe production config:\n  - " + "\n  - ".join(problems))

# --- Media storage: Cloudinary ---
# When configured, generated images/videos are uploaded to Cloudinary and served from its
# CDN (survives redeploys; required for Instagram publishing). Empty = local disk.
# Easiest: paste CLOUDINARY_URL from the dashboard (cloudinary://key:secret@cloud_name).
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "").strip()
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()
# Comma-separated allowed frontend origins for CORS (your Vercel/domain URLs).
FRONTEND_ORIGINS = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o.strip()]
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()

# --- Caption providers ---
# "auto" picks the best available key; or force one:
#   gemini | anthropic | openai | cloudflare | template
CAPTION_PROVIDER = os.getenv("CAPTION_PROVIDER", "auto").strip().lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash").strip()
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_CAPTION_MODEL = os.getenv("OPENAI_CAPTION_MODEL", "gpt-4o-mini").strip()

# --- Image provider ---
# "auto" picks the best available key; or force one:
#   gemini | openai | pollinations | cloudflare | pexels | placeholder
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "auto").strip().lower()
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip()

# Cloudflare Workers AI (free tier). Get both from https://dash.cloudflare.com -> AI -> Workers AI.
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
CLOUDFLARE_IMAGE_MODEL = os.getenv(
    "CLOUDFLARE_IMAGE_MODEL", "@cf/black-forest-labs/flux-1-schnell"
).strip()
CLOUDFLARE_TEXT_MODEL = os.getenv(
    "CLOUDFLARE_TEXT_MODEL", "@cf/meta/llama-3.1-8b-instruct"
).strip()
# Bigger model for structured JSON specs (infographics) — better at valid nested JSON.
CLOUDFLARE_JSON_MODEL = os.getenv(
    "CLOUDFLARE_JSON_MODEL", "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
).strip()

# Pexels (free stock photography — real photos instead of AI). Key: https://www.pexels.com/api/
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()

# --- Text overlay on images ---
# Burn the theme text onto the generated image (quote-card style). true/false.
OVERLAY_TEXT = _get_bool("OVERLAY_TEXT", True)

# --- Scheduler ---
DAILY_ENABLED = _get_bool("DAILY_ENABLED", True)
DAILY_HOUR = _get_int("DAILY_HOUR", 9)
DAILY_MINUTE = _get_int("DAILY_MINUTE", 0)

# How many generation jobs may render at once. Rendering (PIL/ffmpeg/numpy) is
# memory-heavy, so 1 keeps peak RSS low on small instances (e.g. Render 512MB).
GEN_CONCURRENCY = max(1, _get_int("GEN_CONCURRENCY", 1))

# Shared secret for the external cron trigger (/api/cron/run). An always-on cron
# service should hit that endpoint so scheduling works even if the free instance sleeps.
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()

# Skip video (Reel) rendering when free container memory is below this many MB, so
# a heavy ffmpeg render degrades to an image post instead of OOM-killing the whole
# instance. 0 disables the guard (set it high — e.g. 512MB+ instances — or 0 to force).
VIDEO_MIN_FREE_MB = _get_int("VIDEO_MIN_FREE_MB", 350)

# --- Plans & referrals (infra; paid billing not wired yet) ---
FREE_POSTS_PER_MONTH = _get_int("FREE_POSTS_PER_MONTH", 30)
PRO_POSTS_PER_MONTH = _get_int("PRO_POSTS_PER_MONTH", 1000)
FREE_POSTS_PER_DAY = _get_int("FREE_POSTS_PER_DAY", 1)   # auto-post cap on Free
PRO_POSTS_PER_DAY = _get_int("PRO_POSTS_PER_DAY", 3)     # auto-post cap on Pro
REFERRAL_REWARD_DAYS = _get_int("REFERRAL_REWARD_DAYS", 30)  # Pro days per referral

# --- Instagram (legacy single-account env, kept for reference) ---
IG_USER_ID = os.getenv("IG_USER_ID", "").strip()
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN", "").strip()

# --- Instagram Content Publishing (Meta app; "Instagram API with Instagram Login") ---
# These come from your Meta app's Instagram product → "API setup with Instagram login".
INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "").strip()
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "").strip()
# The OAuth redirect back to THIS backend, e.g. https://api.example.com/api/instagram/callback
# Must be listed in the app's OAuth redirect URIs verbatim.
INSTAGRAM_REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "").strip()
IG_GRAPH_VERSION = os.getenv("IG_GRAPH_VERSION", "v21.0").strip()
# Fernet key used to encrypt stored IG tokens at rest. If unset, a deterministic
# key is derived from JWT_SECRET so local dev works without extra setup.
INSTAGRAM_TOKEN_KEY = os.getenv("INSTAGRAM_TOKEN_KEY", "").strip()


def instagram_configured() -> bool:
    """True when the Meta app credentials needed for the OAuth flow are present."""
    return bool(INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET and INSTAGRAM_REDIRECT_URI)


def caption_provider() -> str:
    """Which engine writes captions. An explicit CAPTION_PROVIDER wins over key auto-detect."""
    if CAPTION_PROVIDER and CAPTION_PROVIDER != "auto":
        return CAPTION_PROVIDER
    if GEMINI_API_KEY:
        return "gemini"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if OPENAI_API_KEY:
        return "openai"
    if CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN:
        return "cloudflare"
    return "template"


def image_provider() -> str:
    """Which engine renders images. An explicit IMAGE_PROVIDER wins over key auto-detect."""
    if IMAGE_PROVIDER and IMAGE_PROVIDER != "auto":
        return IMAGE_PROVIDER
    if GEMINI_API_KEY:
        return "gemini"
    if OPENAI_API_KEY:
        return "openai"
    return "placeholder"
