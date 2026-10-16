"""S5 capture-side volume backend tests (mic guard platform layer).

The speaker-side backends are covered by ``tests/test_volume_backends.py``;
this file covers the capture-side siblings plus the factory wiring, so the
mic guard never depends on an untested platform shim.
"""

from __future__ import annotations

import sys
from unittest.mock import patch

from voice_typer.server import volume_backends as vb
from voice_typer.server.server_platform import platform_flags
from voice_typer.server.volume_backends import (
    LinuxMicVolumeBackend,
    MacMicVolumeBackend,
    WinMicVolumeBackend,
)


class TestLinuxMicBackend:
    """S5: the capture-side Linux backend (pactl / wpctl / amixer)."""

    @staticmethod
    def _backend(tool: str, outputs: dict[str, str]):
        b = LinuxMicVolumeBackend()
        b._tool = tool
        calls: list[list[str]] = []

        def fake_run(cmd, timeout=2.0):
            calls.append(list(cmd))
            for needle, out in outputs.items():
                if needle in cmd:
                    return out
            return None

        b._run = fake_run
        return b, calls

    def test_pactl_reads_the_default_source(self):
        b, calls = self._backend(
            "pactl",
            {"get-source-volume": "Volume: front-left: 32768 / 50% / -18.06 dB"},
        )
        assert b.get_level() == 0.5
        assert "get-source-volume" in calls[0]
        assert "@DEFAULT_SOURCE@" in calls[0]

    def test_pactl_writes_the_default_source_as_percent(self):
        b, calls = self._backend("pactl", {"set-source-volume": ""})
        assert b.set_level(1.0) is True
        assert "set-source-volume" in calls[0]
        assert "100%" in calls[0]

    def test_pactl_clamps_above_full_scale(self):
        b, calls = self._backend("pactl", {"set-source-volume": ""})
        b.set_level(1.7)
        assert "100%" in calls[0]

    def test_wpctl_reads_the_default_audio_source(self):
        b, calls = self._backend("wpctl", {"get-volume": "Volume: 0.60"})
        assert b.get_level() == 0.6
        assert "@DEFAULT_AUDIO_SOURCE@" in calls[0]

    def test_wpctl_writes_a_float(self):
        b, calls = self._backend("wpctl", {"set-volume": ""})
        assert b.set_level(0.25) is True
        assert "set-volume" in calls[0]
        assert "0.25" in calls[0]

    def test_amixer_reads_the_capture_control(self):
        b, calls = self._backend("amixer", {"sget": "Capture: 80% [80%] [on]"})
        assert b.get_level() == 0.8
        assert "Capture" in calls[0]

    def test_amixer_writes_the_capture_control(self):
        b, calls = self._backend("amixer", {"sset": ""})
        assert b.set_level(0.5) is True
        assert "sset" in calls[0]
        assert "Capture" in calls[0]

    def test_a_failed_read_returns_none(self):
        b, _ = self._backend("pactl", {})
        assert b.get_level() is None

    def test_a_failed_write_returns_false(self):
        b, _ = self._backend("pactl", {})
        assert b.set_level(1.0) is False

    def test_uninitialized_backend_cannot_set(self):
        b = LinuxMicVolumeBackend()
        assert b._tool is None
        assert b.supports_set is False
        assert b.set_level(1.0) is False
        assert b.get_level() is None

    def test_tool_detection_prefers_pactl(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda t: f"/usr/bin/{t}")
        b = LinuxMicVolumeBackend()
        assert b.initialize() is True
        assert b._tool == "pactl"
        assert b.supports_set is True

    def test_tool_detection_falls_back_to_wpctl(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda t: "/usr/bin/wpctl" if t == "wpctl" else None)
        b = LinuxMicVolumeBackend()
        assert b.initialize() is True
        assert b._tool == "wpctl"

    def test_tool_detection_falls_back_to_amixer(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda t: "/usr/bin/amixer" if t == "amixer" else None)
        b = LinuxMicVolumeBackend()
        assert b.initialize() is True
        assert b._tool == "amixer"

    def test_no_tool_means_initialize_fails(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _t: None)
        assert LinuxMicVolumeBackend().initialize() is False

    def test_reports_a_poll_floor_for_subprocess_reads(self):
        """Every read spawns a process, so the guard must not poll hot."""
        assert LinuxMicVolumeBackend().min_poll_interval_ms >= 2000

    def test_name_names_the_capture_side(self):
        b = LinuxMicVolumeBackend()
        b._tool = "pactl"
        assert "pactl" in b.name


