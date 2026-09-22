"""Shared text-LLM call. One `chat()` used by both caption and structured-content generation.

Provider is chosen by config.caption_provider(): cloudflare | gemini | anthropic | openai.
Raises if no real provider is available (callers handle their own fallback).
"""
from __future__ import annotations

import json

import httpx

from .. import config


def _cloudflare(system: str, user: str) -> str:
    resp = httpx.post(
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{config.CLOUDFLARE_ACCOUNT_ID}/ai/run/{config.CLOUDFLARE_TEXT_MODEL}",
        headers={"Authorization": f"Bearer {config.CLOUDFLARE_API_TOKEN}"},
        json={"messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]},
        timeout=90,
    )
    resp.raise_for_status()
    result = resp.json()["result"]["response"]
    # Newer Workers AI auto-parses JSON output into a dict; older returns a raw string.
    return result if isinstance(result, str) else json.dumps(result)


def _gemini(system: str, user: str) -> str:
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.GEMINI_TEXT_MODEL}:generateContent",
        headers={"x-goog-api-key": config.GEMINI_API_KEY, "content-type": "application/json"},
        json={
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _anthropic(system: str, user: str) -> str:
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": config.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": config.ANTHROPIC_MODEL,
            "max_tokens": 1024,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def _openai(system: str, user: str) -> str:
    resp = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        json={
            "model": config.OPENAI_CAPTION_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=90,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _cloudflare_json(system: str, user: str) -> str:
    """Cloudflare with forced JSON output and the stronger structured-output model."""
    resp = httpx.post(
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{config.CLOUDFLARE_ACCOUNT_ID}/ai/run/{config.CLOUDFLARE_JSON_MODEL}",
        headers={"Authorization": f"Bearer {config.CLOUDFLARE_API_TOKEN}"},
        json={
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 2560,  # VS specs have ~10 panels; avoid truncated JSON
        },
        timeout=120,
    )
    resp.raise_for_status()
    result = resp.json()["result"]["response"]
    return result if isinstance(result, str) else json.dumps(result)


def chat(system: str, user: str) -> str:
    """Return the model's raw text response using the best available provider."""
    provider = config.caption_provider()
    if provider == "cloudflare":
        return _cloudflare(system, user)
    if provider == "gemini":
        return _gemini(system, user)
    if provider == "anthropic":
        return _anthropic(system, user)
    if provider == "openai":
        return _openai(system, user)
    raise RuntimeError("no text-LLM provider configured")


def chat_json(system: str, user: str) -> str:
    """Like chat(), but requests strict JSON (used for structured infographic specs)."""
    if config.caption_provider() == "cloudflare":
        return _cloudflare_json(system, user)
    return chat(system, user)
