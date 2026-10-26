"""TY-4: level_monitor disconnect detection tests."""

from __future__ import annotations

import threading
import time

import numpy as np
import pytest


def _reset_level_monitor_state() -> None:
    """Delegate: one canonical reset (see tests/fixtures/level_monitor_state.py)."""
    from tests.fixtures.level_monitor_state import reset_level_monitor_state

    reset_level_monitor_state()


@pytest.fixture(autouse=True)
def _reset_level_monitor():
    _reset_level_monitor_state()
    yield
    _reset_level_monitor_state()


def _wire_stream_with_callback_capture(monkeypatch):
    """Wire a mock ``sd.InputStream`` capturing BOTH the audio callback"""
    import sounddevice as sd

    holder = {"callback": None, "finished_callback": None}

    class _Stream:
        def __init__(self, *args, **kwargs):
            holder["callback"] = kwargs.get("callback")
            holder["finished_callback"] = kwargs.get("finished_callback")

        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    sd.InputStream = _Stream  # type: ignore[assignment]
    sd.query_devices.return_value = {
        "name": "Mock Mic",
        "default_samplerate": 16000,
        "max_input_channels": 1,
        "hostapi": 0,
    }
    return holder


def _patch_event_bus_publish(monkeypatch):
    """Patch ``event_bus.publish`` to capture emitted events."""
    captured: list[dict] = []
    lock = threading.Lock()

    def _fake_publish(event: dict) -> bool:
        with lock:
            captured.append(dict(event))
        return True

    import voice_typer.server.event_bus as eb

    monkeypatch.setattr(eb, "publish", _fake_publish)
    return captured


class TestFinishedCallbackWiring:
    """TY-4: ``sd.InputStream`` is constructed with a ``finished_callback``."""

    def test_input_stream_receives_finished_callback(self, monkeypatch):
        """The ``sd.InputStream`` constructor is called with a"""
        import voice_typer.server.level_monitor as lm

        holder = _wire_stream_with_callback_capture(monkeypatch)
        lm.start_monitoring(mic_id=None)

        assert holder["finished_callback"] is not None, (
            "TY-4: sd.InputStream must be constructed with a "
            "finished_callback kwarg so PortAudio can signal device loss"
        )
        assert callable(holder["finished_callback"]), "TY-4: finished_callback must be a callable"

        lm.stop_monitoring()

    def test_finished_callback_sets_monitor_active_false(self, monkeypatch):
        """Invoking the captured finished_callback sets"""
        import voice_typer.server.level_monitor as lm

        holder = _wire_stream_with_callback_capture(monkeypatch)
        _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)
        assert lm._monitor_active is True, "fixture: monitor should be active"

        # Simulate PortAudio firing the finished_callback (device lost).
        holder["finished_callback"]()

        assert lm._monitor_active is False, "TY-4: _level_stream_finished must set _monitor_active=False"

        lm.stop_monitoring()


