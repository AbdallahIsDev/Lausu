"""Unified model lifecycle: registration, start, startup, idle, wait, shutdown.

Fakes sit only at OS/process boundaries (physical-memory read, clock scaling,
simulated runtime process). The policy extension API is exercised for real.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from voice_typer.server import dictation_gate, dictation_origin, model_lifecycle as ml
from voice_typer.server.model_lifecycle import (
    CallablePolicy,
    idle,
    loading,
    memory,
    registry,
)
from voice_typer.server.shutdown.cleanup import do_cleanup, do_fast_cleanup

from tests.fixtures.shutdown_helpers import make_quiet_cleanup_controller

_GIB = 1024 * 1024 * 1024


@pytest.fixture(autouse=True)
def isolated_lifecycle(monkeypatch: pytest.MonkeyPatch) -> Any:
    # Snapshot other modules' registrations (builtins + translation) so this
    # suite's isolation never leaks an empty registry into a later test.
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


def _fake(
    name: str,
    *,
    residency: str = "optional",
    estimate: int = 0,
    dedicated_startup: bool = False,
    applicable: bool = True,
    loaded: bool = False,
    busy: bool = False,
    load_ok: bool = True,
    on_load: Any = None,
    on_unload: Any = None,
) -> CallablePolicy:
    state = {"loaded": loaded, "busy": busy, "calls": 0}

    def _load(_config: Any) -> bool:
        state["calls"] += 1
        if on_load is not None:
            on_load(state)
        state["loaded"] = load_ok
        return load_ok

    def _unload() -> None:
        state["loaded"] = False
        if on_unload is not None:
            on_unload(state)

    policy = CallablePolicy(
        name=name,
        residency=residency,
        estimate_private_bytes=estimate,
        dedicated_startup=dedicated_startup,
        applicable_fn=lambda _config: applicable,
        is_loaded_fn=lambda _config: state["loaded"],
        is_busy_fn=lambda: state["busy"],
        load_fn=_load,
        unload_fn=_unload,
        wait_fn=lambda _timeout: state["loaded"],
    )
    policy.state = state  # type: ignore[attr-defined]
    return policy


def _app(**config: Any) -> SimpleNamespace:
    return SimpleNamespace(config=SimpleNamespace(model_idle_unload_minutes=0, **config))


def _wait(event: threading.Event, timeout: float = 3.0) -> None:
    assert event.wait(timeout), "lifecycle worker did not reach the expected state"


class TestRegistry:
    def test_new_kind_registers_with_a_few_lines(self) -> None:
        ml.register("fake", CallablePolicy("fake"))
        assert ml.get("fake") is not None
        assert ml.get("missing") is None
        assert ml.kinds() == ("fake",)

    def test_need_order_core_first_then_translation_then_tts_last(self) -> None:
        ml.register("tts", _fake("tts"))
        ml.register("misc", _fake("misc"))
        ml.register("translation", _fake("translation"))
        ml.register("asr", _fake("asr", residency="core"))
        assert registry.ordered_kinds() == ("asr", "translation", "misc", "tts")


class TestStartupPrewarm:
    def test_new_kind_gets_startup_preload_when_fast_startup_and_memory_fit(self) -> None:
        done = threading.Event()
        policy = _fake("fake", on_load=lambda _state: done.set())
        ml.register("fake", policy)
        app = _app(fast_startup=True)

        ml.prewarm_optional_at_startup(app)
        _wait(done)
        assert policy.state["calls"] == 1  # type: ignore[attr-defined]

    def test_fast_startup_off_skips_every_optional_kind(self) -> None:
        done = threading.Event()
        ml.register("fake", _fake("fake", on_load=lambda _state: done.set()))
        ml.prewarm_optional_at_startup(_app(fast_startup=False))
        assert not done.wait(0.15)

    def test_guard_cannot_read_memory_skips_with_one_log_line(self, caplog: pytest.LogCaptureFixture) -> None:
        seen = threading.Event()

        def _unreadable() -> int | None:
            seen.set()
            return None

        with patch.object(memory, "available_physical_bytes", _unreadable):
            caplog.set_level("INFO", logger="voice_typer.server.model_lifecycle.startup")
            done = threading.Event()
            policy = _fake("fake", on_load=lambda _state: done.set())
            ml.register("fake", policy)
            ml.prewarm_optional_at_startup(_app(fast_startup=True))
            _wait(seen)
            assert policy.state["calls"] == 0  # type: ignore[attr-defined]
            assert sum("startup preload skipped" in r.getMessage() for r in caplog.records) == 1

    def test_insufficient_physical_memory_skips(self) -> None:
        seen = threading.Event()
        policy = _fake("fake", estimate=7 * _GIB)
        ml.register("fake", policy)

        def _low() -> int:
            seen.set()
            return 2 * _GIB

        with patch.object(memory, "available_physical_bytes", _low):
            ml.prewarm_optional_at_startup(_app(fast_startup=True))
            _wait(seen)
            assert policy.state["calls"] == 0  # type: ignore[attr-defined]

    def test_memory_guard_uses_private_estimate_plus_headroom(self) -> None:
        small = _fake("small", estimate=100)
        large = _fake("large", estimate=memory.HEADROOM_BYTES)
        with patch.object(memory, "available_physical_bytes", lambda: memory.HEADROOM_BYTES + 200):
            assert memory.memory_fits(small) is True
            assert memory.memory_fits(large) is False
        with patch.object(memory, "available_physical_bytes", lambda: None):
            assert memory.memory_fits(small) is False


class TestRecordStart:
    def test_decide_toggle_loads_kinds_in_need_order(self) -> None:
        order: list[str] = []
        done = threading.Event()

        def _record(name: str) -> Any:
            def _on_load(_state: Any) -> None:
                order.append(name)
                if name == "tts":
                    done.set()

            return _on_load

        ml.register("tts", _fake("tts", on_load=_record("tts")))
        ml.register("translation", _fake("translation", on_load=_record("translation")))
        ml.register("asr", _fake("asr", residency="core", on_load=_record("asr")))
        app = _app()

        with dictation_origin.user_action("hotkey"):
            assert dictation_gate.decide_toggle(app) == "start"
        _wait(done)
        assert order == ["asr", "translation", "tts"]

    def test_no_user_origin_is_a_noop_and_never_mints_one(self) -> None:
        done = threading.Event()
        ml.register("fake", _fake("fake", on_load=lambda _state: done.set()))
        with patch.object(ml, "on_dictation_start", side_effect=ml.on_dictation_start) as hook:
            assert dictation_gate.decide_toggle(_app()) == "start"
            hook.assert_called_once()
        assert dictation_origin.current() == ""
        assert not done.wait(0.15)

    def test_start_hook_never_breaks_dictation(self) -> None:
        with patch.object(ml, "on_dictation_start", side_effect=RuntimeError("boom")):
            assert dictation_gate.decide_toggle(_app()) == "start"

    def test_ignore_action_does_not_call_the_hook(self) -> None:
        with patch.object(ml, "on_dictation_start") as hook:
            gate = dictation_gate.DictationGate(clock=SimpleNamespace(monotonic=lambda: 100.0))
            app = _app()
            app._dictation_gate = gate
            app.tray = SimpleNamespace(_state=SimpleNamespace(value="recording"), _recording_started_at=90.0)
            assert dictation_gate.decide_toggle(app) == "stop"
            hook.assert_not_called()

    def test_single_flight_per_kind(self) -> None:
        started = threading.Event()
        release = threading.Event()
        state: dict[str, int] = {"calls": 0}

        def _load(_config: Any) -> bool:
            state["calls"] += 1
            started.set()
            release.wait(3.0)
            return True

        policy = CallablePolicy("fake", load_fn=_load, is_loaded_fn=lambda _c: False)
        ml.register("fake", policy)
        results: list[bool] = []
        threads = [
            threading.Thread(target=lambda: results.append(loading.load_one(policy, object()))) for _ in range(2)
        ]
        for thread in threads:
            thread.start()
        _wait(started)
        release.set()
        for thread in threads:
            thread.join(timeout=3.0)
        assert state["calls"] == 1
        assert sorted(results) == [False, True]


class TestSharedWait:
    def test_ensure_loaded_waits_for_inflight_load_without_second_loader(self) -> None:
        started = threading.Event()
        release = threading.Event()
        state: dict[str, int] = {"calls": 0}

        def _load(_config: Any) -> bool:
            state["calls"] += 1
            started.set()
            release.wait(3.0)
            return True

        policy = CallablePolicy(
            "fake",
            load_fn=_load,
            is_loaded_fn=lambda _c: state["calls"] > 0 and release.is_set(),
        )
        ml.register("fake", policy)
        config = object()
        worker = threading.Thread(target=lambda: loading.load_one(policy, config))
        worker.start()
        _wait(started)
        result: list[bool] = []
        waiter = threading.Thread(target=lambda: result.append(ml.ensure_loaded("fake", config, 2.0)))
        waiter.start()
        release.set()
        waiter.join(timeout=3.0)
        worker.join(timeout=3.0)
        assert result == [True]
        assert state["calls"] == 1

    def test_ensure_loaded_times_out_once(self) -> None:
        policy = CallablePolicy("fake", wait_fn=lambda _t: False, is_loaded_fn=lambda _c: False)
        ml.register("fake", policy)
        assert ml.ensure_loaded("fake", object(), 0.01) is False
        assert ml.ensure_loaded("missing", object(), 0.01) is False


class TestBackgroundLoad:
    def test_load_in_background_is_single_flight_and_non_blocking(self) -> None:
        started = threading.Event()
        returned = threading.Event()
        release = threading.Event()
        state: dict[str, int] = {"calls": 0}

        def _load(_config: Any) -> bool:
            state["calls"] += 1
            started.set()
            release.wait(3.0)
            return True

        ml.register("fake", CallablePolicy("fake", load_fn=_load, is_loaded_fn=lambda _c: False))
        config = object()
        results: list[bool] = []

        def _call() -> None:
            results.append(ml.load_in_background("fake", config))
            returned.set()

        caller = threading.Thread(target=_call)
        caller.start()
        _wait(started)
        # The caller returned while the load was still blocked.
        assert returned.wait(3.0)
        assert results == [True]
        assert ml.load_in_background("fake", config) is False
        assert state["calls"] == 1
        release.set()
        caller.join(timeout=3.0)
        loaders = list(loading._threads)
        loading.join_loaders(timeout_s=3.0)
        assert loaders
        assert not any(thread.is_alive() for thread in loaders)

    def test_load_in_background_missing_kind_is_false(self) -> None:
        assert ml.load_in_background("missing", object()) is False


class TestIdle:
    def test_each_kind_has_its_own_clock(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(idle, "_SECONDS_PER_MINUTE", 0.01)
        done = {"a": threading.Event(), "b": threading.Event()}
        ml.register("a", _fake("a", on_unload=lambda _s: done["a"].set()))
        ml.register("b", _fake("b", on_unload=lambda _s: done["b"].set()))
        ml.apply_idle_setting(1)
        idle.touch("a")
        _wait(done["a"])
        assert not done["b"].is_set()
        idle.touch("b")
        _wait(done["b"])

    def test_always_never_unloads(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(idle, "_SECONDS_PER_MINUTE", 0.01)
        unloaded = threading.Event()
        ml.register("fake", _fake("fake", on_unload=lambda _s: unloaded.set()))
        ml.apply_idle_setting(0)
        idle.touch("fake")
        assert not unloaded.wait(0.1)

    def test_busy_kind_is_retried_not_unloaded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(idle, "_SECONDS_PER_MINUTE", 0.01)
        unloaded = threading.Event()
        policy = _fake("fake", busy=True, on_unload=lambda _s: unloaded.set())
        ml.register("fake", policy)
        ml.apply_idle_setting(1)
        idle.touch("fake")
        time.sleep(0.08)
        assert not unloaded.is_set()
        policy.state["busy"] = False  # type: ignore[attr-defined]
        idle.touch("fake")
        _wait(unloaded)

    def test_non_numeric_setting_fails_closed(self) -> None:
        from unittest.mock import MagicMock

        ml.apply_idle_setting(MagicMock())
        with idle._lock:
            assert idle._minutes == 0.0
            assert idle._deadlines == {}

    def test_dedicated_startup_kind_is_not_prewarmed_twice(self) -> None:
        done = threading.Event()
        policy = _fake("fake", dedicated_startup=True, on_load=lambda _state: done.set())
        ml.register("fake", policy)
        ml.prewarm_optional_at_startup(_app(fast_startup=True))
        assert not done.wait(0.15)

    def test_runtime_setting_change_applies_immediately(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(idle, "_SECONDS_PER_MINUTE", 0.01)
        unloaded = threading.Event()
        ml.register("fake", _fake("fake", on_unload=lambda _s: unloaded.set()))
        ml.apply_idle_setting(1)
        idle.touch("fake")
        ml.apply_idle_setting(0)
        with idle._lock:
            assert idle._deadlines == {}
        assert not unloaded.wait(0.1)

    def test_config_side_effect_handler_is_registered(self) -> None:
        from voice_typer.server.config_applier import ConfigApplier
        from voice_typer.server.config_applier_handlers import _ModelIdleHandler

        applier = ConfigApplier(SimpleNamespace(_app=SimpleNamespace()))
        assert any(isinstance(h, _ModelIdleHandler) for h in applier._side_effect_handlers)


class TestRealShutdownPath:
    def test_do_cleanup_terminates_inflight_load_and_leaves_no_loader(self) -> None:
        started = threading.Event()
        release = threading.Event()
        process: dict[str, bool] = {"alive": False}

        def _load(_config: Any) -> bool:
            process["alive"] = True
            started.set()
            while not release.wait(0.01):
                if loading.is_cancelled():
                    process["alive"] = False
                    return False
            process["alive"] = False
            return True

        ml.register(
            "fake",
            CallablePolicy(
                "fake",
                load_fn=_load,
                unload_fn=lambda: process.__setitem__("alive", False),
                is_loaded_fn=lambda _c: False,
            ),
        )
        loader = threading.Thread(target=lambda: loading.load_one(ml.get("fake"), object()))
        loader.start()
        _wait(started)
        assert process["alive"] is True

        app = SimpleNamespace(_cleanup_done=False, _cycle_id="", _ipc_server=None)
        do_cleanup(make_quiet_cleanup_controller(app))

        assert process["alive"] is False
        release.set()
        loader.join(timeout=3.0)
        assert not loader.is_alive()

    def test_fast_cleanup_also_stops_registered_runtimes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from voice_typer.server import backend_pid, session_state
        from voice_typer.server.shutdown import cleanup as cleanup_mod

        monkeypatch.setattr(cleanup_mod.os, "_exit", lambda code=0: None)
        monkeypatch.setattr(session_state, "clear_session_marker", lambda _path: None)
        monkeypatch.setattr(backend_pid, "_clear_backend_pid_file", lambda: None)
        unloaded = threading.Event()
        ml.register("fake", _fake("fake", on_unload=lambda _s: unloaded.set()))
        app = SimpleNamespace(_cleanup_done=False, _quit_lock=threading.Lock())
        controller = make_quiet_cleanup_controller(app)

        do_fast_cleanup(controller)
        assert unloaded.is_set()


class TestShutdown:
    def test_shutdown_during_load_cancels_and_leaves_no_process(self) -> None:
        started = threading.Event()
        release = threading.Event()
        process: dict[str, bool] = {"alive": False}
        state: dict[str, Any] = {"unloaded": False}

        def _load(_config: Any) -> bool:
            process["alive"] = True
            started.set()
            while not release.wait(0.01):
                if loading.is_cancelled():
                    process["alive"] = False
                    return False
            process["alive"] = False
            return True

        def _unload() -> None:
            process["alive"] = False
            state["unloaded"] = True

        ml.register("fake", CallablePolicy("fake", load_fn=_load, unload_fn=_unload, is_loaded_fn=lambda _c: False))
        worker = threading.Thread(target=lambda: loading.load_one(ml.get("fake"), object()))
        worker.start()
        _wait(started)
        assert process["alive"] is True
        ml.shutdown_all()
        release.set()
        worker.join(timeout=3.0)
        assert not worker.is_alive()
        assert process["alive"] is False
        assert state["unloaded"] is True
