"""SP-1 slice A: slim-has-no-worker + full-keeps-worker contract.

Slim installer (host + sidecar only) vs full (sidecar + worker):
- the slim ``-slim.conf.json`` narrows ``externalBin`` to the sidecar;
- the base ``tauri.conf.json`` + full per-arch conf keep the worker;
- the Windows workflow's slim leg skips worker download/sign/bundle and
  asserts the staged bundle contains no worker binary.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_TAURI = PROJECT_ROOT / "src-tauri"
SLIM_CONF = SRC_TAURI / "tauri.windows-x86_64-slim.conf.json"
BASE_CONF = SRC_TAURI / "tauri.conf.json"
STUB_SCRIPT = PROJECT_ROOT / "scripts" / "gen_tauri_icons_stub.py"
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "tauri-windows-build.yml"


def _stub_module():
    spec = importlib.util.spec_from_file_location("_vt_slim_stub", STUB_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _tauri_job() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["tauri-windows-build"]


class TestSlimConfNarrowsWorkerOut:
    def test_slim_external_bin_is_subset_of_base_without_worker(self) -> None:
        slim = json.loads(SLIM_CONF.read_text(encoding="utf-8"))["bundle"]["externalBin"]
        base = json.loads(BASE_CONF.read_text(encoding="utf-8"))["bundle"]["externalBin"]
        assert set(slim) < set(base), "slim externalBin must strictly narrow the base list"
        assert not any("worker" in entry for entry in slim), "slim must not reference the worker"
        assert any("worker" in entry for entry in base), "base (full) must keep the worker"


class TestFullKeepsWorker:
    def test_base_conf_keeps_both_external_bin_entries(self) -> None:
        base = json.loads(BASE_CONF.read_text(encoding="utf-8"))["bundle"]["externalBin"]
        assert base == ["bin/python-sidecar", "bin/lausu-worker"]

    def test_stub_full_set_still_covers_worker(self) -> None:
        stub = _stub_module()
        assert ("worker", stub.WORKER_BASENAME) in stub._EXTERNAL_BIN_STUBS
        assert any(kind == "worker" for _, _, kind in stub._all_stub_specs())

    def test_worker_freeze_job_still_exists(self) -> None:
        jobs = yaml.safe_load(_workflow_text())["jobs"]
        assert "build-worker-exe" in jobs, "the worker freeze job stays for the pack pipeline"


class TestSlimStubSet:
    def test_slim_specs_exclude_worker(self) -> None:
        stub = _stub_module()
        assert not any(kind == "worker" for _, _, kind in stub._slim_stub_specs())
        assert any(kind == "sidecar" for _, _, kind in stub._slim_stub_specs())
        assert any(kind == "native" for _, _, kind in stub._slim_stub_specs())

    def test_slim_plus_worker_partitions_full_set(self) -> None:
        stub = _stub_module()
        assert set(stub._slim_stub_specs()) | set(stub._worker_stub_specs()) == set(stub._all_stub_specs())
        assert set(stub._slim_stub_specs()) & set(stub._worker_stub_specs()) == set()

    def test_triple_lockstep_unaffected(self) -> None:
        stub = _stub_module()
        names = [
            p.name
            for p, _, kind in stub._slim_stub_specs()
            if kind == "sidecar" and "python-sidecar-" in p.name
        ]
        release = {
            name.split("python-sidecar-")[1].removesuffix(".exe")
            for name in names
            if "windows-gnu" not in name
        }
        assert release == set(stub.SIDECAR_TRIPLES)
        assert any("x86_64-pc-windows-gnu" in name for name in names), (
            "slim set must keep the GNU local-dev mirror (C-TDEV-1)"
        )


class TestSlimWorkflowLeg:
    def test_matrix_builds_slim_config(self) -> None:
        job = _tauri_job()
        configs = [leg["tauri_config"] for leg in job["strategy"]["matrix"]["include"]]
        assert "tauri.windows-x86_64-slim.conf.json" in configs

    def test_no_worker_download_step(self) -> None:
        names = [s.get("name", "") for s in _tauri_job()["steps"]]
        assert not any("worker" in name.lower() and "download" in name.lower() for name in names)
        assert "Download sidecar binary" in names

    def test_no_worker_sign_block(self) -> None:
        assert "Signing worker exe" not in _workflow_text()

    def test_slim_assertion_step_present_next_to_bundle_assertion(self) -> None:
        text = _workflow_text()
        bundle_pos = text.find("Post-build assertion — bundle has no non-Windows binaries")
        slim_pos = text.find("Post-build assertion — slim bundle has no worker binary")
        assert bundle_pos != -1 and slim_pos != -1
        assert slim_pos > bundle_pos, "slim assertion must sit next to (after) the bundle assertion"

    def test_worker_absent_from_slim_payload_steps(self) -> None:
        text = _workflow_text()
        upload_pos = text.find("name: Lausu-Windows-Sidecar-Binaries")
        checksums_pos = text.find("name: Generate SHA-256 checksums")
        slsa_pos = text.find("name: Attest build provenance (SLSA)")
        for step_name, pos in (
            ("sidecar-binaries upload", upload_pos),
            ("checksums", checksums_pos),
            ("slsa", slsa_pos),
        ):
            assert pos != -1, f"{step_name} step missing"
        for section in (
            text[upload_pos : upload_pos + 1200],
            text[checksums_pos : checksums_pos + 1500],
            text[slsa_pos : slsa_pos + 1200],
        ):
            assert "lausu-worker" not in section

    def test_timeout_gate_order_and_slsa_gate_kept(self) -> None:
        job = _tauri_job()
        assert job["timeout-minutes"] == 240
        names = [s.get("name", "") for s in job["steps"]]
        order = [
            "Verify version lockstep across layers (fail fast)",
            "Verify config drift guards (icons, identity, binaries) (fail fast)",
            "Generate Tauri binary stubs",
            "Verify bundle.icon icons are present + valid (fail fast)",
        ]
        positions = [next(i for i, n in enumerate(names) if n == want) for want in order]
        assert positions == sorted(positions), "C-CI-7 gate order must hold"
        slsa = next(s for s in job["steps"] if s.get("name", "") == "Attest build provenance (SLSA)")
        assert slsa.get("if") == "${{ github.event_name == 'workflow_dispatch' && env.SIGN_ENABLED == 'true' }}"

    def test_slim_size_gate_stays_informational(self) -> None:
        job = _tauri_job()
        gate = next(
            s
            for s in job["steps"]
            if s.get("name", "").startswith("Assert slim-core installer size <=")
        )
        assert gate.get("continue-on-error") is True
