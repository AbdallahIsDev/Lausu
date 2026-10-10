"""Facade re-exports of the split startup-task modules keep resolving.

``startup_config_sync`` and ``startup_launch_checks`` were split out of
``voice_typer.server.startup_tasks`` (one concern per file). Callers and tests
import the names from the facade, so two contracts must hold:

1. every moved symbol is re-exported by the facade as the SAME object as in its
   owning sibling module;
2. the runtime lookups tests monkeypatch ON the facade
   (``startup_tasks.sync_autostart``) are still read at call time by the sibling
   code that consumes them.

The same two contracts are pinned below for the ``qwen_engine`` facade,
whose per-chunk inference loops were split into ``qwen_chunking``, and for the
``worker_client`` facade, whose wire codec was split into ``worker_protocol``
and whose WS session loop was split into ``worker_session``, and for the
``cloud._engine`` facade, whose provider send paths were split into
``cloud._sendpaths`` and whose cloud-to-local fallback policy was split into
``cloud._fallback``, and for the ``log.setup`` facade, whose log-path helpers
were split into ``log.paths`` and whose log-level policy was split into
``log.levels``, and for the ``ipc.validation`` facade, whose error-code
registry was split into ``ipc.error_codes`` and whose typed error-envelope
contract was split into ``ipc.error_envelope``.
"""

from __future__ import annotations

import pytest


class TestStartupTaskFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server import (
            startup_config_sync,
            startup_launch_checks,
            startup_tasks,
        )

        assert startup_tasks.sync_autostart is startup_config_sync.sync_autostart
        assert (
            startup_tasks.reconcile_configured_model
            is startup_config_sync.reconcile_configured_model
        )
        assert (
            startup_tasks.reset_onboarding_complete
            is startup_config_sync.reset_onboarding_complete
        )
        assert (
            startup_tasks.check_offline_pack_on_launch
            is startup_launch_checks.check_offline_pack_on_launch
        )
        assert (
            startup_tasks.check_media_extractor_refresh
            is startup_launch_checks.check_media_extractor_refresh
        )
        assert (
            startup_tasks.ensure_desktop_shortcut
            is startup_launch_checks.ensure_desktop_shortcut
        )
        assert (
            startup_tasks.prewarm_connect_probes
            is startup_launch_checks.prewarm_connect_probes
        )

    def test_sync_autostart_patch_on_facade_is_honoured(self, monkeypatch):
        from voice_typer.server import startup_tasks
        from voice_typer.server.config_applier_handlers import (
            SideEffectContext,
            _AutostartSyncHandler,
        )

        sentinel = {"registered": True, "error": None}
        seen: list[object] = []

        def fake_sync(app):
            seen.append(app)
            return sentinel

        monkeypatch.setattr(startup_tasks, "sync_autostart", fake_sync)

        app = object()
        ctx = SideEffectContext(
            app=app,
            config=None,
            updates={},
            status={"autostart_status": None, "prewarm_status": None},
        )
        _AutostartSyncHandler().apply(ctx)

        assert seen == [app]
        assert ctx.status["autostart_status"] is sentinel


