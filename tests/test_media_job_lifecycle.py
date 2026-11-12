"""Media job lifecycle vocabulary is the IPC contract (ADR-0029)."""

from __future__ import annotations

import json

from voice_typer.server.media_ingest.jobs import MediaJob
from voice_typer.server.media_ingest.lifecycle import (
    JobPhase,
    JobStatus,
    parse_job_phase,
)


def test_status_values_are_the_wire_strings() -> None:
    assert {status.value for status in JobStatus} == {
        "running",
        "completed",
        "cancelled",
        "failed",
    }


def test_phase_values_are_the_wire_strings() -> None:
    # ``error`` is a backend terminal: the renderer drops the row and shows a
    # toast, so it never renders an error phase.
    assert {phase.value for phase in JobPhase} == {
        "starting",
        "preparing",
        "downloading",
        "loading_model",
        "transcribing",
        "done",
        "error",
    }


def test_parse_job_phase_accepts_known_values_and_rejects_unknown() -> None:
    assert parse_job_phase("transcribing") is JobPhase.TRANSCRIBING
    assert parse_job_phase(JobPhase.DONE) is JobPhase.DONE
    assert parse_job_phase("teleporting") is None
    assert parse_job_phase(None) is None


def test_job_defaults_serialize_as_the_wire_strings() -> None:
    job = MediaJob(job_id="j1", source="a.mp3")

    payload = json.loads(json.dumps({"status": job.status, "phase": job.phase}))

    assert payload == {"status": "running", "phase": "starting"}
