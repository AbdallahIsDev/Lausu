"""Facade re-exports, patch seams and enumeration parity of the Wave 7 split modules.

Wave 7 decomposed three recording-package facades (create-first splits):

* ``device_manager`` moved its resolution + health concerns onto
  ``_DeviceResolutionMixin`` / ``_DeviceHealthMixin`` (``device_resolution``,
  ``device_health``); the facade keeps ``DeviceManager`` composed from both.
* ``recording_lifecycle`` moved ``start_recording`` onto ``recording_start``;
  the facade keeps ``stop_recording`` / ``discard_recording`` plus the
  session-memo globals the moved body mutates through the facade.
* ``capture`` moved the audio-worker trio onto ``_AudioWorkerMixin``
  (``capture_audio_worker``); the facade keeps the RT callback dispatch and
  the IPC event worker.

Three contracts must hold, mirroring the wave-2..6 close-out files:

1. every moved symbol is the SAME object as the one owned by its sibling
   module (the facade and ``Recorder`` re-exports resolve through the
   mixins without a second definition);
2. runtime lookups that tests monkeypatch ON the facade are still read at
   call time by the moved code (``device_manager.sd``,
   ``recording_lifecycle.refresh_vad_caches`` / ``prepare_audio``,
   ``capture.ensure_mono`` / ``capture._DRAIN_STOP_CHECK_INTERVAL``);
3. device enumeration output (order + content) is exactly the pre-split
   list, the expectation below was captured from the git-HEAD (pre-split)
   implementation and verified equal to the post-split facade.
"""

from __future__ import annotations

import collections
import threading
from unittest.mock import MagicMock

import numpy as np

# PortAudio-style device table exercising every enumeration boundary:
# a normal input, an output-only device, a same-name device on another host
# API (kept: no name-only dedup, C-MIC-7), a placeholder endpoint and a
# whitespace-only name (both filtered), plus a second real input.
_DEVICE_FIXTURE = (
    {"name": "Microphone (USB Audio Device)", "max_input_channels": 2, "default_samplerate": 48000.0, "hostapi": 0},
    {"name": "Speakers (Realtek(R) Audio)", "max_input_channels": 0, "default_samplerate": 48000.0, "hostapi": 0},
    {"name": "Blue Yeti", "max_input_channels": 1, "default_samplerate": 44100.0, "hostapi": 1},
    {"name": "Input ()", "max_input_channels": 1, "default_samplerate": 48000.0, "hostapi": 0},
    {"name": "   ", "max_input_channels": 1, "default_samplerate": 48000.0, "hostapi": 0},
    {"name": "Blue Yeti", "max_input_channels": 1, "default_samplerate": 44100.0, "hostapi": 2},
    {"name": "Line In (Realtek(R) Audio)", "max_input_channels": 1, "default_samplerate": 48000.0, "hostapi": 3},
)

# Captured from the pre-split (git-HEAD) ``DeviceManager._refresh_device_list``
# against _DEVICE_FIXTURE; verified equal to the post-split facade output.
_PRE_SPLIT_DEVICE_LIST = [
    {
        "index": 0,
        "name": "Microphone (USB Audio Device)",
        "max_input_channels": 2,
        "default_samplerate": 48000.0,
        "hostapi": 0,
    },
    {"index": 2, "name": "Blue Yeti", "max_input_channels": 1, "default_samplerate": 44100.0, "hostapi": 1},
    {"index": 5, "name": "Blue Yeti", "max_input_channels": 1, "default_samplerate": 44100.0, "hostapi": 2},
]


def _make_device_manager():
    """Build a bare ``DeviceManager`` without the watcher-thread ``__init__``."""
    from voice_typer.server.recording import device_manager

    dm = device_manager.DeviceManager.__new__(device_manager.DeviceManager)
    dm._mic_watcher = None
    dm._device_list_cache = None
    dm._device_list_cache_time = 0.0
    dm._device_list_cache_ttl = 30.0
    return dm


class _FakeSd:
    """``sounddevice`` stand-in; records the calls the moved code makes."""

    def __init__(self, devices=()) -> None:
        self._devices = devices
        self.calls: list[tuple] = []

    def query_devices(self, *args, **kwargs):
        self.calls.append(("query_devices", args, kwargs))
        return [dict(d) for d in self._devices]

    def query_hostapis(self, index):
        self.calls.append(("query_hostapis", index))
        return {"name": "Windows WASAPI"}


class _MinimalPrerollRecorder:
    """Minimal recorder for the pre-roll dispatch branch (no model, no RT)."""

    def __init__(self) -> None:
        self._recording_event = threading.Event()  # not set → pre-roll branch
        self._preroll_active = True
        self._preroll_buffer: collections.deque = collections.deque(maxlen=100)


