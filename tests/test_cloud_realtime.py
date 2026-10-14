"""Pure unit tests for the realtime helpers and the batch-POST guard."""

from __future__ import annotations

import base64

import numpy as np
import pytest
from voice_typer.server.asr_errors import CloudConfigError, CloudEngineError
from voice_typer.server.cloud._realtime import (
    REALTIME_MODELS,
    WS_REALTIME_MODELS,
    DeltaAssembler,
    assert_official_realtime_host,
    build_append_envelope,
    build_commit_envelope,
    build_session_update,
    ensure_not_realtime,
    float32_to_pcm16,
    frame_200ms,
    is_realtime_model,
    is_ws_realtime_model,
    resample_16k_to_24k,
)


class TestMembership:
    def test_set_holds_the_three_pairs(self):
        assert len(REALTIME_MODELS) == 3
        assert ("openai", "gpt-live-transcribe") in REALTIME_MODELS
        assert ("openai", "gpt-realtime-whisper") in REALTIME_MODELS
        assert ("gemini", "gemini-3.5-transcribe-live") in REALTIME_MODELS

    @pytest.mark.parametrize(
        "provider,model",
        [
            ("openai", "gpt-live-transcribe"),
            ("openai", "gpt-realtime-whisper"),
            ("gemini", "gemini-3.5-transcribe-live"),
        ],
    )
    def test_known_pairs(self, provider, model):
        assert is_realtime_model(provider, model) is True

    def test_whitespace_stripped(self):
        assert is_realtime_model("  openai  ", "  gpt-live-transcribe\t") is True

    @pytest.mark.parametrize(
        "provider,model",
        [(None, None), (None, "gpt-live-transcribe"), ("openai", None), (None, 42), (123, "x")],
    )
    def test_none_and_non_str_safe(self, provider, model):
        assert is_realtime_model(provider, model) is False

    @pytest.mark.parametrize(
        "provider,model",
        [
            ("OpenAI", "gpt-live-transcribe"),
            ("openai", "GPT-LIVE-TRANSCRIBE"),
            ("OPENAI", "GPT-REALTIME-WHISPER"),
            ("Gemini", "gemini-3.5-transcribe-live"),
        ],
    )
    def test_case_sensitive(self, provider, model):
        assert is_realtime_model(provider, model) is False

    @pytest.mark.parametrize(
        "provider,model",
        [
            ("openai", "whisper-1"),
            ("openai", "gpt-4o-transcribe"),
            ("groq", "whisper-large-v3"),
            ("deepgram", "nova-3"),
            ("gemini", "gemini-3.5-transcribe"),
            ("unknown", "gpt-live-transcribe"),
            ("openai", ""),
            ("", ""),
        ],
    )
    def test_batch_models_excluded(self, provider, model):
        assert is_realtime_model(provider, model) is False


class TestEnvelopes:
    def test_session_update_shape(self):
        assert build_session_update("gpt-live-transcribe") == {
            "type": "session.update",
            "session": {
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": {"type": "audio/pcm", "rate": 24000},
                        "transcription": {"model": "gpt-live-transcribe"},
                        "turn_detection": None,
                    }
                },
            },
        }

    def test_append_envelope_roundtrip(self):
        raw = b"\x01\x02\xfe\xffhello"
        envelope = build_append_envelope(raw)
        assert envelope["type"] == "input_audio_buffer.append"
        assert base64.b64decode(envelope["audio"]) == raw

    def test_append_envelope_empty(self):
        assert build_append_envelope(b"") == {"type": "input_audio_buffer.append", "audio": ""}

    def test_commit_envelope_shape(self):
        assert build_commit_envelope() == {"type": "input_audio_buffer.commit"}


class TestPcm16:
    def test_clip(self):
        audio = np.array([2.0, -2.0, 0.5, -0.5, 0.0], dtype=np.float32)
        assert float32_to_pcm16(audio) == np.array(
            [32767, -32767, 16383, -16383, 0], dtype="<i2"
        ).tobytes()

    def test_empty(self):
        assert float32_to_pcm16(np.zeros(0, dtype=np.float32)) == b""


