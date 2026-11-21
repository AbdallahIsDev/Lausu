"""
Installer-config tests for the slim-core / runtime-pack split.
C-CI-13 forbids RENAMING the existing artifacts without updating every
consumer in lockstep; these are NEW names
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_TAURI = PROJECT_ROOT / "src-tauri"
INSTALLER_HOOKS_NSH = PROJECT_ROOT / "scripts" / "windows" / "installer-hooks.nsh"
UNINSTALLER_NSH = PROJECT_ROOT / "scripts" / "windows" / "uninstaller.nsh"
FULL_OFFLINE_NSI = PROJECT_ROOT / "scripts" / "windows" / "full-offline-installer.nsi"
FULL_OFFLINE_BUILD_SH = PROJECT_ROOT / "scripts" / "build" / "build_full_offline_installer_windows.sh"
ARTIFACT_NAMES_PY = PROJECT_ROOT / "scripts" / "build" / "artifact_names.py"
STUB_SCRIPT = PROJECT_ROOT / "scripts" / "gen_tauri_icons_stub.py"


def _strip_nsis_comments(text: str) -> str:
    """
    Strip ``;``-comments from NSIS source so directive checks don't
    SectionIn RO" must NOT trigger the SectionIn RO directive check).
    """
    out_lines: list[str] = []
    for line in text.splitlines():
        idx = line.find(";")
        if idx >= 0:
            line = line[:idx]
        out_lines.append(line)
    return "\n".join(out_lines)


def _nsi_section(text: str, name: str) -> str:
    """Return one NSIS Section's raw source (PowerShell `;` stays intact)."""
    start = text.index(f'Section "{name}"')
    end = text.index("SectionEnd", start)
    return text[start:end]


def _tauri_conf() -> dict:
    return json.loads((SRC_TAURI / "tauri.conf.json").read_text(encoding="utf-8"))


def _installer_hooks_list() -> list[str]:
    """Return the ``bundle.windows.nsis.installerHooks`` entries as a list."""
    nsis = _tauri_conf()["bundle"]["windows"]["nsis"]
    hooks = nsis.get("installerHooks", [])
    if isinstance(hooks, str):
        hooks = [hooks]
    return list(hooks)


# File-existence gates, these scripts are owned by a separate workstream
_MISSING_ARTIFACT_NAMES_RSN = (
    f"scripts/build/artifact_names.py not present at {ARTIFACT_NAMES_PY}, "
    "this file is the §11.9 naming-contract source of truth and is owned by "
    "the installer-build workstream. Skipping until the file lands."
)
_MISSING_FULL_OFFLINE_BUILD_SH_RSN = (
    f"scripts/build/build_full_offline_installer_windows.sh not present at "
    f"{FULL_OFFLINE_BUILD_SH}, this script is owned by the installer-build "
    "workstream (it wires makensis + the .nsi template + the §11.9 "
    "artifact-name module). Skipping until the file lands."
)


def _skip_if_missing(path: Path, reason: str) -> None:
    """Skip the calling test when ``path`` does not exist."""
    if not path.is_file():
        pytest.skip(reason)


