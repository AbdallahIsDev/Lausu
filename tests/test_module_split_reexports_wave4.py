"""Facade re-exports + patch seams of the Wave 4 split server modules.

``audio_filters.noise_suppressor``, ``service.update_check``,
``native_hotkeys.binary_path``, ``level_monitor.monitoring`` and
``handlers.system_handlers`` were split into focused sibling modules. Callers
(and tests) import names from the facades, so two contracts must hold:

1. every moved symbol is re-exported by the facade as the SAME object as in
   its owning sibling module;
2. runtime lookups that tests monkeypatch ON the facade are still read at call
   time by the sibling code (never captured by value at import).
"""

from __future__ import annotations

import hashlib
import json
import sys


class TestNoiseSuppressorFacadeReexports:
    def test_moved_symbols_resolve_to_the_resampler_module(self):
        from voice_typer.server.audio_filters import noise_suppressor, resampler

        assert noise_suppressor._StreamingResampler is resampler._StreamingResampler
        assert (
            noise_suppressor._resampler_fir_num_taps is resampler._resampler_fir_num_taps
        )
        assert (
            noise_suppressor._resampler_group_delay_ms
            is resampler._resampler_group_delay_ms
        )

    def test_suppressor_class_stays_on_the_facade(self):
        from voice_typer.server.audio_filters import noise_suppressor

        assert noise_suppressor.NoiseSuppressor.__module__ == (
            "voice_typer.server.audio_filters.noise_suppressor"
        )

    def test_backend_ready_latch_patch_on_facade_is_honoured(self, monkeypatch):
        """``_backend_ready_logged`` is patched on the facade by log-hygiene
        tests; ``_log_backend_ready_once`` must read+write that facade set."""
        from voice_typer.server.audio_filters import noise_suppressor

        monkeypatch.setattr(noise_suppressor, "_backend_ready_logged", set())
        noise_suppressor._log_backend_ready_once("wave4-unit-key", "[NOISE] test")

        assert "wave4-unit-key" in noise_suppressor._backend_ready_logged


class TestUpdateCheckFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server.service import (
            update_check,
            update_check_http,
            update_check_urls,
            update_check_versions,
        )

        for name in (
            "DEFAULT_OFFLINE_PACK_MANIFEST_URL",
            "MAX_MANIFEST_BYTES",
            "ROLLING_OFFLINE_PACK_MANIFEST_URL",
            "_resolve_manifest_url",
            "pack_manifest_url_candidates",
        ):
            assert getattr(update_check, name) is getattr(update_check_urls, name), name
        for name in (
            "LAUNCH_MANIFEST_TIMEOUT_S",
            "_SSRFAwareRedirectHandler",
            "_http_get_manifest",
            "_is_missing_manifest_404",
            "fetch_remote_manifest",
            "fetch_remote_manifest_first_success",
        ):
            assert getattr(update_check, name) is getattr(update_check_http, name), name
        for name in ("_parse_version", "is_newer_version"):
            assert getattr(update_check, name) is getattr(update_check_versions, name), name

    def test_download_orchestration_stays_on_the_facade(self):
        from voice_typer.server.service import offline_pack, update_check

        assert update_check.UpdateCheckResult.__module__ == (
            "voice_typer.server.service.update_check"
        )
        for name in (
            "_local_offline_pack_version",
            "_trigger_background_download",
            "check_offline_pack_update",
            "handle_check_offline_pack_update_ipc",
        ):
            assert getattr(update_check, name).__module__ == (
                "voice_typer.server.service.update_check"
            ), name
        assert isinstance(update_check._ACTIVE_PACK_DOWNLOADS, set)
        assert update_check.offline_pack is offline_pack

    def test_default_transport_patch_on_facade_is_honoured(self, monkeypatch):
        """``update_check._http_get_manifest`` is patched as the default
        transport; ``fetch_remote_manifest`` must route through the facade."""
        from voice_typer.server.service import update_check

        captured: dict[str, object] = {}
        manifest = {
            "version": "9.9.9",
            "sha256": hashlib.sha256(b"pack-body").hexdigest(),
            "files": [
                {
                    "name": "worker.exe",
                    "sha256": hashlib.sha256(b"worker").hexdigest(),
                    "size": 1024,
                },
            ],
            "min_proto_version": 1,
        }

        def fake_default_transport(url, *, max_bytes=None, timeout=30.0):
            captured["url"] = url
            captured["timeout"] = timeout
            return json.dumps(manifest)

        monkeypatch.setattr(update_check, "_http_get_manifest", fake_default_transport)

        url = (
            "https://github.com/AbdallahIsDev/lausu/releases/latest/download/"
            "pack-manifest.json"
        )
        result = update_check.fetch_remote_manifest(url, timeout=7.5)

        assert captured.get("timeout") == 7.5
        assert result is not None
        assert result["version"] == "9.9.9"


class TestBinaryPathFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server.native_hotkeys import (
            binary_names,
            binary_path,
            binary_verification,
        )

        for name in (
            "_ARCH_SUFFIX_TO_LEGACY",
            "_ArchAwareBinaryNameMap",
            "_BINARY_NAMES",
            "_LEGACY_BINARY_NAMES",
            "_LEGACY_TO_ARCH_SUFFIX",
            "_MANIFEST_PATH",
            "_candidate_binary_names",
            "_normalize_machine",
        ):
            assert getattr(binary_path, name) is getattr(binary_names, name), name
        for name in (
            "_VERIFIED_CACHE",
            "_VERIFIED_CACHE_LOCK",
            "_env_specified_paths",
            "_equivalent_manifest_names",
            "_is_trusted_path_override",
            "_path_matches_env_override",
            "_verified_cache_key",
            "clear_verified_cache",
            "get_expected_sha256",
            "load_binary_manifest",
            "verify_native_binary",
        ):
            assert (
                getattr(binary_path, name) is getattr(binary_verification, name)
            ), name

    def test_discovery_and_gate_entrypoints_stay_on_the_facade(self):
        from voice_typer.server.native_hotkeys import binary_path

        assert binary_path.get_native_binary_path.__module__ == (
            "voice_typer.server.native_hotkeys.binary_path"
        )
        assert binary_path.verify_native_binary_or_skip.__module__ == (
            "voice_typer.server.native_hotkeys.binary_path"
        )
        # ``platform`` is a monkeypatch target (``binary_path.platform.machine``).
        assert binary_path.platform is sys.modules["platform"]

    def test_candidate_names_patch_on_facade_is_honoured(self, monkeypatch):
        from voice_typer.server.native_hotkeys import binary_path

        monkeypatch.setattr(binary_path, "_candidate_binary_names", lambda: [])
        binary_path.get_native_binary_path.cache_clear()
        try:
            assert binary_path.get_native_binary_path() is None
        finally:
            binary_path.get_native_binary_path.cache_clear()

    def test_manifest_path_patch_on_facade_is_honoured(self, monkeypatch, tmp_path):
        from voice_typer.server.native_hotkeys import binary_path

        monkeypatch.setattr(binary_path, "_MANIFEST_PATH", tmp_path / "missing.json")
        assert binary_path.get_expected_sha256("linux-key-listener-x86_64") is None

    def test_verify_or_skip_honours_facade_digest_patches(self, monkeypatch, tmp_path):
        from voice_typer.server.native_hotkeys import binary_path

        binary = tmp_path / "linux-key-listener-x86_64"
        binary.write_text("payload")

        monkeypatch.setattr(binary_path, "_is_trusted_path_override", lambda: False)
        monkeypatch.setattr(binary_path, "get_expected_sha256", lambda _name: "a" * 64)
        seen: dict[str, str] = {}

        def fake_verify(path, expected):
            seen["expected"] = expected
            return True

        monkeypatch.setattr(binary_path, "verify_native_binary", fake_verify)
        binary_path.clear_verified_cache()
        try:
            assert binary_path.verify_native_binary_or_skip(binary) is True
        finally:
            binary_path.clear_verified_cache()
        assert seen.get("expected") == "a" * 64


class TestMonitoringFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server.level_monitor import (
            mic_level_push,
            monitoring,
            monitoring_queries,
        )

        for name in (
            "get_level",
            "get_level_diagnostics",
            "is_monitoring",
            "update_level_processor",
        ):
            assert getattr(monitoring, name) is getattr(monitoring_queries, name), name
        for name in (
            "_ensure_mic_level_worker_running",
            "_mic_level_worker_loop",
            "_push_mic_level",
            "_stop_mic_level_worker",
        ):
            assert getattr(monitoring, name) is getattr(mic_level_push, name), name

    def test_stream_lifecycle_stays_on_the_facade(self):
        from voice_typer.server.level_monitor import monitoring

        for name in (
            "_emit_device_lost",
            "_idle_timeout_auto_stop",
            "_level_stream_finished",
            "_make_stream_finished_guard",
            "start_monitoring",
            "stop_monitoring",
        ):
            assert getattr(monitoring, name).__module__ == (
                "voice_typer.server.level_monitor.monitoring"
            ), name
        # The worker-start seam is patched on the facade, so ``start_monitoring``
        # must resolve it from the facade's own globals (behaviourally pinned by
        # ``test_mic_page_selection_and_test_transport`` bookkeeping-leak test).
        assert monitoring.start_monitoring.__globals__ is monitoring.__dict__
        assert (
            "_ensure_mic_level_worker_running"
            in monitoring.start_monitoring.__code__.co_names
        )

    def test_stop_worker_patch_on_facade_is_honoured(self, monkeypatch):
        from voice_typer.server.level_monitor import monitoring

        calls: list[int] = []
        monkeypatch.setattr(
            monitoring, "_stop_mic_level_worker", lambda: calls.append(1)
        )
        result = monitoring.stop_monitoring()
        assert calls, "stop_monitoring must call the facade's _stop_mic_level_worker"
        assert result["success"] is True


class TestSystemHandlersFacadeReexports:
    def test_permission_handlers_resolve_to_the_mixin_module(self):
        from voice_typer.server.handlers import (
            system_handlers,
            system_permissions_handlers,
        )

        mixin = system_permissions_handlers._SystemPermissionsHandlersMixin
        assert system_handlers.SystemHandlersMixin.__mro__[1] is mixin
        for name in (
            "_handle_check_accessibility",
            "_handle_reset_linux_permissions",
            "_handle_reset_macos_accessibility",
        ):
            assert getattr(system_handlers.SystemHandlersMixin, name) is getattr(
                mixin, name
            ), name

    def test_notification_and_tray_handlers_stay_on_the_facade(self):
        from voice_typer.server.handlers import system_handlers

        for name in (
            "_handle_restart_app",
            "_handle_quit_app",
            "_handle_set_esc_cancel_paused",
            "_handle_set_tray_locale",
            "_handle_show_notification",
            "_publish_service_failure",
        ):
            assert getattr(system_handlers.SystemHandlersMixin, name).__module__ == (
                "voice_typer.server.handlers.system_handlers"
            ), name
        for name in (
            "_enumerate_polkit_actions",
            "_has_control_chars",
            "_polkit_check_authorization",
            "_reset_polkit_authorization",
            "is_linux",
            "is_macos",
        ):
            assert hasattr(system_handlers, name), name

    def test_platform_probes_and_polkit_patches_on_facade_are_honoured(
        self, monkeypatch
    ):
        """The mixin must re-resolve ``is_macos``/``is_linux`` and the polkit
        helpers from the facade, because tests patch them there."""
        from voice_typer.server.handlers import (
            system_handlers,
            system_permissions_handlers,
        )

        class _Stub:
            def _wrap(self, *, cmd_name, resp_type, data, resp, body, schema, pre_coerce):
                return body({})

        monkeypatch.setattr(system_handlers, "is_linux", lambda: True)
        monkeypatch.setattr(
            system_handlers,
            "_enumerate_polkit_actions",
            lambda: ["com.Lausu.install-permissions"],
        )
        monkeypatch.setattr(
            system_handlers, "_reset_polkit_authorization", lambda: ("pkexec ok", True, None)
        )
        monkeypatch.setattr(
            system_handlers, "_polkit_check_authorization", lambda _action: "authorized"
        )

        result = system_permissions_handlers._SystemPermissionsHandlersMixin._handle_reset_linux_permissions(
            _Stub(), {}, {}
        )

        assert result["data"]["ok"] is True
        assert result["data"]["command"] == "pkexec ok"
        assert result["data"]["actions"] == ["com.Lausu.install-permissions"]
        assert result["data"]["checks"] == {
            "com.Lausu.install-permissions": "authorized",
        }
