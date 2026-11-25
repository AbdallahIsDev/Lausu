"""Bridge keepalive logs status transitions, not every 20-second poll.

The loop makes real extension traffic every 20 s to keep the MV3 worker awake;
logging each round trip buried real plugin events in identical DEBUG lines.
"""

from __future__ import annotations

import logging

from tools.internal_plugins.anthropic_stt import plugin as plugin_module

_LOGGER = "voice_typer.internal_plugin.anthropic_stt"
_CONNECTED = {"browser": "connected", "page": "ok"}
_DISCONNECTED = {"browser": "disconnected", "page": "unknown"}


def _lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == _LOGGER]


class TestKeepaliveLogging:
    def test_identical_polls_log_once(self, caplog) -> None:
        keepalive = plugin_module.BridgeKeepalive(interval_s=3600.0)
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            for _ in range(25):
                keepalive._note_status(_CONNECTED)
        lines = _lines(caplog)
        assert len(lines) == 1, f"25 identical keepalives must log once, got {lines!r}"
        assert "browser=connected" in lines[0] and "page=ok" in lines[0]

    def test_status_transitions_are_logged(self, caplog) -> None:
        keepalive = plugin_module.BridgeKeepalive(interval_s=3600.0)
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            for status in (_CONNECTED, _CONNECTED, _DISCONNECTED, _DISCONNECTED, _CONNECTED):
                keepalive._note_status(status)
        lines = _lines(caplog)
        assert len(lines) == 3, lines
        assert "browser=disconnected" in lines[1]

    def test_missing_status_is_a_transition_to_unknown(self, caplog) -> None:
        keepalive = plugin_module.BridgeKeepalive(interval_s=3600.0)
        with caplog.at_level(logging.DEBUG, logger=_LOGGER):
            keepalive._note_status(_CONNECTED)
            keepalive._note_status(None)
            keepalive._note_status(None)
        lines = _lines(caplog)
        assert len(lines) == 2, lines
        assert "browser=unknown" in lines[1] and "page=unknown" in lines[1]

    def test_reactivation_does_not_relog_an_unchanged_status(self, caplog) -> None:
        keepalive = plugin_module.BridgeKeepalive(interval_s=3600.0)
        keepalive._last_status = ("connected", "ok")
        try:
            keepalive.start()
            with caplog.at_level(logging.DEBUG, logger=_LOGGER):
                keepalive._note_status(_CONNECTED)
            assert _lines(caplog) == [], "unchanged state must not be logged again"
        finally:
            keepalive.stop()
            if keepalive._thread is not None:
                keepalive._thread.join(timeout=5.0)