def _load_artifact_names_module():
    _skip_if_missing(ARTIFACT_NAMES_PY, _MISSING_ARTIFACT_NAMES_RSN)
    spec = importlib.util.spec_from_file_location("_vt_artifact_names_test", ARTIFACT_NAMES_PY)
    assert spec is not None and spec.loader is not None, f"cannot load {ARTIFACT_NAMES_PY}"
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec so ``@dataclass`` can resolve
    sys.modules["_vt_artifact_names_test"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop("_vt_artifact_names_test", None)
    return module


class TestInstallerHooksNshRegistered:
    """``installer-hooks.nsh`` must be reachable via ``installerHooks``."""

    def test_installer_hooks_is_a_single_registered_nsh(self) -> None:
        nsis = _tauri_conf()["bundle"]["windows"]["nsis"]
        hooks = nsis.get("installerHooks")
        assert isinstance(hooks, str) and hooks, (
            "bundle.windows.nsis.installerHooks must be a single .nsh path "
            "string (tauri-utils deserializes it as Option<PathBuf>, a "
            "list fails the config parse, breaking the build)."
        )
        assert hooks.endswith(".nsh"), (
            f"installerHooks entry {hooks!r} must be an NSIS script (.nsh), "
            "Tauri !includes it into installer.nsi; a non-NSIS file aborts "
            "makensis."
        )
        # The path in tauri.conf.json is relative to src-tauri/ (Tauri's
        target = (SRC_TAURI / hooks).resolve()
        assert target.is_file(), f"installerHooks entry {hooks!r} does not exist at {target}."

    def test_wrapper_includes_both_install_and_uninstall_hooks(self) -> None:
        """The registered wrapper must compose BOTH hook files."""
        nsis = _tauri_conf()["bundle"]["windows"]["nsis"]
        hooks = nsis.get("installerHooks")
        assert isinstance(hooks, str) and hooks, "installerHooks must be set."
        wrapper = (SRC_TAURI / hooks).resolve()
        text = wrapper.read_text(encoding="utf-8")
        hook_names = {Path(h).name for h in _installer_hooks_list()}
        assert "uninstaller.nsh" in text, (
            "the hooks wrapper must !include uninstaller.nsh, defines "
            "customUnInstall for CR-69/CR-70 cleanup (autostart Run keys, "
            "Task Scheduler tasks, %APPDATA%\\lausu data dir)."
        )
        assert "installer-hooks.nsh" in text, (
            "the hooks wrapper must !include installer-hooks.nsh, defines "
            "the Include offline engine pack checkbox Section and the "
            "customInstall macro that writes installer-state.json (plan "
            "§4.8 consent gate)."
        )
        assert hook_names, "installerHooks must resolve to at least one .nsh."

    def test_every_hook_ends_in_nsh_and_exists(self) -> None:
        """Mirror the contract in TestTauriNsisInstallerHooks for new entries."""
        for hook in _installer_hooks_list():
            assert hook.endswith(".nsh"), (
                f"installerHooks entry {hook!r} must be an NSIS script (.nsh), "
                "Tauri !includes it into installer.nsi; a non-NSIS file aborts "
                "makensis."
            )
            # The path in tauri.conf.json is relative to src-tauri/ (Tauri's
            target = (SRC_TAURI / hook).resolve()
            assert target.is_file(), f"installerHooks entry {hook!r} does not exist at {target}."


class TestInstallerHooksNshSection:
    """The .nsh must surface a visible "Include offline engine pack" choice.

    Tauri's generated installer.nsi has NO ``MUI_PAGE_COMPONENTS`` page, so
    a Section would never render as a checkbox (and inserting one would
    expose Tauri's own Install section as optional). The choice is a
    ``Page custom`` + nsDialogs checkbox instead.
    """

    def test_custom_pack_option_page_present(self) -> None:
        text = INSTALLER_HOOKS_NSH.read_text(encoding="utf-8")
        assert "Page custom LausuPackOptionCreate LausuPackOptionLeave" in text, (
            "installer-hooks.nsh must declare a custom Page for the pack "
            "checkbox (Tauri v2 has no Components page; a Section alone is "
            "invisible)."
        )

    def test_checkbox_label_pinned(self) -> None:
        text = INSTALLER_HOOKS_NSH.read_text(encoding="utf-8")
        assert "Include offline engine pack" in text, (
            'installer-hooks.nsh must label the checkbox "Include offline '
            "engine pack\" (plan §4.8 / §9.3)."
        )

    def test_checkbox_defaults_to_checked(self) -> None:
        """Default is include (opt-out, not opt-in — plan §4.8)."""
        text = _strip_nsis_comments(INSTALLER_HOOKS_NSH.read_text(encoding="utf-8"))
        assert "${BST_CHECKED}" in text, (
            "the pack checkbox must default to checked "
            "(${NSD_SetState} ... ${BST_CHECKED}); the product default is "
            "auto-download and the user opts OUT."
        )

    def test_no_components_page_section(self) -> None:
        """A Components-page Section must NOT be reintroduced.

        Inserting ``MUI_PAGE_COMPONENTS`` would expose Tauri's EarlyChecks /
        WebView2 / Install sections as optional checkboxes (a user could
        untick Install and break the app).
        """
        text = _strip_nsis_comments(INSTALLER_HOOKS_NSH.read_text(encoding="utf-8"))
        assert 'Section "Include offline engine pack"' not in text, (
            "do not model the pack choice as an NSIS Section — Tauri's wizard "
            "has no Components page, and adding one exposes Tauri's own "
            "sections as optional."
        )
        assert "MUI_PAGE_COMPONENTS" not in text, (
            "do not insert MUI_PAGE_COMPONENTS; it would render Tauri's "
            "Install section as an optional checkbox."
        )

    def test_checkbox_reads_nsd_state(self) -> None:
        text = INSTALLER_HOOKS_NSH.read_text(encoding="utf-8")
        assert "${NSD_GetState}" in text, (
            "the pack-option leave handler must read the checkbox via "
            "${NSD_GetState} (nsDialogs), not SectionGetFlags."
        )


class TestInstallerHooksCustomInstallMacro:
    """The install hook writes installer-state.json (Tauri NSIS_HOOK_POSTINSTALL)."""

    def test_nsis_hook_postinstall_defined(self) -> None:
        text = INSTALLER_HOOKS_NSH.read_text(encoding="utf-8")
        assert "!macro NSIS_HOOK_POSTINSTALL" in text, (
            "installer-hooks.nsh must define `!macro NSIS_HOOK_POSTINSTALL` — "
            "that is the ONLY install-side hook Tauri v2's installer.nsi "
            "invokes (crates/tauri-bundler). A bare customInstall is never "
            "called."
        )

    def test_custom_install_alias_still_defined(self) -> None:
        text = INSTALLER_HOOKS_NSH.read_text(encoding="utf-8")
        assert "!macro customInstall" in text, (
            "customInstall must remain as a thin alias of "
            "NSIS_HOOK_POSTINSTALL (older references / focused tests)."
        )

    def test_installer_state_json_path_pinned(self) -> None:
        """The macro must write to the canonical installer-state.json path."""
        text = INSTALLER_HOOKS_NSH.read_text(encoding="utf-8")
        assert r"$LOCALAPPDATA\lausu\installer-state.json" in text, (
            "installer-hooks.nsh must write installer-state.json to "
            "%LOCALAPPDATA%\\lausu\\, the SAME per-user data root the "
            "Python backend uses (voice_typer/server/_paths.py). A different "
            "path breaks the first-launch consent read (plan §4.7 / §4.8)."
        )

    def test_installer_state_json_schema_pinned(self) -> None:
        """The JSON shape written by the macro is pinned here."""
        text = INSTALLER_HOOKS_NSH.read_text(encoding="utf-8")
        for required_field in (
            "include_offline_engine_pack",
            "installer_version",
            "pack_bundled",
        ):
            assert required_field in text, (
                f"installer-hooks.nsh must write the `{required_field}` field to "
                "installer-state.json, the slim-core Python reader pins the schema. "
                "See plan-runtime-pack-split.md §4.8."
            )

    def test_installer_version_uses_tauri_version_define(self) -> None:
        """Tauri defines ``VERSION``; ``PRODUCT_VERSION`` is undefined and
        aborts makensis."""
        text = _strip_nsis_comments(INSTALLER_HOOKS_NSH.read_text(encoding="utf-8"))
        assert "${VERSION}" in text, (
            "installer-state.json must embed ${VERSION} (the define Tauri's "
            "installer.nsi sets)."
        )
        assert "${PRODUCT_VERSION}" not in text, (
            "${PRODUCT_VERSION} is not defined by Tauri's installer.nsi — "
            "makensis aborts on the unknown symbol. Use ${VERSION}."
        )

    def test_custom_install_reads_checkbox_state(self) -> None:
        """The hook must consult the checkbox, not hardcode."""
        text = INSTALLER_HOOKS_NSH.read_text(encoding="utf-8")
        assert "$IncludeOfflineEnginePack" in text, (
            "the state writer must read $IncludeOfflineEnginePack (set by "
            "the custom-page checkbox), not a hardcoded value."
        )


class TestArtifactNames:
    """``scripts/build/artifact_names.py`` owns the §11.9 naming contract."""

    def test_slim_core_name_format(self) -> None:

        # Import via path so the test doesn't require the module on sys.path.
        mod = _load_artifact_names_module()
        name = mod.slim_core_installer_name("1.0.0", "x86_64-pc-windows-msvc")
        assert name == "lausu-slim-core-1.0.0-x86_64-pc-windows-msvc.exe", (
            "slim-core installer name must match §11.9: lausu-slim-core-<version>-<triple>.exe"
        )

    def test_runtime_pack_name_format(self) -> None:
        mod = _load_artifact_names_module()
        name = mod.runtime_pack_name("3", "x86_64-pc-windows-msvc")
        assert name == "lausu-runtime-pack-3-x86_64-pc-windows-msvc.zip", (
            "runtime-pack name must match §11.9: lausu-runtime-pack-<pack-version>-<triple>.zip"
        )

    def test_pack_manifest_name(self) -> None:
        mod = _load_artifact_names_module()
        assert mod.pack_manifest_name() == "pack-manifest.json", (
            "pack-manifest.json is the §11.9 manifest release-asset filename (platform-AGNOSTIC, no triple suffix)."
        )

    def test_full_offline_installer_name_format(self) -> None:
        mod = _load_artifact_names_module()
        name = mod.full_offline_installer_name("1.0.0", "x86_64-pc-windows-msvc")
        assert name == "lausu-full-offline-1.0.0-x86_64-pc-windows-msvc.exe", (
            "full-offline installer name must match the §11.9 addendum: lausu-full-offline-<app-version>-<triple>.exe"
        )

    def test_cli_round_trip(self) -> None:
        """The CLI prints the same name the library function returns."""
        _skip_if_missing(ARTIFACT_NAMES_PY, _MISSING_ARTIFACT_NAMES_RSN)
        import subprocess

        result = subprocess.run(
            [
                sys.executable,  # ``python3`` is not portable (Windows: ``python``)
                str(ARTIFACT_NAMES_PY),
                "--slim-core",
                "--app-version",
                "1.0.0",
                "--triple",
                "aarch64-pc-windows-msvc",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "lausu-slim-core-1.0.0-aarch64-pc-windows-msvc.exe"

    def test_invalid_triple_rejected(self) -> None:
        """Unknown triples must raise, prevents typos in CI yaml."""
        mod = _load_artifact_names_module()
        with pytest.raises(ValueError, match="unsupported target triple"):
            mod.slim_core_installer_name("1.0.0", "invalid-triple")

    def test_invalid_version_rejected(self) -> None:
        """Malformed versions must raise, prevents bad release bumps."""
        mod = _load_artifact_names_module()
        with pytest.raises(ValueError, match="malformed app-version"):
            mod.slim_core_installer_name("not-a-version", "x86_64-pc-windows-msvc")


class TestNoRenameOfExistingArtifacts:
    """
    C-CI-13: never rename EXISTING artifacts without lockstep consumer
    updates. C-CI-13-protected existing names (a collision would be a silent
    """

    def test_new_names_do_not_collide_with_protected(self) -> None:
        mod = _load_artifact_names_module()
        protected = set(mod.EXISTING_PROTECTED_NAMES)
        # Sample new-name artifacts across all triples and a few versions.
        new_names: set[str] = set()
        for triple in mod.SUPPORTED_TRIPLES:
            new_names.add(mod.slim_core_installer_name("1.0.0", triple))
            new_names.add(mod.runtime_pack_name("3", triple))
            new_names.add(mod.full_offline_installer_name("1.0.0", triple))
        new_names.add(mod.pack_manifest_name())
        overlap = protected & new_names
        assert not overlap, (
            "C-CI-13 violation: new §11.9 artifact names overlap with the "
            f"protected existing names: {sorted(overlap)}. The new names must "
            "be ADDITIVE, they must NOT rename or overwrite the existing "
            "Lausu-Windows-Installer / Lausu-Windows-* / python-sidecar-* "
            "artifact names."
        )

    def test_existing_protected_names_listed(self) -> None:
        """
        The protected names list must enumerate every C-CI-13 entry.
        C-CI-13 enumerates: ``Lausu-Windows-Installer``, ``Lausu-Windows-MSI``,
        """
        mod = _load_artifact_names_module()
        expected = {
            "Lausu-Windows-Installer",
            "Lausu-Windows-MSI",
            "Lausu-Windows-Sidecar-Binaries",
            "Lausu-Windows-SHA256SUMS",
            "Lausu-Binaries-Manifest-Windows",
        }
        assert expected.issubset(set(mod.EXISTING_PROTECTED_NAMES)), (
            "EXISTING_PROTECTED_NAMES missing entries from C-CI-13: "
            f"{sorted(expected - set(mod.EXISTING_PROTECTED_NAMES))}"
        )


class TestSlimInstallerNaming:
    """SP-1 slice A: the slim installer keeps the existing names (C-CI-13)."""

    SLIM_CONF = SRC_TAURI / "tauri.windows-x86_64-slim.conf.json"
    FULL_CONF = SRC_TAURI / "tauri.windows-x86_64.conf.json"
    WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "tauri-windows-build.yml"

    def test_slim_conf_exists_with_sidecar_only_external_bin(self) -> None:
        assert self.SLIM_CONF.is_file(), f"slim config missing at {self.SLIM_CONF}"
        conf = json.loads(self.SLIM_CONF.read_text(encoding="utf-8"))
        ext = conf["bundle"]["externalBin"]
        assert "bin/python-sidecar" in ext, "slim config must declare the sidecar"
        assert not any("worker" in e for e in ext), "slim config must not declare the worker"
        assert "bin/ffmpeg" in ext, "Windows x64 slim must bundle the LGPL ffmpeg"
        assert "bin/ffprobe" not in ext, "ffprobe is not shipped; duration comes from ffmpeg's stderr"

    def test_slim_conf_resources_match_full_conf(self) -> None:
        slim = json.loads(self.SLIM_CONF.read_text(encoding="utf-8"))["bundle"]["resources"]
        full = json.loads(self.FULL_CONF.read_text(encoding="utf-8"))["bundle"]["resources"]
        assert slim == full, "slim resources must equal the full Windows narrowing."

    def test_workflow_builds_slim_config(self) -> None:
        text = self.WORKFLOW.read_text(encoding="utf-8")
        assert "tauri.windows-x86_64-slim.conf.json" in text, (
            "tauri-windows-build.yml must build the slim config (SP-1 slim leg)."
        )

    def test_existing_installer_name_stays_with_slim(self) -> None:
        """``Lausu-Windows-Installer`` is still uploaded (now the slim payload)."""
        text = self.WORKFLOW.read_text(encoding="utf-8")
        assert "name: Lausu-Windows-Installer" in text, (
            "C-CI-13: Lausu-Windows-Installer must stay (it now carries the "
            "slim installer per owner decision); full-offline uses ADDITIVE names."
        )
        for protected in (
            "Lausu-Windows-MSI",
            "Lausu-Windows-Sidecar-Binaries",
            "Lausu-Windows-SHA256SUMS",
            "Lausu-Binaries-Manifest-Windows",
        ):
            assert f"name: {protected}" in text, f"C-CI-13: {protected} must stay."


class TestFullOfflineInstallerTemplate:
    """The full-offline installer .nsi template must require its !defines."""

    def test_template_exists(self) -> None:
        assert FULL_OFFLINE_NSI.is_file(), (
            f"full-offline-installer.nsi must exist at {FULL_OFFLINE_NSI}, "
            "the full-offline installer artifact is the second Windows installer "
            "alongside the slim core (plan §4.1 / §14.5)."
        )

    @pytest.mark.parametrize(
        "define",
        ["SLIM_CORE_EXE", "PACK_ZIP", "PACK_VERSION", "APP_VERSION", "PRODUCT_TRIPLE"],
    )
    def test_template_requires_each_define(self, define: str) -> None:
        text = FULL_OFFLINE_NSI.read_text(encoding="utf-8")
        # Each !define must be guarded by an !ifndef block that !errors
        pattern = rf"!ifndef\s+{define}\b"
        assert re.search(pattern, text), (
            f"full-offline-installer.nsi must guard {define} with `!ifndef {define}` "
            f"and `!error`, without the guard, makensis silently produces a "
            "broken installer when the build script forgets to pass -D{define}=..."
        )

    def test_template_outfile_uses_canonical_name(self) -> None:
        """The OutFile directive must produce the §11.9 name."""
        text = FULL_OFFLINE_NSI.read_text(encoding="utf-8")
        # The OutFile uses ${APP_VERSION} and ${PRODUCT_TRIPLE} !defines
        assert "lausu-full-offline-${APP_VERSION}-${PRODUCT_TRIPLE}.exe" in text, (
            "full-offline-installer.nsi OutFile must be "
            "`lausu-full-offline-${APP_VERSION}-${PRODUCT_TRIPLE}.exe`, "
            "the §11.9 canonical name (built from the build-time !defines so it "
            "cannot drift from artifact_names.py)."
        )

    def test_template_extracts_pack_to_runtime_pack_dir(self) -> None:
        """The pack zip must be extracted to the per-user runtime-pack dir."""
        text = FULL_OFFLINE_NSI.read_text(encoding="utf-8")
        assert r"$LOCALAPPDATA\lausu\runtime-pack\${PACK_VERSION}" in text, (
            "full-offline-installer.nsi must extract the pack to "
            "%LOCALAPPDATA%\\lausu\\runtime-pack\\<PACK_VERSION>\\, the "
            "SAME path the slim-core app's runtime-pack resolver scans (plan §4.7)."
        )

    def test_template_writes_installer_state_with_pack_bundled_true(self) -> None:
        """The wrapper writes installer-state.json with pack_bundled=true."""
        text = FULL_OFFLINE_NSI.read_text(encoding="utf-8")
        assert '"pack_bundled": true' in text, (
            "full-offline-installer.nsi must write `pack_bundled: true` to "
            "installer-state.json, the slim-core app's first-launch consent "
            "gate checks this flag to skip the silent background download "
            "(plan §4.8)."
        )

    def test_template_runs_slim_core_installer(self) -> None:
        """The wrapper invokes the slim-core installer with only installer params."""
        text = FULL_OFFLINE_NSI.read_text(encoding="utf-8")
        assert "ExecWait" in text, (
            "full-offline-installer.nsi must ExecWait the bundled slim-core "
            "installer, without it, the slim-core app is never installed."
        )
        assert "!include FileFunc.nsh" in text, (
            "full-offline-installer.nsi must include FileFunc.nsh; its "
            "${GetParameters} macro extracts only the installer parameters "
            "(raw $CMDLINE includes the wrapper's own exe path)."
        )
        assert "${GetParameters}" in text, (
            "full-offline-installer.nsi must use ${GetParameters} to extract "
            "only the parameters passed to this wrapper before forwarding "
            "them to the slim-core installer."
        )
        exec_lines = [
            line
            for line in text.splitlines()
            if "ExecWait" in line and "slim-core-setup.exe" in line
        ]
        assert exec_lines, "the slim-core ExecWait line must be present"
        exec_line = exec_lines[0]
        assert "$CMDLINE" not in exec_line, (
            "the slim-core ExecWait line must NOT forward raw $CMDLINE — it "
            "contains the wrapper's own exe path and omits /D=path; forward "
            "the ${GetParameters} result instead."
        )
        assert "$R0" in exec_line, (
            "the slim-core ExecWait line must forward the ${GetParameters} "
            "result ($R0), the installer parameters only."
        )
        assert "Forward the original cmdline" not in text, (
            "the old comment falsely claimed /S and /D=path propagate via "
            "$CMDLINE; it must be corrected."
        )
        assert "/D=" in text and "cannot be forwarded" in text, (
            "the wrapper must document that /D=path cannot be forwarded "
            "through a parameter string (NSIS consumes it as the wrapper's "
            "own install dir), so users know to set the slim-core install "
            "dir through its own UI/config."
        )

    def test_extraction_failure_aborts_install(self) -> None:
        """A nonzero Expand-Archive exit must fail the wrapper."""
        text = FULL_OFFLINE_NSI.read_text(encoding="utf-8")
        pack = _nsi_section(text, "Offline engine pack (bundled)")
        assert "${If} $0 != 0" in pack, "the pack section must branch on the extraction exit code $0"
        fail_start = pack.index("${If} $0 != 0")
        fail_end = pack.index("${EndIf}", fail_start)
        fail_branch = pack[fail_start:fail_end]
        assert "Abort" in fail_branch, (
            "nonzero Expand-Archive exit code must Abort the install; a warning "
            "leaves a partial/empty pack marked as bundled."
        )
        assert "WARNING: Expand-Archive" not in fail_branch, (
            "a warning-only extraction failure branch regresses failure handling."
        )

    def test_extract_uses_terminating_powershell_errors(self) -> None:
        """Corrupt zips must yield a nonzero exit, not a silent success."""
        text = FULL_OFFLINE_NSI.read_text(encoding="utf-8")
        pack = _nsi_section(text, "Offline engine pack (bundled)")
        assert "-ErrorAction Stop" in pack, (
            "Expand-Archive needs -ErrorAction Stop so a corrupt/partial zip "
            "produces a nonzero exit code instead of a non-terminating error."
        )
        # NSIS `$$` emits a literal `$` for PowerShell (NSIS string escaping),
        # so this asserts the emitted command sets the real $ErrorActionPreference.
        assert "$$ErrorActionPreference" in pack, (
            "$ErrorActionPreference = 'Stop' must reach PowerShell (write it as "
            "$$ErrorActionPreference in NSIS), not be swallowed as an NSIS variable."
        )

    def test_zip_deleted_only_after_extraction_verified(self) -> None:
        """The archive stays on disk until extraction is proven good."""
        text = FULL_OFFLINE_NSI.read_text(encoding="utf-8")
        pack = _nsi_section(text, "Offline engine pack (bundled)")
        zip_name = "lausu-runtime-pack-${PACK_VERSION}-${PRODUCT_TRIPLE}.zip"
        delete_line = next(
            (line for line in pack.splitlines() if line.strip().startswith("Delete ") and zip_name in line),
            None,
        )
        assert delete_line is not None, "the pack zip must still be deleted after a verified extraction"
        assert "Get-ChildItem" in pack, (
            "extraction must be verified by inspecting the extracted files before "
            "the archive is deleted (file assertion)."
        )
        aborts = [m.start() for m in re.finditer(r"\bAbort\b", pack)]
        assert len(aborts) >= 2, (
            "there must be both an extract-failure Abort and a verify-failure Abort."
        )
        assert max(aborts) < pack.index(delete_line), (
            "the zip Delete must come after every failure Abort, so a failed "
            "extraction leaves the archive for retry."
        )

    def test_slim_core_failure_aborts_install(self) -> None:
        """A nonzero slim-core installer exit must fail the wrapper."""
        text = FULL_OFFLINE_NSI.read_text(encoding="utf-8")
        slim = _nsi_section(text, "Install slim core")
        assert "${If} $0 != 0" in slim, "the slim-core section must branch on ExecWait's exit code $0"
        fail_start = slim.index("${If} $0 != 0")
        fail_end = slim.index("${EndIf}", fail_start)
        assert "Abort" in slim[fail_start:fail_end], (
            "nonzero slim-core installer exit code must Abort the install; a "
            "warning makes a failed app install look successful."
        )
        assert "WARNING: slim-core installer" not in slim, (
            "a warning-only slim-core failure branch regresses failure handling."
        )

    def test_state_written_only_after_successful_steps(self) -> None:
        """pack_bundled=true is emitted only after both steps succeed."""
        text = FULL_OFFLINE_NSI.read_text(encoding="utf-8")
        slim_start = text.index('Section "Install slim core"')
        state_start = text.index('Section "Write installer state"')
        pack_start = text.index('Section "Offline engine pack (bundled)"')
        assert pack_start < slim_start < state_start, (
            "NSIS runs sections in source order: pack extraction, then the "
            "slim-core installer, then installer-state.json. Writing "
            "pack_bundled=true earlier would claim a broken install succeeded."
        )


class TestFullOfflineBuildScript:
    """The build script wires makensis + the .nsi template + the inputs."""

    _SKIP_REASON = (
        f"build_full_offline_installer_windows.sh not present at "
        f"{FULL_OFFLINE_BUILD_SH}, this script is owned by the installer-build "
        "workstream. Skipping until the file lands."
    )

    def test_script_exists_and_is_executable(self) -> None:
        _skip_if_missing(FULL_OFFLINE_BUILD_SH, self._SKIP_REASON)
        assert FULL_OFFLINE_BUILD_SH.is_file(), (
            f"build_full_offline_installer_windows.sh must exist at {FULL_OFFLINE_BUILD_SH}."
        )
        # On Windows CI the script runs under Git Bash, the executable
        if os.name == "posix":
            mode = FULL_OFFLINE_BUILD_SH.stat().st_mode
            assert mode & stat.S_IXUSR, (
                f"{FULL_OFFLINE_BUILD_SH.name} must be executable (chmod +x), the CI YAML invokes it directly."
            )

    def test_script_requires_all_inputs(self) -> None:
        _skip_if_missing(FULL_OFFLINE_BUILD_SH, self._SKIP_REASON)
        """The script must reject missing inputs at arg-parse time."""
        text = FULL_OFFLINE_BUILD_SH.read_text(encoding="utf-8")
        for flag in ("--slim-core", "--pack-zip", "--pack-version", "--app-version", "--triple"):
            assert flag in text, (
                f"build_full_offline_installer_windows.sh must accept {flag}, "
                "the build script composes the slim-core installer + pack zip "
                "into the full-offline artifact; each input is required."
            )

    def test_script_invokes_artifact_names_py_for_output_name(self) -> None:
        _skip_if_missing(FULL_OFFLINE_BUILD_SH, self._SKIP_REASON)
        """The script must NOT hardcode the output filename.

        The §11.9 name is owned by artifact_names.py; the build script
        must call the Python module so the name cannot drift. A
        hardcoded name in the shell script would silently diverge from
        the Python contract.
        """
        text = FULL_OFFLINE_BUILD_SH.read_text(encoding="utf-8")
        assert "artifact_names.py" in text, (
            "build_full_offline_installer_windows.sh must invoke "
            "artifact_names.py to compute the output filename, the §11.9 "
            "name is owned by that module so it cannot drift between the "
            "Python and shell sides."
        )

    def test_script_passes_all_defines_to_makensis(self) -> None:
        _skip_if_missing(FULL_OFFLINE_BUILD_SH, self._SKIP_REASON)
        text = FULL_OFFLINE_BUILD_SH.read_text(encoding="utf-8")
        for define in ("SLIM_CORE_EXE", "PACK_ZIP", "PACK_VERSION", "APP_VERSION", "PRODUCT_TRIPLE"):
            assert f"-D{define}=" in text, (
                f"build_full_offline_installer_windows.sh must pass -D{define}=... "
                f"to makensis, the .nsi template !errors on missing {define}."
            )


class TestSupportedTriplesMatchesStubGenerator:
    """artifact_names.py::SUPPORTED_TRIPLES ↔ gen_tauri_icons_stub.py::SIDECAR_TRIPLES."""

    def test_supported_triples_equals_stub_generator_sidecar_triples(self) -> None:
        mod = _load_artifact_names_module()
        # Load the stub generator module the same way test_config_script_drift does.
        spec = importlib.util.spec_from_file_location("_vt_stub_triples_test", STUB_SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {STUB_SCRIPT}"
        stub = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stub)
        assert set(mod.SUPPORTED_TRIPLES) == set(stub.SIDECAR_TRIPLES), (
            "artifact_names.py::SUPPORTED_TRIPLES drifted from "
            "gen_tauri_icons_stub.py::SIDECAR_TRIPLES, both must enumerate "
            "the canonical build triples. Add new triples to BOTH in the same "
            f"commit.\n  artifact_names only: {sorted(set(mod.SUPPORTED_TRIPLES) - set(stub.SIDECAR_TRIPLES))}\n"
            f"  stub only: {sorted(set(stub.SIDECAR_TRIPLES) - set(mod.SUPPORTED_TRIPLES))}"
        )


class TestUninstallerNshNotRegressed:
    """Adding installer-hooks.nsh must NOT break the existing uninstaller."""

    def test_uninstaller_nsh_still_defines_custom_uninstall(self) -> None:
        text = UNINSTALLER_NSH.read_text(encoding="utf-8")
        assert "!macro customUnInstall" in text, (
            "uninstaller.nsh must still define `!macro customUnInstall`, the "
            "CR-69 / CR-70 cleanup (autostart Run keys, Task Scheduler tasks, "
            "%APPDATA%\\lausu data dir) depends on it. Adding "
            "installer-hooks.nsh must NOT remove the existing uninstall hooks."
        )

    def test_uninstaller_nsh_wires_tauri_post_uninstall_hook(self) -> None:
        """Tauri invokes only NSIS_HOOK_POSTUNINSTALL."""
        text = UNINSTALLER_NSH.read_text(encoding="utf-8")
        assert "!macro NSIS_HOOK_POSTUNINSTALL" in text, (
            "uninstaller.nsh must define `!macro NSIS_HOOK_POSTUNINSTALL` — "
            "that is the ONLY uninstall-side hook Tauri v2's installer.nsi "
            "invokes. customUnInstall alone is never called."
        )

    def test_uninstaller_nsh_still_cleans_appdata(self) -> None:
        text = UNINSTALLER_NSH.read_text(encoding="utf-8")
        # The path is quoted in the .nsh (NSIS literal: `"$APPDATA\lausu"`).
        assert r'RMDir /r "$APPDATA\lausu"' in text, (
            'uninstaller.nsh must still RMDir /r "%APPDATA%\\lausu", CR-70 '
            "per-user data dir cleanup (settings JSON, history DB, vocabularies)."
        )

    def test_uninstaller_nsh_cleans_local_runtime_pack(self) -> None:
        text = UNINSTALLER_NSH.read_text(encoding="utf-8")
        assert r'RMDir /r "$LOCALAPPDATA\lausu\runtime-pack"' in text, (
            "uninstaller.nsh must remove the installer-owned runtime pack from "
            "%LOCALAPPDATA%\\lausu\\runtime-pack; the pack resolver reads that "
            "root, and a stale pack survives every uninstall otherwise."
        )
        assert r'Delete "$LOCALAPPDATA\lausu\installer-state.json"' in text, (
            "uninstaller.nsh must delete installer-state.json, which carries "
            "the pack_bundled consent flag and can be reused by a reinstall."
        )
        assert 'RMDir "$LOCALAPPDATA\\lausu"' in text, (
            "the LOCALAPPDATA root may be removed only when empty; a blanket "
            "recursive delete would take user-created files with it."
        )
        assert r'RMDir /r "$LOCALAPPDATA\lausu"' not in text

    def test_uninstaller_nsh_cleans_startup_folder_bats(self) -> None:
        text = UNINSTALLER_NSH.read_text(encoding="utf-8")
        assert "Start Menu" in text and "Startup" in text, (
            "uninstaller.nsh must handle the per-user Startup folder: the "
            "tertiary autostart mechanism writes its .bat there and neither "
            "the Run-key loop nor the task sweep removes files."
        )
        assert "com.Lausu.autostart_*.bat" in text, (
            "uninstaller.nsh must enumerate the current Startup .bat scheme "
            "`com.Lausu.autostart_*.bat` (hash-suffixed per install)."
        )
        assert "Lausu_*.bat" in text, (
            "uninstaller.nsh must also enumerate the pre-rename legacy scheme "
            "`Lausu_*.bat` so stale entries from older installs are removed."
        )
        assert "FindFirst" in text, (
            "uninstaller.nsh must enumerate Startup .bat matches (FindFirst / "
            "FindNext loop): a single fixed-path Delete cannot cover "
            "hash-suffixed names from previous installs."
        )
