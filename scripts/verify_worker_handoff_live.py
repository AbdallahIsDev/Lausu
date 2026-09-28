"""ADR-0024 Step 6 — live worker-handoff verification on a real host.

Drives REAL processes: spawns the actual worker, reads its real
``worker_started`` handshake, connects the real
:class:`~voice_typer.server.worker_client.WorkerClient`, and checks a
real ``transcribe_offline`` round trip returns the expected text. The
static preflight (``verify_worker_handoff_preflight.py``) proves the
wiring exists; this proves it runs.

Usage (from the repo root, with a real model selected in the config
under ``--config-dir``)::

    python scripts/verify_worker_handoff_live.py \\
        --config-dir <dir> --audio <file.wav> --expect "<text>"

Nothing here mocks a process, a socket, or the ASR engine. It never
touches the developer's real profile: ``--config-dir`` is explicit.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from voice_typer.server._paths import IPC_TOKEN_ENV_VAR  # noqa: E402

_HANDSHAKE_RE = re.compile(r'"event"\s*:\s*"worker_started"')

# Model load on CPU plus one inference; generous so a slow host does not
# produce a false negative.
_CONNECT_TIMEOUT_S = 30.0
_RESULT_TIMEOUT_S = 600.0


class _ResultSink:
    """Collects event-bus publishes from the worker client."""

    def __init__(self) -> None:
        self._q: queue.Queue[dict] = queue.Queue()
        self.all: list[dict] = []

    def __call__(self, event: dict) -> None:
        self.all.append(event)
        self._q.put(event)

    def wait_for(self, ftype: str, timeout: float) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                event = self._q.get(timeout=0.25)
            except queue.Empty:
                continue
            if event.get("type") == ftype:
                return event
        return None


def _read_handshake(stream, proc, timeout: float) -> dict:
    """Block until the worker's ``worker_started`` stdout line arrives."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = stream.readline()
        if not line:
            if proc.poll() is not None:
                raise RuntimeError(f"worker exited early with code {proc.returncode}")
            continue
        line = line.strip()
        if not line or not _HANDSHAKE_RE.search(line):
            continue
        return json.loads(line)
    raise TimeoutError("worker did not emit worker_started in time")


def _wait_for_connected(log_path: Path, proc: subprocess.Popen, timeout: float = 30.0) -> bool:
    """Block until the worker logs a successful client connection.

    The worker emits ``slim-core sidecar connected from ...`` only AFTER
    it has accepted the auth frame, so seeing that line is proof the hop
    is fully established and the next request cannot be lost. Polling the
    worker's own log beats sleeping a fixed interval: a slow host makes
    the old sleep fire too early (request queued, never sent) and a fast
    host makes it waste time.
    """
    needle = "slim-core sidecar connected from"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        if needle in text:
            return True
        time.sleep(0.2)
    return False