class TestWinMicBackendSmoke:
    """S5: Windows capture backend, only the no-pycaw paths."""

    def test_supports_set_is_true(self):
        assert WinMicVolumeBackend().supports_set is True

    def test_initialize_returns_false_without_pycaw(self):
        b = WinMicVolumeBackend()
        with patch.dict(sys.modules, {"pycaw": None, "pycaw.pycaw": None, "comtypes": None}):
            assert b.initialize() is False

    def test_get_level_returns_none_when_uninitialized(self):
        assert WinMicVolumeBackend().get_level() is None

    def test_set_level_returns_false_when_uninitialized(self):
        assert WinMicVolumeBackend().set_level(0.5) is False

    def test_level_is_read_from_the_com_pointer(self):
        b = WinMicVolumeBackend()
        b._vol = type("Vol", (), {"GetMasterVolumeLevelScalar": lambda _s: 0.92})()
        assert b.get_level() == 0.92

    def test_write_goes_through_the_com_pointer(self):
        seen: list[tuple[float, object]] = []
        b = WinMicVolumeBackend()
        b._vol = type(
            "Vol",
            (),
            {"SetMasterVolumeLevelScalar": lambda _s, level, ctx: seen.append((level, ctx))},
        )()
        assert b.set_level(0.75) is True
        assert seen == [(0.75, None)]

    def test_write_clamps(self):
        seen: list[float] = []
        b = WinMicVolumeBackend()
        b._vol = type(
            "Vol",
            (),
            {"SetMasterVolumeLevelScalar": lambda _s, level, _ctx: seen.append(level)},
        )()
        b.set_level(1.9)
        assert seen == [1.0]


class TestMacMicBackend:
    """S5: macOS capture backend. Most built-in mics expose no settable gain."""

    def test_initialize_degrades_when_coreaudio_input_is_unavailable(self, monkeypatch):
        from voice_typer.server.volume_backends import macos as macos_mod

        monkeypatch.setattr(macos_mod, "_try_import_coreaudio_input", lambda: None)
        b = MacMicVolumeBackend()
        assert b.initialize() is False
        assert b.supports_set is False

    def test_initialize_degrades_on_import_error(self, monkeypatch):
        from voice_typer.server.volume_backends import macos as macos_mod

        def boom():
            raise ImportError("pyobjc-framework-CoreAudio missing")

        monkeypatch.setattr(macos_mod, "_try_import_coreaudio_input", boom)
        b = MacMicVolumeBackend()
        assert b.initialize() is False
        assert b.get_level() is None

    def test_read_only_device_reports_supports_set_false(self, monkeypatch):
        """Message-only path: never pretend a write the OS will ignore."""
        from voice_typer.server.volume_backends import macos as macos_mod

        monkeypatch.setattr(macos_mod, "_try_import_coreaudio_input", lambda: object())
        b = MacMicVolumeBackend()
        # No resolvable default input device → the read cannot succeed.
        b._ca = object()
        monkeypatch.setattr(b, "_default_input_device", lambda: None)

        assert b.get_level() is None
        assert b.set_level(1.0) is False
        assert b.supports_set is False

    def test_a_refused_write_downgrades_settable(self, monkeypatch):
        b = MacMicVolumeBackend()

        class _Ca:
            prop_default_input_device = 1
            prop_volume_scalar = 2
            scope_global = 3
            scope_input = 4
            element_master = 5
            system_object = 6

            @staticmethod
            def set_property(*_args):
                return -50  # kAudioHardwareUnknownPropertyError

        b._ca = _Ca()
        b._settable = True
        monkeypatch.setattr(b, "_default_input_device", lambda: 42)

        assert b.set_level(1.0) is False
        assert b.supports_set is False, "a refused write must downgrade supports_set, not pretend success"

    def test_a_refused_write_on_the_first_call_also_downgrades(self, monkeypatch):
        b = MacMicVolumeBackend()
        b._ca = None
        assert b.set_level(1.0) is False


class TestMicVolumeFactory:
    """``get_mic_volume_backend`` mirrors ``get_volume_backend``."""

    def test_returns_none_on_unsupported_platform(self, monkeypatch):
        monkeypatch.setattr(platform_flags, "SYSTEM", "freebsd")
        assert vb is not None  # keep the import used
        from voice_typer.server.server_platform import volume_factory

        assert volume_factory.get_mic_volume_backend() is None

    def test_win32_maps_to_the_windows_mic_backend(self, monkeypatch):
        from voice_typer.server.server_platform import volume_factory

        monkeypatch.setattr(platform_flags, "SYSTEM", "win32")
        assert isinstance(volume_factory.get_mic_volume_backend(), WinMicVolumeBackend)

    def test_darwin_maps_to_the_macos_mic_backend(self, monkeypatch):
        from voice_typer.server.server_platform import volume_factory

        monkeypatch.setattr(platform_flags, "SYSTEM", "darwin")
        assert isinstance(volume_factory.get_mic_volume_backend(), MacMicVolumeBackend)

    def test_linux_maps_to_the_linux_mic_backend(self, monkeypatch):
        from voice_typer.server.server_platform import volume_factory

        monkeypatch.setattr(platform_flags, "SYSTEM", "linux")
        assert isinstance(volume_factory.get_mic_volume_backend(), LinuxMicVolumeBackend)
