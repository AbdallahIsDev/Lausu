"""Media error copy parity: backend code -> renderer copy -> contract doc.

The three surfaces drift independently, and a missing mapping is invisible at
runtime: `mediaErrorKey` returns null and the toast falls back to the generic
line, so a precise failure ("this link contains 3 videos") reads as "something
went wrong". Every code the media job can emit must therefore (1) exist in the
backend taxonomy, (2) have a renderer copy key, and (3) be named in the
error-envelope contract that documents the envelope vocabulary.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from voice_typer.server.media_ingest import errors as media_errors

ROOT = Path(__file__).resolve().parents[1]
COPY_TS = ROOT / "voice_typer" / "client" / "src" / "renderer" / "src" / "pages" / "media" / "lib" / "mediaErrorCopy.ts"
ENVELOPE_DOC = ROOT / "docs" / "architecture" / "error-envelope-contract.md"

#: The codes this change introduced. Each has to reach all three surfaces.
NEW_CODES = (
    "media_too_short",
    "media_truncated",
    "multi_item_url",
    "no_media_url",
    "model_loading",
    "model_changed",
)


def _copy_source() -> str:
    return COPY_TS.read_text(encoding="utf-8")


def _copy_keys() -> dict[str, str]:
    """Parse the code -> translation-key map out of the TS module."""
    source = _copy_source()
    block = re.search(r"MEDIA_ERROR_KEYS[^{]*\{(?P<body>.*?)\n\};", source, re.S)
    assert block is not None, "MEDIA_ERROR_KEYS map not found in mediaErrorCopy.ts"
    return dict(re.findall(r'"?([\w.]+)"?:\s*"([^"]+)"', block.group("body")))


@pytest.mark.parametrize("code", NEW_CODES)
def test_code_is_in_the_backend_taxonomy(code: str) -> None:
    # The bare ingest codes are their own vocabulary; the two model-layer
    # codes are namespaced (`server.*`) because they also travel on envelopes.
    assert {code, f"server.{code}"} & media_errors.MEDIA_JOB_CODES


@pytest.mark.parametrize("code", NEW_CODES)
def test_code_has_renderer_copy(code: str) -> None:
    mapping = _copy_keys()
    assert code in mapping, f"{code} has no entry in MEDIA_ERROR_KEYS"
    assert mapping[code].startswith("media."), f"{code} maps outside the media copy namespace"


@pytest.mark.parametrize("code", NEW_CODES)
def test_code_is_named_in_the_error_contract_doc(code: str) -> None:
    doc = ENVELOPE_DOC.read_text(encoding="utf-8")
    assert f"`{code}`" in doc, f"{code} is not documented in error-envelope-contract.md"


def test_namespaced_model_codes_are_registered() -> None:
    """The two model-layer codes travel on envelopes, so they are namespaced."""
    from voice_typer.server.ipc.error_codes import ERROR_CODES, ErrorCodes

    assert ErrorCodes.MODEL_LOADING in ERROR_CODES
    assert ErrorCodes.MODEL_CHANGED in ERROR_CODES
    assert media_errors.MODEL_LOADING == ErrorCodes.MODEL_LOADING
    assert media_errors.MODEL_CHANGED == ErrorCodes.MODEL_CHANGED
    # ... and the renderer map covers both spellings, because a job event
    # carries the bare code while an envelope carries the namespaced one.
    mapping = _copy_keys()
    assert mapping["model_loading"] == mapping["server.model_loading"]
    assert mapping["model_changed"] == mapping["server.model_changed"]


def test_every_media_job_code_is_known_to_the_renderer() -> None:
    """A code the backend can emit must never fall through to generic copy."""
    mapping = _copy_keys()
    missing = sorted(code for code in media_errors.MEDIA_JOB_CODES if code not in mapping)
    # `job_busy` / `no_engine_loaded` are start-refusal ENVELOPE codes handled
    # by the start path's own copy; everything else travels on the job event.
    allowed_unmapped = {"cancelled", "no_active_job"}
    assert not [code for code in missing if code not in allowed_unmapped], (
        f"media job codes without renderer copy: {missing}"
    )
