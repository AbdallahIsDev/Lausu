#!/usr/bin/env python3
"""ADR-0024 host gate: the FROZEN slim sidecar boots and transcribes via the worker.

``scripts/verify_worker_handoff_live.py`` proved the worker hop, but it drove
``worker_relay`` / ``WorkerClient`` **in-process from source**. That cannot see
the failure this gate exists for: with
``--nofollow-import-to=faster_whisper,ctranslate2`` (ADR-0025 C7) the frozen
sidecar has no ASR library on disk, so any surviving in-process import surfaces
as ``ModuleNotFoundError`` at launch or mid-dictation, and VAD silently
degrades. Unit tests cannot observe either because the source tree still has
the libs installed.

So this gate does what production does:

1. launches the FROZEN sidecar exe (``--ws``) and reads its real
   ``server_started`` handshake off stdout,
2. authenticates on the real host<->sidecar WS hop,
3. relays a REAL worker ``worker_started {pid, version, port}`` frame into the
   frozen sidecar's own relay,
4. drives ``media_transcribe_start`` over the real dispatch hop so a real WAV
   crosses the worker hop *inside the frozen binary*,
5. triggers recorder init so Silero VAD warms in the frozen binary,
6. asserts the transcript and greps the frozen sidecar's own log for
   ``[VAD] Silero VAD model preloaded + warmed`` and a C-LOG-2
   ``[WORKER] offline transcription complete ... <duration>`` line.

The worker is launched as a subprocess exactly as ADR-0024 Step 6 did (the
frozen-worker question is a separate gate); the thing under test here is the
sidecar.

Requires ``websockets`` in the interpreter that runs this script.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

_TOKEN_ENV = "VOICE_TYPER_IPC_TOKEN"
_PROTOCOL_VERSION = 1
_START_TIMEOUT_S = 300.0
_TRANSCRIBE_TIMEOUT_S = 900.0
# The C-LOG-2 line reads "[VAD] Silero VAD model loaded from local ONNX,
# preloaded + warmed <d>" - match the stable tail, not the leading clause, so
# a wording change in the loader does not silently disarm this gate.
_VAD_MARKER = "preloaded + warmed"
# NOTE: the log line the sidecar writes is
#   [WORKER] transcribe_offline_result (len=N chars) <duration>
# but `security.redaction.redact_api_keys` rewrites the token
# `transcribe_offline_result` to `***` (it treats the trailing `_result`
# as a secret-ish key), so the name is NOT greppable in the log. Match the
# stable, non-redacted shape instead. The redaction defect itself is recorded
# separately, not fixed here.
_WORKER_MARKER_RE = re.compile(r"\[WORKER\].*\(len=\d+ chars\)")
# C-LOG-2 canonical form: the suffix is `` 2.3s`` / `` 1m 2.3s`` — one leading
# SPACE, nothing glued to the number. Requiring the space rejects the banned
# ``took=2.3s`` shape; a leading ``--``/``—`` marker cannot be told apart from a
# space by regex alone and is not asserted here.
_DURATION_RE = re.compile(r" \d+(?:m \d+)?\.\ds$")

# Worker default cwd: the dev worker runs from the source checkout.
REPO_ROOT = Path(__file__).resolve().parents[1]


def _log(msg: str) -> None:
    print(f"[frozen-gate] {msg}", flush=True)


def _fail(msg: str) -> int:
    print(f"[frozen-gate] FAIL: {msg}", flush=True)
    return 1


def _read_stream_handshake(stream, proc: subprocess.Popen, timeout: float) -> dict | None:
    """Read one JSON object from a PIPE-backed stream (the worker handshake)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = stream.readline()
        if not line:
            if proc.poll() is not None:
                return None
            time.sleep(0.05)
            continue
        line = line.strip()
        if not line:
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return None


