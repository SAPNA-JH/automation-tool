"""Composite structured infographic posters (1080x1350) from a spec + AI panel images.

The AI supplies only the panel pictures (no text). Everything readable — titles, labels,
badges, CTA — is drawn here so it is always correct and on-brand.
"""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from . import config
from .providers import images

W, H = 1080, 1350
PAD = 56
BG_TOP, BG_BOTTOM = (18, 18, 26), (10, 10, 15)
CARD = (26, 26, 36)
WHITE = (240, 240, 246)
MUTED = (150, 150, 176)
GLITCH_RED = (239, 68, 68)
REBOOT_GREEN = (34, 197, 94)

# Bundled brand fonts (assets/fonts, OFL-licensed) first; system fonts as fallback.
_FONT_DIR = config.BASE_DIR / "assets" / "fonts"

_FONTS = {
    "bold": [
        str(_FONT_DIR / "Poppins-Bold.ttf"),
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ],
    "regular": [
        str(_FONT_DIR / "Poppins-Regular.ttf"),
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
}


def _hex(value: str, fallback=(168, 85, 247)) -> tuple[int, int, int]:
    value = (value or "").lstrip("#")
    if len(value) == 6:
        try:
            return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore
        except ValueError:
            pass
    return fallback


@lru_cache(maxsize=512)
def _load_truetype(path: str, size: int):
    # Cached so repeated renders don't re-read font files from disk each call.
    return ImageFont.truetype(path, size)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in _FONTS["bold" if bold else "regular"]:
        try:
            return _load_truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


_HAND_FONTS = [  # Kalam covers Devanagari too (Hindi shayari in हिन्दी renders fine)
    str(_FONT_DIR / "Kalam-Bold.ttf"),
    "/System/Library/Fonts/MarkerFelt.ttc",
]
_SERIF_FONTS = [
    str(_FONT_DIR / "DMSerifDisplay-Regular.ttf"),
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
]
_SERIF_ITALIC_FONTS = [
    str(_FONT_DIR / "DMSerifDisplay-Italic.ttf"),
    "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
]
_ITALIC_FONTS = [
    str(_FONT_DIR / "Poppins-Italic.ttf"),
    "/System/Library/Fonts/Supplemental/Arial Italic.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
]
_PHONETIC_FONTS = [  # needs IPA glyph coverage (ː, ʊ, ə, ...)
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]
_DISPLAY_FONTS = [  # tall condensed display face for giant numerals / stat posts
    str(_FONT_DIR / "BebasNeue-Regular.ttf"),
    str(_FONT_DIR / "Poppins-Bold.ttf"),
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
_DEVANAGARI_FONTS = [  # for future Hindi-script content
    str(_FONT_DIR / "Hind-Bold.ttf"),
    str(_FONT_DIR / "Kalam-Bold.ttf"),
]


def _special_font(paths: list[str], size: int, bold: bool = True):
    """Font from the first loadable path in `paths`, falling back to the brand font."""
    for path in paths:
        try:
            return _load_truetype(path, size)
        except OSError:
            continue
    return _font(size, bold=bold)


def _fit_text_any(draw, text, max_w, max_h, sizes, font_fn, spacing=6):
    """Like _fit_text but with a custom size->font factory. Returns (font, wrapped, height)."""
    font = font_fn(sizes[-1])
    wrapped, h = text, 0
    for size in sizes:
        font = font_fn(size)
        wrapped = _wrap(draw, text, font, max_w)
        bb = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing)
        h = bb[3] - bb[1]
        if h <= max_h:
            break
    return font, wrapped, h


def _fit_line(draw, text, sizes, font_fn, max_w):
    """Largest single-line font from `sizes` whose rendered width fits max_w."""
    font = font_fn(sizes[-1])
    for size in sizes:
        f = font_fn(size)
        if draw.textlength(text, font=f) <= max_w:
            return f
    return font


def _diag_gradient(size: tuple[int, int], c1, c2) -> Image.Image:
    """Diagonal (top-left → bottom-right) gradient, computed small then upscaled."""
    sw, sh = 72, 90
    small = Image.new("RGB", (sw, sh))
    px = small.load()
    for yy in range(sh):
        for xx in range(sw):
            t = (xx / (sw - 1) + yy / (sh - 1)) / 2
            px[xx, yy] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    return small.resize(size, Image.BILINEAR)


def _sparkle(draw, cx, cy, r, fill):
    """4-point star (diamond sparkle) centered at (cx, cy)."""
    w = r * 0.24
    draw.polygon(
        [(cx, cy - r), (cx + w, cy - w), (cx + r, cy), (cx + w, cy + w),
         (cx, cy + r), (cx - w, cy + w), (cx - r, cy), (cx - w, cy - w)],
        fill=fill,
    )


def _timestamped_name(prefix: str = "post") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return f"{prefix}-{stamp}.png"


def _background() -> Image.Image:
    img = Image.new("RGB", (W, H))
    for y in range(H):
        t = y / H
        row = tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3))
        ImageDraw.Draw(img).line([(0, y), (W, y)], fill=row)
    return img


def _gradient_tile(size: tuple[int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size)
    top, bottom = (60, 55, 90), (30, 28, 48)
    for y in range(h):
        t = y / h
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        ImageDraw.Draw(img).line([(0, y), (w, y)], fill=row)
    return img


def _wrap(draw, text, font, max_width) -> str:
    words, lines, line = text.split(), [], ""
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


def _rounded(img: Image.Image, radius: int) -> Image.Image:
    img = img.convert("RGBA")
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, img.size[0] - 1, img.size[1] - 1], radius=radius, fill=255
    )
    img.putalpha(mask)
    return img


def _panel_images(prompts: list[str], size: tuple[int, int]) -> list[Image.Image]:
    """Fetch all panel images concurrently, each fit to `size`; gradient tile on failure."""
    def one(prompt: str) -> Image.Image:
        if not prompt:  # preview mode / no prompt → gradient tile, no network call
            return _gradient_tile(size)
        fn = images.generate_raw(prompt)
        if fn:
            try:
                src = Image.open(config.IMAGES_DIR / fn).convert("RGB")
                return ImageOps.fit(src, size, Image.LANCZOS)
            except Exception:  # noqa: BLE001
                pass
        return _gradient_tile(size)

    with ThreadPoolExecutor(max_workers=6) as pool:
        return list(pool.map(one, prompts))


def _scrim(tile: Image.Image, start=0.45, strength=225) -> Image.Image:
    """Darken the bottom of a tile so overlaid white text stays legible."""
    w, h = tile.size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    top = h * start
    for y in range(h):
        a = max(0.0, (y - top) / (h - top)) if h > top else 0.0
        d.line([(0, y), (w, y)], fill=(0, 0, 0, int(strength * a)))
    return Image.alpha_composite(tile.convert("RGBA"), overlay)


def _draw_header(img, draw, spec, accent, handle) -> int:
    """Draw eyebrow + title + accent underline. Returns the y where the body can start."""
    y = PAD
    eyebrow = (spec.get("category") or "").upper()
    if eyebrow:
        f = _font(26, bold=True)
        draw.text((PAD, y), eyebrow, font=f, fill=accent)
        if handle:
            hf = _font(26, bold=False)
            draw.text((W - PAD - draw.textlength(handle, font=hf), y), handle, font=hf, fill=MUTED)
        y += 44

    title = spec.get("title", "")
    tf = _font(66, bold=True)
    wrapped = _wrap(draw, title, tf, W - 2 * PAD)
    draw.multiline_text((PAD, y), wrapped, font=tf, fill=WHITE, spacing=8)
    _accent_leading_number(draw, PAD, y, title, tf, accent)
    bbox = draw.multiline_textbbox((PAD, y), wrapped, font=tf, spacing=8)
    y = bbox[3] + 22
    draw.rounded_rectangle([PAD, y, PAD + 120, y + 8], radius=4, fill=accent)
    return y + 34


def _accent_leading_number(draw, x, y, title, font, accent) -> None:
    """Recolor a leading numeric token (e.g. the '6' in '6 Signs...') in the accent colour."""
    first = title.split(" ", 1)[0]
    if first.rstrip(".").isdigit():
        draw.text((x, y), first, font=font, fill=accent)


def _draw_footer(img, draw, cta, accent) -> None:
    if not cta:
        return
    f = _font(40, bold=True)
    tw = draw.textlength(cta.upper(), font=f)
    pill_w = min(W - 2 * PAD, tw + 96)
    x0 = (W - pill_w) / 2
    y0 = H - PAD - 84
    draw.rounded_rectangle([x0, y0, x0 + pill_w, y0 + 84], radius=42, fill=accent)
    draw.text(((W - tw) / 2, y0 + 20), cta.upper(), font=f, fill=(255, 255, 255))


