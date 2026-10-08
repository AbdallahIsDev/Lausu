"""In-process event bus for broadcasting events to subscribers.

Leaf of the dependency tree, it imports only stdlib plus
:mod:`voice_typer.server.log_rate_limit` (itself stdlib-only), so any
module can import it without a circular-import risk. Domain modules
(recording, service, app, tray, hotkey_dispatcher, level_monitor,
dictation_pipeline, startup_tasks, recording_controller,
handlers/config_handlers, handlers/system_handlers, tray_window) call
``publish(event)`` to broadcast a JSON-lines event.

The IPC server (``voice_typer.server.ipc_server.IPCServer``) calls
``subscribe(self.push)`` on ``start()`` and ``unsubscribe(self.push)``
on ``stop()`` so that every published event is forwarded to the
connected Tauri host over the sidecar WebSocket (or to stdout in
gated stdin/stdout mode). Other transports (CLI, gRPC, future
WebSocket) can subscribe the same way without touching the domain
modules.

Implementation split (every moved name is re-exported here, so the
historical import path keeps resolving):
:mod:`voice_typer.server.event_bus_subscribers` (weak-ref subscriber
set), :mod:`voice_typer.server.event_bus_delivery` (fan-out, deferred
executor, ``shutdown``). This module owns the event registry, the
subscriber hooks, the transport-probe registry, and ``publish``.

Canonical event catalogue
------------------------------------------------------------
Every event broadcast through ``event_bus.publish`` OR ``IPCServer.push``
flows through the same channel (2) (server-initiated events). The
catalogue below is the source of truth mirrored in ADR-0020 §2's
"Sidecar→UI Event Table". When you ADD an event, append it to BOTH
this list AND the ADR table (the docstring is the code-side anchor;
the ADR is the spec-side anchor). Payload shapes are documented in
``docs/code-notes/event-catalogue.md``.

Events emitted via ``event_bus.publish`` (the modern path):

* ``ready`` (``{}``), ``bubble_show`` / ``bubble_hide`` / ``bubble_config``
  (``{}``), ``bubble_level`` (``{rms, peak}``), ``bubble_set_state``
  (``{state}``).
* ``transcription_final`` (``{text:str (≤200 chr),
  quality?:{mean_logprob, min_logprob, no_speech_prob_max, segments}}``;
  ``quality`` only from the Whisper batch path) and
  ``transcription_partial`` (``{text, cycle_id, supported?:false}``,
  ≤4 Hz latest-value-wins live preview; ``supported:false`` once per
  recording start when the engine lacks ``transcribe_words``).
* ``vocabulary_suggestion``, ``hotkey_capture_cancel``,
  ``config_changed``, ``history_changed``.
* ``microphone_test_complete``, ``microphones_changed``,
  ``microphone_permission_revoked``, ``microphone_disconnected``.
* ``audio_clip``, ``recording_started``, ``recording_stopped``.
* ``download_progress`` (model + progress fields),
  ``notification``, ``navigate``, ``show_window``, ``quit_app``,
  ``relaunch_app``, ``paste_failed``, ``paste_deferred``.
* ``tray_menu`` and ``tray_state`` (Tauri sidecar host only,
  ``TAURI_SIDECAR=1``; standalone pystray updates the native menu /
  ``TrayIcon`` directly), ``tray_fallback_notification`` (tray
  unavailable; queued notifications drained to log + this event).
* ``consent_required``, ``parakeet_cpu_fallback``, ``gpu_cpu_fallback``
  (published BEFORE the Whisper GPU→CPU reload so the tray can surface
  "switching to CPU" during the multi-second reload),
  ``cloud_fallback_used``,
  ``llm_polish_failed``, ``error``.
* Model-load lifecycle: ``asr_backend_ready``,
  ``asr_backend_load_failed``, ``asr_backend_disabled``,
  ``asr_last_resort_unloaded``.
* Pipeline / device observability: ``dictation_suppressed``,
  ``dictation_lost``, ``device_lost``, ``mic_level``.
* History-store integrity: ``history_corrupted``,
  ``history_fts5_rebuild_failed``.
* ADR-0023 media jobs: ``media_transcribe_progress``,
  ``media_transcribe_complete``, ``media_transcribe_error``.

Master plan §7.4, runtime-pack / worker IPC events (13 event
types introduced by the slim-core / runtime-pack split). The
canonical schema is the ``OFFLINE_PACK_EVENT_TYPES`` frozenset in
``voice_typer/server/service/offline_pack.py``; all 13 are also listed
in the Rust ``ALLOWED_EVENT_TYPES`` slice in
``src-tauri/src/sidecar/ws/event_protocol.rs`` so the Tauri WS reader
does not silently drop the frames. The 12 push events are members of
the TS ``PythonPushEvent`` union
(``voice_typer/client/src/renderer/src/types/ipc/push_events.ts``);
the 1 request event is a member of the TS ``PythonRequest`` union
(``voice_typer/client/src/renderer/src/types/ipc/requests.ts``).
Pinned by ``tests/test_event_types_parity.py``.

* Offline-pack download lifecycle (published by
  ``voice_typer/server/service/offline_pack.py``):
  ``offline_pack_download_started``, ``offline_pack_download_progress``
  (silent, no UI surface today), ``offline_pack_download_completed``,
  ``offline_pack_download_failed`` (retry budgets exhausted).
* Offline-pack integrity: ``offline_pack_verified``,
  ``offline_pack_missing``, ``offline_pack_corrupt``,
  ``offline_pack_ready`` (worker started AND prewarmed).
* Worker process lifecycle (slim-core supervisor):
  ``worker_started`` (``{pid, version, port?}``),
  ``worker_crashed`` (``{pid, exit_code}``),
  ``worker_unloaded`` (``{reason}``).
* Offline transcription: ``transcribe_offline`` (REQUEST,
  renderer → slim core → worker; registered in ``_COMMAND_REGISTRY``)
  and ``transcribe_offline_result`` (PUSH, worker → slim core →
  renderer; ``{text, latency_ms}``); the request resolves to
  ``{type:"ack", data:{queued:True}}``.

Events emitted via ``IPCServer.push`` (NOT through ``event_bus.publish``
— they bypass the bus because they are wired into the IPC accept loop
or the tray-state hook, both of which already hold a reference to the
server):

* ``state_changed``, emitted ONCE per WS client connect so the
  renderer immediately knows the current app state.
  Payload: ``{status:str, message:str}``.
* ``status_change``, emitted on EVERY tray state transition via the
  ``_hook_tray_set_state`` wrapper installed in ``IPCServer.start()``.
  Payload: ``{status:str}``. Distinct from ``state_changed``: the
  former is a per-transition signal with just ``status``; the latter
  is the connect-time snapshot with a ``message`` field.

Total: 51 events, the live count is ``len(EVENT_TYPES)`` and this
sentence is kept in lockstep with it by
``tests/test_event_bus.py::TestCanonicalCatalogue
::test_catalogue_total_count_updated``. Update this docstring whenever
an event is added to ``EVENT_TYPES``.
"""

