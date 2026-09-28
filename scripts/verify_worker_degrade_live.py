"""ADR-0024 Step 6 (c) — live pack-missing degradation probe.

Exercises the REAL ``_handle_transcribe_offline`` degradation matrix
(``lifecycle.py`` §8.10) against a REAL (temp) pack root, with no mocks
on the decision path: ``_local_offline_pack_version`` -> ``offline_pack_exists``
-> ``queued/degraded/reason``. Uses the shared IPC test helper to obtain a
real ``IPCServer`` bound to the isolated ``VT_PACK_ROOT``.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def main() -> int:  # noqa: C901
    # Isolate the pack root BEFORE importing the config/offline_pack chain.
    tmp = Path(tempfile.mkdtemp(prefix="packroot_"))
    os.environ["VT_PACK_ROOT"] = str(tmp)

    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from fixtures.ipc_test_helpers import make_ipc_server_with_fakes

    ipc_server, _app, _service = make_ipc_server_with_fakes()
    handler = ipc_server._handle_transcribe_offline

    def call(payload: dict) -> dict:
        resp: dict = {"type": "ack", "data": {}}
        handler(payload, resp)
        return resp.get("data") or {}

    evidence: dict = {"pack_root": str(tmp), "pack_root_exists": tmp.exists()}

    # Case 1: pack root is empty -> must degrade, never silently queue.
    empty = call({"audio_path": "C:/tmp/nope.wav", "sample_rate": 22050, "language": "en"})
    evidence["pack_missing_case"] = empty
    ok_missing = (
        empty.get("queued") is False and empty.get("degraded") is True and empty.get("reason") == "offline_pack_missing"
    )
    print(f"[degrade] pack-missing -> {json.dumps(empty)}")
    print(f"[degrade] pack-missing correct: {ok_missing}")

    # Case 2: fabricate a valid pack (manifest + one file) so the cheap
    # existence check passes -> the handler must NOT degrade on the pack
    # gate (it will either forward or queue-until-worker-ready; both are
    # non-degraded, proving the gate is what decided case 1).
    version = "9.9.9"
    pdir = tmp / version
    pdir.mkdir(parents=True, exist_ok=True)
    worker_file = pdir / "lausu-worker-x86_64-pc-windows-msvc.exe"
    worker_file.write_bytes(b"fake-worker-binary")
    manifest = {
        "version": version,
        "sha256": "0" * 64,
        "min_proto_version": 1,
        "files": [{"name": worker_file.name, "sha256": "0" * 64, "size": worker_file.stat().st_size}],
    }
    (pdir / "pack-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    present = call({"audio_path": "C:/tmp/nope.wav", "sample_rate": 22050, "language": "en"})
    evidence["pack_present_case"] = present
    # With a pack present the response is either forwarded (worker ready)
    # or queued worker_not_ready -- NOT degraded/offline_pack_missing.
    ok_present = present.get("degraded") is not True and present.get("reason") != "offline_pack_missing"
    print(f"[degrade] pack-present  -> {json.dumps(present)}")
    print(f"[degrade] pack-present correct (not degraded): {ok_present}")

    # Case 3: remove the pack again -> must degrade again (round trip).
    shutil.rmtree(pdir)
    again = call({"audio_path": "C:/tmp/nope.wav", "sample_rate": 22050, "language": "en"})
    evidence["pack_removed_again_case"] = again
    ok_removed = again.get("queued") is False and again.get("reason") == "offline_pack_missing"
    print(f"[degrade] pack-removed-again -> {json.dumps(again)}")
    print(f"[degrade] pack-removed-again correct: {ok_removed}")

    ok = ok_missing and ok_present and ok_removed
    evidence["result_ok"] = ok
    out = Path(os.environ.get("TEMP", ".")) / "vt_verify" / "step6c_degrade.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"[degrade] RESULT_OK={ok} (evidence: {out})")
    # Clean the isolated pack root: it is a throwaway fixture, and leaving
    # one behind per run accumulates junk in TEMP.
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"[degrade] temp pack root removed: {tmp}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
