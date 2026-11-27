"""Partial recovery enters through the real session start/stop/watch paths.

Fakes are only at the OS boundary (browser state, daemon POST, clock). The
snapshot itself stays in RAM and is never logged or written to a file.
"""

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


def dying_statuses(recording_reads: int = 40):
    """A live capture, then a browser that is no longer answering."""
    return [ready_snapshot(state="recording")] * recording_reads + [
        ready_snapshot(state="idle", browser="disconnected")
    ] * 40


@pytest.fixture
def plugin(monkeypatch):
    name = "anthropic_stt_partial_recovery_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _session(plugin, monkeypatch, *, posts=None, statuses=None):
    app = SimpleNamespace(tray=SimpleNamespace(notify=lambda *_a: None))
    session = plugin.PluginSession(app)
    delivered = []
    notices = []

    def post(path, timeout=None):
        if posts is not None:
            return posts(path, timeout)
        return {}

    state = iter(statuses or [ready_snapshot()])
    fallback = ready_snapshot() if statuses is None else ready_snapshot(state="idle", browser="disconnected")

    monkeypatch.setattr(session, "_ensure_daemon", lambda: True)
    monkeypatch.setattr(session, "_ensure_browser", lambda *a, **k: True)
    monkeypatch.setattr(session, "_status", lambda: next(state, fallback))
    monkeypatch.setattr(session, "_post", post)
    monkeypatch.setattr(session, "_session_events", lambda *, start: None)
    monkeypatch.setattr(session, "_duck", lambda: None)
    monkeypatch.setattr(session, "_restore_volume", lambda: None)
    monkeypatch.setattr(session, "_deliver", lambda text, duration, **kw: delivered.append((text, kw)))
    monkeypatch.setattr(session, "_critical_notify", lambda msg, category: notices.append((msg, category)))
    monkeypatch.setattr(plugin.time, "sleep", lambda *_a: None)
    # start() would spawn a watcher thread; drive the SAME method explicitly so
    # the test controls the status sequence (no second consumer of the fakes).
    watch = session._watch_platform
    monkeypatch.setattr(session, "_watch_platform", lambda: None)

    class FakeMeter:
        def __init__(self, app):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(plugin, "LevelMeter", FakeMeter)
    return session, delivered, notices, watch


def _start(plugin, session):
    with dictation_origin.user_action("hotkey"):
        session.start()
    assert session.active is True


def test_tab_closed_with_words_captured_delivers_once(plugin, monkeypatch, caplog):
    def posts(path, timeout=None):
        if path == "/draft-snapshot":
            return {"text": SENTENCE, "source": "composer"}
        return {}

    session, delivered, notices, watch = _session(
        plugin,
        monkeypatch,
        posts=posts,
        statuses=dying_statuses(6),
    )
    with caplog.at_level("WARNING"):
        _start(plugin, session)
        watch()

    assert session.active is False
    assert len(delivered) == 1
    assert delivered[0][0] == SENTENCE
    assert delivered[0][1]["method"] == "recovered (partial)"
    assert len(delivered) == 1
    assert "recovered=13 words" in caplog.text
    assert SENTENCE not in caplog.text
    assert "recovered the text captured so far (13 words)" in notices[0][0]


def test_profile_killed_mid_recording_uses_last_ram_snapshot(plugin, monkeypatch):
    polls = [0]

    def posts(path, timeout=None):
        if path == "/draft-snapshot":
            polls[0] += 1
            if polls[0] == 1:
                return {"text": ""}  # baseline before speech
            if polls[0] == 2:
                return {"text": SENTENCE}  # cumulative snapshot in RAM
            raise RuntimeError("browser is gone")
        return {}

    session, delivered, notices, watch = _session(
        plugin,
        monkeypatch,
        posts=posts,
        statuses=dying_statuses(40),
    )
    _start(plugin, session)
    watch()

    assert delivered[0][0] == SENTENCE
    assert len(delivered) == 1
    assert notices[0][1] == "recording-lost"