class TestDeviceLostEventEmitted:
    """Unexpected death retries the open first; ``device_lost`` only when truly gone."""

    def test_finished_callback_recovers_when_reopen_succeeds(self, monkeypatch):
        """The user's OS-effects-toggle scenario: the stream dies but the
        device is still there, so the retry reopens it and NO banner fires."""
        import voice_typer.server.level_monitor as lm
        import voice_typer.server.level_monitor.monitoring as mon

        monkeypatch.setattr(mon, "_STREAM_REOPEN_DELAY_SEC", 0.01)
        holder = _wire_stream_with_callback_capture(monkeypatch)
        captured = _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)

        # Fire the finished_callback (simulates the OS killing the stream).
        holder["finished_callback"]()

        # Wait for the retry to reopen the stream.
        deadline = time.perf_counter() + 5.0
        while time.perf_counter() < deadline:
            if lm._monitor_active:
                break
            time.sleep(0.01)

        assert lm._monitor_active is True, "retry must reopen a still-present device"
        device_lost_events = [e for e in captured if e.get("type") == "device_lost"]
        assert len(device_lost_events) == 0, f"recovered stream must NOT emit device_lost; got {device_lost_events}"

        lm.stop_monitoring()

    def test_finished_callback_emits_device_lost_when_reopen_fails(self, monkeypatch):
        """Exhausted retries (device really gone/unopenable) emit exactly one."""
        import voice_typer.server.level_monitor as lm
        import voice_typer.server.level_monitor.monitoring as mon

        monkeypatch.setattr(mon, "_STREAM_REOPEN_DELAY_SEC", 0.01)
        holder = _wire_stream_with_callback_capture(monkeypatch)
        captured = _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)

        attempts: list[str | None] = []

        def _fail_open(mic_id=None):
            attempts.append(mic_id)
            return {"success": False, "message": "no device"}

        monkeypatch.setattr(mon, "start_monitoring", _fail_open)
        holder["finished_callback"]()

        deadline = time.perf_counter() + 5.0
        while time.perf_counter() < deadline:
            if any(e.get("type") == "device_lost" for e in captured):
                break
            time.sleep(0.01)

        device_lost_events = [e for e in captured if e.get("type") == "device_lost"]
        assert len(device_lost_events) == 1, (
            f"exhausted retry must publish exactly one device_lost event; "
            f"got {len(device_lost_events)} (all events: {captured})"
        )
        evt = device_lost_events[0]
        assert evt["data"]["source"] == "stream_finished", (
            f"source must be 'stream_finished' for the callback path; got {evt['data']['source']!r}"
        )
        assert len(attempts) == mon._STREAM_REOPEN_ATTEMPTS, (
            f"must try the open {mon._STREAM_REOPEN_ATTEMPTS}x before giving up; tried {len(attempts)}x"
        )
        assert lm._monitor_active is False

        lm.stop_monitoring()

    def test_finished_callback_emits_immediately_when_device_gone(self, monkeypatch):
        """A provably-absent device skips the retry loop (fast banner)."""
        import voice_typer.server.level_monitor as lm
        import voice_typer.server.level_monitor.monitoring as mon

        monkeypatch.setattr(mon, "_STREAM_REOPEN_DELAY_SEC", 0.01)
        monkeypatch.setattr(mon, "_monitor_device_present", lambda mic_id: False)
        opened: list[str | None] = []
        monkeypatch.setattr(mon, "start_monitoring", lambda mic_id=None: opened.append(mic_id) or {"success": True})
        holder = _wire_stream_with_callback_capture(monkeypatch)
        captured = _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)

        holder["finished_callback"]()

        deadline = time.perf_counter() + 5.0
        while time.perf_counter() < deadline:
            if any(e.get("type") == "device_lost" for e in captured):
                break
            time.sleep(0.01)

        device_lost_events = [e for e in captured if e.get("type") == "device_lost"]
        assert len(device_lost_events) == 1
        assert opened == [], "gone device must not attempt any reopen"

        lm.stop_monitoring()

    def test_retry_aborts_when_user_stops_meanwhile(self, monkeypatch):
        """A user stop (nav away) during the retry window kills the retry silently."""
        import voice_typer.server.level_monitor as lm
        import voice_typer.server.level_monitor.monitoring as mon

        monkeypatch.setattr(mon, "_STREAM_REOPEN_DELAY_SEC", 0.3)
        opened: list[str | None] = []
        real_open = mon.start_monitoring

        def _counting_open(mic_id=None):
            opened.append(mic_id)
            return real_open(mic_id=mic_id)

        monkeypatch.setattr(mon, "start_monitoring", _counting_open)
        holder = _wire_stream_with_callback_capture(monkeypatch)
        captured = _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)
        n_opens_at_death = len(opened)

        holder["finished_callback"]()
        # User navigates away before the first retry fires.
        lm.stop_monitoring()

        time.sleep(0.8)
        device_lost_events = [e for e in captured if e.get("type") == "device_lost"]
        assert len(device_lost_events) == 0, f"user-stopped retry must stay silent; got {device_lost_events}"
        assert len(opened) == n_opens_at_death, "no reopen attempt may run after a user stop"

    def test_zero_chunk_detector_emits_device_lost_when_reopen_fails(self, monkeypatch):
        """Starved stream + unopenable device → exactly one ``device_lost``."""
        import voice_typer.server.level_monitor as lm
        import voice_typer.server.level_monitor.monitoring as mon

        monkeypatch.setattr(mon, "_STREAM_REOPEN_DELAY_SEC", 0.01)
        holder = _wire_stream_with_callback_capture(monkeypatch)
        captured = _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)

        def _fail_open(mic_id=None):
            return {"success": False, "message": "no device"}

        monkeypatch.setattr(mon, "start_monitoring", _fail_open)

        n = lm._LEVEL_ZERO_CHUNK_DISCONNECT_THRESHOLD
        zero_chunk = np.zeros((512, 1), dtype=np.float32)
        for _ in range(n):
            holder["callback"](zero_chunk, 512, None, None)

        # Wait for the worker thread to drain + the retry to exhaust.
        deadline = time.perf_counter() + 5.0
        while time.perf_counter() < deadline:
            if any(e.get("type") == "device_lost" for e in captured):
                break
            time.sleep(0.01)

        device_lost_events = [e for e in captured if e.get("type") == "device_lost"]
        assert len(device_lost_events) == 1, (
            f"starved stream with failing reopen must publish exactly one device_lost event; got {captured}"
        )
        evt = device_lost_events[0]
        assert evt["data"]["source"] == "zero_chunks", (
            f"source must be 'zero_chunks' for the worker path; got {evt['data']['source']!r}"
        )

        lm.stop_monitoring()

    def test_zero_chunk_recovers_silently_when_reopen_succeeds(self, monkeypatch):
        """Linux-suspend shape: zero-fill trip, device still there → reopen, no banner."""
        import voice_typer.server.level_monitor as lm
        import voice_typer.server.level_monitor.monitoring as mon

        monkeypatch.setattr(mon, "_STREAM_REOPEN_DELAY_SEC", 0.01)
        holder = _wire_stream_with_callback_capture(monkeypatch)
        captured = _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)

        n = lm._LEVEL_ZERO_CHUNK_DISCONNECT_THRESHOLD
        zero_chunk = np.zeros((512, 1), dtype=np.float32)
        for _ in range(n):
            holder["callback"](zero_chunk, 512, None, None)

        deadline = time.perf_counter() + 5.0
        while time.perf_counter() < deadline:
            if lm._monitor_active:
                break
            time.sleep(0.01)

        assert lm._monitor_active is True, "retry must reopen a still-present device"
        device_lost_events = [e for e in captured if e.get("type") == "device_lost"]
        assert len(device_lost_events) == 0, (
            f"recovered starved stream must NOT emit device_lost; got {device_lost_events}"
        )

        lm.stop_monitoring()

    def test_persistent_silence_loop_emits_after_episode_cap(self, monkeypatch):
        """Reopen succeeds but streams keep yielding only silence → banner after the cap."""
        import voice_typer.server.level_monitor as lm
        import voice_typer.server.level_monitor.monitoring as mon

        monkeypatch.setattr(mon, "_STREAM_REOPEN_DELAY_SEC", 0.01)
        holder = _wire_stream_with_callback_capture(monkeypatch)
        captured = _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)

        # Every episode needs a full threshold run of zero chunks (the
        # commit resets the counter, never the episode count). Batches
        # are pushed only while recovered, so none are dropped while
        # parked: push → trip → outcome, serialized per episode.
        zero_chunk = np.zeros((512, 1), dtype=np.float32)
        for _ in range(7):
            deadline = time.perf_counter() + 5.0
            while time.perf_counter() < deadline:
                if lm._monitor_active or any(e.get("type") == "device_lost" for e in captured):
                    break
                time.sleep(0.01)
            if any(e.get("type") == "device_lost" for e in captured):
                break
            for _ in range(lm._LEVEL_ZERO_CHUNK_DISCONNECT_THRESHOLD):
                holder["callback"](zero_chunk, 512, None, None)
            deadline = time.perf_counter() + 5.0
            while time.perf_counter() < deadline:
                if not lm._monitor_active or any(e.get("type") == "device_lost" for e in captured):
                    break
                time.sleep(0.01)
            deadline = time.perf_counter() + 5.0
            while time.perf_counter() < deadline:
                if lm._monitor_active or any(e.get("type") == "device_lost" for e in captured):
                    break
                time.sleep(0.01)
            if any(e.get("type") == "device_lost" for e in captured):
                break

        deadline = time.perf_counter() + 5.0
        while time.perf_counter() < deadline:
            if any(e.get("type") == "device_lost" for e in captured):
                break
            time.sleep(0.01)

        device_lost_events = [e for e in captured if e.get("type") == "device_lost"]
        assert len(device_lost_events) == 1, (
            f"silence loop must emit exactly once after the episode cap; got {captured}"
        )

        lm.stop_monitoring()

    def test_zero_chunk_detector_resets_on_nonzero_chunk(self, monkeypatch):
        """A non-zero chunk in the middle of a zero-run resets the"""
        import voice_typer.server.level_monitor as lm

        holder = _wire_stream_with_callback_capture(monkeypatch)
        captured = _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)

        n = lm._LEVEL_ZERO_CHUNK_DISCONNECT_THRESHOLD
        zero_chunk = np.zeros((512, 1), dtype=np.float32)
        nonzero_chunk = np.ones((512, 1), dtype=np.float32) * 0.1

        # Push (n-1) zero chunks, then a non-zero chunk, then (n-1) more
        for _ in range(n - 1):
            holder["callback"](zero_chunk, 512, None, None)
        holder["callback"](nonzero_chunk, 512, None, None)
        for _ in range(n - 1):
            holder["callback"](zero_chunk, 512, None, None)

        # Wait briefly to let the worker drain.
        time.sleep(0.3)

        device_lost_events = [e for e in captured if e.get("type") == "device_lost"]
        assert len(device_lost_events) == 0, (
            f"TY-4: a non-zero chunk must reset the zero-chunk counter; "
            f"got {len(device_lost_events)} unexpected device_lost events"
        )

        lm.stop_monitoring()


