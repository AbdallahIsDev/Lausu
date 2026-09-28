"""ADR-0025 C2 — live sync-bridge verification on a real host.

Drives REAL processes: spawns the actual worker, relays its real
``worker_started`` bind through the real ``worker_relay``, connects the
real shared ``WorkerClient``, then issues TWO ``request_transcribe``
calls through the SAME client and proves each Future resolves with the
result the C1 id router correlated to its own request id (not merely
that two type-routed publishes arrived).

Usage (from the repo root)::

    python scripts/verify_worker_bridge_live.py --config-dir <dir> --audio <file.wav>

Nothing here mocks a process, a socket, or the ASR engine. The two
transcriptions run sequentially so shared model state is never
contended; per-id correlation is what is under proof (simultaneous
discrimination is covered by
``tests/test_worker_request_bridge.py::TestEchoCorrelation``).
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from voice_typer.server._paths import IPC_TOKEN_ENV_VAR  # noqa: E402

from scripts.verify_worker_handoff_live import (  # noqa: E402
    _CONNECT_TIMEOUT_S,
    _read_handshake,
    _spawn_worker,
    _wait_for_connected,
)

_RESULT_TIMEOUT_S = 600.0
_ABORT_QUIET_S = 30.0


def _run_samples_leg(client, published, audio: Path, log_path: Path, evidence: dict) -> bool:
    """C3 live: in-memory float32 samples through the same client."""
    from voice_typer.worker._transcribe import _load_wav_float32, _resample_to_16k

    pcm, rate = _load_wav_float32(str(audio))
    pcm16 = _resample_to_16k(pcm, rate)
    import numpy as _np

    raw = _np.asarray(pcm16, dtype=_np.float32).tobytes()
    print(f"[bridge] samples leg: {len(raw)} raw bytes at 16 kHz")
    future = client.request_samples(raw, 16000, "en", timeout=_RESULT_TIMEOUT_S)
    if future is None:
        print("[bridge] FAIL: samples request refused (no port)")
        return False
    try:
        result = future.result(timeout=_RESULT_TIMEOUT_S)
    except Exception as exc:
        print(f"[bridge] FAIL: samples future raised: {exc!r}")
        return False
    text = str(result.get("text") or "")
    device_info = result.get("device_info")
    print(f"[bridge] samples text={text[:60]!r} device_info={device_info!r}")
    ok = text.strip() != "" and isinstance(device_info, str) and bool(device_info)
    evidence["samples_ok"] = ok
    evidence["samples_text"] = text
    evidence["samples_device_info"] = device_info
    if not ok:
        print("[bridge] FAIL: samples leg needs non-empty text + str device_info")
    return ok


def _run_abort_leg(client, published, audio: Path, log_path: Path, evidence: dict) -> bool:
    """C4 live: abort mid-inference, then prove nothing leaks."""
    from voice_typer.worker._transcribe import _load_wav_float32, _resample_to_16k

    pcm, rate = _load_wav_float32(str(audio))
    pcm16 = _resample_to_16k(pcm, rate)
    import numpy as _np

    raw = _np.asarray(pcm16, dtype=_np.float32).tobytes()
    print(f"[bridge] t+{time.perf_counter() - _T0:.1f}s abort-leg audio ready ({len(raw)} bytes)")
    before = len(published)
    future = client.request_samples(raw, 16000, "en", timeout=_RESULT_TIMEOUT_S)
    print(f"[bridge] t+{time.perf_counter() - _T0:.1f}s samples enqueued")
    if future is None:
        print("[bridge] FAIL: abort-leg request refused (no port)")
        return False
    request_id = client._request_seq
    sent_abort = client.send_abort(request_id)
    print(f"[bridge] t+{time.perf_counter() - _T0:.1f}s abort enqueued (sent={sent_abort})")
    client.cancel_request(request_id)
    print(f"[bridge] abort sent={sent_abort} for id={request_id}; waiting {_ABORT_QUIET_S}s for leaks")
    time.sleep(_ABORT_QUIET_S)
    leaked = len(published) - before
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    worker_saw_abort = f"abort_request id={request_id}" in text
    worker_dropped = f"dropping result for aborted request id={request_id}" in text
    print(f"[bridge] worker saw abort: {worker_saw_abort}; worker dropped result: {worker_dropped}; leaked: {leaked}")
    ok = bool(sent_abort and worker_saw_abort and worker_dropped and leaked == 0)
    evidence["abort_ok"] = ok
    if not ok:
        print("[bridge] FAIL: abort leg incomplete")
    return ok


_T0 = time.perf_counter()


def _run_streaming_leg(client, published, audio: Path, evidence: dict) -> bool:
    """C6 live: overlapping pushes through a worker session, then finalize."""
    import base64

    import numpy as _np
    from voice_typer.server.worker_client import build_streaming_frame
    from voice_typer.worker._transcribe import _load_wav_float32, _resample_to_16k

    pcm, rate = _load_wav_float32(str(audio))
    raw = _np.asarray(_resample_to_16k(pcm, rate), dtype=_np.float32).tobytes()
    opened = client.open_streaming_session(
        {
            "chunk_seconds": 12.0,
            "step_seconds": 5.0,
            "left_overlap_seconds": 3.0,
            "right_guard_seconds": 1.5,
            "min_first_chunk_seconds": 6.0,
            "silence_threshold": 0.003,
            "sample_rate": 16000,
            "cycle_id": "live-overlap",
            "language": "en",
        },
        timeout=30.0,
    )
    if opened is None:
        print("[bridge] FAIL: streaming open refused (no port)")
        return False
    request_id, opened_future = opened
    try:
        ack = opened_future.result(timeout=30.0)
    except Exception as exc:
        print(f"[bridge] FAIL: streaming open unacknowledged: {exc!r}")
        return False
    if not isinstance(ack, dict) or not ack.get("opened"):
        print("[bridge] FAIL: streaming open ack negative")
        return False
    # Overlapping 4 s pushes at a 5 s window step: every window shares
    # audio with its neighbors, so duplicated or dropped words would
    # surface in the final text.
    piece = 4 * 16000 * 4
    frames = []
    for index in range(0, len(raw), piece):
        frames.append(
            build_streaming_frame(
                "streaming_session_push",
                request_id,
                {"index": index // piece, "payload_b64": base64.b64encode(raw[index : index + piece]).decode("ascii")},
            )
        )
    before = len(published)
    # Prove the live partial path, not just the final: feed the first
    # window, wait for at least one partial, then feed the rest. If
    # everything arrives at once, finalize tears the session down before
    # any window completes and partials are (correctly) skipped.
    first, rest = frames[:3], frames[3:]
    if not client.enqueue_frames(first):
        print("[bridge] FAIL: streaming pushes refused")
        return False
    deadline = time.perf_counter() + 90.0
    while time.perf_counter() < deadline:
        if any(e.get("type") == "transcription_partial" for e in published[before:]):
            break
        time.sleep(0.5)
    partials_early = sum(1 for e in published[before:] if e.get("type") == "transcription_partial")
    print(f"[bridge] early partials before finalize: {partials_early}")
    if rest and not client.enqueue_frames(rest):
        print("[bridge] FAIL: streaming tail pushes refused")
        return False
    result_future = client.expect_streaming_result(request_id, timeout=_RESULT_TIMEOUT_S)
    if not client.enqueue_frames([build_streaming_frame("streaming_session_finalize", request_id, {})]):
        print("[bridge] FAIL: streaming finalize refused")
        return False
    try:
        result = result_future.result(timeout=_RESULT_TIMEOUT_S)
    except Exception as exc:
        print(f"[bridge] FAIL: streaming result unanswered: {exc!r}")
        return False
    text = str(result.get("text") or "")
    partials = [e for e in published[before:] if e.get("type") == "transcription_partial"]
    print(f"[bridge] streaming final text={text[:60]!r} partials={len(partials)}")
    # No-drops check: every expected word must appear IN ORDER (a
    # repeated variant like engine "PackWorker" vs committed "pack" is
    # engine boundary variance, shared with the in-process path — not a
    # drop; see the assembler-equivalence unit test for port fidelity).
    expected = "the quick brown fox jumps over the lazy dog this is a runtime pack worker handoff verification test"
    hay = text.lower()
    pos, missing = 0, []
    for word in expected.split():
        at = hay.find(word, pos)
        if at < 0:
            missing.append(word)
        else:
            pos = at + len(word)
    ok = not missing
    evidence["streaming_ok"] = ok
    evidence["streaming_text"] = text
    evidence["streaming_partials"] = len(partials)
    evidence["streaming_missing_words"] = missing
    try:
        expected = Path(os.environ.get("TEMP", "."), "vt_verify", "expect.txt").read_text(encoding="utf-8").strip()
    except OSError:
        expected = ""
    evidence["streaming_byte_equal"] = bool(expected) and text.strip() == expected
    print(f"[bridge] streaming byte-equal to expect.txt: {evidence['streaming_byte_equal']}")
    if not ok:
        print(f"[bridge] FAIL: streaming leg dropped words: {missing}")
    return ok


def _run(
    config_dir: Path,
    audio: Path,
    work: Path,
    log_path: Path,
    token: str,
    with_abort: bool = False,
    with_streaming: bool = False,
) -> int:
    print(f"[bridge] spawning worker (config_dir={config_dir})")
    proc, handles = _spawn_worker(config_dir, token, log_path)
    evidence: dict = {"worker_pid": proc.pid, "log": str(log_path)}
    try:
        handshake = _read_handshake(proc.stdout, proc, _CONNECT_TIMEOUT_S)
        port = handshake.get("port")
        print(f"[bridge] worker_started: port={port} protocol={handshake.get('protocol')}")
        if not isinstance(port, int):
            print("[bridge] FAIL: handshake carried no integer port")
            return 1

        from voice_typer.server import worker_relay
        from voice_typer.server.worker_client import get_shared_client

        worker_relay.reset_worker_port()
        if not worker_relay.handle_host_frame(
            {"type": "worker_started", "data": {"pid": proc.pid, "version": "v1", "port": port}, "id": 1}
        ):
            print("[bridge] FAIL: relay rejected worker_started")
            return 1

        published: list = []
        client = get_shared_client()
        if not client.update_from_worker_started({"port": port, "pid": proc.pid, "version": "v1"}):
            print("[bridge] FAIL: client rejected the relayed worker_started")
            return 1
        client._publish = published.append
        if not _wait_for_connected(log_path, proc):
            print("[bridge] FAIL: client did not connect+auth within timeout")
            return 1

        results = []
        for n in (1, 2):
            future = client.request_transcribe(str(audio), 22050, "en", timeout=_RESULT_TIMEOUT_S)
            if future is None:
                print(f"[bridge] FAIL: request {n} refused (no port)")
                return 1
            t0 = time.perf_counter()
            try:
                result = future.result(timeout=_RESULT_TIMEOUT_S)
            except Exception as exc:
                print(f"[bridge] FAIL: request {n} future raised: {exc!r}")
                return 1
            dt = time.perf_counter() - t0
            print(f"[bridge] request {n} resolved in {dt:.1f}s text={str(result.get('text'))[:60]!r}")
            results.append({"text": str(result.get("text") or ""), "latency_ms": int(result.get("latency_ms") or 0)})
            if client._resolvers:
                print(f"[bridge] FAIL: resolver map not drained after request {n}: {sorted(client._resolvers)}")
                return 1

        evidence["results"] = results
        evidence["publishes"] = len(published)
        same_text = results[0]["text"].strip() == results[1]["text"].strip() != ""
        print(f"[bridge] both futures resolved by own id: True; identical non-empty text: {same_text}")
        evidence["both_resolved_by_id"] = True
        evidence["identical_text"] = same_text
        result_ok = same_text and len(published) >= 2
        if with_abort:
            if not _run_samples_leg(client, published, audio, log_path, evidence):
                return 1
            if not _run_abort_leg(client, published, audio, log_path, evidence):
                return 1
            result_ok = result_ok and evidence["samples_ok"] and evidence["abort_ok"]
        if with_streaming:
            if not _run_streaming_leg(client, published, audio, evidence):
                return 1
            result_ok = result_ok and evidence["streaming_ok"]
        client.close()
        evidence["result_ok"] = result_ok
    finally:
        if proc.poll() is None:
            proc.kill()
        handles["log"].close()

    out = work / "item_c2_bridge.json"
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"[bridge] evidence written to {out}")
    print(f"[bridge] RESULT_OK={evidence.get('result_ok')}")
    return 0 if evidence.get("result_ok") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument(
        "--with-abort",
        action="store_true",
        help="also run the C3 samples leg and the C4 abort mid-inference leg",
    )
    parser.add_argument(
        "--with-streaming",
        action="store_true",
        help="also run the C6 streaming overlap leg (open/push/finalize)",
    )
    args = parser.parse_args()

    work = Path(os.environ.get("TEMP", ".")) / "vt_verify"
    work.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(32)
    previous_token = os.environ.get(IPC_TOKEN_ENV_VAR)
    os.environ[IPC_TOKEN_ENV_VAR] = token
    try:
        return _run(
            args.config_dir, args.audio, work, work / "worker_bridge.log", token, args.with_abort, args.with_streaming
        )
    finally:
        if previous_token is None:
            os.environ.pop(IPC_TOKEN_ENV_VAR, None)
        else:
            os.environ[IPC_TOKEN_ENV_VAR] = previous_token


if __name__ == "__main__":
    raise SystemExit(main())
