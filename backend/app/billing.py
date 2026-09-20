"""Plans, quotas and referral rewards.

Infra only — no payment integration yet. A user's *effective* plan is Pro if their
base plan is 'pro' OR they hold unexpired temporary Pro (plan_expires_at), which is
how referral rewards are granted. Limits live here (env-tunable via config); usage is
derived from the posts table so there's no separate meter to keep in sync.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from . import config, database

FREE, PRO = "free", "pro"

PLANS = {
    FREE: {
        "key": FREE, "name": "Free", "price": 0,
        "limits": {
            "posts_per_month": config.FREE_POSTS_PER_MONTH,
            "reels": False,
            "auto_post": False,
            "posts_per_day": config.FREE_POSTS_PER_DAY,
        },
    },
    PRO: {
        "key": PRO, "name": "Pro", "price": None,  # not purchasable yet
        "limits": {
            "posts_per_month": config.PRO_POSTS_PER_MONTH,
            "reels": True,
            "auto_post": True,
            "posts_per_day": config.PRO_POSTS_PER_DAY,
        },
    },
}


class PlanLimitError(Exception):
    """Raised when an action exceeds the user's plan. Carries an HTTP status."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def effective_plan(user: dict) -> str:
    # Pro is purely plan-based: the `plan` column (permanent) or a live plan_expires_at
    # (temporary, e.g. referral reward). No email is privileged.
    if (user.get("plan") or FREE) == PRO:
        return PRO
    exp = user.get("plan_expires_at")
    if exp:
        try:
            if datetime.fromisoformat(exp) > _now():
                return PRO  # temporary Pro (e.g. referral reward)
        except (ValueError, TypeError):
            pass
    return FREE


def limits(user: dict) -> dict:
    return PLANS[effective_plan(user)]["limits"]


def _month_start_iso() -> str:
    return _now().replace(day=1, hour=0, minute=0, second=0,
                          microsecond=0).isoformat(timespec="seconds")


def usage(user_id: str) -> dict:
    since = _month_start_iso()
    return {
        "posts": database.count_posts_since(user_id, since),
        "reels": database.count_posts_since(user_id, since, media_kind="video"),
    }


def status(user: dict) -> dict:
    plan = effective_plan(user)
    lim = PLANS[plan]["limits"]
    use = usage(user["id"])
    return {
        "plan": plan,
        "base_plan": user.get("plan") or FREE,
        "plan_expires_at": user.get("plan_expires_at"),
        "limits": lim,
        "usage": use,
        "remaining_posts": max(0, lim["posts_per_month"] - use["posts"]),
        "referral_code": user.get("referral_code") or "",
        "referrals": database.count_referrals(user["id"]),
        "reward_days": config.REFERRAL_REWARD_DAYS,
    }


def check_generate(user: dict, *, count: int, is_reel: bool) -> None:
    """Gate a generation request. Raises PlanLimitError if not allowed."""
    lim = limits(user)
    if is_reel and not lim["reels"]:
        raise PlanLimitError(403, "Reels are a Pro feature — upgrade to generate video.")
    used = usage(user["id"])["posts"]
    cap = lim["posts_per_month"]
    if used + count > cap:
        raise PlanLimitError(
            402, f"Monthly limit reached ({cap} posts). It resets on the 1st, "
                 f"or earn Pro by referring friends.")


def allows_reels(user: dict) -> bool:
    return bool(limits(user)["reels"])


def max_posts_per_day(user: dict) -> int:
    return int(limits(user)["posts_per_day"])


def grant_referral_reward(referrer: dict) -> None:
    """Extend the referrer's temporary Pro by REFERRAL_REWARD_DAYS (stacking on any
    existing grant that's still in the future)."""
    base = _now()
    existing = referrer.get("plan_expires_at")
    if existing:
        try:
            cur = datetime.fromisoformat(existing)
            if cur > base:
                base = cur
        except (ValueError, TypeError):
            pass
    until = (base + timedelta(days=config.REFERRAL_REWARD_DAYS)).isoformat(timespec="seconds")
    database.extend_plan(referrer["id"], until_iso=until)


def apply_referral(new_user: dict, code: str) -> bool:
    """Credit a referral: link new_user to the code's owner and reward the referrer.

    Returns True if applied. No-op (False) on self-referral, unknown code, or if the
    user was already referred.
    """
    if not code or new_user.get("referred_by"):
        return False
    referrer = database.get_user_by_referral_code(code.strip())
    if not referrer or referrer["id"] == new_user["id"]:
        return False
    database.set_referred_by(new_user["id"], referrer["id"])
    grant_referral_reward(referrer)
    return True
