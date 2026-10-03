"""Unit coverage for ``scripts/verify_frozen_slim_live.py`` (ADR-0024 host gate).

The gate itself needs a frozen exe + a real worker, so what is tested here is
everything that is deterministic offline: the minimal-pack writer must satisfy
the product's own ``offline_pack_exists`` check (that is what opens the
worker-path gate), the log scanners must find the C-LOG-2 lines and reject a
completion line without a duration suffix, and the CLI must refuse to run
without an expectation.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_frozen_slim_live.py"


def _load():
    spec = importlib.util.spec_from_file_location("_vt_frozen_slim_gate", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_minimal_pack_is_accepted_by_the_products_own_presence_check(tmp_path):
    """The gate opens only if the real ``offline_pack_exists`` accepts the pack."""
    from voice_typer.server.service import offline_pack

    module = _load()
    root = tmp_path / "runtime-pack"
    version = "0.0.0-gate"
    module._write_minimal_pack(root, version)

    assert offline_pack.offline_pack_exists(version, root=root) is True
    assert (root / version / "pack-manifest.json").is_file()


def test_minimal_pack_manifest_matches_the_offline_pack_schema(tmp_path):
    from voice_typer.server.service.offline_pack.core import load_offline_pack_manifest

    module = _load()
    root = tmp_path / "runtime-pack"
    version = "1.2.3-gate"
    pack_dir = module._write_minimal_pack(root, version)

    manifest = load_offline_pack_manifest(pack_dir / "pack-manifest.json")
    assert manifest is not None, "the gate's manifest must parse under the real schema"
    assert manifest["version"] == version
    assert manifest["min_proto_version"] == 1


def test_pack_missing_a_declared_file_fails_closed(tmp_path):
    """``offline_pack_exists`` is the CHEAP presence check: manifest + files present.

    Integrity is enforced separately by ``_verify_manifest_files`` at install
    time (§8.10 keeps the launch-time check cheap), so the gate must not
    depend on hashing at startup.
    """
    from voice_typer.server.service import offline_pack

    module = _load()
    root = tmp_path / "runtime-pack"
    version = "2.0.0-gate"
    pack_dir = module._write_minimal_pack(root, version)
    (pack_dir / "pack-verification-marker.txt").unlink()

    assert offline_pack.offline_pack_exists(version, root=root) is False


def test_install_time_hash_verification_is_the_integrity_boundary(tmp_path):
    """A wrong per-file hash IS caught, by the install-time verifier."""
    from voice_typer.server.service.offline_pack.core import _verify_manifest_files, load_offline_pack_manifest

    module = _load()
    root = tmp_path / "runtime-pack"
    version = "2.1.0-gate"
    pack_dir = module._write_minimal_pack(root, version)
    manifest_path = pack_dir / "pack-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    parsed = load_offline_pack_manifest(manifest_path)
    assert parsed is not None
    assert _verify_manifest_files(pack_dir, parsed, version=version) is False


def test_scan_log_finds_vad_and_worker_markers(tmp_path):
    module = _load()
    log = tmp_path / "lausu.log"
    # NOTE the ``***``: security.redaction.redact_api_keys rewrites the token
    # ``transcribe_offline_result`` to ``***`` in the real log, so the worker
    # marker matches the stable ``(len=N chars)`` shape, not the command name.
    log.write_text(
        "\n".join(
            [
                "2026-10-03  12:00:00  INFO  Starting",
                "2026-10-03  12:00:05  INFO  [VAD] Silero VAD model loaded from local ONNX, preloaded + warmed 0.1s",
                "2026-10-03  12:00:09  INFO  [WORKER] *** (len=101 chars) 25.1s",
            ]
        ),
        encoding="utf-8",
    )
    assert len(module._scan_log(log, module._VAD_MARKER)) == 1
    assert len(module._scan_log_re(log, module._WORKER_MARKER_RE)) == 1


def test_worker_marker_regex_survives_the_redacted_command_name(tmp_path):
    """The regex must NOT require the redacted ``transcribe_offline_result``."""
    module = _load()
    log = tmp_path / "lausu.log"
    log.write_text("2026-10-03  12:00:09  INFO  [WORKER] *** (len=0 chars) 5.0s\n", encoding="utf-8")
    assert module._scan_log_re(log, module._WORKER_MARKER_RE)
    log.write_text("2026-10-03  12:00:09  INFO  [WORKER] offline transcription complete 2.3s\n", encoding="utf-8")
    assert not module._scan_log_re(log, module._WORKER_MARKER_RE)


def test_scan_log_returns_empty_for_missing_file(tmp_path):
    module = _load()
    assert module._scan_log(tmp_path / "absent.log", module._VAD_MARKER) == []


def test_duration_suffix_regex_accepts_seconds_and_minutes():
    module = _load()
    assert module._DURATION_RE.search("[WORKER] offline transcription complete 2.3s")
    assert module._DURATION_RE.search("[WORKER] offline transcription complete 1m 2.3s")
    # C-LOG-2: the suffix carries its own single leading space; nothing is glued.
    assert not module._DURATION_RE.search("[WORKER] offline transcription complete took=2.3s")
    assert not module._DURATION_RE.search("[WORKER] offline transcription complete 2.3 seconds")


def test_cli_requires_an_expectation():
    module = _load()
    with pytest.raises(SystemExit):
        module.main(["--sidecar-exe", "x.exe", "--audio", "a.wav", "--worker-cmd"])


def test_cli_refuses_to_build_a_scratch_tree_without_expectation(tmp_path):
    """Guard against a half-provisioned run: no expectation, no directories."""
    module = _load()
    scratch = Path.home() / "frozen-gate-test-guard"
    assert not scratch.exists()
    with pytest.raises(SystemExit):
        module.main(["--sidecar-exe", "x.exe", "--audio", "a.wav", "--worker-cmd"])
    assert not scratch.exists()