def test_bridge_dropped_with_page_alive_rereads_full_text(plugin, monkeypatch):
    def posts(path, timeout=None):
        if path == "/draft-snapshot":
            return {"text": SENTENCE}
        if path == "/stop":
            raise RuntimeError("bridge timed out")
        return {}

    session, delivered, notices, watch = _session(plugin, monkeypatch, posts=posts)
    _start(plugin, session)
    session.stop()

    assert delivered[0][0] == SENTENCE
    assert delivered[0][1]["method"] == "recovered (partial)"
    assert notices


def test_nothing_spoken_keeps_the_nothing_captured_notice(plugin, monkeypatch):
    session, delivered, notices, watch = _session(
        plugin,
        monkeypatch,
        posts=lambda path, timeout=None: {"text": ""} if path == "/draft-snapshot" else {},
        statuses=dying_statuses(40),
    )
    _start(plugin, session)
    watch()

    assert delivered == []
    assert "nothing was captured" in notices[0][0]


def test_esc_cancel_discards_the_snapshot(plugin, monkeypatch):
    def posts(path, timeout=None):
        return {"text": SENTENCE} if path == "/draft-snapshot" else {}

    session, delivered, notices, watch = _session(plugin, monkeypatch, posts=posts)
    _start(plugin, session)
    assert session._poll_live_text() is True
    assert session._live_snapshot == SENTENCE
    assert session.cancel() is True

    assert delivered == []
    assert notices == []
    assert session._live_snapshot == ""


def test_normal_stop_ignores_the_snapshot(plugin, monkeypatch):
    def posts(path, timeout=None):
        if path == "/draft-snapshot":
            return {"text": SENTENCE}
        if path == "/stop":
            return {"text": "Final text wins.", "duration_s": 1.0}
        return {}

    session, delivered, notices, watch = _session(plugin, monkeypatch, posts=posts)
    _start(plugin, session)
    session._poll_live_text()
    session.stop()

    assert len(delivered) == 1 and delivered[0][0] == "Final text wins."
    assert delivered[0][1].get("method") is None, "final stop text must not be marked as recovered"
    assert notices == []


def test_preexisting_draft_is_not_recovered_as_this_cycle(plugin, monkeypatch):
    old = "Typed words that existed before the hotkey."
    dictated = "Only these words were dictated."
    reads = [0]

    def posts(path, timeout=None):
        if path != "/draft-snapshot":
            return {}
        reads[0] += 1
        return {"text": old if reads[0] == 1 else dictated}

    session, delivered, _notices, _watch = _session(plugin, monkeypatch, posts=posts)
    with dictation_origin.user_action("hotkey"):
        session.start()
    assert session._snapshot_baseline == old
    session._poll_live_text()
    session._poll_live_text()
    session._recover_lost_cycle(trigger="browser-lost")
    assert delivered[0][0] == dictated
    assert old not in delivered[0][0]


def test_text_typed_during_recording_is_part_of_the_live_draft(plugin, monkeypatch):
    parts = ["first dictated words", "first dictated words and typed words"]
    index = [0]

    def posts(path, timeout=None):
        if path != "/draft-snapshot":
            return {}
        i = min(index[0], len(parts) - 1)
        index[0] += 1
        return {"text": parts[i]}

    session, _delivered, _notices, _watch = _session(plugin, monkeypatch, posts=posts)
    with dictation_origin.user_action("hotkey"):
        session.start()
    session._poll_live_text()
    session._poll_live_text()
    assert session._live_snapshot == parts[-1]


def test_snapshot_never_written_to_disk(plugin, monkeypatch, tmp_path):
    def posts(path, timeout=None):
        return {"text": SENTENCE} if path == "/draft-snapshot" else {}

    session, _delivered, _notices, _watch = _session(plugin, monkeypatch, posts=posts)
    _start(plugin, session)
    session._poll_live_text()
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    hits = [p for p in files if SENTENCE in p.read_text(encoding="utf-8", errors="ignore")]
    assert hits == []
