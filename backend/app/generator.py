"""Orchestrates a full post for a user's studio: pick category + template, build, persist."""
from __future__ import annotations

import random
from secrets import choice

from . import composer, database, media
from .providers import captions, images, structured


def _find_category(categories: list[dict], name: str) -> dict | None:
    return next((c for c in categories if c.get("name") == name), None)


def _pick_category(categories: list[dict], name: str | None) -> dict | None:
    """Return the named category, else a weighted-random one (category['weight'], default 1)."""
    if name:
        chosen = _find_category(categories, name)
        if chosen:
            return chosen
    if not categories:
        return None
    weights = [max(0, c.get("weight", 1)) for c in categories]
    if sum(weights) <= 0:
        return choice(categories)
    return random.choices(categories, weights=weights, k=1)[0]


def _templates(formats: dict) -> list[str]:
    return formats.get("templates") or ["grid", "vs", "single"]


def _pick_template(formats: dict, name: str | None, allow_video: bool = True) -> str:
    options = _templates(formats)
    if name and name in options:
        return name
    if not allow_video:  # Free plan: never randomly pick a Reel
        options = [t for t in options if t not in VIDEO_DESIGNS] or options
    return choice(options)


def category_names(account: dict) -> list[str]:
    """Category names for the studio picker."""
    return [c.get("name", "") for c in account.get("categories", []) if c.get("name")]


def template_names(account: dict) -> list[str]:
    """Template names for the studio picker."""
    return _templates(account.get("formats", {}))


def _context(brand: dict, category: dict | None) -> dict:
    """Brand info enriched with the current category's angle, passed to the AI providers."""
    ctx = dict(brand)
    if category:
        ctx["category"] = category.get("name", "")
        ctx["angle"] = category.get("description", "")
    return ctx


GRID_DESIGNS = ("grid", "grid-light", "grid-list", "grid-polaroid", "grid-steps",
                "grid-checklist", "grid-neon", "grid-mag", "grid-ranking")
VS_DESIGNS = ("vs", "vs-split", "this-or-that", "before-after")
OVERLAY_DESIGNS = ("overlay-classic", "overlay-center", "overlay-band",
                   "overlay-tweet", "overlay-polaroid", "overlay-editorial")
# Single-card formats: design -> the kind of copy the LLM writes for it
CARD_KINDS = {
    "quote-serif": "quote",
    "quote-neon": "quote",
    "did-you-know": "fact",
    "affirmation": "affirmation",
    "qna-sticker": "question",
}
STAT_DESIGNS = ("stat-hero",)
DEFINITION_DESIGNS = ("definition-card",)
VIDEO_DESIGNS = ("reel-quote", "reel-slides", "reel-facts", "reel-story", "reel-countdown", "reel-vs")

FAMILIES = [
    {"key": "grid", "label": "Grid layouts", "designs": list(GRID_DESIGNS)},
    {"key": "vs", "label": "Comparisons", "designs": list(VS_DESIGNS)},
    {"key": "overlay", "label": "Overlay posts", "designs": list(OVERLAY_DESIGNS)},
    {"key": "card", "label": "Cards & quotes", "designs": list(CARD_KINDS)},
    {"key": "data", "label": "Data & definitions", "designs": list(STAT_DESIGNS + DEFINITION_DESIGNS)},
    {"key": "video", "label": "Reels", "designs": list(VIDEO_DESIGNS)},
]


