"""Facade re-exports + patch seams of the Wave 5 split server modules.

``model_manager._change``, ``config._schema``, ``sidecar_ws``,
``recording.audio_pipeline`` and ``ipc.entrypoint`` each lost one cohesive
concern to a new sibling module. Callers (and tests) import names from the
facades, so two contracts must hold:

1. every moved symbol is re-exported by the facade as the SAME object as in
   its owning sibling module;
2. runtime lookups that tests monkeypatch ON the facade are still read at call
   time by the sibling code (never captured by value at import).
"""

from __future__ import annotations

import os
import sys


class TestChangeFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server.model_manager import (
            _backend_names,
            _change,
            _change_events,
        )

        assert _change.AsrBackendName is _backend_names.AsrBackendName
        assert _change._backend_for_model_size is _backend_names._backend_for_model_size
        assert _change.ChangeEventsMixin is _change_events.ChangeEventsMixin

    def test_change_mixin_keeps_the_events_base(self):
        from voice_typer.server.model_manager import _change, _change_events

        assert _change.ChangeMixin.__mro__[1] is _change_events.ChangeEventsMixin

    def test_publish_helpers_resolve_event_bus_at_call_time(self, monkeypatch):
        """The event-bus publish seam lives INSIDE the moved methods (the
        ``from voice_typer.server import event_bus`` import is per call), so
        patching ``event_bus.publish`` is honoured from the leaf."""
        from voice_typer.server import event_bus
        from voice_typer.server.model_manager import _change_events

        published: list[dict] = []
        monkeypatch.setattr(event_bus, "publish", published.append)

        _change_events.ChangeEventsMixin()._publish_backend_ready_event("whisper", "base")

        assert published, "the leaf must publish through the patched event_bus.publish"
        assert published[0]["type"] == "asr_backend_ready"


class TestSchemaFacadeReexports:
    def test_moved_symbols_resolve_to_the_validation_module(self):
        from voice_typer.server.config import _schema, _schema_validation

        for name in (
            "_ENUM_FIELDS_TO_RESET_ON_LOAD",
            "_SECRET_FIELD_NAMES_FALLBACK",
            "_reset_invalid_enum_fields_impl",
            "_secret_field_names_impl",
        ):
            assert getattr(_schema, name) is getattr(_schema_validation, name), name

    def test_existing_importers_still_resolve_through_the_facade(self):
        """``config/__init__.py`` and ``config/_lifecycle.py`` import the two
        impls FROM ``_schema``; the re-export keeps those bindings identical."""
        import voice_typer.server.config as config_pkg
        from voice_typer.server.config import _lifecycle, _schema_validation

        for module in (config_pkg, _lifecycle):
            assert module._reset_invalid_enum_fields_impl is _schema_validation._reset_invalid_enum_fields_impl
            assert module._secret_field_names_impl is _schema_validation._secret_field_names_impl

    def test_schema_dataclass_stays_on_the_facade(self):
        from voice_typer.server.config import _schema

        assert _schema._ConfigSchema.__module__ == "voice_typer.server.config._schema"


class TestSidecarWsFacadeReexports:
    def test_moved_symbols_resolve_to_the_early_bind_leaf(self):
        from voice_typer.server import sidecar_ws
        from voice_typer.server.sidecar_ws_internals import early_bind

        for name in (
            "_EARLY_BIND_BUFFER_CAP",
            "_drain_early_dispatch_buffer",
            "_wrap_dispatch_for_early_bind",
            "flush_early_dispatch_buffer",
        ):
            assert getattr(sidecar_ws, name) is getattr(early_bind, name), name

    def test_leaf_reads_its_patch_seams_from_its_own_globals(self):
        """C-ARCH-2: the leaf calls ``_outbound_mod._safe_send`` /
        ``_read_loop_mod._dispatch_and_respond`` through module aliases
        resolved at CALL time, so leaf-level patches take effect."""
        from voice_typer.server.sidecar_ws_internals import (
            early_bind,
            outbound,
            read_loop,
        )

        assert early_bind._outbound_mod is outbound
        assert early_bind._read_loop_mod is read_loop
        assert early_bind._drain_early_dispatch_buffer.__globals__ is early_bind.__dict__

    def test_connection_handlers_stay_on_the_facade(self):
        from voice_typer.server import sidecar_ws

        for name in (
            "_abnormal_close_note",
            "_handle_connection",
            "_handle_connection_inner",
            "_is_graceful_loop_stop",
            "run",
        ):
            assert getattr(sidecar_ws, name).__module__ == "voice_typer.server.sidecar_ws", name


