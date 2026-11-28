"""Manual local E2E: localhost pack -> install -> installed worker -> real ASR.

Owner command (from the repo root, repo venv active)::

    python tests/offline_pack_e2e/run_local_pack_e2e.py \\
        --native-dir <dir with transcribe.dll + contract.json> \\
        --audio <16k mono wav> --expect "<transcript>" \\
        --out <evidence.json>

Nothing is downloaded, published or installed system-wide. The pack is
served from 127.0.0.1, installed into a fresh TEMP root, and the installed
launcher runs the REAL worker module from the source checkout (the supported
dev seam; no frozen worker is built locally).
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from scripts.release.build_pack_manifest import build_pack_manifest  # noqa: E402
from voice_typer.server._paths import IPC_TOKEN_ENV_VAR  # noqa: E402

from tests.offline_pack_e2e.fixtures import MANIFEST_NAME, WORKER_NAME, RecordingBus  # noqa: E402
from tests.offline_pack_e2e.pack_server import LoopbackPackServer  # noqa: E402


def _worker_launcher() -> bytes:
    repo = str(REPO_ROOT).replace("\\", "\\\\")
    return (
        "import runpy, sys\n"
        f"sys.path.insert(0, {repo!r})\n"
        'runpy.run_module("voice_typer.worker", run_name="__main__")\n'
    ).encode()


def _scratch_config(scratch: Path) -> Path:
    cfg_dir = scratch / "cfg"
    cfg_dir.mkdir(parents=True)
    if os.name == "nt":
        source = Path(os.environ["APPDATA"]) / "lausu" / "config.json"
    else:
        source = Path.home() / ".lausu" / "config.json"
    data: dict = {}
    if source.is_file():
        data = json.loads(source.read_text(encoding="utf-8"))
    data.update({"active_plugin": "", "paste_on_stop": False, "device": "cpu"})
    data.setdefault("model_size", "parakeet")
    (cfg_dir / "config.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return cfg_dir


def _read_handshake(stream, proc, timeout_s: float) -> dict:
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        line = stream.readline().strip()
        if line:
            payload = json.loads(line)
            if payload.get("event") == "worker_started":
                return payload
        if proc.poll() is not None:
            raise RuntimeError(f"installed worker exited early: {proc.returncode}")
    raise TimeoutError("installed worker never emitted worker_started")


def main() -> int:  # noqa: C901 - linear harness reads better flat
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dir", required=True, type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--expect", default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--pack-version", default="31")
    args = parser.parse_args()
    if not args.audio.is_file() or not (args.native_dir / "transcribe.dll").is_file():
        parser.error("audio file and native transcribe.dll must exist")

    scratch = Path(tempfile.mkdtemp(prefix="r10-pack-e2e-"))
    cfg_dir = _scratch_config(scratch)
    pack_root = scratch / "runtime-pack"
    token = secrets.token_hex(32)
    previous_token = os.environ.get(IPC_TOKEN_ENV_VAR)
    os.environ[IPC_TOKEN_ENV_VAR] = token

    archive = scratch / f"pack-{args.pack_version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(WORKER_NAME, _worker_launcher())
    manifest = dict(build_pack_manifest(archive, version=args.pack_version))
    server = LoopbackPackServer(
        {
            MANIFEST_NAME: json.dumps(manifest).encode(),
            f"pack-{args.pack_version}.zip": archive.read_bytes(),
        }
    ).start()
    evidence: dict = {"scratch": str(scratch), "pack_version": args.pack_version}
    proc = None
    try:
        os.environ["VT_PACK_DEV_LOCAL_SERVER"] = "1"
        os.environ["VT_PACK_ROOT"] = str(pack_root)
        os.environ["VOICE_TYPER_CONFIG_DIR"] = str(cfg_dir)
        os.environ["VT_PACK_MANIFEST_URL"] = server.url(MANIFEST_NAME)
        os.environ["TRANSCRIBE_LIBRARY"] = str(args.native_dir / "transcribe.dll")
        os.environ.setdefault("HF_HUB_CACHE", str(Path.home() / ".cache" / "huggingface" / "hub"))
        os.environ["PYTHONPATH"] = str(REPO_ROOT)

        from voice_typer.server.service import update_check

        bus = RecordingBus()
        result = update_check.check_offline_pack_update(None, bus, root=pack_root)
        terminal = bus.wait_for({"offline_pack_verified", "offline_pack_corrupt", "offline_pack_download_failed"})
        evidence["check_result"] = result
        evidence["terminal_event"] = terminal
        if terminal is None or terminal["type"] != "offline_pack_verified":
            print(f"[e2e] FAIL: pack not verified: {terminal}")
            return 1

        installed_worker = pack_root / args.pack_version / WORKER_NAME
        evidence["installed_worker"] = str(installed_worker)
        log_path = scratch / "worker.log"
        log_file = log_path.open("w", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, str(installed_worker)],
            cwd=str(REPO_ROOT),
            env=dict(os.environ),
            stdout=subprocess.PIPE,
            stderr=log_file,
            text=True,
            bufsize=1,
        )
        handshake = _read_handshake(proc.stdout, proc, 30.0)
        port = handshake.get("port")
        evidence["handshake"] = handshake
        if not isinstance(port, int):
            print("[e2e] FAIL: installed worker gave no port")
            return 1

        from scripts.verify_worker_handoff_live import _ResultSink as ScriptSink, _wait_for_connected

        sink = ScriptSink()
        from voice_typer.server import worker_relay
        from voice_typer.server.worker_client import get_shared_client

        worker_relay.reset_worker_port()
        if not worker_relay.handle_host_frame(
            {
                "type": "worker_started",
                "data": {"pid": proc.pid, "version": args.pack_version, "port": port},
                "id": 1,
            }
        ):
            print("[e2e] FAIL: real host relay refused installed worker")
            return 1
        client = get_shared_client()
        client.update_from_worker_started({"pid": proc.pid, "version": args.pack_version, "port": port})
        client._publish = sink
        if not _wait_for_connected(log_path, proc, 30.0):
            print("[e2e] FAIL: sidecar client did not connect+auth to installed worker")
            return 1

        request_id = client.send_transcribe(str(args.audio), 16000, "en")
        result_event = sink.wait_for("transcribe_offline_result", 300.0)
        if request_id is None or result_event is None:
            print("[e2e] FAIL: no real transcription result")
            return 1
        data = result_event.get("data") or {}
        evidence["transcription"] = {
            "text": data.get("text"),
            "error": data.get("error"),
            "latency_ms": data.get("latency_ms"),
        }
        text = str(data.get("text") or "").strip()
        matched = args.expect is None or text == args.expect.strip()
        evidence["text_matches"] = matched
        print(f"[e2e] transcript={text!r} error={data.get('error')!r} matched={matched}")
        log_file.close()
        return 0 if matched and not data.get("error") else 1
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        server.stop()
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            print(f"[e2e] evidence written to {args.out}")
        print(f"[e2e] scratch retained for inspection: {scratch}")
        if previous_token is None:
            os.environ.pop(IPC_TOKEN_ENV_VAR, None)
        else:
            os.environ[IPC_TOKEN_ENV_VAR] = previous_token


if __name__ == "__main__":
    raise SystemExit(main())
