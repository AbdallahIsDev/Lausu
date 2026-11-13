"""The internal plugin source ships bundled, but never active by default.

Plan: docs/plan-internal-plugin-google-stt.md. Three properties, all
greppable, no process launches:

1. Every sidecar freeze stages the plugin tree and embeds it as data, so a
   packaged install can seed a writable workspace on first unlock.
2. The staged copy carries source only: config, settings, debug output and
   the generated extension config never leave the machine that built it.
3. The product seam stays inert until developer mode is unlocked, so a
   normal install behaves exactly as before.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PLUGINS_DIR = _REPO_ROOT / "tools" / "internal_plugins"
_STAGER = _REPO_ROOT / "scripts" / "build" / "stage_internal_plugins.py"
_MANIFEST = _REPO_ROOT / "MANIFEST.in"
_TAURI_CONF = _REPO_ROOT / "src-tauri" / "tauri.conf.json"
_HOOK = _REPO_ROOT / "voice_typer" / "server" / "internal_plugin_hook.py"
_APP_PY = _REPO_ROOT / "voice_typer" / "server" / "app.py"
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "tauri-windows-build.yml"

_PLUGINS_REL = "tools/internal_plugins"
# Tokens that must not appear in the Tauri bundle description: the data rides
# inside the sidecar binary, not as a Tauri resource.
_BUNDLE_TOKENS = ("internal-plugin", "internal_plugin", "google_stt", "gemini_stt")


def _sidecar_scripts() -> list[Path]:
    return sorted((_REPO_ROOT / "scripts" / "build").glob("build_sidecar_*.sh"))


def _load_stager():
    spec = importlib.util.spec_from_file_location("stage_internal_plugins", _STAGER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPackagingInputsEmbedThePluginTree:
    def test_every_sidecar_script_stages_and_includes_it(self) -> None:
        for script in _sidecar_scripts():
            text = script.read_text(encoding="utf-8", errors="replace")
            assert "stage_internal_plugins.py" in text, f"{script.name} does not stage"
            assert "--include-data-dir=" in text, f"{script.name} does not embed data"
            assert _PLUGINS_REL in text, f"{script.name} does not embed the plugin tree"

    def test_windows_ci_workflow_stages_and_includes_it(self) -> None:
        text = _WORKFLOW.read_text(encoding="utf-8")
        assert "scripts/build/stage_internal_plugins.py" in text
        assert (f"--include-data-dir=build/internal_plugins_bundle/{_PLUGINS_REL}={_PLUGINS_REL}") in text

    def test_tauri_bundle_stays_plugin_free(self) -> None:
        """The bundled copy lives inside the sidecar, not in Tauri resources."""
        conf = json.loads(_TAURI_CONF.read_text(encoding="utf-8"))
        blob = json.dumps(conf.get("bundle", {})).lower()
        hits = [tok for tok in _BUNDLE_TOKENS if tok in blob]
        assert hits == [], f"bundle must not reference plugin tools: {hits}"

    def test_sdist_still_prunes_the_checkout_copy(self) -> None:
        text = _MANIFEST.read_text(encoding="utf-8")
        assert "prune tools" in text, "MANIFEST.in must keep the checkout copy out of the sdist"


@pytest.fixture(scope="class")
def staged_plugins(tmp_path_factory: pytest.TempPathFactory) -> Path:
    destination = tmp_path_factory.mktemp("plugins-stage") / _PLUGINS_REL
    _load_stager().stage(_PLUGINS_DIR, destination)
    return destination


class TestStageCarriesSourceOnly:
    """The staged tree is what a packaged install seeds from."""

    def test_source_files_are_present(self, staged_plugins: Path) -> None:
        for rel in (
            "google_stt/plugin.py",
            "google_stt/plugin.json",
            "google_stt/run.js",
            "anthropic_stt/plugin.py",
            "anthropic_stt/plugin.json",
            "anthropic_stt/chrome_profile.py",
        ):
            assert (staged_plugins / rel).is_file(), f"{rel} must be bundled"

    def test_runtime_state_never_ships(self, staged_plugins: Path) -> None:
        names = {path.name for path in staged_plugins.rglob("*")}
        for name in ("PLUGINS_ENABLED", "config.json", "settings.json", "last_error.json", "STOP"):
            assert name not in names, f"{name} is per-machine state and must not ship"
        assert "debug" not in names

    def test_generated_extension_config_never_ships(self, staged_plugins: Path) -> None:
        """The relay token is per-workspace; a build must not pin one."""
        assert not (staged_plugins / "anthropic_stt" / "extension" / "generated").exists()

    def test_caches_tests_and_verifiers_never_ship(self, staged_plugins: Path) -> None:
        files = [path.name for path in staged_plugins.rglob("*") if path.is_file()]
        assert not [name for name in files if name.endswith((".pyc", ".pyo"))]
        assert "app_test.py" not in files
        assert not [name for name in files if name.startswith("verify_")]
        assert not [name for name in files if name.startswith("test_")]


class TestPluginSeamIsInertWhileLocked:
    def test_hook_exposes_the_gate_install_and_teardown(self) -> None:
        text = _HOOK.read_text(encoding="utf-8")
        for name in ("def plugins_enabled", "def install", "def teardown"):
            assert name in text

    def test_hook_gate_reads_the_persisted_flag(self) -> None:
        text = _HOOK.read_text(encoding="utf-8")
        assert "developer_mode" in text
        assert "VOICE_TYPER_INTERNAL_PLUGINS" in text

    def test_app_constructor_calls_the_gated_hook_only(self) -> None:
        text = _APP_PY.read_text(encoding="utf-8")
        assert "internal_plugin_hook.install(self)" in text
        # The seam must not be duplicated across the constructor.
        assert text.count("internal_plugin_hook.install") == 1

    def test_hook_install_is_noop_outside_the_gate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        sys.path.insert(0, str(_REPO_ROOT))
        prefix = "voice_typer.server.internal_plugin_hook"
        for mod in [m for m in list(sys.modules) if m.startswith(prefix)]:
            sys.modules.pop(mod, None)
        from voice_typer.server import internal_plugin_hook

        # Simulate a locked install: no developer flag, no env flag and no
        # usable workspace, which is what `internal_surface_enabled()` needs.
        monkeypatch.delenv("VOICE_TYPER_INTERNAL_PLUGINS", raising=False)
        monkeypatch.setenv("VOICE_TYPER_PLUGINS_DIR", str(_REPO_ROOT / "tools" / "absent-plugins"))
        assert internal_plugin_hook.plugins_enabled() is False
        assert internal_plugin_hook.install(object()) is False


class TestPluginSourcesAreTrackedButStateIsNot:
    """Source lives in the public repo; only local state is gitignored."""

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

    def test_root_gitignore_does_not_hide_plugin_sources(self) -> None:
        code, out = self._git(
            "check-ignore",
            "--no-index",
            "-q",
            "tools/internal_plugins/anthropic_stt/plugin.json",
        )
        assert code == 1, (
            "tools/internal_plugins source must be visible in the repo, not ignored "
            f"(git check-ignore said: {out or 'ignored'})"
        )

    def test_plugin_sources_are_tracked(self) -> None:
        code, out = self._git("ls-files", "tools/internal_plugins")
        assert code == 0, f"git ls-files failed: {out}"
        tracked = {line for line in out.splitlines() if line.strip()}
        for rel in (
            "tools/internal_plugins/anthropic_stt/plugin.json",
            "tools/internal_plugins/anthropic_stt/plugin.py",
            "tools/internal_plugins/google_stt/plugin.json",
        ):
            assert rel in tracked, f"{rel} must be tracked in the parent repo"

    def test_runtime_state_is_not_tracked(self) -> None:
        code, out = self._git("ls-files", "tools/internal_plugins")
        assert code == 0, f"git ls-files failed: {out}"
        tracked = [line for line in out.splitlines() if line.strip()]
        forbidden = ("PLUGINS_ENABLED", "config.json", "settings.json")
        leaked = [p for p in tracked if p.rsplit("/", 1)[-1] in forbidden]
        assert leaked == [], f"runtime state must stay untracked: {leaked}"

    def test_runtime_state_stays_ignored(self) -> None:
        for rel in (
            "tools/internal_plugins/PLUGINS_ENABLED",
            "tools/internal_plugins/anthropic_stt/config.json",
            "tools/internal_plugins/anthropic_stt/settings.json",
            "tools/internal_plugins/google_stt/config.json",
            "tools/internal_plugins/google_stt/settings.json",
            "tools/internal_plugins/anthropic_stt/extension/generated/config.js",
        ):
            code, out = self._git("check-ignore", "--no-index", "-q", rel)
            assert code == 0, f"{rel} must stay gitignored (git check-ignore said: {out or 'not ignored'})"


@pytest.mark.parametrize("js_file", ["run.js", "playwright_runner.js"])
def test_plugin_js_files_stay_inside_the_plugin_workspace(js_file: str) -> None:
    target = _PLUGINS_DIR / "google_stt" / js_file
    assert target.exists(), f"{js_file} must live under tools/internal_plugins/google_stt"