class _StopOnFirstChunkRecorder:
    """Recorder whose first processed chunk sets the worker stop event."""

    def __init__(self, chunks: int = 5) -> None:
        self._ring_buffer: collections.deque = collections.deque((i,) for i in range(chunks))
        self._worker_stop_event = threading.Event()
        self._worker_wake_event = threading.Event()
        self._session_state = MagicMock()  # no-op prepend_preroll_to_buffer
        self.processed: list[tuple] = []

    def _process_audio_chunk(self, *args) -> None:
        self.processed.append(args)
        self._worker_stop_event.set()


class TestDeviceSplitReexports:
    def test_mixins_resolve_to_the_sibling_modules(self):
        from voice_typer.server.recording import device_health, device_manager, device_resolution

        assert device_manager._DeviceHealthMixin is device_health._DeviceHealthMixin
        assert device_manager._DeviceResolutionMixin is device_resolution._DeviceResolutionMixin

    def test_moved_methods_resolve_to_their_sibling_mixins(self):
        from voice_typer.server.recording import device_health, device_manager, device_resolution

        moved = {
            device_health._DeviceHealthMixin: (
                "_start_device_health_checker",
                "_stop_device_health_checker",
                "stop_device_health_checker",
                "_device_health_checker_loop",
                "_effective_device_check_interval_s",
                "record_stream_open_default_input_index",
                "_check_default_input_device_changed",
                "_verify_post_restart_sample_rate",
                "_detect_sample_rate_drift",
                "_check_microphone_permission_revoked",
            ),
            device_resolution._DeviceResolutionMixin: (
                "_build_device_info_for_retry_policy",
                "_get_max_retries_for_device",
                "_get_retry_sleep_for_device",
                "_host_api_name",
                "_canonical_default_index",
                "_cached_device_info",
                "_device_index",
                "_same_physical_microphone_candidates",
                "_fallback_host_rank",
                "_resolve_effective_sample_rate",
                "_all_input_device_candidates",
            ),
        }
        for mixin, names in moved.items():
            for name in names:
                assert getattr(device_manager.DeviceManager, name) is getattr(mixin, name), name

    def test_host_owned_methods_stay_on_the_facade(self):
        from voice_typer.server.recording import device_manager

        for name in (
            "__init__",
            "_refresh_device_list",
            "_resolve_device",
            "set_service_cache_invalidator",
            "_invalidate_device_cache",
            "shutdown_mic_watcher",
        ):
            assert getattr(device_manager.DeviceManager, name).__module__ == (
                "voice_typer.server.recording.device_manager"
            ), name


class TestDevicePatchSeams:
    def test_moved_code_reads_sd_from_the_facade_at_call_time(self, monkeypatch):
        from voice_typer.server.recording import device_manager

        fake_sd = _FakeSd()
        monkeypatch.setattr(device_manager, "sd", fake_sd)

        dm = _make_device_manager()
        dm._host_api_cache = {}
        assert dm._host_api_name(0) == "Windows WASAPI"
        assert ("query_hostapis", 0) in fake_sd.calls

        # Same patched facade global through the resolution sibling.
        assert dm._all_input_device_candidates() == []
        assert any(call[0] == "query_devices" for call in fake_sd.calls)


class TestDeviceEnumerationParity:
    def test_device_list_matches_pre_split_order_and_content(self, monkeypatch):
        from voice_typer.server.recording import device_manager

        monkeypatch.setattr(device_manager, "sd", _FakeSd(_DEVICE_FIXTURE))
        assert _make_device_manager()._refresh_device_list() == _PRE_SPLIT_DEVICE_LIST

    def test_empty_device_table_stays_empty(self, monkeypatch):
        from voice_typer.server.recording import device_manager

        monkeypatch.setattr(device_manager, "sd", _FakeSd(()))
        assert _make_device_manager()._refresh_device_list() == []


class TestLifecycleSplitReexports:
    def test_start_recording_resolves_to_the_sibling_module(self):
        from voice_typer.server.recording import recording_lifecycle, recording_start

        assert recording_lifecycle.start_recording is recording_start.start_recording

    def test_facade_kept_seams_resolve_to_their_owners(self):
        from voice_typer.server.recording import recording_lifecycle
        from voice_typer.server.recording.format import prepare_audio
        from voice_typer.server.recording.vad_helpers import refresh_vad_caches

        assert recording_lifecycle.prepare_audio is prepare_audio
        assert recording_lifecycle.refresh_vad_caches is refresh_vad_caches

    def test_stop_and_discard_stay_on_the_facade(self):
        from voice_typer.server.recording import recording_lifecycle

        for name in (
            "stop_recording",
            "discard_recording",
            "_reset_session_device_memo",
            "_prefer_session_last_good_device",
            "_remember_session_device",
            "_device_display_name",
        ):
            assert getattr(recording_lifecycle, name).__module__ == (
                "voice_typer.server.recording.recording_lifecycle"
            ), name


