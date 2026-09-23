"""Video template registry — parallels composer's _DESIGNS for poster templates."""
from __future__ import annotations

from PIL import Image, ImageDraw

from .. import composer, config
from . import assemble, scripts

VIDEO_DESIGNS = ("reel-quote", "reel-slides", "reel-facts", "reel-story", "reel-countdown", "reel-vs")


def build(template: str, theme: str, ctx: dict, brand: dict) -> tuple[str, str, str]:
    """Generate script + render video. Returns (mp4_filename, caption, hashtags)."""
    # Memory guard: bail before ffmpeg if the container is already low on RAM, so the
    # caller degrades to an image post rather than OOM-killing the whole instance.
    if config.VIDEO_MIN_FREE_MB > 0:
        free = assemble.available_mb()
        if free is not None and free < config.VIDEO_MIN_FREE_MB:
            raise RuntimeError(
                f"low memory ({free:.0f}MB free < {config.VIDEO_MIN_FREE_MB}MB) — "
                f"skipping video render")

    visual_style = ctx.get("visual_style", brand.get("visual_style", "moody cinematic, no text"))

    if template == "reel-quote":
        spec = scripts.generate_quote_reel(theme, ctx)
        bg_prompt = (f"An evocative, conceptual vertical image representing: {theme}. "
                     f"Visual style: {visual_style}. No text.")
        filename = assemble.render_quote_reel(spec, brand, bg_prompt)
    elif template == "reel-slides":
        spec = scripts.generate_slides_reel(theme, ctx)
        filename = assemble.render_slides_reel(spec, brand, visual_style)
    elif template == "reel-facts":
        spec = scripts.generate_facts_reel(theme, ctx)
        filename = assemble.render_facts_reel(spec, brand, visual_style)
    elif template == "reel-story":
        spec = scripts.generate_story_reel(theme, ctx)
        filename = assemble.render_story_reel(spec, brand, visual_style)
    elif template == "reel-countdown":
        spec = scripts.generate_countdown_reel(theme, ctx)
        filename = assemble.render_countdown_reel(spec, brand, visual_style)
    elif template == "reel-vs":
        spec = scripts.generate_vs_reel(theme, ctx)
        filename = assemble.render_vs_reel(spec, brand, visual_style)
    else:
        raise ValueError(f"unknown video template: {template}")
    return filename, spec["caption"], spec["hashtags"]


# ---------------------------------------------------------------------------
# Static gallery previews (poster frames with a play badge — no render cost)
# ---------------------------------------------------------------------------

_PREVIEW_COPY = {
    "reel-quote": ("Kinetic quote", "lines fade in over a slow-zooming image"),
    "reel-slides": ("Slideshow reel", "your listicle panels as animated slides"),
    "reel-facts": ("Narrated facts", "voiceover + word-timed captions + b-roll"),
    "reel-story": ("POV story", "short lines revealed one at a time, moody"),
    "reel-countdown": ("Top-N countdown", "ranks count down from #N to #1"),
    "reel-vs": ("This vs That", "split-screen comparison, side by side"),
}


def render_video_previews(brand: dict) -> None:
    accent = composer._hex(brand.get("accent", ""))
    composer.PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for design, (title, sub) in _PREVIEW_COPY.items():
        w, h = 1080, 1350
        img = composer._gradient_tile((w, h))
        d = ImageDraw.Draw(img)
        # play badge
        cx, cy, r = w // 2, h // 2 - 120, 110
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 255))
        d.polygon([(cx - 34, cy - 52), (cx - 34, cy + 52), (cx + 56, cy)], fill=accent)
        tf = composer._font(64, bold=True)
        d.text(((w - d.textlength(title, font=tf)) / 2, cy + r + 60), title,
               font=tf, fill=(245, 245, 250))
        sf = composer._font(34)
        wrapped = composer._wrap(d, sub, sf, w - 240)
        bb = d.multiline_textbbox((0, 0), wrapped, font=sf, spacing=6)
        d.multiline_text(((w - (bb[2] - bb[0])) / 2, cy + r + 150), wrapped,
                         font=sf, fill=(185, 185, 200), spacing=6, align="center")
        badge = "9:16 REEL"
        bf = composer._font(30, bold=True)
        bw = d.textlength(badge, font=bf)
        d.rounded_rectangle([(w - bw) / 2 - 24, h - 190, (w + bw) / 2 + 24, h - 130],
                            radius=14, fill=accent)
        d.text(((w - bw) / 2, h - 178), badge, font=bf, fill=(255, 255, 255))
        img.save(composer.PREVIEW_DIR / f"{design}.png")
