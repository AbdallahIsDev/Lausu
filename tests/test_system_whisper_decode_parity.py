"""SystemWhisperEngine decode parity + hidden-streaming hooks.

The pack-less dev engine used to call ``model.transcribe(samples,
language, beam_size)`` itself, silently ignoring the decode contract the
pack worker obeys (temperature ladder, VAD filter, previous-text
conditioning, batched long-audio path) and exposing no word timestamps,
which disabled hidden streaming entirely. These tests pin both halves of
the parity.
"""

from __future__ import annotations

import sys
import threading
import time
import types
from types import SimpleNamespace

import numpy as np

from tests.fixtures.system_whisper_helpers import decoded, make_system_engine, word


def _speech(seconds: float = 1.0) -> np.ndarray:
    """Non-silent float32 mono audio (the near-silence gate must not fire)."""
    return np.full(int(16000 * seconds), 0.1, dtype=np.float32)


class TestSharedDecodeContract:
    def test_decode_honours_config_knobs(self):
        engine = make_system_engine(device="cpu")
        engine._model.transcribe.return_value = decoded(" hello ")

        assert engine.transcribe_with_fallback(_speech()) == "hello"

        kwargs = engine._model.transcribe.call_args.kwargs
        # Ladder (not a single 0.0): the retry is what breaks repeat loops.
        assert kwargs["temperature"] == (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
        assert kwargs["condition_on_previous_text"] is False
        assert kwargs["without_timestamps"] is True
        assert kwargs["beam_size"] == 5
        assert kwargs["language"] == "en"

    def test_vad_toggle_reaches_the_decoder(self):
        engine = make_system_engine(device="cpu")
        engine.config.vad_filter_enabled = True
        engine._model.transcribe.return_value = decoded("ok")

        engine.transcribe_with_fallback(_speech())

        assert engine._model.transcribe.call_args.kwargs["vad_filter"] is True

    def test_quality_summary_is_written_back(self):
        engine = make_system_engine(device="cpu")
        engine._model.transcribe.return_value = decoded("hello world")

        engine.transcribe_with_fallback(_speech())

        assert engine.last_quality_summary is not None
        assert engine.last_quality_summary["segments"] == 1.0

    def test_decodes_are_serialized_on_the_shared_model(self):
        engine = make_system_engine(device="cpu")
        state = {"now": 0, "peak": 0}
        guard = threading.Lock()

        def _transcribe(audio, **kwargs):
            with guard:
                state["now"] += 1
                state["peak"] = max(state["peak"], state["now"])
            time.sleep(0.05)
            with guard:
                state["now"] -= 1
            return decoded(" hi ")

        engine._model.transcribe.side_effect = _transcribe
        threads = [threading.Thread(target=engine.transcribe_with_fallback, args=(_speech(),)) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert state["peak"] == 1, "concurrent decodes hit one ctranslate2 model"


class TestStreamingHooks:
    def test_capability_is_advertised(self):
        engine = make_system_engine()
        assert callable(engine.transcribe_words)
        assert engine.worker_backed is False

    def test_word_timings_carry_the_global_offset(self):
        engine = make_system_engine(device="cpu")
        engine._model.transcribe.return_value = decoded(
            " hi there",
            words=[word(" hi", 0.1, 0.4), word(" there", 0.5, 0.9)],
        )

        timings = engine.transcribe_words(_speech(), offset_seconds=2.0)

        assert [(t.word, round(t.start_seconds, 2), round(t.end_seconds, 2)) for t in timings] == [
            ("hi", 2.1, 2.4),
            ("there", 2.5, 2.9),
        ]
        kwargs = engine._model.transcribe.call_args.kwargs
        assert kwargs["word_timestamps"] is True
        assert kwargs["without_timestamps"] is False

    def test_abort_token_stops_the_segment_loop(self):
        engine = make_system_engine(device="cpu")
        engine._model.transcribe.return_value = decoded(" hello ")

        engine.request_abort()
        assert engine.transcribe_with_fallback(_speech()) == ""

        engine.clear_abort()
        assert engine.transcribe_with_fallback(_speech()) == "hello"


class TestLoadWiring:
    def test_live_config_reaches_the_engine(self, monkeypatch, tmp_path):
        from voice_typer.server import system_whisper

        weights = tmp_path / "snap"
        weights.mkdir()
        (weights / "model.bin").write_bytes(b"\x00")
        monkeypatch.setitem(sys.modules, "faster_whisper", types.ModuleType("faster_whisper"))
        monkeypatch.setattr(system_whisper, "_resolve_weights_dir", lambda *a, **k: weights)
        monkeypatch.setattr(
            "voice_typer.server.nvidia_dll_paths._configure_nvidia_dll_paths",
            lambda: None,
        )
        captured: dict = {}

        class _Engine:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def load(self) -> bool:
                return True

        monkeypatch.setattr(system_whisper, "SystemWhisperEngine", _Engine)
        cfg = SimpleNamespace(model_size="tiny", device="cpu", language="en", beam_size=1)

        assert system_whisper.try_load_system_whisper(cfg) is not None
        assert captured["config"] is cfg
