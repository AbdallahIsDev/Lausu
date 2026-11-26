"""Warm translator on a genuine user recording start + idle unload.

Fakes stay at the OS/process boundary (recorder, llama-server, loopback POST).
The recording entry is the real ``RecordingLifecycle.start`` path production
uses, entered inside the same user-origin context the hotkey/button/tray
callers set. No network, no real model and no download are used.
"""

from __future__ import annotations

import contextlib
import json
import threading
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from voice_typer.server import dictation_origin, event_bus, model_language_gate, permissions
from voice_typer.server.translation import service as svc

_SOURCE = "النص اللي بعتهولي"


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class _CountingRuntime:
    base_url = "http://127.0.0.1:54321"

    def __init__(self, stops: list[int]) -> None:
        self._stops = stops

    @property
    def running(self) -> bool:
        return True

    def stop(self) -> None:
        self._stops.append(1)


def _wait_for(predicate: Callable[[], bool], *, timeout: float = 5.0) -> None:
    """Bounded positive wait; a miss is a failure, never a negative verdict."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError(f"condition not reached within {timeout:.1f}s")


@pytest.fixture(autouse=True)
def _isolate_translation_globals() -> Any:
    svc.shutdown()
    yield
    warm = svc._warm_thread
    if warm is not None and warm.is_alive():
        warm.join(timeout=5.0)
    svc.shutdown()


def _config(*, enabled: bool = True, warm: bool = True, idle: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        translation_enabled=enabled,
        translation_warm_on_record=warm,
        translation_idle_unload_seconds=idle,
        translation_model="index-translate-2b-q4-k-m",
        translation_model_path="",
        translation_runtime_path="",
        translation_gpu_enabled=True,
        translation_glossary="",
        language="ar",
        model_size="turbo",
        asr_backend="local",
    )


def _patch_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    start_impl: Callable[[], None] | None = None,
    post_impl: Callable[[Any, float], _FakeResponse] | None = None,
    answer: str = "ok",
) -> tuple[list[int], list[int], list[str], list[int]]:
    """Own one fake llama-server process and one fake loopback POST endpoint."""
    starts: list[int] = []
    stops: list[int] = []
    threads: list[str] = []
    calls: list[int] = []

    def _start(*_args: object, **_kwargs: object) -> _CountingRuntime:
        starts.append(1)
        threads.append(threading.current_thread().name)
        if start_impl is not None:
            start_impl()
        return _CountingRuntime(stops)

    def _urlopen(request: Any, timeout: float) -> _FakeResponse:
        calls.append(1)
        if post_impl is not None:
            return post_impl(request, timeout)
        return _FakeResponse({"choices": [{"message": {"content": answer}}]})

    monkeypatch.setattr(svc, "work_dir", lambda: tmp_path)
    monkeypatch.setattr(svc, "resolve_runtime_path", lambda _cfg: tmp_path / "llama-server.exe")
    monkeypatch.setattr(svc, "resolve_model_path", lambda _cfg: tmp_path / "model.gguf")
    monkeypatch.setattr(svc.RuntimeServer, "start", _start)
    monkeypatch.setattr(svc, "urlopen", _urlopen)
    return starts, stops, threads, calls


def _notices(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    published: list[dict[str, Any]] = []
    monkeypatch.setattr(event_bus, "publish", lambda event: published.append(event) or True)
    return published


def _start_recording(
    monkeypatch: pytest.MonkeyPatch,
    config: SimpleNamespace,
    *,
    origin: str | None = "hotkey",
) -> None:
    """Enter through the real RecordingLifecycle.start, with OS/UI edges faked."""
    from voice_typer.server.recording_lifecycle import RecordingLifecycle

    lifecycle = RecordingLifecycle()
    idle_event = threading.Event()
    idle_event.set()
    app = SimpleNamespace(
        config=config,
        _cycle_id="#1",
        _cycle_counter=1,
        _shutting_down_event=threading.Event(),
        _busy_event=idle_event,
        _cancel_pending_timers=lambda: None,
        tray=SimpleNamespace(set_state=lambda *_a, **_kw: None),
        _waveform_bubble=SimpleNamespace(apply_visibility=lambda *_a, **_kw: None),
    )
    app.recorder = SimpleNamespace(recording=False, start=lambda: None)
    app.models = SimpleNamespace(
        active_transcriber=lambda: None,
        _model_load_thread=None,
        apply_pending_model_change=lambda: None,
    )
    controller = SimpleNamespace(
        _app=app,
        _toggle_lock=threading.RLock(),
        _start_worker_thread=None,
        _start_worker_join_timeout=0.0,
    )
    for name in (
        "_publish_instant_start_feedback",
        "_wire_recorder_start_callbacks",
        "_notify_mic_watcher_of_active_device",
        "_claim_keyboard_ownership_for_recording",
        "_rearm_esc_cancel_if_enabled",
        "_spawn_dictation_start_worker",
    ):
        monkeypatch.setattr(lifecycle, name, lambda *_a, **_kw: None)
    monkeypatch.setattr(lifecycle, "_gate_voice_biometric_consent", lambda _app: True)
    monkeypatch.setattr(model_language_gate, "gate_dictation_language", lambda _app: True)
    monkeypatch.setattr(permissions, "verify_microphone_accessible", lambda: None)

    scope = dictation_origin.user_action(origin) if origin else contextlib.nullcontext()
    with scope:
        lifecycle.start(controller)


class TestWarmOnUserRecord:
    def test_no_load_at_app_start_and_no_warm_without_user_origin(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        starts, _stops, threads, _calls = _patch_runtime(monkeypatch, tmp_path)
        config = _config()

        # App start / IPC hydration only constructs the cached service.
        svc.get_service(config)
        assert starts == []

        # A start with no user origin (e.g. a stray background entry) must
        # not warm. The thread is created synchronously, so this is exact.
        _start_recording(monkeypatch, config, origin=None)
        assert svc._warm_thread is None

        # A real hotkey start does.
        _start_recording(monkeypatch, config, origin="hotkey")
        assert svc._warm_thread is not None
        _wait_for(lambda: len(starts) == 1)
        assert threads == ["translation-warm"]

    def test_warm_runs_off_hotkey_thread_and_never_blocks_recording(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        gate = threading.Event()
        starts, _stops, threads, _calls = _patch_runtime(monkeypatch, tmp_path, start_impl=lambda: gate.wait(5.0))
        config = _config()

        _start_recording(monkeypatch, config, origin="hotkey")

        # The caller returned while the warm thread was still blocked in the
        # fake process start: proof the hotkey path did not wait for the load.
        assert not gate.is_set()
        _wait_for(lambda: len(starts) == 1)
        assert not gate.is_set()
        gate.set()
        _wait_for(lambda: not svc._warm_thread.is_alive())
        assert threads == ["translation-warm"]

    def test_second_recording_during_warm_is_coalesced(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        gate = threading.Event()
        starts, _stops, _threads, _calls = _patch_runtime(monkeypatch, tmp_path, start_impl=lambda: gate.wait(5.0))
        config = _config()

        _start_recording(monkeypatch, config, origin="hotkey")
        first = svc._warm_thread
        _start_recording(monkeypatch, config, origin="button")
        assert svc._warm_thread is first

        gate.set()
        _wait_for(lambda: not first.is_alive())
        assert len(starts) == 1

    def test_translate_waits_for_inflight_warm_without_starting_a_second_process(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        gate = threading.Event()
        starts, _stops, _threads, calls = _patch_runtime(monkeypatch, tmp_path, start_impl=lambda: gate.wait(5.0))
        config = _config()

        _start_recording(monkeypatch, config, origin="hotkey")
        result: list[str] = []

        def _translate() -> None:
            result.append(svc.translate_text(_SOURCE, config, "en", "ar"))

        worker = threading.Thread(target=_translate, name="stage-b", daemon=True)
        worker.start()
        _wait_for(lambda: len(starts) == 1)
        # Both workers are still in flight: Stage B is waiting on the warm
        # load, not starting its own llama-server.
        assert worker.is_alive() and calls == []

        gate.set()
        worker.join(timeout=5.0)
        assert not worker.is_alive()
        assert result == ["ok"] and len(starts) == 1 and len(calls) == 1

    def test_warm_failure_keeps_dictation_and_adds_no_notice(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        starts: list[int] = []
        stops: list[int] = []

        def _start(*_args: object, **_kwargs: object) -> _CountingRuntime:
            starts.append(1)
            if len(starts) == 1:
                raise RuntimeError("fake process start failed")
            return _CountingRuntime(stops)

        monkeypatch.setattr(svc, "work_dir", lambda: tmp_path)
        monkeypatch.setattr(svc, "resolve_runtime_path", lambda _cfg: tmp_path / "llama-server.exe")
        monkeypatch.setattr(svc, "resolve_model_path", lambda _cfg: tmp_path / "model.gguf")
        monkeypatch.setattr(svc.RuntimeServer, "start", _start)
        monkeypatch.setattr(
            svc,
            "urlopen",
            lambda _req, timeout=None: _FakeResponse({"choices": [{"message": {"content": "ok"}}]}),
        )
        notices = _notices(monkeypatch)
        caplog.set_level("WARNING", logger=svc.log.name)
        config = _config()

        _start_recording(monkeypatch, config, origin="hotkey")
        warm = svc._warm_thread
        assert warm is not None
        _wait_for(lambda: not warm.is_alive())
        assert "prewarm failed" in caplog.text

        # Stage B still works: the lazy path starts the process on demand.
        assert svc.translate_text(_SOURCE, config, "en", "ar") == "ok"
        assert len(starts) == 2
        assert [e for e in notices if e.get("type") == "notification"] == []

    @pytest.mark.parametrize("origin", ["hotkey", "button", "tray", "dev-driver"])
    def test_every_user_origin_warms(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, origin: str) -> None:
        starts, _stops, _threads, _calls = _patch_runtime(monkeypatch, tmp_path)
        _start_recording(monkeypatch, _config(), origin=origin)
        _wait_for(lambda: len(starts) == 1)


class TestDisabledWarmPaths:
    @pytest.mark.parametrize(
        ("field", "value"),
        [("enabled", False), ("warm", False)],
    )
    def test_disabled_paths_never_load(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, field: str, value: bool
    ) -> None:
        starts, _stops, _threads, _calls = _patch_runtime(monkeypatch, tmp_path)
        config = _config(**{field: value})
        expected = field == "enabled"  # the warm flag refuses before spawning
        with dictation_origin.user_action("hotkey"):
            assert svc.warm_on_user_record(config) is expected
        warm = svc._warm_thread
        if warm is not None:
            _wait_for(lambda: not warm.is_alive())
        assert starts == []

    @pytest.mark.parametrize("backend", ["", "cloud"])
    def test_no_model_state_never_loads(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, backend: str) -> None:
        starts, _stops, _threads, _calls = _patch_runtime(monkeypatch, tmp_path)
        config = _config()
        config.model_size = ""
        config.asr_backend = backend
        with dictation_origin.user_action("hotkey"):
            assert svc.warm_on_user_record(config) is (backend == "cloud")
        if backend == "cloud":
            # Cloud ASR is a valid Stage A engine: warming is still allowed.
            _wait_for(lambda: len(starts) == 1)
        else:
            warm = svc._warm_thread
            if warm is not None:
                _wait_for(lambda: not warm.is_alive())
            assert starts == []

    def test_model_not_installed_never_loads(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        starts, _stops, _threads, _calls = _patch_runtime(monkeypatch, tmp_path)

        def _missing(_cfg: Any) -> Path:
            raise svc.TranslationError("not installed")

        monkeypatch.setattr(svc, "resolve_model_path", _missing)
        config = _config()
        _start_recording(monkeypatch, config, origin="hotkey")
        _wait_for(lambda: not svc._warm_thread.is_alive())
        assert starts == []


class TestIdleUnload:
    def test_idle_unload_then_next_recording_rewarms(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        starts, stops, _threads, _calls = _patch_runtime(monkeypatch, tmp_path)
        config = _config(idle=1)

        _start_recording(monkeypatch, config, origin="hotkey")
        _wait_for(lambda: len(starts) == 1)
        _wait_for(lambda: len(stops) == 1, timeout=8.0)

        # Next genuine start re-warms; the same cached service is reused.
        _start_recording(monkeypatch, config, origin="button")
        _wait_for(lambda: len(starts) == 2)
        assert len(stops) == 1

    def test_no_unload_during_inflight_request(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        entered = threading.Event()
        release = threading.Event()

        def _post(_request: Any, _timeout: float) -> _FakeResponse:
            entered.set()
            release.wait(5.0)
            return _FakeResponse({"choices": [{"message": {"content": "ok"}}]})

        starts, stops, _threads, calls = _patch_runtime(monkeypatch, tmp_path, post_impl=_post)
        config = _config(idle=2)
        _start_recording(monkeypatch, config, origin="hotkey")
        _wait_for(lambda: len(starts) == 1)

        result: list[str] = []

        def _translate() -> None:
            result.append(svc.translate_text(_SOURCE, config, "en", "ar"))

        worker = threading.Thread(target=_translate, name="stage-b", daemon=True)
        worker.start()
        assert entered.wait(5.0)
        # Let the idle deadline pass while the POST is still in flight. The
        # negative verdict is the in-flight worker, not the elapsed time.
        time.sleep(3.0)
        assert worker.is_alive() and stops == []

        release.set()
        worker.join(timeout=5.0)
        assert not worker.is_alive() and result == ["ok"]
        # A successful POST restarted the countdown; no immediate unload.
        assert stops == [] and calls == [1]


class TestConfigContract:
    def test_defaults_are_migration_safe(self) -> None:
        from voice_typer.server.config import Config

        config = Config()
        assert config.translation_warm_on_record is True
        assert config.translation_idle_unload_seconds == 600

        # An older config.json simply omits the keys; defaults apply.
        data = asdict(config)
        data.pop("translation_warm_on_record")
        data.pop("translation_idle_unload_seconds")
        older = Config(**data)
        assert older.translation_warm_on_record is True
        assert older.translation_idle_unload_seconds == 600

    def test_allowlist_validators(self) -> None:
        from voice_typer.server.config_validators import IPC_CONFIG_ALLOWLIST

        bool_type, bool_validator = IPC_CONFIG_ALLOWLIST["translation_warm_on_record"]
        assert bool_type is bool
        assert bool_validator(True) is None
        assert bool_validator(False) is None
        assert bool_validator("yes") is not None

        int_type, int_validator = IPC_CONFIG_ALLOWLIST["translation_idle_unload_seconds"]
        assert int_type is int
        assert int_validator(0) is None
        assert int_validator(600) is None
        assert int_validator(-1) is not None
        assert int_validator(90_000) is not None
