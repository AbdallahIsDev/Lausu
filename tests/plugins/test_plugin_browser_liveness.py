"""Debounced profile liveness: one empty WMI sample is not a dead browser."""

from __future__ import annotations

from tools.internal_plugins._common.bridge import chrome_profile
from tools.internal_plugins._common.bridge.chrome_profile import browser_liveness as real_liveness


def test_single_empty_enumeration_is_not_death(monkeypatch):
    samples = [[], [123], [123]]
    monkeypatch.setattr(chrome_profile, "resolve_browser_pids", lambda _dir, *, strict=False: samples.pop(0))
    monkeypatch.setattr(chrome_profile.time, "sleep", lambda _s: None)
    assert real_liveness("P") is True


def test_three_empty_enumerations_are_death(monkeypatch):
    monkeypatch.setattr(chrome_profile, "resolve_browser_pids", lambda _dir, *, strict=False: [])
    monkeypatch.setattr(chrome_profile.time, "sleep", lambda _s: None)
    assert real_liveness("P") is False


def test_enumeration_error_is_unknown_not_death(monkeypatch):
    def _boom(_dir, *, strict=False):
        raise OSError("WMI unavailable")

    monkeypatch.setattr(chrome_profile, "resolve_browser_pids", _boom)
    monkeypatch.setattr(chrome_profile.time, "sleep", lambda _s: None)
    assert real_liveness("P") is True


def test_wait_aborts_immediately_when_profile_dies(monkeypatch):
    from tools.internal_plugins._common.bridge import session

    calls = {"status": 0, "sleep": 0}

    def _status():
        calls["status"] += 1
        return {"browser": "connecting"}

    def _sleep(_s):
        calls["sleep"] += 1

    ok = session.ensure_browser(
        status_fn=_status,
        launch_fn=lambda: True,
        ready_fn=lambda snapshot: False,
        clock=type("Clock", (), {"monotonic": lambda self: calls["status"] * 0.5})(),
        timeout=10.0,
        alive_fn=lambda: False,
    )
    monkeypatch.setattr(session.time, "sleep", _sleep)
    assert ok is False
    assert calls["status"] <= 2, "a dead profile must abort on the first poll after launch"
