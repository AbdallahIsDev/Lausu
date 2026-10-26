"""OpenAI realtime transcription over WebSocket, burst-append at stop."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
from collections.abc import Callable, Iterable
from typing import Any

from voice_typer.server._secrets import redact_secret, redact_url
from voice_typer.server.asr_errors import (
    CloudAuthError,
    CloudEmptyResponseError,
    CloudEngineError,
    CloudNetworkError,
)
from voice_typer.server.cloud._realtime import (
    OFFICIAL_REALTIME_HOST,
    WS_MAX_MESSAGE_BYTES,
    WS_OVERALL_TIMEOUT_S,
    WS_REALTIME_URL,
    DeltaAssembler,
    build_append_envelope,
    build_commit_envelope,
    build_session_update,
)

log = logging.getLogger(__name__)

_HTTPS_REALTIME_URL = f"https://{OFFICIAL_REALTIME_HOST}/v1/realtime?intent=transcription"
_ABORT_POLL_S = 0.25
# Handshake bound: without it a stalled TCP connect hangs the join below
# forever, regressing the ~10s abort-latency contract of the HTTP path.
_OPEN_TIMEOUT_S = 15.0
# Join bound slack past the in-session deadline: the worker thread must
# never outlive the caller's patience, even if the WS stack wedges.
_JOIN_SLACK_S = 10.0
# Supplementary only: no published close-code table was found (checked
# 2026-10-14), so 401/403 status + key-worded messages below are the
# primary auth detection and these observed codes are the backstop.
_AUTH_CLOSE_CODES = frozenset({4001, 4010, 4401})


def _facade():
    # Call-time import: the facade owns assert_url_allowed for tests.
    from voice_typer.server import cloud_engines

    return cloud_engines


def _is_auth_failure(exc: BaseException) -> bool:
    if getattr(exc, "status_code", None) in (401, 403):
        return True
    if getattr(getattr(exc, "response", None), "status_code", None) in (401, 403):
        return True
    if getattr(exc, "code", None) in _AUTH_CLOSE_CODES:
        return True
    text = str(exc).lower()
    return (
        "401" in text
        or "unauthorized" in text
        or "invalid api key" in text
        or "incorrect api key" in text
    )


def _map_ws_error(exc: BaseException) -> CloudEngineError:
    if isinstance(exc, CloudEngineError):
        return exc
    if _is_auth_failure(exc):
        return CloudAuthError("realtime authentication failed")
    name = type(exc).__name__
    if name == "PayloadTooBig":
        return CloudEngineError("realtime message exceeded size cap")
    # Timeout first: builtin TimeoutError subclasses OSError, so the
    # connection branch below would swallow it with the wrong message.
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
        return CloudNetworkError("realtime transcription timed out")
    if name.startswith("ConnectionClosed") or isinstance(exc, (ConnectionError, OSError)):
        return CloudNetworkError(
            f"realtime connection lost: {redact_secret(redact_url(str(exc)))}"
        )
    return CloudEngineError(
        f"realtime transcription failed: {redact_secret(redact_url(str(exc)))}"
    )


def _parse_event(raw: str | bytes | dict) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, bytes):
        try:
            # Decode INSIDE the try: a malformed binary frame skips like
            # any other unparsable frame instead of killing the session.
            raw = raw.decode("utf-8")
        except (ValueError, TypeError):
            return None
    if not isinstance(raw, str):
        return None
    try:
        event = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return event if isinstance(event, dict) else None


async def _await_final(
    ws: Any,
    abort_event: threading.Event | None,
    overall_timeout_s: float,
    model: str,
) -> str:
    assembler = DeltaAssembler()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + overall_timeout_s
    while True:
        if abort_event is not None and abort_event.is_set():
            with contextlib.suppress(Exception):
                await ws.close()
            raise CloudEngineError("realtime transcription aborted by user")
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise CloudNetworkError("realtime transcription timed out")
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=min(remaining, _ABORT_POLL_S))
        except TimeoutError:
            continue
        except Exception as exc:
            raise _map_ws_error(exc) from exc
        # Wire-first cap in BYTES (str len undercounts multibyte text);
        # dict frames only exist in tests and bypass the wire cap.
        if isinstance(raw, str):
            size = len(raw.encode("utf-8"))
        elif isinstance(raw, bytes):
            size = len(raw)
        else:
            size = 0
        if size > WS_MAX_MESSAGE_BYTES:
            raise CloudEngineError("realtime message exceeded size cap")
        event = _parse_event(raw)
        if event is None:
            continue
        event_type = event.get("type", "")
        if not isinstance(event_type, str) or event_type.startswith("session."):
            continue
        assembler.feed(event)
        if event_type.endswith("transcription.completed"):
            text = assembler.result().strip()
            if not text:
                raise CloudEmptyResponseError("realtime transcription returned no text")
            log.info("[CLOUD] %s realtime transcription: %d chars", model, len(text))
            return text


async def _session(
    *,
    api_key: str,
    model: str,
    frames: list[bytes],
    abort_event: threading.Event | None,
    connect: Callable[..., Any] | None,
    overall_timeout_s: float,
) -> str:
    connect_fn = connect
    if connect_fn is None:
        # Lazy: the batch-only path never pays the WS import cost.
        from websockets.asyncio.client import connect as connect_fn  # noqa: F811
    headers = {"Authorization": f"Bearer {api_key}", "OpenAI-Beta": "realtime=v1"}
    loop = asyncio.get_running_loop()
    send_deadline = loop.time() + overall_timeout_s
    try:
        async with connect_fn(
            WS_REALTIME_URL,
            additional_headers=headers,
            max_size=WS_MAX_MESSAGE_BYTES,
            open_timeout=_OPEN_TIMEOUT_S,
        ) as ws:

            async def _send_bounded(payload: str) -> None:
                # Sends share the overall deadline: a wedged send must fail
                # the session, never hang the worker past the join bound.
                remaining = send_deadline - loop.time()
                if remaining <= 0:
                    raise CloudNetworkError("realtime transcription timed out")
                await asyncio.wait_for(ws.send(payload), timeout=remaining)

            await _send_bounded(json.dumps(build_session_update(model)))
            for frame in frames:
                await _send_bounded(json.dumps(build_append_envelope(frame)))
            await _send_bounded(json.dumps(build_commit_envelope()))
            return await _await_final(ws, abort_event, overall_timeout_s, model)
    except CloudEngineError:
        raise
    except Exception as exc:
        raise _map_ws_error(exc) from exc


def transcribe_via_realtime(
    *,
    api_key: str,
    model: str,
    pcm24k_frames: Iterable[bytes],
    language_ignored: str | None = None,
    abort_event: threading.Event | None = None,
    connect: Callable[..., Any] | None = None,
    overall_timeout_s: float = WS_OVERALL_TIMEOUT_S,
) -> str:
    frames = [frame for frame in pcm24k_frames if frame]
    if not frames:
        raise CloudEmptyResponseError("realtime transcription got no audio frames")
    _facade().assert_url_allowed(
        _HTTPS_REALTIME_URL,
        field_name="cloud_api_url",
        client_name="cloud/openai",
    )
    coro = _session(
        api_key=api_key,
        model=model,
        frames=frames,
        abort_event=abort_event,
        connect=connect,
        overall_timeout_s=overall_timeout_s,
    )
    box: dict[str, Any] = {}

    def _target() -> None:
        try:
            box["result"] = asyncio.run(coro)
        except BaseException as exc:  # CancelledError is BaseException
            box["error"] = exc

    # Daemon so a hung WS cannot block interpreter exit; join bounds it anyway.
    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    # Full worst case: handshake (open timeout) + sends + in-session
    # deadline, hence all three terms. Without the handshake term a
    # session completing just inside its own deadline could be abandoned.
    worker.join(timeout=overall_timeout_s + _OPEN_TIMEOUT_S + _JOIN_SLACK_S)
    if worker.is_alive():
        # Bounded leak by design: the wedged thread/socket dies with the
        # process (daemon). Signalling abort here is worse — the fallback
        # reads abort as user-cancel and would silently skip local
        # fallback. Reachable only after handshake+sends+recv all wedged.
        log.warning("[CLOUD] realtime worker outlived its join bound, abandoning it")
        raise CloudNetworkError("realtime transcription timed out")
    if "error" in box:
        raise _map_ws_error(box["error"])
    if "result" not in box:
        raise CloudNetworkError("realtime worker exited without a result")
    return box["result"]