def _draw_grid(spec: dict, accent, handle) -> Image.Image:
    img = _background()
    draw = ImageDraw.Draw(img)
    body_top = _draw_header(img, draw, spec, accent, handle)
    footer_top = H - PAD - 84 - 24

    items = spec["items"]
    cols = 2
    rows = math.ceil(len(items) / cols)
    gutter = 24
    col_w = (W - 2 * PAD - (cols - 1) * gutter) // cols
    row_h = (footer_top - body_top - (rows - 1) * gutter) // rows

    tiles = _panel_images([it["image"] for it in items], (col_w, row_h))
    label_font = _font(34, bold=True)
    badge_font = _font(30, bold=True)

    for idx, (item, tile) in enumerate(zip(items, tiles)):
        r, c = divmod(idx, cols)
        x = PAD + c * (col_w + gutter)
        y = body_top + r * (row_h + gutter)

        card = _scrim(tile)
        cdraw = ImageDraw.Draw(card)
        # index badge
        cdraw.ellipse([18, 18, 74, 74], fill=accent)
        num = str(idx + 1)
        nb = cdraw.textbbox((0, 0), num, font=badge_font)
        cdraw.text((46 - (nb[2] - nb[0]) / 2, 46 - (nb[3] - nb[1]) / 2 - 4), num,
                   font=badge_font, fill=(255, 255, 255))
        # label bottom-left
        label = _wrap(cdraw, item["label"], label_font, col_w - 40)
        lb = cdraw.multiline_textbbox((0, 0), label, font=label_font, spacing=6)
        cdraw.multiline_text((22, row_h - (lb[3] - lb[1]) - 28), label,
                             font=label_font, fill=WHITE, spacing=6)

        rounded = _rounded(card.convert("RGB"), 26)
        img.paste(rounded, (x, y), rounded)

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_grid_light(spec: dict, accent, handle) -> Image.Image:
    """Bright design: white cards with the picture on top and the label on a clean bar below."""
    ink, sub = (26, 26, 30), (120, 120, 132)
    cream_top, cream_bottom = (250, 247, 240), (238, 232, 220)

    img = Image.new("RGB", (W, H))
    for yy in range(H):
        t = yy / H
        row = tuple(int(cream_top[i] + (cream_bottom[i] - cream_top[i]) * t) for i in range(3))
        ImageDraw.Draw(img).line([(0, yy), (W, yy)], fill=row)
    draw = ImageDraw.Draw(img)

    # Header (dark ink on cream)
    y = PAD
    eyebrow = (spec.get("category") or "").upper()
    if eyebrow:
        draw.text((PAD, y), eyebrow, font=_font(26, bold=True), fill=accent)
        if handle:
            hf = _font(26)
            draw.text((W - PAD - draw.textlength(handle, font=hf), y), handle, font=hf, fill=sub)
        y += 44
    title = spec.get("title", "")
    tf = _font(66, bold=True)
    wrapped = _wrap(draw, title, tf, W - 2 * PAD)
    draw.multiline_text((PAD, y), wrapped, font=tf, fill=ink, spacing=8)
    _accent_leading_number(draw, PAD, y, title, tf, accent)
    bbox = draw.multiline_textbbox((PAD, y), wrapped, font=tf, spacing=8)
    body_top = bbox[3] + 22
    draw.rounded_rectangle([PAD, body_top, PAD + 120, body_top + 8], radius=4, fill=accent)
    body_top += 34
    footer_top = H - PAD - 84 - 24

    items = spec["items"]
    cols = 2
    rows = math.ceil(len(items) / cols)
    gutter = 26
    col_w = (W - 2 * PAD - (cols - 1) * gutter) // cols
    row_h = (footer_top - body_top - (rows - 1) * gutter) // rows
    img_h = int(row_h * 0.66)
    inner = 12

    tiles = _panel_images([it["image"] for it in items], (col_w - 2 * inner, img_h))
    label_font = _font(30, bold=True)
    badge_font = _font(28, bold=True)

    # One soft shadow layer behind all cards.
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    positions = []
    for idx in range(len(items)):
        r, c = divmod(idx, cols)
        x = PAD + c * (col_w + gutter)
        yy = body_top + r * (row_h + gutter)
        positions.append((x, yy))
        sdraw.rounded_rectangle([x, yy + 10, x + col_w, yy + row_h + 10], radius=24, fill=(0, 0, 0, 55))
    img = Image.alpha_composite(img.convert("RGBA"), shadow.filter(ImageFilter.GaussianBlur(10))).convert("RGB")
    draw = ImageDraw.Draw(img)

    for idx, (item, tile) in enumerate(zip(items, tiles)):
        x, yy = positions[idx]
        draw.rounded_rectangle([x, yy, x + col_w, yy + row_h], radius=24, fill=(255, 255, 255))
        thumb = _rounded(tile, 16)
        img.paste(thumb, (x + inner, yy + inner), thumb)
        # index badge on the image
        bd = ImageDraw.Draw(img)
        bd.ellipse([x + inner + 12, yy + inner + 12, x + inner + 60, yy + inner + 60], fill=accent)
        num = str(idx + 1)
        nb = bd.textbbox((0, 0), num, font=badge_font)
        bd.text((x + inner + 36 - (nb[2] - nb[0]) / 2, yy + inner + 36 - (nb[3] - nb[1]) / 2 - 4),
                num, font=badge_font, fill=(255, 255, 255))
        # label below image
        label = _wrap(draw, item["label"], label_font, col_w - 32)
        ly = yy + inner + img_h + 12
        draw.multiline_text((x + 20, ly), label, font=label_font, fill=ink, spacing=4)

    _draw_footer(img, ImageDraw.Draw(img), spec.get("cta", ""), accent)
    return img