def _read_sidecar_handshake(stdout_path: Path, proc: subprocess.Popen, timeout: float) -> dict | None:
    """Read the sidecar's ``server_started`` line by PATH, not by shared handle.

    Popen dups the child's stdout onto the same file description the parent
    holds, so the two share one file offset: once the child has written the
    handshake the parent's reader sits at EOF forever. Opening the path
    separately gives an independent offset. (Reopening the parent's own
    handle does NOT help — the offset is on the OS file description.)
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with stdout_path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass
        if proc.poll() is not None:
            return None
        time.sleep(0.5)
    return None


def _write_minimal_pack(root: Path, version: str) -> Path:
    """Install a minimal but schema-valid pack so the worker-path gate opens.

    ``update_check._local_offline_pack_version`` accepts a version only when
    every manifest-declared file exists with a matching SHA-256, so the marker
    is hashed for real rather than faked. This is deliberately NOT a full ML
    pack: it opens the gate under the product's own definition of "present"
    and nothing more. The worker resolves its model from the shared HF cache.
    """
    pack_dir = root / version
    pack_dir.mkdir(parents=True, exist_ok=True)
    marker = pack_dir / "pack-verification-marker.txt"
    marker.write_bytes(b"adr-0024 frozen slim sidecar host gate\n")
    digest = hashlib.sha256(marker.read_bytes()).hexdigest()
    manifest = {
        "version": version,
        "sha256": digest,
        "files": [{"name": marker.name, "sha256": digest, "size": marker.stat().st_size}],
        "min_proto_version": 1,
    }
    (pack_dir / "pack-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return pack_dir


class FrozenSidecarClient:
    """Minimal host-side client for the sidecar WS hop (auth + dispatch)."""

    def __init__(self, ws, token: str) -> None:
        self._ws = ws
        self._token = token
        self._next_id = 1

    async def call(self, command: str, data: dict | None = None, timeout: float = 120.0) -> dict:
        request_id = self._next_id
        self._next_id += 1
        frame: dict = {"type": command, "id": request_id}
        if data is not None:
            frame["data"] = data
        await self._ws.send(json.dumps(frame))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=max(0.1, deadline - time.monotonic()))
            msg = json.loads(raw)
            if msg.get("id") != request_id:
                continue  # push frame or another request's response
            return msg
        raise TimeoutError(f"no response for {command}")

    async def close(self) -> None:
        await self._ws.close()

    async def notify(self, frame: dict) -> None:
        await self._ws.send(json.dumps(frame))

    async def wait_push(self, push_type: str, timeout: float) -> dict | None:
        """Wait for an unsolicited bus push of *push_type* (e.g. a worker result)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=max(0.1, deadline - time.monotonic()))
            msg = json.loads(raw)
            if msg.get("type") == push_type:
                return msg
        return None


async def _connect(port: int, token: str) -> FrozenSidecarClient:
    import websockets

    ws = await websockets.connect(f"ws://127.0.0.1:{port}", max_size=8 * 1024 * 1024)
    await ws.send(json.dumps({"type": "auth", "token": token, "protocol_version": _PROTOCOL_VERSION}))
    raw = await asyncio.wait_for(ws.recv(), timeout=30)
    msg = json.loads(raw)
    if msg.get("type") not in ("ready", "auth_ok", "welcome"):
        raise RuntimeError(f"unexpected first frame after auth: {msg}")
    _log(f"authenticated on sidecar WS port={port}, first frame type={msg.get('type')!r}")
    return FrozenSidecarClient(ws, token)