class TestResample:
    def test_ratio_3_to_2(self):
        pcm = np.zeros(100, dtype="<i2").tobytes()
        assert len(resample_16k_to_24k(pcm)) == 150 * 2

    def test_small_ratio(self):
        pcm = np.zeros(4, dtype="<i2").tobytes()
        assert len(resample_16k_to_24k(pcm)) == 6 * 2

    def test_constant_signal_preserved(self):
        pcm = np.full(8, 1000, dtype="<i2").tobytes()
        assert np.frombuffer(resample_16k_to_24k(pcm), dtype="<i2").tolist() == [1000] * 12

    def test_ramp_interpolated(self):
        pcm = np.array([0, 1000, 2000, 3000], dtype="<i2").tobytes()
        assert np.frombuffer(resample_16k_to_24k(pcm), dtype="<i2").tolist() == [
            0,
            600,
            1200,
            1800,
            2400,
            3000,
        ]

    def test_empty(self):
        assert resample_16k_to_24k(b"") == b""

    def test_single_sample(self):
        pcm = np.array([1234], dtype="<i2").tobytes()
        assert np.frombuffer(resample_16k_to_24k(pcm), dtype="<i2").tolist() == [1234, 1234]


class TestFraming:
    def test_exact_multiple(self):
        pcm = bytes(9600 * 2)
        frames = list(frame_200ms(pcm))
        assert len(frames) == 2
        assert all(len(f) == 9600 for f in frames)

    def test_short_tail_kept(self):
        pcm = bytes(9600 + 100)
        frames = list(frame_200ms(pcm))
        assert [len(f) for f in frames] == [9600, 100]
        assert b"".join(frames) == pcm

    def test_empty_yields_nothing(self):
        assert list(frame_200ms(b"")) == []

    def test_custom_frame_size(self):
        frames = list(frame_200ms(bytes(10), frame_samples=2))
        assert [len(f) for f in frames] == [4, 4, 2]


class TestAssembler:
    def test_delta_then_completed_without_transcript(self):
        assembler = DeltaAssembler()
        assembler.feed({"type": "conversation.item.input_audio_transcription.delta", "delta": "hello "})
        assembler.feed({"type": "conversation.item.input_audio_transcription.delta", "delta": "world"})
        assembler.feed({"type": "conversation.item.input_audio_transcription.completed"})
        assert assembler.result() == "hello world"

    def test_completed_only(self):
        assembler = DeltaAssembler()
        assembler.feed(
            {"type": "conversation.item.input_audio_transcription.completed", "transcript": "done"}
        )
        assert assembler.result() == "done"

    def test_completed_transcript_wins_over_deltas(self):
        assembler = DeltaAssembler()
        assembler.feed({"type": "x.transcription.delta", "delta": "stale"})
        assembler.feed({"type": "x.transcription.completed", "transcript": "final"})
        assert assembler.result() == "final"

    def test_failed_raises(self):
        assembler = DeltaAssembler()
        with pytest.raises(CloudEngineError):
            assembler.feed({"type": "conversation.item.input_audio_transcription.failed"})

    def test_reset(self):
        assembler = DeltaAssembler()
        assembler.feed({"type": "x.transcription.delta", "delta": "hello"})
        assembler.feed({"type": "x.transcription.completed", "transcript": "hello"})
        assembler.reset()
        assert assembler.result() == ""
        assembler.feed({"type": "x.transcription.delta", "delta": "again"})
        assembler.feed({"type": "x.transcription.completed"})
        assert assembler.result() == "again"

    def test_unrelated_types_ignored(self):
        assembler = DeltaAssembler()
        assembler.feed({"type": "session.created"})
        assert assembler.result() == ""


class TestWsSubset:
    def test_ws_models_are_openai_only(self):
        assert {
            ("openai", "gpt-live-transcribe"),
            ("openai", "gpt-realtime-whisper"),
        } == WS_REALTIME_MODELS
        assert set(REALTIME_MODELS) > WS_REALTIME_MODELS

    @pytest.mark.parametrize(
        "provider,model",
        [("openai", "gpt-live-transcribe"), ("openai", "gpt-realtime-whisper")],
    )
    def test_ws_pairs(self, provider, model):
        assert is_ws_realtime_model(provider, model) is True

    @pytest.mark.parametrize(
        "provider,model",
        [
            ("gemini", "gemini-3.5-transcribe-live"),
            ("openai", "whisper-1"),
            (None, None),
        ],
    )
    def test_non_ws_pairs(self, provider, model):
        assert is_ws_realtime_model(provider, model) is False

    def test_official_host_accepted(self):
        assert (
            assert_official_realtime_host("https://api.openai.com/v1/audio/transcriptions")
            is None
        )

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/v1/realtime",
            "https://api.openai.com.evil.com/v1/realtime",
            "",
            None,
        ],
    )
    def test_foreign_host_rejected(self, url):
        with pytest.raises(CloudConfigError):
            assert_official_realtime_host(url)


