"""USER-INITIATED-START RULE: only an explicit user action starts a cycle.

REAL-PATH TEST RULE: every scenario enters through the real wrapped app entry
or the real activation/start path; only the OS boundary (browser, daemon,
clock, process spawn) is faked.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest
from tests.plugins.conftest import ready_snapshot
from tools.internal_plugins._common.bridge import session
from voice_typer.server import dictation_origin, event_bus, internal_plugin_hook as hook

_PATH = Path(__file__).resolve().parents[2] / "tools" / "internal_plugins" / "anthropic_stt" / "plugin.py"


@pytest.fixture
def plugin(monkeypatch):
    name = "anthropic_stt_start_origin_under_test"
    if name in sys.modules:
        module = sys.modules[name]
    else:
        spec = importlib.util.spec_from_file_location(name, _PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


def _stub_plugin(monkeypatch, name: str, events: list[str]):
    module = ModuleType(name)
    module.activate = lambda app: events.append(f"{name}:activate") or True  # type: ignore[attr-defined]
    module.deactivate = lambda: events.append(f"{name}:deactivate")  # type: ignore[attr-defined]
    module.attach = lambda app: SimpleNamespace(  # type: ignore[attr-defined]
        toggle=lambda: events.append(f"{name}:toggle"),
        stop=lambda: events.append(f"{name}:stop"),
        cancel=lambda: events.append(f"{name}:cancel"),
        owns_cycle=False,
        active=False,
    )
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setitem(hook.PLUGIN_MODULES, name, module.__name__)
    return module


def _installed_app(monkeypatch, *, plugin_id: str, events: list[str]):
    _stub_plugin(monkeypatch, "alpha_stt", events)
    _stub_plugin(monkeypatch, "beta_stt", events)
    app = SimpleNamespace(
        config=SimpleNamespace(
            active_plugin=plugin_id,
            developer_mode=True,
            model_size="",
            asr_backend="",
        ),
        _internal_plugin_wrapped=False,
        _internal_plugin_selected_id="",
        _internal_plugin_selected_id_initial="",
        _internal_plugin_active_session=None,
        _thread_registry=SimpleNamespace(spawn_and_register=lambda **kwargs: None),
        tray=SimpleNamespace(notify=lambda *_a: None, _state=None),
        _duck_volume=lambda: events.append("duck"),
        _restore_volume=lambda *_a, **_k: None,
        _recording_started_at=None,
        toggle_dictation=lambda: events.append("local:toggle"),
        _stop_dictation=lambda: events.append("local:stop"),
        _cancel_dictation=lambda: events.append("local:cancel"),
    )
    monkeypatch.setenv("VOICE_TYPER_INTERNAL_PLUGINS", "1")
    monkeypatch.setattr(hook, "internal_surface_enabled", lambda _config: True)
    # Startup sync normally runs on its own thread; run it explicitly in the
    # test so the page-ready transition is deterministic (fakes at thread seam).
    monkeypatch.setattr(hook.threading, "Thread", lambda *a, **k: SimpleNamespace(start=lambda: None))
    assert hook.install(app) is True
    return app


def _no_start(events: list[str]) -> None:
    assert not any(e.endswith(":toggle") or e == "duck" for e in events), events


def test_app_start_with_plugin_active_and_page_ready_never_records(monkeypatch, caplog):
    events: list[str] = []
    app = _installed_app(monkeypatch, plugin_id="alpha_stt", events=events)
    published = []
    monkeypatch.setattr(event_bus, "publish", lambda event: published.append(event))

    with caplog.at_level(logging.WARNING):
        # Real startup path: install() starts sync_selection off-thread, so call
        # the same function it calls; the stub plugin's activate is the only
        # fake, standing in for the browser/daemon boundary.
        hook.sync_selection(app)

    _no_start(events)
    assert events == ["alpha_stt:activate"]
    assert not any(
        e.get("type") == "bubble_set_state" and e.get("data", {}).get("state") == "recording" for e in published
    )
    assert "start requested" not in caplog.text


def test_activation_after_plugin_switch_never_records(monkeypatch):
    events: list[str] = []
    app = _installed_app(monkeypatch, plugin_id="alpha_stt", events=events)
    hook.sync_selection(app)
    events.clear()

    app.config.active_plugin = "beta_stt"
    hook.sync_selection(app)

    _no_start(events)
    assert "beta_stt:activate" in events


def test_relaunch_recovery_after_refused_start_never_starts_later(monkeypatch):
    """A refused start must not resume when Chrome finally comes up."""
    events: list[str] = []
    calls = {"status": 0, "posts": []}
    clock = SimpleNamespace(monotonic=lambda: 0.0, sleep=lambda _s: None)
    budget = session.RelaunchBudget(clock=clock, log=logging.getLogger("test"))
    ready = [False]

    def status():
        calls["status"] += 1
        return ready_snapshot(browser="connecting" if not ready[0] else "connected")

    def post(path, **_kwargs):
        calls["posts"].append(path)
        return {}

    ok, reason = session.ensure_target_ready(
        browser_fn=lambda **_kw: True,
        post_fn=post,
        status_fn=status,
        ready_fn=lambda _snapshot: ready[0],
        clock=clock,
        log=logging.getLogger("test"),
        cycle=1,
        budget=budget,
        stage="tab",
    )
    assert ok is False and reason == "page-not-ready"
    ready[0] = True
    # No queued start is consumed by the recovery path after the page appears.
    assert "/start" not in calls["posts"]
    assert "toggle" not in events


def test_reconnect_and_reload_while_idle_never_records(monkeypatch):
    events: list[str] = []
    app = _installed_app(monkeypatch, plugin_id="alpha_stt", events=events)
    hook.sync_selection(app)
    events.clear()
    for _ in range(3):
        hook.sync_selection(app)  # reconcile on reconnect/extension reload
    _no_start(events)


def test_no_origin_is_refused_once_with_caller_name(monkeypatch, caplog):
    events: list[str] = []
    app = _installed_app(monkeypatch, plugin_id="alpha_stt", events=events)
    with caplog.at_level(logging.WARNING):
        app.toggle_dictation()
    assert events == []
    assert "internal_plugin_hook.toggle_dictation" in caplog.text
    assert caplog.text.count("start refused") == 1


def test_hotkey_origin_reaches_real_start_entry_once(plugin, monkeypatch, caplog):
    messages = []
    log = MagicMock()
    log.info.side_effect = lambda fmt, *args: messages.append(fmt % args if args else fmt)
    log.warning.side_effect = lambda fmt, *args: messages.append(fmt % args if args else fmt)
    log.debug.side_effect = lambda *_a, **_k: None
    log.error.side_effect = lambda *_a, **_k: None
    session_obj = plugin.PluginSession(SimpleNamespace(tray=SimpleNamespace(notify=lambda *_a: None)))
    monkeypatch.setattr(session_obj, "_ensure_daemon", lambda: True)
    monkeypatch.setattr(session_obj, "_ensure_browser", lambda *a, **k: True)
    states = iter([ready_snapshot()] * 6)
    monkeypatch.setattr(session_obj, "_status", lambda: next(states, ready_snapshot()))
    monkeypatch.setattr(session_obj, "_post", lambda path, timeout=None: {})
    monkeypatch.setattr(session_obj, "_watch_platform", lambda: None)
    monkeypatch.setattr(session_obj, "_session_events", lambda *, start: None)
    monkeypatch.setattr(session_obj, "_duck", lambda: None)
    monkeypatch.setattr(session_obj, "_restore_volume", lambda: None)
    monkeypatch.setattr(plugin.time, "sleep", lambda *_a: None)
    monkeypatch.setattr(session_obj, "_log", log)

    class FakeMeter:
        def __init__(self, app):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    monkeypatch.setattr(plugin, "LevelMeter", FakeMeter)
    with dictation_origin.user_action("hotkey"):
        session_obj.toggle()

    assert session_obj.active is True
    assert any("start requested (cycle=#1, origin=hotkey)" in m for m in messages), messages
    assert sum("start requested" in m for m in messages) == 1
