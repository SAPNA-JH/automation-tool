"""Image generation. Uses OpenAI's image model, else renders a local placeholder card."""
from __future__ import annotations

import base64
import os
import re
import textwrap
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .. import config


def _timestamped_name(prefix: str = "post") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return f"{prefix}-{stamp}.png"


def build_image_prompt(theme: str, brand: dict) -> str:
    """Turn a theme into a descriptive prompt for an image model."""
    style = brand.get(
        "visual_style",
        "moody cinematic photography, muted tones, film grain, no text",
    )
    mood = brand.get("category", "")
    mood_hint = f" Evokes the feeling of '{mood}'." if mood else ""
    return (
        f"An evocative, conceptual image representing: {theme}.{mood_hint} "
        f"Visual style: {style}. "
        "High quality, emotionally resonant, no text, no letters, no words, no watermark, no typography."
    )


def _pexels_query(prompt: str) -> str:
    """Distill a long AI-image prompt into a short stock-photo search query."""
    m = re.search(r"representing:\s*(.+?)[.\n]", prompt)
    text = m.group(1) if m else prompt
    words = re.sub(r"[^a-zA-Z ]", " ", text).split()
    stop = {"the", "a", "an", "of", "in", "on", "at", "and", "or", "to", "for", "with",
            "your", "our", "we", "that", "this", "without", "feels", "feeling"}
    keep = [w for w in words if w.lower() not in stop][:5]
    return " ".join(keep) or "moody lifestyle"


def _via_pexels(prompt: str) -> str:
    """Real stock photography from Pexels (free API). Great for travel/food/lifestyle niches."""
    resp = httpx.get(
        "https://api.pexels.com/v1/search",
        headers={"Authorization": config.PEXELS_API_KEY},
        params={"query": _pexels_query(prompt), "per_page": 20, "orientation": "portrait"},
        timeout=30,
    )
    resp.raise_for_status()
    photos = resp.json().get("photos", [])
    if not photos:
        raise RuntimeError("pexels returned no photos for query")
    photo = photos[int.from_bytes(os.urandom(2), "big") % len(photos)]
    url = photo["src"].get("large2x") or photo["src"]["original"]
    img = httpx.get(url, timeout=60, follow_redirects=True)
    img.raise_for_status()
    filename = _timestamped_name()
    (config.IMAGES_DIR / filename).write_bytes(img.content)
    return filename


def _via_cloudflare(prompt: str) -> str:
    """Cloudflare Workers AI (free tier). Flux returns JSON base64; SDXL returns raw bytes."""
    resp = httpx.post(
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{config.CLOUDFLARE_ACCOUNT_ID}/ai/run/{config.CLOUDFLARE_IMAGE_MODEL}",
        headers={"Authorization": f"Bearer {config.CLOUDFLARE_API_TOKEN}"},
        json={"prompt": prompt},
        timeout=120,
    )
    resp.raise_for_status()
    filename = _timestamped_name()
    if resp.headers.get("content-type", "").startswith("application/json"):
        data = resp.json()
        b64 = data["result"]["image"]  # Flux-schnell returns base64 here
        (config.IMAGES_DIR / filename).write_bytes(base64.b64decode(b64))
    else:
        (config.IMAGES_DIR / filename).write_bytes(resp.content)  # SDXL returns raw PNG
    return filename


def _via_pollinations(prompt: str) -> str:
    """Free, keyless image generation via pollinations.ai (returns the image directly)."""
    seed = int.from_bytes(os.urandom(2), "big")  # vary the output each call
    url = (
        f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        f"?width=1024&height=1024&nologo=true&model=flux&seed={seed}"
    )
    resp = httpx.get(url, timeout=180, follow_redirects=True)
    resp.raise_for_status()
    if not resp.headers.get("content-type", "").startswith("image"):
        raise RuntimeError("pollinations did not return an image")
    filename = _timestamped_name()
    (config.IMAGES_DIR / filename).write_bytes(resp.content)
    return filename


def _via_gemini(prompt: str) -> str:
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_IMAGE_MODEL}:generateContent",
        headers={
            "x-goog-api-key": config.GEMINI_API_KEY,
            "content-type": "application/json",
        },
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=120,
    )
    resp.raise_for_status()
    parts = resp.json()["candidates"][0]["content"]["parts"]
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            filename = _timestamped_name()
            (config.IMAGES_DIR / filename).write_bytes(base64.b64decode(inline["data"]))
            return filename
    raise RuntimeError("Gemini response contained no image data")


