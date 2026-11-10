"""Activation record: the bridge between a finished install and the respawn.

The download never writes ``config.device``. It writes this record, the
renderer restarts the sidecar, and the next process proves the stack before
it persists ``"cuda"``. A failure keeps the record so the UI can explain what
went wrong instead of silently staying on CPU.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from voice_typer.server.cuda_install.paths import activation_file

PENDING = "pending"
FAILED = "failed"


def read() -> dict[str, Any] | None:
    """Current activation record, or ``None`` when nothing is pending."""
    path = activation_file()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    state = data.get("state")
    if state not in (PENDING, FAILED):
        return None
    return data


def write_pending(artifacts: list[str]) -> None:
    _write({"state": PENDING, "artifacts": artifacts, "written_at": time.time()})


def write_failure(reason: str) -> None:
    _write({"state": FAILED, "reason": reason, "written_at": time.time()})


def clear() -> None:
    try:
        activation_file().unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def _write(payload: dict[str, Any]) -> None:
    path = activation_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)
