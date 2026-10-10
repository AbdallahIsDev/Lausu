"""Wire framing + routing helpers for the worker WS hop (ADR-0024/0025).

One concern only: the stateless envelope codec between the slim sidecar and
the runtime-pack worker, outbound frame builders, the inbound parser, frame
routing, reconnect backoff, and the ``worker_started`` port extraction. The
stateful session client that drives them lives in
:mod:`voice_typer.server.worker_client`; the socket/loop machinery lives in
:mod:`voice_typer.server.worker_session`.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from voice_typer.server.ipc.protocol_version import MAX_WS_FRAME_BYTES

log = logging.getLogger(__name__)


# 1 MiB frame cap (ADR-0020 §10), shared with the worker's WS server via
# a dependency-free module. Imported rather than redefined: the slim-core
# build must not depend on the ``voice_typer.worker`` package (Step 7
# slims it out), so the constant lives under ``voice_typer.server.ipc``.
_MAX_FRAME_BYTES = MAX_WS_FRAME_BYTES

_BACKOFF_FIRST_SECONDS = 0.5
_BACKOFF_CAP_SECONDS = 30.0


def build_auth_frame(token: str) -> str:
    """First-frame auth envelope the worker's ``_authenticate`` expects."""
    # C-WS-2: str, never bytes, so the frame leaves as a TEXT opcode.
    return json.dumps({"type": "auth", "token": token})


def build_transcribe_frame(audio_path: str, sample_rate: int | None, language: str | None, request_id: int) -> str:
    """Forward envelope for one offline transcription (event_bus §7.4 shape)."""
    # C-WS-2: numeric top-level id for response correlation; the worker
    # echoes it (ADR-0025 C1) and results without one fall back to type
    # routing so older workers keep working.
    return json.dumps(
        {
            "cmd": "transcribe_offline",
            "id": int(request_id),
            "data": {"audio_path": audio_path, "sample_rate": sample_rate, "language": language},
        }
    )


def build_heartbeat_frame() -> str:
    """Liveness ping; the worker answers ``heartbeat_ack`` (plan §7.2)."""
    return json.dumps({"type": "heartbeat"})


# ADR-0025 C3: raw PCM bytes per chunk. 720 KiB raw encodes to ~960 KiB
# of base64, which plus the small JSON envelope stays under the 1 MiB
# frame cap on both hops. (The ADR text says "1 MiB raw", but 1 MiB raw
# would encode to ~1.4 MiB and breach the cap — the cap wins, the
# intent (bounded frames) is preserved.)
_SAMPLES_CHUNK_RAW_BYTES = 720 * 1024


