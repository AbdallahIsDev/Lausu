"""microphone_test_status: running progress + last-test review payload."""

from __future__ import annotations


def _reset(monkeypatch=None):
    from voice_typer.server.level_monitor import test_recording_lifecycle as lc

    lc.clear_last_test()


def test_idle_no_last():
    from voice_typer.server.level_monitor import test_recording_lifecycle as lc

    _reset()
    status = lc.get_test_status()
    assert status["running"] is False
    assert status["elapsed_sec"] == 0.0
    assert status["last_test"] is None


def test_store_and_recall_last():
    from voice_typer.server.level_monitor import test_recording_lifecycle as lc

    _reset()
    lc._store_last_test(
        {
            "success": True,
            "audio_file": {"path": "p.wav", "bytes": 100},
            "raw_audio_file": None,
            "duration_ms": 9982,
            "sample_rate": 44100,
            "quality": {"volume_level": "good"},
        }
    )
    status = lc.get_test_status()
    assert status["running"] is False
    last = status["last_test"]
    assert last["duration_ms"] == 9982
    assert last["quality"] == {"volume_level": "good"}
    assert last["audio_file"] == {"path": "p.wav", "bytes": 100}
    assert last["completed_age_sec"] >= 0.0


def test_failed_stop_stores_nothing():
    from voice_typer.server.level_monitor import test_recording_lifecycle as lc

    _reset()
    lc._store_last_test({"success": False, "audio_file": None})
    assert lc.get_test_status()["last_test"] is None


def test_cancel_clears_last():
    from voice_typer.server.level_monitor import test_recording_lifecycle as lc

    _reset()
    lc._store_last_test(
        {
            "success": True,
            "audio_file": {"path": "p.wav", "bytes": 1},
            "duration_ms": 1,
            "sample_rate": 16000,
            "quality": {},
        }
    )
    assert lc.get_test_status()["last_test"] is not None
    lc.clear_last_test()
    assert lc.get_test_status()["last_test"] is None


def test_stale_last_treated_as_absent(monkeypatch):
    import time

    from voice_typer.server.level_monitor import test_recording_lifecycle as lc
    from voice_typer.server.level_monitor.test_recording_files import (
        MIC_TEST_RECORDING_TTL_SEC,
    )

    _reset()
    lc._store_last_test(
        {
            "success": True,
            "audio_file": {"path": "p.wav", "bytes": 1},
            "duration_ms": 1,
            "sample_rate": 16000,
            "quality": {},
        }
    )
    lc._last_test_completed_at = (
        time.monotonic() - MIC_TEST_RECORDING_TTL_SEC - 1.0
    )
    assert lc.get_test_status()["last_test"] is None


def test_transcription_note_merges():
    from voice_typer.server.level_monitor import test_recording_lifecycle as lc

    _reset()
    lc._store_last_test(
        {
            "success": True,
            "audio_file": {"path": "p.wav", "bytes": 1},
            "duration_ms": 1,
            "sample_rate": 16000,
            "quality": {},
        }
    )
    lc.note_test_transcription("hello", False, None)
    last = lc.get_test_status()["last_test"]
    assert last["transcription"] == "hello"
    assert last["transcription_unavailable"] is False
    # No stored test: no crash, no-op.
    lc.clear_last_test()
    lc.note_test_transcription("x", True, "r")
    assert lc.get_test_status()["last_test"] is None