class TestQwenChunkingFacadeReexports:
    """``voice_typer.server.qwen_engine`` re-exports the moved chunking loops."""

    def test_moved_functions_resolve_to_the_sibling_module(self):
        from voice_typer.server import qwen_chunking, qwen_engine

        assert qwen_engine.transcribe_chunks_batched is qwen_chunking.transcribe_chunks_batched
        assert qwen_engine.transcribe_chunks_sequential is qwen_chunking.transcribe_chunks_sequential
        assert qwen_engine.transcribe_batch is qwen_chunking.transcribe_batch

    def test_merge_chunks_patch_on_facade_is_honoured(self, monkeypatch):
        from unittest.mock import MagicMock

        import numpy as np
        import voice_typer.server.qwen_engine as qwen_module

        monkeypatch.delenv("QWEN_BATCH_SIZE", raising=False)

        calls: list[list[str]] = []

        def _spy_merge_chunks(texts):
            calls.append(list(texts))
            return "merged"

        monkeypatch.setattr(qwen_module, "merge_chunks", _spy_merge_chunks)

        engine = qwen_module.QwenEngine(model_path="/fake/qwen/model")
        mock_model = MagicMock(name="qwen_model")
        mock_model.transcribe.side_effect = [
            [MagicMock(text="first chunk")],
            [MagicMock(text="second chunk")],
        ]
        engine._model = mock_model

        t = np.linspace(0, 40.0, int(40.0 * 16000), endpoint=False, dtype=np.float32)
        audio = (0.1 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
        result = engine.transcribe(audio)

        assert result == "merged"
        assert calls == [["first chunk", "second chunk"]]

    def test_batched_loop_calls_back_through_the_engine(self, monkeypatch):
        from unittest.mock import MagicMock

        import numpy as np
        import voice_typer.server.qwen_engine as qwen_module

        monkeypatch.setenv("QWEN_BATCH_SIZE", "2")

        engine = qwen_module.QwenEngine(model_path="/fake/qwen/model")
        assert engine._INFERENCE_BATCH_SIZE == 2

        seen_batches: list[int] = []

        def _fake_batch(model, batch, sample_rate):
            seen_batches.append(len(batch))
            return ["alpha", "beta"]

        engine._transcribe_batch = _fake_batch
        engine._model = MagicMock(name="qwen_model")

        t = np.linspace(0, 40.0, int(40.0 * 16000), endpoint=False, dtype=np.float32)
        audio = (0.1 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
        result = engine.transcribe(audio)

        assert seen_batches == [2]
        assert result == "alpha beta"
        engine._model.transcribe.assert_not_called()


class TestQwenChunkingFacadeRouting:
    """The facade's methods must delegate, not keep a duplicate copy.

    The chunking loops now live in ``voice_typer.server.qwen_chunking`` and
    ``qwen_engine`` re-exports them, so each ``QwenEngine`` method reads the
    facade module global at call time. A stale inline copy surviving on the
    class would make these patches silently ineffective.
    """

    def test_delegating_methods_forward_to_the_facade_global(self, monkeypatch):
        from unittest.mock import MagicMock

        import numpy as np
        import voice_typer.server.qwen_engine as qwen_module

        engine = qwen_module.QwenEngine(model_path="/fake/qwen/model")
        model = MagicMock(name="qwen_model")
        chunks = [np.zeros(10, dtype=np.float32)]

        for facade_name, method_name in (
            ("transcribe_chunks_batched", "_transcribe_chunks_batched"),
            ("transcribe_chunks_sequential", "_transcribe_chunks_sequential"),
            ("transcribe_batch", "_transcribe_batch"),
        ):
            sentinel = MagicMock(name=facade_name, return_value=[f"via {facade_name}"])
            monkeypatch.setattr(qwen_module, facade_name, sentinel)

            result = getattr(engine, method_name)(model, chunks, 16000)

            assert result == [f"via {facade_name}"]
            assert sentinel.call_args.args == (engine, model, chunks, 16000)
            model.transcribe.assert_not_called()

    def test_transcribe_chunked_hands_off_to_the_sibling_loops(self, monkeypatch):
        from unittest.mock import MagicMock

        import numpy as np
        import voice_typer.server.qwen_engine as qwen_module

        engine = qwen_module.QwenEngine(model_path="/fake/qwen/model")
        model = MagicMock(name="qwen_model")
        sentinel_loop = MagicMock(name="transcribe_chunks_batched", return_value=["a", "b"])
        merged: list[list[str]] = []

        def _spy_merge_chunks(texts):
            merged.append(list(texts))
            return "a b"

        monkeypatch.setattr(qwen_module, "transcribe_chunks_batched", sentinel_loop)
        monkeypatch.setattr(qwen_module, "merge_chunks", _spy_merge_chunks)

        t = np.linspace(0, 40.0, int(40.0 * 16000), endpoint=False, dtype=np.float32)
        audio = (0.1 * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
        result = engine._transcribe_chunked(model, audio, 16000)

        assert result == "a b"
        assert merged == [["a", "b"]]
        # The facade split the audio, then handed the chunks to the moved loop.
        assert sentinel_loop.call_args.args[0] is engine
        assert sentinel_loop.call_args.args[1] is model
        assert sentinel_loop.call_args.args[3] == 16000
        assert len(sentinel_loop.call_args.args[2]) == 2


class _ScriptedWS:
    """Minimal worker WS stub: replays scripted inbound items, records sends."""

    def __init__(self, inbound: list):
        self._inbound = list(inbound)
        self.sent: list[str] = []

    async def send(self, frame) -> None:
        self.sent.append(frame)

    async def recv(self):
        item = self._inbound.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


class TestWorkerClientFacadeReexports:
    """``voice_typer.server.worker_client`` re-exports both sibling modules."""

    def test_protocol_symbols_resolve_to_the_wire_codec_module(self):
        from voice_typer.server import worker_client, worker_protocol

        for name in (
            "_MAX_FRAME_BYTES",
            "_SAMPLES_CHUNK_RAW_BYTES",
            "backoff_delay",
            "build_abort_frame",
            "build_auth_frame",
            "build_heartbeat_frame",
            "build_streaming_frame",
            "build_transcribe_frame",
            "chunk_samples",
            "parse_incoming",
            "port_from_worker_started",
            "route_frame",
        ):
            assert getattr(worker_client, name) is getattr(worker_protocol, name), name

    def test_session_symbols_resolve_to_the_session_module(self):
        from voice_typer.server import worker_client, worker_session

        for name in (
            "_WorkerUnresponsiveError",
            "connect_loop",
            "current_url",
            "drain_outbound",
            "is_current",
            "pump",
            "run_session",
        ):
            assert getattr(worker_client, name) is getattr(worker_session, name), name

    def test_error_class_identity_survives_the_split(self):
        from voice_typer.server import worker_client, worker_session

        assert worker_client._WorkerUnresponsiveError is worker_session._WorkerUnresponsiveError
        assert issubclass(worker_client._WorkerUnresponsiveError, Exception)

    async def test_heartbeat_budget_patches_on_facade_are_honoured(self, monkeypatch):
        """The moved session loop reads the heartbeat budget through the facade.

        Patching ``worker_client._HEARTBEAT_SECONDS`` /
        ``_MAX_MISSED_HEARTBEATS`` must steer the session loop now that the
        loop lives in ``worker_session`` (the call-time facade lookup is the
        only reason the existing suites' patches still work).
        """
        import asyncio

        from voice_typer.server import worker_client

        monkeypatch.setattr(worker_client, "_HEARTBEAT_SECONDS", 0.01)
        monkeypatch.setattr(worker_client, "_MAX_MISSED_HEARTBEATS", 7)

        client = worker_client.WorkerClient()
        ws = _ScriptedWS([asyncio.TimeoutError() for _ in range(8)])

        with pytest.raises(worker_client._WorkerUnresponsiveError):
            await client._pump(ws, client._generation, asyncio.Event())

        assert len(ws.sent) == 8
        assert all(isinstance(frame, str) for frame in ws.sent)
        assert all('"type": "heartbeat"' in frame for frame in ws.sent)


class _FakeHTTPResponse:
    """Context-manager HTTP response fake for the opener seam."""

    status = 200
    fp = None

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        body, self._body = self._body, b""
        return body


class TestCloudEngineFacadeReexports:
    """``voice_typer.server.cloud._engine`` re-exports both split leaves."""

    def test_send_path_symbols_resolve_to_the_sendpaths_leaf(self):
        from voice_typer.server.cloud import _engine, _sendpaths

        for name in (
            "_facade",
            "_verify_cloud_peer",
            "_send_openai_compatible",
            "_send_deepgram",
            "_send_gemini",
            "_build_multipart_body",
            "_multipart_parts",
        ):
            assert getattr(_engine, name) is getattr(_sendpaths, name), name

    def test_fallback_symbols_resolve_to_the_fallback_leaf(self):
        from voice_typer.server.cloud import _engine, _fallback

        for name in ("_fallback_kind", "fall_back_to_local"):
            assert getattr(_engine, name) is getattr(_fallback, name), name

    def test_engine_class_stays_owned_by_the_engine_leaf(self):
        import voice_typer.server.cloud_engines as facade
        from voice_typer.server.cloud import _engine

        assert _engine.CloudEngine.__module__ == "voice_typer.server.cloud._engine"
        assert facade.CloudEngine is _engine.CloudEngine

    def test_moved_methods_still_exist_on_the_engine(self):
        from voice_typer.server.cloud import _engine

        for name in (
            "transcribe_with_fallback",
            "_send_openai_compatible",
            "_send_deepgram",
            "_send_gemini",
            "_build_multipart_body",
            "_multipart_parts",
            "_send_request",
            "_transcribe_with_retry",
            "test_connection",
        ):
            assert hasattr(_engine.CloudEngine, name), name

    def test_moved_send_path_reads_patched_facade_names_at_call_time(self, monkeypatch):
        """The moved send path must resolve ``_opener``/``assert_url_allowed``
        from the ``cloud_engines`` facade namespace (the patch contract the
        pre-split method honored).
        """
        from unittest.mock import MagicMock

        import voice_typer.server.cloud_engines as facade
        from voice_typer.server.cloud import _sendpaths

        allowlisted: list[str] = []
        monkeypatch.setattr(facade, "assert_url_allowed", lambda url, **kwargs: allowlisted.append(url))
        opener = MagicMock()
        opener.open.return_value = _FakeHTTPResponse(b'{"text": "hi"}')
        monkeypatch.setattr(facade, "_opener", opener)

        engine = facade.CloudEngine(
            provider="openai",
            api_key="test-key",
            api_url="https://api.openai.com/v1/audio/transcriptions",
            model="whisper-1",
            consent_given=True,
        )
        result = _sendpaths._send_openai_compatible(engine, b"wav-bytes", "audio.wav")

        assert result == "hi"
        assert allowlisted == [engine.api_url]
        assert opener.open.call_count == 1


class TestLogSetupFacadeReexports:
    """``voice_typer.server.log.setup`` re-exports both split leaves."""

    def test_path_helpers_resolve_to_the_paths_leaf(self):
        from voice_typer.server.log import paths, setup

        for name in (
            "LOG_SUBDIR",
            "_LEGACY_LOG_GLOBS",
            "_LEGACY_LOG_NAMES",
            "_maybe_migrate_legacy_logs",
            "_maybe_move_legacy_log_file",
            "get_log_file_path",
            "get_logs_dir",
        ):
            assert getattr(setup, name) is getattr(paths, name), name

    def test_level_policy_resolves_to_the_levels_leaf(self):
        from voice_typer.server.log import levels, setup

        for name in (
            "_THIRD_PARTY_LOGGER_LEVELS",
            "_apply_per_module_log_levels",
            "_apply_third_party_logger_levels",
            "_ensure_last_resort_redacted",
            "_json_logging_enabled",
            "get_module_levels",
            "set_module_level",
        ):
            assert getattr(setup, name) is getattr(levels, name), name

    def test_package_still_exports_the_split_names(self):
        import voice_typer.server.log as vt_log
        from voice_typer.server.log import levels, paths

        for name in ("LOG_SUBDIR", "get_logs_dir", "get_log_file_path", "_sweep_stale_logs", "setup_logging"):
            assert hasattr(vt_log, name), name
        for name in ("set_module_level", "get_module_levels", "_apply_per_module_log_levels"):
            assert getattr(vt_log, name) is getattr(levels, name), name
        assert vt_log.get_logs_dir is paths.get_logs_dir

    def test_split_modules_share_the_historical_logger_name(self):
        """C-LOG routing: every module of the package logs under one name."""
        from voice_typer.server.log import levels, paths, setup

        assert setup.log.name == paths.log.name == levels.log.name == "voice_typer.server.log"

    def test_sweep_patch_on_the_package_is_honoured(self, monkeypatch, tmp_path):
        """``setup_logging`` resolves the sweep through the package at call time.

        The sweep stays in ``log.setup``; this pins that the split did not
        replace the C-ARCH-2 package lookup with a module-global call, which
        would silently break ``tests/test_log_retention_sweep.py``'s patches.
        """
        from pathlib import Path

        import voice_typer.server.log as vt_log

        vt_log.reset()
        monkeypatch.delenv("VOICE_TYPER_LOG_JSON", raising=False)
        swept: list[Path] = []

        def _spy(config_dir: Path) -> None:
            swept.append(config_dir)

        monkeypatch.setattr(vt_log, "_sweep_stale_logs", _spy)
        config_dir = tmp_path / "cfg"
        try:
            vt_log.setup_logging(config_dir)
            assert swept == [config_dir]
        finally:
            vt_log.reset()


class TestIpcValidationFacadeReexports:
    """``voice_typer.server.ipc.validation`` re-exports both split leaves.

    No suite monkeypatches a name ON the validation facade (verified by
    grepping tests for ``setattr(validation`` / ``validation, "_name"``), so
    the re-export identity checks below plus the wire-code behavior tests
    are the whole contract the split must keep.
    """

    def test_registry_symbols_resolve_to_the_error_codes_leaf(self):
        from voice_typer.server.ipc import error_codes, validation

        for name in (
            "ALL_ERROR_CODES",
            "ERROR_CODES",
            "LEGACY_ERROR_CODES",
            "ErrorCodes",
            "LegacyErrorCodes",
        ):
            assert getattr(validation, name) is getattr(error_codes, name), name

    def test_envelope_symbols_resolve_to_the_error_envelope_leaf(self):
        from voice_typer.server.ipc import error_envelope, validation

        for name in ("ErrorData", "ErrorEnvelope", "_error_response"):
            assert getattr(validation, name) is getattr(error_envelope, name), name

    def test_wire_code_literals_survive_the_split(self):
        """The renderer branches on these exact strings (wire contract)."""
        from voice_typer.server.ipc import validation

        assert validation.ErrorCodes.INVALID_PAYLOAD == "client.invalid_payload"
        assert validation.ErrorCodes.INVALID_FIELD == "client.invalid_field"
        assert validation.ErrorCodes.MISSING_FIELD == "client.missing_field"
        assert validation.ErrorCodes.PAYLOAD_TOO_LARGE == "client.payload_too_large"
        assert validation.ErrorCodes.HANDLER_ERROR == "server.handler_error"
        assert validation.ErrorCodes.INVALID_PAYLOAD in validation.ERROR_CODES
        assert validation.LegacyErrorCodes.INVALID_FIELD in validation.LEGACY_ERROR_CODES
        assert validation.ALL_ERROR_CODES == validation.ERROR_CODES | validation.LEGACY_ERROR_CODES

    def test_validation_and_envelope_paths_emit_the_same_codes(self):
        """The validators stayed in the facade: same codes, same envelope shape."""
        from voice_typer.server.ipc import validation

        validated, error = validation._validate_dict_payload(
            ["not", "a", "dict"], {"field": {"type": str, "required": True}}
        )
        assert validated is None
        assert error is not None
        assert error["type"] == "error"
        assert error["data"]["code"] == validation.ErrorCodes.INVALID_PAYLOAD

        validated, error = validation._validate_dict_payload({}, {"field": {"type": str, "required": True}})
        assert validated is None
        assert error is not None
        assert error["data"]["code"] == validation.ErrorCodes.MISSING_FIELD

        validated, error = validation._validate_dict_payload(
            {"field": 1}, {"field": {"type": str, "required": True}}
        )
        assert validated is None
        assert error is not None
        assert error["data"]["code"] == validation.ErrorCodes.INVALID_FIELD

        validated, error = validation._validate_dict_payload(
            {"field": "way too long"}, {"field": {"type": str, "required": True, "max_value_len": 3}}
        )
        assert validated is None
        assert error is not None
        assert error["data"]["code"] == validation.ErrorCodes.INVALID_FIELD

        resp = validation._error_response({"id": 7}, "boom")
        assert resp["type"] == "error"
        assert resp["id"] == 7
        assert resp["data"]["code"] == validation.ErrorCodes.HANDLER_ERROR

