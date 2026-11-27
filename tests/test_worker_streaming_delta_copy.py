"""Push path copies only unseen PCM; wire bytes stay identical to full-copy."""

from __future__ import annotations

import base64
import concurrent.futures
import json

import numpy as np
import pytest
from voice_typer.server import worker_streaming

_RATE = 16000
_STEP = int(worker_streaming._PUSH_INTERVAL_SECONDS * _RATE)
_CHUNK = worker_streaming._PUSH_RAW_BYTES


class _CapturingClient:
    def __init__(self) -> None:
        self.frames: list[str] = []

    def enqueue_frames(self, frames) -> bool:
        self.frames.extend(frames)
        return True


class _ScriptedRecorder:
    def __init__(self, snapshots) -> None:
        self._snapshots = list(snapshots)
        self._index = 0
        self.stop_event = None

    def snapshot(self):
        snap = self._snapshots[min(self._index, len(self._snapshots) - 1)]
        self._index += 1
        if self._index >= len(self._snapshots) and self.stop_event is not None:
            self.stop_event.set()
        return snap


class _RaisingAudio:
    def __array__(self, *args, **kwargs):
        raise ValueError("unusable audio")


def _session(recorder, client):
    session = worker_streaming.WorkerStreamingSession(recorder, client, None, _RATE, poll_interval_seconds=0.0)
    session._request_id = 1
    recorder.stop_event = session._stop_event
    return session


def _push_data(frames) -> list[dict]:
    bodies = [json.loads(frame) for frame in frames]
    return [body["data"] for body in bodies if body["cmd"] == "streaming_session_push"]


def _old_push_data_from_snapshots(snapshots) -> list[dict]:
    """Full-snapshot-to-bytes oracle: the algorithm the delta path replaced."""
    sent = 0
    index = 0
    expected = []
    for snapshot in snapshots:
        raw = np.asarray(snapshot, dtype=np.float32).reshape(-1).tobytes()
        total = len(raw) // 4
        if total < sent:
            sent = 0
        if total > sent:
            tail = raw[sent * 4 :]
            for offset in range(0, max(1, len(tail)), _CHUNK):
                piece = tail[offset : offset + _CHUNK]
                expected.append({"index": index, "payload_b64": base64.b64encode(piece).decode("ascii")})
                index += 1
            sent = total
    return expected


def _old_tail_payloads(full_audio, from_samples) -> list[dict]:
    raw = np.asarray(full_audio, dtype=np.float32).reshape(-1).tobytes()[from_samples * 4 :]
    expected = []
    for index, offset in enumerate(range(0, max(1, len(raw)), _CHUNK)):
        piece = raw[offset : offset + _CHUNK] if raw else b""
        if piece:
            expected.append({"index": index, "payload_b64": base64.b64encode(piece).decode("ascii")})
    return expected


class TestDeltaCopyScaling:
    def test_copied_bytes_scale_linearly_with_take_length(self, monkeypatch):
        real = worker_streaming._f32_delta_bytes
        buckets: dict[str, list[int]] = {}
        offsets: dict[str, list[int]] = {}
        active = {"name": "30"}

        def spy(audio, from_samples):
            total, raw = real(audio, from_samples)
            buckets[active["name"]].append(len(raw))
            offsets[active["name"]].append(from_samples)
            return total, raw

        monkeypatch.setattr(worker_streaming, "_f32_delta_bytes", spy)
        totals = {}
        for seconds in (30, 120, 480):
            name = str(seconds)
            active["name"] = name
            buckets[name] = []
            offsets[name] = []
            total_samples = seconds * _RATE
            buf = np.zeros(total_samples, dtype=np.float32)
            snapshots = [buf[:sent] for sent in range(_STEP, total_samples + _STEP, _STEP)]
            session = _session(_ScriptedRecorder(snapshots), _CapturingClient())
            session._drive_pushes()
            totals[name] = total_samples * 4

            assert session._sent_samples == total_samples
            assert len(buckets[name]) == len(snapshots)
            assert sum(buckets[name]) == totals[name]
            assert max(buckets[name]) == _STEP * 4
            assert offsets[name][0] == 0
            assert offsets[name][-1] == total_samples - _STEP

        assert sum(buckets["120"]) == 4 * sum(buckets["30"])
        assert sum(buckets["480"]) == 16 * sum(buckets["30"])
        assert sum(sum(buckets[name]) for name in buckets) == sum(seconds * 4 * _RATE for seconds in (30, 120, 480))
        whole_copy_480 = sum(_STEP * 4 * poll for poll in range(1, 961))
        assert whole_copy_480 / sum(buckets["480"]) > 16

    def test_unchanged_snapshot_copies_nothing(self, monkeypatch):
        real = worker_streaming._f32_delta_bytes
        copied: list[int] = []

        def spy(audio, from_samples):
            total, raw = real(audio, from_samples)
            copied.append(len(raw))
            return total, raw

        monkeypatch.setattr(worker_streaming, "_f32_delta_bytes", spy)
        full = np.arange(_STEP, dtype=np.float32)
        session = _session(_ScriptedRecorder([full, full, full]), _CapturingClient())
        session._drive_pushes()

        assert copied == [full.nbytes, 0, 0]
        assert session._sent_samples == _STEP


class TestWireParity:
    def test_push_frames_match_full_copy_oracle(self):
        growing = np.linspace(-1.0, 1.0, _STEP * 2, dtype=np.float32)
        snapshots = [
            growing[:_STEP],
            growing[:_STEP],
            growing,
            growing[::-1],
            growing[: _STEP // 2],
            np.arange(_CHUNK // 4 + 17, dtype=np.float32) / 3.0,
        ]
        client = _CapturingClient()
        session = _session(_ScriptedRecorder(snapshots), client)
        session._drive_pushes()

        assert _push_data(client.frames) == _old_push_data_from_snapshots(snapshots)
        assert len([f for f in client.frames if "streaming_session_push" in f]) > 1

    @pytest.mark.parametrize("sent", [0, 1000, None, 10**9])
    def test_finalize_tail_matches_full_copy_oracle(self, sent):
        full = np.arange(_CHUNK // 4 + 17, dtype=np.float32) / 9.0
        client = _CapturingClient()
        session = _session(_ScriptedRecorder([full]), client)
        session._sent_samples = full.size if sent is None else sent
        future: concurrent.futures.Future[dict] = concurrent.futures.Future()
        future.set_result({"text": "ok", "error": None})
        session._result_future = future

        assert session.finalize(full) == "ok"
        expected_sent = full.size if sent is None else sent
        assert _push_data(client.frames) == _old_tail_payloads(full, expected_sent)
        assert sum("streaming_session_finalize" in frame for frame in client.frames) == 1


class TestFailureBehaviour:
    def test_unusable_snapshot_does_not_mark_session_failed(self):
        client = _CapturingClient()
        session = _session(_ScriptedRecorder([_RaisingAudio()]), client)
        session._drive_pushes()

        assert session._failed is False
        assert client.frames == []
        assert session._sent_samples == 0

    def test_unusable_finalize_audio_still_returns_worker_text(self):
        client = _CapturingClient()
        session = _session(_ScriptedRecorder([np.zeros(8, dtype=np.float32)]), client)
        future: concurrent.futures.Future[dict] = concurrent.futures.Future()
        future.set_result({"text": "ok", "error": None})
        session._result_future = future

        assert session.finalize(_RaisingAudio()) == "ok"
        assert _push_data(client.frames) == []
        assert sum("streaming_session_finalize" in frame for frame in client.frames) == 1
