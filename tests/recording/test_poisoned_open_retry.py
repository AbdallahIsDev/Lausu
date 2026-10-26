"""Poisoned PortAudio state must go to reinit, not a same-candidate retry.

A ``-9999`` / WdmSyncIoctl open failure means the host API state itself is
poisoned (WDM-KS leaking into a WASAPI open). Re-opening the same device
without ``Pa_Terminate``/``Pa_Initialize`` cannot succeed, so the
per-candidate "transient" retry was a guaranteed-failing open plus a sleep
on the dictation hotkey thread. These tests pin the split: poisoned
signatures skip the plain retry (one open attempt), while a genuinely
transient hold still earns its retry (two attempts).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from voice_typer.server.recording import stream_lifecycle as sl_mod
from voice_typer.server.recording.stream_lifecycle import StreamLifecycle

_WDM_SYNC_IOCTL = (
    "Error starting stream: Unanticipated host error [PaErrorCode -9999]: "
    "'WdmSyncIoctl: DeviceIoControl GLE = 0x00000492 (prop_set = "
    "{1464EDA5-6A8F-11D1-9AA7-00A0C9223196}, prop_id = 0)' [Windows WDM-KS error 0]"
)


class _PortAudioError(Exception):
    """Stands in for sounddevice.PortAudioError (not an OSError)."""


class _FakeSD:
    """Records every InputStream construction; raises on each one."""

    def __init__(self, message: str) -> None:
        self.message = message
        self.open_count = 0

    def InputStream(self, **kwargs):  # noqa: N802 - mirrors sounddevice API
        self.open_count += 1
        raise _PortAudioError(self.message)

    def _terminate(self) -> None:
        pass

    def _initialize(self) -> None:
        pass


def _recorder() -> MagicMock:
    recorder = MagicMock(name="recorder")
    recorder.config.recording_channels = 1
    recorder._devices._resolve_effective_sample_rate.return_value = (48000, None)
    recorder._cached_max_input_channels.return_value = 1
    return recorder


def _run(monkeypatch: pytest.MonkeyPatch, message: str) -> _FakeSD:
    fake_sd = _FakeSD(message)
    monkeypatch.setattr(sl_mod, "sd", fake_sd)
    lifecycle = StreamLifecycle(recorder=MagicMock())
    lifecycle._attempt_candidate_list(
        _recorder(),
        candidates=[28],
        callback=MagicMock(),
        effective_sr=48000,
        last_error=None,
    )
    return fake_sd


@pytest.mark.parametrize(
    "message",
    [
        _WDM_SYNC_IOCTL,
        "Error starting stream: Unanticipated host error [PaErrorCode -9999]: 'boom'",
    ],
)
def test_poisoned_signature_skips_the_plain_retry(monkeypatch, message):
    fake_sd = _run(monkeypatch, message)
    assert fake_sd.open_count == 1, (
        "a poisoned PortAudio state cannot be cured by re-opening the same "
        "candidate; the open must fall through to the reinit branch"
    )


def test_genuinely_transient_hold_still_retries_once(monkeypatch):
    fake_sd = _run(monkeypatch, "Error opening InputStream: Device or resource busy")
    assert fake_sd.open_count == 2, "an exclusive hold is worth one delayed retry"


def test_poisoned_failure_still_earns_the_reinit_branch(monkeypatch):
    """The reinit path must still fire: skipping the retry is not skipping the cure."""
    fake_sd = _FakeSD(_WDM_SYNC_IOCTL)
    monkeypatch.setattr(sl_mod, "sd", fake_sd)
    recorder = _recorder()
    lifecycle = StreamLifecycle(recorder=MagicMock())

    selected, _sr, last_error = lifecycle.open_stream_for_candidates(
        recorder,
        candidates=[28],
        callback=MagicMock(),
        effective_sr=48000,
        last_error=None,
    )

    assert selected is None
    assert last_error is not None
    # One open in the first pass, one in the post-reinit pass: the reinit
    # branch ran and the configured candidate list was retried.
    assert fake_sd.open_count == 2
    recorder._devices._invalidate_device_cache.assert_called_once()
