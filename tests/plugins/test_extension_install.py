"""Install-path invariants: one extension, one profile, one port, one token.

The old install lived in the git tree and Chrome registers unpacked extensions
by absolute path, so a refactor silently removed it. These tests pin the
stable app-data path and the read-only diagnostic around it.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from tests.plugins.profile_path_helpers import assert_shared_profile
from tools.internal_plugins._common.bridge import (
    chrome_profile,
    install_paths,
    keepalive,
)
from tools.internal_plugins.anthropic_stt import plugin as anthropic
from tools.internal_plugins.google_stt import plugin as google

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = ROOT / "tools" / "internal_plugins"
BRIDGE = PLUGINS / "_common" / "bridge"

_VERIFIER = BRIDGE / "verify_extension_install.py"
_spec = importlib.util.spec_from_file_location("verify_extension_install", _VERIFIER)
verifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verifier)


@pytest.fixture
def hermetic_source_config(monkeypatch, tmp_path):
    """Give the verifier a generated config and skip the real Node subprocess."""
    here = tmp_path / "source"
    source = here / "extension" / "generated" / "config.js"
    source.parent.mkdir(parents=True)
    source.write_text("// hermetic test config\nself.ANTHROPIC_STT_CONFIG = {};\n", encoding="utf-8")
    monkeypatch.setattr(verifier, "HERE", here)
    monkeypatch.setattr(
        verifier,
        "subprocess",
        SimpleNamespace(
            run=lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="ok", stderr="")
        ),
    )
    return source.read_bytes()


class TestInstallAuthority:
    def test_stable_path_is_outside_the_repo(self):
        target = install_paths.stable_extension_dir().resolve()
        repo = install_paths.repo_root().resolve()
        assert target != repo and repo not in target.parents
        assert target.name == "extension"

    @pytest.mark.parametrize("module", [anthropic, google])
    def test_one_profile_from_one_authority(self, module):
        # config.json is gitignored runtime state; the tracked example is the
        # shipped descriptor that must agree with the one profile authority.
        text = (module.HERE / "config.example.json").read_text(encoding="utf-8")
        assert_shared_profile(json.loads(text)["profileDir"])
        profile_leaf = install_paths.PROFILE_RELATIVE_PATH.split("/")[-1]
        for value in {line.split('"')[3] for line in text.splitlines() if profile_leaf in line}:
            assert_shared_profile(value)

    def test_one_extension_and_no_second_copy(self):
        assert (BRIDGE / "extension" / "manifest.json").is_file()
        for name in ("anthropic_stt", "google_stt"):
            assert not (PLUGINS / name / "extension").exists()
        stager = ROOT / "scripts" / "build" / "stage_internal_plugins.py"
        text = stager.read_text(encoding="utf-8")
        assert '"generated"' in text and '"config.json"' in text

    @pytest.mark.parametrize(
        ("module", "platform"), [(anthropic, "claude"), (google, "gemini")]
    )
    def test_one_port_and_one_token_store(self, module, platform):
        descriptor = json.loads((module.HERE / "config.example.json").read_text(encoding="utf-8"))
        assert descriptor["port"] == install_paths.PORT == 17875
        assert descriptor["platform"] == platform
        assert module.DAEMON_URL.endswith(":17875")
        assert (BRIDGE / "install.json").is_file()
        # token.json is gitignored runtime state; pin the single source authority.
        store = (BRIDGE / "config_store.js").read_text(encoding="utf-8")
        assert "const TOKEN_FILE = path.join(BRIDGE_DIR, 'token.json')" in store
        assert store.count("'token.json'") == 1
        assert install_paths.EXTENSION_ID == "kkinikdljfdmbeibhhgkgmljahmfgecg"


class TestRegistryReader:
    def test_reads_the_requested_id_among_many_entries(self, tmp_path):
        doc = {
            "extensions": {
                "settings": {
                    "other-id": {"path": "C:/somewhere/else"},
                    install_paths.EXTENSION_ID: {"path": "C:/stable/extension"},
                }
            }
        }
        file = tmp_path / "Secure Preferences"
        file.write_text(json.dumps(doc), encoding="utf-8")
        assert install_paths.read_registered_extension_path(file) == "C:/stable/extension"

    def test_path_match_wins_over_a_drifted_id(self, tmp_path):
        target = tmp_path / "extension"
        target.mkdir()
        doc = {
            "extensions": {
                "settings": {
                    "path-derived-id": {"path": str(target)},
                    "unrelated-id": {"path": "C:/somewhere/else"},
                }
            }
        }
        file = tmp_path / "Secure Preferences"
        file.write_text(json.dumps(doc), encoding="utf-8")
        assert install_paths.read_registered_extension_path(file, target=target) == str(target)
        assert install_paths.duplicate_registration_count(file, target) == 1

    def test_duplicate_registrations_are_counted(self, tmp_path):
        target = tmp_path / "extension"
        target.mkdir()
        doc = {
            "extensions": {
                "settings": {
                    "one": {"path": str(target)},
                    install_paths.EXTENSION_ID: {"path": str(target)},
                }
            }
        }
        file = tmp_path / "Secure Preferences"
        file.write_text(json.dumps(doc), encoding="utf-8")
        assert install_paths.duplicate_registration_count(file, target) == 2

    def test_missing_and_malformed_files_fail_closed(self, tmp_path):
        assert install_paths.read_registered_extension_path(tmp_path / "absent") is None
        bad = tmp_path / "Secure Preferences"
        bad.write_text("{not json", encoding="utf-8")
        assert install_paths.read_registered_extension_path(bad) is None
        bad.write_text(json.dumps({"extensions": {"settings": {}}}), encoding="utf-8")
        assert install_paths.read_registered_extension_path(bad) is None

    def test_repo_registration_is_detected(self):
        assert install_paths.points_into_repo(BRIDGE / "extension") is True
        assert install_paths.points_into_repo(install_paths.stable_extension_dir()) is False
        assert install_paths.points_into_repo(None) is False


class TestSync:
    def test_sync_writes_all_files_and_removes_stale(self, tmp_path):
        target = tmp_path / "extension"
        target.mkdir()
        stale = target / "old-renamed-asset.js"
        stale.write_text("stale", encoding="utf-8")
        proc = subprocess.run(
            [
                "node",
                "-e",
                "const p=require(process.argv[1]); const s=require(process.argv[2]); "
                "const r=s.sync({dir:process.argv[3],targetDir:process.argv[4]}); console.log(r.files.join(' '));",
                str(BRIDGE / "install_paths.js"),
                str(BRIDGE / "sync_extension.js"),
                str(anthropic.HERE),
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, proc.stderr
        for rel in ("manifest.json", "content.js", "service_worker.js", "tab_resolution.js", "popup.html", "popup.js",
                    "icons/icon-16.png", "generated/config.js"):
            assert (target / rel).is_file(), rel
        assert not stale.exists(), "a renamed asset must not linger in the install path"
        assert "old-renamed-asset.js" not in proc.stdout


class TestKeepaliveRegression:
    @pytest.mark.parametrize("module", [anthropic, google])
    def test_note_status_never_raises_and_dedupes(self, module, caplog):
        import logging

        keepalive = module.BridgeKeepalive(interval_s=3600.0)
        with caplog.at_level(logging.DEBUG, logger=module._copy.LOG_NAME):
            keepalive._note_status({"browser": "connected", "page": "ok"})
            keepalive._note_status({"browser": "connected", "page": "ok"})
            keepalive._note_status({"browser": "disconnected", "page": "unknown"})
        lines = [r.getMessage() for r in caplog.records if r.name == module._copy.LOG_NAME]
        assert len(lines) == 2, lines
        assert "browser=disconnected" in lines[1]

    def test_run_loop_uses_the_injected_logger(self):
        logger = MagicMock()
        status_fn = MagicMock(return_value={"browser": "connected", "page": "ok"})
        kl = keepalive.BridgeKeepalive(0.001, status_fn=status_fn, owns_cycle_fn=lambda: False, log=logger)
        kl._stop.wait = MagicMock(side_effect=[False, True])
        kl._run()
        logger.debug.assert_called_once()


class TestVerifierLiveRegistration:
    def test_live_bridge_counts_as_registered_before_chrome_flushes_prefs(
        self, monkeypatch, capsys, tmp_path, hermetic_source_config
    ):
        target = tmp_path / "extension"
        for rel in verifier.REQUIRED:
            file = target / rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("x", encoding="utf-8")
        (target / "generated" / "config.js").write_bytes(hermetic_source_config)
        monkeypatch.setattr(verifier.paths, "stable_extension_dir", lambda: target)
        monkeypatch.setattr(verifier.paths, "registered_extension_path", lambda: None)
        monkeypatch.setattr(verifier, "_live_bridge_connected", lambda: True)
        code = verifier.main()
        out = capsys.readouterr().out
        assert code == 0, out
        assert "loaded in the running Chrome" in out
        assert "install is healthy" in out
        assert "Load unpacked" not in out


class TestVerifierOutput:
    def test_not_registered_case(self, monkeypatch, capsys, tmp_path, hermetic_source_config):
        target = tmp_path / "extension"
        generated = target / "generated"
        generated.mkdir(parents=True)
        (generated / "config.js").write_bytes(hermetic_source_config)
        monkeypatch.setattr(verifier.paths, "stable_extension_dir", lambda: target)
        monkeypatch.setattr(verifier.paths, "registered_extension_path", lambda: None)
        # The live probe must never depend on a daemon running on this machine.
        monkeypatch.setattr(verifier, "_live_bridge_connected", lambda: False)
        code = verifier.main()
        out = capsys.readouterr().out
        assert code != 0
        assert "Chrome registration" in out and "not registered" in out
        assert "Load unpacked" in out and str(target) in out

    def test_healthy_case(self, monkeypatch, capsys, tmp_path, hermetic_source_config):
        target = tmp_path / "extension"
        for rel in verifier.REQUIRED:
            file = target / rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("x", encoding="utf-8")
        (target / "generated" / "config.js").write_bytes(hermetic_source_config)
        monkeypatch.setattr(verifier.paths, "stable_extension_dir", lambda: target)
        monkeypatch.setattr(verifier.paths, "registered_extension_path", lambda: str(target))
        monkeypatch.setattr(verifier, "_live_bridge_connected", lambda: False)
        code = verifier.main()
        out = capsys.readouterr().out
        assert code == 0, out
        assert "install is healthy" in out
        assert "reload the extension" in out


class TestSingleChromeInstance:
    @pytest.mark.parametrize(
        ("platform", "url"), [("claude", "https://claude.ai/new"), ("gemini", "https://gemini.google.com/app")]
    )
    def test_arg_vector_is_identical_except_the_url(self, platform, url):
        args = chrome_profile.profile_args(chrome_profile.PROFILE_DIR, url)
        assert args == [
            f"--user-data-dir={chrome_profile.PROFILE_DIR}",
            "--profile-directory=Default",
            url,
        ]
        chrome_profile._assert_plain(args)
        with pytest.raises(ValueError):
            chrome_profile._assert_plain(args + ["--load-extension=C:/anywhere"])

    def test_switching_plugins_hands_the_port_back(self):
        with patch.object(anthropic, "_post") as a_post, patch.object(google, "_post") as g_post:
            anthropic.deactivate()
            google.deactivate()
        a_post.assert_called_once()
        g_post.assert_called_once()
        for post in (a_post, g_post):
            assert post.call_args.args[0] == "/shutdown"
        assert anthropic.DAEMON_URL == google.DAEMON_URL
