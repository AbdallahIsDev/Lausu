"""Structural pins for the Part B Windows CI wiring (round 10).

Guards fetch-before-freeze/build, hash-locked freeze installs, the single
ENFORCE_NO_GPL_DLLS soft switch, and the unsigned signing path — without
weakening the existing signing pins in ``tests/tauri/mig18``.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "tauri-windows-build.yml"
CALLER = ROOT / ".github" / "workflows" / "tauri-build.yml"
GATE_SCRIPT = ROOT / "scripts" / "verify_windows_bundle.py"
SELFCHECK = ROOT / "voice_typer" / "server" / "media_ingest" / "selfcheck.py"
FETCH_SCRIPT = ROOT / "scripts" / "build" / "fetch_ffmpeg_lgpl_win64.sh"


def _text(path: Path) -> str:
    assert path.is_file(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def _workflow() -> dict:
    return yaml.safe_load(_text(WORKFLOW))


def _steps(job: dict) -> list[dict]:
    return job["steps"]


def test_workflow_parses_as_yaml() -> None:
    data = _workflow()
    assert "jobs" in data and isinstance(data["jobs"], dict)
    for job_name in ("build-sidecar-exe", "build-worker-exe", "tauri-windows-build"):
        assert job_name in data["jobs"], f"missing job {job_name}"
        assert data["jobs"][job_name]["strategy"]["matrix"]["include"][0]["runner"] == "windows-2022"


def test_fetch_runs_in_all_three_windows_legs_before_freeze_and_build() -> None:
    text = _text(WORKFLOW)
    assert "bash scripts/build/fetch_ffmpeg_lgpl_win64.sh" in text
    assert FETCH_SCRIPT.is_file()
    jobs = _workflow()["jobs"]
    for job_name in ("build-sidecar-exe", "build-worker-exe", "tauri-windows-build"):
        steps = _steps(jobs[job_name])
        fetch_idx = [
            i for i, s in enumerate(steps)
            if "fetch_ffmpeg_lgpl_win64.sh" in str(s.get("run", ""))
        ]
        assert len(fetch_idx) == 1, f"{job_name}: expected exactly one fetch step"
        i = fetch_idx[0]
        # Must precede any freeze / cargo tauri build in the same job.
        later = "\n".join(str(s.get("run", "")) + str(s.get("name", "")) for s in steps[i + 1:])
        if job_name == "tauri-windows-build":
            assert "cargo tauri build" in later, "fetch must precede cargo tauri build"
        else:
            assert "nuitka" in later.lower(), f"fetch must precede the Nuitka freeze in {job_name}"


def test_freeze_pins_hash_locked_requirements_twice() -> None:
    text = _text(WORKFLOW)
    assert text.count("pip install --no-warn-script-location --require-hashes -r requirements-lock.txt") == 2
    assert text.count('pip install --no-warn-script-location --no-deps -e ".[dev,test]"') == 2
    # No lock hacks / baseline inflation.
    for forbidden in ("--ignore-vuln", "pip-audit", "continue-on-error: true\n        run: pip"):
        assert forbidden not in text, f"forbidden gate edit: {forbidden}"


def test_freeze_evidence_steps_and_artifacts() -> None:
    text = _text(WORKFLOW)
    assert text.count("name: Record PYBS version + pip freeze (freeze env evidence)") == 2
    assert text.count("name: Upload freeze env evidence") == 2
    assert text.count("name: windows-pybs-freeze-${{ matrix.arch }}") == 2
    assert "pip freeze" in text


def test_single_gpl_soft_switch_and_gate_step() -> None:
    text = _text(WORKFLOW)
    jobs = _workflow()["jobs"]
    steps = _steps(jobs["tauri-windows-build"])
    gate = [s for s in steps if s.get("name", "").startswith("Post-build verification gate")]
    assert len(gate) == 1, "exactly one post-build verification gate step"
    step = gate[0]
    assert step["env"]["ENFORCE_NO_GPL_DLLS"] == "${{ vars.ENFORCE_NO_GPL_DLLS || '0' }}"
    assert "scripts/verify_windows_bundle.py" in step["run"]
    assert "--summary" in step["run"] and "$GITHUB_STEP_SUMMARY" in step["run"]
    # Single explicit switch: no second GPL-related toggle, no added soft gates.
    assert text.count("ENFORCE_NO_GPL_DLLS") >= 2
    assert "continue-on-error" not in step, "verification gate must be hard (except the switch)"
    assert "|| true" not in step["run"]


def test_post_build_gate_runs_after_artifact_uploads_and_still_fails_job() -> None:
    steps = _steps(_workflow()["jobs"]["tauri-windows-build"])
    names = [str(s.get("name", "")) for s in steps]
    gate_idx = [i for i, n in enumerate(names) if n.startswith("Post-build verification gate")]
    assert len(gate_idx) == 1, "exactly one post-build verification gate step"
    g = gate_idx[0]

    # The installer / SHA256SUMS / notices evidence must already be uploaded
    # before the gate renders its verdict.
    for upload in (
        "Upload NSIS installer artifact",
        "Upload MSI installer artifact",
        "Upload sidecar + native listener",
        "Upload checksums",
        "Upload third-party notices",
    ):
        assert upload in names, f"missing expected upload step {upload!r}"
        assert names.index(upload) < g, (
            f"{upload!r} must run BEFORE the post-build verification gate"
        )

    # The gate still fails the job: no soft-fail knob, strict bash, and the
    # verifier's exit code survives the tee pipeline via pipefail.
    gate = steps[g]
    assert "continue-on-error" not in gate, "gate must not be softened"
    run = gate["run"]
    assert "set -euo pipefail" in run
    assert "2>&1 | tee gate-output.txt" in run
    assert "|| true" not in run

    # always(): the gate console output ships even when the gate fails.
    uploads = [
        s for s in steps
        if str(s.get("with", {}).get("name", "")) == "Lausu-Windows-Gate-Output"
    ]
    assert len(uploads) == 1, "exactly one gate-output artifact upload"
    up = uploads[0]
    assert str(up.get("if", "")).strip() == "always()"
    assert up.get("uses") == "actions/upload-artifact@v6"
    assert up["with"]["path"] == "gate-output.txt"
    assert "continue-on-error" not in up
    assert names.index(str(up.get("name"))) > g


def test_no_new_soft_gates_or_relaxed_existing_gates() -> None:
    text = _text(WORKFLOW)
    # The only pre-existing continue-on-error is the informational slim size
    # gate. No new ones, no new '|| true' / --ignore-vuln / baseline inflation.
    # Baseline 2: the pre-existing informational slim-core size gate's YAML
    # key AND its warning string. No new soft gates added in Part B.
    assert text.count("continue-on-error: true") == 2
    assert text.count("continue-on-error:") == 2
    assert text.count("|| true") == 0
    assert "--ignore-vuln" not in text


def test_unsigned_path_never_requires_signing_secrets() -> None:
    jobs = _workflow()["jobs"]
    steps = _steps(jobs["tauri-windows-build"])
    for step in steps:
        name = str(step.get("name", ""))
        cond = str(step.get("if", ""))
        if "Sign" in name and "optional" in name:
            assert "env.SIGN_ENABLED == 'true'" in cond, (
                f"signing step {name!r} must be gated on SIGN_ENABLED"
            )
            assert "env.WIN_CSC_LINK != ''" in cond, (
                f"signing step {name!r} must require non-empty CSC_LINK"
            )
    # Signed config is only referenced behind the SIGN_ENABLED branch.
    build = next(s for s in steps if s.get("name", "").startswith("Build the Tauri app"))
    assert "if ($env:SIGN_ENABLED -eq 'true')" in build["run"]
    assert "--config', 'tauri.windows-signed.json'" in build["run"]
    # Fetch step must not reference signing secrets.
    fetch = next(s for s in steps if "fetch_ffmpeg_lgpl_win64.sh" in str(s.get("run", "")))
    assert "WIN_CSC" not in str(fetch.get("env", {})) and "WIN_CSC" not in fetch["run"]


def test_notices_and_checksums_uploaded() -> None:
    text = _text(WORKFLOW)
    assert "name: Lausu-Windows-SHA256SUMS" in text
    assert "name: Lausu-Windows-Third-Party-Notices" in text
    assert "docs/THIRD_PARTY_NOTICES.md" in text


def test_gate_script_self_test_and_helpers() -> None:
    import importlib.util

    assert GATE_SCRIPT.is_file()
    spec = importlib.util.spec_from_file_location("_verify_windows_bundle", GATE_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.self_test() == 0
    # GPL scan detects all three explicit tokens, nothing else.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        dll = Path(tmp) / "fake.dll"
        dll.write_bytes(b"libx265.dll avcodec-61.dll")
        rows = {token for token, _, _ in mod.gpl_dll_table([dll])}
        assert {"libx265", "avcodec"} <= rows
        assert "libx264" not in rows
    # Default is a WARNING (soft) switch, not a hard gate: self-test must pass.
    assert mod.main(["--self-test"]) == 0


def test_sidecar_selfcheck_is_inert_on_normal_startup() -> None:
    import importlib.util

    assert SELFCHECK.is_file()
    spec = importlib.util.spec_from_file_location("_vt_selfcheck", SELFCHECK)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.maybe_run_self_check([]) is False
    assert mod.maybe_run_self_check(["--ws", "--debug"]) is False
    entry = _text(ROOT / "voice_typer" / "server" / "ipc" / "entrypoint.py")
    assert "maybe_run_self_check(sys.argv[1:])" in entry
    # parse_ipc_args return contract untouched.
    assert re.search(r"def parse_ipc_args\(\) -> tuple\[int \| None, bool\]:", entry)


def test_caller_unchanged_signing_contract() -> None:
    caller = _text(CALLER)
    assert "uses: ./.github/workflows/tauri-windows-build.yml" in caller
    assert "sign: ${{ fromJSON(github.event.inputs.sign) }}" in caller