from __future__ import annotations

import contextlib
import logging
import os
import threading
import typing
import weakref

from voice_typer.server.event_bus_delivery import (  # noqa: F401  # facade re-export
    _DEFERRED_QUEUE_MAX,
    _RT_THREAD_NAME_PREFIXES,
    _deliver,
    _deliver_deferred,
    _get_deferred_executor,
    _is_rt_thread,
    dispatch_deferred,
    shutdown,
)
from voice_typer.server.event_bus_subscribers import (  # noqa: F401  # facade re-export
    _CWeakResolver,
    _StrongResolver,
    _subscriber_key,
    _SubscriberSet,
)
from voice_typer.server.log_rate_limit import log_rate_limited

# The docstring catalogue above lists every event the system knows about,
EVENT_TYPES: frozenset[str] = frozenset(
    {
        "ready",
        "bubble_show",
        "bubble_hide",
        "bubble_level",
        "bubble_set_state",
        "bubble_config",
        "transcription_final",
        "transcription_partial",
        "vocabulary_suggestion",
        "hotkey_capture_cancel",
        "config_changed",
        "history_changed",
        "microphone_test_complete",
        "microphones_changed",
        "audio_clip",
        "recording_started",
        "recording_stopped",
        "download_progress",
        "notification",
        "navigate",
        "show_window",
        "quit_app",
        "relaunch_app",
        "paste_failed",
        "tray_menu",
        "tray_state",
        "consent_required",
        "parakeet_cpu_fallback",
        "gpu_cpu_fallback",
        # IPCServer.push-only (included so assertion doesn't false-positive):
        "state_changed",
        "status_change",
        # ADR-0023 failure push (media_ingest/jobs.py via _on_event, same path):
        "media_transcribe_error",
        # Emitted but missing from the docstring catalogue:
        "asr_backend_disabled",
        "asr_last_resort_unloaded",
        "llm_polish_failed",
        "error",
        "mic_level",
        "device_lost",
        "dictation_lost",
        # Model-load lifecycle (model_manager/_change.py background
        "asr_backend_ready",
        "asr_backend_load_failed",
        # Mid-recording device/permission events (recorder stream's
        "microphone_permission_revoked",
        "microphone_disconnected",
        # Engine / pipeline degradation observability:
        "cloud_fallback_used",
        "dictation_suppressed",
        # History-store integrity:
        "history_corrupted",
        "history_fts5_rebuild_failed",
        # Clipboard paste safety (Secure Input / deferred paste):
        "paste_deferred",
        # Tray-unavailable fallback (tray.py `_drain_pending`):
        "tray_fallback_notification",
        # ADR-0023 media jobs (published in handlers/media_handlers.py,
        # already in Rust ALLOWED_EVENT_TYPES + renderer known-event-types):
        "media_transcribe_complete",
        "media_transcribe_progress",
    }
)

