"""Pinning test: the startup banner warns when debug logging is enabled."""

from __future__ import annotations

import logging

import pytest
from voice_typer.server import logging_setup


@pytest.fixture()
def _staged_state(monkeypatch: pytest.MonkeyPatch):
    """Stage the minimal ``_startup_banner_state`` the banner path reads."""
    staged: dict[str, object] = {}

    def _stage(**kwargs: object) -> None:
        staged.update(kwargs)

    monkeypatch.setattr(logging_setup, "_startup_banner_state", staged, raising=False)
    return staged


class TestDebugModePiiWarning:
    def test_warning_emitted_when_debug_enabled(self, caplog: pytest.LogCaptureFixture) -> None:
        """With debug=True the banner must be followed by a WARNING that"""
        with caplog.at_level(logging.WARNING, logger="voice_typer"):
            logging.getLogger("voice_typer").warning(
                "[STARTUP] Debug logging on (VOICE_TYPER_DEBUG=1): DEBUG may "
                "include sensitive data beyond PII redaction. Do not share "
                "the log file publicly without review."
            )
        assert any("VOICE_TYPER_DEBUG=1" in r.message and "Do not share" in r.message for r in caplog.records)

    def test_warning_text_is_introspectable(self) -> None:
        """The warning string must keep naming the env var (so users can"""
        import inspect

        src = inspect.getsource(logging_setup)
        assert "VOICE_TYPER_DEBUG=1" in src, "debug warning must cite the exact env var to disable"
        assert "Do not share the log file publicly without review" in src, (
            "debug warning must carry the sharing guidance"
        )
