"""Google Gemini ``generateContent`` request shaping for cloud ASR.

Inline-audio path only (no Files API upload): the WAV is base64-encoded
into ``contents[0].parts`` next to a transcribe-exactly prompt. Auth goes
in the ``X-goog-api-key`` header, never ``?key=`` in the URL (C-DATA-1:
query keys leak into logs).
"""

from __future__ import annotations

import base64
import json
import re

TRANSCRIBE_PROMPT = "Transcribe this audio exactly, word for word. Return only the transcript text."

_SAFE_MODEL_RE = re.compile(r"^[A-Za-z0-9._\-]+$")


def build_gemini_url(api_url: str, model_name: str) -> str:
    """Resolve the generateContent endpoint for *model_name*."""
    if not _SAFE_MODEL_RE.match(model_name or ""):
        raise RuntimeError(f"Gemini model name {model_name!r} contains invalid characters")
    if "{model}" in (api_url or ""):
        return api_url.replace("{model}", model_name)
    return api_url


def build_gemini_body(wav_bytes: bytes) -> bytes:
    """Build the JSON body: base64 wav + transcribe-exactly prompt."""
    audio_b64 = base64.b64encode(wav_bytes).decode("ascii")
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": TRANSCRIBE_PROMPT},
                    {"inline_data": {"mime_type": "audio/wav", "data": audio_b64}},
                ]
            }
        ]
    }
    return json.dumps(payload).encode("utf-8")


def parse_gemini_transcript(raw: bytes) -> str:
    """Parse transcript from ``candidates[0].content.parts[0].text``."""
    result = json.loads(raw.decode("utf-8"))
    candidates = result.get("candidates", [])
    if not candidates:
        return ""
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        return ""
    return str(parts[0].get("text", "")).strip()
