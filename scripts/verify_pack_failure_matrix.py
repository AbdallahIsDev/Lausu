"""Headless pack/worker failure matrix, mocked, no network/GPU/hosts.

Drives five failure cells against tmp pack roots only: worker dead-port
timeout/abort, corrupt pack checksum, deleted pack dir, offline first
launch, stale pack protocol refusal. Prints one PASS/FAIL line per cell
plus an evidence line; exits nonzero on any FAIL.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

FAIL_FAST_S = 2.0
WORKER_TIMEOUT_S = 1.0
STRESS_REQUESTS = 20


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_pack(root: Path, version: str, min_proto: int = 1) -> Path:
    pdir = root / version
    pdir.mkdir(parents=True, exist_ok=True)
    blob = pdir / "worker.bin"
    blob.write_bytes(b"pack-bytes-for-matrix")
    manifest = {
        "version": version,
        "sha256": "0" * 64,
        "files": [{"name": blob.name, "sha256": _sha256_bytes(blob.read_bytes()), "size": blob.stat().st_size}],
        "min_proto_version": min_proto,
    }
    (pdir / "pack-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return pdir


class _FakeBus:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def publish(self, event: dict) -> None:
        self.events.append(event)


def _dead_client():
    from voice_typer.server import worker_client as wc_mod

    client = wc_mod.WorkerClient(publish=lambda _e: None)
    with client._lock:
        client._port = 9
    return client


def _cell_worker_killed(root: Path, iterations: int) -> tuple[bool, str]:
    from voice_typer.server import worker_backed_asr as asr_mod, worker_client as wc_mod

    latencies: list[float] = []
    for _ in range(iterations):
        client = _dead_client()
        future = client.request_transcribe("C:/tmp/nope.wav", 16000, "en", timeout=WORKER_TIMEOUT_S)
        if future is None:
            client.close()
            return False, "request refused without a future"
        start = time.monotonic()
        try:
            future.result(timeout=FAIL_FAST_S)
            client.close()
            return False, "dead-port future unexpectedly resolved"
        except TimeoutError:
            latencies.append(time.monotonic() - start)
        except Exception as exc:
            client.close()
            return False, f"wrong exception {exc!r}"
        time.sleep(WORKER_TIMEOUT_S + 0.3)
        if client._resolvers:
            client.close()
            return False, f"resolver map not drained: {sorted(client._resolvers)}"
        probe = client._register_future(client._next_id(), timeout=30.0)
        aborted = client.abort_all_outstanding()
        try:
            probe.result(timeout=FAIL_FAST_S)
            client.close()
            return False, "aborted future unexpectedly resolved"
        except wc_mod.WorkerAbortedError:
            pass
        except Exception as exc:
            client.close()
            return False, f"abort raised {exc!r} instead of WorkerAbortedError"
        if aborted != 1 or client._resolvers:
            client.close()
            return False, f"abort count={aborted} resolvers={sorted(client._resolvers)}"
        done: concurrent.futures.Future[dict] = concurrent.futures.Future()
        done.set_exception(TimeoutError("dead"))
        stub = _dead_client()

        def _samples(*_a: object, _done: object = done, **_k: object) -> concurrent.futures.Future[dict]:
            return _done  # type: ignore[return-value]

        stub.request_samples = _samples  # type: ignore[method-assign]
        original = asr_mod.get_shared_client

        def _stub_client(_stub: object = stub) -> object:
            return _stub

        asr_mod.get_shared_client = _stub_client  # type: ignore[assignment]
        try:
            import numpy as _np

            try:
                asr_mod.WorkerBackedAsr(model_size="tiny").transcribe_with_fallback(_np.zeros(160, dtype=_np.float32))
                return False, "mapping path unexpectedly resolved"
            except asr_mod.WorkerTranscriptionError:
                pass
            except Exception as exc:
                return False, f"mapping raised {exc!r} instead of WorkerTranscriptionError"
        finally:
            asr_mod.get_shared_client = original  # type: ignore[assignment]
            stub.close()
        client.close()
    worst = max(latencies) if latencies else 0.0
    if worst >= FAIL_FAST_S:
        return False, f"fail-fast violated worst={worst:.2f}s"
    return (True, f"dead-port TimeoutError x{len(latencies)} worst={worst:.2f}s abort+map OK")


def _cell_corrupt_pack(root: Path, iterations: int) -> tuple[bool, str]:
    from voice_typer.server.service import offline_pack as pack

    for i in range(iterations):
        sub = root / f"corrupt_{i}"
        if sub.exists():
            shutil.rmtree(sub)
        sub.mkdir(parents=True)
        pdir = _write_pack(sub, "v9")
        if pack.verify_offline_pack_or_skip("v9", root=sub) is not True:
            return False, "valid baseline did not verify"
        (pdir / "worker.bin").write_bytes(b"TAMPERED")
        if pack.verify_offline_pack_or_skip("v9", root=sub) is not False:
            return False, "tampered pack still verified"
        bus = _FakeBus()
        checker = pack.BackgroundChecksum("v9", event_bus=bus, root=sub)  # type: ignore[arg-type]
        checker.start()
        if checker.join(timeout_s=10.0) is not False:
            return False, "background checksum did not report corrupt"
        if not [e for e in bus.events if e.get("type") == "offline_pack_corrupt"]:
            return False, "corrupt signal missing from event bus"
    return True, f"tamper detected x{iterations} verify=False + offline_pack_corrupt signal"


def _cell_pack_deleted(root: Path, iterations: int) -> tuple[bool, str]:
    from voice_typer.server.service import offline_pack as pack, update_check

    for i in range(iterations):
        sub = root / f"deleted_{i}"
        if sub.exists():
            shutil.rmtree(sub)
        sub.mkdir(parents=True)
        _write_pack(sub, "v9")
        shutil.rmtree(sub / "v9")
        manifest_path = pack.offline_pack_manifest_path("v9", root=sub)
        if pack.load_offline_pack_manifest(manifest_path) is not None:
            return False, "missing manifest did not load None"
        if pack.offline_pack_exists("v9", root=sub) is not False:
            return False, "deleted pack still reports exists"
        if pack.verify_offline_pack_or_skip("v9", root=sub) is not False:
            return False, "deleted pack still verified"
        if update_check._local_offline_pack_version(root=sub) is not None:
            return False, "deleted pack still resolves a local version"
        bus = _FakeBus()
        pack._publish_event(bus, "offline_pack_missing", {"version": "v9"})  # type: ignore[arg-type]
        if not [e for e in bus.events if e.get("type") == "offline_pack_missing"]:
            return False, "missing signal missing from event bus"
    return True, f"deleted dir loads None exists=False verify=False + offline_pack_missing signal x{iterations}"


def _cell_no_internet(root: Path, iterations: int) -> tuple[bool, str]:
    from voice_typer.server.service import update_check

    def _raising(url: str, **_kwargs: object) -> str:
        raise ConnectionError("offline")

    url = "https://github.com/owner/repo/releases/download/v9/pack-manifest.json"
    for _ in range(iterations):
        sub = root / "offline"
        sub.mkdir(parents=True, exist_ok=True)
        try:
            first = update_check.check_offline_pack_update(
                None,
                None,
                http_get=_raising,
                manifest_url=url,
                local_version=None,
                root=sub,
                trigger_download=False,
                manifest_timeout=2.0,
            )
            second = update_check.check_offline_pack_update(
                None,
                None,
                http_get=_raising,
                manifest_url=url,
                local_version=None,
                root=sub,
                trigger_download=True,
                manifest_timeout=2.0,
            )
        except Exception as exc:
            return False, f"offline check raised {exc!r}"
        for result in (first, second):
            if result.get("success") is not False or result.get("reason") != "fetch_failed":
                return False, f"unexpected offline result {result!r}"
            if result.get("update_available") is not False:
                return False, f"offline result claims an update {result!r}"
    return True, f"http down returns fetch_failed success=False no raise x{iterations}"


def _host_proto_range() -> tuple[int, int]:
    import re

    try:
        text = (REPO_ROOT / "src-tauri" / "src" / "platform" / "worker_path.rs").read_text(encoding="utf-8")
        lo = re.search(r"HOST_MIN_PROTO_VERSION:\s*u32\s*=\s*(\d+)", text)
        hi = re.search(r"HOST_PROTO_VERSION:\s*u32\s*=\s*(\d+)", text)
        if lo and hi:
            return int(lo.group(1)), int(hi.group(1))
    except OSError:
        pass
    from voice_typer.server.ipc import protocol_version as pv

    return 1, int(pv.PROTOCOL_VERSION)


def _cell_stale_pack(root: Path, iterations: int) -> tuple[bool, str]:
    from voice_typer.server.service.offline_pack import core as pack_core

    lo, hi = _host_proto_range()
    for i in range(iterations):
        sub = root / f"stale_{i}"
        if sub.exists():
            shutil.rmtree(sub)
        sub.mkdir(parents=True)
        pdir = _write_pack(sub, "v9", min_proto=9999)
        manifest = pack_core.load_offline_pack_manifest(pdir / "pack-manifest.json")
        if manifest is None:
            return False, "stale manifest failed to parse"
        stale = int(manifest["min_proto_version"])
        if lo <= stale <= hi:
            return False, f"stale {stale} unexpectedly inside {lo}..={hi}"
        fresh_dir = _write_pack(sub, "fresh", min_proto=lo)
        fresh = pack_core.load_offline_pack_manifest(fresh_dir / "pack-manifest.json")
        if fresh is None or not (lo <= int(fresh["min_proto_version"]) <= hi):
            return False, "in-range control refused"
    return True, f"min_proto 9999 outside {lo}..={hi} refused outdated x{iterations} control {lo} allowed"


def _stress_worker_abort(root: Path) -> tuple[bool, str]:
    del root
    before = len(threading.enumerate())
    client = _dead_client()
    futures: list[concurrent.futures.Future[dict]] = []
    for _ in range(STRESS_REQUESTS):
        future = client.request_transcribe("C:/tmp/nope.wav", 16000, "en", timeout=WORKER_TIMEOUT_S)
        if future is None:
            client.close()
            return False, "stress request refused without a future"
        futures.append(future)
    worst = 0.0
    for future in futures:
        start = time.monotonic()
        try:
            future.result(timeout=FAIL_FAST_S)
            client.close()
            return False, "stress future unexpectedly resolved"
        except TimeoutError:
            worst = max(worst, time.monotonic() - start)
        except Exception as exc:
            client.close()
            return False, f"stress raised {exc!r}"
    time.sleep(WORKER_TIMEOUT_S + 0.5)
    leaked = sorted(client._resolvers)
    client.close()
    time.sleep(0.5)
    after = len(threading.enumerate())
    if leaked:
        return False, f"stress leaked resolvers {leaked}"
    if worst >= FAIL_FAST_S:
        return False, f"stress fail-fast violated worst={worst:.2f}s"
    if after > before + 2:
        return False, f"thread count grew {before}->{after}"
    return True, f"20 dead-port requests worst={worst:.2f}s resolvers=empty threads {before}->{after}"


CELLS: tuple[tuple[str, object], ...] = (
    ("worker_killed_mid_transcription", _cell_worker_killed),
    ("corrupt_pack_download", _cell_corrupt_pack),
    ("pack_folder_deleted", _cell_pack_deleted),
    ("first_launch_no_internet", _cell_no_internet),
    ("stale_pack_after_update", _cell_stale_pack),
)


def _run_bounded(label: str, func: object, root: Path, iterations: int, timeout: float) -> tuple[bool, str]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(func, root, iterations)  # type: ignore[arg-type]
        try:
            return pending.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return False, f"{label} exceeded {timeout:.0f}s cell budget"
        except Exception as exc:
            return False, f"{label} raised {exc!r}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--cell-timeout", type=float, default=60.0)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be >= 1")
    base = args.root if args.root is not None else Path(tempfile.mkdtemp(prefix="pack_matrix_"))
    base.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, bool, str]] = []
    for label, func in CELLS:
        ok, evidence = _run_bounded(label, func, base, args.iterations, args.cell_timeout)
        results.append((label, ok, evidence))
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: {evidence}")
    if args.stress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(_stress_worker_abort, base)
            try:
                ok, evidence = pending.result(timeout=args.cell_timeout)
            except concurrent.futures.TimeoutError:
                ok, evidence = False, "stress burst exceeded cell budget"
            except Exception as exc:
                ok, evidence = False, f"stress burst raised {exc!r}"
        results.append(("worker_abort_stress_burst", ok, evidence))
        print(f"[{'PASS' if ok else 'FAIL'}] worker_abort_stress_burst: {evidence}")
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"matrix: {passed}/{len(results)} cells passed (iterations={args.iterations} root={base})")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
