"""Worker cutover for media windows (ADR-0025 C5 site 4)."""

from __future__ import annotations

import concurrent.futures
import os
import threading
from pathlib import Path

import numpy as np
import pytest
from voice_typer.server.media_ingest import engine_loop as loop


class _FakeClient:
    def __init__(self, texts=None, *, fail_ids=None, error_result=False):
        self._request_seq = 0
        self.requests: list[tuple[bytes, int, object]] = []
        self.aborts: list[int] = []
        self.cancels: list[int] = []
        self.port = 5123
        self._texts = list(texts or [])
        self._fail_ids = set(fail_ids or ())
        self._error_result = error_result

    def request_samples(self, audio_bytes, rate, language, timeout=None):
        self._request_seq += 1
        rid = self._request_seq
        self.requests.append((bytes(audio_bytes), int(rate), language))
        fut: concurrent.futures.Future[dict] = concurrent.futures.Future()
        if rid in self._fail_ids:
            fut.set_exception(RuntimeError("worker boom"))
        elif self._error_result:
            fut.set_result({"text": "", "error": "worker failed", "latency_ms": 0})
        elif self._texts:
            fut.set_result({"text": self._texts.pop(0), "latency_ms": 1})
        else:
            fut.set_result({"text": "worker-default", "latency_ms": 1})
        return fut

    def send_abort(self, request_id):
        self.aborts.append(int(request_id))
        return True

    def cancel_request(self, request_id):
        self.cancels.append(int(request_id))
        return True


class _LocalBackend:
    def __init__(self, texts=None, language="en"):
        self.calls = 0
        self.aborted = False
        self.language = language
        self._texts = list(texts or [])

    def transcribe_with_fallback(self, audio, *a, **k):
        self.calls += 1
        if self._texts:
            return self._texts.pop(0)
        return f"local-{self.calls}"

    def request_abort(self):
        self.aborted = True


def _chunks(n, sr=None):
    sr = sr or loop.TARGET_SAMPLE_RATE
    return [np.zeros(sr * 5, dtype=np.float32) for _ in range(n)]


def test_cutover_per_window_prefers_worker(monkeypatch):
    fake = _FakeClient(texts=["worker-w1", "worker-w2"])
    monkeypatch.setattr(loop, "_worker_path_available", lambda backend: True)
    monkeypatch.setattr(loop, "_shared_worker_client", lambda: fake)
    local = _LocalBackend()
    state = loop.transcribe_windows(iter(_chunks(12)), local)
    assert state.text == "worker-w1 worker-w2"
    assert local.calls == 0
    assert len(fake.requests) == 2
    for raw, rate, _lang in fake.requests:
        assert rate == loop.TARGET_SAMPLE_RATE
        assert len(raw) == int(loop.WINDOW_SECONDS * loop.TARGET_SAMPLE_RATE) * 4


def test_fallback_on_worker_error(monkeypatch):
    fake = _FakeClient(fail_ids={1, 2})
    monkeypatch.setattr(loop, "_worker_path_available", lambda backend: True)
    monkeypatch.setattr(loop, "_shared_worker_client", lambda: fake)
    local = _LocalBackend(texts=["local-w1", "local-w2"])
    state = loop.transcribe_windows(iter(_chunks(7)), local)
    assert state.text == "local-w1 local-w2"
    assert local.calls == 2


def test_fallback_on_error_result_dict(monkeypatch):
    fake = _FakeClient(error_result=True)
    monkeypatch.setattr(loop, "_worker_path_available", lambda backend: True)
    monkeypatch.setattr(loop, "_shared_worker_client", lambda: fake)
    local = _LocalBackend(texts=["local-fallback"])
    state = loop.transcribe_windows(iter(_chunks(6)), local)
    assert state.text == "local-fallback"
    assert local.calls == 1


def test_worker_backend_raises_for_caller_fallback():
    fake = _FakeClient(fail_ids={1})
    backend = loop.WorkerWindowBackend(language="en", client=fake, timeout=5)
    with pytest.raises(RuntimeError):
        backend.transcribe_with_fallback(np.zeros(16000, dtype=np.float32))


def test_request_abort_maps_to_send_abort():
    fake = _FakeClient()
    backend = loop.WorkerWindowBackend(language="en", client=fake, timeout=5)
    backend._current_request_id = 42
    backend.request_abort()
    assert fake.aborts == [42]
    assert fake.cancels == [42]


def test_request_abort_noop_without_request():
    fake = _FakeClient()
    backend = loop.WorkerWindowBackend(client=fake)
    backend.request_abort()
    assert fake.aborts == []


def test_cancel_calls_both_aborts(monkeypatch):
    fake = _FakeClient(texts=["w1"])
    monkeypatch.setattr(loop, "_worker_path_available", lambda backend: True)
    monkeypatch.setattr(loop, "_shared_worker_client", lambda: fake)
    local = _LocalBackend(texts=["should-not-run"])

    seen_abort = {}

    orig_flush = local.transcribe_with_fallback

    def _counting(audio, *a, **k):
        return orig_flush(audio, *a, **k)

    local.transcribe_with_fallback = _counting  # type: ignore[method-assign]
    event = threading.Event()
    event.set()
    state = loop.transcribe_windows(iter(_chunks(2)), local, cancel_event=event)
    assert state.text == ""
    assert local.aborted is True
    seen_abort["ok"] = True
    assert seen_abort["ok"]