def chunk_samples(audio_f32: bytes, sample_rate: int, language: str | None, request_id: int) -> list[str]:
    """Split raw float32 PCM into ``transcribe_samples`` chunk frames.

    Pure function (no IO): every frame carries ``(id, index, total)``
    so the worker reassembles without ordering assumptions. Empty audio
    yields exactly one (empty-payload) chunk — silence is data, not an
    error. Every returned frame is ``str`` (C-WS-2, TEXT opcode).
    """
    total = max(1, (len(audio_f32) + _SAMPLES_CHUNK_RAW_BYTES - 1) // _SAMPLES_CHUNK_RAW_BYTES)
    frames = []
    for index in range(total):
        raw = audio_f32[index * _SAMPLES_CHUNK_RAW_BYTES : (index + 1) * _SAMPLES_CHUNK_RAW_BYTES]
        frames.append(
            json.dumps(
                {
                    "cmd": "transcribe_samples",
                    "id": int(request_id),
                    "data": {
                        "index": index,
                        "total": total,
                        "sample_rate": int(sample_rate),
                        "language": language,
                        "payload_b64": base64.b64encode(raw).decode("ascii"),
                    },
                }
            )
        )
    return frames


def build_abort_frame(request_id: int) -> str:
    """Best-effort cooperative abort for one in-flight request (C4)."""
    return json.dumps({"cmd": "abort_request", "id": int(request_id), "data": {}})


def build_streaming_frame(cmd: str, request_id: int, data: dict) -> str:
    """One streaming-session command frame (C6: open/push/finalize)."""
    return json.dumps({"cmd": str(cmd), "id": int(request_id), "data": dict(data)})


def parse_incoming(raw: object) -> dict | None:
    """Decode one inbound frame; ``None`` means ignorable (never raises)."""
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        frame = json.loads(raw)  # type: ignore[arg-type]
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        return None
    return frame if isinstance(frame, dict) else None


def route_frame(frame: dict, publish: Any, on_result: Any = None) -> str:
    """Route one decoded frame; returns the action taken for liveness.

    ADR-0025 C1: when ``on_result`` is supplied and the worker echoed a
    numeric request ``id``, the callback receives ``(request_id, result)``
    so a future request/reply bridge can correlate. The event-bus publish
    is UNCHANGED in every case, so existing consumers (and the frozen
    ``transcribe_offline_result`` shape) are unaffected either way.
    """
    ftype = frame.get("type") or frame.get("cmd")
    if ftype == "transcribe_offline_result":
        data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
        result = {"text": str(data.get("text") or ""), "latency_ms": int(data.get("latency_ms") or 0)}
        # ADR-0025 C4: optional worker device description. Copied only
        # when present as a string, so the frozen shape is unchanged for
        # results that do not carry it (older workers keep working).
        device_info = data.get("device_info")
        if isinstance(device_info, str) and device_info:
            result["device_info"] = device_info
        if on_result is not None:
            request_id = frame.get("id")
            if isinstance(request_id, int) and not isinstance(request_id, bool):
                try:
                    on_result(request_id, result)
                except Exception:  # noqa: BLE001, a bad resolver must not drop the result
                    log.debug("[WORKER] result resolver failed for id=%s", request_id, exc_info=True)
        publish({"type": "transcribe_offline_result", "data": result})
        return "result"
    if ftype == "heartbeat_ack":
        return "heartbeat_ack"
    if ftype == "abort_ack":
        return "abort_ack"
    if ftype == "streaming_session_opened":
        # Resolve the opener's Future; nothing to publish (the renderer
        # only cares about partials and the pipeline consumes finalize).
        if on_result is not None:
            request_id = frame.get("id")
            if isinstance(request_id, int) and not isinstance(request_id, bool):
                try:
                    on_result(request_id, {"opened": True})
                except Exception:  # noqa: BLE001, same never-drop contract
                    log.debug("[WORKER] streaming open resolver failed for id=%s", request_id, exc_info=True)
        return "streaming_opened"
    if ftype == "streaming_session_result":
        # Final text for one streaming session: resolve the finalize
        # Future. NOT published — live partials already went out and the
        # pipeline consumes the final text synchronously.
        if on_result is not None:
            request_id = frame.get("id")
            if isinstance(request_id, int) and not isinstance(request_id, bool):
                try:
                    data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
                    on_result(
                        request_id,
                        {"text": str(data.get("text") or ""), "error": data.get("error")},
                    )
                except Exception:  # noqa: BLE001, same never-drop contract
                    log.debug("[WORKER] streaming result resolver failed for id=%s", request_id, exc_info=True)
        return "streaming_result"
    if ftype == "transcription_partial":
        # Live preview: straight to the event bus in the worker's shape
        # (text + cycle_id, plus additive is_final/words the renderer
        # tolerates). Published by the slim side, not the worker.
        data = frame.get("data") if isinstance(frame.get("data"), dict) else {}
        publish({"type": "transcription_partial", "data": dict(data)})
        return "partial"
    if ftype == "error":
        log.warning("[WORKER] worker error frame: %s", frame.get("data"))
        return "error"
    log.debug("[WORKER] unknown frame type %r: ignoring", ftype)
    return "ignored"


def backoff_delay(attempt: int) -> float:
    """Exponential reconnect backoff, capped (attempt counts failed tries)."""
    return min(_BACKOFF_FIRST_SECONDS * (2.0 ** max(0, attempt)), _BACKOFF_CAP_SECONDS)


def port_from_worker_started(payload: object) -> int | None:
    """Extract the worker port from a Step-2 ``worker_started`` payload."""
    # E8: None is the only no-value; invalid ports degrade to it.
    if not isinstance(payload, dict):
        return None
    port = payload.get("port")
    if isinstance(port, bool) or not isinstance(port, int):
        return None
    return port if 1 <= port <= 65535 else None
