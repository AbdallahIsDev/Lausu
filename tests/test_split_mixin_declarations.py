"""Structural pin: split-package mixins must declare their host-provided"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# (file, class, annotation-only member declarations the class must carry)
MIXIN_HOST_MEMBERS: dict[str, dict[str, set[str]]] = {
    "voice_typer/server/native_hotkeys/_spawn.py": {
        "_SpawnMixin": {
            "platform_name",
            "hotkey_str",
            "_binary_path",
            "_native_log_path",
            "_process",
            "_reader_thread",
            "_watchdog_thread",
            "_watchdog_stop_event",
            "_failed",
            "_error_message",
            "_last_event_received_at",
            "_last_pong_received_at",
        },
    },
    "voice_typer/server/native_hotkeys/_reader.py": {
        "_ReaderMixin": {
            "platform_name",
            "_process",
            "_stop_event",
            "_ready_event",
            "_restart_lock",
            "_restart_attempts",
            "_failed",
            "_error_message",
            "_binary_version",
            "_on_permanent_failure_callback",
            "_on_error_callback",
            "_on_warn_callback",
            "_WIRE_HANDLERS",
        },
    },
    "voice_typer/server/native_hotkeys/_watchdog.py": {
        "_WatchdogMixin": {
            "platform_name",
            "_process",
            "_stop_event",
            "_watchdog_stop_event",
            "_last_event_received_at",
            "_last_pong_received_at",
            "_pong_supported",
            "_shutdown_requested",
            "_callback",
            "_on_watchdog_restart_callback",
        },
    },
    "voice_typer/server/native_hotkeys/_matching.py": {
        "_MatchingMixin": {
            "platform_name",
            "_match_lock",
            "_held_modifiers",
            "_fn_down",
            "_main_key_down",
            "_parsed",
            "_extra_matchers",
            "_on_release_callback",
        },
    },
    "voice_typer/server/microphone_watcher/_linux.py": {
        "_LinuxMixin": {
            "_stop_event",
            "_poll_interval",
            "_idle_poll_interval_s",
            "_active_poll_interval_s",
            "_is_idle",
            "_on_default_device_changed",
        },
    },
    "voice_typer/server/microphone_watcher/_macos.py": {
        "_MacOSMixin": {
            "_stop_event",
            "_poll_interval",
            "_idle_poll_interval_s",
            "_active_poll_interval_s",
            "_is_idle",
        },
    },
    "voice_typer/server/vocabulary_apply.py": {
        "VocabularyApplyMixin": {
            "_data",
            "_lock",
            "_config_dir",
            "_usage_tracker",
            "_combined_phrase_cache",
        },
    },
    "voice_typer/server/vocabulary_persistence.py": {
        "VocabularyPersistenceMixin": {
            "_data",
            "_deleted",
            "_bundled_path",
            "_bundled_raw",
            "_user_store",
            "_lock",
        },
    },
    "voice_typer/server/clipboard_snapshot_win32.py": {
        "WindowsClipboardMixin": {"items"},
    },
    "voice_typer/server/clipboard_snapshot_macos.py": {
        "MacosClipboardMixin": {"items"},
    },
    "voice_typer/server/clipboard_snapshot_linux.py": {
        "LinuxClipboardMixin": {"items"},
    },
    # Wave 3 splits: onboarding selections + VAD calibration/cache mixins.
    # onboarding_permissions is a stateless probe (no host state), omitted.
    "voice_typer/server/onboarding_selections.py": {
        "_OnboardingSelectionsMixin": {
            "selected_microphone",
            "selected_hotkey",
            "selected_model",
            "selected_backend",
        },
    },
    "voice_typer/server/vad_calibration.py": {
        "_VadCalibrationMixin": {
            "_calibration_duration",
            "_calibration_rms_values",
            "_calibration_prob_values",
            "_calibrated",
            "_calibration_status",
            "_use_silero_vad",
            "_silero_available",
            "_vad_auto_calibrate",
            "_silence_threshold",
            "_speech_threshold",
            "_silence_threshold_db",
            "_speech_threshold_db",
        },
    },
    "voice_typer/server/vad_enabled_cache.py": {
        "_VadEnabledCacheMixin": {
            "_config",
            "_vad_enabled_cached",
            "_vad_enabled_cache_ts",
            "VAD_ENABLED_CACHE_TTL_S",
        },
    },
    # Wave 5 split: the telemetry mixin reads the clip/peak counters
    # initialised by AudioPipeline.__init__.
    "voice_typer/server/recording/audio_pipeline_telemetry.py": {
        "AudioPipelineTelemetryMixin": {
            "_clip_count",
            "_peak",
            "_last_clip_log_time",
        },
    },
    # Wave 7 splits: device_manager facade trim + capture audio-worker body.
    # capture_audio_worker._AudioWorkerMixin is stateless (no host state), omitted;
    # recording_start.py has no classes.
    "voice_typer/server/recording/device_health.py": {
        "_DeviceHealthMixin": {
            "recorder",
            "_device_disconnected",
            "_device_health_checker_thread",
            "_device_health_stop_event",
            "_device_check_interval_s",
            "_device_check_interval_s_bt",
            "_last_default_input_info",
            "_permission_check_counter",
            "_permission_check_interval",
            "_stream_open_default_input_index",
        },
    },
    "voice_typer/server/recording/device_resolution.py": {
        "_DeviceResolutionMixin": {
            "recorder",
            "_device_list_cache",
            "_host_api_cache",
            "_bt_retry_sleep_seconds",
            "_last_default_input_info",
        },
    },
    # Wave 9 splits: hotkey_dispatcher facade trim (5 sibling mixins) and
    # service/model/_downloads facade trim (4 sibling mixins). Without these
    # declarations mypy infers each attribute from the first ``self.x = ...``
    # in the mixin body (often ``None``), so the composed facade's
    # ``__init__`` assignments became "base class defined the type as ...".
    # service/model/_download_state.py declares nothing annotation-only
    # (its only annotated assignment carries a value), so it is omitted.
    "voice_typer/server/hotkey_dispatch.py": {
        "HotkeyDispatchMixin": {
            "_app",
            "_esc_backend",
            "_esc_pending_capture_exit_event",
        },
    },
    "voice_typer/server/hotkey_registration.py": {
        "HotkeyRegistrationMixin": {
            "_app",
            "_esc_backend",
            "_esc_callback",
            "_esc_pending_capture_exit_event",
            "_esc_spec",
            "_hotkey_backend",
            "_repaste_backend",
            "_repaste_callback",
            "_repaste_spec",
            "_shared_backend",
            "_shared_backend_pool",
        },
    },
    "voice_typer/server/hotkey_pool.py": {
        "HotkeyPoolMixin": {
            "_app",
            "_esc_callback",
            "_esc_spec",
            "_repaste_callback",
            "_repaste_spec",
            "_resyncing_aux",
            "_shared_backend",
            "_shared_backend_pool",
        },
    },
    "voice_typer/server/hotkey_lifecycle.py": {
        "HotkeyLifecycleMixin": {
            "_app",
            "_esc_callback",
            "_esc_spec",
            "_hotkey_backend",
            "_repaste_callback",
            "_repaste_spec",
            "_shared_backend",
            "_shared_backend_pool",
        },
    },
    "voice_typer/server/hotkey_ptt_safety.py": {
        "HotkeyPttSafetyMixin": {
            "_PTT_SAFETY_TIMEOUT_SECONDS",
            "_app",
            "_ptt_safety_timer",
        },
    },
    "voice_typer/server/service/model/_download_queue.py": {
        "DownloadQueueMixin": {
            "_active_download_id",
            "_download_cancel_events",
            "_download_cancel_lock",
            "_download_queue",
        },
    },
    "voice_typer/server/service/model/_download_dispatch.py": {
        "DownloadDispatchMixin": {"_app"},
    },
    "voice_typer/server/service/model/_download_preflight.py": {
        "DownloadPreflightMixin": {"_app"},
    },
    "voice_typer/server/service/model/_download_qwen_parakeet.py": {
        "QwenParakeetDownloadMixin": {"_app"},
    },
}

# (file, class, TYPE_CHECKING-only method stubs the class must carry)
MIXIN_STUB_METHODS: dict[str, dict[str, set[str]]] = {
    "voice_typer/server/native_hotkeys/_spawn.py": {
        "_SpawnMixin": {"_reader_loop", "_watchdog_loop"},
    },
    "voice_typer/server/native_hotkeys/_reader.py": {
        "_ReaderMixin": {"_spawn_process"},
    },
    "voice_typer/server/native_hotkeys/_watchdog.py": {
        "_WatchdogMixin": {"start", "stop"},
    },
    "voice_typer/server/microphone_watcher/_linux.py": {
        "_LinuxMixin": {"_invoke_callback"},
    },
    "voice_typer/server/microphone_watcher/_macos.py": {
        "_MacOSMixin": {"_invoke_callback", "_device_signature"},
    },
    "voice_typer/server/microphone_watcher/_windows.py": {
        "_WindowsMixin": {"_invoke_callback"},
    },
    "voice_typer/server/vocabulary_persistence.py": {
        # _load_bundled: facade (vocabulary.py); _invalidate_pattern_cache:
        # sibling VocabularyApplyMixin -- both refs live inside
        # if TYPE_CHECKING: stubs in vocabulary_persistence.py.
        "VocabularyPersistenceMixin": {"_load_bundled", "_invalidate_pattern_cache"},
    },
    # Wave 3: selections mixin calls facade-owned _persist_progress at
    # set_microphone. vad_calibration carries three TYPE_CHECKING stubs:
    # vad_enabled (real property on sibling vad_enabled_cache) plus the
    # threshold properties owned by the composed VadProcessor.
    "voice_typer/server/onboarding_selections.py": {
        "_OnboardingSelectionsMixin": {"_persist_progress"},
    },
    "voice_typer/server/vad_calibration.py": {
        "_VadCalibrationMixin": {"vad_enabled", "speech_threshold_db", "silence_threshold_db"},
    },
    # Wave 7: device_health/device_resolution delegate to the facade's
    # _resolve_device/_refresh_device_list and to sibling-mixin helpers.
    "voice_typer/server/recording/device_health.py": {
        "_DeviceHealthMixin": {
            "_resolve_device",
            "_build_device_info_for_retry_policy",
            "_get_max_retries_for_device",
            "_cached_device_info",
        },
    },
    "voice_typer/server/recording/device_resolution.py": {
        "_DeviceResolutionMixin": {"_refresh_device_list", "_resolve_device"},
    },
    # Wave 9: every cross-mixin method reference in the hotkey / download
    # siblings still carries its ``if TYPE_CHECKING:`` stub. The stubs are
    # what keep ``self._sibling_method(...)`` typed on the composed class
    # instead of an untyped missing-attribute error.
    "voice_typer/server/hotkey_dispatch.py": {
        "HotkeyDispatchMixin": {"_shared_native"},
    },
    "voice_typer/server/hotkey_registration.py": {
        "HotkeyRegistrationMixin": {
            "_handle_shared_native_state_changed",
            "_make_dictation_callback",
            "_make_repaste_callback",
            "_maybe_warn_wayland_caps_lock",
            "_on_esc_release",
            "_pool_aux_into_shared",
            "_remove_shared_extra_matcher",
            "_repool_aux_into_shared",
            "_shared_native",
            "_start_ptt_safety_timer",
            "_track_pooled_backend",
            "_untrack_pooled_backend",
        },
    },
    "voice_typer/server/hotkey_pool.py": {
        "HotkeyPoolMixin": {"register_esc", "register_repaste"},
    },
    "voice_typer/server/hotkey_lifecycle.py": {
        "HotkeyLifecycleMixin": {
            "_cancel_ptt_safety_timer",
            "_create_and_start_main_backend",
            "_untrack_pooled_backend",
        },
    },
    "voice_typer/server/service/model/_download_queue.py": {
        "DownloadQueueMixin": {"download_model"},
    },
    "voice_typer/server/service/model/_download_dispatch.py": {
        "DownloadDispatchMixin": {
            "_download_parakeet",
            "_download_qwen",
            "_download_whisper_family",
            "_start_next_queued_download",
        },
    },
    "voice_typer/server/service/model/_download_qwen_parakeet.py": {
        "QwenParakeetDownloadMixin": {
            "_enqueue_download",
            "_require_huggingface_consent",
        },
    },
}


def _class_node(tree: ast.Module, class_name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node
    raise AssertionError(f"class {class_name} not found")


def _annotated_members(cls: ast.ClassDef) -> set[str]:
    """Names declared as annotation-only statements in the class body."""
    names: set[str] = set()
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and stmt.value is None:
            targets = stmt.target
            if isinstance(targets, ast.Name):
                names.add(targets.id)
    return names


def _type_checking_stub_methods(cls: ast.ClassDef) -> set[str]:
    """Method names defined under an ``if TYPE_CHECKING:`` block."""
    names: set[str] = set()
    for stmt in cls.body:
        if not isinstance(stmt, ast.If):
            continue
        test = stmt.test
        is_tc = (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
            isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
        )
        if not is_tc:
            continue
        for inner in stmt.body:
            if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(inner.name)
            # @staticmethod-decorated stubs inside the block count too.
            elif isinstance(inner, ast.ClassDef):
                pass
    return names


def test_mixin_host_member_declarations_present() -> None:
    """Every split-package mixin still declares its host-provided state."""
    for rel_path, classes in MIXIN_HOST_MEMBERS.items():
        tree = ast.parse((REPO_ROOT / rel_path).read_text(encoding="utf-8"), filename=rel_path)
        for class_name, expected in classes.items():
            declared = _annotated_members(_class_node(tree, class_name))
            missing = expected - declared
            assert not missing, (
                f"{rel_path}: {class_name} lost host-provided member "
                f"declarations {sorted(missing)}, re-add the "
                f"annotation-only declaration so pyrefly keeps resolving "
                f"the composed-class attribute (missing declarations were "
                f"the original error source)."
            )


def test_mixin_type_checking_stubs_present() -> None:
    """Every cross-mixin method reference still has its TYPE_CHECKING stub."""
    for rel_path, classes in MIXIN_STUB_METHODS.items():
        tree = ast.parse((REPO_ROOT / rel_path).read_text(encoding="utf-8"), filename=rel_path)
        for class_name, expected in classes.items():
            stubs = _type_checking_stub_methods(_class_node(tree, class_name))
            missing = expected - stubs
            assert not missing, (
                f"{rel_path}: {class_name} lost the TYPE_CHECKING stubs "
                f"{sorted(missing)} for sibling-mixin methods, without the "
                f"stub the cross-mixin method reference is an untyped "
                f"missing-attribute error again."
            )


def test_linux_default_device_callback_none_guarded() -> None:
    """
    _on_default_device_changed must be None-guarded before the call.
    Pins the real bug fix from the wave-3 reconcile: the Linux mixin
    """
    src = (REPO_ROOT / "voice_typer/server/microphone_watcher/_linux.py").read_text(encoding="utf-8")
    # The guarded shape: local binding + None check before the call.
    assert "callback = self._on_default_device_changed" in src
    assert "if callback is None:" in src
    assert "self._on_default_device_changed()" not in src
