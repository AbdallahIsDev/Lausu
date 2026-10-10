"""Worker startup helpers: prewarm phase + stdout protocol.

Split out of ``voice_typer.worker._ws_server`` (one concern per file).
The facade keeps the module names and every monkeypatch seam; this
module owns the moved bodies only. The ``[STARTUP]`` log lines keep their
space-separated C-LOG-2 ``<duration>`` suffix unchanged.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sys
import time

from voice_typer.server.duration import format_duration
from voice_typer.server.ipc.protocol_version import PROTOCOL_VERSION

log = logging.getLogger("voice_typer.worker")

# Stdout event name. Distinct from the slim-core sidecar's
# ``server_started`` (which the host already listens for) so the host's
# stdout parser can route the worker's bind info to the worker-spawn
# code path (not the sidecar-spawn code path). See master plan §7.3.
_WORKER_STARTED_EVENT = "worker_started"


# ─── Prewarm phase (master plan §6.2 P-1) ──────────────────────────────


def _fast_startup_enabled() -> bool:
    """Read the ``fast_startup`` config toggle (Settings → General).

    The toggle is the user's start/stop switch for prewarm: when
    disabled, the worker skips its warm phase entirely. Read from the
    config file directly, the worker is a separate process spawned
    by the host, so there is no live ``app.config`` instance to
    consult. Defaults to ENABLED on any read failure (the historical
    default; a config hiccup must not silently stop warming).
    """
    try:
        from voice_typer.server.config import Config

        return bool(getattr(Config.load(), "fast_startup", True))
    except Exception:
        log.debug("[WORKER] fast_startup config read failed: defaulting to enabled", exc_info=True)
        return True


def _run_prewarm_phase() -> float:
    """Run the prewarm phase ONCE at worker startup.

    Calls :func:`voice_typer.server.prewarm.warm_imports_for_worker`,
    which pages the runtime-pack libraries' files into the OS standby
    cache (``onnxruntime`` + ``ctranslate2`` + ``numpy`` + ``scipy`` +
    ``faster_whisper``) WITHOUT importing them. The worker still has
    to execute each library's code once, in its own process, that is
    unavoidable, but the cold-disk read is paid here, in the
    background, BEFORE the first transcription request.

    Skips warming entirely when the ``fast_startup`` config toggle is
    disabled (the user's start/stop control, RESTORED 2026-08-14,
    see plan §6.3 addendum). Either way, the warm-run timing is
    persisted via :func:`write_prewarm_status_file` so the About-page
    Cache Status card can show "last run + seconds".

    Returns the elapsed wall-clock seconds (used for the
    ``[STARTUP]`` log line's space-separated ``<duration>`` suffix per C-LOG-2;
    ``0.0`` when prewarm was skipped).
    """
    from datetime import datetime

    from voice_typer.server.prewarm.status import write_prewarm_status_file

    t0 = time.perf_counter()
    if not _fast_startup_enabled():
        log.info("[STARTUP] worker prewarm phase SKIPPED: fast_startup disabled in config")
        write_prewarm_status_file(last_run=None, elapsed_s=0.0)
        return 0.0
    try:
        from voice_typer.server.prewarm import warm_imports_for_worker

        warm_imports_for_worker()
    except Exception:
        # Prewarm is best-effort: a failure here MUST NOT crash the
        # worker (the cold cache only costs latency, never correctness).
        log.debug("[WORKER] prewarm phase failed: continuing with cold cache", exc_info=True)
    elapsed = time.perf_counter() - t0
    write_prewarm_status_file(
        last_run=datetime.now().isoformat(timespec="seconds"),
        elapsed_s=round(elapsed, 1),
    )
    log.info("[STARTUP] worker prewarm phase complete%s", format_duration(elapsed))
    return elapsed


# ─── Stdout protocol ──────────────────────────────────────────────────


def _force_line_buffered_stdout() -> None:
    """Force stdout to line buffering (ADR-0020 §1 Phase-0 blocker).

    When the Tauri host pipes the worker's stdout, CPython switches to
    block buffering, so the ``worker_started`` JSON is held in the
    buffer and the host hangs forever waiting. ``reconfigure`` flips
    the stream back to line buffering so each ``\\n`` flushes.

    Mirrors :func:`voice_typer.server.sidecar_ws._force_line_buffered_stdout`.
    """
    try:
        sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        with contextlib.suppress(Exception):
            sys.stdout = open(  # noqa: SIM115 - intentional reopen
                sys.stdout.fileno(),
                "w",
                buffering=1,
                encoding="utf-8",
                closefd=False,
            )


def _emit_worker_started(port: int, protocol: int = PROTOCOL_VERSION) -> None:
    """Write the ONE structured stdout line the host is parsing for.

    Per master plan §7.3, this is the ONLY thing that ever goes to
    stdout from the worker. Every other log goes to stderr / the
    rotating file log. The host blocks reading stdout until it parses
    this JSON, then opens a WS client to ``ws://127.0.0.1:<port>``.

    The ``protocol`` field lets the host detect version skew at
    handshake time (mirrors :func:`sidecar_ws._emit_server_started`).
    """
    print(
        json.dumps({"event": _WORKER_STARTED_EVENT, "port": int(port), "protocol": int(protocol)}),
        flush=True,
    )