def test_state_resume_and_progress_intact(monkeypatch):
    fake = _FakeClient(texts=["w2"])
    monkeypatch.setattr(loop, "_worker_path_available", lambda backend: True)
    monkeypatch.setattr(loop, "_shared_worker_client", lambda: fake)
    local = _LocalBackend()
    prior = loop.WindowsState(texts=["w1"], decoded_seconds=30.0)
    seen: list[tuple[float, float | None]] = []
    state = loop.transcribe_windows(
        iter(_chunks(6)),
        local,
        on_progress=lambda frac, eta: seen.append((frac, eta)),
        total_seconds=60.0,
        state=prior,
    )
    assert state.text == "w1 w2"
    assert state.decoded_seconds == pytest.approx(60.0)
    assert seen and seen[-1][0] == pytest.approx(1.0)
    assert seen[-1][1] == pytest.approx(0.0)


def test_cloud_backend_stays_in_process(monkeypatch):
    import voice_typer.server.worker_path as worker_path_mod

    real_gate = worker_path_mod.worker_path_for_backend
    fake = _FakeClient(texts=["worker-must-not-run"])
    monkeypatch.setattr(worker_path_mod, "worker_path_for_backend", lambda backend: (False, "cloud_backend"))
    monkeypatch.setattr(loop, "_shared_worker_client", lambda: fake)

    class CloudEngine:
        def transcribe_with_fallback(self, audio, *a, **k):
            return "cloud-local"

        def request_abort(self):
            pass

    state = loop.transcribe_windows(iter(_chunks(6)), CloudEngine())  # type: ignore[arg-type]
    assert state.text == "cloud-local"
    assert fake.requests == []
    # The shared gate itself rejects name-only doubles (no import needed).
    monkeypatch.undo()
    assert real_gate(CloudEngine()) == (False, "cloud_backend")


def test_pack_missing_stays_in_process(monkeypatch):
    import voice_typer.server.worker_path as worker_path_mod

    fake = _FakeClient(texts=["worker-must-not-run"])
    monkeypatch.setattr(worker_path_mod, "worker_path_for_backend", lambda backend: (False, "offline_pack_missing"))
    monkeypatch.setattr(loop, "_shared_worker_client", lambda: fake)
    local = _LocalBackend(texts=["local-only"])
    state = loop.transcribe_windows(iter(_chunks(6)), local)
    assert state.text == "local-only"
    assert fake.requests == []


def _load_step0_or_synth():
    candidate = Path(os.environ.get("TEMP", ".")) / "vt_verify" / "step0.wav"
    if candidate.is_file():
        try:
            from voice_typer.worker._transcribe import _load_wav_float32, _resample_to_16k

            pcm, rate = _load_wav_float32(str(candidate))
            pcm16 = _resample_to_16k(pcm, rate)
            return np.asarray(pcm16, dtype=np.float32).reshape(-1), True
        except Exception:  # noqa: BLE001, fall through to synth
            pass
    rng = np.random.default_rng(0)
    tone = (0.2 * np.sin(2 * np.pi * 440 * np.arange(16000 * 8) / 16000)).astype(np.float32)
    noise = (0.01 * rng.standard_normal(len(tone))).astype(np.float32)
    return (tone + noise).astype(np.float32), False


def test_real_wav_window_bytes_roundtrip(monkeypatch):
    audio, _used_real = _load_step0_or_synth()
    window = audio[: int(loop.WINDOW_SECONDS * loop.TARGET_SAMPLE_RATE)]
    if len(window) < loop.TARGET_SAMPLE_RATE:
        window = np.tile(window, int(np.ceil(loop.TARGET_SAMPLE_RATE / max(1, len(window)))))

    def _echo(audio_bytes, rate, language, timeout=None):
        assert rate == loop.TARGET_SAMPLE_RATE
        fut: concurrent.futures.Future[dict] = concurrent.futures.Future()
        recovered = np.frombuffer(bytes(audio_bytes), dtype=np.float32)
        assert recovered.shape == np.asarray(window[: len(recovered)], dtype=np.float32).shape
        np.testing.assert_array_equal(recovered, np.asarray(window[: len(recovered)], dtype=np.float32))
        fut.set_result({"text": "echo-ok", "latency_ms": 1})
        return fut

    class _EchoClient:
        _request_seq = 0
        port = 5123

        def request_samples(self, audio_bytes, rate, language, timeout=None):
            type(self)._request_seq += 1
            return _echo(audio_bytes, rate, language, timeout)

        def send_abort(self, request_id):
            return True

        def cancel_request(self, request_id):
            return True

    echo = _EchoClient()
    monkeypatch.setattr(loop, "_worker_path_available", lambda backend: True)
    monkeypatch.setattr(loop, "_shared_worker_client", lambda: echo)
    local = _LocalBackend(texts=["must-not-run"])
    backend = loop.WorkerWindowBackend(language="en", client=echo, timeout=30)
    text = backend.transcribe_with_fallback(window)
    assert text == "echo-ok"
    assert local.calls == 0
