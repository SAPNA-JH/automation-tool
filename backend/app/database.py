"""Multi-tenant data layer.

Backends behind one API: Postgres when DATABASE_URL is set (production), else SQLite (local dev).
Tables:
  users     — Google identity
  accounts  — one studio per user (brand + niche + formats, stored as JSON)
  posts     — generated content, scoped by user_id

All SQL uses `?` placeholders; `_q()` rewrites to `%s` for Postgres. JSON columns are TEXT
in SQLite / JSONB in Postgres and go through `_dumps`/`_loads`.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from . import config

STATUSES = ("pending", "approved", "posted", "rejected")
IS_PG = bool(config.DATABASE_URL)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _q(sql: str) -> str:
    return sql.replace("?", "%s") if IS_PG else sql


def _dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _loads(val):
    if val is None or val == "":
        return None
    return val if isinstance(val, (dict, list)) else json.loads(val)


_pool = None


def _get_pool():
    """Lazily create a shared Postgres connection pool (reused across requests)."""
    global _pool
    if _pool is None:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        _pool = ConnectionPool(
            config.DATABASE_URL,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            # Recycle idle connections in the background before Neon (~5 min) drops them,
            # so requests get a live connection without a per-query validation round-trip.
            max_idle=120,
            max_lifetime=1800,
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def _connect():
    if IS_PG:
        # Borrow a live connection from the pool — no TLS handshake per query.
        # The pool commits on clean exit and rolls back on exception.
        with _get_pool().connection() as conn:
            yield conn
    else:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def _one(row):
    return dict(row) if row else None


def _scalar(row):
    if row is None:
        return None
    return list(row.values())[0] if isinstance(row, dict) else row[0]


def _columns(conn, table: str) -> set[str]:
    if IS_PG:
        rows = conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        ).fetchall()
        return {r["column_name"] for r in rows}
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db() -> None:
    json_type = "JSONB" if IS_PG else "TEXT"
    post_pk = "SERIAL PRIMARY KEY" if IS_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with _connect() as conn:
        # user ids are UUID strings (generated in Python), stored as TEXT in both backends.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          TEXT PRIMARY KEY,
                google_sub  TEXT UNIQUE,
                email       TEXT UNIQUE NOT NULL,
                name        TEXT NOT NULL DEFAULT '',
                picture     TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL
            )
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS accounts (
                user_id     TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                brand       {json_type} NOT NULL,
                categories  {json_type} NOT NULL,
                formats     {json_type} NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS posts (
                id           {post_pk},
                user_id      TEXT REFERENCES users(id) ON DELETE CASCADE,
                created_at   TEXT NOT NULL,
                theme        TEXT NOT NULL,
                image_prompt TEXT NOT NULL,
                image_file   TEXT,
                caption      TEXT NOT NULL,
                hashtags     TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'pending',
                category     TEXT NOT NULL DEFAULT '',
                post_type    TEXT NOT NULL DEFAULT 'single',
                media_kind   TEXT NOT NULL DEFAULT 'image',
                media_url    TEXT NOT NULL DEFAULT ''
            )
        """)
        # Legacy migration: add user_id to a posts table that predates multi-tenancy.
        if "user_id" not in _columns(conn, "posts"):
            conn.execute("ALTER TABLE posts ADD COLUMN user_id TEXT")
        # Plan + referral columns on users (infra for free/paid tiers).
        for col, ddl in (("plan", "TEXT NOT NULL DEFAULT 'free'"),
                         ("plan_expires_at", "TEXT"),
                         ("referral_code", "TEXT"),
                         ("referred_by", "TEXT")):
            if col not in _columns(conn, "users"):
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
        # Who referred whom (one reward per referred user).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referee_id   TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                referrer_id  TEXT NOT NULL,
                created_at   TEXT NOT NULL
            )
        """)
        # Per-user automation mode: 'auto' | 'semi' | 'manual'.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS automation (
                user_id    TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                mode       TEXT NOT NULL DEFAULT 'manual',
                auto_niche TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )
        """)
        if "auto_niche" not in _columns(conn, "automation"):
            conn.execute("ALTER TABLE automation ADD COLUMN auto_niche TEXT NOT NULL DEFAULT ''")
        # Records the Instagram media id once a post is published (proof + dedupe).
        if "ig_media_id" not in _columns(conn, "posts"):
            conn.execute("ALTER TABLE posts ADD COLUMN ig_media_id TEXT")
        # Per-user Meta app credentials for the OAuth flow (secret encrypted at rest).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS instagram_config (
                user_id        TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                app_id         TEXT NOT NULL DEFAULT '',
                app_secret_enc TEXT NOT NULL DEFAULT '',
                redirect_uri   TEXT NOT NULL DEFAULT '',
                updated_at     TEXT NOT NULL
            )
        """)
        # Per-user connected Instagram account (token encrypted at rest via app.crypto).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS instagram_accounts (
                user_id       TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                ig_user_id    TEXT NOT NULL,
                username      TEXT NOT NULL DEFAULT '',
                token_enc     TEXT NOT NULL,
                token_expires TEXT NOT NULL DEFAULT '',
                auto_post     INTEGER NOT NULL DEFAULT 0,
                post_hour     INTEGER NOT NULL DEFAULT 10,
                post_minute   INTEGER NOT NULL DEFAULT 0,
                frequency     TEXT NOT NULL DEFAULT 'daily',
                posts_per_day INTEGER NOT NULL DEFAULT 1,
                last_posted   TEXT NOT NULL DEFAULT '',
                connected_at  TEXT NOT NULL
            )
        """)
        # Migrations for instagram_accounts tables created before these columns existed.
        for col, ddl in (("frequency", "TEXT NOT NULL DEFAULT 'daily'"),
                         ("posts_per_day", "INTEGER NOT NULL DEFAULT 1"),
                         ("post_slots", "TEXT NOT NULL DEFAULT ''")):  # JSON list of "HH:MM" (IST)
            if col not in _columns(conn, "instagram_accounts"):
                conn.execute(f"ALTER TABLE instagram_accounts ADD COLUMN {col} {ddl}")
        if "ig_posted_at" not in _columns(conn, "posts"):
            conn.execute("ALTER TABLE posts ADD COLUMN ig_posted_at TEXT")
        # Niche preset library (seeded from code on first boot; see niches.seed()).
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS niche_presets (
                key         TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                emoji       TEXT NOT NULL DEFAULT '',
                tagline     TEXT NOT NULL DEFAULT '',
                accent      TEXT NOT NULL DEFAULT '#a855f7',
                brand       {json_type} NOT NULL,
                categories  {json_type} NOT NULL,
                sort_order  INTEGER NOT NULL DEFAULT 0
            )
        """)


# --------------------------------------------------------------------------
# Niche preset library
# --------------------------------------------------------------------------

def seed_niches(presets: list[dict], *, force: bool = False) -> int:
    """Populate the niche_presets table from code presets. Skips if already seeded."""
    with _connect() as conn:
        existing = int(_scalar(conn.execute("SELECT COUNT(*) FROM niche_presets").fetchone()) or 0)
        if existing and not force:
            return 0
        if force:
            conn.execute("DELETE FROM niche_presets")
        for i, p in enumerate(presets):
            conn.execute(
                _q("""INSERT INTO niche_presets (key, name, emoji, tagline, accent, brand,
                       categories, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""),
                (p["key"], p["name"], p.get("emoji", ""), p.get("tagline", ""),
                 p.get("accent", "#a855f7"), _dumps(p["brand"]), _dumps(p["categories"]), i),
            )
        return len(presets)


