"""Worker-death visibility and VEH crash-file tests.

Entry points are the real worker client session end, the lifecycle crash
hook and the real VEH callback. Only sockets, kernel32 calls and the clock
are faked.
"""

from __future__ import annotations

import ctypes
import io
from types import SimpleNamespace
from typing import Any

import pytest
from voice_typer.server import crash_handler as _ch, event_bus, worker_client
from voice_typer.server.crash_handler import _veh_callback
from voice_typer.server.model_lifecycle import registry, worker_lifecycle
from voice_typer.server.tray_types import AppState


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


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> Any:
    worker_lifecycle.reset_for_tests()
    events: list[dict] = []
    monkeypatch.setattr(event_bus, "publish", lambda event: events.append(event) or True)
    app = SimpleNamespace(
        config=SimpleNamespace(model_idle_unload_minutes=1),
        models=SimpleNamespace(),
        tray=FakeTray(),
        _shutting_down=False,
    )
    registry.bind_app(app)
    yield events, app
    worker_lifecycle.reset_for_tests()


def _types(events: list[dict]) -> list[str]:
    return [event["type"] for event in events]


def test_crash_publishes_one_event_and_critical_notice(monkeypatch, _reset) -> None:
    events, app = _reset
    monkeypatch.setattr(worker_lifecycle, "t", lambda key, **kw: f"[{key}]")
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: None)
    worker_lifecycle.note_worker_started({"pid": 3100, "port": 7100})
    worker_lifecycle.note_connection_lost()
    worker_lifecycle.note_connection_lost()
    assert _types(events).count("worker_crashed") == 1
    assert events[0]["data"] == {"pid": 3100, "exit_code": -1}
    notice = [e for e in events if e["type"] == "notification"][0]
    assert notice["data"]["critical"] is True
    assert app.tray.safety and app.tray.states[-1][0] is AppState.ERROR


def test_intentional_stop_is_not_a_crash(monkeypatch, _reset) -> None:
    events, _ = _reset
    fake = SimpleNamespace(port=None, close=lambda: None, abort_all_outstanding=lambda: 0)
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: fake)
    worker_lifecycle.note_worker_started({"pid": 3100, "port": 7100})
    assert worker_lifecycle.request_idle_stop() is True
    worker_lifecycle.note_connection_lost()
    assert "worker_crashed" not in _types(events)
    assert "worker_unloaded" in _types(events)


def test_three_rapid_crashes_publish_persistent_notice(monkeypatch, _reset) -> None:
    events, _ = _reset
    monkeypatch.setattr(worker_lifecycle, "t", lambda key, **kw: f"[{key}]")
    worker_lifecycle.note_worker_started({"pid": 1, "port": 7100})
    for _ in range(3):
        worker_lifecycle.note_connection_lost()
    messages = [e["data"]["message"] for e in events if e["type"] == "notification"]
    assert "[notify.worker.restart_failed]" in messages


def test_worker_started_heals_crash_episode(monkeypatch, _reset) -> None:
    events, _ = _reset
    worker_lifecycle.note_worker_started({"pid": 1, "port": 7100})
    worker_lifecycle.note_connection_lost()
    worker_lifecycle.note_worker_started({"pid": 2, "port": 7101})
    worker_lifecycle.note_connection_lost()
    assert _types(events).count("worker_crashed") == 2
    assert events[-1]["data"]["pid"] == 2


def test_client_session_end_enters_crash_hook(monkeypatch, _reset) -> None:
    events, _ = _reset
    client = worker_client.WorkerClient(publish=lambda event: events.append(event) or True)
    client.set_port(7100)
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: client)
    seen: list[int] = []

    async def _fake_run_session(client_arg: Any, ws: Any, generation: int) -> None:
        seen.append(generation)
        return None

    monkeypatch.setattr(worker_client, "run_session", _fake_run_session)
    import asyncio

    asyncio.run(client._run_session(object(), client._generation))
    assert seen == [client._generation]
    assert "worker_crashed" in _types(events)
    client.close()


