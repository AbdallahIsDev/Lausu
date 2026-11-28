"""Real-entry tests for ASR idle unload of the worker process.

The entry is the shared model lifecycle (idle loop / ASR policy), not a
private helper. Only the OS boundary (host event relay, worker socket,
process clock) is faked.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest
from voice_typer.server import event_bus
from voice_typer.server.model_lifecycle import builtins, idle, registry, worker_lifecycle


class FakeClient:
    def __init__(self, *, port: int | None = 7100, busy: bool = False) -> None:
        self.port = port
        self.busy = busy
        self.closed = 0
        self.aborted = 0

    def has_outstanding(self) -> bool:
        return self.busy

    def abort_all_outstanding(self) -> int:
        self.aborted += 1
        return 1

    def close(self) -> None:
        self.closed += 1
        self.port = None


class FakeTray:
    def __init__(self) -> None:
        self.states: list[tuple[Any, str]] = []
        self.notices: list[tuple[str, str]] = []
        self.safety: list[tuple[str, str]] = []

    def set_state(self, state: Any, message: str) -> None:
        self.states.append((state, message))

    def notify(self, title: str, message: str) -> None:
        self.notices.append((title, message))

    def notify_safety(self, title: str, message: str) -> None:
        self.safety.append((title, message))


class FakeModels:
    def __init__(self, *, worker_backed: bool = True) -> None:
        self.engine = SimpleNamespace(is_loaded=True, worker_backed=worker_backed, _loaded=True)
        self.cancelled = 0
        self.reloads = 0
        self._registry = SimpleNamespace(is_busy=lambda name: False)

    def active_transcriber(self) -> Any:
        return self.engine

    def cancel_idle_unload_timer(self) -> None:
        self.cancelled += 1

    def ensure_active_engine_loaded(self) -> None:
        self.reloads += 1
        self.engine._loaded = True
        self.engine.is_loaded = True

    def wait_for_active_engine_loaded(self, timeout_s: float) -> Any:
        return self.engine


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> Any:
    idle._reset_for_tests()
    worker_lifecycle.reset_for_tests()
    events: list[dict] = []
    monkeypatch.setattr(event_bus, "publish", lambda event: events.append(event) or True)
    yield events
    idle._reset_for_tests()
    worker_lifecycle.reset_for_tests()


def _bind(minutes: int = 1, *, models: FakeModels | None = None) -> tuple[FakeModels, FakeTray]:
    models = models or FakeModels()
    tray = FakeTray()
    app = SimpleNamespace(
        config=SimpleNamespace(model_idle_unload_minutes=minutes),
        models=models,
        tray=tray,
        _shutting_down=False,
    )
    registry.bind_app(app)
    return models, tray


def _types(events: list[dict]) -> list[str]:
    return [event["type"] for event in events]


def test_idle_stop_goes_through_policy_and_stops_worker(monkeypatch, _reset) -> None:
    models, _ = _bind()
    client = FakeClient()
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: client)
    policy = builtins._AsrPolicy(name="asr", residency="core")

    policy.unload()

    assert "worker_unloaded" in _types(_reset)
    assert _reset[-1]["data"]["reason"] == "idle_timeout"
    assert client.aborted == 1
    assert client.closed == 1
    assert models.engine._loaded is False
    assert models.cancelled == 1
    assert policy.is_loaded(models) is False


def test_always_never_stops_worker(monkeypatch, _reset) -> None:
    _bind(minutes=0)
    client = FakeClient()
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: client)
    builtins._AsrPolicy(name="asr", residency="core").unload()
    assert "worker_unloaded" not in _types(_reset)
    assert client.closed == 0


def test_busy_worker_is_never_stopped(monkeypatch, _reset) -> None:
    _bind()
    client = FakeClient(busy=True)
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: client)
    policy = builtins._AsrPolicy(name="asr", residency="core")
    assert policy.is_busy() is True
    policy.unload()
    assert "worker_unloaded" not in _types(_reset)


def test_idle_connected_session_is_not_busy(monkeypatch, _reset) -> None:
    _bind()
    client = FakeClient()
    client._session_loop = object()  # connected at rest, no request in flight
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: client)
    policy = builtins._AsrPolicy(name="asr", residency="core")
    assert policy.is_busy() is False
    policy.unload()
    assert "worker_unloaded" in _types(_reset)


def test_two_unloads_publish_one_stop(monkeypatch, _reset) -> None:
    _bind()
    client = FakeClient()
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: client)
    policy = builtins._AsrPolicy(name="asr", residency="core")
    policy.unload()
    policy.unload()
    assert _types(_reset).count("worker_unloaded") == 1


def test_press_during_stop_waits_then_respawns(monkeypatch, _reset) -> None:
    models, _ = _bind()
    stopped = FakeClient()
    restarted = FakeClient()
    holder = {"client": stopped}
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: holder["client"])
    policy = builtins._AsrPolicy(name="asr", residency="core")
    policy.unload()

    def _respawn() -> None:
        time.sleep(0.05)
        holder["client"] = restarted
        worker_lifecycle.note_worker_started({"pid": 4242, "port": 7101})

    threading.Thread(target=_respawn, daemon=True).start()
    assert policy.load(models) is True
    assert "offline_pack_verified" in _types(_reset)
    assert models.reloads == 1
    assert policy.is_loaded(models) is True


def test_press_during_stop_orders_stop_before_restart(monkeypatch, _reset) -> None:
    _bind()
    stopped = FakeClient()
    restarted = FakeClient()
    holder = {"client": stopped}
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: holder["client"])
    policy = builtins._AsrPolicy(name="asr", residency="core")

    thread = threading.Thread(target=policy.unload, daemon=True)
    thread.start()

    def _arrive() -> None:
        time.sleep(0.02)
        holder["client"] = restarted
        worker_lifecycle.note_worker_started({"pid": 99, "port": 7102})

    threading.Thread(target=_arrive, daemon=True).start()
    assert policy.load(_bind()[0]) is True
    thread.join(timeout=2.0)
    types = _types(_reset)
    assert types.index("worker_unloaded") < types.index("offline_pack_verified")


def test_respawn_failure_is_actionable(monkeypatch, _reset) -> None:
    _, tray = _bind()
    monkeypatch.setattr(worker_lifecycle, "t", lambda key, **kw: f"[{key}]")
    monkeypatch.setattr(worker_lifecycle, "_RESTART_WAIT_SECONDS", 0.01)
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: FakeClient(port=None))
    worker_lifecycle.note_worker_started({"pid": 1, "port": 7000})
    worker_lifecycle.request_idle_stop()
    assert worker_lifecycle.request_start("idle_reload") is False
    notices = [e for e in _reset if e["type"] == "notification"]
    assert notices and notices[-1]["data"]["critical"] is True
    assert notices[-1]["data"]["click_path"] == "/settings"
    assert tray.safety and tray.states[-1][1] == "[state.worker.restart_failed]"


def test_shutdown_never_publishes_idle_stop(monkeypatch, _reset) -> None:
    app = SimpleNamespace(
        config=SimpleNamespace(model_idle_unload_minutes=1),
        models=FakeModels(),
        tray=FakeTray(),
        _shutting_down=True,
    )
    registry.bind_app(app)
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: FakeClient())
    builtins._AsrPolicy(name="asr", residency="core").unload()
    assert "worker_unloaded" not in _types(_reset)


def test_idle_loop_entry_unloads_asr_policy(monkeypatch, _reset) -> None:
    models, _ = _bind()
    client = FakeClient()
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: client)
    policy = builtins._AsrPolicy(name="asr", residency="core")
    registry.register("asr", policy)
    idle.apply_idle_setting(0.001)  # 0.06 s; real loop, no timer fake
    idle.touch("asr")
    deadline = time.monotonic() + 3.0
    while "worker_unloaded" not in _types(_reset) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert "worker_unloaded" in _types(_reset)
    assert models.engine._loaded is False
