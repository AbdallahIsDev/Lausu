"""Proof-of-absence: the owner tools and their app seam never ship.

Plan: docs/plan-owner-gemini-web-stt.md §4.4. Static source/JSON
assertions only (no process launches), wired into the same drift spirit
as the C-CI-7 gates.

Two directions are pinned:
1. ``tools/owner`` (the never-ship spike) is absent from every packaging
   input: Nuitka scripts, tauri.conf.json, CI artifacts.
2. The product-side seam ``voice_typer/server/owner_hook.py`` is inert
   when the owner gate is closed, so the shipped app behaves as before.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_OWNER_DIR = _REPO_ROOT / "tools" / "owner"
_TAURI_CONF = _REPO_ROOT / "src-tauri" / "tauri.conf.json"
_HOOK = _REPO_ROOT / "voice_typer" / "server" / "owner_hook.py"
_APP_PY = _REPO_ROOT / "voice_typer" / "server" / "app.py"

_OWNER_REF = re.compile(r"tools[/\\]owner|tools\.owner")
_OWNER_DIR_REF = re.compile(r"owner_dir|owner")


def _nuitka_scripts() -> list[Path]:
    build_dir = _REPO_ROOT / "scripts" / "build"
    return sorted(build_dir.glob("build_*.sh"))


class TestOwnerToolsAbsentFromPackaging:
    def test_no_nuitka_script_includes_owner_tools(self) -> None:
        offenders = [
            str(p.relative_to(_REPO_ROOT))
            for p in _nuitka_scripts()
            if _OWNER_REF.search(p.read_text(encoding="utf-8", errors="replace"))
        ]
        assert offenders == [], f"owner tools referenced by Nuitka scripts: {offenders}"

    def test_tauri_conf_has_no_owner_resources(self) -> None:
        text = _TAURI_CONF.read_text(encoding="utf-8")
        assert "owner" not in text.lower(), "tauri.conf.json must not reference owner tools"

    def test_tauri_conf_external_bin_and_resources_are_owner_free(self) -> None:
        conf = json.loads(_TAURI_CONF.read_text(encoding="utf-8"))
        bundle = conf.get("bundle", {})
        blob = json.dumps(bundle)
        assert "owner" not in blob.lower()

    def test_gitignore_covers_owner_artifacts(self) -> None:
        gi = (_OWNER_DIR / ".gitignore").read_text(encoding="utf-8")
        for entry in ("OWNER_ENABLED", "config.json", "debug/", "last_error.json"):
            assert entry in gi, f"{entry} must stay gitignored"


class TestOwnerSeamIsInertWhenClosed:
    def test_hook_module_exposes_only_gate_and_install(self) -> None:
        text = _HOOK.read_text(encoding="utf-8")
        for name in ("def owner_enabled", "def install"):
            assert name in text

    def test_hook_checks_env_flag_file_marker_and_frozen(self) -> None:
        text = _HOOK.read_text(encoding="utf-8")
        assert "VOICE_TYPER_OWNER_TOOLS" in text
        assert "OWNER_ENABLED" in text
        assert "frozen" in text

    def test_app_constructor_calls_the_gated_hook_only(self) -> None:
        text = _APP_PY.read_text(encoding="utf-8")
        assert "owner_hook.install(self)" in text
        # The seam must not be duplicated across the constructor.
        assert text.count("owner_hook.install") == 1

    def test_hook_install_is_noop_outside_the_gate(self) -> None:
        import os
        import sys

        sys.path.insert(0, str(_REPO_ROOT))
        for mod in [m for m in list(sys.modules) if m.startswith("voice_typer.server.owner_hook")]:
            sys.modules.pop(mod, None)
        from voice_typer.server import owner_hook

        prev = os.environ.pop("VOICE_TYPER_OWNER_TOOLS", None)
        try:
            assert owner_hook.owner_enabled() is False
            assert owner_hook.install(object()) is False
        finally:
            if prev is not None:
                os.environ["VOICE_TYPER_OWNER_TOOLS"] = prev


class TestOwnerToolsNotInMainRepo:
    """The plugin must live outside the main repo's history.

    Backed up by its own nested repository (tools/owner/backup.ps1) to a
    PRIVATE remote, never this one. These two assertions are the CI
    tripwire for the 8397fc480 leak: the folder must be ignored by the
    parent repo AND have zero tracked files in it.
    """

    def _git(self, *args: str) -> tuple[int, str]:
        import subprocess

        proc = subprocess.run(
            ["git", *args],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return proc.returncode, (proc.stdout + proc.stderr).strip()

    def test_root_gitignore_covers_owner_tools(self) -> None:
        # --no-index: git deliberately reports TRACKED paths as
        # "not ignored" regardless of the pattern; this asserts the
        # RULE exists (the tracked-vs-ignored state is test 2).
        code, out = self._git("check-ignore", "--no-index", "-q", "tools/owner")
        assert code == 0, (
            "tools/owner must be listed in the root .gitignore "
            f"(git check-ignore said: {out or 'not ignored'})"
        )

    def test_no_tracked_files_under_owner_tools(self) -> None:
        code, out = self._git("ls-files", "tools/owner")
        assert code == 0, f"git ls-files failed: {out}"
        tracked = [line for line in out.splitlines() if line.strip()]
        assert tracked == [], (
            "Owner-only files are tracked in the main repo. Run:\n"
            "  git rm -r --cached tools/owner\n"
            "  git commit -m 'chore: untrack owner plugin (private repo)'\n"
            f"Tracked: {tracked}"
        )


@pytest.mark.parametrize("js_file", ["run.js", "playwright_runner.js"])
def test_owner_js_files_stay_inside_tools_owner(js_file: str) -> None:
    target = _OWNER_DIR / "gemini_stt" / js_file
    assert target.exists(), f"{js_file} must live under tools/owner"