def list_niches() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM niche_presets ORDER BY sort_order").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["brand"] = _loads(d["brand"]) or {}
        d["categories"] = _loads(d["categories"]) or []
        out.append(d)
    return out


def get_niche(key: str) -> dict | None:
    with _connect() as conn:
        row = _one(conn.execute(_q("SELECT * FROM niche_presets WHERE key = ?"), (key,)).fetchone())
    if not row:
        return None
    row["brand"] = _loads(row["brand"]) or {}
    row["categories"] = _loads(row["categories"]) or []
    return row


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------

def get_user_by_email(email: str) -> dict | None:
    with _connect() as conn:
        return _one(conn.execute(_q("SELECT * FROM users WHERE email = ?"),
                                 (email.lower(),)).fetchone())


def get_user(user_id: str) -> dict | None:
    with _connect() as conn:
        return _one(conn.execute(_q("SELECT * FROM users WHERE id = ?"), (user_id,)).fetchone())


def upsert_user(*, google_sub: str, email: str, name: str = "", picture: str = "") -> dict:
    """Create or update a user by email; returns the row. New users get a UUID id."""
    email = email.lower()
    existing = get_user_by_email(email)
    with _connect() as conn:
        if existing:
            row = {**existing, "google_sub": google_sub or existing["google_sub"],
                   "name": name or existing["name"], "picture": picture or existing["picture"]}
            conn.execute(
                _q("UPDATE users SET google_sub = ?, name = ?, picture = ? WHERE id = ?"),
                (row["google_sub"], row["name"], row["picture"], existing["id"]),
            )
            return row
        row = {"id": str(uuid.uuid4()), "google_sub": google_sub, "email": email,
               "name": name, "picture": picture, "created_at": _now(),
               "plan": "free", "plan_expires_at": None,
               "referral_code": uuid.uuid4().hex[:8], "referred_by": None}
        conn.execute(
            _q("""INSERT INTO users (id, google_sub, email, name, picture, created_at,
                                     plan, referral_code)
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""),
            (row["id"], row["google_sub"], row["email"], row["name"], row["picture"],
             row["created_at"], row["plan"], row["referral_code"]),
        )
        return row


# --------------------------------------------------------------------------
# Plans & referrals
# --------------------------------------------------------------------------

def get_user_by_referral_code(code: str) -> dict | None:
    if not code:
        return None
    with _connect() as conn:
        return _one(conn.execute(_q("SELECT * FROM users WHERE referral_code = ?"),
                                 (code,)).fetchone())


def ensure_referral_code(user_id: str) -> str:
    """Backfill a referral code for users created before the column existed."""
    with _connect() as conn:
        row = conn.execute(_q("SELECT referral_code FROM users WHERE id = ?"),
                           (user_id,)).fetchone()
        code = (dict(row).get("referral_code") if row else None)
        if not code:
            code = uuid.uuid4().hex[:8]
            conn.execute(_q("UPDATE users SET referral_code = ? WHERE id = ?"), (code, user_id))
        return code


def set_referred_by(user_id: str, referrer_id: str) -> None:
    with _connect() as conn:
        conn.execute(_q("UPDATE users SET referred_by = ? WHERE id = ?"), (referrer_id, user_id))
        conn.execute(_q("INSERT INTO referrals (referee_id, referrer_id, created_at) "
                        "VALUES (?, ?, ?)"), (user_id, referrer_id, _now()))


def count_referrals(user_id: str) -> int:
    with _connect() as conn:
        row = conn.execute(_q("SELECT COUNT(*) FROM referrals WHERE referrer_id = ?"),
                           (user_id,)).fetchone()
        return int(_scalar(row) or 0)


def extend_plan(user_id: str, *, until_iso: str) -> None:
    """Grant/extend temporary Pro access up to until_iso (used for referral rewards)."""
    with _connect() as conn:
        conn.execute(_q("UPDATE users SET plan_expires_at = ? WHERE id = ?"),
                     (until_iso, user_id))


def set_plan(user_id: str, plan: str) -> None:
    with _connect() as conn:
        conn.execute(_q("UPDATE users SET plan = ? WHERE id = ?"), (plan, user_id))


def count_posts_since(user_id: str, since_iso: str, media_kind: str | None = None) -> int:
    sql = "SELECT COUNT(*) FROM posts WHERE user_id = ? AND created_at >= ?"
    params: list = [user_id, since_iso]
    if media_kind:
        sql += " AND media_kind = ?"; params.append(media_kind)
    with _connect() as conn:
        return int(_scalar(conn.execute(_q(sql), params).fetchone()) or 0)


def claim_orphan_posts(user_id: str) -> int:
    """Assign posts with no owner (legacy import) to this user. Returns count."""
    with _connect() as conn:
        cur = conn.execute(_q("UPDATE posts SET user_id = ? WHERE user_id IS NULL"), (user_id,))
        return getattr(cur, "rowcount", 0) or 0


# --------------------------------------------------------------------------
# Accounts (per-user brand + niche + formats)
# --------------------------------------------------------------------------

def get_account(user_id: str) -> dict | None:
    with _connect() as conn:
        row = _one(conn.execute(_q("SELECT * FROM accounts WHERE user_id = ?"),
                                (user_id,)).fetchone())
    if not row:
        return None
    return {
        "user_id": row["user_id"],
        "brand": _loads(row["brand"]) or {},
        "categories": _loads(row["categories"]) or [],
        "formats": _loads(row["formats"]) or {},
    }


def upsert_account(user_id: str, *, brand: dict, categories: list, formats: dict) -> None:
    exists = get_account(user_id) is not None
    with _connect() as conn:
        if exists:
            conn.execute(
                _q("""UPDATE accounts SET brand = ?, categories = ?, formats = ?, updated_at = ?
                      WHERE user_id = ?"""),
                (_dumps(brand), _dumps(categories), _dumps(formats), _now(), user_id),
            )
        else:
            conn.execute(
                _q("""INSERT INTO accounts (user_id, brand, categories, formats, updated_at)
                      VALUES (?, ?, ?, ?, ?)"""),
                (user_id, _dumps(brand), _dumps(categories), _dumps(formats), _now()),
            )


# --------------------------------------------------------------------------
# Posts (scoped by user_id)
# --------------------------------------------------------------------------

def create_post(
    *, user_id: str, theme: str, image_prompt: str, image_file: str | None,
    caption: str, hashtags: str, category: str = "", post_type: str = "single",
    media_kind: str = "image", media_url: str = "", created_at: str | None = None,
    status: str = "pending",
) -> int:
    values = (user_id, created_at or _now(), theme, image_prompt, image_file, caption,
              hashtags, status, category, post_type, media_kind, media_url)
    sql = """
        INSERT INTO posts (user_id, created_at, theme, image_prompt, image_file, caption,
                           hashtags, status, category, post_type, media_kind, media_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with _connect() as conn:
        if IS_PG:
            return int(conn.execute(_q(sql) + " RETURNING id", values).fetchone()["id"])
        return int(conn.execute(sql, values).lastrowid)


def list_posts(user_id: str, status: str | None = None, category: str | None = None,
               post_type: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM posts WHERE user_id = ?", [user_id]
    if status:
        sql += " AND status = ?"; params.append(status)
    if category:
        sql += " AND category = ?"; params.append(category)
    if post_type:
        sql += " AND post_type = ?"; params.append(post_type)
    if q:
        sql += " AND (theme LIKE ? OR caption LIKE ?)"; params += [f"%{q}%", f"%{q}%"]
    sql += " ORDER BY id DESC"
    with _connect() as conn:
        return [dict(r) for r in conn.execute(_q(sql), params).fetchall()]


def get_post(user_id: str, post_id: int) -> dict[str, Any] | None:
    with _connect() as conn:
        return _one(conn.execute(_q("SELECT * FROM posts WHERE id = ? AND user_id = ?"),
                                 (post_id, user_id)).fetchone())


def update_fields(user_id: str, post_id: int, **fields) -> None:
    allowed = {"caption", "hashtags", "status", "theme"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    if "status" in updates and updates["status"] not in STATUSES:
        raise ValueError(f"invalid status: {updates['status']}")
    cols = ", ".join(f"{k} = ?" for k in updates)
    with _connect() as conn:
        conn.execute(_q(f"UPDATE posts SET {cols} WHERE id = ? AND user_id = ?"),
                     (*updates.values(), post_id, user_id))


def set_status(user_id: str, post_id: int, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status}")
    with _connect() as conn:
        conn.execute(_q("UPDATE posts SET status = ? WHERE id = ? AND user_id = ?"),
                     (status, post_id, user_id))


def set_media_url(user_id: str, post_id: int, media_url: str) -> None:
    with _connect() as conn:
        conn.execute(_q("UPDATE posts SET media_url = ? WHERE id = ? AND user_id = ?"),
                     (media_url, post_id, user_id))


def update_content(user_id: str, post_id: int, *, image_prompt: str, image_file: str | None,
                   caption: str, hashtags: str, media_url: str = "") -> None:
    with _connect() as conn:
        conn.execute(_q("""
            UPDATE posts SET image_prompt = ?, image_file = ?, caption = ?, hashtags = ?,
                media_url = ?, status = 'pending'
            WHERE id = ? AND user_id = ?
        """), (image_prompt, image_file, caption, hashtags, media_url, post_id, user_id))


def delete_post(user_id: str, post_id: int) -> str | None:
    with _connect() as conn:
        row = conn.execute(_q("SELECT image_file FROM posts WHERE id = ? AND user_id = ?"),
                           (post_id, user_id)).fetchone()
        conn.execute(_q("DELETE FROM posts WHERE id = ? AND user_id = ?"), (post_id, user_id))
        return (dict(row)["image_file"] if row else None)


def count_recent_posts(user_id: str, since_iso: str) -> int:
    with _connect() as conn:
        row = conn.execute(
            _q("SELECT COUNT(*) FROM posts WHERE user_id = ? AND created_at >= ?"),
            (user_id, since_iso)).fetchone()
        return int(_scalar(row) or 0)


def next_publishable_post(user_id: str) -> dict[str, Any] | None:
    """The oldest approved post with hosted media that hasn't been published yet."""
    with _connect() as conn:
        return _one(conn.execute(_q(
            """SELECT * FROM posts
               WHERE user_id = ? AND status = 'approved'
                 AND media_url <> '' AND (ig_media_id IS NULL OR ig_media_id = '')
               ORDER BY id ASC LIMIT 1"""), (user_id,)).fetchone())


def mark_post_published(user_id: str, post_id: int, ig_media_id: str) -> None:
    with _connect() as conn:
        conn.execute(_q(
            """UPDATE posts SET ig_media_id = ?, ig_posted_at = ?, status = 'posted'
               WHERE id = ? AND user_id = ?"""),
            (ig_media_id, _now(), post_id, user_id))


def count_published_since(user_id: str, since_iso: str) -> int:
    with _connect() as conn:
        row = conn.execute(_q(
            """SELECT COUNT(*) FROM posts
               WHERE user_id = ? AND ig_posted_at IS NOT NULL AND ig_posted_at >= ?"""),
            (user_id, since_iso)).fetchone()
        return int(_scalar(row) or 0)


# --------------------------------------------------------------------------
# Instagram app credentials (per user; Meta app for the OAuth flow)
# --------------------------------------------------------------------------

def get_instagram_config(user_id: str) -> dict | None:
    with _connect() as conn:
        return _one(conn.execute(_q("SELECT * FROM instagram_config WHERE user_id = ?"),
                                 (user_id,)).fetchone())


def save_instagram_config(user_id: str, *, app_id: str, app_secret_enc: str,
                          redirect_uri: str) -> None:
    exists = get_instagram_config(user_id) is not None
    with _connect() as conn:
        if exists:
            conn.execute(_q(
                """UPDATE instagram_config
                   SET app_id = ?, app_secret_enc = ?, redirect_uri = ?, updated_at = ?
                   WHERE user_id = ?"""),
                (app_id, app_secret_enc, redirect_uri, _now(), user_id))
        else:
            conn.execute(_q(
                """INSERT INTO instagram_config
                   (user_id, app_id, app_secret_enc, redirect_uri, updated_at)
                   VALUES (?, ?, ?, ?, ?)"""),
                (user_id, app_id, app_secret_enc, redirect_uri, _now()))


# --------------------------------------------------------------------------
# Instagram connection (per user)
# --------------------------------------------------------------------------

def get_instagram(user_id: str) -> dict | None:
    with _connect() as conn:
        return _one(conn.execute(_q("SELECT * FROM instagram_accounts WHERE user_id = ?"),
                                 (user_id,)).fetchone())


def save_instagram(user_id: str, *, ig_user_id: str, username: str, token_enc: str,
                   token_expires: str) -> None:
    """Insert or replace the connection, preserving auto-post settings on reconnect."""
    existing = get_instagram(user_id)
    with _connect() as conn:
        if existing:
            conn.execute(_q(
                """UPDATE instagram_accounts
                   SET ig_user_id = ?, username = ?, token_enc = ?, token_expires = ?
                   WHERE user_id = ?"""),
                (ig_user_id, username, token_enc, token_expires, user_id))
        else:
            conn.execute(_q(
                """INSERT INTO instagram_accounts
                   (user_id, ig_user_id, username, token_enc, token_expires, connected_at)
                   VALUES (?, ?, ?, ?, ?, ?)"""),
                (user_id, ig_user_id, username, token_enc, token_expires, _now()))


def set_instagram_token(user_id: str, token_enc: str, token_expires: str) -> None:
    with _connect() as conn:
        conn.execute(_q(
            "UPDATE instagram_accounts SET token_enc = ?, token_expires = ? WHERE user_id = ?"),
            (token_enc, token_expires, user_id))


FREQUENCIES = ("daily", "weekdays", "every_2_days", "every_3_days", "weekly")


def update_instagram_settings(user_id: str, *, auto_post: bool | None = None,
                              post_hour: int | None = None,
                              post_minute: int | None = None,
                              frequency: str | None = None,
                              posts_per_day: int | None = None,
                              post_slots: list | None = None) -> None:
    sets, params = [], []
    if auto_post is not None:
        sets.append("auto_post = ?"); params.append(1 if auto_post else 0)
    if post_hour is not None:
        sets.append("post_hour = ?"); params.append(max(0, min(23, int(post_hour))))
    if post_minute is not None:
        sets.append("post_minute = ?"); params.append(max(0, min(59, int(post_minute))))
    if frequency is not None and frequency in FREQUENCIES:
        sets.append("frequency = ?"); params.append(frequency)
    if posts_per_day is not None:
        sets.append("posts_per_day = ?"); params.append(max(1, min(5, int(posts_per_day))))
    if post_slots is not None:
        # normalize to unique, sorted, valid "HH:MM" strings (max 6 as a spam-safety cap)
        clean = []
        for s in post_slots:
            try:
                h, m = str(s).split(":")
                h, m = int(h), int(m)
                if 0 <= h <= 23 and 0 <= m <= 59:
                    clean.append(f"{h:02d}:{m:02d}")
            except (ValueError, AttributeError):
                continue
        clean = sorted(set(clean))[:6]
        sets.append("post_slots = ?"); params.append(_dumps(clean))
    if not sets:
        return
    params.append(user_id)
    with _connect() as conn:
        conn.execute(_q(f"UPDATE instagram_accounts SET {', '.join(sets)} WHERE user_id = ?"),
                     params)


def mark_instagram_posted(user_id: str, at_iso: str) -> None:
    with _connect() as conn:
        conn.execute(_q("UPDATE instagram_accounts SET last_posted = ? WHERE user_id = ?"),
                     (at_iso, user_id))


def delete_instagram(user_id: str) -> None:
    with _connect() as conn:
        conn.execute(_q("DELETE FROM instagram_accounts WHERE user_id = ?"), (user_id,))


def list_autopost_instagram() -> list[dict]:
    """All connected accounts with auto-post enabled (for the background publisher)."""
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            _q("SELECT * FROM instagram_accounts WHERE auto_post = 1")).fetchall()]


def list_connected_instagram() -> list[dict]:
    """All connected accounts (posting is gated by automation mode, not a flag)."""
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            _q("SELECT * FROM instagram_accounts")).fetchall()]


# --------------------------------------------------------------------------
# Automation mode (per user)
# --------------------------------------------------------------------------

def get_automation(user_id: str) -> dict:
    with _connect() as conn:
        row = conn.execute(_q("SELECT mode, auto_niche FROM automation WHERE user_id = ?"),
                           (user_id,)).fetchone()
    if not row:
        return {"mode": "manual", "auto_niche": ""}
    d = dict(row)
    return {"mode": d.get("mode") or "manual", "auto_niche": d.get("auto_niche") or ""}


def get_automation_mode(user_id: str) -> str:
    return get_automation(user_id)["mode"]


def set_automation(user_id: str, *, mode: str | None = None,
                   auto_niche: str | None = None) -> None:
    cur = get_automation(user_id)
    new_mode = mode if mode is not None else cur["mode"]
    new_niche = auto_niche if auto_niche is not None else cur["auto_niche"]
    with _connect() as conn:
        exists = conn.execute(_q("SELECT 1 FROM automation WHERE user_id = ?"),
                              (user_id,)).fetchone()
        if exists:
            conn.execute(_q("UPDATE automation SET mode = ?, auto_niche = ?, updated_at = ? "
                            "WHERE user_id = ?"), (new_mode, new_niche, _now(), user_id))
        else:
            conn.execute(_q("INSERT INTO automation (user_id, mode, auto_niche, updated_at) "
                            "VALUES (?, ?, ?, ?)"), (user_id, new_mode, new_niche, _now()))


def _pairs(rows) -> dict:
    out = {}
    for r in rows:
        vals = list(r.values()) if isinstance(r, dict) else list(r)
        out[vals[0]] = vals[1]
    return out


def stats(user_id: str) -> dict[str, Any]:
    with _connect() as conn:
        by_status = _pairs(conn.execute(
            _q("SELECT status, COUNT(*) FROM posts WHERE user_id = ? GROUP BY status"),
            (user_id,)).fetchall())
        by_category = _pairs(conn.execute(
            _q("SELECT category, COUNT(*) FROM posts WHERE user_id = ? AND category != '' "
               "GROUP BY category"), (user_id,)).fetchall())
        by_type = _pairs(conn.execute(
            _q("SELECT post_type, COUNT(*) FROM posts WHERE user_id = ? GROUP BY post_type"),
            (user_id,)).fetchall())
        total = int(_scalar(conn.execute(
            _q("SELECT COUNT(*) FROM posts WHERE user_id = ?"), (user_id,)).fetchone()) or 0)
    return {"total": total, "by_status": by_status, "by_category": by_category,
            "by_type": by_type}
