"""Caption + hashtag + overlay-tagline generation, on top of the shared llm.chat()."""
from __future__ import annotations

import json
import re

from .. import config
from . import llm

_SYSTEM = (
    "You are a creative copywriter for a moody, honest Instagram account about the glitches "
    "of modern life. For the given theme, produce three things:\n"
    "1. overlay: a punchy, poetic TAGLINE to display ON the image — roughly 6 to 14 words, "
    "evocative and self-contained so that reading it alone captures the whole post. Original and "
    "creative, not a cliche. No hashtags, no emojis, no surrounding quotation marks.\n"
    "2. caption: a 1-3 sentence Instagram caption that deepens the idea, with at most 1 emoji.\n"
    "3. hashtags: 8-12 relevant lowercase hashtags.\n"
    'Respond ONLY as JSON: {"overlay": "...", "caption": "...", "hashtags": ["tag1", "tag2"]}'
)


def _build_prompt(theme: str, brand: dict) -> str:
    lines = [f"Theme: {theme}"]
    if brand.get("category"):
        lines.append(f"Category: {brand['category']}")
    if brand.get("angle"):
        lines.append(f"Angle & tone: {brand['angle']}")
    lines += [
        f"Niche: {brand.get('niche', '')}",
        f"Voice: {brand.get('voice', '')}",
        f"Audience: {brand.get('audience', '')}",
    ]
    return "\n".join(lines)


def _parse(text: str) -> tuple[str, str, str]:
    """Pull (caption, hashtags, overlay) out of a model response (tolerant of stray prose)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            caption = str(data.get("caption", "")).strip()
            overlay = str(data.get("overlay", "")).strip().strip('"')
            tags = data.get("hashtags", [])
            if isinstance(tags, list):
                hashtags = " ".join(t if str(t).startswith("#") else f"#{t}" for t in tags)
            else:
                hashtags = str(tags)
            if caption:
                return caption, hashtags.strip(), overlay
        except json.JSONDecodeError:
            pass
    # Couldn't parse structured output — fall back to raw text as the caption.
    return text.strip(), "", ""


def _via_template(theme: str, brand: dict) -> tuple[str, str, str]:
    """Zero-dependency fallback so the app works with no API keys."""
    caption = f"{theme}.\n\nSome glitches don't get fixed — they just get felt."
    stop = {"the", "and", "for", "with", "you", "your", "are", "but", "not", "was"}
    words = re.sub(r"[^a-z0-9 ]", "", theme.lower()).split()
    seed = [w for w in words if len(w) > 3 and w not in stop]
    base = ["glitchlife", "modernlife", "rawthoughts", "honestreflections", "overstimulated"]
    tags = base + seed[:4]
    hashtags = " ".join(f"#{t}" for t in dict.fromkeys(tags))
    return caption, hashtags, theme  # overlay falls back to the theme


def generate_caption(theme: str, brand: dict) -> tuple[str, str, str]:
    """Return (caption, hashtags, overlay). Uses the best provider, degrades safely."""
    if config.caption_provider() != "template":
        try:
            return _parse(llm.chat(_SYSTEM, _build_prompt(theme, brand)))
        except Exception as exc:  # noqa: BLE001 — never let generation crash the app
            print(f"[captions] generation failed ({exc}); using template fallback")
    return _via_template(theme, brand)
