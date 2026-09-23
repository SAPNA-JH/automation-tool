"""Procedurally synthesized ambient music beds.

Generated with numpy = written by this code = zero licensing risk (unlike downloaded tracks,
and the IG API can't use trending audio anyway). Four moods, ~24s loopable WAVs, written once
to assets/music/. Users can also drop their own .mp3/.wav files into assets/music/ — any file
whose name starts with the mood is picked up.
"""
from __future__ import annotations

import wave
from pathlib import Path
from secrets import choice

import numpy as np

from .. import config

MUSIC_DIR = config.BASE_DIR / "assets" / "music"
SR = 44100

# Mood -> (chord progression as semitone offsets from root, root hz, brightness)
_MOODS = {
    "calm":    ([(0, 4, 7, 12), (5, 9, 12, 16), (7, 11, 14, 17), (0, 4, 7, 12)], 130.81, 0.5),   # C maj
    "dark":    ([(0, 3, 7, 12), (-4, 0, 3, 8), (-2, 2, 5, 10), (0, 3, 7, 12)], 110.00, 0.25),    # A min
    "hopeful": ([(0, 4, 7, 12), (2, 5, 9, 14), (4, 7, 11, 16), (5, 9, 12, 17)], 146.83, 0.7),    # D maj lift
    "upbeat":  ([(0, 4, 7, 12), (5, 9, 12, 16), (2, 5, 9, 14), (7, 11, 14, 19)], 164.81, 0.85),  # E maj
}


def _tone(freq: float, n: int, detune: float = 0.15) -> np.ndarray:
    t = np.arange(n) / SR
    return (
        np.sin(2 * np.pi * freq * t)
        + 0.55 * np.sin(2 * np.pi * (freq + detune) * t)
        + 0.30 * np.sin(2 * np.pi * freq * 2 * t)   # soft octave shimmer
    )


def _chord(offsets, root: float, seconds: float) -> np.ndarray:
    n = int(SR * seconds)
    out = np.zeros(n)
    for off in offsets:
        out += _tone(root * (2 ** (off / 12)), n)
    # slow swell envelope so chords breathe and crossfade smoothly
    env = np.minimum(1.0, np.linspace(0, 4, n))
    env *= np.minimum(1.0, np.linspace(4, 0, n))
    return out * env


def _arp(offsets, root: float, seconds: float, rate: float) -> np.ndarray:
    """Short plucked notes cycling through the chord — adds motion for brighter moods."""
    n = int(SR * seconds)
    out = np.zeros(n)
    step = int(SR / rate)
    notes = [root * 2 ** ((off + 12) / 12) for off in offsets]
    for i, start in enumerate(range(0, n - step, step)):
        t = np.arange(step) / SR
        pluck = np.sin(2 * np.pi * notes[i % len(notes)] * t) * np.exp(-6 * t)
        out[start : start + step] += pluck
    return out


def _synth_mood(mood: str, seconds_per_chord: float = 6.0) -> np.ndarray:
    progression, root, brightness = _MOODS[mood]
    parts = []
    for offsets in progression:
        pad = _chord(offsets, root, seconds_per_chord)
        bass = _tone(root * (2 ** (offsets[0] / 12)) / 2, len(pad), detune=0.05) * 0.5
        mix = pad + bass
        if brightness >= 0.7:
            mix += _arp(offsets, root, seconds_per_chord, rate=4 if mood == "upbeat" else 2) * 0.6
        parts.append(mix)
    audio = np.concatenate(parts)
    # gentle one-pole lowpass — darker moods get more filtering
    alpha = 0.12 + 0.25 * brightness
    filtered = np.empty_like(audio)
    acc = 0.0
    for i, x in enumerate(audio):          # small arrays; fine in numpy-python
        acc += alpha * (x - acc)
        filtered[i] = acc
    filtered /= np.max(np.abs(filtered)) + 1e-9
    return (filtered * 0.85)


def _write_wav(path: Path, audio: np.ndarray) -> None:
    pcm = (audio * 32767 * 0.75).astype(np.int16)
    stereo = np.repeat(pcm[:, None], 2, axis=1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())


def ensure_music() -> None:
    """Synthesize the mood beds once (skipped if files already exist)."""
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    for mood in _MOODS:
        path = MUSIC_DIR / f"{mood}.wav"
        if not path.exists():
            _write_wav(path, _synth_mood(mood))
            print(f"[music] synthesized {path.name}")


def pick_track(mood: str) -> Path:
    """A track for the mood — prefers user-dropped files, falls back to synthesized bed."""
    ensure_music()
    mood = mood if mood in _MOODS else "calm"
    candidates = [p for p in MUSIC_DIR.glob(f"{mood}*") if p.suffix in (".wav", ".mp3", ".m4a")]
    return choice(candidates) if candidates else MUSIC_DIR / "calm.wav"
