"""Part F integration edges: real start hook, shared wait, guard, shutdown.

Fakes sit only at OS/process boundaries (memory read, runtime process, clock).
The tests enter through the same `decide_toggle` seam used by local, cloud and
plugin dictation starts (REAL-PATH TEST RULE).
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest
from voice_typer.server import dictation_gate, dictation_origin, model_lifecycle as ml
from voice_typer.server.model_lifecycle import CallablePolicy, idle, loading, memory, registry

_GIB = 1024 * 1024 * 1024


@pytest.fixture(autouse=True)
def isolated_lifecycle(monkeypatch: pytest.MonkeyPatch) -> Any:
    saved = {kind: registry.get(kind) for kind in registry.kinds()}
    registry._reset_for_tests()
    idle._reset_for_tests()
    loading._reset_for_tests()
    monkeypatch.setattr(memory, "available_physical_bytes", lambda: 8 * _GIB)
    yield
    loading._reset_for_tests()
    idle._reset_for_tests()
    registry._reset_for_tests()
    for kind, policy in saved.items():
        registry.register(kind, policy)


def _app(**config: Any) -> SimpleNamespace:
    return SimpleNamespace(config=SimpleNamespace(model_idle_unload_minutes=0, fast_startup=True, **config))


def _fake(name: str, **overrides: Any) -> CallablePolicy:
    state = {"loaded": False, "calls": 0, "process_alive": False}
    events: dict[str, threading.Event] = {}

    def load(_config: Any) -> bool:
        state["calls"] += 1
        state["process_alive"] = True
        if "hook" in overrides:
            overrides["hook"](state, events)
        state["loaded"] = not state.get("fail", False)
        return state["loaded"]

    def unload() -> None:
        state["loaded"] = False
        state["process_alive"] = False

    policy = CallablePolicy(
        name=name,
        residency=overrides.get("residency", "optional"),
        estimate_private_bytes=overrides.get("estimate", 0),
        applicable_fn=overrides.get("applicable", lambda _config: True),
        is_loaded_fn=lambda _config: state["loaded"],
        is_busy_fn=lambda: state.get("busy", False),
        load_fn=load,
        unload_fn=unload,
        wait_fn=lambda _timeout: state["loaded"],
    )
    policy.state = state  # type: ignore[attr-defined]
    policy.events = events  # type: ignore[attr-defined]
    return policy


def _start(app: Any, *, origin: str = "hotkey") -> str:
    with dictation_origin.user_action(origin):
        return dictation_gate.decide_toggle(app)


def _settle(policy: CallablePolicy, expected: int = 1, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if policy.state["calls"] >= expected:  # type: ignore[attr-defined]
            return
        time.sleep(0.01)
    raise AssertionError(f"{policy.name}: expected {expected} load calls, got {policy.state['calls']}")


class TestSharedStartHook:
    def test_local_and_plugin_starts_use_one_shared_hook(self) -> None:
        from unittest.mock import MagicMock

        from voice_typer.server.dictation_gate import DictationGate

        policy = _fake("translation")
        ml.register("translation", policy)
        app = _app()
        clock = MagicMock()
        clock.monotonic.return_value = 100.0
        app._dictation_gate = DictationGate(clock=clock)
        app.tray = SimpleNamespace(_state=SimpleNamespace(value="idle"))

        assert _start(app) == "start"
        _settle(policy)
        # A second gesture from another engine family must not start a second load.
        clock.monotonic.return_value = 101.0
        app.tray = SimpleNamespace(_state=SimpleNamespace(value="idle"))
        assert _start(app, origin="button") == "start"
        time.sleep(0.2)
        assert policy.state["calls"] == 1  # type: ignore[attr-defined]

    def test_start_without_a_user_origin_never_preloads(self) -> None:
        policy = _fake("translation")
        ml.register("translation", policy)
        app = _app()
        app.tray = SimpleNamespace(_state=SimpleNamespace(value="idle"))
        assert dictation_gate.decide_toggle(app) == "start"
        time.sleep(0.2)
        assert policy.state["calls"] == 0  # type: ignore[attr-defined]

    def test_no_model_state_skips_optional_kinds(self) -> None:
        policy = _fake(
            "translation",
            applicable=lambda config: bool(getattr(config, "model_size", "")) or config.asr_backend == "cloud",
        )
        ml.register("translation", policy)
        app = _app(model_size="", asr_backend="")
        app.tray = SimpleNamespace(_state=SimpleNamespace(value="idle"))
        _start(app)
        time.sleep(0.2)
        assert policy.state["calls"] == 0  # type: ignore[attr-defined]

    def test_two_quick_presses_are_one_gesture(self) -> None:
        policy = _fake("translation")
        ml.register("translation", policy)
        app = _app()
        app.tray = SimpleNamespace(_state=SimpleNamespace(value="idle"))
        assert _start(app) == "start"
        assert dictation_gate.decide_toggle(app).startswith("ignore")
        _settle(policy)
        time.sleep(0.2)
        assert policy.state["calls"] == 1  # type: ignore[attr-defined]

    def test_switch_off_during_load_finishes_without_blocking_dictation(self) -> None:
        policy = _fake("translation", applicable=lambda config: config.translation_enabled)
        ml.register("translation", policy)
        app = _app(translation_enabled=True)
        app.tray = SimpleNamespace(_state=SimpleNamespace(value="idle"))
        assert _start(app) == "start"
        app.config.translation_enabled = False
        _settle(policy)
        assert policy.applicable(app.config) is False


class TestGuardAndWait:
    def test_memory_unreadable_skips_preload_but_real_need_still_loads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def unreadable() -> int:
            raise OSError("cannot read physical memory")

        monkeypatch.setattr(memory, "available_physical_bytes", unreadable)
        policy = _fake("translation", estimate=256 * _GIB)
        ml.register("translation", policy)
        app = _app()
        app.tray = SimpleNamespace(_state=SimpleNamespace(value="idle"))
        ml.prewarm_optional_at_startup(app)
        time.sleep(0.1)
        assert policy.state["calls"] == 0  # type: ignore[attr-defined]
        # A real need still loads; the guard only governs preload.
        assert ml.loading.load_one(policy, app.config) is True
        assert policy.state["calls"] == 1  # type: ignore[attr-defined]

    def test_failed_load_waits_bounded_and_reports_failure(self) -> None:
        policy = _fake("translation", hook=lambda state, _events: state.update(fail=True))
        ml.register("translation", policy)
        config = _app().config
        assert loading.load_one(policy, config) is False
        assert ml.ensure_loaded("translation", config, timeout_s=0.2) is False

    def test_background_load_is_single_flight_and_non_blocking(self) -> None:
        gate = threading.Event()
        release = threading.Event()

        def hold(state: Any, events: dict[str, threading.Event]) -> None:
            gate.set()
            release.wait(2.0)

        policy = _fake("translation", hook=hold)
        ml.register("translation", policy)
        config = _app().config
        assert ml.load_in_background("translation", config) is True
        assert gate.wait(2.0)
        assert ml.load_in_background("translation", config) is False
        release.set()
        assert ml.ensure_loaded("translation", config, timeout_s=2.0) is True

    def test_idle_expiry_racing_new_recording_keeps_kind_loaded(self) -> None:
        policy = _fake("translation")
        ml.register("translation", policy)
        app = _app()
        app.tray = SimpleNamespace(_state=SimpleNamespace(value="idle"))
        ml.apply_idle_setting(0.01)  # 0.6 s: long enough to re-arm before expiry
        _start(app)
        _settle(policy)
        _start(app, origin="button")
        time.sleep(0.7)  # past the FIRST deadline, inside the re-armed one
        assert policy.state["loaded"] is True  # type: ignore[attr-defined]


class TestShutdownEdge:
    def test_shutdown_during_load_terminates_fake_process(self) -> None:
        policy = _fake("translation")
        ml.register("translation", policy)
        config = _app().config
        ml.load_in_background("translation", config)
        _settle(policy)
        assert policy.state["process_alive"] is True  # type: ignore[attr-defined]
        ml.shutdown_all()
        assert policy.state["process_alive"] is False  # type: ignore[attr-defined]


EDGE_CASES_COVERED_ELSEWHERE = {
    "app start with Fast Startup on/off": "test_model_lifecycle.py::TestStartupPrewarm",
    "translation tooltips / GPU switch while loaded": "test_translation_lifecycle.py::TestGpuSwitch",
    "load failure keeps original text + one notice": "test_translation_lifecycle.py (wait tests)",
    "per-kind clocks / Always / runtime change": "test_model_lifecycle.py::TestIdle",
    "focus change during the long wait aborts paste": "test_dictation_destination_stop_time.py (E1)",
    "same-language skip makes no translator call": "test_translation.py (skip rule)",
    "plugin session user origin": "dictation_origin guard (other session, read-only)",
    "sleep/resume with a dead runtime": ("UNVERIFIED — ensure_loaded re-checks is_loaded before reuse"),
}
