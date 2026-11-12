"""Policy + cache for LOCAL provider catalogue probes (Ollama, LM Studio).

Two problems this solves, both visible as ``[PROVIDERS] … catalogue unavailable``
spam on a machine that has neither server installed:

1. **Dialling a server nobody asked for.** ``provider_list`` runs on every
   Providers-page mount and after every key/domain write, and it enumerated
   EVERY provider's catalogue — including two local servers that may not even be
   installed. A probe against a dead port costs a full connect timeout (2 s for
   Ollama, 15 s for a filtered LM Studio port), so the page blocked for seconds
   per command to learn nothing. A local catalogue is now only probed when the
   user has pointed us at that server: a custom base URL is set, or one of the
   three domains selects it. Explicit actions (Test connection, a ``refresh``
   catalogue read) bypass the gate — see :func:`force_local_catalogue`.
2. **Probing the same server repeatedly.** Even when it IS wanted, the answer
   only changes when the user starts or stops the server, so one probe per short
   window is enough. Concurrent callers share the in-flight result
   (single-flight) — which also collapses the React StrictMode double-effect's
   two simultaneous ``provider_list`` calls into one probe — and a FAILURE is
   cached too (negative cache).
"""

from __future__ import annotations

import contextlib
import contextvars
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

#: Long enough to absorb a page's mount + its follow-up writes, short enough
#: that starting the local server becomes visible without a restart.
_LOCAL_TTL_SECONDS = 30.0

#: A waiter must never outlive the probe it waits on by much; the probe itself
#: is bounded by its own connect timeout.
_WAIT_SECONDS = 15.0

#: Set for the duration of an explicit probe request (Test connection, a
#: ``refresh`` catalogue read) so the opt-in gate cannot suppress it.
_FORCED: contextvars.ContextVar[bool] = contextvars.ContextVar("local_catalogue_forced", default=False)


@contextlib.contextmanager
def force_local_catalogue() -> Iterator[None]:
    """Probe local servers even when no config points at them."""
    token = _FORCED.set(True)
    try:
        yield
    finally:
        _FORCED.reset(token)


def local_catalogue_forced() -> bool:
    return _FORCED.get()


def local_catalogue_wanted(provider_id: str, base_url: str, selected: set[str]) -> bool:
    """True when this local server is one the user actually uses.

    ``base_url`` is the provider's own config field (non-empty = a custom
    endpoint was configured) and ``selected`` is the set of provider ids the
    three domains currently point at.
    """
    if local_catalogue_forced():
        return True
    return bool(base_url.strip()) or provider_id in selected


@dataclass(frozen=True)
class _Entry:
    at: float
    models: tuple[Any, ...]


_lock = threading.Lock()
_entries: dict[str, _Entry] = {}
_inflight: dict[str, threading.Event] = {}


def cached_local_catalogue(
    provider: str,
    probe: Callable[[], list[Any]],
    *,
    ttl: float = _LOCAL_TTL_SECONDS,
) -> tuple[list[Any], Exception | None]:
    """Return ``(models, error)`` for one local provider, probing at most once.

    ``error`` is non-``None`` only for the call that actually ran the probe, so
    the caller logs one line per probe window instead of one per command.
    Followers get the cached outcome and no error.
    """
    with _lock:
        entry = _entries.get(provider)
        if entry is not None and time.monotonic() - entry.at < ttl:
            return list(entry.models), None
        waiter = _inflight.get(provider)
        leader = waiter is None
        if leader:
            waiter = threading.Event()
            _inflight[provider] = waiter

    if not leader:
        # Single-flight: share the leader's outcome instead of dialling again.
        waiter.wait(_WAIT_SECONDS)
        with _lock:
            entry = _entries.get(provider)
        return (list(entry.models) if entry is not None else []), None

    models: list[Any] = []
    error: Exception | None = None
    try:
        models = list(probe())
    except Exception as exc:  # noqa: BLE001 - handed to the caller, never swallowed
        error = exc
    finally:
        # Publish before waking the waiters, and wake them even on a crash so a
        # dead probe cannot wedge every later caller for _WAIT_SECONDS.
        with _lock:
            _entries[provider] = _Entry(time.monotonic(), tuple(models))
            _inflight.pop(provider, None)
        waiter.set()
    return models, error


def clear_local_catalogue(provider: str | None = None) -> None:
    """Forget cached local catalogues (one provider, or all when ``None``)."""
    with _lock:
        if provider is None:
            _entries.clear()
        else:
            _entries.pop(provider, None)


__all__ = [
    "cached_local_catalogue",
    "clear_local_catalogue",
    "force_local_catalogue",
    "local_catalogue_forced",
    "local_catalogue_wanted",
]
