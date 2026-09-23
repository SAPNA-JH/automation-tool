"""ffmpeg assembly engine: Ken Burns clips, slide decks, narrated scenes → 1080x1920 Reels."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageOps

from .. import composer, config
from ..providers import images
from . import captions as caps
from . import music

VW, VH, FPS = 1080, 1920, 30
# Working resolution for Ken Burns zoompan. Was 2× (2160×3840) which is heavy on
# ffmpeg RAM; 1.5× keeps the zoom smooth at a fraction of the memory.
ZW, ZH = int(VW * 1.5), int(VH * 1.5)
VIDEOS_DIR = config.DATA_DIR / "videos"
FONTS_DIR = config.BASE_DIR / "assets" / "fonts"


def _ffmpeg() -> str:
    return shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def available_mb() -> float | None:
    """Free memory in this container (cgroup-aware), or None if it can't be read."""
    pairs = (
        ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory.max"),          # cgroup v2
        ("/sys/fs/cgroup/memory/memory.usage_in_bytes",                          # cgroup v1
         "/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    )
    for cur_p, max_p in pairs:
        try:
            with open(max_p) as f:
                raw = f.read().strip()
            if raw == "max":
                continue
            limit = int(raw)
            if limit >= (1 << 62):  # "unlimited" sentinel
                continue
            with open(cur_p) as f:
                used = int(f.read().strip())
            return (limit - used) / 1e6
        except (OSError, ValueError):
            continue
    return None


def _ff(args: list[str]) -> None:
    proc = subprocess.run(
        [_ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args],
        capture_output=True, text=True, timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr[-600:]}")


def _out_name(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    return f"{prefix}-{stamp}.mp4"


ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
          "-threads", "2",  # cap x264 threads — fewer frame buffers = lower peak RAM
          "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart"]


# ---------------------------------------------------------------------------
# Visual sources
# ---------------------------------------------------------------------------

def portrait_image(prompt: str, work: Path, name: str) -> Path:
    """AI image fitted to 1080x1920 (brand gradient fallback). Returns a PNG path."""
    path = work / f"{name}.png"
    fn = images.generate_raw(prompt) if prompt else None
    if fn:
        try:
            src = Image.open(config.IMAGES_DIR / fn).convert("RGB")
            ImageOps.fit(src, (VW, VH), Image.LANCZOS).save(path)
            return path
        except Exception:  # noqa: BLE001
            pass
    composer._gradient_tile((VW, VH)).save(path)
    return path


def pexels_clip(query: str, seconds: float, work: Path, name: str) -> Path | None:
    """Portrait stock b-roll from Pexels Videos (free key), trimmed/cropped. None on failure."""
    if not config.PEXELS_API_KEY:
        return None
    try:
        resp = httpx.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": config.PEXELS_API_KEY},
            params={"query": query[:80], "orientation": "portrait", "per_page": 5},
            timeout=30,
        )
        resp.raise_for_status()
        for video in resp.json().get("videos", []):
            files = [f for f in video.get("video_files", [])
                     if f.get("file_type") == "video/mp4" and (f.get("height") or 0) >= 1280]
            if not files:
                continue
            url = sorted(files, key=lambda f: f["height"])[0]["link"]
            raw = work / f"{name}-raw.mp4"
            with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
                r.raise_for_status()
                with open(raw, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
            out = work / f"{name}.mp4"
            _ff(["-i", str(raw), "-t", f"{seconds:.2f}",
                 "-vf", f"scale={VW}:{VH}:force_original_aspect_ratio=increase,"
                        f"crop={VW}:{VH},fps={FPS}",
                 "-an", *ENCODE[:10], str(out)])
            return out
    except Exception as exc:  # noqa: BLE001
        print(f"[video] pexels clip failed ({exc}); falling back to image")
    return None


def kenburns_clip(image: Path, seconds: float, work: Path, name: str,
                  zoom: float = 0.10) -> Path:
    """Slow push-in on a still image → silent mp4 segment."""
    frames = int(seconds * FPS)
    out = work / f"{name}.mp4"
    _ff(["-loop", "1", "-t", f"{seconds:.2f}", "-i", str(image),
         "-vf",
         f"scale={ZW}:{ZH},"
         f"zoompan=z='1+{zoom}*on/{frames}':d={frames}:"
         f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':s={VW}x{VH}:fps={FPS}",
         "-an", *ENCODE[:10], str(out)])
    return out


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_quote_reel(spec: dict, brand: dict, bg_prompt: str) -> str:
    """Kinetic text: lines fade in one by one and stack, over a slow-zooming background."""
    lines = spec["lines"]
    per, hold = 2.6, 3.4
    total = per * len(lines) + hold
    accent = composer._hex(brand.get("accent", ""))
    handle = brand.get("handle", "")

    with tempfile.TemporaryDirectory(dir=config.DATA_DIR) as td:
        work = Path(td)
        bg = portrait_image(bg_prompt, work, "bg")
        # darken bg for legibility
        img = Image.open(bg).convert("RGB")
        img = Image.blend(img, Image.new("RGB", img.size, (8, 8, 12)), 0.45)
        img.save(bg)

        # one transparent overlay PNG per line, positioned as a stacked poem
        font = composer._special_font(composer._SERIF_FONTS, 76)
        probe = ImageDraw.Draw(Image.new("RGB", (VW, VH)))
        wrapped = [composer._wrap(probe, l, font, VW - 200) for l in lines]
        heights = [probe.multiline_textbbox((0, 0), w, font=font, spacing=10)[3] for w in wrapped]
        gap = 56
        block_h = sum(heights) + gap * (len(lines) - 1)
        y0 = (VH - block_h) // 2
        overlays = []
        y = y0
        for i, w in enumerate(wrapped):
            layer = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            color = (*accent, 255) if i == len(lines) - 1 else (245, 245, 250, 255)
            d.multiline_text((100, y), w, font=font, fill=color, spacing=10)
            p = work / f"line{i}.png"
            layer.save(p)
            overlays.append(p)
            y += heights[i] + gap

        # static chrome: handle bottom-center
        chrome = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
        d = ImageDraw.Draw(chrome)
        hf = composer._font(34, bold=True)
        if handle:
            d.text(((VW - d.textlength(handle, font=hf)) / 2, VH - 140), handle,
                   font=hf, fill=(235, 235, 240, 220))
        chrome_p = work / "chrome.png"
        chrome.save(chrome_p)

        track = music.pick_track(spec.get("music_mood", "calm"))
        frames = int(total * FPS)

        inputs = ["-loop", "1", "-t", f"{total:.2f}", "-i", str(bg)]
        for p in [*overlays, chrome_p]:
            inputs += ["-loop", "1", "-t", f"{total:.2f}", "-i", str(p)]
        inputs += ["-stream_loop", "-1", "-i", str(track)]

        fc = [f"[0:v]scale={ZW}:{ZH},zoompan=z='1+0.10*on/{frames}':d={frames}:"
              f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':s={VW}x{VH}:fps={FPS}[base]"]
        cur = "base"
        for i in range(len(overlays)):
            st = i * per + 0.3
            fc.append(f"[{i + 1}:v]format=rgba,fade=t=in:st={st:.2f}:d=0.7:alpha=1[o{i}]")
            fc.append(f"[{cur}][o{i}]overlay[v{i}]")
            cur = f"v{i}"
        fc.append(f"[{len(overlays) + 1}:v]format=rgba[ch]")
        fc.append(f"[{cur}][ch]overlay,format=yuv420p[vout]")
        a_idx = len(overlays) + 2
        fc.append(f"[{a_idx}:a]atrim=0:{total:.2f},volume=0.75,"
                  f"afade=t=out:st={total - 1.6:.2f}:d=1.6[aout]")

        out_name = _out_name("reelquote")
        VIDEOS_DIR.mkdir(exist_ok=True)
        _ff([*inputs, "-filter_complex", ";".join(fc),
             "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
             *ENCODE, str(VIDEOS_DIR / out_name)])
    return out_name


def render_story_reel(spec: dict, brand: dict, visual_style: str) -> str:
    """POV micro-story: each short line fades in alone (one at a time) over a moody clip."""
    lines = spec["lines"]
    per, hold = 2.6, 2.2
    total = per * len(lines) + hold
    accent = composer._hex(brand.get("accent", ""))
    handle = brand.get("handle", "")
    bg_prompt = (f"An atmospheric, emotional vertical background representing: "
                 f"{lines[0]}. Visual style: {visual_style}. No text.")

    with tempfile.TemporaryDirectory(dir=config.DATA_DIR) as td:
        work = Path(td)
        bg = portrait_image(bg_prompt, work, "bg")
        img = Image.open(bg).convert("RGB")
        img = Image.blend(img, Image.new("RGB", img.size, (6, 6, 10)), 0.5)
        img.save(bg)

        # one centered overlay PNG per line — shown ONE at a time
        font = composer._special_font(composer._SERIF_FONTS, 82)
        probe = ImageDraw.Draw(Image.new("RGB", (VW, VH)))
        overlays = []
        for i, line in enumerate(lines):
            wrapped = composer._wrap(probe, line, font, VW - 200)
            bb = probe.multiline_textbbox((0, 0), wrapped, font=font, spacing=12)
            layer = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            color = (*accent, 255) if i == len(lines) - 1 else (245, 245, 250, 255)
            d.multiline_text(((VW - (bb[2] - bb[0])) / 2, (VH - (bb[3] - bb[1])) / 2),
                             wrapped, font=font, fill=color, spacing=12, align="center")
            p = work / f"line{i}.png"
            layer.save(p)
            overlays.append(p)

        chrome = Image.new("RGBA", (VW, VH), (0, 0, 0, 0))
        d = ImageDraw.Draw(chrome)
        hf = composer._font(34, bold=True)
        if handle:
            d.text(((VW - d.textlength(handle, font=hf)) / 2, VH - 140), handle,
                   font=hf, fill=(235, 235, 240, 220))
        chrome_p = work / "chrome.png"
        chrome.save(chrome_p)

        track = music.pick_track(spec.get("music_mood", "calm"))
        frames = int(total * FPS)

        inputs = ["-loop", "1", "-t", f"{total:.2f}", "-i", str(bg)]
        for p in [*overlays, chrome_p]:
            inputs += ["-loop", "1", "-t", f"{total:.2f}", "-i", str(p)]
        inputs += ["-stream_loop", "-1", "-i", str(track)]

        fc = [f"[0:v]scale={ZW}:{ZH},zoompan=z='1+0.08*on/{frames}':d={frames}:"
              f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':s={VW}x{VH}:fps={FPS}[base]"]
        cur = "base"
        for i in range(len(overlays)):
            st = i * per + 0.2
            # fade in, then fade out before the next line (last line stays)
            fade = (f"format=rgba,fade=t=in:st={st:.2f}:d=0.6:alpha=1"
                    if i == len(overlays) - 1 else
                    f"format=rgba,fade=t=in:st={st:.2f}:d=0.5:alpha=1,"
                    f"fade=t=out:st={st + per - 0.5:.2f}:d=0.5:alpha=1")
            fc.append(f"[{i + 1}:v]{fade}[o{i}]")
            fc.append(f"[{cur}][o{i}]overlay[v{i}]")
            cur = f"v{i}"
        fc.append(f"[{len(overlays) + 1}:v]format=rgba[ch]")
        fc.append(f"[{cur}][ch]overlay,format=yuv420p[vout]")
        a_idx = len(overlays) + 2
        fc.append(f"[{a_idx}:a]atrim=0:{total:.2f},volume=0.7,"
                  f"afade=t=out:st={total - 1.6:.2f}:d=1.6[aout]")

        out_name = _out_name("reelstory")
        VIDEOS_DIR.mkdir(exist_ok=True)
        _ff([*inputs, "-filter_complex", ";".join(fc),
             "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
             *ENCODE, str(VIDEOS_DIR / out_name)])
    return out_name


def render_countdown_reel(spec: dict, brand: dict, visual_style: str) -> str:
    """Top-N countdown: cover → items from #N down to #1 → CTA, punchy slide-up cuts."""
    accent = composer._hex(brand.get("accent", ""))
    handle = brand.get("handle", "")
    L, fade = 2.6, 0.4
    items = spec["items"]
    n_items = len(items)

    with tempfile.TemporaryDirectory(dir=config.DATA_DIR) as td:
        work = Path(td)
        slides = [_slide_png(work, "cover", visual_style, spec["title"],
                             f"Top {n_items} countdown", accent, handle)]
        # highest rank first, counting DOWN to #1 for suspense
        for pos, item in enumerate(reversed(items)):
            rank = n_items - pos
            slides.append(_slide_png(
                work, f"c{pos}", f"{item['image']}. {visual_style}",
                item["label"], "", accent, handle, big_index=f"#{rank}"))
        if spec.get("cta"):
            slides.append(_slide_png(work, "outro", visual_style,
                                     spec["cta"].upper(), "", accent, handle))

        n = len(slides)
        total = n * L - (n - 1) * fade
        track = music.pick_track(spec.get("music_mood", "upbeat"))

        inputs = []
        for p in slides:
            inputs += ["-loop", "1", "-t", f"{L:.2f}", "-i", str(p)]
        inputs += ["-stream_loop", "-1", "-i", str(track)]

        fc = [f"[{i}:v]scale={VW}:{VH},setsar=1,fps={FPS}[v{i}]" for i in range(n)]
        cur = "v0"
        for i in range(1, n):
            offset = i * (L - fade)
            nxt = f"x{i}"
            fc.append(f"[{cur}][v{i}]xfade=transition=slideup:duration={fade}:"
                      f"offset={offset:.2f}[{nxt}]")
            cur = nxt
        fc.append(f"[{cur}]format=yuv420p[vout]")
        fc.append(f"[{n}:a]atrim=0:{total:.2f},volume=0.8,"
                  f"afade=t=out:st={total - 1.5:.2f}:d=1.5[aout]")

        out_name = _out_name("reelcountdown")
        VIDEOS_DIR.mkdir(exist_ok=True)
        _ff([*inputs, "-filter_complex", ";".join(fc),
             "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
             *ENCODE, str(VIDEOS_DIR / out_name)])
    return out_name


def _fit_image(prompt: str, work: Path, name: str, size: tuple[int, int]) -> Path:
    """AI image fitted to an arbitrary size (brand gradient fallback)."""
    path = work / f"{name}.png"
    fn = images.generate_raw(prompt) if prompt else None
    if fn:
        try:
            src = Image.open(config.IMAGES_DIR / fn).convert("RGB")
            ImageOps.fit(src, size, Image.LANCZOS).save(path)
            return path
        except Exception:  # noqa: BLE001
            pass
    composer._gradient_tile(size).save(path)
    return path


def _split_slide(work: Path, name: str, top_prompt: str, top_label: str,
                 bot_prompt: str, bot_label: str, accent, handle: str,
                 top_tag: str = "", bot_tag: str = "") -> Path:
    """A 1080x1920 top/bottom split card with a centered VS chip."""
    half = (VW, VH // 2)
    canvas = Image.new("RGB", (VW, VH), (10, 10, 14))
    for prompt, y0 in ((top_prompt, 0), (bot_prompt, VH // 2)):
        piece = Image.open(_fit_image(prompt, work, f"{name}-{y0}", half)).convert("RGB")
        piece = composer._scrim(piece, start=0.15, strength=205).convert("RGB")
        canvas.paste(piece, (0, y0))
    d = ImageDraw.Draw(canvas)
    tf = composer._font(76, bold=True)
    for label, tag, cy in ((top_label, top_tag, VH // 2 - 210), (bot_label, bot_tag, VH - 260)):
        if tag:
            gf = composer._font(34, bold=True)
            gw = d.textlength(tag, font=gf)
            d.rounded_rectangle([90, cy - 70, 90 + gw + 40, cy - 8], radius=12,
                                fill=accent if len(accent) != 3 else (*accent, 255))
            d.text((110, cy - 62), tag, font=gf, fill=(255, 255, 255))
        wrapped = composer._wrap(d, label, tf, VW - 180)
        d.multiline_text((90, cy), wrapped, font=tf, fill=(248, 248, 252), spacing=8)
    # center VS divider chip
    r = 66
    cx, cy = VW // 2, VH // 2
    d.line([(0, cy), (VW, cy)], fill=(255, 255, 255), width=4)
    d.ellipse([cx - r, cy - r, cx + r, cy + r],
              fill=accent if len(accent) != 3 else (*accent, 255))
    vf = composer._font(52, bold=True)
    d.text((cx - d.textlength("VS", font=vf) / 2, cy - 30), "VS", font=vf, fill=(255, 255, 255))
    if handle:
        hf = composer._font(30, bold=True)
        d.text((90, VH - 90), handle, font=hf, fill=(220, 220, 230))
    path = work / f"{name}.png"
    canvas.save(path)
    return path


def render_vs_reel(spec: dict, brand: dict, visual_style: str) -> str:
    """This-or-That: cover → split comparison rows → CTA, crossfades + music bed."""
    accent = composer._hex(brand.get("accent", ""))
    handle = brand.get("handle", "")
    lt, rt = spec.get("left_title", "This"), spec.get("right_title", "That")
    rows = min(len(spec["left"]), len(spec["right"]))
    L, fade = 3.0, 0.5

    with tempfile.TemporaryDirectory(dir=config.DATA_DIR) as td:
        work = Path(td)
        slides = [_slide_png(work, "cover", visual_style, spec["title"],
                             f"{lt}  vs  {rt}", accent, handle)]
        for i in range(rows):
            a, b = spec["left"][i], spec["right"][i]
            slides.append(_split_slide(
                work, f"r{i}",
                f"{a['image']}. {visual_style}", a["label"],
                f"{b['image']}. {visual_style}", b["label"],
                accent, handle, top_tag=lt.upper()[:14], bot_tag=rt.upper()[:14]))
        if spec.get("cta"):
            slides.append(_slide_png(work, "outro", visual_style,
                                     spec["cta"].upper(), "", accent, handle))

        n = len(slides)
        total = n * L - (n - 1) * fade
        track = music.pick_track(spec.get("music_mood", "dark"))

        inputs = []
        for p in slides:
            inputs += ["-loop", "1", "-t", f"{L:.2f}", "-i", str(p)]
        inputs += ["-stream_loop", "-1", "-i", str(track)]

        fc = [f"[{i}:v]scale={VW}:{VH},setsar=1,fps={FPS}[v{i}]" for i in range(n)]
        cur = "v0"
        for i in range(1, n):
            offset = i * (L - fade)
            nxt = f"x{i}"
            fc.append(f"[{cur}][v{i}]xfade=transition=fade:duration={fade}:"
                      f"offset={offset:.2f}[{nxt}]")
            cur = nxt
        fc.append(f"[{cur}]format=yuv420p[vout]")
        fc.append(f"[{n}:a]atrim=0:{total:.2f},volume=0.75,"
                  f"afade=t=out:st={total - 1.5:.2f}:d=1.5[aout]")

        out_name = _out_name("reelvs")
        VIDEOS_DIR.mkdir(exist_ok=True)
        _ff([*inputs, "-filter_complex", ";".join(fc),
             "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
             *ENCODE, str(VIDEOS_DIR / out_name)])
    return out_name


def _slide_png(work: Path, name: str, bg_prompt: str, title: str, subtitle: str,
               accent, handle: str, big_index: str = "") -> Path:
    """One 1080x1920 slide card: AI/gradient bg + scrim + text (all composed by us)."""
    path = portrait_image(bg_prompt, work, name)
    img = composer._scrim(Image.open(path).convert("RGB"), start=0.30, strength=235).convert("RGB")
    d = ImageDraw.Draw(img)
    if big_index:
        nf = composer._special_font(composer._DISPLAY_FONTS, 190)
        d.text((90, VH - 900), big_index, font=nf, fill=(*accent, 255) if len(accent) == 3 else accent)
    tf = composer._font(84, bold=True)
    wrapped = composer._wrap(d, title, tf, VW - 180)
    bb = d.multiline_textbbox((0, 0), wrapped, font=tf, spacing=10)
    ty = VH - 620
    d.multiline_text((90, ty), wrapped, font=tf, fill=(248, 248, 252), spacing=10)
    if subtitle:
        sf = composer._font(44)
        sw = composer._wrap(d, subtitle, sf, VW - 180)
        d.multiline_text((90, ty + (bb[3] - bb[1]) + 40), sw, font=sf,
                         fill=(200, 200, 214), spacing=8)
    if handle:
        hf = composer._font(32, bold=True)
        d.text((90, VH - 120), handle, font=hf, fill=(220, 220, 230))
    img.save(path)
    return path


def render_slides_reel(spec: dict, brand: dict, visual_style: str) -> str:
    """Cover → item slides → CTA outro, xfade transitions, music bed."""
    accent = composer._hex(brand.get("accent", ""))
    handle = brand.get("handle", "")
    L, fade = 2.8, 0.45

    with tempfile.TemporaryDirectory(dir=config.DATA_DIR) as td:
        work = Path(td)
        slides = [_slide_png(work, "cover",
                             f"{spec['items'][0]['image']}. {visual_style}",
                             spec["title"], "", accent, handle)]
        for i, item in enumerate(spec["items"]):
            slides.append(_slide_png(
                work, f"s{i}", f"{item['image']}. {visual_style}",
                item["label"], "", accent, handle, big_index=f"{i + 1:02d}"))
        if spec.get("cta"):
            slides.append(_slide_png(work, "outro", visual_style,
                                     spec["cta"].upper(), "", accent, handle))

        n = len(slides)
        total = n * L - (n - 1) * fade
        track = music.pick_track(spec.get("music_mood", "upbeat"))

        inputs = []
        for p in slides:
            inputs += ["-loop", "1", "-t", f"{L:.2f}", "-i", str(p)]
        inputs += ["-stream_loop", "-1", "-i", str(track)]

        fc = [f"[{i}:v]scale={VW}:{VH},setsar=1,fps={FPS}[v{i}]" for i in range(n)]
        cur = "v0"
        for i in range(1, n):
            offset = i * (L - fade)
            nxt = f"x{i}"
            fc.append(f"[{cur}][v{i}]xfade=transition=slideleft:duration={fade}:"
                      f"offset={offset:.2f}[{nxt}]")
            cur = nxt
        fc.append(f"[{cur}]format=yuv420p[vout]")
        fc.append(f"[{n}:a]atrim=0:{total:.2f},volume=0.75,"
                  f"afade=t=out:st={total - 1.5:.2f}:d=1.5[aout]")

        out_name = _out_name("reelslides")
        VIDEOS_DIR.mkdir(exist_ok=True)
        _ff([*inputs, "-filter_complex", ";".join(fc),
             "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
             *ENCODE, str(VIDEOS_DIR / out_name)])
    return out_name


def render_facts_reel(spec: dict, brand: dict, visual_style: str) -> str:
    """Narrated reel: VO with word-timed captions over b-roll/AI scenes, music bed."""
    from . import voice

    segments = [spec["hook"], *[s["text"] for s in spec["scenes"]]]
    visuals = [spec["scenes"][0]["visual"], *[s["visual"] for s in spec["scenes"]]]
    if spec.get("outro"):
        segments.append(spec["outro"])
        visuals.append(spec["scenes"][-1]["visual"])

    with tempfile.TemporaryDirectory(dir=config.DATA_DIR) as td:
        work = Path(td)
        vo_path = work / "vo.mp3"
        words = voice.synthesize(" ".join(segments), vo_path, voice=spec.get("voice", "en"))
        if not words:
            raise RuntimeError("TTS returned no word timings")
        total = words[-1]["end"] + 0.9

        # Split the timeline into segments by walking word counts (proportional fallback).
        seg_word_counts = [len(s.split()) for s in segments]
        boundaries, idx = [], 0
        for count in seg_word_counts[:-1]:
            idx += count
            boundaries.append(words[idx]["start"] if idx < len(words)
                              else total * sum(seg_word_counts[:len(boundaries) + 1]) / sum(seg_word_counts))
        starts = [0.0, *boundaries]
        ends = [*boundaries, total]

        clips = []
        for i, (visual, s, e) in enumerate(zip(visuals, starts, ends)):
            dur = max(1.2, e - s)
            clip = pexels_clip(visual, dur, work, f"seg{i}")
            if clip is None:
                img = portrait_image(f"{visual}. {visual_style}", work, f"img{i}")
                clip = kenburns_clip(img, dur, work, f"seg{i}", zoom=0.12)
            clips.append(clip)

        cap_pngs = caps.render_caption_pngs(words, work, brand.get("accent", "#a855f7"))
        track = music.pick_track(spec.get("music_mood", "calm"))

        inputs = []
        for c in clips:
            inputs += ["-i", str(c)]
        for png, _, _ in cap_pngs:
            inputs += ["-loop", "1", "-t", f"{total:.2f}", "-i", str(png)]
        inputs += ["-i", str(vo_path), "-stream_loop", "-1", "-i", str(track)]

        n = len(clips)
        fc = [f"[{i}:v]scale={VW}:{VH},setsar=1,fps={FPS}[v{i}]" for i in range(n)]
        fc.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[cat]")
        cur = "cat"
        for j, (_, cs, ce) in enumerate(cap_pngs):
            idx = n + j
            nxt = f"c{j}"
            fc.append(f"[{cur}][{idx}:v]overlay=enable=between(t\\,{cs:.2f}\\,{ce:.2f})[{nxt}]")
            cur = nxt
        fc.append(f"[{cur}]format=yuv420p[vout]")
        vo_idx, bed_idx = n + len(cap_pngs), n + len(cap_pngs) + 1
        fc.append(f"[{vo_idx}:a]volume=1.0[vo];"
                  f"[{bed_idx}:a]atrim=0:{total:.2f},volume=0.16[bed];"
                  f"[vo][bed]amix=inputs=2:duration=first:dropout_transition=2,"
                  f"afade=t=out:st={max(0.0, total - 1.2):.2f}:d=1.2[aout]")

        out_name = _out_name("reelfacts")
        VIDEOS_DIR.mkdir(exist_ok=True)
        _ff([*inputs, "-filter_complex", ";".join(fc),
             "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.2f}",
             *ENCODE, str(VIDEOS_DIR / out_name)])
    return out_name
