"""Process-level startup setup for the IPC entry point.

Split out of ``ipc/entrypoint.py``: these two helpers make the OS
process itself right (console identity, process group) before any
subsystem is imported. ``main`` calls them in this order, first thing.
"""

from __future__ import annotations

import os

from voice_typer.server.ipc._helpers import log


def _set_process_metadata() -> None:
    """Set process-level metadata (console title, AppUserModelID, etc.).

    BRAND-METADATA: On Windows the Python backend appears as a generic
    pythonw.exe in Task Manager.  We call the platform helper to set
    the console title and AppUserModelID, which improves the process
    identity wherever the OS supports it.
    """
    from voice_typer.server.branding import APP_NAME
    from voice_typer.server.platform_utils import _set_windows_process_metadata

    _set_windows_process_metadata(APP_NAME)


def _detach_process_group() -> bool:
    """Move the sidecar into its own POSIX process group (best-effort).

    The Tauri host spawns the frozen release sidecar as an ``externalBin``
    WITHOUT a pre-exec ``setsid``/``setpgid`` hook (pre_exec is not
    applied to spawned externalBin children in release mode), so the
    sidecar lands in the HOST's process group, a group-wide signal to
    the host (terminal Ctrl-C, group kill) would take the sidecar down
    before the cooperative shutdown handshake runs. The sidecar
    therefore detaches ITSELF: ``os.setpgid(0, 0)`` makes the process
    the leader of a fresh process group, isolating it (and the native
    listeners / prewarm / worker children it later spawns, they
    inherit the new group) from the host's group-wide signals. The
    host's lifecycle control is unaffected: the supervisor kills the
    sidecar BY PID (kill-tree), not by process group.

    POSIX only, a no-op on Windows (process groups are a POSIX
    concept; the Windows host uses Taskkill-style tree kills). The
    early-return guard also keeps the frozen dev-mode exe safe: the
    call is inert everywhere it is not applicable.

    Best-effort by design: any failure is logged at DEBUG and swallowed
    (a ``setpgid`` refusal: e.g. EACCES/EPERM in a sandboxed frozen
    environment, must never block sidecar startup; the sidecar then
    simply stays in the host's group, which is the pre-fix behavior).
    """
    if os.name != "posix":
        return False
    # Resolved via getattr: POSIX-only os attributes are absent from the
    setpgid = getattr(os, "setpgid", None)
    if not callable(setpgid):
        return False
    try:
        setpgid(0, 0)
    except OSError as exc:
        log.debug(
            "[IPC] process-group self-detach unavailable (%s), staying in the parent's group",
            exc,
        )
        return False
    getpgrp = getattr(os, "getpgrp", None)
    pgid = getpgrp() if getpgrp is not None else -1
    log.debug("[IPC] sidecar detached into its own process group (pgid=%d)", pgid)
    return True