def _via_openai(prompt: str) -> str:
    resp = httpx.post(
        "https://api.openai.com/v1/images/generations",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        json={
            "model": config.OPENAI_IMAGE_MODEL,
            "prompt": prompt,
            "size": "1024x1024",
            "n": 1,
        },
        timeout=120,
    )
    resp.raise_for_status()
    b64 = resp.json()["data"][0]["b64_json"]
    filename = _timestamped_name()
    (config.IMAGES_DIR / filename).write_bytes(base64.b64decode(b64))
    return filename


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _via_placeholder(theme: str) -> str:
    """Render a 1080x1080 gradient card with the theme text — works with no API keys."""
    size = 1080
    img = Image.new("RGB", (size, size))
    top, bottom = (99, 102, 241), (168, 85, 247)  # indigo -> purple
    for y in range(size):
        t = y / size
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(size):
            img.putpixel((x, y), row)

    draw = ImageDraw.Draw(img)
    font = _load_font(72)
    wrapped = textwrap.fill(theme, width=18)

    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=18, align="center")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.multiline_text(
        ((size - tw) / 2, (size - th) / 2),
        wrapped,
        font=font,
        fill="white",
        spacing=18,
        align="center",
    )

    filename = _timestamped_name("placeholder")
    img.save(config.IMAGES_DIR / filename)
    return filename


def _wrap_to_width(draw, text, font, max_width) -> str:
    """Word-wrap text so each line fits within max_width, measured in the given font."""
    words = text.split()
    lines, line = [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return "\n".join(lines)


def _overlay_text(filename: str, text: str) -> None:
    """Composite a tagline onto the image, quote-card style, with a legibility scrim.

    Font size adapts so short punchy lines look bold and longer taglines still fit.
    """
    path = config.IMAGES_DIR / filename
    size = 1080
    margin = 76
    max_width = size - 2 * margin
    max_height = size * 0.5  # text must fit in the bottom half

    img = ImageOps.fit(Image.open(path).convert("RGB"), (size, size), Image.LANCZOS)
    draw = ImageDraw.Draw(img)

    # Pick the largest font size at which the wrapped tagline fits the box.
    font, wrapped, text_h = _load_font(88), text, 0
    for font_size in (88, 78, 68, 60, 54, 48):
        font = _load_font(font_size)
        wrapped = _wrap_to_width(draw, text, font, max_width)
        bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=12)
        text_h = bbox[3] - bbox[1]
        if text_h <= max_height:
            break

    # Bottom-up gradient scrim sized to cover the text block so white always reads.
    scrim_top = min(size * 0.42, size - margin - text_h - 40)
    scrim = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(scrim)
    for y in range(size):
        t = max(0.0, (y - scrim_top) / (size - scrim_top))
        sdraw.line([(0, y), (size, y)], fill=(0, 0, 0, int(225 * t)))
    img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")

    draw = ImageDraw.Draw(img)
    draw.multiline_text(
        (margin, size - margin - text_h),
        wrapped,
        font=font,
        fill="white",
        spacing=12,
    )
    img.save(path)


def generate_raw(image_prompt: str) -> str | None:
    """Generate a plain AI image (no overlay). Returns filename, or None on failure.

    Used for infographic panels, where our composer draws all the text.
    """
    provider = config.image_provider()
    try:
        if provider == "gemini":
            return _via_gemini(image_prompt)
        if provider == "openai":
            return _via_openai(image_prompt)
        if provider == "pollinations":
            return _via_pollinations(image_prompt)
        if provider == "cloudflare":
            return _via_cloudflare(image_prompt)
        if provider == "pexels":
            return _via_pexels(image_prompt)
    except Exception as exc:  # noqa: BLE001
        print(f"[images] {provider} failed ({exc})")
    return None


def generate_image(theme: str, image_prompt: str, overlay_text: str | None = None) -> str:
    """Return the filename of the generated image inside IMAGES_DIR.

    overlay_text is the tagline burned onto the image; falls back to the theme.
    """
    filename = generate_raw(image_prompt)
    if filename is None:
        return _via_placeholder(theme)  # placeholder already renders its own text

    if config.OVERLAY_TEXT:
        try:
            _overlay_text(filename, overlay_text or theme)
        except Exception as exc:  # noqa: BLE001
            print(f"[images] text overlay failed ({exc})")
    return filename