class TestAudioPipelineFacadeReexports:
    def test_telemetry_mixin_resolves_to_the_leaf(self):
        from voice_typer.server.recording import audio_pipeline, audio_pipeline_telemetry

        assert audio_pipeline.AudioPipelineTelemetryMixin is audio_pipeline_telemetry.AudioPipelineTelemetryMixin

    def test_clipping_helper_comes_from_the_mixin(self):
        from voice_typer.server.recording import audio_pipeline, audio_pipeline_telemetry

        assert (
            audio_pipeline.AudioPipeline.detect_and_emit_clipping
            is audio_pipeline_telemetry.AudioPipelineTelemetryMixin.detect_and_emit_clipping
        )
        assert [cls.__name__ for cls in audio_pipeline.AudioPipeline.__mro__] == [
            "AudioPipeline",
            "AudioPipelineTelemetryMixin",
            "object",
        ]

    def test_host_initialises_the_declared_telemetry_state(self):
        """The mixin only DECLARES ``_clip_count`` / ``_peak`` /
        ``_last_clip_log_time``; ``AudioPipeline.__init__`` owns the values."""
        from unittest.mock import MagicMock

        from voice_typer.server.recording.audio_pipeline import AudioPipeline

        pipeline = AudioPipeline(MagicMock(name="RecorderStub"))

        assert pipeline._clip_count == 0
        assert pipeline._peak == 0.0
        assert pipeline._last_clip_log_time == 0.0

    def test_rms_and_vad_helpers_stay_on_the_facade(self):
        from voice_typer.server.recording import audio_pipeline

        for name in (
            "append_to_buffer_locked",
            "compute_rms_and_peak",
            "detect_device_disconnect",
            "handle_xrun_status",
            "run_vad_state_machine",
        ):
            assert getattr(audio_pipeline.AudioPipeline, name).__module__ == (
                "voice_typer.server.recording.audio_pipeline"
            ), name


class TestEntrypointFacadeReexports:
    def test_process_helpers_resolve_to_the_process_leaf(self):
        from voice_typer.server.ipc import entrypoint, entrypoint_process

        assert entrypoint._set_process_metadata is entrypoint_process._set_process_metadata
        assert entrypoint._detach_process_group is entrypoint_process._detach_process_group

    def test_invocation_helpers_resolve_to_the_args_leaf(self):
        from voice_typer.server.ipc import entrypoint, entrypoint_args

        assert entrypoint._version_requested is entrypoint_args._version_requested
        assert entrypoint._early_server_started_enabled is entrypoint_args._early_server_started_enabled
        assert entrypoint._EARLY_SERVER_STARTED_ENV_VAR is entrypoint_args._EARLY_SERVER_STARTED_ENV_VAR

    def test_process_group_seam_patches_the_shared_os_module(self, monkeypatch):
        """``tests/server/test_ipc_entrypoint.py`` patches ``entrypoint.os``;
        the leaf must observe it, so both must hold the same ``os`` object."""
        from voice_typer.server.ipc import entrypoint, entrypoint_process

        assert entrypoint.os is os
        assert entrypoint_process.os is sys.modules["os"]

        calls: list[tuple[int, int]] = []

        def _fake_setpgid(pid: int, pgid: int) -> None:
            calls.append((pid, pgid))

        monkeypatch.setattr(entrypoint_process.os, "name", "posix")
        monkeypatch.setattr(entrypoint_process.os, "setpgid", _fake_setpgid, raising=False)
        monkeypatch.setattr(entrypoint_process.os, "getpgrp", lambda: 4242, raising=False)

        assert entrypoint._detach_process_group() is True
        assert calls == [(0, 0)]

    def test_main_and_the_single_construction_site_stay_on_the_facade(self):
        from voice_typer.server.ipc import entrypoint

        for name in (
            "_construct_app_with_diagnostics",
            "_ws_startup_thread_main",
            "_ws_startup_thread_main_early",
            "main",
            "parse_ipc_args",
        ):
            assert getattr(entrypoint, name).__module__ == "voice_typer.server.ipc.entrypoint", name
