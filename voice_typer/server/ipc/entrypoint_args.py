"""Invocation-selection helpers for the IPC entry point (argv + env).

Split out of ``ipc/entrypoint.py``: how a single invocation selects
behaviour — ``--version`` detection from argv, and the launch-order env
flag read once per boot by ``main``.
"""

from __future__ import annotations

import os


def _version_requested(argv: list[str]) -> bool:
    """Return True when an argv token selects the ``--version`` action.

    Matches the exact ``--version`` flag AND unambiguous argparse prefix
    abbreviations (``--vers``: argparse's ``allow_abbrev`` default
    resolves them to the same action). Used to resolve the installed
    package version lazily: only a ``--version`` invocation pays the
    ``importlib.metadata`` dist-metadata scan.

    The prefix match requires a NON-EMPTY prefix: a bare ``--`` token
    (argparse's end-of-options marker, legitimately present when a
    host or launcher appends it) yields ``arg[2:] == ""``, and every
    string satisfies ``startswith("")``: without the guard the bare
    marker was misclassified as a version request and every such boot
    paid the metadata scan for nothing.
    """
    return any(arg == "--version" or (len(arg) > 2 and "version".startswith(arg[2:])) for arg in argv)


# Environment variable selecting the early server-started launch order.
# Sunset: Tauri WS sidecar is the sole shipping path since the 2026-09-17
# cutover (predecessor removed); keep this default-OFF escape hatch until
# the 2026-Q4 host validation closes, then delete the early-bind branch.
# Deletion checklist (symbol-anchored, FV-64): this flag +
# ``_early_server_started_enabled`` + the ``_ws_early_bind`` branch in
# ``main`` + ``_ws_startup_thread_main_early`` + ``_wrap_dispatch_for_early_bind``,
# ``flush_early_dispatch_buffer`` and ``_drain_early_dispatch_buffer`` in
# ``sidecar_ws`` + ``tests/server/test_early_ws_bind.py``.
_EARLY_SERVER_STARTED_ENV_VAR = "VT_EARLY_SERVER_STARTED"


def _early_server_started_enabled() -> bool:
    """True when the early server-started launch order is selected.

    Read once per boot in :func:`main` (before the launch-order branch)
    so the flag has exactly one selection point; the ws transport
    learns the mode from the server marker attribute
    (``server._early_ws_bind``) rather than re-reading the environment.
    """
    return os.environ.get(_EARLY_SERVER_STARTED_ENV_VAR, "").strip().lower() in {"1", "true"}