class TestIdempotency:
    """TY-4: ``device_lost`` is emitted ONCE per disconnect episode."""

    def test_finished_callback_idempotent(self, monkeypatch):
        """Calling the finished_callback twice publishes only one"""
        import voice_typer.server.level_monitor as lm
        import voice_typer.server.level_monitor.monitoring as mon

        monkeypatch.setattr(mon, "_STREAM_REOPEN_DELAY_SEC", 0.01)
        holder = _wire_stream_with_callback_capture(monkeypatch)
        captured = _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)

        def _fail_open(mic_id=None):
            return {"success": False, "message": "no device"}

        monkeypatch.setattr(mon, "start_monitoring", _fail_open)
        # Fire the finished_callback twice (PortAudio shouldn't do this,
        holder["finished_callback"]()
        holder["finished_callback"]()

        deadline = time.perf_counter() + 5.0
        while time.perf_counter() < deadline:
            if any(e.get("type") == "device_lost" for e in captured):
                break
            time.sleep(0.01)
        # Let any second retry finish so a double-emit would show.
        time.sleep(0.2)

        device_lost_events = [e for e in captured if e.get("type") == "device_lost"]
        assert len(device_lost_events) == 1, (
            f"finished_callback must be idempotent, second fire is ignored "
            f"while inactive; got {len(device_lost_events)} events"
        )

        lm.stop_monitoring()

    def test_zero_chunk_then_finished_callback_emits_once(self, monkeypatch):
        """A zero-trip emit followed by a finished-callback death stays ONE event."""
        import voice_typer.server.level_monitor as lm
        import voice_typer.server.level_monitor.monitoring as mon

        monkeypatch.setattr(mon, "_STREAM_REOPEN_DELAY_SEC", 0.01)

        def _fail_open(mic_id=None):
            return {"success": False, "message": "no device"}

        monkeypatch.setattr(mon, "start_monitoring", _fail_open)
        holder = _wire_stream_with_callback_capture(monkeypatch)
        captured = _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)

        # Trigger zero-chunk detector first (reopen fails → emit).
        n = lm._LEVEL_ZERO_CHUNK_DISCONNECT_THRESHOLD
        zero_chunk = np.zeros((512, 1), dtype=np.float32)
        for _ in range(n):
            holder["callback"](zero_chunk, 512, None, None)

        # Wait for the zero-chunk emit.
        deadline = time.perf_counter() + 5.0
        while time.perf_counter() < deadline:
            if any(e.get("type") == "device_lost" for e in captured):
                break
            time.sleep(0.01)

        # Now fire the finished_callback (PortAudio tears down the stream).
        holder["finished_callback"]()

        # Wait briefly for any trailing publish.
        time.sleep(0.5)

        device_lost_events = [e for e in captured if e.get("type") == "device_lost"]
        assert len(device_lost_events) == 1, (
            f"zero-chunk + finished_callback must coalesce to ONE "
            f"device_lost event (via _device_lost_emitted); got "
            f"{len(device_lost_events)} events"
        )

        lm.stop_monitoring()

    def test_device_lost_flag_cleared_on_restart(self, monkeypatch):
        """``_device_lost_emitted`` flag is cleared so a fresh disconnect"""
        import voice_typer.server.level_monitor as lm
        import voice_typer.server.level_monitor.monitoring as mon

        monkeypatch.setattr(mon, "_STREAM_REOPEN_DELAY_SEC", 0.01)

        def _fail_open(mic_id=None):
            return {"success": False, "message": "no device"}

        monkeypatch.setattr(mon, "start_monitoring", _fail_open)
        holder = _wire_stream_with_callback_capture(monkeypatch)
        captured = _patch_event_bus_publish(monkeypatch)
        lm.start_monitoring(mic_id=None)

        def _wait_for_count(n: int) -> None:
            deadline = time.perf_counter() + 5.0
            while time.perf_counter() < deadline:
                if sum(1 for e in captured if e.get("type") == "device_lost") >= n:
                    return
                time.sleep(0.01)

        # First disconnect (reopen fails → emit).
        holder["finished_callback"]()
        _wait_for_count(1)
        first_count = sum(1 for e in captured if e.get("type") == "device_lost")
        assert first_count == 1, "fixture: first disconnect should emit once"

        # Stop + restart.
        lm.stop_monitoring()
        holder2 = _wire_stream_with_callback_capture(monkeypatch)
        lm.start_monitoring(mic_id=None)

        assert lm._device_lost_emitted is False, (
            "start_monitoring must clear _device_lost_emitted so a fresh disconnect can emit a new device_lost event"
        )

        # Second disconnect should emit a new event.
        holder2["finished_callback"]()
        _wait_for_count(2)
        second_count = sum(1 for e in captured if e.get("type") == "device_lost")
        assert second_count == 2, (
            f"after restart, a new disconnect must emit a new device_lost event; expected 2 total, got {second_count}"
        )

        lm.stop_monitoring()


class TestConstructorFailure:
    """``sd.InputStream(...)`` itself can raise (no device, PortAudio"""

    def test_constructor_failure_returns_clean_failure(self, monkeypatch):
        """A raising constructor yields ``success=False`` with cleared state."""
        import sounddevice as sd
        import voice_typer.server.level_monitor as lm

        def _raise(*args, **kwargs):
            raise OSError("No input devices available")

        monkeypatch.setattr(sd, "InputStream", _raise)
        monkeypatch.setattr(
            sd,
            "query_devices",
            lambda *args, **kwargs: {"name": "Mock Mic", "default_samplerate": 16000},
        )

        result = lm.start_monitoring(mic_id=None)

        assert result["success"] is False, f"constructor failure must return success=False; got {result}"
        assert "No input devices available" in result["message"]
        assert lm._monitor_active is False
        assert lm._monitor_stream is None
        assert lm._monitor_mic_id is None
