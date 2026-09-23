"""LLM-generated reel scripts (specs the assembler renders)."""
from __future__ import annotations

from ..providers import llm, structured

MOODS = ("calm", "dark", "hopeful", "upbeat")

_QUOTE_SYSTEM = (
    "You write a short kinetic-text Instagram Reel for the given brand and theme.\n"
    "Produce: lines — exactly 4 short text lines (3-9 words each) that build ONE idea with a "
    "twist or emotional payoff on the final line; shown one after another on screen. "
    "music_mood: one of calm|dark|hopeful|upbeat. caption: 1-2 sentences. "
    "hashtags: 8-12 lowercase.\n"
    'Respond ONLY as JSON: {"lines":["...","...","...","..."],"music_mood":"...",'
    '"caption":"...","hashtags":["a","b"]}'
)

_FACTS_SYSTEM = (
    "You write a narrated Instagram Reel script for the given brand and theme.\n"
    "Produce: hook — an arresting opening line (max 12 words, spoken first). "
    "scenes — exactly 3 scenes, each: text (1-2 spoken sentences, conversational, ~20 words) "
    "and visual (a concrete cinematic shot description for the scene background, no text in "
    "scene). outro — a spoken closing line with a soft CTA (max 12 words). "
    "music_mood: calm|dark|hopeful|upbeat. voice: en|en-in|hi (hi only if the brand voice is "
    "Hinglish/Hindi). caption: 1-2 sentences. hashtags: 8-12 lowercase.\n"
    'Respond ONLY as JSON: {"hook":"...","scenes":[{"text":"...","visual":"..."}],'
    '"outro":"...","music_mood":"...","voice":"en","caption":"...","hashtags":["a","b"]}'
)


def _mood(value: str) -> str:
    return value if value in MOODS else "calm"


def generate_quote_reel(theme: str, brand: dict) -> dict:
    data = structured._extract_json(
        llm.chat_json(_QUOTE_SYSTEM, structured._user_prompt(theme, brand))
    )
    lines = [str(l).strip() for l in data.get("lines", []) if str(l).strip()][:5]
    if len(lines) < 3:
        raise ValueError("quote reel returned too few lines")
    return {
        "type": "reel-quote",
        "lines": lines,
        "music_mood": _mood(str(data.get("music_mood", "calm"))),
        "caption": str(data.get("caption", "")).strip(),
        "hashtags": structured._hashtags(data.get("hashtags", [])),
    }


def generate_slides_reel(theme: str, brand: dict, n: int = 5) -> dict:
    """Slideshow reel reuses the grid content generator — one panel per slide."""
    grid = structured.generate_grid(theme, brand, n=n)
    return {
        "type": "reel-slides",
        "title": grid["title"],
        "items": grid["items"],
        "cta": grid.get("cta", ""),
        "music_mood": "dark" if "glitch" in str(brand.get("niche", "")).lower() else "upbeat",
        "caption": grid["caption"],
        "hashtags": grid["hashtags"],
    }


_STORY_SYSTEM = (
    "You write a first-person POV micro-story Instagram Reel for the given brand and theme.\n"
    "Produce: lines — 5 to 7 very short lines (3-9 words each) that tell ONE tiny story in "
    "sequence with an emotional turn on the final line; each shown ALONE on screen, one at a "
    "time. The first line should read like a relatable 'POV:' hook. "
    "music_mood: one of calm|dark|hopeful|upbeat. caption: 1-2 sentences. hashtags: 8-12 "
    "lowercase.\n"
    'Respond ONLY as JSON: {"lines":["...","..."],"music_mood":"...","caption":"...",'
    '"hashtags":["a","b"]}'
)


def generate_story_reel(theme: str, brand: dict) -> dict:
    """POV micro-story: short lines revealed one at a time over a moody clip."""
    data = structured._extract_json(
        llm.chat_json(_STORY_SYSTEM, structured._user_prompt(theme, brand))
    )
    lines = [str(l).strip() for l in data.get("lines", []) if str(l).strip()][:7]
    if len(lines) < 4:
        raise ValueError("story reel returned too few lines")
    return {
        "type": "reel-story",
        "lines": lines,
        "music_mood": _mood(str(data.get("music_mood", "calm"))),
        "caption": str(data.get("caption", "")).strip(),
        "hashtags": structured._hashtags(data.get("hashtags", [])),
    }


def generate_countdown_reel(theme: str, brand: dict, n: int = 5) -> dict:
    """Top-N countdown reel — reuses the grid generator, played high→low for suspense."""
    grid = structured.generate_grid(theme, brand, n=n)
    return {
        "type": "reel-countdown",
        "title": grid["title"],
        "items": grid["items"],
        "cta": grid.get("cta", ""),
        "music_mood": "upbeat",
        "caption": grid["caption"],
        "hashtags": grid["hashtags"],
    }


def generate_vs_reel(theme: str, brand: dict, n: int = 3) -> dict:
    """This-or-That comparison reel — reuses the VS content generator."""
    vs = structured.generate_vs(theme, brand, n=n)
    return {
        "type": "reel-vs",
        "title": vs["title"],
        "left_title": vs["left_title"],
        "right_title": vs["right_title"],
        "left": vs["left"],
        "right": vs["right"],
        "cta": vs.get("cta", ""),
        "music_mood": "dark",
        "caption": vs["caption"],
        "hashtags": vs["hashtags"],
    }


def generate_facts_reel(theme: str, brand: dict) -> dict:
    data = structured._extract_json(
        llm.chat_json(_FACTS_SYSTEM, structured._user_prompt(theme, brand))
    )
    scenes = []
    for s in data.get("scenes", []):
        text = str(s.get("text", "")).strip()
        if text:
            scenes.append({"text": text, "visual": str(s.get("visual", "")).strip() or text})
    if not data.get("hook") or len(scenes) < 2:
        raise ValueError("facts reel returned incomplete script")
    return {
        "type": "reel-facts",
        "hook": str(data["hook"]).strip(),
        "scenes": scenes[:4],
        "outro": str(data.get("outro", "")).strip(),
        "voice": str(data.get("voice", "en")).strip() or "en",
        "music_mood": _mood(str(data.get("music_mood", "calm"))),
        "caption": str(data.get("caption", "")).strip(),
        "hashtags": structured._hashtags(data.get("hashtags", [])),
    }
