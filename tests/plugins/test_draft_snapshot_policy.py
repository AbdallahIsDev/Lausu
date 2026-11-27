"""Draft snapshot logging/backoff and start-order policy (REAL-PATH entry)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.plugins.conftest import ready_snapshot
from voice_typer.server import dictation_origin

_PATH = Path(__file__).resolve().parents[2] / "tools" / "internal_plugins" / "anthropic_stt" / "plugin.py"
SENTENCE = "This is what your dictated text sounds like when spoken back to you."


@pytest.fixture
def plugin(monkeypatch):
    name = "anthropic_stt_snapshot_policy_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _session(plugin, monkeypatch, *, posts, statuses=None, watch=True):
    messages = []
    log = SimpleNamespace(
        debug=lambda fmt, *a: messages.append(fmt % a if a else fmt),
        info=lambda fmt, *a: messages.append(fmt % a if a else fmt),
        warning=lambda fmt, *a: messages.append(fmt % a if a else fmt),
        error=lambda fmt, *a: messages.append(fmt % a if a else fmt),
        exception=lambda fmt, *a: messages.append(fmt % a if a else fmt),
    )
    session = plugin.PluginSession(SimpleNamespace(tray=SimpleNamespace(notify=lambda *_a: None)), log=log)
    state = iter(statuses or [ready_snapshot()] * 5)
    calls = []

    def post(path, timeout=None):
        calls.append(path)
        return posts(path, timeout)

    monkeypatch.setattr(session, "_ensure_daemon", lambda: True)
    monkeypatch.setattr(session, "_ensure_browser", lambda *a, **k: True)
    monkeypatch.setattr(session, "_status", lambda: next(state, ready_snapshot()))
    monkeypatch.setattr(session, "_post", post)
    monkeypatch.setattr(session, "_session_events", lambda *, start: None)
    monkeypatch.setattr(session, "_duck", lambda: None)
    monkeypatch.setattr(session, "_restore_volume", lambda: None)
    monkeypatch.setattr(session, "_critical_notify", lambda *_a: None)
    monkeypatch.setattr(session, "_deliver", lambda *_a, **_k: None)
    monkeypatch.setattr(plugin.time, "sleep", lambda *_a: None)
    if not watch:
        monkeypatch.setattr(session, "_watch_platform", lambda: None)

    class FakeMeter:
        def __init__(self, app):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(plugin, "LevelMeter", FakeMeter)
    return session, messages, calls


def test_pre_start_baseline_read_is_never_logged(plugin, monkeypatch):
    session, messages, _calls = _session(plugin, monkeypatch, posts=lambda p, t: {"text": SENTENCE}, watch=False)
    assert session._read_draft(purpose="baseline") == SENTENCE
    assert not any("draft snapshot read" in m for m in messages)


def test_backoff_polls_far_less_than_once_per_second_during_silence(plugin, monkeypatch):
    now = [0.0]

    def monotonic():
        return now[0]

    monkeypatch.setattr(plugin.time, "monotonic", monotonic)
    monkeypatch.setattr(plugin.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    statuses = [ready_snapshot(state="recording", browser="connected")] * 61 + [
        ready_snapshot(state="idle", browser="disconnected")
    ] * 5
    session, messages, calls = _session(
        plugin,
        monkeypatch,
        posts=lambda p, t: {"text": SENTENCE} if p == "/draft-snapshot" else {},
        statuses=statuses,
    )
    with dictation_origin.user_action("hotkey"):
        session.start()
    watch = session._watch_platform
    monkeypatch.setattr(session, "_watch_platform", lambda: None)
    watch()
    total_snapshots = calls.count("/draft-snapshot")
    assert total_snapshots <= 25, total_snapshots  # 1 baseline + ~20 slow reads, not 60+
    assert not any("draft snapshot read" in m for m in messages), messages
    assert session._live_snapshot == SENTENCE
    assert any("recovered=" in m for m in messages)


def test_burst_of_changes_logs_each_change_at_most_once(plugin, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(plugin.time, "monotonic", lambda: now[0])
    words = ["one", "two", "three", "four", "five", "six"]
    index = [0]

    def posts(path, timeout=None):
        if path != "/draft-snapshot":
            return {}
        i = min(index[0], len(words) - 1)
        index[0] += 1
        return {"text": " ".join(words[: i + 1]), "source": "live-selector"}

    session, messages, _calls = _session(plugin, monkeypatch, posts=posts, watch=False)
    with dictation_origin.user_action("hotkey"):
        session.start()
    for _ in words:
        session._poll_live_text()
        now[0] += 1
    lines = [m for m in messages if "draft snapshot read" in m or "live draft snapshot" in m]
    assert len(lines) <= 2, lines  # 5 s rate limit per kind
    assert session._snapshot_changes == len(words) - 1


def test_summary_is_emitted_exactly_once_per_cycle(plugin, monkeypatch):
    session, messages, _calls = _session(plugin, monkeypatch, posts=lambda p, t: {}, watch=False)
    session._emit_snapshot_summary()
    session._emit_snapshot_summary()
    assert sum("draft snapshot summary" in m for m in messages) == 1


def test_refused_start_never_starts_the_snapshot_loop(plugin, monkeypatch):
    started = []

    def posts(path, timeout=None):
        if path == "/draft-snapshot":
            return {"text": SENTENCE}
        if path == "/start":
            raise RuntimeError("bridge down")
        return {}

    session, messages, calls = _session(plugin, monkeypatch, posts=posts, watch=False)
    monkeypatch.setattr(session, "_watch_platform", lambda: started.append("watch"))
    with dictation_origin.user_action("hotkey"):
        session.start()
    assert session.active is False
    assert started == []
    assert session._live_snapshot == ""
    assert not any("draft snapshot summary" in m for m in messages)
    assert calls.count("/draft-snapshot") == 1  # pre-start baseline only


def test_cancel_clears_snapshot_and_ends_summary(plugin, monkeypatch):
    session, messages, _calls = _session(plugin, monkeypatch, posts=lambda p, t: {"text": SENTENCE}, watch=False)
    with dictation_origin.user_action("hotkey"):
        session.start()
    session._poll_live_text()
    assert session.cancel() is True
    assert session._live_snapshot == ""
    assert sum("draft snapshot summary" in m for m in messages) == 1
