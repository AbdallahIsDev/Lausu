"""Shared recording-open guards for :class:`Recorder` paths."""

from __future__ import annotations


def _looks_permission_blocked(exc: BaseException | None) -> bool:
    """True when every open failure so far is the OS privacy-block signal."""
    if exc is None:
        return False
    msg = str(exc).lower()
    return "-9999" in msg or "unanticipated host error" in msg


def raise_if_permission_blocked(exc: BaseException | None) -> None:
    """Raise typed denial when the failure is the privacy-block signal."""
    if not _looks_permission_blocked(exc):
        return
    from voice_typer.server.asr_errors import MicrophonePermissionDeniedError

    raise MicrophonePermissionDeniedError(
        "Microphone blocked by OS privacy settings",
        state="denied",
    ) from exc
