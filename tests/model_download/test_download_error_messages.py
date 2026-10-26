"""User-facing text for failed model downloads."""

from __future__ import annotations

import logging
import sys
import types
from unittest.mock import MagicMock

import pytest
from voice_typer.server.service.model._download_dispatch import (
    _DISK_FULL_MESSAGE,
    _NETWORK_DOWN_MESSAGE,
    _STALLED_DOWNLOAD_MESSAGE,
    _friendly_download_error,
    _transport_error_types,
)

NETWORK_MESSAGES = (
    "[Errno 11001] getaddrinfo failed",
    "Name or service not known",
    "Temporary failure in name resolution",
    "Network is unreachable",
    "Connection refused",
    "Connection reset by peer",
    "Cannot send a request, as the client has been closed.",
)
STALLED_MESSAGES = (
    "Read timed out",
    "The download stalled",
    "no progress for 120s",
)
DISK_FULL_MESSAGES = (
    "[Errno 28] No space left on device",
    "There is not enough space on the disk",
    "[WinError 112] The disk is full",
)


class TestFriendlyDownloadError:
    def test_httpx_connect_error_maps_to_network_message(self):
        httpx = pytest.importorskip("httpx")
        assert _friendly_download_error(httpx.ConnectError("boom")) == _NETWORK_DOWN_MESSAGE

    def test_httpcore_connect_error_maps_to_network_message(self):
        httpcore = pytest.importorskip("httpcore")
        assert _friendly_download_error(httpcore.ConnectError("boom")) == _NETWORK_DOWN_MESSAGE

    @pytest.mark.parametrize("stack", ["httpx", "httpx2"])
    def test_connect_timeout_maps_to_network_message(self, stack):
        """httpx 2.x drops the ConnectTimeout -> ConnectError subclass link."""
        module = pytest.importorskip(stack)
        assert _friendly_download_error(module.ConnectTimeout("boom")) == _NETWORK_DOWN_MESSAGE

    def test_httpx2_connect_error_maps_to_network_message(self):
        httpx2 = pytest.importorskip("httpx2")
        assert _friendly_download_error(httpx2.ConnectError("boom")) == _NETWORK_DOWN_MESSAGE

    def test_connect_errors_are_collected_from_every_installed_stack(self, monkeypatch):
        """huggingface-hub 2.x swaps httpx/httpcore for httpx2/httpcore2."""

        class ConnectError(OSError):
            """Stand-in for the next-generation stack's connect error."""

        stack = types.ModuleType("httpx2")
        stack.ConnectError = ConnectError
        monkeypatch.setitem(sys.modules, "httpx2", stack)

        assert ConnectError in _transport_error_types()
        assert _friendly_download_error(ConnectError("boom")) == _NETWORK_DOWN_MESSAGE

    @pytest.mark.parametrize("message", NETWORK_MESSAGES)
    def test_network_failures(self, message):
        assert _friendly_download_error(OSError(message)) == _NETWORK_DOWN_MESSAGE

    @pytest.mark.parametrize("message", STALLED_MESSAGES)
    def test_stalled_downloads(self, message):
        assert _friendly_download_error(OSError(message)) == _STALLED_DOWNLOAD_MESSAGE

    @pytest.mark.parametrize("message", DISK_FULL_MESSAGES)
    def test_disk_full(self, message):
        assert _friendly_download_error(OSError(message)) == _DISK_FULL_MESSAGE

    def test_unknown_error_keeps_redacted_url(self):
        text = _friendly_download_error(RuntimeError("https://user:hunter2@huggingface.co/x?token=abc123secret"))
        assert "hunter2" not in text
        assert "abc123secret" not in text
        assert "huggingface.co/x" in text

    def test_unknown_error_redacts_bearer_token(self):
        text = _friendly_download_error(RuntimeError("401 Unauthorized: Authorization: Bearer sk-live-abcdef123456"))
        assert "sk-live-abcdef123456" not in text
        assert "401 Unauthorized" in text

    def test_cause_chain_is_walked(self):
        outer = RuntimeError("snapshot download failed")
        outer.__cause__ = OSError("[Errno 11001] getaddrinfo failed")
        assert _friendly_download_error(outer) == _NETWORK_DOWN_MESSAGE

    def test_context_chain_is_walked(self):
        with pytest.raises(RuntimeError) as caught:
            try:
                raise OSError("[Errno 28] No space left on device")
            except OSError:
                raise RuntimeError("download failed") from None
        assert caught.value.__context__ is not None
        assert _friendly_download_error(caught.value) == _DISK_FULL_MESSAGE

    def test_cyclic_chain_terminates(self):
        first = RuntimeError("first")
        second = RuntimeError("second")
        first.__cause__ = second
        second.__context__ = first
        assert _friendly_download_error(first) == "first"


def _make_service():
    from voice_typer.server.service import LausuService

    app = MagicMock()
    app.config.qwen_model_path = None
    app.config.huggingface_consent = True
    return LausuService(app)


class TestDispatchFailureSurfaces:
    @pytest.fixture()
    def spies(self, monkeypatch):
        from voice_typer.server.service import _download_helpers

        progress: list[tuple[int, str]] = []
        toasts: list[str] = []
        monkeypatch.setattr(
            _download_helpers,
            "push_progress",
            lambda _bus, name, pct, message, **_kw: progress.append((pct, message)),
        )
        monkeypatch.setattr(
            _download_helpers,
            "notify",
            lambda _tray, _name, _title, body: toasts.append(body),
        )
        return progress, toasts

    def test_network_failure_reaches_progress_toast_and_error(self, spies, monkeypatch, caplog):
        progress, toasts = spies
        service = _make_service()

        def _boom(*_args, **_kwargs):
            raise ConnectionError("[Errno 11001] getaddrinfo failed")

        monkeypatch.setattr("voice_typer.server.model_registry.get_model_metadata", _boom)

        with caplog.at_level(logging.ERROR, logger="voice_typer.server.service.model._download_dispatch"):
            result = service.download_model("tiny")

        assert result["success"] is False
        assert result["error"] == _NETWORK_DOWN_MESSAGE
        assert any(_NETWORK_DOWN_MESSAGE in message for _, message in progress)
        assert any(_NETWORK_DOWN_MESSAGE in body for body in toasts)
        assert "getaddrinfo failed" in caplog.text, "the server log keeps the full transport detail"

    def test_unknown_failure_redacts_secret_on_every_surface(self, spies, monkeypatch):
        progress, toasts = spies
        service = _make_service()

        def _boom(*_args, **_kwargs):
            raise RuntimeError("https://user:hunter2@huggingface.co/x?token=abc123secret")

        monkeypatch.setattr("voice_typer.server.model_registry.get_model_metadata", _boom)

        result = service.download_model("tiny")

        for surface in (result["error"], *(message for _, message in progress), *toasts):
            assert "hunter2" not in surface
            assert "abc123secret" not in surface