# dev-time assertion gate. Default OFF so production is not
_DEBUG_EVENTS: bool = os.environ.get("VOICE_TYPER_DEBUG_EVENTS", "") == "1"


log = logging.getLogger("voice_typer.server.event_bus")


# weak-ref-aware subscriber set. Bound methods are stored via
_subscribers: _SubscriberSet = _SubscriberSet()

# RLock (not Lock) so a subscriber that calls publish() re-entrantly
_lock = threading.RLock()


def subscribe(callback: typing.Callable[[dict], None] | None) -> None:
    """Register *callback* to receive every published event.

    Calling with ``None`` is a no-op (matches the previous
    ``_set_push_event`` semantics where ``None`` was used as a
    sentinel and rejected).

    Duplicate callbacks are stored only once (set semantics).
    Safe to call from any thread.
    """
    if callback is None:
        return
    with _lock:
        _subscribers.add(callback)


def unsubscribe(callback: typing.Callable[[dict], None] | None) -> None:
    """Unregister *callback*.

    Safe to call with a callback that was never registered (no-op).
    Safe to call with ``None`` (no-op).  Safe to call from any thread.
    """
    if callback is None:
        return
    with _lock:
        _subscribers.discard(callback)


# ``publish()`` returns True when ANY in-process subscriber accepted the
_transport_probes: list[typing.Any] = []
# RLock (not Lock), mirrors ``_lock``: the WeakMethod eviction
_transport_probes_lock = threading.RLock()


def _as_probe_entry(probe: typing.Callable[[], bool]) -> typing.Any:
    """Wrap *probe* for registry storage.

    Bound methods become a ``weakref.WeakMethod`` so the registry
    holds NO strong reference to the owning server: if the server is
    GC'd without an explicit ``unregister_transport_probe`` (e.g. a
    test fixture that deliberately skips ``stop()``), the probe is
    auto-evicted instead of pinning the server alive forever and
    reporting stale liveness for the rest of the process. Plain
    functions / lambdas (test probes, no captured server instance) are
    stored as-is.
    """
    # ``getattr`` with defaults (not ``hasattr``) so the check is
    if getattr(probe, "__self__", None) is not None and getattr(probe, "__func__", None) is not None:
        return weakref.WeakMethod(probe, _on_transport_probe_dead)
    return probe


def _on_transport_probe_dead(ref: typing.Any) -> None:
    """Evict a probe whose owning instance was collected.

    ``weakref.WeakMethod`` callback: fires when the bound method's
    ``__self__`` (the IPC server) is GC'd without a matching
    ``unregister_transport_probe``. Removing the entry keeps
    ``has_live_transport`` truthful and prevents the registry from
    accumulating dead entries across server start/stop cycles.
    """
    with _transport_probes_lock, contextlib.suppress(ValueError):
        # Already unregistered (or evicted by a sibling callback).
        _transport_probes.remove(ref)


def register_transport_probe(probe: typing.Callable[[], bool] | None) -> None:
    """Register *probe*, a zero-arg callable reporting whether the IPC
    transport currently has a live host client connected.

    Extension point used by tests today; no production transport
    registers one. ``IPCServer.stop`` unregisters its (unset) slot.
    Registering ``None`` is a no-op.
    """
    if probe is None:
        return
    with _transport_probes_lock:
        _transport_probes.append(_as_probe_entry(probe))


def unregister_transport_probe(probe: typing.Callable[[], bool] | None) -> None:
    """Unregister *probe* (no-op if unknown or ``None``)."""
    if probe is None:
        return
    with _transport_probes_lock, contextlib.suppress(ValueError):
        # ``WeakMethod.__eq__`` compares the underlying bound method,
        _transport_probes.remove(_as_probe_entry(probe))


