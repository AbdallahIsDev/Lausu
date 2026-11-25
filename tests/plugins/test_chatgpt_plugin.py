"""The ChatGPT (OpenAI) platform plugin.

Pins the seams that make the ChatGPT plugin a THIRD member of the shared
Chrome-extension bridge rather than a fork of it: one daemon, one profile,
one port, one token store, one extension -- and one selector set of its own.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = ROOT / "tools" / "internal_plugins"
BRIDGE = PLUGINS / "_common" / "bridge"
CHATGPT = PLUGINS / "chatgpt_stt"


def _manifest() -> dict:
    return json.loads((CHATGPT / "plugin.json").read_text(encoding="utf-8"))


def _descriptor() -> dict:
    return json.loads((CHATGPT / "config.example.json").read_text(encoding="utf-8"))


class TestManifest:
    def test_manifest_declares_the_openai_platform(self) -> None:
        manifest = _manifest()
        assert manifest["id"] == "chatgpt_stt"
        assert manifest["name"] == "ChatGPT STT"
        assert manifest["vendor"] == "OpenAI"
        assert manifest["description"]

    def test_manifest_id_is_a_valid_slug(self) -> None:
        """The registry rejects an id outside ``[a-z0-9_-]``."""
        from voice_typer.server.plugins.registry import _valid_id

        assert _valid_id(_manifest()["id"]) is True

    def test_manifest_declares_no_settings(self) -> None:
        """C-PLUGIN-2: a manifest declares identity, never settings."""
        manifest = _manifest()
        for key in ("settings", "config", "options", "preferences"):
            assert key not in manifest

    def test_icon_falls_back_to_the_initial_tile(self) -> None:
        """No bundled vendor asset ships for this plugin.

        The card renders the name's initial when the icon id resolves to
        nothing, so an empty id is the honest choice: it never points at an
        asset that is not in the tree.
        """
        assert _manifest()["icon"] == ""


class TestDescriptor:
    def test_descriptor_is_a_chatgpt_platform_descriptor(self) -> None:
        descriptor = _descriptor()
        assert descriptor["platform"] == "chatgpt"
        assert descriptor["url"] == "https://chatgpt.com/"
        assert descriptor["chatgptUrl"] == "https://chatgpt.com/"
        assert descriptor["port"] == 17875
        assert descriptor["selectorsRef"].endswith("chatgpt.json")

    def test_descriptor_shares_the_one_profile_and_port(self) -> None:
        from tests.plugins.profile_path_helpers import assert_shared_profile

        descriptor = _descriptor()
        assert_shared_profile(descriptor["profileDir"])
        assert descriptor["port"] == 17875


class TestHookRegistration:
    def test_hook_maps_the_id_to_the_module(self) -> None:
        from voice_typer.server import internal_plugin_hook as hook

        assert hook.PLUGIN_MODULES["chatgpt_stt"] == "tools.internal_plugins.chatgpt_stt.plugin"

    def test_the_module_imports_and_exposes_the_seam(self) -> None:
        from tools.internal_plugins.chatgpt_stt import plugin as chatgpt

        for name in (
            "attach",
            "detach",
            "activate",
            "deactivate",
            "ensure_daemon",
            "plugins_enabled",
            "handle_escape",
            "shutdown_daemon",
        ):
            assert callable(getattr(chatgpt, name)), name
        assert chatgpt.DISPLAY_NAME == "ChatGPT STT"

    def test_daemon_is_spawned_with_the_chatgpt_platform(self) -> None:
        from tools.internal_plugins.chatgpt_stt import plugin as chatgpt

        assert chatgpt._CLIENT.daemon_args == (
            f"--plugin-dir={CHATGPT}",
            "--platform=chatgpt",
        )
        assert Path(chatgpt._CLIENT.daemon_script) == BRIDGE / "run.js"
        assert chatgpt.DAEMON_URL.endswith(":17875")


class TestSharedTransport:
    def test_the_plugin_carries_no_second_transport(self) -> None:
        for rel in (
            "run.js",
            "relay.js",
            "control_plane.js",
            "config_store.py",
            "chrome_profile.py",
            "session.py",
            "extension",
        ):
            assert not (CHATGPT / rel).exists(), rel

    def test_the_extension_covers_the_chatgpt_origin(self) -> None:
        manifest = json.loads((BRIDGE / "extension" / "manifest.json").read_text(encoding="utf-8"))
        assert "https://chatgpt.com/*" in manifest["content_scripts"][0]["matches"]
        assert "https://chatgpt.com/*" in manifest["host_permissions"]

    def test_the_content_script_resolves_the_chatgpt_platform(self) -> None:
        content = (BRIDGE / "extension" / "content.js").read_text(encoding="utf-8")
        assert "chatgpt.com" in content
        assert "'chatgpt'" in content

    def test_the_service_worker_targets_the_chatgpt_tab(self) -> None:
        worker = (BRIDGE / "extension" / "service_worker.js").read_text(encoding="utf-8")
        assert "chatgpt: 'https://chatgpt.com/*'" in worker
        assert "chatgptUrl" in worker

    def test_the_control_plane_names_the_platform(self) -> None:
        plane = (BRIDGE / "control_plane.js").read_text(encoding="utf-8")
        assert "chatgpt: 'ChatGPT'" in plane

    def test_the_generator_compiles_the_chatgpt_selectors(self) -> None:
        generator = (BRIDGE / "tools" / "build-extension.js").read_text(encoding="utf-8")
        assert "const PLATFORMS = ['claude', 'gemini', 'chatgpt'];" in generator


class TestSelectors:
    def test_the_selector_set_exists_and_is_complete(self) -> None:
        selectors = json.loads((BRIDGE / "selectors" / "chatgpt.json").read_text(encoding="utf-8"))
        for key in (
            "chatgptUrl",
            "idleSlot",
            "composer",
            "micSelector",
            "stopSelector",
            "cancelSelector",
            "micButton",
            "recordingIndicator",
            "stopButton",
            "promptBox",
            "newChatNames",
        ):
            assert key in selectors, key

    def test_the_dictation_mic_never_matches_the_voice_orb(self) -> None:
        """ChatGPT shows a dictation mic AND a blue Voice orb.

        Clicking the Voice orb starts a live conversation instead of a
        dictation, so the mic selector must exclude it.
        """
        selectors = json.loads((BRIDGE / "selectors" / "chatgpt.json").read_text(encoding="utf-8"))
        mic = selectors["micSelector"]
        assert "voice-mode-button" not in mic
        assert "voice mode" in mic.lower()

    def test_the_composer_carries_more_than_one_candidate(self) -> None:
        """The composer id/testid drifts between releases."""
        selectors = json.loads((BRIDGE / "selectors" / "chatgpt.json").read_text(encoding="utf-8"))
        assert "#prompt-textarea" in selectors["composer"]
        assert "contenteditable" in selectors["composer"]

    def test_the_commit_and_the_discard_controls_are_distinct(self) -> None:
        """C-ASR-4: the live ChatGPT row exposes ONE dictating toggle. It is
        the commit/stop control; there is no separate discard control to
        collide with. The stable data attribute beats the drifting label.
        """
        selectors = json.loads((BRIDGE / "selectors" / "chatgpt.json").read_text(encoding="utf-8"))
        commit = selectors["stopSelector"]
        discard = selectors["cancelSelector"]
        assert commit, "ChatGPT needs a stop/commit control"
        assert 'button[data-dictation-button="dictating"]' in commit
        assert discard == "", "the live row has no separate discard control"
        assert commit != discard


class TestCopy:
    def test_the_copy_module_owns_the_vendor_words(self) -> None:
        from tools.internal_plugins.chatgpt_stt import copy

        assert copy.DISPLAY_NAME == "ChatGPT STT"
        assert copy.MODEL_LABEL == "chatgpt-web"
        assert copy.START_HINTS
        for key, (hint, *_rest) in copy.START_HINTS.items():
            assert hint, key

    def test_the_start_hints_never_name_another_platform(self) -> None:
        from tools.internal_plugins.chatgpt_stt import copy

        joined = " ".join(hint for hint, *_rest in copy.START_HINTS.values()).lower()
        assert "gemini" not in joined
        assert "claude" not in joined


class TestSession:
    def test_the_session_uses_the_chatgpt_copy(self) -> None:
        from unittest.mock import MagicMock

        from tools.internal_plugins.chatgpt_stt import plugin as chatgpt

        app = SimpleNamespace(tray=MagicMock())
        session = chatgpt.PluginSession(app)
        session._notify("hello")
        app.tray.notify.assert_called_once_with("ChatGPT STT (internal)", "hello")
