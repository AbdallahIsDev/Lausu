"""One shared Chrome-extension bridge, two thin platform plugins.

No real browser, network or Node process: the seams are faked. The contract
pinned here is that both plugins spawn the SAME daemon with a platform
descriptor, share one profile/port/token authority, and keep their own copy.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from tools.internal_plugins._common import daemon as daemon_common
from tools.internal_plugins._common.bridge import chrome_profile, daemon_client
from tools.internal_plugins.anthropic_stt import plugin as anthropic
from tools.internal_plugins.google_stt import plugin as google

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = ROOT / "tools" / "internal_plugins"
BRIDGE = PLUGINS / "_common" / "bridge"


def _example(plugin: str) -> dict:
    return json.loads((PLUGINS / plugin / "config.example.json").read_text(encoding="utf-8"))


class TestOneSharedAuthority:
    @pytest.mark.parametrize(
        ("module", "plugin", "platform", "url"),
        [
            (anthropic, "anthropic_stt", "claude", "https://claude.ai/new"),
            (google, "google_stt", "gemini", "https://gemini.google.com/app"),
        ],
    )
    def test_descriptor_and_client(self, module, plugin, platform, url):
        descriptor = _example(plugin)
        assert descriptor["platform"] == platform
        assert descriptor["url"] == url
        assert descriptor["port"] == 17875
        assert descriptor["profileDir"] == chrome_profile.PROFILE_DIR
        assert descriptor["selectorsRef"].endswith(f"{platform}.json")
        assert module.DAEMON_URL.endswith(":17875")
        assert module._CLIENT.daemon_args == (
            f"--plugin-dir={module.HERE}",
            f"--platform={platform}",
        )
        assert Path(module._CLIENT.daemon_script) == BRIDGE / "run.js"

    def test_one_token_authority_and_both_selectors(self):
        assert (BRIDGE / "token.json").is_file()
        for name in ("claude", "gemini"):
            assert (BRIDGE / "selectors" / f"{name}.json").is_file()
        manifest = json.loads((BRIDGE / "extension" / "manifest.json").read_text(encoding="utf-8"))
        matches = manifest["content_scripts"][0]["matches"]
        assert matches == ["https://claude.ai/*", "https://gemini.google.com/*"]
        assert set(manifest["host_permissions"]) >= set(matches)

    def test_no_plugin_carries_a_second_transport(self):
        for name in ("anthropic_stt", "google_stt"):
            root = PLUGINS / name
            for rel in ("run.js", "relay.js", "control_plane.js", "config_store.py",
                        "chrome_profile.py", "session.py", "extension"):
                assert not (root / rel).exists(), f"{name} duplicated {rel}"


class TestDaemonSpawn:
    @pytest.mark.parametrize(
        ("module", "platform"), [(anthropic, "claude"), (google, "gemini")]
    )
    def test_spawns_the_shared_daemon_with_a_platform(self, module, platform):
        calls = []

        def fake_popen(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return SimpleNamespace(pid=4242)

        with (
            patch.object(daemon_common.subprocess, "Popen", fake_popen),
            patch.object(module, "_daemon_alive", lambda: False),
            patch.object(daemon_common.time, "sleep", lambda *_: None),
        ):
            # First probe says dead, then the liveness loop sees it up.
            answers = iter([False, True])
            with patch.object(module, "_daemon_alive", lambda: next(answers)):
                assert module.ensure_daemon() is True
        assert calls, "the daemon must be spawned"
        cmd = calls[0][0]
        assert cmd[0] == daemon_common.node_exe()
        assert Path(cmd[1]) == BRIDGE / "run.js"
        assert f"--platform={platform}" in cmd
        assert f"--plugin-dir={module.HERE}" in cmd
        assert Path(calls[0][1]["cwd"]) == BRIDGE


class TestPlatformGuards:
    def test_bridge_ready_rejects_another_platform(self):
        ready = daemon_client.DaemonClient.bridge_ready
        assert ready({"browser": "connected", "page": "ok", "platform": "claude"}) is True
        assert ready({"browser": "connected", "page": "ok", "state": "wrong-platform"}) is False

    @pytest.mark.parametrize("module", [anthropic, google])
    def test_visible_toggle_uses_the_plain_profile_launcher(self, module):
        seen = []
        original = chrome_profile._set_window_visible_fn
        chrome_profile._set_window_visible_fn = lambda pid, visible, wait: seen.append((pid, visible)) or True
        try:
            with patch.object(module, "_profile_visible", lambda: False), patch.object(
                module, "_launch_chrome", MagicMock(return_value=True)
            ) as launch:
                module.launch_profile(chrome_profile.PROFILE_DIR, "https://example.invalid/")
            assert launch.call_args.kwargs["visible"] is False
            assert launch.call_args.kwargs["plugin_dir"] == str(module.HERE)
        finally:
            chrome_profile._set_window_visible_fn = original
        assert seen == []  # launching is faked; no real window was touched

    @pytest.mark.parametrize(
        ("module", "display"), [(anthropic, "Anthropic STT"), (google, "Google STT")]
    )
    def test_notify_uses_each_plugins_copy(self, module, display):
        app = SimpleNamespace(tray=MagicMock())
        with patch.object(module._copy, "notify_enabled", lambda: True):
            session = module.PluginSession(app)
            session._notify("test message")
        app.tray.notify.assert_called_once_with(f"{display} (internal)", "test message")
