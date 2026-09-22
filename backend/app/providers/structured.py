"""Generate structured infographic specs (card-grid + VS) via the shared LLM.

Each returns a dict the composer knows how to lay out. The AI never renders text into
images — it only supplies a short `image` description per panel; our composer draws all copy.
"""
from __future__ import annotations

import json
import re

from . import llm

_GRID_SYSTEM = (
    "You design a structured Instagram listicle infographic for a moody, honest brand about the "
    "glitches of modern life. Given a theme, produce a scroll-stopping list of {n} points.\n"
    "Rules:\n"
    "- title: punchy, max 6 words. A '{n} Signs...', '{n} Ways...', or '{n} Reasons...' style works well.\n"
    "- items: exactly {n}. Each has: label (a sharp phrase, MAX 6 words, no period) and image "
    "(a concrete, literal visual scene to illustrate it — moody cinematic photography, a person or "
    "object, NO text in the scene).\n"
    "- cta: a short footer line, max 5 words (e.g. 'which one hit?').\n"
    "- caption: 1-3 sentence Instagram caption, at most 1 emoji.\n"
    "- hashtags: 8-12 lowercase hashtags.\n"
    'Respond ONLY as JSON: {{"title":"...","items":[{{"label":"...","image":"..."}}],'
    '"cta":"...","caption":"...","hashtags":["a","b"]}}'
)

_VS_SYSTEM = (
    "You design a VS comparison Instagram infographic for a moody, honest brand about modern life. "
    "Contrast the unhealthy modern habit (THE GLITCH) with the healthier alternative (THE REBOOT) "
    "for the given theme, {n} rows each.\n"
    "Rules:\n"
    "- title: punchy, max 6 words.\n"
    "- left_title: 2-3 words for the bad column (e.g. 'The Glitch').\n"
    "- right_title: 2-3 words for the good column (e.g. 'The Reboot').\n"
    "- left / right: exactly {n} items each. Each has: label (MAX 5 words, no period) and image "
    "(a concrete literal visual scene, moody cinematic, NO text). Row i of left and right should "
    "be opposites.\n"
    "- cta: short footer line, max 5 words.\n"
    "- caption: 1-3 sentence caption, at most 1 emoji.\n"
    "- hashtags: 8-12 lowercase hashtags.\n"
    'Respond ONLY as JSON: {{"title":"...","left_title":"...","right_title":"...",'
    '"left":[{{"label":"...","image":"..."}}],"right":[{{"label":"...","image":"..."}}],'
    '"cta":"...","caption":"...","hashtags":["a","b"]}}'
)


def _user_prompt(theme: str, brand: dict) -> str:
    lines = [f"Theme: {theme}"]
    if brand.get("category"):
        lines.append(f"Category: {brand['category']}")
    if brand.get("angle"):
        lines.append(f"Angle & tone: {brand['angle']}")
    lines += [
        f"Voice: {brand.get('voice', '')}",
        f"Audience: {brand.get('audience', '')}",
    ]
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    # Fast path: whole response is JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Otherwise scan for the first balanced {...} block (avoids greedy over-capture).
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in model response")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("no balanced JSON object in model response")


def _norm_items(raw: list, n: int) -> list[dict]:
    items = []
    for it in raw or []:
        label = str(it.get("label", "")).strip().strip('"')
        image = str(it.get("image", "")).strip() or label
        if label:
            items.append({"label": label, "image": image})
    return items[:n]


def generate_grid(theme: str, brand: dict, n: int = 6) -> dict:
    text = llm.chat_json(_GRID_SYSTEM.format(n=n), _user_prompt(theme, brand))
    data = _extract_json(text)
    items = _norm_items(data.get("items", []), n)
    if len(items) < 3:
        raise ValueError(f"grid returned too few items ({len(items)})")
    return {
        "type": "grid",
        "title": str(data.get("title", theme)).strip().strip('"'),
        "items": items,
        "cta": str(data.get("cta", "")).strip().strip('"'),
        "caption": str(data.get("caption", "")).strip(),
        "hashtags": _hashtags(data.get("hashtags", [])),
    }


def generate_vs(theme: str, brand: dict, n: int = 5) -> dict:
    text = llm.chat_json(_VS_SYSTEM.format(n=n), _user_prompt(theme, brand))
    data = _extract_json(text)
    left = _norm_items(data.get("left", []), n)
    right = _norm_items(data.get("right", []), n)
    rows = min(len(left), len(right))
    if rows < 3:
        raise ValueError(f"vs returned too few rows ({rows})")
    return {
        "type": "vs",
        "title": str(data.get("title", theme)).strip().strip('"'),
        "left_title": str(data.get("left_title", "The Glitch")).strip().strip('"'),
        "right_title": str(data.get("right_title", "The Reboot")).strip().strip('"'),
        "left": left[:rows],
        "right": right[:rows],
        "cta": str(data.get("cta", "")).strip().strip('"'),
        "caption": str(data.get("caption", "")).strip(),
        "hashtags": _hashtags(data.get("hashtags", [])),
    }


def _hashtags(tags) -> str:
    if isinstance(tags, list):
        return " ".join(t if str(t).startswith("#") else f"#{t}" for t in tags)
    return str(tags)


# --------------------------------------------------------------------------
# Single-card formats: quote / fact / affirmation / question
# --------------------------------------------------------------------------

