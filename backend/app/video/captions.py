"""Word-timed burned-in captions, rendered with PIL + overlaid by ffmpeg.

We draw each caption chunk as a transparent PNG with our own brand fonts and let ffmpeg
show it during its spoken window (overlay enable=between(t,start,end)). No libass needed —
the Homebrew ffmpeg build ships without the subtitles filter.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .. import composer

VW, VH = 1080, 1920
_CAPTION_Y = VH - 560  # sits in the lower third, above the safe area


def _chunks(words: list[dict], max_words: int = 3, max_gap: float = 0.6):
    """Group word timings into short caption chunks (2-3 words reads best on Reels)."""
    chunk: list[dict] = []
    for w in words:
        if chunk and (len(chunk) >= max_words or w["start"] - chunk[-1]["end"] > max_gap):
            yield chunk
            chunk = []
        chunk.append(w)
    if chunk:
        yield chunk


def render_caption_pngs(
    words: list[dict], work: Path, accent_hex: str = "#a855f7"
) -> list[tuple[Path, float, float]]:
    """One transparent PNG per chunk. Returns [(png_path, start_s, end_s)]."""
    accent = composer._hex(accent_hex)
    font = composer._font(84, bold=True)
    out: list[tuple[Path, float, float]] = []

    for i, chunk in enumerate(_chunks(words)):
        text = " ".join(w["word"] for w in chunk)
        layer = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        wrapped = composer._wrap(d, text, font, VW - 160)
        bb = d.multiline_textbbox((0, 0), wrapped, font=font, spacing=8)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x, y = (VW - tw) / 2, _CAPTION_Y - th / 2
        # pill backing for guaranteed legibility over any footage
        pad = 34
        d.rounded_rectangle([x - pad, y - pad + 8, x + tw + pad, y + th + pad + 14],
                            radius=26, fill=(10, 10, 14, 200))
        # accent keyword: last word of the chunk pops in the accent colour
        head = " ".join(w["word"] for w in chunk[:-1])
        d.multiline_text((x, y), wrapped, font=font, fill=(250, 250, 252), spacing=8,
                         align="center")
        if head and "\n" not in wrapped:
            # overpaint the final word in accent (single-line chunks only — the common case)
            head_w = d.textlength(head + " ", font=font)
            d.text((x + head_w, y), chunk[-1]["word"], font=font, fill=(*accent, 255))
        path = work / f"cap{i}.png"
        layer.save(path)
        out.append((path, chunk[0]["start"], chunk[-1]["end"] + 0.15))
    return out
