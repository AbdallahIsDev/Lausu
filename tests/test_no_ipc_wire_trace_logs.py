"""C-LOG-3: per-frame IPC wire-trace logs must not return.

Routine RX/TX DEBUG dumps of every WS request/response drowned real
signals. These anchors are the greppable contract named in AGENTS.md.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVER_SRC = REPO_ROOT / "voice_typer" / "server"

FORBIDDEN_SNIPPETS = (
    "RX frame type=",
    "TX response id=",
)

# Quiet-list exemptions that only partially silence the traces are the
# same defect class (they re-admit the dump for "non-routine" frames).
FORBIDDEN_IDENTIFIERS = (
    "_QUIET_FRAME_TYPES",
)


def _iter_python_sources():
    yield from SERVER_SRC.rglob("*.py")


def test_no_per_frame_ipc_wire_trace_logs() -> None:
    offenders: list[str] = []
    for path in _iter_python_sources():
        text = path.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_SNIPPETS:
            if snippet in text:
                offenders.append(f"{path}: contains {snippet!r}")
        for ident in FORBIDDEN_IDENTIFIERS:
            if ident in text:
                offenders.append(f"{path}: contains {ident!r}")
    assert not offenders, (
        "C-LOG-3 forbids per-frame IPC wire-trace logs:\n" + "\n".join(offenders)
    )