_CARD_BRIEFS = {
    "quote": (
        "an original, striking QUOTE — aphoristic, quotable, no cliches. "
        "kicker: 2-3 word eyebrow (e.g. 'MODERN WISDOM'). headline: the quote itself, 8-25 words. "
        "body: empty string. attribution: the brand handle or a fitting persona name."
    ),
    "fact": (
        "a surprising, TRUE and widely-reported FACT relevant to the theme. "
        "kicker: 'DID YOU KNOW?'. headline: the fact in 10-25 words. "
        "body: one line of extra context. attribution: the general source (e.g. 'sleep research')."
        " Never invent precise numbers; prefer well-established findings."
    ),
    "affirmation": (
        "a gentle, grounding AFFIRMATION in first person. "
        "kicker: 2-3 soft words (e.g. 'A REMINDER'). headline: the affirmation, 6-18 words, "
        "warm but not saccharine. body: empty. attribution: empty."
    ),
    "question": (
        "a reflective QUESTION that makes people stop and answer in the comments. "
        "kicker: 'ASK YOURSELF'. headline: the question, 6-20 words. "
        "body: empty. attribution: empty."
    ),
}

_CARD_SYSTEM = (
    "You write a single-card Instagram post for the given brand and theme. Produce {brief}\n"
    "Also: cta (short footer line, max 5 words, may be ''), caption (1-3 sentences, max 1 emoji), "
    "hashtags (8-12 lowercase).\n"
    'Respond ONLY as JSON: {{"kicker":"...","headline":"...","body":"...","attribution":"...",'
    '"cta":"...","caption":"...","hashtags":["a","b"]}}'
)


def generate_card(theme: str, brand: dict, kind: str = "quote") -> dict:
    brief = _CARD_BRIEFS.get(kind, _CARD_BRIEFS["quote"])
    text = llm.chat_json(_CARD_SYSTEM.format(brief=brief), _user_prompt(theme, brand))
    data = _extract_json(text)
    headline = str(data.get("headline", "")).strip().strip('"')
    if not headline:
        raise ValueError("card returned no headline")
    return {
        "type": "card",
        "kind": kind,
        "kicker": str(data.get("kicker", "")).strip().strip('"'),
        "headline": headline,
        "body": str(data.get("body", "")).strip(),
        "attribution": str(data.get("attribution", "")).strip().strip('"'),
        "cta": str(data.get("cta", "")).strip().strip('"'),
        "category": brand.get("category", ""),
        "caption": str(data.get("caption", "")).strip(),
        "hashtags": _hashtags(data.get("hashtags", [])),
    }


_STAT_SYSTEM = (
    "You write a data-point Instagram post for the given brand and theme. Pick ONE striking, "
    "REAL and widely-reported statistic relevant to the theme (round it; prefix '~' if approximate; "
    "never fabricate precision).\n"
    "Produce: stat (just the number/short figure, e.g. '~70%' or '6h 42m'), context (headline "
    "explaining it, 5-15 words), body (one supporting line, may be ''), source (short source "
    "name, e.g. 'Pew Research'), cta (max 5 words, may be ''), caption (1-3 sentences, may note "
    "the stat is approximate), hashtags (8-12 lowercase).\n"
    'Respond ONLY as JSON: {"stat":"...","context":"...","body":"...","source":"...",'
    '"cta":"...","caption":"...","hashtags":["a","b"]}'
)


def generate_stat(theme: str, brand: dict) -> dict:
    text = llm.chat_json(_STAT_SYSTEM, _user_prompt(theme, brand))
    data = _extract_json(text)
    stat = str(data.get("stat", "")).strip()
    if not stat:
        raise ValueError("stat returned no figure")
    return {
        "type": "stat",
        "stat": stat,
        "context": str(data.get("context", "")).strip(),
        "body": str(data.get("body", "")).strip(),
        "source": str(data.get("source", "")).strip(),
        "cta": str(data.get("cta", "")).strip().strip('"'),
        "category": brand.get("category", ""),
        "caption": str(data.get("caption", "")).strip(),
        "hashtags": _hashtags(data.get("hashtags", [])),
    }


_DEFINITION_SYSTEM = (
    "You write a dictionary-style Instagram post defining a term for the given brand and theme. "
    "Coin or pick a resonant term the audience will recognize from their own life (can be an "
    "invented compound like 'doomscroll' era words).\n"
    "Produce: word (lowercase term), phonetic (IPA-ish, e.g. '/duːm.skrəʊl/', may be ''), "
    "part_of_speech (noun/verb/adjective), meaning (the definition, 12-35 words, relatable and "
    "sharp), example (an example sentence in first person, may be ''), cta (max 5 words, may be "
    "''), caption (1-3 sentences), hashtags (8-12 lowercase).\n"
    'Respond ONLY as JSON: {"word":"...","phonetic":"...","part_of_speech":"...","meaning":"...",'
    '"example":"...","cta":"...","caption":"...","hashtags":["a","b"]}'
)


def generate_definition(theme: str, brand: dict) -> dict:
    text = llm.chat_json(_DEFINITION_SYSTEM, _user_prompt(theme, brand))
    data = _extract_json(text)
    word = str(data.get("word", "")).strip().strip('"')
    meaning = str(data.get("meaning", "")).strip()
    if not word or not meaning:
        raise ValueError("definition returned no word/meaning")
    return {
        "type": "definition",
        "word": word,
        "phonetic": str(data.get("phonetic", "")).strip(),
        "part_of_speech": str(data.get("part_of_speech", "noun")).strip(),
        "meaning": meaning,
        "example": str(data.get("example", "")).strip(),
        "cta": str(data.get("cta", "")).strip().strip('"'),
        "category": brand.get("category", ""),
        "caption": str(data.get("caption", "")).strip(),
        "hashtags": _hashtags(data.get("hashtags", [])),
    }
