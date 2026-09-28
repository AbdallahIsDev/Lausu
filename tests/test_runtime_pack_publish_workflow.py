"""Contract pins for ``.github/workflows/runtime-pack-publish.yml`` (ADR-0024 Step 8).

The workflow is NEW and additive (C-CI-13): it must never touch the
``tauri-*.yml`` family (C-CI-2), must be manual-``workflow_dispatch`` only
(C-CI-4), must keep the 240-minute Nuitka budget (C-CI-3), must pin Node-24
actions (C-CI-5), must keep ``CLCACHE_DISABLE`` at job level (C-CI-12), and
must emit the exact §11.9 artifact names (``scripts/build/artifact_names.py``).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "runtime-pack-publish.yml"
TAURI_WORKFLOWS = (
    "tauri-build.yml",
    "tauri-windows-build.yml",
    "tauri-macos-build.yml",
    "tauri-linux-build.yml",
    "tauri-windows-arm-validation.yml",
)

# C-CI-5 / tests/test_workflow_yaml_valid.py: the canonical pin map.
PINNED_ACTION_VERSIONS: dict[str, str] = {
    "actions/checkout": "v5",
    "actions/setup-python": "v7",
    "actions/upload-artifact": "v6",
    "actions/download-artifact": "v6",
    "astral-sh/setup-uv": "v7",
}


@pytest.fixture(scope="module")
def workflow_text() -> str:
    assert WORKFLOW_PATH.is_file(), (
        "runtime-pack-publish.yml is missing — ADR-0024 Step 8 ships this workflow "
        f"at {WORKFLOW_PATH}"
    )
    return WORKFLOW_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def workflow_doc(workflow_text: str) -> dict:
    parsed = yaml.safe_load(workflow_text)
    assert isinstance(parsed, dict)
    return parsed


class TestTriggerContract:
    """C-CI-4: manual dispatch only, no push/PR automation."""

    def test_only_workflow_dispatch_trigger(self, workflow_doc: dict):
        triggers = workflow_doc.get("on") or workflow_doc.get(True)
        assert triggers is not None, "workflow has no `on:` block"
        if isinstance(triggers, str):
            assert triggers == "workflow_dispatch"
            return
        assert isinstance(triggers, dict), f"`on:` must be a mapping, got {type(triggers).__name__}"
        assert set(triggers) == {"workflow_dispatch"}, (
            "runtime-pack-publish.yml must be workflow_dispatch-only "
            f"(C-CI-4: no push/PR triggers until Phase 0-W passes); got triggers {sorted(triggers)}"
        )

    def test_no_push_or_pull_request_anywhere(self, workflow_text: str):
        for forbidden in ("pull_request:", "push:", "schedule:", "workflow_call:"):
            assert forbidden not in workflow_text, (
                f"{forbidden} must not appear in runtime-pack-publish.yml (C-CI-4)"
            )

    def test_dispatch_inputs_expose_pack_version_and_tag(self, workflow_doc: dict):
        triggers = workflow_doc.get("on") or workflow_doc.get(True)
        inputs = triggers["workflow_dispatch"].get("inputs", {})
        assert "pack_version" in inputs, "pack_version input is required to name the pack"
        assert "tag" in inputs, "tag input is required to address the GitHub release"
        assert "primary_triple" in inputs, "primary_triple selects the pack-manifest.json subject"


class TestBudgetAndEnvContract:
    """C-CI-3 (timeout) + C-CI-12 (CLCACHE_DISABLE job-level)."""

    def _build_job(self, workflow_doc: dict) -> dict:
        jobs = workflow_doc["jobs"]
        assert "build-pack" in jobs, "build-pack job missing"
        return jobs["build-pack"]

    def test_build_job_timeout_is_at_least_240(self, workflow_doc: dict):
        job = self._build_job(workflow_doc)
        timeout = job.get("timeout-minutes")
        assert isinstance(timeout, int), "build-pack must set timeout-minutes explicitly"
        assert timeout >= 240, (
            f"C-CI-3: build-pack timeout-minutes must be >= 240 (Nuitka freeze is "
            f"C-compilation-bound); got {timeout}"
        )

    def test_publish_job_has_explicit_timeout(self, workflow_doc: dict):
        job = workflow_doc["jobs"]["publish"]
        assert isinstance(job.get("timeout-minutes"), int)

    def test_clcache_disable_is_job_level_on_build(self, workflow_doc: dict):
        job = self._build_job(workflow_doc)
        env = job.get("env", {})
        assert env.get("CLCACHE_DISABLE") == "1", (
            "C-CI-12: CLCACHE_DISABLE must be a job-level env '1' on the Nuitka "
            "build job (step-level never reaches the C-compiler subprocess)"
        )

    def test_no_step_level_only_clcache(self, workflow_text: str):
        # The job-level pin is the contract; a step-level echo alone would not
        # satisfy C-CI-12. This asserts the job-level form is present in text.
        assert re.search(r"CLCACHE_DISABLE:\s*[\"']1[\"']", workflow_text), (
            "C-CI-12: CLCACHE_DISABLE: \"1\" must appear as a job-level env entry"
        )


class TestActionPinContract:
    """C-CI-5: Node-24-pinned actions only."""

    def test_actions_match_pin_map(self, workflow_text: str):
        uses = re.findall(r"uses:\s*([A-Za-z0-9_.\-/]+)@([A-Za-z0-9_.\-/]+)", workflow_text)
        assert uses, "workflow must use at least one action"
        violations = []
        for action, ref in uses:
            if action not in PINNED_ACTION_VERSIONS:
                violations.append(f"unpinned/unknown action: {action}@{ref}")
                continue
            if ref != PINNED_ACTION_VERSIONS[action]:
                violations.append(f"{action}@{ref} (expected @{PINNED_ACTION_VERSIONS[action]})")
        assert not violations, "C-CI-5 pin violations:\n" + "\n".join(violations)

    def test_nuitka_pin_is_2810(self, workflow_text: str):
        """C-CI-6: never ship a worker freeze on a different Nuitka."""
        assert "nuitka==2.8.10" in workflow_text, (
            "C-CI-6 / NU-105: the worker freeze must pin nuitka==2.8.10"
        )
        assert not re.search(r"nuitka==(?!2\.8\.10)\d", workflow_text), (
            "C-CI-6: a second nuitka== pin must not appear alongside 2.8.10"
        )


class TestArtifactNamingContract:
    """plan §11.9 / C-CI-13: canonical names, derived from artifact_names.py."""

    def test_zip_name_comes_from_artifact_names_helper(self, workflow_text: str):
        assert "scripts/build/artifact_names.py" in workflow_text, (
            "the zip name must be resolved via scripts/build/artifact_names.py "
            "(single source of truth for §11.9 naming)"
        )
        assert "--runtime-pack" in workflow_text
        assert "--pack-version" in workflow_text

    def test_manifest_filename_is_unversioned(self, workflow_text: str):
        assert "pack-manifest.json" in workflow_text, "pack-manifest.json must be written/uploaded"
        # The §11.9 manifest name is NOT versioned and NOT per-triple.
        assert not re.search(r"pack-manifest-.*\.json", workflow_text), (
            "pack-manifest.json must not be versioned or triple-suffixed"
        )

    def test_downloader_alias_is_emitted(self, workflow_text: str):
        """update_check.py builds ``pack-<version>.zip``; the alias must exist."""
        assert "pack-${PACK_VERSION}.zip" in workflow_text or 'pack-" + "$PACK_VERSION' in workflow_text, (
            "the publish job must emit pack-<pack_version>.zip — the asset name "
            "update_check.py constructs from the manifest version"
        )

    def test_publisher_invoked_with_pack_assets(self, workflow_text: str):
        assert "scripts/release/publish_pack_release.py" in workflow_text
        assert "--pack-onefile" in workflow_text
        assert "--pack-manifest" in workflow_text

    def test_manifest_builder_invoked(self, workflow_text: str):
        assert "scripts/release/build_pack_manifest.py" in workflow_text


class TestTauriWorkflowsUntouched:
    """C-CI-2: this step must be purely additive."""

    @pytest.mark.parametrize("name", TAURI_WORKFLOWS)
    def test_tauri_workflow_named_only_in_comments(self, workflow_text: str, name: str):
        """A tauri-*.yml filename may appear ONLY on comment lines.

        Any non-comment occurrence would mean the workflow reads/writes that
        file as part of its run (C-CI-2 forbids operating on that family).
        """
        offenders = []
        for lineno, line in enumerate(workflow_text.splitlines(), 1):
            if name not in line:
                continue
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            offenders.append(f"  line {lineno}: {line.strip()}")
        assert not offenders, (
            f"runtime-pack-publish.yml must not reference {name} outside comments (C-CI-2):\n"
            + "\n".join(offenders)
        )


class TestSigningContract:
    """C-CI-11: signing stays in CI; sign=true + missing secrets hard-fails."""

    def test_windows_sign_gate_hard_fails_on_missing_secrets(self, workflow_text: str):
        assert "Fail fast — sign=true but Windows signing secrets missing" in workflow_text
        assert "WIN_CSC_LINK" in workflow_text
        assert "WIN_CSC_KEY_PASSWORD" in workflow_text

    def test_worker_exe_is_a_signing_target(self, workflow_text: str):
        assert "signtool sign" in workflow_text, "the Windows worker must be Authenticode-signed"
        assert "lausu-worker-" in workflow_text

    def test_signing_description_comes_from_branding(self, workflow_text: str):
        """C-BRAND-1: no hardcoded app-name in the Authenticode description."""
        assert "branding.py" in workflow_text and "APP_NAME" in workflow_text

    def test_linux_worker_is_unsigned_by_design(self, workflow_text: str):
        assert "UNSIGNED by design" in workflow_text, (
            "the Linux worker is intentionally unsigned (ADR-0020 §13.3) — keep the comment"
        )
