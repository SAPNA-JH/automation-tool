"""Media storage on Cloudinary.

When configured, generated posters/reels are uploaded to Cloudinary and served from its
CDN — so media survives Render redeploys and is reachable by the Instagram Graph API later.
Not configured → the app keeps serving files from local disk via /posts/{id}/image.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import config

FOLDER = "glitch-studio"
_configured = False


def _creds() -> tuple[str, str, str] | None:
    """Resolve (cloud_name, api_key, api_secret) from either config form."""
    if config.CLOUDINARY_CLOUD_NAME and config.CLOUDINARY_API_KEY and config.CLOUDINARY_API_SECRET:
        return (config.CLOUDINARY_CLOUD_NAME, config.CLOUDINARY_API_KEY,
                config.CLOUDINARY_API_SECRET)
    m = re.match(r"cloudinary://([^:]+):([^@]+)@(.+)", config.CLOUDINARY_URL)
    if m:
        return (m.group(3), m.group(1), m.group(2))  # cloud_name, key, secret
    return None


def enabled() -> bool:
    return _creds() is not None


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    import cloudinary

    cloud_name, api_key, api_secret = _creds()
    cloudinary.config(cloud_name=cloud_name, api_key=api_key, api_secret=api_secret, secure=True)
    _configured = True


def _local_path(filename: str, media_kind: str) -> Path:
    base = config.DATA_DIR / ("videos" if media_kind == "video" else "images")
    return base / filename


def cleanup_local(filename: str | None, media_kind: str = "image") -> None:
    """Delete a local media file (after it's been uploaded to the CDN)."""
    if not filename:
        return
    try:
        _local_path(filename, media_kind).unlink(missing_ok=True)
    except OSError:
        pass


def sweep_scratch(older_than_minutes: int = 30) -> int:
    """Delete stale scratch files (intermediate panels, orphaned renders). Returns count."""
    import time

    removed = 0
    cutoff = time.time() - older_than_minutes * 60
    for sub in ("images", "videos"):
        d = config.DATA_DIR / sub
        if not d.exists():
            continue
        for f in d.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                pass
    return removed


def upload_media(filename: str | None, media_kind: str = "image") -> str | None:
    """Upload a generated file to Cloudinary; return its secure URL (or None if disabled/failed)."""
    if not filename or not enabled():
        return None
    path = _local_path(filename, media_kind)
    if not path.exists():
        return None
    try:
        _ensure_configured()
        import cloudinary.uploader

        result = cloudinary.uploader.upload(
            str(path),
            resource_type="video" if media_kind == "video" else "image",
            folder=FOLDER,
            public_id=path.stem,
            overwrite=True,
        )
        return result["secure_url"]
    except Exception as exc:  # noqa: BLE001 — never let upload crash generation
        print(f"[media] Cloudinary upload failed for {filename}: {exc}")
        return None