def _draw_grid_list(spec: dict, accent, handle) -> Image.Image:
    """Editorial single-column list: big accent numeral + thumbnail + label per row."""
    img = _background()
    draw = ImageDraw.Draw(img)
    body_top = _draw_header(img, draw, spec, accent, handle)
    footer_top = H - PAD - 84 - 24

    items = spec["items"]
    n = len(items)
    row_gap = 16
    row_h = (footer_top - body_top - (n - 1) * row_gap) // n
    thumb = min(row_h - 8, 150)
    num_w = 96

    tiles = _panel_images([it["image"] for it in items], (thumb, thumb))
    num_font = _font(66, bold=True)
    label_font = _font(36, bold=True)

    for idx, (item, tile) in enumerate(zip(items, tiles)):
        y = body_top + idx * (row_h + row_gap)
        cy = y + row_h // 2
        # big accent numeral
        num = f"{idx + 1:02d}"
        nb = draw.textbbox((0, 0), num, font=num_font)
        draw.text((PAD, cy - (nb[3] - nb[1]) / 2 - 8), num, font=num_font, fill=accent)
        # thumbnail
        tx = PAD + num_w
        img.paste(_rounded(tile, 18), (tx, cy - thumb // 2), _rounded(tile, 18))
        # label
        lx = tx + thumb + 24
        label = _wrap(draw, item["label"], label_font, W - PAD - lx)
        lb = draw.multiline_textbbox((0, 0), label, font=label_font, spacing=4)
        draw.multiline_text((lx, cy - (lb[3] - lb[1]) / 2 - 4), label, font=label_font,
                            fill=WHITE, spacing=4)
        # divider
        if idx < n - 1:
            dy = y + row_h + row_gap // 2
            draw.line([(PAD, dy), (W - PAD, dy)], fill=(42, 42, 56), width=2)

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_vs(spec: dict, accent, handle) -> Image.Image:
    img = _background()
    draw = ImageDraw.Draw(img)
    body_top = _draw_header(img, draw, spec, accent, handle)
    footer_top = H - PAD - 84 - 24

    left, right = spec["left"], spec["right"]
    rows = min(len(left), len(right))
    center_gap = 8
    col_w = (W - 2 * PAD - center_gap) // 2
    left_x = PAD
    right_x = PAD + col_w + center_gap

    # Column header pills
    head_f = _font(30, bold=True)
    head_h = 60
    for cx, title, color in (
        (left_x, spec.get("left_title", "The Glitch"), GLITCH_RED),
        (right_x, spec.get("right_title", "The Reboot"), REBOOT_GREEN),
    ):
        draw.rounded_rectangle([cx, body_top, cx + col_w, body_top + head_h], radius=18, fill=color)
        t = title.upper()
        tw = draw.textlength(t, font=head_f)
        draw.text((cx + (col_w - tw) / 2, body_top + 15), t, font=head_f, fill=(255, 255, 255))

    grid_top = body_top + head_h + 18
    row_gap = 14
    row_h = (footer_top - grid_top - (rows - 1) * row_gap) // rows
    thumb = min(row_h, 132)
    label_font = _font(28, bold=True)

    left_tiles = _panel_images([it["image"] for it in left[:rows]], (thumb, thumb))
    right_tiles = _panel_images([it["image"] for it in right[:rows]], (thumb, thumb))

    for i in range(rows):
        y = grid_top + i * (row_h + row_gap)
        for cx, tile, item in (
            (left_x, left_tiles[i], left[i]),
            (right_x, right_tiles[i], right[i]),
        ):
            img.paste(_rounded(tile, 18), (cx, y + (row_h - thumb) // 2), _rounded(tile, 18))
            tx = cx + thumb + 16
            label = _wrap(draw, item["label"], label_font, col_w - thumb - 28)
            lb = draw.multiline_textbbox((0, 0), label, font=label_font, spacing=4)
            draw.multiline_text((tx, y + (row_h - (lb[3] - lb[1])) // 2 - 4), label,
                                font=label_font, fill=WHITE, spacing=4)

    # Center VS badge
    cx, cy = W // 2, grid_top + (footer_top - grid_top) // 2
    draw.ellipse([cx - 46, cy - 46, cx + 46, cy + 46], fill=accent, outline=(255, 255, 255), width=4)
    vf = _font(38, bold=True)
    vw = draw.textlength("VS", font=vf)
    draw.text((cx - vw / 2, cy - 26), "VS", font=vf, fill=(255, 255, 255))

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_grid_polaroid(spec: dict, accent, handle) -> Image.Image:
    """Scrapbook: white-framed polaroids with handwritten labels, scattered at slight angles."""
    img = _background()
    draw = ImageDraw.Draw(img)
    body_top = _draw_header(img, draw, spec, accent, handle)
    footer_top = H - PAD - 84 - 24

    items = spec["items"]
    cols = 2
    rows = math.ceil(len(items) / cols)
    gutter = 16
    cell_w = (W - 2 * PAD - (cols - 1) * gutter) // cols
    cell_h = (footer_top - body_top - (rows - 1) * gutter) // rows

    border, band = 14, 72
    card_w = cell_w - 30                      # slack so the rotated card stays inside its cell
    photo_w = card_w - 2 * border
    photo_h = max(cell_h - 36 - border - band, 80)
    card_h = border + photo_h + band

    tiles = _panel_images([it["image"] for it in items], (photo_w, photo_h))
    paper = (252, 250, 245, 255)
    ink = (40, 38, 44)

    # Soft shadows under every card, blurred once.
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    placed: list[tuple[Image.Image, int, int]] = []

    for idx, (item, tile) in enumerate(zip(items, tiles)):
        r, c = divmod(idx, cols)
        card = Image.new("RGBA", (card_w, card_h), paper)
        card.paste(tile, (border, border))
        cdraw = ImageDraw.Draw(card)
        font, wrapped, th = _fit_text_any(
            cdraw, item["label"], card_w - 2 * border, band - 18, (34, 30, 26, 22),
            lambda s: _special_font(_HAND_FONTS, s), spacing=2,
        )
        lw = max(cdraw.textlength(line, font=font) for line in wrapped.split("\n"))
        cdraw.multiline_text(((card_w - lw) / 2, border + photo_h + (band - th) / 2 - 6),
                             wrapped, font=font, fill=ink, spacing=2, align="center")

        angle = (3.5, -4.5, -3.0, 4.0, 4.5, -3.5)[idx % 6]
        rot = card.rotate(angle, expand=True, resample=Image.BICUBIC)
        x = PAD + c * (cell_w + gutter) + (cell_w - rot.width) // 2
        y = body_top + r * (cell_h + gutter) + (cell_h - rot.height) // 2
        sdraw.rounded_rectangle([x + 8, y + 12, x + rot.width - 4, y + rot.height + 6],
                                radius=10, fill=(0, 0, 0, 90))
        placed.append((rot, x, y))

    img = Image.alpha_composite(img.convert("RGBA"),
                                shadow.filter(ImageFilter.GaussianBlur(9))).convert("RGB")
    for rot, x, y in placed:
        img.paste(rot, (x, y), rot)

    _draw_footer(img, ImageDraw.Draw(img), spec.get("cta", ""), accent)
    return img


def _draw_grid_steps(spec: dict, accent, handle) -> Image.Image:
    """Vertical numbered process timeline: accent spine, circle nodes, thumb + label rows."""
    img = _background()
    draw = ImageDraw.Draw(img)
    body_top = _draw_header(img, draw, spec, accent, handle)
    footer_top = H - PAD - 84 - 24

    items = spec["items"]
    n = len(items)
    row_gap = 14
    row_h = (footer_top - body_top - (n - 1) * row_gap) // n
    line_x = PAD + 38
    node_r = 32
    thumb = min(row_h - 14, 128)

    first_cy = body_top + row_h // 2
    last_cy = body_top + (n - 1) * (row_h + row_gap) + row_h // 2
    dim = tuple(int(c * 0.55) for c in accent)
    draw.line([(line_x, first_cy), (line_x, last_cy)], fill=dim, width=6)

    tiles = _panel_images([it["image"] for it in items], (thumb, thumb))
    num_font = _font(30, bold=True)
    label_font = _font(36, bold=True)

    for idx, (item, tile) in enumerate(zip(items, tiles)):
        cy = body_top + idx * (row_h + row_gap) + row_h // 2
        draw.ellipse([line_x - node_r, cy - node_r, line_x + node_r, cy + node_r],
                     fill=CARD, outline=accent, width=4)
        num = str(idx + 1)
        nb = draw.textbbox((0, 0), num, font=num_font)
        draw.text((line_x - (nb[2] - nb[0]) / 2, cy - (nb[3] - nb[1]) / 2 - 6),
                  num, font=num_font, fill=WHITE)

        tx = line_x + node_r + 26
        rounded = _rounded(tile, 18)
        img.paste(rounded, (tx, cy - thumb // 2), rounded)

        lx = tx + thumb + 26
        label = _wrap(draw, item["label"], label_font, W - PAD - lx)
        lb = draw.multiline_textbbox((0, 0), label, font=label_font, spacing=4)
        draw.multiline_text((lx, cy - (lb[3] - lb[1]) / 2 - 6), label,
                            font=label_font, fill=WHITE, spacing=4)

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_grid_checklist(spec: dict, accent, handle) -> Image.Image:
    """Checklist rows: card with an accent checkbox + drawn check, label, thumbnail right."""
    img = _background()
    draw = ImageDraw.Draw(img)
    body_top = _draw_header(img, draw, spec, accent, handle)
    footer_top = H - PAD - 84 - 24

    items = spec["items"]
    n = len(items)
    row_gap = 16
    row_h = (footer_top - body_top - (n - 1) * row_gap) // n
    thumb = min(row_h - 24, 116)
    box = 62

    tiles = _panel_images([it["image"] for it in items], (thumb, thumb))
    label_font = _font(34, bold=True)
    tint = tuple(min(255, int(c * 0.28 + 20)) for c in accent)

    for idx, (item, tile) in enumerate(zip(items, tiles)):
        y = body_top + idx * (row_h + row_gap)
        cy = y + row_h // 2
        draw.rounded_rectangle([PAD, y, W - PAD, y + row_h], radius=22, fill=CARD)

        # checkbox with drawn check mark
        bx = PAD + 26
        by = cy - box // 2
        draw.rounded_rectangle([bx, by, bx + box, by + box], radius=14,
                               fill=tint, outline=accent, width=4)
        draw.line([(bx + 14, by + 32), (bx + 26, by + 45), (bx + 49, by + 17)],
                  fill=accent, width=7, joint="curve")

        # thumbnail on the right
        tx = W - PAD - 20 - thumb
        rounded = _rounded(tile, 16)
        img.paste(rounded, (tx, cy - thumb // 2), rounded)

        # label between checkbox and thumbnail
        lx = bx + box + 26
        label = _wrap(draw, item["label"], label_font, tx - lx - 20)
        lb = draw.multiline_textbbox((0, 0), label, font=label_font, spacing=4)
        draw.multiline_text((lx, cy - (lb[3] - lb[1]) / 2 - 6), label,
                            font=label_font, fill=WHITE, spacing=4)

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_grid_neon(spec: dict, accent, handle) -> Image.Image:
    """Glassmorphism: translucent dark cards with a glowing accent border, image over label."""
    img = _background()
    draw = ImageDraw.Draw(img)
    body_top = _draw_header(img, draw, spec, accent, handle)
    footer_top = H - PAD - 84 - 24

    items = spec["items"]
    cols = 2
    rows = math.ceil(len(items) / cols)
    gutter = 26
    col_w = (W - 2 * PAD - (cols - 1) * gutter) // cols
    row_h = (footer_top - body_top - (rows - 1) * gutter) // rows
    inner = 14
    img_h = int(row_h * 0.60)

    tiles = _panel_images([it["image"] for it in items], (col_w - 2 * inner, img_h))
    label_font = _font(30, bold=True)
    positions = []
    for idx in range(len(items)):
        r, c = divmod(idx, cols)
        positions.append((PAD + c * (col_w + gutter), body_top + r * (row_h + gutter)))

    # Glow pass: blurred accent outlines behind every card.
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for x, y in positions:
        for width, alpha in ((12, 46), (7, 80), (3, 130)):
            gdraw.rounded_rectangle([x, y, x + col_w, y + row_h], radius=26,
                                    outline=accent + (alpha,), width=width)
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(7)))

    # Card pass: translucent dark fill + crisp 2px accent border.
    cards = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(cards)
    for x, y in positions:
        cdraw.rounded_rectangle([x, y, x + col_w, y + row_h], radius=26,
                                fill=(22, 22, 34, 200), outline=accent + (255,), width=2)
    img = Image.alpha_composite(img, cards).convert("RGB")
    draw = ImageDraw.Draw(img)

    for idx, (item, tile) in enumerate(zip(items, tiles)):
        x, y = positions[idx]
        rounded = _rounded(tile, 18)
        img.paste(rounded, (x + inner, y + inner), rounded)
        label = _wrap(draw, item["label"], label_font, col_w - 2 * inner - 8)
        lb = draw.multiline_textbbox((0, 0), label, font=label_font, spacing=4)
        lw = lb[2] - lb[0]
        ly = y + inner + img_h + (row_h - inner - img_h - (lb[3] - lb[1])) / 2 - 8
        draw.multiline_text((x + (col_w - lw) / 2, ly), label, font=label_font,
                            fill=WHITE, spacing=4, align="center")

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_grid_mag(spec: dict, accent, handle) -> Image.Image:
    """Editorial magazine: big hero card for item 1, compact numbered rows for the rest."""
    img = _background()
    draw = ImageDraw.Draw(img)
    body_top = _draw_header(img, draw, spec, accent, handle)
    footer_top = H - PAD - 84 - 24

    items = spec["items"]
    hero, rest = items[0], items[1:]
    hero_h = int((footer_top - body_top) * 0.42)
    hero_w = W - 2 * PAD

    tiles = _panel_images([hero["image"]] + [it["image"] for it in rest], (hero_w, hero_h))
    hero_tile, rest_tiles_full = tiles[0], tiles[1:]

    # Hero card: scrimmed image with 01 + big label overlaid.
    card = _scrim(hero_tile, start=0.30, strength=235)
    cdraw = ImageDraw.Draw(card)
    hero_font, wrapped, th = _fit_text_any(
        cdraw, hero["label"], hero_w - 150, hero_h * 0.5, (58, 50, 44, 38),
        lambda s: _font(s, bold=True), spacing=6,
    )
    num_font = _font(64, bold=True)
    ly = hero_h - th - 40
    cdraw.text((30, ly - 12), "01", font=num_font, fill=accent)
    cdraw.multiline_text((30 + cdraw.textlength("01", font=num_font) + 22, ly),
                         wrapped, font=hero_font, fill=WHITE, spacing=6)
    rounded = _rounded(card.convert("RGB"), 26)
    img.paste(rounded, (PAD, body_top), rounded)

    # Remaining numbered rows.
    rows_top = body_top + hero_h + 26
    n = len(rest)
    row_gap = 12
    row_h = (footer_top - rows_top - (n - 1) * row_gap) // n if n else 0
    thumb = min(row_h - 6, 96)
    num_font_s = _font(40, bold=True)
    label_font = _font(33, bold=True)

    rest_tiles = _panel_images([it["image"] for it in rest], (thumb, thumb)) if n else []
    for idx, (item, tile) in enumerate(zip(rest, rest_tiles)):
        y = rows_top + idx * (row_h + row_gap)
        cy = y + row_h // 2
        num = f"{idx + 2:02d}"
        nb = draw.textbbox((0, 0), num, font=num_font_s)
        draw.text((PAD, cy - (nb[3] - nb[1]) / 2 - 6), num, font=num_font_s, fill=accent)
        tx = PAD + 84
        rt = _rounded(tile, 14)
        img.paste(rt, (tx, cy - thumb // 2), rt)
        lx = tx + thumb + 22
        label = _wrap(draw, item["label"], label_font, W - PAD - lx)
        lb = draw.multiline_textbbox((0, 0), label, font=label_font, spacing=4)
        draw.multiline_text((lx, cy - (lb[3] - lb[1]) / 2 - 5), label,
                            font=label_font, fill=WHITE, spacing=4)
        if idx < n - 1:
            dy = y + row_h + row_gap // 2
            draw.line([(PAD, dy), (W - PAD, dy)], fill=(42, 42, 56), width=2)

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_vs_split(spec: dict, accent, handle) -> Image.Image:
    """Full-bleed dramatic split: red-tinted left vs green-tinted right, jagged divider, VS badge."""
    left_top, left_bot = (54, 18, 24), (22, 9, 13)
    right_top, right_bot = (15, 44, 26), (7, 19, 12)
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        lrow = tuple(int(left_top[i] + (left_bot[i] - left_top[i]) * t) for i in range(3))
        rrow = tuple(int(right_top[i] + (right_bot[i] - right_top[i]) * t) for i in range(3))
        d.line([(0, y), (W // 2, y)], fill=lrow)
        d.line([(W // 2, y), (W, y)], fill=rrow)
    draw = ImageDraw.Draw(img)

    # Header: eyebrow/handle + centered title.
    y = PAD
    eyebrow = (spec.get("category") or "").upper()
    if eyebrow:
        draw.text((PAD, y), eyebrow, font=_font(26, bold=True), fill=WHITE)
        if handle:
            hf = _font(26)
            draw.text((W - PAD - draw.textlength(handle, font=hf), y), handle,
                      font=hf, fill=(225, 220, 228))
        y += 46
    tf, wrapped, th = _fit_text_any(draw, spec.get("title", ""), W - 2 * PAD, 170,
                                    (60, 54, 48, 42), lambda s: _font(s, bold=True), spacing=8)
    tw = max(draw.textlength(line, font=tf) for line in wrapped.split("\n"))
    draw.multiline_text(((W - tw) / 2, y), wrapped, font=tf, fill=WHITE,
                        spacing=8, align="center")
    body_top = y + th + 34
    footer_top = H - PAD - 84 - 24

    left, right = spec["left"], spec["right"]
    rows = min(len(left), len(right))
    margin, center_gap = 44, 76
    col_w = W // 2 - margin - center_gap
    right_x = W // 2 + center_gap

    # One thumbnail banner at the top of each column (first item's image).
    banner_h = 148
    banners = _panel_images([left[0]["image"], right[0]["image"]], (col_w, banner_h))
    head_f = _font(30, bold=True)
    pill_h = 58
    for cx, tile, title, color in (
        (margin, banners[0], spec.get("left_title", "The Glitch"), GLITCH_RED),
        (right_x, banners[1], spec.get("right_title", "The Reboot"), REBOOT_GREEN),
    ):
        rb = _rounded(tile, 20)
        img.paste(rb, (cx, body_top), rb)
        py = body_top + banner_h + 18
        draw.rounded_rectangle([cx, py, cx + col_w, py + pill_h], radius=18, fill=color)
        t = title.upper()
        ttw = draw.textlength(t, font=head_f)
        draw.text((cx + (col_w - ttw) / 2, py + 14), t, font=head_f, fill=(255, 255, 255))

    # Stacked big bold labels.
    list_top = body_top + banner_h + 18 + pill_h + 26
    row_h = (footer_top - list_top) // rows
    for cx, items in ((margin, left), (right_x, right)):
        for i in range(rows):
            cy = list_top + i * row_h + row_h // 2
            lf, lwrapped, lh = _fit_text_any(draw, items[i]["label"], col_w, row_h - 14,
                                             (40, 36, 32, 28), lambda s: _font(s, bold=True),
                                             spacing=4)
            draw.multiline_text((cx, cy - lh / 2 - 5), lwrapped, font=lf,
                                fill=WHITE, spacing=4)

    # Jagged white divider down the middle (starting below the header).
    div_top = body_top - 24
    pts = []
    step, amp = 84, 20
    for i, yy in enumerate(range(div_top, H + step, step)):
        pts.append((W // 2 + (amp if i % 2 == 0 else -amp), min(yy, H)))
    draw.line(pts, fill=(255, 255, 255), width=5, joint="curve")

    # Big VS badge at the center of the list area.
    cx, cy = W // 2, list_top + (footer_top - list_top) // 2
    r = 58
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=accent,
                 outline=(255, 255, 255), width=5)
    vf = _font(46, bold=True)
    vw = draw.textlength("VS", font=vf)
    draw.text((cx - vw / 2, cy - 30), "VS", font=vf, fill=(255, 255, 255))

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


# --- Card / stat / definition designs (pure typography, no AI panels) ---

def _draw_quote_serif(spec: dict, accent, handle) -> Image.Image:
    """Literary quote: giant faded serif quotation mark, Georgia headline, em-dash credit."""
    img = _background()
    draw = ImageDraw.Draw(img)

    kicker = (spec.get("kicker") or spec.get("category") or "").upper()
    if kicker:
        draw.text((PAD, PAD), kicker, font=_font(26, bold=True), fill=accent)
    if handle:
        hf = _font(26)
        draw.text((W - PAD - draw.textlength(handle, font=hf), PAD), handle, font=hf, fill=MUTED)

    # Giant translucent serif quotation mark.
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    qf = _special_font(_SERIF_FONTS, 380)
    ImageDraw.Draw(overlay).text((PAD - 22, PAD + 10), "“", font=qf, fill=accent + (110,))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    headline = spec.get("headline", "")
    font, wrapped, th = _fit_text_any(
        draw, headline, W - 2 * PAD - 20, H * 0.46, (84, 76, 68, 60, 52, 46),
        lambda s: _special_font(_SERIF_FONTS, s), spacing=14,
    )
    attribution = spec.get("attribution", "")
    attr_f = _special_font(_SERIF_ITALIC_FONTS, 36, bold=False)
    attr_h = 76 if attribution else 0
    top = PAD + 150 + (H - PAD - 150 - PAD - 90 - th - attr_h) // 2
    draw.multiline_text((PAD, top), wrapped, font=font, fill=WHITE, spacing=14)
    if attribution:
        draw.text((PAD, top + th + 52), f"— {attribution}", font=attr_f, fill=MUTED)

    # Thin accent rule + handle at the bottom.
    draw.rounded_rectangle([W // 2 - 55, H - PAD - 64, W // 2 + 55, H - PAD - 58],
                           radius=3, fill=accent)
    if handle:
        hf = _font(26)
        draw.text(((W - draw.textlength(handle, font=hf)) / 2, H - PAD - 38),
                  handle, font=hf, fill=MUTED)
    return img


def _draw_quote_neon(spec: dict, accent, handle) -> Image.Image:
    """Glassmorphic quote card: glowing accent border, bold sans headline, muted credit."""
    img = _background()
    draw = ImageDraw.Draw(img)
    _eyebrow_and_handle(draw, spec.get("category", ""), "", accent)

    pad_in = 52
    card_w = W - 2 * PAD
    kicker = (spec.get("kicker") or "").upper()
    attribution = spec.get("attribution", "")
    font, wrapped, th = _fit_text_any(
        draw, spec.get("headline", ""), card_w - 2 * pad_in, H * 0.42,
        (68, 60, 54, 48, 42, 38), lambda s: _font(s, bold=True), spacing=10,
    )
    card_h = pad_in + (52 if kicker else 0) + th + (76 if attribution else 0) + pad_in
    x0 = PAD
    y0 = PAD + 60 + (H - PAD - 60 - PAD - 130 - card_h) // 2

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    for width, alpha in ((14, 46), (8, 85), (3, 140)):
        gdraw.rounded_rectangle([x0, y0, x0 + card_w, y0 + card_h], radius=30,
                                outline=accent + (alpha,), width=width)
    img = Image.alpha_composite(img.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(8)))

    card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(card)
    cdraw.rounded_rectangle([x0, y0, x0 + card_w, y0 + card_h], radius=30,
                            fill=(22, 22, 34, 205), outline=accent + (255,), width=2)
    img = Image.alpha_composite(img, card).convert("RGB")
    draw = ImageDraw.Draw(img)

    ty = y0 + pad_in
    if kicker:
        draw.text((x0 + pad_in, ty), kicker, font=_font(26, bold=True), fill=accent)
        ty += 52
    draw.multiline_text((x0 + pad_in, ty), wrapped, font=font, fill=WHITE, spacing=10)
    if attribution:
        af = _font(30)
        draw.text((x0 + pad_in, ty + th + 42), f"— {attribution}", font=af, fill=MUTED)

    if handle:
        hf = _font(28, bold=True)
        draw.text(((W - draw.textlength(handle, font=hf)) / 2, H - PAD - 130),
                  handle, font=hf, fill=accent)
    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_did_you_know(spec: dict, accent, handle) -> Image.Image:
    """Fact post: kicker pill top-center, bold headline, body, faint giant '?' watermark."""
    img = _background()

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    qf = _font(760, bold=True)
    ImageDraw.Draw(overlay).text((W - 470, H - 900), "?", font=qf, fill=accent + (34,))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    if handle:
        hf = _font(26)
        draw.text((W - PAD - draw.textlength(handle, font=hf), PAD), handle, font=hf, fill=MUTED)

    kicker = (spec.get("kicker") or "DID YOU KNOW?").upper()
    kf = _font(32, bold=True)
    kw = draw.textlength(kicker, font=kf)
    ky = PAD + 60
    draw.rounded_rectangle([(W - kw - 88) / 2, ky, (W + kw + 88) / 2, ky + 72],
                           radius=36, fill=accent)
    draw.text(((W - kw) / 2, ky + 17), kicker, font=kf, fill=(255, 255, 255))

    font, wrapped, th = _fit_text(draw, spec.get("headline", ""), W - 2 * PAD - 20,
                                  H * 0.40, (74, 66, 58, 52, 46))
    body = spec.get("body", "")
    bf, bwrapped, bh = (_fit_text(draw, body, W - 2 * PAD - 80, H * 0.18,
                                  (38, 34, 30), bold=False) if body else (None, "", 0))
    block = th + ((44 + bh) if body else 0)
    top = ky + 120 + (H - ky - 120 - PAD - 140 - block) // 2

    hw = max(draw.textlength(line, font=font) for line in wrapped.split("\n"))
    draw.multiline_text(((W - hw) / 2, top), wrapped, font=font, fill=WHITE,
                        spacing=10, align="center")
    if body:
        bw = max(draw.textlength(line, font=bf) for line in bwrapped.split("\n"))
        draw.multiline_text(((W - bw) / 2, top + th + 44), bwrapped, font=bf,
                            fill=MUTED, spacing=8, align="center")

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_affirmation(spec: dict, accent, handle) -> Image.Image:
    """Calm affirmation: diagonal accent→warm gradient, serif-italic headline, sparkles."""
    pink = (236, 72, 153)
    warm = tuple(int(accent[i] * 0.42 + pink[i] * 0.58) for i in range(3))
    soft_a = tuple(min(255, int(c * 0.72 + 40)) for c in accent)
    soft_w = tuple(min(255, int(c * 0.72 + 40)) for c in warm)
    img = _diag_gradient((W, H), soft_a, soft_w).convert("RGBA")

    deco = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(deco)
    for cx, cy, r, a in ((150, 210, 20, 190), (930, 165, 26, 210), (80, 420, 13, 150),
                         (990, 700, 17, 170), (205, 1105, 24, 200), (880, 1160, 14, 160),
                         (540, 130, 12, 150), (760, 1020, 10, 130)):
        _sparkle(d, cx, cy, r, (255, 255, 255, a))
    img = Image.alpha_composite(img, deco).convert("RGB")
    draw = ImageDraw.Draw(img)

    kicker = (spec.get("kicker") or spec.get("category") or "").upper()
    if kicker:
        kf = _font(26, bold=True)
        draw.text(((W - draw.textlength(kicker, font=kf)) / 2, PAD + 34), kicker,
                  font=kf, fill=(255, 255, 255))

    font, wrapped, th = _fit_text_any(
        draw, spec.get("headline", ""), W - 2 * PAD - 60, H * 0.5,
        (78, 70, 62, 56, 50, 44), lambda s: _special_font(_SERIF_ITALIC_FONTS, s, bold=False),
        spacing=18,
    )
    top = (H - th) // 2 - 20
    hw = max(draw.textlength(line, font=font) for line in wrapped.split("\n"))
    draw.multiline_text(((W - hw) / 2, top), wrapped, font=font, fill=(255, 255, 255),
                        spacing=18, align="center")
    _sparkle(draw, W // 2, top - 76, 16, (255, 255, 255, 235))
    _sparkle(draw, W // 2, top + th + 92, 16, (255, 255, 255, 235))

    if handle:
        hf = _font(28, bold=True)
        draw.text(((W - draw.textlength(handle, font=hf)) / 2, H - PAD - 44),
                  handle, font=hf, fill=(255, 255, 255))
    return img


def _draw_qna_sticker(spec: dict, accent, handle) -> Image.Image:
    """IG question-sticker: rotated white card with accent header band + fake answer bar."""
    img = _background()
    draw = ImageDraw.Draw(img)
    _eyebrow_and_handle(draw, spec.get("category", ""), handle, accent)

    ink = (24, 24, 32)
    card_w = W - 2 * PAD - 60
    pad_in = 44
    band_h = 86

    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    font, wrapped, th = _fit_text(tmp, spec.get("headline", ""), card_w - 2 * pad_in,
                                  H * 0.32, (56, 50, 44, 40, 36))
    bar_h = 92
    card_h = band_h + 34 + th + 40 + bar_h + pad_in

    card = Image.new("RGBA", (card_w, card_h), (252, 252, 255, 255))
    cdraw = ImageDraw.Draw(card)
    # Accent gradient header band (horizontal blend accent → lighter accent).
    light = tuple(min(255, int(c * 0.55 + 130)) for c in accent)
    for xx in range(card_w):
        t = xx / card_w
        col = tuple(int(accent[i] + (light[i] - accent[i]) * t) for i in range(3))
        cdraw.line([(xx, 0), (xx, band_h)], fill=col)
    kicker = (spec.get("kicker") or "ASK YOURSELF").upper()
    kf = _font(30, bold=True)
    cdraw.text(((card_w - cdraw.textlength(kicker, font=kf)) / 2, band_h / 2 - 20),
               kicker, font=kf, fill=(255, 255, 255))
    # Question text.
    hw = max(cdraw.textlength(line, font=font) for line in wrapped.split("\n"))
    cdraw.multiline_text(((card_w - hw) / 2, band_h + 34), wrapped, font=font,
                         fill=ink, spacing=8, align="center")
    # Fake answer bar.
    by = band_h + 34 + th + 40
    cdraw.rounded_rectangle([pad_in, by, card_w - pad_in, by + bar_h], radius=20,
                            fill=(240, 240, 246), outline=(212, 212, 222), width=2)
    pf = _special_font(_ITALIC_FONTS, 30, bold=False)
    cdraw.text((pad_in + 30, by + bar_h / 2 - 19), "type something...", font=pf,
               fill=(148, 148, 162))

    card = _rounded(card.convert("RGB"), 28)
    rot = card.rotate(-1.5, expand=True, resample=Image.BICUBIC)
    x = (W - rot.width) // 2
    y = PAD + 70 + (H - PAD - 70 - PAD - 130 - rot.height) // 2

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x + 10, y + 18, x + rot.width, y + rot.height + 12], radius=28, fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img.convert("RGBA"),
                                shadow.filter(ImageFilter.GaussianBlur(13)))
    img.paste(rot, (x, y), rot)
    img = img.convert("RGB")
    _draw_footer(img, ImageDraw.Draw(img), spec.get("cta", ""), accent)
    return img


def _draw_stat_hero(spec: dict, accent, handle) -> Image.Image:
    """Data post: giant accent stat, bold context headline, body, source, faint chart."""
    img = _background()
    draw = ImageDraw.Draw(img)

    # Faint rising polyline chart in the lower half.
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    pts = [(-20, H - 150), (230, H - 290), (450, H - 225), (700, H - 400), (W + 20, H - 520)]
    od.line(pts, fill=accent + (52,), width=8, joint="curve")
    for px, py in pts[1:-1]:
        od.ellipse([px - 11, py - 11, px + 11, py + 11], fill=accent + (72,))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    _eyebrow_and_handle(draw, spec.get("category", ""), handle, accent)

    stat = spec.get("stat", "")
    sf = _fit_line(draw, stat, (320, 280, 240, 200, 165, 135, 105),
                   lambda s: _special_font(_DISPLAY_FONTS, s), W - 2 * PAD)
    sb = draw.textbbox((0, 0), stat, font=sf)
    sw, sh = sb[2] - sb[0], sb[3] - sb[1]

    ctx_f, ctx_w, ctx_h = _fit_text(draw, spec.get("context", ""), W - 2 * PAD - 40,
                                    H * 0.22, (58, 52, 46, 40))
    body = spec.get("body", "")
    bf, bwrapped, bh = (_fit_text(draw, body, W - 2 * PAD - 100, H * 0.14, (34, 30),
                                  bold=False) if body else (None, "", 0))
    source = spec.get("source", "")
    src_h = 52 if source else 0
    block = sh + 46 + ctx_h + ((36 + bh) if body else 0) + ((30 + src_h) if source else 0)
    y = PAD + 70 + (H - PAD - 70 - PAD - 140 - block) // 2

    draw.text(((W - sw) / 2 - sb[0], y - sb[1]), stat, font=sf, fill=accent)
    y += sh + 46
    cw = max(draw.textlength(line, font=ctx_f) for line in ctx_w.split("\n"))
    draw.multiline_text(((W - cw) / 2, y), ctx_w, font=ctx_f, fill=WHITE,
                        spacing=8, align="center")
    y += ctx_h + 36
    if body:
        bw = max(draw.textlength(line, font=bf) for line in bwrapped.split("\n"))
        draw.multiline_text(((W - bw) / 2, y), bwrapped, font=bf, fill=MUTED,
                            spacing=6, align="center")
        y += bh + 30
    if source:
        srcf = _font(24)
        text = f"source: {source}"
        draw.text(((W - draw.textlength(text, font=srcf)) / 2, y + 10), text,
                  font=srcf, fill=MUTED)

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_definition_card(spec: dict, accent, handle) -> Image.Image:
    """Dictionary entry on cream: big lowercase word, phonetic, meaning, italic example."""
    ink, sub = (26, 26, 30), (128, 124, 116)
    cream_top, cream_bottom = (250, 247, 240), (238, 232, 220)
    img = Image.new("RGB", (W, H))
    for yy in range(H):
        t = yy / H
        row = tuple(int(cream_top[i] + (cream_bottom[i] - cream_top[i]) * t) for i in range(3))
        ImageDraw.Draw(img).line([(0, yy), (W, yy)], fill=row)
    draw = ImageDraw.Draw(img)

    _eyebrow_and_handle(draw, spec.get("category", ""), handle, accent, light=True)

    # Measure every block first so the whole entry can be vertically centered.
    word = (spec.get("word") or "").lower()
    wf = _fit_line(draw, word, (150, 132, 116, 100, 86, 72, 60),
                   lambda s: _special_font(_SERIF_FONTS, s), W - 2 * PAD)
    wb = draw.textbbox((0, 0), word, font=wf)
    wh = wb[3] - wb[1]

    pos = spec.get("part_of_speech", "")
    phonetic = spec.get("phonetic", "")
    pos_h = 100 if (pos or phonetic) else 0

    meaning = spec.get("meaning", "")
    mf, mwrapped, mh = _fit_text_any(
        draw, meaning, W - 2 * PAD - 30, H * 0.30, (52, 48, 44, 40, 36, 32),
        lambda s: _special_font(_SERIF_FONTS[1:], s, bold=False), spacing=16,
    )
    example = spec.get("example", "")
    ef, ewrapped, eh = (_fit_text_any(
        draw, f"“{example}”", W - 2 * PAD - 60, H * 0.16, (40, 36, 32),
        lambda s: _special_font(_SERIF_ITALIC_FONTS, s, bold=False), spacing=10,
    ) if example else (None, "", 0))

    block = wh + 44 + pos_h + 74 + mh + ((70 + eh) if example else 0)
    y = PAD + 90 + max(0, (H - PAD - 90 - PAD - 80 - block)) // 2

    draw.text((PAD - wb[0], y - wb[1]), word, font=wf, fill=ink)
    y += wh + 44

    if pos or phonetic:
        pf = _special_font(_SERIF_ITALIC_FONTS, 40, bold=False)
        phf = _special_font(_PHONETIC_FONTS, 36, bold=False)
        x = PAD
        if pos:
            draw.text((x, y), pos, font=pf, fill=accent)
            x += draw.textlength(pos, font=pf) + 38
        if phonetic:
            draw.text((x, y + 4), phonetic, font=phf, fill=sub)
        y += pos_h

    draw.line([(PAD, y), (W - PAD, y)], fill=(206, 199, 186), width=2)
    y += 74

    draw.multiline_text((PAD, y), mwrapped, font=mf, fill=ink, spacing=16)
    y += mh + 70

    if example:
        draw.rounded_rectangle([PAD, y + 4, PAD + 7, y + eh + 12], radius=3, fill=accent)
        draw.multiline_text((PAD + 34, y), ewrapped, font=ef, fill=sub, spacing=10)

    ff = _special_font(_SERIF_ITALIC_FONTS, 28, bold=False)
    draw.text((PAD, H - PAD - 34), "— modern dictionary", font=ff, fill=sub)
    if handle:
        hf = _font(26)
        draw.text((W - PAD - draw.textlength(handle, font=hf), H - PAD - 32),
                  handle, font=hf, fill=sub)
    return img


def _draw_this_or_that(spec: dict, accent, handle) -> Image.Image:
    """Engagement bait: two huge A/B choice panels side by side with a center VS badge."""
    img = _background()
    draw = ImageDraw.Draw(img)
    _eyebrow_and_handle(draw, spec.get("category", ""), handle, accent)

    tf, twrapped, th = _fit_text(draw, spec.get("title", ""), W - 2 * PAD, 170, (60, 52, 46, 40))
    tw = max(draw.textlength(line, font=tf) for line in twrapped.split("\n"))
    draw.multiline_text(((W - tw) / 2, PAD + 54), twrapped, font=tf, fill=WHITE,
                        spacing=8, align="center")
    body_top = PAD + 54 + th + 36
    footer_top = H - PAD - 84 - 24

    left, right = spec["left"][0], spec["right"][0]
    gap = 22
    col_w = (W - 2 * PAD - gap) // 2
    panel_h = footer_top - body_top
    tiles = _panel_images([left["image"], right["image"]], (col_w, panel_h))

    badge_f = _font(44, bold=True)
    for i, (item, tile, bx) in enumerate(((left, tiles[0], PAD),
                                          (right, tiles[1], PAD + col_w + gap))):
        panel = _scrim(tile, start=0.42, strength=235)
        pdraw = ImageDraw.Draw(panel)
        # Circled A/B badge.
        pdraw.ellipse([24, 24, 112, 112], fill=accent, outline=(255, 255, 255), width=4)
        letter = "AB"[i]
        lb = pdraw.textbbox((0, 0), letter, font=badge_f)
        pdraw.text((68 - (lb[2] - lb[0]) / 2 - lb[0], 68 - (lb[3] - lb[1]) / 2 - lb[1]),
                   letter, font=badge_f, fill=(255, 255, 255))
        # Giant label near the bottom.
        lf, lwrapped, lh = _fit_text(pdraw, item["label"], col_w - 52, panel_h * 0.34,
                                     (58, 50, 44, 38, 34))
        lw = max(pdraw.textlength(line, font=lf) for line in lwrapped.split("\n"))
        pdraw.multiline_text(((col_w - lw) / 2, panel_h - lh - 44), lwrapped, font=lf,
                             fill=WHITE, spacing=6, align="center")
        rounded = _rounded(panel.convert("RGB"), 26)
        img.paste(rounded, (bx, body_top), rounded)

    cx, cy = W // 2, body_top + panel_h // 2
    draw.ellipse([cx - 52, cy - 52, cx + 52, cy + 52], fill=(14, 14, 20),
                 outline=(255, 255, 255), width=4)
    vf = _font(40, bold=True)
    vb = draw.textbbox((0, 0), "VS", font=vf)
    draw.text((cx - (vb[2] - vb[0]) / 2 - vb[0], cy - (vb[3] - vb[1]) / 2 - vb[1]),
              "VS", font=vf, fill=(255, 255, 255))

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_before_after(spec: dict, accent, handle) -> Image.Image:
    """Top/bottom transformation split: BEFORE panel (red pill) over AFTER panel (green)."""
    img = _background()
    draw = ImageDraw.Draw(img)
    body_top = _draw_header(img, draw, spec, accent, handle)
    footer_top = H - PAD - 84 - 24

    left, right = spec["left"][0], spec["right"][0]
    gap = 66
    panel_w = W - 2 * PAD
    panel_h = (footer_top - body_top - gap) // 2
    tiles = _panel_images([left["image"], right["image"]], (panel_w, panel_h))

    tag_f = _font(28, bold=True)
    for item, tile, py, tag, color in (
        (left, tiles[0], body_top, "BEFORE", GLITCH_RED),
        (right, tiles[1], body_top + panel_h + gap, "AFTER", REBOOT_GREEN),
    ):
        panel = _scrim(tile, start=0.45, strength=230)
        pdraw = ImageDraw.Draw(panel)
        text_w = pdraw.textlength(tag, font=tag_f)
        pdraw.rounded_rectangle([24, 24, 24 + text_w + 52, 24 + 56], radius=28, fill=color)
        pdraw.text((24 + 26, 24 + 13), tag, font=tag_f, fill=(255, 255, 255))
        lf, lwrapped, lh = _fit_text(pdraw, item["label"], panel_w - 60, panel_h * 0.32,
                                     (48, 42, 38, 34))
        pdraw.multiline_text((30, panel_h - lh - 30), lwrapped, font=lf, fill=WHITE, spacing=6)
        rounded = _rounded(panel.convert("RGB"), 26)
        img.paste(rounded, (PAD, py), rounded)

    # Downward arrow in the gap.
    ay = body_top + panel_h + gap // 2
    draw.line([(W // 2, ay - 16), (W // 2, ay + 10)], fill=accent, width=8)
    draw.polygon([(W // 2 - 15, ay + 6), (W // 2 + 15, ay + 6), (W // 2, ay + 24)], fill=accent)

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


def _draw_grid_ranking(spec: dict, accent, handle) -> Image.Image:
    """Ranked list: medal circles for the top 3, muted rank numerals for the rest."""
    gold, silver, bronze = (212, 175, 55), (170, 180, 190), (205, 127, 50)
    img = _background()
    draw = ImageDraw.Draw(img)
    body_top = _draw_header(img, draw, spec, accent, handle)
    footer_top = H - PAD - 84 - 24

    items = spec["items"]
    n = len(items)
    row_gap = 16
    row_h = (footer_top - body_top - (n - 1) * row_gap) // n
    thumb = min(row_h - 10, 144)
    rank_w = 118

    tiles = _panel_images([it["image"] for it in items], (thumb, thumb))
    medal_f = _font(38, bold=True)
    rank_f = _font(48, bold=True)
    label_font = _font(36, bold=True)

    for idx, (item, tile) in enumerate(zip(items, tiles)):
        y = body_top + idx * (row_h + row_gap)
        cy = y + row_h // 2
        num = f"#{idx + 1}"
        if idx < 3:
            color = (gold, silver, bronze)[idx]
            r = 44
            cxm = PAD + rank_w // 2 - 6
            draw.ellipse([cxm - r, cy - r, cxm + r, cy + r], fill=color)
            nb = draw.textbbox((0, 0), num, font=medal_f)
            draw.text((cxm - (nb[2] - nb[0]) / 2 - nb[0], cy - (nb[3] - nb[1]) / 2 - nb[1]),
                      num, font=medal_f, fill=(20, 18, 14))
        else:
            nb = draw.textbbox((0, 0), num, font=rank_f)
            draw.text((PAD + rank_w // 2 - 6 - (nb[2] - nb[0]) / 2 - nb[0],
                       cy - (nb[3] - nb[1]) / 2 - nb[1]), num, font=rank_f, fill=MUTED)

        tx = PAD + rank_w
        rounded = _rounded(tile, 18)
        img.paste(rounded, (tx, cy - thumb // 2), rounded)

        lx = tx + thumb + 26
        label = _wrap(draw, item["label"], label_font, W - PAD - lx)
        lb = draw.multiline_textbbox((0, 0), label, font=label_font, spacing=4)
        draw.multiline_text((lx, cy - (lb[3] - lb[1]) / 2 - 4), label, font=label_font,
                            fill=WHITE, spacing=4)
        if idx < n - 1:
            dy = y + row_h + row_gap // 2
            draw.line([(PAD, dy), (W - PAD, dy)], fill=(42, 42, 56), width=2)

    _draw_footer(img, draw, spec.get("cta", ""), accent)
    return img


# --- Overlay templates (single AI image + composed tagline) ---

def _load_bg(image_file: str | None) -> Image.Image:
    if image_file:
        try:
            src = Image.open(config.IMAGES_DIR / image_file).convert("RGB")
            return ImageOps.fit(src, (W, H), Image.LANCZOS)
        except Exception:  # noqa: BLE001
            pass
    return _gradient_tile((W, H))


def _fit_text(draw, text, max_w, max_h, sizes, bold=True):
    """Return (font, wrapped, height) for the largest size that fits the box."""
    font, wrapped, h = _font(sizes[-1], bold=bold), text, 0
    for size in sizes:
        font = _font(size, bold=bold)
        wrapped = _wrap(draw, text, font, max_w)
        bb = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=10)
        h = bb[3] - bb[1]
        if h <= max_h:
            break
    return font, wrapped, h


def _eyebrow_and_handle(draw, category, handle, accent, y=PAD, light=False):
    if category:
        draw.text((PAD, y), category.upper(), font=_font(26, bold=True), fill=accent)
    if handle:
        hf = _font(26)
        col = (90, 90, 100) if light else (215, 215, 225)
        draw.text((W - PAD - draw.textlength(handle, font=hf), y), handle, font=hf, fill=col)


def _overlay_classic(bg, tagline, accent, handle, category="") -> Image.Image:
    """Full-bleed image, tagline bottom-left over a scrim with an accent bar."""
    img = _scrim(bg, start=0.32, strength=238).convert("RGB")
    draw = ImageDraw.Draw(img)
    _eyebrow_and_handle(draw, category, handle, accent)
    font, wrapped, th = _fit_text(draw, tagline, W - 2 * PAD, H * 0.42, (94, 84, 74, 64, 56))
    y = H - PAD - th
    draw.rounded_rectangle([PAD, y - 34, PAD + 110, y - 26], radius=4, fill=accent)
    draw.multiline_text((PAD, y), wrapped, font=font, fill=WHITE, spacing=10)
    return img


def _overlay_center(bg, tagline, accent, handle, category="") -> Image.Image:
    """Uniformly darkened image with a big centered quote."""
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 125))
    img = Image.alpha_composite(bg.convert("RGBA"), dark).convert("RGB")
    draw = ImageDraw.Draw(img)
    font, wrapped, th = _fit_text(draw, tagline, W - 2 * PAD - 30, H * 0.5, (98, 86, 76, 66, 58))
    top = (H - th) // 2
    draw.rounded_rectangle([W // 2 - 44, top - 46, W // 2 + 44, top - 38], radius=4, fill=accent)
    bw = max(draw.textlength(line, font=font) for line in wrapped.split("\n"))
    draw.multiline_text(((W - bw) // 2, top), wrapped, font=font, fill=WHITE, spacing=12, align="center")
    if handle:
        hf = _font(28, bold=True)
        draw.text(((W - draw.textlength(handle, font=hf)) // 2, H - PAD - 44), handle, font=hf, fill=accent)
    return img


def _overlay_band(bg, tagline, accent, handle, category="") -> Image.Image:
    """Image with a solid caption band across the bottom (magazine style)."""
    img = bg.convert("RGB")
    draw = ImageDraw.Draw(img)
    font, wrapped, th = _fit_text(draw, tagline, W - 2 * PAD, H * 0.30, (72, 64, 58, 52, 46))
    band_h = th + 150
    band_top = H - band_h
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(band).rectangle([0, band_top, W, H], fill=(12, 12, 18, 236))
    img = Image.alpha_composite(img.convert("RGBA"), band).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, band_top, W, band_top + 6], fill=accent)
    ty = band_top + 38
    if category:
        draw.text((PAD, ty), category.upper(), font=_font(24, bold=True), fill=accent)
        ty += 36
    draw.multiline_text((PAD, ty), wrapped, font=font, fill=WHITE, spacing=8)
    if handle:
        hf = _font(24)
        draw.text((W - PAD - draw.textlength(handle, font=hf), band_top + 38), handle, font=hf, fill=MUTED)
    return img


def _overlay_tweet(bg, tagline, accent, handle, category="") -> Image.Image:
    """White tweet-style card centered on the darkened image: avatar, handle, tagline, icons."""
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 150))
    img = Image.alpha_composite(bg.convert("RGBA"), dark).convert("RGB")
    draw = ImageDraw.Draw(img)

    card_w = W - 2 * PAD - 30
    pad_in = 46
    ink = (20, 24, 32)
    gray = (101, 119, 134)

    name_f = _font(34, bold=True)
    sub_f = _font(26)
    font, wrapped, th = _fit_text(draw, tagline, card_w - 2 * pad_in, H * 0.38,
                                  (54, 48, 42, 38, 34), bold=False)
    avatar = 84
    card_h = pad_in + avatar + 30 + th + 46 + 34 + pad_in
    x0 = (W - card_w) // 2
    y0 = (H - card_h) // 2
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x0 + 6, y0 + 16, x0 + card_w + 10, y0 + card_h + 22], radius=34, fill=(0, 0, 0, 160))
    img = Image.alpha_composite(img.convert("RGBA"),
                                shadow.filter(ImageFilter.GaussianBlur(14))).convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([x0, y0, x0 + card_w, y0 + card_h], radius=34,
                           fill=(250, 250, 252))
    draw.rounded_rectangle([x0, y0, x0 + card_w, y0 + card_h], radius=34,
                           outline=(255, 255, 255, 60), width=1)

    # Avatar + names.
    ax, ay = x0 + pad_in, y0 + pad_in
    draw.ellipse([ax, ay, ax + avatar, ay + avatar], fill=accent)
    initial = (handle or "@g").lstrip("@")[:1].upper()
    inf = _font(40, bold=True)
    ib = draw.textbbox((0, 0), initial, font=inf)
    draw.text((ax + avatar / 2 - (ib[2] - ib[0]) / 2, ay + avatar / 2 - (ib[3] - ib[1]) / 2 - 8),
              initial, font=inf, fill=(255, 255, 255))
    nx = ax + avatar + 22
    draw.text((nx, ay + 6), handle or "", font=name_f, fill=ink)
    if category:
        draw.text((nx, ay + 48), f"@{category.lower().replace(' ', '')}", font=sub_f, fill=gray)

    # Tweet text.
    ty = ay + avatar + 30
    draw.multiline_text((x0 + pad_in, ty), wrapped, font=font, fill=ink, spacing=10)

    # Engagement icons (drawn, no fake numbers): reply bubble, retweet arrows, heart.
    iy = ty + th + 46
    ix = x0 + pad_in
    # reply bubble
    draw.rounded_rectangle([ix, iy, ix + 34, iy + 26], radius=12, outline=gray, width=3)
    draw.polygon([(ix + 8, iy + 24), (ix + 8, iy + 34), (ix + 18, iy + 24)], fill=gray)
    # retweet arrows
    rx = ix + 150
    draw.line([(rx + 6, iy + 8), (rx + 26, iy + 8)], fill=gray, width=3)
    draw.line([(rx + 26, iy + 8), (rx + 26, iy + 22)], fill=gray, width=3)
    draw.polygon([(rx, iy + 8), (rx + 12, iy + 8), (rx + 6, iy)], fill=gray)
    draw.line([(rx + 8, iy + 26), (rx + 28, iy + 26)], fill=gray, width=3)
    draw.line([(rx + 8, iy + 26), (rx + 8, iy + 12)], fill=gray, width=3)
    draw.polygon([(rx + 22, iy + 26), (rx + 34, iy + 26), (rx + 28, iy + 34)], fill=gray)
    # heart: two circles + polygon
    hx = ix + 300
    draw.ellipse([hx, iy + 4, hx + 16, iy + 20], fill=gray)
    draw.ellipse([hx + 14, iy + 4, hx + 30, iy + 20], fill=gray)
    draw.polygon([(hx + 1, iy + 15), (hx + 15, iy + 32), (hx + 29, iy + 15)], fill=gray)
    return img


def _overlay_polaroid(bg, tagline, accent, handle, category="") -> Image.Image:
    """One large slightly-rotated polaroid with the tagline handwritten in the bottom band."""
    img = _background()
    draw = ImageDraw.Draw(img)
    _eyebrow_and_handle(draw, category, "", accent)

    border = 26
    card_w = W - 2 * PAD - 44
    photo_w = card_w - 2 * border
    photo_h = 820
    photo = ImageOps.fit(bg.convert("RGB"), (photo_w, photo_h), Image.LANCZOS)

    card_tmp = Image.new("RGB", (10, 10))
    tdraw = ImageDraw.Draw(card_tmp)
    font, wrapped, th = _fit_text_any(
        tdraw, tagline, photo_w - 20, 190, (52, 46, 40, 36, 32),
        lambda s: _special_font(_HAND_FONTS, s), spacing=8,
    )
    band = th + 78
    card_h = border + photo_h + band

    card = Image.new("RGBA", (card_w, card_h), (252, 250, 245, 255))
    card.paste(photo, (border, border))
    cdraw = ImageDraw.Draw(card)
    lw = max(cdraw.textlength(line, font=font) for line in wrapped.split("\n"))
    cdraw.multiline_text(((card_w - lw) / 2, border + photo_h + (band - th) / 2 - 10),
                         wrapped, font=font, fill=(42, 40, 46), spacing=8, align="center")

    rot = card.rotate(-2, expand=True, resample=Image.BICUBIC)
    x = (W - rot.width) // 2
    y = PAD + 44 + (H - PAD - 44 - PAD - 60 - rot.height) // 2 + 10

    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x + 14, y + 20, x + rot.width - 4, y + rot.height + 14], radius=14, fill=(0, 0, 0, 120))
    img = Image.alpha_composite(img.convert("RGBA"),
                                shadow.filter(ImageFilter.GaussianBlur(12)))
    img.paste(rot, (x, y), rot)
    img = img.convert("RGB")
    if handle:
        d = ImageDraw.Draw(img)
        hf = _font(26)
        d.text((W - PAD - d.textlength(handle, font=hf), H - PAD - 20), handle,
               font=hf, fill=MUTED)
    return img


def _overlay_editorial(bg, tagline, accent, handle, category="") -> Image.Image:
    """Film-still: letterboxed image, serif tagline in the bottom bar, category chip on top."""
    bar = 180
    img = Image.new("RGB", (W, H), (6, 6, 9))
    frame = ImageOps.fit(bg.convert("RGB"), (W, H - 2 * bar), Image.LANCZOS)
    img.paste(frame, (0, bar))
    draw = ImageDraw.Draw(img)

    # Category chip in the top bar.
    if category:
        cf = _font(26, bold=True)
        text = category.upper()
        tw = draw.textlength(text, font=cf)
        cx0, cy0 = PAD, bar // 2 - 28
        draw.rounded_rectangle([cx0, cy0, cx0 + tw + 56, cy0 + 56], radius=28,
                               outline=accent, width=3)
        draw.text((cx0 + 28, cy0 + 13), text, font=cf, fill=accent)

    # Serif tagline centered in the bottom bar.
    font, wrapped, th = _fit_text_any(
        draw, tagline, W - 2 * PAD, bar - 56, (54, 48, 42, 38, 34, 30),
        lambda s: _special_font(_SERIF_FONTS, s), spacing=8,
    )
    tw = max(draw.textlength(line, font=font) for line in wrapped.split("\n"))
    draw.multiline_text(((W - tw) / 2, H - bar + (bar - 44 - th) / 2 - 4), wrapped,
                        font=font, fill=(244, 242, 238), spacing=8, align="center")
    if handle:
        hf = _font(24)
        draw.text((W - PAD - draw.textlength(handle, font=hf), H - 42), handle,
                  font=hf, fill=MUTED)
    return img


_DESIGNS = {
    "grid": _draw_grid,
    "grid-light": _draw_grid_light,
    "grid-list": _draw_grid_list,
    "grid-polaroid": _draw_grid_polaroid,
    "grid-steps": _draw_grid_steps,
    "grid-checklist": _draw_grid_checklist,
    "grid-neon": _draw_grid_neon,
    "grid-mag": _draw_grid_mag,
    "grid-ranking": _draw_grid_ranking,
    "vs": _draw_vs,
    "vs-split": _draw_vs_split,
    "this-or-that": _draw_this_or_that,
    "before-after": _draw_before_after,
    "quote-serif": _draw_quote_serif,
    "quote-neon": _draw_quote_neon,
    "did-you-know": _draw_did_you_know,
    "affirmation": _draw_affirmation,
    "qna-sticker": _draw_qna_sticker,
    "stat-hero": _draw_stat_hero,
    "definition-card": _draw_definition_card,
}

# Which sample spec each design consumes when rendering previews.
_DESIGN_SAMPLE = {
    "this-or-that": "vs",
    "before-after": "vs",
    "quote-serif": "card",
    "quote-neon": "card",
    "did-you-know": "card",
    "affirmation": "card",
    "qna-sticker": "card",
    "stat-hero": "stat",
    "definition-card": "definition",
}

_OVERLAY_DESIGNS = {
    "overlay-classic": _overlay_classic,
    "overlay-center": _overlay_center,
    "overlay-band": _overlay_band,
    "overlay-tweet": _overlay_tweet,
    "overlay-polaroid": _overlay_polaroid,
    "overlay-editorial": _overlay_editorial,
}


def compose(spec: dict, brand: dict, design: str | None = None) -> str:
    """Render `spec` with the chosen design and return the image filename in IMAGES_DIR."""
    accent = _hex(brand.get("accent", ""))
    handle = brand.get("handle", "")
    renderer = _DESIGNS.get(design or spec.get("type", "grid"), _draw_grid)
    img = renderer(spec, accent, handle)
    filename = _timestamped_name((design or spec.get("type", "post")).replace("-", ""))
    img.save(config.IMAGES_DIR / filename)
    return filename


def compose_overlay(design: str, image_file: str | None, tagline: str, brand: dict,
                    category: str = "") -> str:
    """Render a single-image overlay poster and return the image filename in IMAGES_DIR."""
    accent = _hex(brand.get("accent", ""))
    handle = brand.get("handle", "")
    renderer = _OVERLAY_DESIGNS.get(design, _overlay_classic)
    img = renderer(_load_bg(image_file), tagline, accent, handle, category)
    filename = _timestamped_name(design.replace("-", ""))
    img.save(config.IMAGES_DIR / filename)
    return filename


# --- Template previews (rendered with placeholder tiles, no AI) ---

PREVIEW_DESIGNS = list(_DESIGNS.keys()) + list(_OVERLAY_DESIGNS.keys())
PREVIEW_DIR = config.BASE_DIR / "app" / "static" / "previews"


def _sample_spec(design: str) -> dict:
    """A canned spec (empty image prompts → gradient tiles) used only for layout previews."""
    kind = _DESIGN_SAMPLE.get(design, "vs" if design.startswith("vs") else "grid")
    if kind == "card":
        return {
            "type": "card",
            "kind": "quote",
            "kicker": "MODERN WISDOM",
            "headline": "we scroll to feel less alone and end up more alone",
            "body": "connection was never meant to fit in a feed.",
            "attribution": "glitch.life",
            "cta": "Share if you felt this",
            "category": "Screen Static",
        }
    if kind == "stat":
        return {
            "type": "stat",
            "stat": "6h 42m",
            "context": "average daily screen time in 2026",
            "body": "that's over 100 full days a year staring at a screen.",
            "source": "digital wellness report",
            "cta": "Time to log off?",
            "category": "Screen Static",
        }
    if kind == "definition":
        return {
            "type": "definition",
            "word": "doomscroll",
            "phonetic": "/duːm.skrəʊl/",
            "part_of_speech": "verb",
            "meaning": "to compulsively consume negative content online despite its harm to your mood",
            "example": "i lost two hours doomscrolling before bed.",
            "category": "Modern Dictionary",
        }
    if kind == "vs":
        return {
            "type": "vs",
            "category": "Screen Static",
            "title": "The Glitch vs The Reboot",
            "left_title": "The Glitch",
            "right_title": "The Reboot",
            "left": [{"label": x, "image": ""} for x in
                     ["Doomscroll", "Endless Feed", "Comparison", "Late Nights", "Numb Mind"]],
            "right": [{"label": x, "image": ""} for x in
                      ["Be Present", "Read a Book", "Log Off", "Real Sleep", "Clear Mind"]],
            "cta": "Take back control",
        }
    return {
        "type": "grid",
        "category": "Stuck on Autopilot",
        "title": "6 Signs You're Stuck",
        "items": [{"label": x, "image": ""} for x in
                  ["Mindless Scrolling", "Sunday Dread", "Empty Feed",
                   "Numb Evenings", "Autopilot Days", "Quiet Burnout"]],
        "cta": "Which one hits?",
    }


def render_previews(brand: dict) -> None:
    """Render one sample poster per design to static/previews/<design>.png (fast, no AI)."""
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    accent = _hex(brand.get("accent", ""))
    handle = brand.get("handle", "")
    for design, renderer in _DESIGNS.items():
        try:
            img = renderer(_sample_spec(design), accent, handle)
            img.save(PREVIEW_DIR / f"{design}.png")
        except Exception as exc:  # noqa: BLE001
            print(f"[composer] preview for {design} failed ({exc})")

    sample_tagline = "the quiet ache no one talks about"
    for design, renderer in _OVERLAY_DESIGNS.items():
        try:
            img = renderer(_gradient_tile((W, H)), sample_tagline, accent, handle, "Mental Static")
            img.save(PREVIEW_DIR / f"{design}.png")
        except Exception as exc:  # noqa: BLE001
            print(f"[composer] preview for {design} failed ({exc})")