def _build(theme: str, ctx: dict, brand: dict, formats: dict, template: str):
    """Build the post image + copy for a template. Falls back to a single image on failure.

    Returns (used_template, image_file, caption, hashtags).
    """
    try:
        if template in GRID_DESIGNS:
            spec = structured.generate_grid(theme, ctx, n=formats.get("grid_items", 6))
            image_file = composer.compose(spec, brand, design=template)
            return template, image_file, spec["caption"], spec["hashtags"]
        if template in VS_DESIGNS:
            spec = structured.generate_vs(theme, ctx, n=formats.get("vs_rows", 5))
            return template, composer.compose(spec, brand, design=template), spec["caption"], spec["hashtags"]
        if template in OVERLAY_DESIGNS:
            caption, hashtags, overlay = captions.generate_caption(theme, ctx)
            image_prompt = images.build_image_prompt(theme, ctx)
            image_file = images.generate_raw(image_prompt)
            poster = composer.compose_overlay(
                template, image_file, overlay or theme, brand, category=ctx.get("category", "")
            )
            return template, poster, caption, hashtags
        if template in CARD_KINDS:
            spec = structured.generate_card(theme, ctx, kind=CARD_KINDS[template])
            return template, composer.compose(spec, brand, design=template), spec["caption"], spec["hashtags"]
        if template in STAT_DESIGNS:
            spec = structured.generate_stat(theme, ctx)
            return template, composer.compose(spec, brand, design=template), spec["caption"], spec["hashtags"]
        if template in DEFINITION_DESIGNS:
            spec = structured.generate_definition(theme, ctx)
            return template, composer.compose(spec, brand, design=template), spec["caption"], spec["hashtags"]
        if template in VIDEO_DESIGNS:
            from .video import templates as video_templates
            filename, caption, hashtags = video_templates.build(template, theme, ctx, brand)
            return template, filename, caption, hashtags
    except Exception as exc:  # noqa: BLE001
        print(f"[generator] {template} build failed ({exc}); falling back to single image")

    # Single moody image with a tagline overlay (also the universal fallback).
    caption, hashtags, overlay = captions.generate_caption(theme, ctx)
    image_prompt = images.build_image_prompt(theme, ctx)
    image_file = images.generate_image(theme, image_prompt, overlay_text=overlay or theme)
    return "single", image_file, caption, hashtags


def generate_post(
    user_id: int,
    account: dict,
    category_name: str | None = None,
    template: str | None = None,
    theme: str | None = None,
    allow_video: bool = True,
) -> int:
    """Generate one new post for `user_id`'s studio and return its id."""
    brand = account.get("brand", {})
    categories = account.get("categories", [])
    formats = account.get("formats", {})

    category = _pick_category(categories, category_name)
    if not theme:
        themes = category.get("themes") if category else None
        theme = choice(themes) if themes else "Modern life feels off"
    chosen_template = _pick_template(formats, template, allow_video=allow_video)

    ctx = _context(brand, category)
    used, image_file, caption, hashtags = _build(theme, ctx, brand, formats, chosen_template)

    media_kind = "video" if used in VIDEO_DESIGNS else "image"
    media_url = media.upload_media(image_file, media_kind) or ""
    if media_url:
        media.cleanup_local(image_file, media_kind)  # uploaded to CDN → free local disk
    media.sweep_scratch()  # clear intermediate panel/render leftovers

    cat_name = category["name"] if category else ""
    post_id = database.create_post(
        user_id=user_id,
        theme=theme,
        image_prompt=f"{used}: {theme}",
        image_file=image_file,
        caption=caption,
        hashtags=hashtags,
        category=cat_name,
        post_type=used,
        media_kind=media_kind,
        media_url=media_url,
    )
    print(f"[generator] user {user_id} created post #{post_id}: [{cat_name}/{used}] {theme}")
    return post_id


def regenerate_post(user_id: int, account: dict, post_id: int) -> None:
    """Re-run generation for one of the user's posts, keeping its theme/category/template."""
    post = database.get_post(user_id, post_id)
    if not post:
        raise ValueError(f"post {post_id} not found")

    brand = account.get("brand", {})
    formats = account.get("formats", {})
    theme = post["theme"]
    category = _find_category(account.get("categories", []), post.get("category", ""))
    ctx = _context(brand, category)

    used, image_file, caption, hashtags = _build(
        theme, ctx, brand, formats, post.get("post_type", "single")
    )
    media_kind = "video" if used in VIDEO_DESIGNS else "image"
    media_url = media.upload_media(image_file, media_kind) or ""
    if media_url:
        media.cleanup_local(image_file, media_kind)
    media.sweep_scratch()
    database.update_content(
        user_id, post_id,
        image_prompt=f"{post.get('post_type', 'single')}: {theme}",
        image_file=image_file,
        caption=caption,
        hashtags=hashtags,
        media_url=media_url,
    )
    print(f"[generator] user {user_id} regenerated post #{post_id}")
