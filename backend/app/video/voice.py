"""Voiceover via edge-tts (free Microsoft neural voices) with word-level timings."""
from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts

# voice per language flavor; en-IN/hi-IN suit the desi niches, en-US as neutral default
VOICES = {
    "en": "en-US-ChristopherNeural",
    "en-warm": "en-US-AriaNeural",
    "en-in": "en-IN-NeerjaNeural",
    "hi": "hi-IN-SwaraNeural",
}


def synthesize(text: str, out_path: Path, voice: str = "en", rate: str = "+0%") -> list[dict]:
    """Write narration mp3 to out_path; return [{word, start, end}] second-based timings."""
    voice_id = VOICES.get(voice, voice if "-" in voice else VOICES["en"])

    async def run() -> list[dict]:
        tts = edge_tts.Communicate(text, voice_id, rate=rate, boundary="WordBoundary")
        words: list[dict] = []
        with open(out_path, "wb") as f:
            async for chunk in tts.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    start = chunk["offset"] / 1e7
                    words.append({
                        "word": chunk["text"],
                        "start": start,
                        "end": start + chunk["duration"] / 1e7,
                    })
        return words

    return asyncio.run(run())