def test_crash_aborts_outstanding_requests(monkeypatch, _reset) -> None:
    client = worker_client.WorkerClient()
    client.set_port(7100)
    future = client._register_future(17, None)
    monkeypatch.setattr(worker_lifecycle, "_client", lambda: client)
    worker_lifecycle.note_connection_lost()
    with pytest.raises(worker_client.WorkerAbortedError):
        future.result(timeout=0.1)
    client.close()


def test_aborted_futures_wake_on_worker_stop() -> None:
    client = worker_client.WorkerClient()
    client.set_port(7100)
    future = client._register_future(7, None)
    client.abort_all_outstanding()
    with pytest.raises(worker_client.WorkerAbortedError):
        future.result(timeout=0.1)
    client.close()


class _ExceptionRecord(ctypes.Structure):
    _fields_ = [("ExceptionCode", ctypes.c_uint32), ("ExceptionAddress", ctypes.c_void_p)]


class _ExceptionPointers(ctypes.Structure):
    _fields_ = [("ExceptionRecord", ctypes.POINTER(_ExceptionRecord))]


def test_veh_crash_file_has_fields_after_synthetic_fault(monkeypatch) -> None:
    captured = io.BytesIO()

    def _create(path: Any, *args: Any) -> int:
        return 99  # plain int: the exact shape that broke with ``handle.value``

    def _write(handle: Any, data: Any, length: int, written: Any, overlapped: Any) -> bool:
        address = data.value if hasattr(data, "value") else data
        captured.write(ctypes.string_at(address, length))
        target = getattr(written, "_obj", written)
        target.value = length
        return True

    def _close(handle: Any) -> bool:
        return True

    monkeypatch.setattr(_ch, "_func_create_file_w", _create)
    monkeypatch.setattr(_ch, "_func_write_file", _write)
    monkeypatch.setattr(_ch, "_func_close_handle", _close)
    monkeypatch.setattr(_ch, "_func_get_current_process_id", lambda: 4321)
    monkeypatch.setattr(_ch, "_func_get_current_thread_id", lambda: 5678)

    def _stamp(buf: bytearray, offset: int) -> int:
        value = b"2026-11-28 16:00:00.000"
        buf[offset : offset + len(value)] = value
        return len(value)

    monkeypatch.setattr(_veh_callback, "_write_timestamp", _stamp)
    monkeypatch.setattr(_veh_callback, "_ensure_kernel32", lambda: None)
    monkeypatch.setattr(_ch, "_ensure_kernel32", lambda: None)
    monkeypatch.setattr(_ch, "_crash_file_path", "fake-crash.txt\0")
    monkeypatch.setattr(_ch, "_crash_header_bytes", b"HEADER\r\n")
    monkeypatch.setattr(_ch, "_crash_written", False)
    monkeypatch.setattr(_veh_callback, "_veh_file_handle", None)
    monkeypatch.setattr(_veh_callback, "_veh_template", None)
    monkeypatch.setattr(_veh_callback, "_veh_buffer_addr", None)
    monkeypatch.setattr(_veh_callback, "_prepare_module_table", lambda: None)
    monkeypatch.setattr(_veh_callback, "_veh_modules", [(0x180000000, b"runner.dll")], raising=False)

    assert _veh_callback.prepare_veh_file() is True
    record = _ExceptionRecord(0xC0000005, 0x180001234)
    pointers = _ExceptionPointers(ctypes.pointer(record))
    assert _veh_callback._vectored_handler_impl(ctypes.pointer(pointers)) == 0
    text = captured.getvalue().decode("utf-8", "replace")
    assert "code=0xC0000005" in text
    assert "addr=0x0000000180001234" in text
    assert "pid=0x000010E1" in text
    assert "tid=0x0000162E" in text
    assert "STATUS_ACCESS_VIOLATION" in text
    assert "module=runner.dll" in text
    assert "offset=0x0000000000001234" in text
    assert "app=" in text
    assert "time=20" in text
    assert "\\Users\\" not in text