def _spawn_worker(config_dir: Path, token: str, log_path: Path) -> tuple[subprocess.Popen, dict]:
    """Spawn the real worker with the real auth token + config dir."""
    env = dict(os.environ)
    env["VOICE_TYPER_IPC_TOKEN"] = token
    env["VOICE_TYPER_CONFIG_DIR"] = str(config_dir)
    env["PYTHONUNBUFFERED"] = "1"
    log_file = log_path.open("w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "voice_typer.worker"],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=log_file,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    return proc, {"log": log_file}


def main() -> int:  # noqa: C901 - a linear verification script reads better flat
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--expect", default=None, help="exact expected transcript text")
    parser.add_argument(
        "--expect-file",
        type=Path,
        default=None,
        help="file holding the expected transcript (safer than --expect on shells that split words)",
    )
    parser.add_argument("--out", type=Path, default=None, help="write the evidence JSON here")
    parser.add_argument(
        "--respawn",
        action="store_true",
        help=(
            "ADR-0024 Step 6 row (b): after the first worker connects, kill it and "
            "bring up a replacement, relay the NEW port through the real "
            "worker_relay, and run the transcription through the replacement. "
            "Mirrors what the Rust respawn supervisor does (spawn + relay the "
            "new bind), so the sidecar-side half of the recovery is proven "
            "with real processes, real sockets and real ASR."
        ),
    )
    args = parser.parse_args()

    if args.expect is None and args.expect_file is None:
        parser.error("one of --expect / --expect-file is required")
    expected = args.expect if args.expect is not None else args.expect_file.read_text(encoding="utf-8").strip()

    work = Path(os.environ.get("TEMP", ".")) / "vt_verify"
    log_path = work / "worker.log"
    work.mkdir(parents=True, exist_ok=True)

    token = secrets.token_hex(32)
    # The host passes the SAME token to the sidecar and the worker
    # (Rust `worker_shared_env`). The client reads it from the
    # environment, so the harness must mirror that instead of only
    # exporting it to the child. Restore the previous value afterwards so
    # the harness does not leave a live token in its own environment.
    previous_token = os.environ.get(IPC_TOKEN_ENV_VAR)
    os.environ[IPC_TOKEN_ENV_VAR] = token
    try:
        return _run(args, expected, token, work, log_path)
    finally:
        if previous_token is None:
            os.environ.pop(IPC_TOKEN_ENV_VAR, None)
        else:
            os.environ[IPC_TOKEN_ENV_VAR] = previous_token


def _relay_new_port(worker_relay, new_port: int, new_pid: int) -> bool:
    """Feed a REPLACEMENT worker's bind through the real relay ingest path.

    The relay is the single production place that learns a worker port, and
    it repoints the shared client itself (E7: no second client/store). The
    harness calls it exactly as the host's relay frame would arrive.
    """
    if not worker_relay.handle_host_frame(
        {
            "type": "worker_started",
            "data": {"pid": new_pid, "version": "v1", "port": new_port},
            "id": 2,
        }
    ):
        print("[harness] FAIL: relay rejected the replacement worker_started")
        return False
    if worker_relay.get_worker_port() != new_port:
        print("[harness] FAIL: relay did not store the new port")
        return False
    print(f"[harness] relayed new port={new_port} to shared client")
    return True


def _run(args, expected: str, token: str, work: Path, log_path: Path) -> int:
    print(f"[harness] spawning worker (config_dir={args.config_dir})")
    proc, handles = _spawn_worker(args.config_dir, token, log_path)
    # Replaced only on the --respawn leg; the finally block cleans both.
    extra_proc = None
    extra_handles = None

    evidence: dict = {"worker_pid": proc.pid, "log": str(log_path)}
    try:
        handshake = _read_handshake(proc.stdout, proc, _CONNECT_TIMEOUT_S)
        port = handshake.get("port")
        print(f"[harness] worker_started: port={port} protocol={handshake.get('protocol')}")
        if not isinstance(port, int):
            print("[harness] FAIL: handshake carried no integer port")
            return 1
        evidence["port"] = port
        evidence["handshake"] = handshake

        # Drive the real relay ingest + real client, exactly as the
        # host relay + sidecar do (no second port store, C-CONF-1).
        from voice_typer.server import worker_relay
        from voice_typer.server.worker_client import get_shared_client

        worker_relay.reset_worker_port()
        accepted = worker_relay.handle_host_frame(
            {
                "type": "worker_started",
                "data": {"pid": proc.pid, "version": "v1", "port": port},
                "id": 1,
            }
        )
        stored = worker_relay.get_worker_port()
        print(f"[harness] relay accepted={accepted} stored_port={stored}")
        if not accepted or stored != port:
            print("[harness] FAIL: port relay did not store the worker port")
            return 1
        evidence["relay_port"] = stored

        sink = _ResultSink()
        # The process-wide singleton, i.e. the exact object the app uses.
        client = get_shared_client()
        if not client.update_from_worker_started({"port": port, "pid": proc.pid, "version": "v1"}):
            print("[harness] FAIL: client rejected the relayed worker_started")
            return 1
        client._publish = sink

        # Replace the old fixed sleep: poll the worker's OWN log for the
        # connect+auth line it writes after a client authenticates. This
        # is deterministic and fails loudly instead of racing a sleep.
        if not _wait_for_connected(log_path, proc):
            print("[harness] FAIL: client did not connect+auth within timeout")
            return 1
        request_id = client.send_transcribe(str(args.audio), 22050, "en")
        print(f"[harness] sent transcribe_offline request_id={request_id}")
        if request_id is None:
            print("[harness] FAIL: client refused to queue the request")
            return 1

        result = sink.wait_for("transcribe_offline_result", _RESULT_TIMEOUT_S)
        if result is None:
            print("[harness] FAIL: no transcribe_offline_result within timeout")
            return 1

        data = result.get("data") or {}
        text = str(data.get("text") or "")
        error = data.get("error")
        latency_ms = data.get("latency_ms")
        print(f"[harness] result latency_ms={latency_ms} error={error!r}")
        print(f"[harness] text={text!r}")

        matched = text.strip() == expected.strip()
        print(f"[harness] text matches expected: {matched}")
        evidence.update({"text": text, "error": error, "latency_ms": latency_ms, "text_matches": matched})
        result_ok = bool(matched and not error)

        if args.respawn:
            # Post-respawn transcription (Step 6 row b, second half).
            first_pid, first_port = proc.pid, port
            proc.kill()
            proc.wait(timeout=30)
            print(f"[harness] killed first worker pid={first_pid} (was port {first_port})")

            respawn_log = work / "worker_respawn.log"
            extra_proc, extra_handles = _spawn_worker(args.config_dir, token, respawn_log)
            handshake2 = _read_handshake(extra_proc.stdout, extra_proc, _CONNECT_TIMEOUT_S)
            new_port = handshake2.get("port")
            print(f"[harness] replacement worker_started: pid={extra_proc.pid} port={new_port}")
            if not isinstance(new_port, int):
                print("[harness] FAIL: replacement handshake carried no integer port")
                return 1
            if new_port == first_port:
                print("[harness] FAIL: replacement reused the old port (not a real rebind)")
                return 1
            evidence["respawn"] = {
                "first_pid": first_pid,
                "first_port": first_port,
                "new_pid": extra_proc.pid,
                "new_port": new_port,
            }
            if not _relay_new_port(worker_relay, new_port, extra_proc.pid):
                return 1
            if not _wait_for_connected(respawn_log, extra_proc):
                print("[harness] FAIL: client did not reconnect to the replacement worker")
                return 1
            print("[harness] client reconnected to the replacement worker")

            request_id2 = client.send_transcribe(str(args.audio), 22050, "en")
            print(f"[harness] post-respawn transcribe_offline request_id={request_id2}")
            if request_id2 is None:
                print("[harness] FAIL: client refused the post-respawn request")
                return 1
            result2 = sink.wait_for("transcribe_offline_result", _RESULT_TIMEOUT_S)
            if result2 is None:
                print("[harness] FAIL: no post-respawn transcribe_offline_result")
                return 1
            data2 = result2.get("data") or {}
            text2 = str(data2.get("text") or "")
            error2 = data2.get("error")
            latency2 = data2.get("latency_ms")
            print(f"[harness] post-respawn result latency_ms={latency2} error={error2!r}")
            print(f"[harness] post-respawn text={text2!r}")
            matched2 = text2.strip() == expected.strip()
            print(f"[harness] post-respawn text matches expected: {matched2}")
            evidence["respawn"].update(
                {"text": text2, "error": error2, "latency_ms": latency2, "text_matches": matched2}
            )
            result_ok = result_ok and bool(matched2 and not error2)
        else:
            print("[harness] killing worker mid-idle (peer death, no respawn leg)")
            proc.kill()
            proc.wait(timeout=30)
            evidence["worker_killed"] = True
            time.sleep(2.0)

        client.close()
        evidence["result_ok"] = result_ok
    finally:
        for child, opened in ((proc, handles), (extra_proc, extra_handles)):
            if child is not None and child.poll() is None:
                child.kill()
            if opened is not None:
                opened["log"].close()

    if args.out:
        args.out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        print(f"[harness] evidence written to {args.out}")

    print(f"[harness] RESULT_OK={evidence.get('result_ok')}")
    return 0 if evidence.get("result_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
