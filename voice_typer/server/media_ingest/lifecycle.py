"""Closed lifecycle vocabulary for one media transcription job.

The job's status and phase cross the IPC boundary and drive the Media
page's row, so their values are a contract, not free text. The enums keep
one spelling of each value; ``parse_job_phase`` lets a producer pass a raw
string (old call sites, worker payloads) while refusing anything the
renderer cannot render.
"""

from __future__ import annotations

from enum import StrEnum


class JobStatus(StrEnum):
    """Registry status of one job (RUNNING only while it holds a slot)."""

    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class JobPhase(StrEnum):
    """Coarse stage published to the renderer (the row's detail line)."""

    STARTING = "starting"
    PREPARING = "preparing"
    DOWNLOADING = "downloading"
    LOADING_MODEL = "loading_model"
    TRANSCRIBING = "transcribing"
    DONE = "done"
    ERROR = "error"


def parse_job_phase(value: object) -> JobPhase | None:
    """Return the matching phase, or ``None`` for an unknown value."""
    try:
        return JobPhase(value)
    except (TypeError, ValueError):
        return None
