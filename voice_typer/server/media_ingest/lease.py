"""Model leases: a media job owns the engine it started with.

The ASR engine is one shared object behind one shared lock. A media job can
run for minutes, while a model switch is a click: without a lease the switch
unloads the model under a running decode, and the job either produces a
truncated transcript that still reports success or dies with an unrelated
internal error. There is also no way to say WHICH engine produced a row.

A lease is taken for the whole job (BEFORE the model load, relabelled once
the engine is known, released in a ``finally``) and records the engine label
the job actually got. The model layer asks
:meth:`ModelLeaseGate.wait_for_idle` before it unloads anything, so a switch
defers, then cancels with a reason, and only then frees the engine — it never
tears down a live or loading one.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Final

#: Label of a lease whose job is still loading its engine (the engine name
#: is only known after the load returns; ``relabel`` replaces this).
PENDING_ENGINE_LABEL: Final[str] = "pending"

#: How long a model switch waits for running media jobs before it cancels
#: them. Long enough for a short clip to land, short enough that a model
#: switch never looks hung.
MODEL_SWITCH_LEASE_TIMEOUT_S: Final[float] = 30.0

#: Second wait after cancelling: the jobs need a moment to unwind their
#: decode and release the lease before the engine may be unloaded.
MODEL_SWITCH_LEASE_CANCEL_GRACE_S: Final[float] = 5.0


class ModelLeaseGate:
    """Tracks running media jobs per engine label (thread-safe)."""

    def __init__(self) -> None:
        self._condition = threading.Condition(threading.Lock())
        self._holders: dict[object, str] = {}

    def begin(self, engine_label: str) -> object:
        """Register one running job; the returned token is its identity."""
        token = object()
        with self._condition:
            self._holders[token] = engine_label
        return token

    def relabel(self, token: object, engine_label: str) -> None:
        """Name the engine a job will use, once the load has resolved it.

        A job leases itself BEFORE the model load (so the switch cannot
        unload the model it is loading); the engine name is only known after
        that load returns. Relabelling an already-released token is a no-op,
        never a resurrected lease.
        """
        with self._condition:
            if token in self._holders:
                self._holders[token] = engine_label

    def end(self, token: object) -> None:
        """Release one job's lease (idempotent)."""
        with self._condition:
            self._holders.pop(token, None)
            self._condition.notify_all()

    def active(self) -> int:
        with self._condition:
            return len(self._holders)

    def engines(self) -> set[str]:
        with self._condition:
            return set(self._holders.values())

    def wait_for_idle(self, timeout: float) -> bool:
        """Block until every lease is released; False on timeout."""
        with self._condition:
            return bool(self._condition.wait_for(lambda: not self._holders, timeout=timeout))

    @contextmanager
    def held(self, engine_label: str) -> Iterator[Any]:
        """Context-manager form used by the job bodies."""
        token = self.begin(engine_label)
        try:
            yield token
        finally:
            self.end(token)


_GATE: ModelLeaseGate | None = None
_GATE_LOCK = threading.Lock()


def get_lease_gate() -> ModelLeaseGate:
    """Process-wide gate (one engine, one truth about who is using it)."""
    global _GATE
    if _GATE is None:
        with _GATE_LOCK:
            if _GATE is None:
                _GATE = ModelLeaseGate()
    return _GATE