class TestGuard:
    @pytest.mark.parametrize(
        "provider,model",
        [
            ("openai", "gpt-live-transcribe"),
            ("openai", "gpt-realtime-whisper"),
            ("gemini", "gemini-3.5-transcribe-live"),
        ],
    )
    def test_realtime_raises(self, provider, model):
        with pytest.raises(CloudConfigError) as exc_info:
            ensure_not_realtime(provider, model)
        assert model in str(exc_info.value)
        assert "live" in str(exc_info.value).lower()

    def test_batch_passes(self):
        assert ensure_not_realtime("openai", "whisper-1") is None


class TestEngineGuard:
    def test_ws_model_routes_to_realtime_session(self, monkeypatch):
        import voice_typer.server.cloud._engine as engine_module
        from voice_typer.server import cloud_engines
        from voice_typer.server.cloud import _realtime_ws
        from voice_typer.server.cloud._engine import CloudEngine

        engine = CloudEngine(
            provider="openai",
            api_key="test-key",
            model="gpt-live-transcribe",
            consent_given=True,
        )
        calls: list[dict] = []

        def _fake_transcribe(**kwargs):
            calls.append(kwargs)
            return "hello"

        def _fail_encode(_audio):
            raise AssertionError("WAV encode must not run for realtime ids")

        class _FailOpener:
            def open(self, *args, **kwargs):
                raise AssertionError("HTTP opener must not run for realtime ids")

        monkeypatch.setattr(engine_module, "_audio_to_wav_bytes", _fail_encode)
        monkeypatch.setattr(cloud_engines, "_opener", _FailOpener())
        monkeypatch.setattr(_realtime_ws, "transcribe_via_realtime", _fake_transcribe)
        assert engine._send_request(np.zeros(160, dtype=np.float32)) == "hello"
        assert calls and calls[0]["model"] == "gpt-live-transcribe"

    def test_unsupported_realtime_never_reaches_transport(self, monkeypatch):
        import voice_typer.server.cloud._engine as engine_module
        from voice_typer.server import cloud_engines
        from voice_typer.server.cloud._engine import CloudEngine

        engine = CloudEngine(
            provider="gemini",
            api_key="test-key",
            model="gemini-3.5-transcribe-live",
            consent_given=True,
        )

        def _fail_encode(_audio):
            raise AssertionError("WAV encode must not run for realtime ids")

        class _FailOpener:
            def open(self, *args, **kwargs):
                raise AssertionError("HTTP opener must not run for realtime ids")

        monkeypatch.setattr(engine_module, "_audio_to_wav_bytes", _fail_encode)
        monkeypatch.setattr(cloud_engines, "_opener", _FailOpener())
        with pytest.raises(CloudConfigError):
            engine._send_request(np.zeros(160, dtype=np.float32))

    def test_ws_model_rejects_custom_host(self):
        from voice_typer.server.cloud._engine import CloudEngine

        engine = CloudEngine(
            provider="openai",
            api_key="test-key",
            api_url="https://example.com/v1/audio/transcriptions",
            model="gpt-live-transcribe",
            consent_given=True,
        )
        with pytest.raises(CloudConfigError):
            engine._send_request(np.zeros(160, dtype=np.float32))

    def test_empty_audio_returns_before_any_io(self, monkeypatch):
        from voice_typer.server.cloud import _realtime_ws
        from voice_typer.server.cloud._engine import CloudEngine

        engine = CloudEngine(
            provider="openai",
            api_key="test-key",
            model="gpt-live-transcribe",
            consent_given=True,
        )

        def _fail_transcribe(**kwargs):
            raise AssertionError("WS session must not run for empty audio")

        monkeypatch.setattr(_realtime_ws, "transcribe_via_realtime", _fail_transcribe)
        assert engine._send_request(np.zeros(0, dtype=np.float32)) == ""

    def test_oversized_audio_refuses_before_ws(self, monkeypatch):
        from voice_typer.server.asr_errors import CloudNetworkError
        from voice_typer.server.cloud import _realtime_ws
        from voice_typer.server.cloud._engine import CloudEngine
        from voice_typer.server.cloud._fallback import _fallback_kind

        engine = CloudEngine(
            provider="openai",
            api_key="test-key",
            model="gpt-live-transcribe",
            consent_given=True,
        )

        def _fail_transcribe(**kwargs):
            raise AssertionError("WS session must not run for oversized audio")

        monkeypatch.setattr(_realtime_ws, "transcribe_via_realtime", _fail_transcribe)
        # 6M float32 samples resample past the 15 MiB PCM cap.
        with pytest.raises(CloudNetworkError) as exc_info:
            engine._send_request(np.zeros(6_000_000, dtype=np.float32))
        # Client-side refusal: the request never reached the provider, so
        # the fallback kind must stay "network" (local fallback eligible).
        assert _fallback_kind(exc_info.value) == "network"
