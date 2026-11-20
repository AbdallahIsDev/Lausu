"""Headless macOS bundle preflight contract (host-validation automation)."""

from __future__ import annotations

import json
import plistlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SRC_TAURI = REPO / "src-tauri"
WORKFLOW = REPO / ".github" / "workflows" / "host-validation.yml"
SWIFT_SRC = REPO / "voice_typer" / "server" / "native" / "macos-key-listener.swift"
MANIFEST = REPO / "voice_typer" / "server" / "native" / "binaries.json"


def _info_plist() -> dict:
    return plistlib.loads((SRC_TAURI / "Info.plist").read_bytes())


def _entitlements() -> dict:
    return plistlib.loads((SRC_TAURI / "entitlements.plist").read_bytes())


class TestInfoPlistPartial:
    def test_required_usage_keys_present(self) -> None:
        info = _info_plist()
        for key in (
            "NSMicrophoneUsageDescription",
            "NSUserNotificationsUsageDescription",
            "NSAppleEventsUsageDescription",
            "LSMinimumSystemVersion",
        ):
            assert key in info, f"Info.plist missing {key}"
            assert isinstance(info[key], str) and info[key].strip(), f"Info.plist {key} must be a non-empty string"

    def test_minimum_system_version(self) -> None:
        info = _info_plist()
        assert info["LSMinimumSystemVersion"] == "13.0"


class TestEntitlements:
    def test_required_hardened_runtime_keys(self) -> None:
        ent = _entitlements()
        for key in (
            "com.apple.security.cs.allow-jit",
            "com.apple.security.cs.allow-unsigned-executable-memory",
            "com.apple.security.cs.disable-library-validation",
            "com.apple.security.device.audio-input",
            "com.apple.security.automation.apple-events",
        ):
            assert key in ent, f"entitlements.plist missing {key}"

    def test_no_notification_entitlement(self) -> None:
        ent = _entitlements()
        assert not any("notification" in key for key in ent), "entitlements must not carry a notification entitlement"


class TestTauriMacosConfigParity:
    def test_base_config_macos_block(self) -> None:
        conf = json.loads((SRC_TAURI / "tauri.conf.json").read_text(encoding="utf-8"))
        mac = conf["bundle"]["macOS"]
        assert mac["minimumSystemVersion"] == "13.0"
        assert mac["minimumSystemVersion"] == _info_plist()["LSMinimumSystemVersion"]
        assert mac["entitlements"] == "entitlements.plist"
        assert mac["infoPlist"] == "Info.plist"
        assert (SRC_TAURI / mac["entitlements"]).is_file()
        assert (SRC_TAURI / mac["infoPlist"]).is_file()

    def test_per_arch_config_ships_native_listener(self) -> None:
        mconf = json.loads((SRC_TAURI / "tauri.macos.conf.json").read_text(encoding="utf-8"))
        assert "resources/native/macos-key-listener" in mconf["bundle"]["resources"]


class TestNativeManifestMacosEntry:
    def test_macos_entry_contract(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entry = manifest["binaries"].get("macos-key-listener")
        assert entry is not None, "macos manifest entry missing"
        assert entry.get("version"), "macos manifest version missing"
        assert "min_proto_version" in entry, "macos manifest min_proto_version missing"


class TestSwiftSourceContract:
    def test_wire_protocol_markers(self) -> None:
        text = SWIFT_SRC.read_text(encoding="utf-8")
        for needle in (
            "CGEvent",
            "READY",
            "VERSION:",
            "VOICE_TYPER_SKIP_ACCESSIBILITY_CHECK",
            "PING",
            "NSEvent",
            "tapCreate",
        ):
            assert needle in text, f"swift source missing {needle}"


class TestWorkflowPinsNewSteps:
    def test_workflow_contains_headless_runnable_steps(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "runs-on: macos-15" in text
        assert "swiftc -O" in text
        assert "VOICE_TYPER_SKIP_ACCESSIBILITY_CHECK" in text
        assert "LISTENER_SMOKE=SKIPPED_NO_TCC" in text
        assert "plutil -lint" in text
        assert "NSAppleEventsUsageDescription" in text
        assert "xcrun notarytool --help" in text
        assert "test_clipboard_snapshot.py" in text
        assert "test_macos_bundle_preflight.py" in text
        assert "test_clipboard_macos_capture.py" in text
        assert "actions/checkout@v5" in text
        assert "actions/setup-python@v7" in text
        assert "actions/upload-artifact@v6" in text


class TestFfmpegBundleScopeNotLeakedToMacos:
    """The win64-only LGPL ffmpeg must not leak into base/macOS/Linux configs."""

    @staticmethod
    def _external_bin(name: str) -> list[str]:
        cfg = json.loads((SRC_TAURI / name).read_text(encoding="utf-8"))
        return cfg.get("bundle", {}).get("externalBin", [])

    def test_media_binaries_are_windows_x64_only(self) -> None:
        for name in (
            "tauri.conf.json",
            "tauri.macos.conf.json",
            "tauri.linux-x86_64.conf.json",
            "tauri.linux-aarch64.conf.json",
            "tauri.windows-aarch64.conf.json",
        ):
            path = SRC_TAURI / name
            if not path.is_file():
                continue
            leaked = [e for e in self._external_bin(name) if "ffmpeg" in e or "ffprobe" in e]
            assert not leaked, f"{name} must not declare media binaries (Windows x64 only): {leaked}"

    def test_no_config_declares_ffprobe(self) -> None:
        for path in sorted(SRC_TAURI.glob("tauri*.conf.json")):
            leaked = [e for e in self._external_bin(path.name) if "ffprobe" in e]
            assert not leaked, f"{path.name} declares ffprobe but it is not shipped: {leaked}"