class TestLifecyclePatchSeams:
    def test_start_recording_reads_refresh_vad_caches_from_the_facade_and_updates_its_memo(self, monkeypatch):
        from voice_typer.server.recording import recording_lifecycle
        from voice_typer.server.recording.recording_lifecycle import start_recording

        from tests.test_recorder_split_start import build_mock_recorder

        refresh = MagicMock(name="refresh_vad_caches")
        monkeypatch.setattr(recording_lifecycle, "refresh_vad_caches", refresh)
        recording_lifecycle._reset_session_device_memo()
        try:
            recorder = build_mock_recorder()
            start_recording(recorder)
            memo = recording_lifecycle._SESSION_LAST_GOOD_DEVICE
        finally:
            recording_lifecycle._reset_session_device_memo()

        refresh.assert_called_once_with(recorder)
        assert memo == 5

    def test_stop_recording_reads_prepare_audio_from_the_facade(self, monkeypatch):
        from voice_typer.server.recording import recording_lifecycle
        from voice_typer.server.recording.recording_lifecycle import stop_recording

        from tests.fixtures.ipc_test_helpers import build_mock_recorder

        captured_sr: list[int] = []

        def spy(recorder, audio, effective_sr, **kwargs):
            captured_sr.append(effective_sr)
            return audio

        monkeypatch.setattr(recording_lifecycle, "prepare_audio", spy)
        recorder = build_mock_recorder()
        result = stop_recording(recorder)

        assert captured_sr == [16000]
        assert result is not None


class TestCaptureSplitReexports:
    def test_audio_worker_mixin_resolves_to_the_sibling_module(self):
        from voice_typer.server.recording import capture, capture_audio_worker

        assert capture._AudioWorkerMixin is capture_audio_worker._AudioWorkerMixin

    def test_audio_worker_bodies_resolve_to_the_mixin(self):
        from voice_typer.server.recording import capture, capture_audio_worker

        for name in ("audio_worker_loop", "start_audio_worker_body", "stop_audio_worker_body"):
            assert getattr(capture.AudioCallbackDispatcher, name) is getattr(
                capture_audio_worker._AudioWorkerMixin, name
            ), name

    def test_callback_and_event_worker_bodies_stay_on_the_facade(self):
        from voice_typer.server.recording import capture

        for name in (
            "__init__",
            "dispatch_callback_body",
            "_dispatch_callback_body_inner",
            "_drain_event_queue",
            "start_event_worker_body",
            "stop_event_worker_body",
            "event_worker_loop",
            "surface_ring_overflow_warning",
        ):
            assert getattr(capture.AudioCallbackDispatcher, name).__module__ == (
                "voice_typer.server.recording.capture"
            ), name

    def test_dispatcher_mro_composes_the_mixin(self):
        from voice_typer.server.recording import capture

        assert [cls.__name__ for cls in capture.AudioCallbackDispatcher.__mro__] == [
            "AudioCallbackDispatcher",
            "_AudioWorkerMixin",
            "object",
        ]

    def test_drain_interval_stays_owned_by_the_facade(self):
        from voice_typer.server.recording import capture

        assert capture._DRAIN_STOP_CHECK_INTERVAL == 4


class TestCapturePatchSeams:
    def test_preroll_path_reads_ensure_mono_from_the_facade(self, monkeypatch):
        from voice_typer.server.recording import capture
        from voice_typer.server.recording.capture import AudioCallbackDispatcher

        calls: list[np.ndarray] = []
        real = capture.ensure_mono

        def spy(recorder, audio):
            calls.append(audio)
            return real(recorder, audio)

        monkeypatch.setattr(capture, "ensure_mono", spy)
        recorder = _MinimalPrerollRecorder()
        indata = np.zeros((4, 2), dtype=np.float32)

        assert AudioCallbackDispatcher(recorder).dispatch_callback_body(recorder, indata, 4, "t", "s") is None
        assert len(calls) == 1
        assert len(recorder._preroll_buffer) == 1

    def test_moved_audio_worker_loop_reads_drain_interval_from_the_facade(self, monkeypatch):
        """The moved loop must read the facade's interval at call time (C-ARCH-2 seam).

        With the facade interval patched to 1, the stop event is checked after
        every chunk, so the loop bails out right after the first chunk sets it.
        A stale module-local interval (4) would process 4 chunks instead.
        """
        from voice_typer.server.recording import capture
        from voice_typer.server.recording.capture import AudioCallbackDispatcher

        monkeypatch.setattr(capture, "_DRAIN_STOP_CHECK_INTERVAL", 1)
        recorder = _StopOnFirstChunkRecorder(chunks=5)

        AudioCallbackDispatcher(recorder).audio_worker_loop(recorder)

        assert len(recorder.processed) == 1

    def test_dispatcher_class_stays_patchable_on_the_facade(self):
        from unittest.mock import patch

        with patch("voice_typer.server.recording.capture.AudioCallbackDispatcher") as mock_cls:
            from voice_typer.server.recording import capture

            assert capture.AudioCallbackDispatcher is mock_cls
