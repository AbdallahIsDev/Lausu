"""Pack-worker reconnect log policy: one WARN per outage, then DEBUG.

A worker that never comes up used to re-emit the same WARNING line every
backoff tick for the whole session, burying real signals.
"""

from __future__ import annotations

import asyncio
import logging

from voice_typer.server import worker_session


class _FlakyClient:
    """Fails ``failures`` current-checks, then reports superseded."""

    port = 5123

    def __init__(self, failures: int) -> None:
        self._failures = failures
        self._checks = 0

    def _is_current(self, generation: int) -> bool:
        self._checks += 1
        return self._checks <= self._failures

    def _current_url(self) -> str:
        return "ws://127.0.0.1:5123"


def test_reconnect_warns_once_then_debugs(monkeypatch, caplog):
    def _refuse(url, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("websockets.asyncio.client.connect", _refuse)
    monkeypatch.setattr(worker_session, "backoff_delay", lambda attempt: 0.0)
    client = _FlakyClient(failures=6)

    with caplog.at_level(logging.DEBUG, logger=worker_session.__name__):
        asyncio.run(worker_session.connect_loop(client, generation=1))

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    retries = [
        record for record in caplog.records if record.getMessage().startswith("[WORKER] worker still unreachable")
    ]
    assert len(warnings) == 1
    assert len(retries) == 2
