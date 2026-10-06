"""Facade re-exports of the Wave 3 split server modules keep resolving.

``streaming``, ``onboarding``, ``vad_processor``,
``level_monitor.test_recording`` and ``config_applier`` were split into
focused sibling modules. Callers (and tests) import names from the facades,
so two contracts must hold:

1. every moved symbol is re-exported by the facade as the SAME object as
   in its owning sibling module;
2. the runtime lookups that tests monkeypatch ON the facade
   (``onboarding.resolve_host_bundle_id``,
   ``test_recording._secure_clear_test_chunks`` /
   ``_test_recordings_dir``) are still read at call time by the sibling
   code.
"""

from __future__ import annotations


class TestStreamingFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server import (
            streaming,
            streaming_assembler,
            streaming_broadcaster,
            streaming_windows,
        )

        assert streaming.AudioWindow is streaming_windows.AudioWindow
        assert streaming.AudioWindowPlanner is streaming_windows.AudioWindowPlanner
        assert streaming.StreamingConfig is streaming_windows.StreamingConfig
        assert streaming.WordTiming is streaming_windows.WordTiming
        assert streaming.StreamingTextAssembler is streaming_assembler.StreamingTextAssembler
        assert (
            streaming.PartialTranscriptionBroadcaster
            is streaming_broadcaster.PartialTranscriptionBroadcaster
        )

    def test_session_worker_stays_on_the_facade(self):
        from voice_typer.server import streaming

        assert streaming.StreamingTranscriptionSession.__module__ == (
            "voice_typer.server.streaming"
        )


class TestOnboardingFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server import (
            onboarding,
            onboarding_permissions,
            onboarding_selections,
        )

        selections = onboarding_selections._OnboardingSelectionsMixin
        perms = onboarding_permissions._OnboardingPermissionsMixin
        assert onboarding.OnboardingController.__mro__[1] is selections
        assert onboarding.OnboardingController.__mro__[2] is perms
        assert onboarding.resolve_host_bundle_id.__module__.endswith("macos_bundle_id")

    def test_bundle_id_patch_on_facade_is_honoured(self, monkeypatch):
        from voice_typer.server import onboarding, onboarding_permissions, permissions
        from voice_typer.server.permissions import PermissionState

        seen = {}

        def fake_bundle_id():
            seen["called"] = True
            return "com.example.TestHost"

        monkeypatch.setattr(onboarding, "resolve_host_bundle_id", fake_bundle_id)
        monkeypatch.setattr(permissions, "is_windows", lambda: False)
        monkeypatch.setattr(permissions, "is_macos", lambda: True)
        monkeypatch.setattr(permissions, "is_linux", lambda: False)
        monkeypatch.setattr(
            permissions, "check_keyboard_permission", lambda: PermissionState.DENIED
        )
        controller = onboarding.OnboardingController.__new__(
            onboarding.OnboardingController
        )
        payload = onboarding_permissions._OnboardingPermissionsMixin.check_permissions(
            controller
        )
        assert seen.get("called") is True
        assert payload["platform"] == "macos"
        assert payload["needed"] is True
        commands = payload["instructions"]["commands"]
        assert commands == ["tccutil reset Accessibility com.example.TestHost"]


class TestVadProcessorFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server import vad_constants, vad_processor

        assert (
            vad_processor.DEFAULT_VAD_CALIBRATION_DURATION
            is vad_constants.DEFAULT_VAD_CALIBRATION_DURATION
        )
        assert (
            vad_processor.DEFAULT_VAD_HANGOVER_FRAMES
            is vad_constants.DEFAULT_VAD_HANGOVER_FRAMES
        )
        assert (
            vad_processor.DEFAULT_VAD_SILENCE_FRAMES
            is vad_constants.DEFAULT_VAD_SILENCE_FRAMES
        )
        assert (
            vad_processor.DEFAULT_VAD_SILENCE_PROB_THRESHOLD
            is vad_constants.DEFAULT_VAD_SILENCE_PROB_THRESHOLD
        )
        assert (
            vad_processor.DEFAULT_VAD_SILENCE_THRESHOLD_DB
            is vad_constants.DEFAULT_VAD_SILENCE_THRESHOLD_DB
        )
        assert (
            vad_processor.DEFAULT_VAD_SILERO_CALIBRATION_MARGIN
            is vad_constants.DEFAULT_VAD_SILERO_CALIBRATION_MARGIN
        )
        assert (
            vad_processor.DEFAULT_VAD_SILERO_SPEECH_DELTA
            is vad_constants.DEFAULT_VAD_SILERO_SPEECH_DELTA
        )
        assert (
            vad_processor.DEFAULT_VAD_SPEECH_FRAMES
            is vad_constants.DEFAULT_VAD_SPEECH_FRAMES
        )
        assert (
            vad_processor.DEFAULT_VAD_SPEECH_PROB_THRESHOLD
            is vad_constants.DEFAULT_VAD_SPEECH_PROB_THRESHOLD
        )
        assert (
            vad_processor.DEFAULT_VAD_SPEECH_THRESHOLD_DB
            is vad_constants.DEFAULT_VAD_SPEECH_THRESHOLD_DB
        )
        assert (
            vad_processor.MIN_VAD_SILENCE_THRESHOLD_DB
            is vad_constants.MIN_VAD_SILENCE_THRESHOLD_DB
        )
        assert (
            vad_processor.MIN_VAD_SILERO_THRESHOLD_SPREAD
            is vad_constants.MIN_VAD_SILERO_THRESHOLD_SPREAD
        )
        assert (
            vad_processor.MIN_VAD_SPEECH_THRESHOLD_DB
            is vad_constants.MIN_VAD_SPEECH_THRESHOLD_DB
        )

    def test_state_machine_stays_on_the_facade(self):
        from voice_typer.server import vad_processor

        assert vad_processor.VadState.__module__ == "voice_typer.server.vad_processor"
        assert vad_processor.VadProcessor.__module__ == (
            "voice_typer.server.vad_processor"
        )


class TestLevelMonitorTestRecordingFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server.level_monitor import (
            test_recording,
            test_recording_files,
            test_recording_lifecycle,
        )

        assert (
            test_recording._TEST_RECORDINGS_DIRNAME
            is test_recording_files._TEST_RECORDINGS_DIRNAME
        )
        assert (
            test_recording.MIC_TEST_RECORDING_TTL_SEC
            is test_recording_files.MIC_TEST_RECORDING_TTL_SEC
        )
        assert (
            test_recording._delete_expired_recordings
            is test_recording_files._delete_expired_recordings
        )
        assert (
            test_recording._delete_test_recording_paths
            is test_recording_files._delete_test_recording_paths
        )
        assert (
            test_recording._purge_test_recordings
            is test_recording_files._purge_test_recordings
        )
        assert (
            test_recording._remove_recordings_dir_if_empty
            is test_recording_files._remove_recordings_dir_if_empty
        )
        assert (
            test_recording._schedule_test_recording_expiry
            is test_recording_files._schedule_test_recording_expiry
        )
        assert (
            test_recording._test_recording_expiry_timers
            is test_recording_files._test_recording_expiry_timers
        )
        assert (
            test_recording._test_recordings_dir
            is test_recording_files._test_recordings_dir
        )
        assert test_recording._write_test_wav is test_recording_files._write_test_wav
        assert (
            test_recording.read_test_recording_slice
            is test_recording_files.read_test_recording_slice
        )
        assert (
            test_recording._begin_test_locked
            is test_recording_lifecycle._begin_test_locked
        )
        assert (
            test_recording._cancel_test_locked
            is test_recording_lifecycle._cancel_test_locked
        )
        assert (
            test_recording._do_auto_stop_test
            is test_recording_lifecycle._do_auto_stop_test
        )
        assert (
            test_recording._reset_test_chunks
            is test_recording_lifecycle._reset_test_chunks
        )
        assert (
            test_recording._secure_clear_test_chunks
            is test_recording_lifecycle._secure_clear_test_chunks
        )
        assert (
            test_recording.cancel_test_recording
            is test_recording_lifecycle.cancel_test_recording
        )
        assert test_recording.is_test_active is test_recording_lifecycle.is_test_active
        assert (
            test_recording.start_test_recording
            is test_recording_lifecycle.start_test_recording
        )
        assert (
            test_recording.update_test_filters
            is test_recording_lifecycle.update_test_filters
        )

    def test_stop_path_stays_on_the_facade(self):
        from voice_typer.server.level_monitor import test_recording

        assert test_recording.stop_test_recording.__module__.endswith(
            "level_monitor.test_recording"
        )


class TestConfigApplierFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server import config_applier, config_applier_handlers

        assert config_applier.ConfigSideEffect is config_applier_handlers.ConfigSideEffect
        assert (
            config_applier.SideEffectContext is config_applier_handlers.SideEffectContext
        )
        assert (
            config_applier.SideEffectStatus is config_applier_handlers.SideEffectStatus
        )
        assert (
            config_applier._FILTER_CHAIN_KEYS
            is config_applier_handlers._FILTER_CHAIN_KEYS
        )
        assert (
            config_applier._apply_audio_preset
            is config_applier_handlers._apply_audio_preset
        )
        assert (
            config_applier._AudioPresetHandler
            is config_applier_handlers._AudioPresetHandler
        )
        assert (
            config_applier._AutostartSyncHandler
            is config_applier_handlers._AutostartSyncHandler
        )
        assert (
            config_applier._BubbleBehaviorHandler
            is config_applier_handlers._BubbleBehaviorHandler
        )
        assert (
            config_applier._DictationHotkeyHandler
            is config_applier_handlers._DictationHotkeyHandler
        )
        assert (
            config_applier._EscHotkeyHandler
            is config_applier_handlers._EscHotkeyHandler
        )
        assert (
            config_applier._FilterChainHandler
            is config_applier_handlers._FilterChainHandler
        )
        assert (
            config_applier._NotificationsHandler
            is config_applier_handlers._NotificationsHandler
        )
        assert (
            config_applier._notify_side_effect_failure
            is config_applier_handlers._notify_side_effect_failure
        )
        assert (
            config_applier._PrewarmSyncHandler
            is config_applier_handlers._PrewarmSyncHandler
        )
        assert (
            config_applier._RepasteHotkeyHandler
            is config_applier_handlers._RepasteHotkeyHandler
        )
        assert (
            config_applier._TrayLeftClickHandler
            is config_applier_handlers._TrayLeftClickHandler
        )
        assert (
            config_applier._VolumeDuckPollHandler
            is config_applier_handlers._VolumeDuckPollHandler
        )
        assert config_applier.to_filter_dict is config_applier_handlers.to_filter_dict

    def test_apply_entrypoint_stays_on_the_facade(self):
        from voice_typer.server import config_applier

        assert config_applier.ConfigApplier.__module__ == (
            "voice_typer.server.config_applier"
        )
        names = config_applier.ConfigApplier.apply_config.__code__.co_names
        assert "IPC_CONFIG_ALLOWLIST" in names

    def test_handlers_take_side_effect_context_no_facade_global(self):
        import inspect

        from voice_typer.server import config_applier_handlers as handlers

        for name in (
            "_AutostartSyncHandler",
            "_PrewarmSyncHandler",
            "_EscHotkeyHandler",
            "_RepasteHotkeyHandler",
            "_DictationHotkeyHandler",
            "_TrayLeftClickHandler",
            "_NotificationsHandler",
            "_BubbleBehaviorHandler",
            "_VolumeDuckPollHandler",
            "_AudioPresetHandler",
            "_FilterChainHandler",
        ):
            apply = getattr(handlers, name).apply
            params = list(inspect.signature(apply).parameters)
            assert params == ["self", "ctx"], name
            ann = str(inspect.signature(apply).parameters["ctx"].annotation)
            assert "SideEffectContext" in ann, name