def _find_sidecar_log(config_dir: Path) -> Path:
    """The sidecar's own log: <config>/logs/lausu.log.

    NOT "newest *.log": that picks native-windows.log / worker.log, whose
    markers are a different process's, which is exactly the confusion this
    function exists to avoid.
    """
    canonical = config_dir / "logs" / "lausu.log"
    if canonical.is_file():
        return canonical
    candidates = sorted(config_dir.rglob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else canonical


def _scan_log(log_path: Path, marker: str) -> list[str]:
    if not log_path.is_file():
        return []
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [line for line in text.splitlines() if marker in line]


def _scan_log_re(log_path: Path, pattern: re.Pattern[str]) -> list[str]:
    """Like :func:_scan_log but regex, for markers the redactor mangles."""
    if not log_path.is_file():
        return []
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return [line for line in text.splitlines() if pattern.search(line)]


async def _run(args: argparse.Namespace, token: str) -> int:
    work = args.work
    work.mkdir(parents=True, exist_ok=True)
    stdout_path = work / "sidecar-stdout.log"
    stderr_path = work / "sidecar-stderr.log"

    # ── 1. real worker subprocess (the hop target) ──────────────────────
    _log(f"spawning worker: {args.worker_cmd}")
    worker = subprocess.Popen(  # noqa: S603 - operator-supplied verification command
        list(args.worker_cmd),
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=(work / "worker-stderr.log").open("w", encoding="utf-8"),
        text=True,
        encoding="utf-8",
        bufsize=1,
        env={
            **os.environ,
            _TOKEN_ENV: token,
            "VOICE_TYPER_CONFIG_DIR": str(args.config_dir),
            "PYTHONUNBUFFERED": "1",
        },
    )

    sidecar = None
    try:
        handshake = _read_stream_handshake(worker.stdout, worker, 120.0)
        if not handshake or not isinstance(handshake.get("port"), int):
            return _fail(f"worker handshake carried no integer port: {handshake!r}")
        worker_port = handshake["port"]
        _log(f"worker_started handshake: port={worker_port} protocol={handshake.get('protocol')}")

        # ── 2. frozen sidecar, stdout captured (GUI-subsystem PE) ──────
        env = {
            **os.environ,
            _TOKEN_ENV: token,
            "TAURI_SIDECAR": "1",
            "VOICE_TYPER_CONFIG_DIR": str(args.config_dir),
            "VT_PACK_ROOT": str(args.pack_root),
            # onefile extraction + pack root both live under LOCALAPPDATA;
            # redirect so the gate never touches the real profile.
            "LOCALAPPDATA": str(args.scratch_localappdata),
            "APPDATA": str(args.config_dir.parent / "roaming"),
        }
        # Plain "w": the child writes here; the gate reads the handshake back
        # by PATH (_read_sidecar_handshake) because the two would otherwise share
        # one file offset.
        stdout_file = stdout_path.open("w", encoding="utf-8")
        if args.source_sidecar:
            # Pre-flight mode: same protocol against the SOURCE sidecar, so a
            # failing gate can be attributed to the freeze rather than to the
            # harness. Never a substitute for the frozen run.
            argv = [sys.executable, "-m", "voice_typer.server.ipc_server", "--ws"]
            _log(f"PRE-FLIGHT MODE: source sidecar (NOT the frozen gate): {argv}")
        else:
            argv = [str(args.sidecar_exe), "--ws"]
            _log(f"launching frozen sidecar: {argv}")
        sidecar = subprocess.Popen(  # noqa: S603 - operator-supplied path
            argv,
            cwd=str(REPO_ROOT),
            stdout=stdout_file,
            stderr=stderr_path.open("w", encoding="utf-8"),
            env=env,
        )
        started = _read_sidecar_handshake(stdout_path, sidecar, _START_TIMEOUT_S)
        if not started or not isinstance(started.get("port"), int):
            return _fail(f"frozen sidecar printed no server_started handshake: {started!r}")
        sidecar_port = started["port"]
        _log(f"frozen sidecar server_started: port={sidecar_port} pid={sidecar.pid}")

        log_path = _find_sidecar_log(args.config_dir)
        client = await _connect(sidecar_port, token)

        # ── 3. relay the REAL worker port into the frozen sidecar ──────
        await client.notify(
            {
                "type": "worker_started",
                "data": {"pid": worker.pid, "version": "gate", "port": worker_port},
                "id": 900,
            }
        )
        _log(f"relayed worker_started pid={worker.pid} port={worker_port} into the frozen sidecar")

        # ── 4. recorder init so Silero VAD warms in the frozen binary ──
        try:
            mic = await client.call("microphone_test_start", {}, timeout=90.0)
            _log(f"microphone_test_start -> {mic.get('type')} {json.dumps(mic.get('data'))[:160]}")
            await client.call("microphone_test_cancel", {}, timeout=60.0)
        except Exception as exc:  # noqa: BLE001 - report, do not mask the real gates
            _log(f"WARN: microphone_test_start/cancel failed ({exc!r}); VAD may stay cold")

        # ── 5. real transcription through the worker hop ────────────────
        # ``transcribe_offline`` is the deterministic worker-hop entry point:
        # the sidecar acks immediately and the worker pushes
        # ``transcribe_offline_result {text, latency_ms}`` back on the bus.
        # Driving it through the frozen dispatch surface is what proves the
        # frozen code has no in-process ASR dependency left.
        _log(f"dispatching transcribe_offline for {args.audio}")
        ack = await client.call(
            "transcribe_offline",
            {"audio_path": str(args.audio), "sample_rate": args.sample_rate, "language": None},
            timeout=120.0,
        )
        _log(f"transcribe_offline ack -> {ack.get('type')} {json.dumps(ack.get('data'))[:200]}")
        ack_data = ack.get("data") or {}
        if ack.get("type") == "error":
            return _fail(f"transcribe_offline returned an error: {ack_data}")
        if ack_data.get("degraded"):
            return _fail(f"transcribe_offline degraded: {ack_data}")

        result = await client.wait_push("transcribe_offline_result", timeout=_TRANSCRIBE_TIMEOUT_S)
        if result is None:
            return _fail("no transcribe_offline_result push arrived before the timeout")
        result_data = result.get("data") or {}
        text = str(result_data.get("text") or "")
        _log(
            f"transcribe_offline_result: text_len={len(text)} "
            f"latency_ms={result_data.get('latency_ms')} device={result_data.get('device_info')!r}"
        )
        # Supplementary: the media-ingest leg (site 4) rides the same hop but
        # adds a decode + windowing layer. Recorded, not asserted, so a decode
        # quirk cannot mask or fake the primary result.
        media_note = ""
        try:
            mstart = await client.call("media_transcribe_start", {"source": str(args.audio)}, timeout=180.0)
            media_note = f"media_transcribe_start -> {mstart.get('type')} {json.dumps(mstart.get('data'))[:160]}"
            _log(media_note)
        except Exception as exc:  # noqa: BLE001 - supplementary, never fatal
            media_note = f"media_transcribe_start failed: {exc!r}"
            _log(f"WARN: {media_note}")

        await client.call("shutdown", {}, timeout=60.0)
        await client.close()

        # ── 6. in-binary log assertions ─────────────────────────────────
        vad_lines = _scan_log(log_path, _VAD_MARKER)
        worker_lines = _scan_log_re(log_path, _WORKER_MARKER_RE)
        _log(f"[VAD] marker lines in frozen sidecar log: {len(vad_lines)}")
        for line in vad_lines[-2:]:
            _log(f"  VAD> {line}")
        _log(f"[WORKER] marker lines in frozen sidecar log: {len(worker_lines)}")
        for line in worker_lines[-2:]:
            _log(f"  WORKER> {line}")

        expected = args.expect_file.read_text(encoding="utf-8").strip() if args.expect_file else args.expect
        text_matches = bool(expected) and text.strip() == expected.strip()
        duration_ok = any(_DURATION_RE.search(line.strip()) for line in worker_lines)

        evidence = {
            "sidecar_exe": str(args.sidecar_exe),
            "sidecar_pid": sidecar.pid,
            "sidecar_port": sidecar_port,
            "worker_pid": worker.pid,
            "worker_port": worker_port,
            "media_note": media_note,
            "text": text,
            "expected": expected,
            "text_matches": text_matches,
            "vad_marker_found": bool(vad_lines),
            "vad_lines": vad_lines[-3:],
            "worker_marker_found": bool(worker_lines),
            "worker_lines": worker_lines[-3:],
            "log_duration_suffix_ok": duration_ok,
            "sidecar_log": str(log_path),
        }
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

        problems = []
        if not text_matches:
            problems.append(f"transcript mismatch (got {text!r})")
        if not vad_lines:
            problems.append(f"no {_VAD_MARKER!r} line in the frozen sidecar log")
        if not worker_lines:
            problems.append("no [WORKER] ... (len=N chars) result line in the frozen sidecar log")
        if worker_lines and not duration_ok:
            problems.append("[WORKER] completion line has no C-LOG-2 duration suffix")
        if problems:
            return _fail("; ".join(problems))

        _log("FROZEN_SLIM_GATE_OK")
        return 0
    finally:
        for proc in (sidecar, worker):
            if proc is None or proc.poll() is not None:
                continue
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=20)
            _log(f"terminated pid={proc.pid}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sidecar-exe", required=True, type=Path, help="the FROZEN slim sidecar exe")
    parser.add_argument(
        "--source-sidecar",
        action="store_true",
        help="pre-flight: drive the SOURCE sidecar instead of the frozen exe (harness self-check)",
    )
    parser.add_argument("--worker-cmd", required=True, nargs=argparse.REMAINDER, help="worker launch command")
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--expect", default=None)
    parser.add_argument("--expect-file", type=Path, default=None)
    parser.add_argument("--pack-version", default="0.0.0-gate")
    parser.add_argument("--model-size", default="large-v3", help="ASR model the worker must load")
    parser.add_argument(
        "--sample-rate", type=int, default=16000, help="sample rate of --audio (production records at 16 kHz)"
    )
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.expect is None and args.expect_file is None:
        parser.error("one of --expect / --expect-file is required")

    # A per-run scratch root (pid-suffixed): a previous run that ended mid-config
    # migration can leave an unreadable config.json behind, and reusing the tree
    # would make the NEXT run fail for a reason that has nothing to do with the
    # freeze under test.
    home = Path.home()
    scratch = home / f"frozen-gate-{os.getpid()}"
    _log(f"scratch root: {scratch}")
    args.work = scratch / "work"
    args.config_dir = scratch / "config"
    args.pack_root = scratch / "runtime-pack"
    args.scratch_localappdata = scratch / "localappdata"
    roaming = args.config_dir.parent / "roaming"
    for d in (args.work, args.config_dir, args.pack_root, args.scratch_localappdata, roaming):
        d.mkdir(parents=True, exist_ok=True)

    pack_dir = _write_minimal_pack(args.pack_root, args.pack_version)
    _log(f"minimal pack installed at {pack_dir} (version={args.pack_version})")

    # A selected model is required by media_transcribe_start; the worker
    # resolves the weights from the shared HF cache at transcription time.
    # ``schema_version`` is seeded at the CURRENT value on purpose: a v0 config
    # makes the loader run the migration + pre-migration backup write, which
    # replaces config.json through ``_secure_atomic_write`` and can leave a file
    # this process can no longer open on a locked-down host. Seeding the current
    # version makes the migration a no-op so the gate never depends on it.
    # Seed through the app's OWN save path (`Config.save`), not a hand
    # write_text: the app's atomic writer is what a real install produces, and
    # a hand-written file plus a later in-process save leaves a config.json this
    # process can no longer open (observed on this host). Loading defaults then
    # setting the two fields mirrors first-install.
    os.environ["VOICE_TYPER_CONFIG_DIR"] = str(args.config_dir)
    from voice_typer.server.config import Config as _Config

    seeded = _Config.load()
    seeded.model_size = args.model_size
    # microphone_test_start gates recorder init on this consent; without it the
    # recorder never starts and Silero VAD never warms.
    seeded.voice_biometric_consent = True
    seeded.save()
    reread = _Config.load()
    if reread.model_size != args.model_size:
        raise SystemExit(
            f"[frozen-gate] FAIL: seeded config did not survive a reload "
            f"(model_size={reread.model_size!r}, expected {args.model_size!r}); "
            f"a transcribing gate would silently fall back to defaults"
        )
    _log(f"seeded config via Config.save(): model_size={reread.model_size!r}")

    token = secrets.token_hex(32)
    previous = os.environ.get(_TOKEN_ENV)
    os.environ[_TOKEN_ENV] = token
    try:
        return asyncio.run(_run(args, token))
    finally:
        if previous is None:
            os.environ.pop(_TOKEN_ENV, None)
        else:
            os.environ[_TOKEN_ENV] = previous


if __name__ == "__main__":
    sys.exit(main())
