"""Proof-of-absence: the internal plugins and their app seam never ship.

Plan: docs/plan-internal-plugin-google-stt.md. Static source/JSON
assertions only (no process launches), wired into the same drift spirit
as the C-CI-7 gates.

Two directions are pinned:
1. ``tools/internal-plugins`` (the in-development plugin workspace) is
   absent from every packaging input: Nuitka scripts, tauri.conf.json.
2. The product-side seam ``voice_typer/server/internal_plugin_hook.py``
   is inert when the plugin gate is closed, so the shipped app behaves
   as before.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGINS_DIR = _REPO_ROOT / "tools" / "internal-plugins"
_TAURI_CONF = _REPO_ROOT / "src-tauri" / "tauri.conf.json"
_HOOK = _REPO_ROOT / "voice_typer" / "server" / "internal_plugin_hook.py"
_APP_PY = _REPO_ROOT / "voice_typer" / "server" / "app.py"

# Any packaging reference to the plugin workspace, path or dotted form.
_PLUGINS_REF = re.compile(r"tools[/\\]internal[-_]plugins|tools\.internal_plugins")
# Tokens that must not appear anywhere in the shipped bundle description.
_BUNDLE_TOKENS = ("internal-plugin", "internal_plugin", "google_stt", "gemini_stt")


def _nuitka_scripts() -> list[Path]:
    build_dir = _REPO_ROOT / "scripts" / "build"
    return sorted(build_dir.glob("build_*.sh"))


class TestInternalPluginToolsAbsentFromPackaging:
    def test_no_nuitka_script_includes_plugin_tools(self) -> None:
        offenders = [
            str(p.relative_to(_REPO_ROOT))
            for p in _nuitka_scripts()
            if _PLUGINS_REF.search(p.read_text(encoding="utf-8", errors="replace"))
        ]
        assert offenders == [], f"plugin tools referenced by Nuitka scripts: {offenders}"

    def test_tauri_conf_has_no_plugin_resources(self) -> None:
        text = _TAURI_CONF.read_text(encoding="utf-8").lower()
        hits = [tok for tok in _BUNDLE_TOKENS if tok in text]
        assert hits == [], f"tauri.conf.json must not reference plugin tools: {hits}"

    def test_tauri_conf_external_bin_and_resources_are_plugin_free(self) -> None:
        conf = json.loads(_TAURI_CONF.read_text(encoding="utf-8"))
        blob = json.dumps(conf.get("bundle", {})).lower()
        hits = [tok for tok in _BUNDLE_TOKENS if tok in blob]
        assert hits == [], f"bundle must not reference plugin tools: {hits}"

    def test_gitignore_covers_plugin_artifacts(self) -> None:
        gi = (_PLUGINS_DIR / ".gitignore").read_text(encoding="utf-8")
        for entry in ("PLUGINS_ENABLED", "config.json", "debug/", "last_error.json"):
            assert entry in gi, f"{entry} must stay gitignored"


class TestPluginSeamIsInertWhenClosed:
    def test_hook_module_exposes_only_gate_and_install(self) -> None:
        text = _HOOK.read_text(encoding="utf-8")
        for name in ("def plugins_enabled", "def install"):
            assert name in text

    def test_hook_checks_env_flag_file_marker_and_frozen(self) -> None:
        text = _HOOK.read_text(encoding="utf-8")
        assert "VOICE_TYPER_INTERNAL_PLUGINS" in text
        assert "PLUGINS_ENABLED" in text
        assert "frozen" in text

    def test_app_constructor_calls_the_gated_hook_only(self) -> None:
        text = _APP_PY.read_text(encoding="utf-8")
        assert "internal_plugin_hook.install(self)" in text
        # The seam must not be duplicated across the constructor.
        assert text.count("internal_plugin_hook.install") == 1

    def test_hook_install_is_noop_outside_the_gate(self) -> None:
        import os
        import sys

        sys.path.insert(0, str(_REPO_ROOT))
        prefix = "voice_typer.server.internal_plugin_hook"
        for mod in [m for m in list(sys.modules) if m.startswith(prefix)]:
            sys.modules.pop(mod, None)
        from voice_typer.server import internal_plugin_hook

        prev = os.environ.pop("VOICE_TYPER_INTERNAL_PLUGINS", None)
        try:
            assert internal_plugin_hook.plugins_enabled() is False
            assert internal_plugin_hook.install(object()) is False
        finally:
            if prev is not None:
                os.environ["VOICE_TYPER_INTERNAL_PLUGINS"] = prev


class TestInternalPluginToolsNotInMainRepo:
    """The plugin workspace must live outside the main repo's history.

    Backed up by its own nested repository
    (tools/internal-plugins/backup.ps1) to a PRIVATE remote, never this
    one. These two assertions are the CI tripwire for a plugin leak: the
    folder must be ignored by the parent repo AND have zero tracked files
    in it.
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

    def test_root_gitignore_covers_plugin_tools(self) -> None:
        # --no-index: git deliberately reports TRACKED paths as
        # "not ignored" regardless of the pattern; this asserts the
        # RULE exists (the tracked-vs-ignored state is test 2).
        code, out = self._git(
            "check-ignore", "--no-index", "-q", "tools/internal-plugins"
        )
        assert code == 0, (
            "tools/internal-plugins must be listed in the root .gitignore "
            f"(git check-ignore said: {out or 'not ignored'})"
        )

    def test_no_tracked_files_under_plugin_tools(self) -> None:
        code, out = self._git("ls-files", "tools/internal-plugins")
        assert code == 0, f"git ls-files failed: {out}"
        tracked = [line for line in out.splitlines() if line.strip()]
        assert tracked == [], (
            "Plugin files are tracked in the main repo. Run:\n"
            "  git rm -r --cached tools/internal-plugins\n"
            "  git commit -m 'chore: untrack internal plugin workspace'\n"
            f"Tracked: {tracked}"
        )


@pytest.mark.parametrize("js_file", ["run.js", "playwright_runner.js"])
def test_plugin_js_files_stay_inside_the_plugin_workspace(js_file: str) -> None:
    target = _PLUGINS_DIR / "google_stt" / js_file
    assert target.exists(), f"{js_file} must live under tools/internal-plugins/google_stt"

