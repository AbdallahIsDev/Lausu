"""Disconnect log wording: routine teardown drops must not read as errors."""

from __future__ import annotations

import logging

from voice_typer.server.sidecar_ws import _abnormal_close_note


class TestAbnormalCloseNote:
    def test_shutdown_drop_has_no_error_prefix(self) -> None:
        exc = RuntimeError("no close frame received or sent")
        note = _abnormal_close_note(exc, shutting_down=True)
        assert "error:" not in note
        assert "closed during shutdown" in note
        assert "no close frame received or sent" in note

    def test_mid_session_drop_keeps_error_prefix(self) -> None:
        exc = RuntimeError("no close frame received or sent")
        note = _abnormal_close_note(exc, shutting_down=False)
        assert note == "error: no close frame received or sent"


class TestCloseLineLevel:
    """The ``connection closed`` line itself must drop to DEBUG during
    teardown (routine host exit) and stay INFO mid-session."""

    async def _run_close(self, monkeypatch, shutting_down: bool):
        import threading
        from unittest.mock import MagicMock

        from voice_typer.server.sidecar_ws_internals import (
            handshake as _handshake_mod,
            read_loop as _read_loop_mod,
        )
        from websockets.exceptions import ConnectionClosedError

        from tests.fixtures.sidecar_ws_test_helpers import _make_fake_server

        server = _make_fake_server()
        server._lock = threading.Lock()
        server.app._shutting_down = shutting_down

        async def _authed(_ws) -> bool:
            return True

        async def _unique(_ws, _server, _peer) -> bool:
            return True

        async def _raise_closed(_ws, _server, _dispatch):
            raise ConnectionClosedError(None, None)

        monkeypatch.setattr(_handshake_mod, "_authenticate", _authed)
        from voice_typer.server import sidecar_ws as _sws_mod

        monkeypatch.setattr(_sws_mod, "_check_duplicate_auth", _unique)
        monkeypatch.setattr(_read_loop_mod, "_read_loop", _raise_closed)

        ws = MagicMock()
        ws.remote_address = ("127.0.0.1", 9999)

        async def _noop_send(_payload: str) -> None:
            return None

        async def _noop_close(*_a: object, **_k: object) -> None:
            return None

        ws.send = _noop_send
        ws.close = _noop_close

        from voice_typer.server import sidecar_ws as _sws

        await _sws._handle_connection_inner(ws, server, MagicMock(), ("127.0.0.1", 9999))
        return server

    async def test_shutdown_drop_logs_at_debug(self, monkeypatch, caplog) -> None:
        with caplog.at_level(logging.DEBUG, logger="voice_typer.server.sidecar_ws"):
            await self._run_close(monkeypatch, shutting_down=True)
        lines = [r for r in caplog.records if "connection closed" in r.message]
        assert len(lines) == 1, f"expected one connection-closed line, got {len(lines)}"
        assert lines[0].levelno == logging.DEBUG, (
            f"teardown drop must log at DEBUG, got {lines[0].levelname}"
        )

    async def test_mid_session_drop_logs_at_info(self, monkeypatch, caplog) -> None:
        with caplog.at_level(logging.DEBUG, logger="voice_typer.server.sidecar_ws"):
            await self._run_close(monkeypatch, shutting_down=False)
        lines = [r for r in caplog.records if "connection closed" in r.message]
        assert len(lines) == 1, f"expected one connection-closed line, got {len(lines)}"
        assert lines[0].levelno == logging.INFO, (
            f"mid-session drop must stay at INFO, got {lines[0].levelname}"
        )
