"""Symmetric encryption for secrets at rest (Instagram access tokens).

Uses Fernet (AES-128-CBC + HMAC). The key comes from INSTAGRAM_TOKEN_KEY if set,
otherwise it is derived deterministically from JWT_SECRET so local dev just works.
In production, set a dedicated INSTAGRAM_TOKEN_KEY and rotate it independently.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from . import config


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = config.INSTAGRAM_TOKEN_KEY
    if key:
        # Accept a ready-made urlsafe Fernet key verbatim…
        try:
            return Fernet(key.encode())
        except Exception:  # noqa: BLE001 — not a raw Fernet key; derive one below
            pass
    seed = (config.INSTAGRAM_TOKEN_KEY or config.JWT_SECRET or "dev-insecure").encode()
    derived = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
    return Fernet(derived)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    """Return the plaintext, or '' if the ciphertext is missing/invalid."""
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError):
        return ""