def has_live_transport() -> bool:
    """Return True if a registered transport probe reports a live client.

    When NO probes are registered no transport tracks liveness
    (gated-stdin mode and the Tauri WS sidecar register none) —
    return True so callers that publish regardless keep their previous
    behavior in those environments.
    """
    with _transport_probes_lock:
        probes = list(_transport_probes)
    if not probes:
        return True
    for entry in probes:
        # removes them first; the skip is purely defensive).
        cb = entry() if isinstance(entry, weakref.WeakMethod) else entry
        if cb is None:
            continue
        try:
            if cb():
                return True
        except Exception:
            # Isolate probe failures (mirrors ``_deliver``'s
            log_rate_limited(
                log,
                logging.WARNING,
                "[event_bus] transport-liveness probe raised",
                exc_info=True,
                key="event_bus:transport_probe",
            )
            continue
    return False


def publish(event: dict, *, async_dispatch: bool = False) -> bool:
    """Broadcast *event* to every subscriber.

        Parameters
        ----------
        event:
            The event dict. Must contain a ``"type"`` key (validated at
            dev-time when ``VOICE_TYPER_DEBUG_EVENTS=1``).
        async_dispatch:
    when ``True``, fan-out is deferred to the single-worker
            :class:`ThreadPoolExecutor` so the caller returns immediately
            (subscribers run on the executor thread, not the publisher's
            thread). Useful for non-RT publisher threads that must not
            block on slow IPC writes: e.g. the transcription thread
    calling ``publish({"type": "transcription_final", ...})``
    would otherwise block on ``IPCServer.push`` →
    ``socket.sendall`` to a stalled host (seconds of
    latency if the host is paused in the debugger).

            When ``False`` (default), subscribers are called synchronously
            in the publisher's thread (existing ``_push_event_now``
            semantics, most tests assert the callable was invoked by the
            time ``publish`` returns).

            The RT-thread auto-defer (PERF-2) takes precedence over this
            flag: audio-worker / PortAudio threads always defer, regardless
            of the ``async_dispatch`` value, so the RT loop never glitches.

        Returns
        -------
        bool
            ``True`` if at least one subscriber accepted the event
            (returned without raising), OR if the event was queued for
            deferred delivery (``async_dispatch=True`` or RT thread).
            ``False`` if there are no subscribers or every subscriber
            raised on the synchronous path.

        Notes
        -----
        - Synchronous (default): subscribers are called in the publisher's
          thread. This preserves the previous ``_push_event_now`` semantics
          (existing tests assert that the callable was invoked by the time
          ``publish`` returns).
        - PERF-2: When called from a real-time audio thread (``audio-worker``
          or ``PortAudio``-prefixed), fan-out is deferred to a single-worker
          ``ThreadPoolExecutor`` so the RT thread returns in microseconds.
          Synchronous path is preserved for all other threads.
    ``async_dispatch=True`` opts non-RT threads into the same
    deferred path. The bounded queue (, ``_DEFERRED_QUEUE_MAX``)
          protects against unbounded memory growth under backpressure.
        - Exception isolation: a subscriber that raises is logged at
          WARNING (with ``exc_info``) on the first occurrence per
          subscriber, then at DEBUG on subsequent occurrences
          (:func:`log_rate_limited`), and skipped. Other subscribers
          still receive the event. See ``TestSubscriberExceptionIsolation``.
        - The subscriber list is snapshotted under the lock before
          iteration, so ``unsubscribe`` from within a subscriber
          callback does not raise ``RuntimeError: Set changed size
          during iteration`` and the unsubscribed callback will not be
          re-invoked on subsequent publishes.
    """
    # dev-time membership check. Gated by ``_DEBUG_EVENTS`` (env
    if _DEBUG_EVENTS:
        _event_type = event.get("type")
        assert _event_type in EVENT_TYPES, (
            f"Unknown event type: {_event_type!r}. "
            "Add it to EVENT_TYPES in event_bus.py AND to the Rust "
            "ALLOWED_EVENT_TYPES allowlist in src-tauri/src/sidecar/ws.rs."
        )
    snapshot = _subscribers._snapshot
    if not snapshot:
        return False
    # defer fan-out when called from an RT thread.
    if _is_rt_thread() or async_dispatch:
        return dispatch_deferred(event, snapshot)
    return _deliver(event, snapshot)


def _subscriber_count() -> int:
    """Return the current number of subscribers (for tests/diagnostics).

    Not part of the public API; exposed for assertions in
    ``tests/test_event_bus.py`` and for the backward-compat shims
    in ``ipc_server.py``.
    """
    with _lock:
        return len(_subscribers)
