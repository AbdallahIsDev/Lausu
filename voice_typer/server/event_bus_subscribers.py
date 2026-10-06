"""Subscriber set for the in-process event bus.

Holds the rate-limit key helper and the weak-ref-aware subscriber
container. Moved verbatim out of ``voice_typer.server.event_bus`` (which
re-exports every name here, so historical import paths keep resolving).
No other state: the live subscriber set itself stays on the bus facade.
"""

from __future__ import annotations

import typing
import weakref


def _subscriber_key(fn: typing.Callable[..., typing.Any]) -> str:
    """Return a stable string key identifying *fn* for rate-limit counters.

    Used as the ``key=`` argument to :func:`log_rate_limited` so that each
    distinct subscriber gets its own counter: the FIRST exception from a
    given subscriber logs at WARNING (with full traceback); subsequent
    exceptions from the SAME subscriber log at DEBUG (no traceback) so a
    persistently-broken subscriber doesn't spam the production log.

    Strategy:
    - Bound methods (``self.method``): include ``id(self.__self__)`` so
      two methods bound to different instances get separate counters.
    - Named functions / unbound methods: use ``module.qualname`` —
      stable across calls and unique within a process.
    - Lambdas and C-level callables (``__qualname__`` is ``<lambda>``
      or absent): fall back to ``id(fn)``: unique for the callable's
      lifetime, which is the only window the counter matters for.
    """
    qualname = getattr(fn, "__qualname__", None) or ""
    module = getattr(fn, "__module__", "") or ""
    # Bound methods: include id() of the bound instance so two methods
    self_obj = getattr(fn, "__self__", None)
    if self_obj is not None:
        return f"{module}.{qualname}@0x{id(self_obj):x}"
    if qualname and qualname != "<lambda>":
        return f"{module}.{qualname}" if module else qualname
    # Lambdas and C-level callables: use id() of the callable itself.
    return f"callable@0x{id(fn):x}"


class _StrongResolver:
    """Resolver that always returns the wrapped strong-ref callable."""

    __slots__ = ("_fn",)

    def __init__(self, fn):
        self._fn = fn

    def __call__(self):
        return self._fn


class _CWeakResolver:
    """Resolver for C-level bound methods stored via weakref.ref."""

    __slots__ = ("_ref", "_name")

    def __init__(self, ref, name):
        self._ref = ref
        self._name = name

    def __call__(self):
        obj = self._ref()
        if obj is None:
            return None
        return getattr(obj, self._name, None)


class _SubscriberSet:
    """A set-like container for event-bus subscribers ().

    ``IPCServer`` subscribes with ``subscribe(self.push)``, a *bound
    method*. A plain ``set`` holds a strong ref to the bound method,
    which holds a strong ref to the IPCServer via ``__self__``. If the
    IPCServer is destroyed without calling ``unsubscribe(self.push)``
    (exception during ``stop()``, crash, ``restart_app``), the bound
    method keeps the IPCServer alive forever, a leak.

    This container fixes the leak by storing bound methods via
    ``weakref.WeakMethod`` (Python-level) or ``weakref.ref(__self__)``
    (C-level like ``list.append``): when the owning instance is GC'd,
    the weak ref's callback fires and the entry is evicted automatically.
    Plain functions / lambdas are stored as strong refs (``weakref.ref``
    of an ephemeral lambda would die immediately).
    """

    def __init__(self) -> None:
        self._strong: set[typing.Callable[[dict], None]] = set()
        # Python bound methods (have __func__), keyed by
        self._weak_py: dict[tuple[int, int], weakref.WeakMethod] = {}
        # C-level bound methods (e.g. list.append, have __self__ +
        self._weak_c: dict[tuple[int, str], tuple[weakref.ref, str]] = {}
        # Fallback for C-level bound methods whose __self__ is not
        self._strong_c: dict[tuple[int, str], typing.Callable[[dict], None]] = {}
        # Snapshot tuple of resolvers (WeakMethod / _StrongResolver /
        self._snapshot: tuple = ()

    @staticmethod
    def _classify(callback: typing.Any) -> str:
        self_obj = getattr(callback, "__self__", None)
        if self_obj is None:
            return "plain"
        if hasattr(callback, "__func__"):
            return "py_bound"
        if hasattr(callback, "__name__"):
            return "c_bound"
        return "plain"

    def add(self, callback: typing.Callable[[dict], None]) -> None:
        kind = self._classify(callback)
        if kind == "py_bound":
            key = (id(callback.__self__), id(callback.__func__))
            if key not in self._weak_py or self._weak_py[key]() is None:
                self._weak_py[key] = weakref.WeakMethod(callback, lambda _ref, k=key: self._weak_py.pop(k, None))
        elif kind == "c_bound":
            key = (id(callback.__self__), callback.__name__)
            existing_weak = self._weak_c.get(key)
            if existing_weak is not None and existing_weak[0]() is not None:
                return
            if key in self._strong_c:
                return
            try:
                ref = weakref.ref(
                    callback.__self__,
                    lambda _r, k=key: self._weak_c.pop(k, None),
                )
            except TypeError:
                self._strong_c[key] = callback
            else:
                self._weak_c[key] = (ref, callback.__name__)
        else:
            self._strong.add(callback)
        self._rebuild_snapshot()

    def discard(self, callback: typing.Callable[[dict], None]) -> None:
        kind = self._classify(callback)
        if kind == "py_bound":
            self._weak_py.pop((id(callback.__self__), id(callback.__func__)), None)
        elif kind == "c_bound":
            key = (id(callback.__self__), callback.__name__)
            self._weak_c.pop(key, None)
            self._strong_c.pop(key, None)
        else:
            self._strong.discard(callback)
        self._rebuild_snapshot()

    def clear(self) -> None:
        self._strong.clear()
        self._weak_py.clear()
        self._weak_c.clear()
        self._strong_c.clear()
        self._snapshot = ()

    def update(self, items: typing.Iterable[typing.Callable[[dict], None]]) -> None:
        for item in items:
            self.add(item)

    def _rebuild_snapshot(self) -> None:
        """Rebuild the resolver snapshot from the current subscriber buckets."""
        resolvers: list[typing.Any] = []
        resolvers.extend(_StrongResolver(fn) for fn in self._strong)
        resolvers.extend(self._weak_py.values())
        for ref, name in list(self._weak_c.values()):
            resolvers.append(_CWeakResolver(ref, name))
        resolvers.extend(_StrongResolver(fn) for fn in self._strong_c.values())
        self._snapshot = tuple(resolvers)

    def __iter__(self) -> typing.Iterator[typing.Callable[[dict], None]]:
        live: list[typing.Callable[[dict], None]] = list(self._strong)
        for key, ref in list(self._weak_py.items()):
            cb = ref()
            if cb is not None:
                live.append(cb)
            else:
                self._weak_py.pop(key, None)
        for key, (ref, name) in list(self._weak_c.items()):
            obj = ref()
            if obj is not None:
                cb = getattr(obj, name, None)
                if cb is not None:
                    live.append(cb)
                else:
                    self._weak_c.pop(key, None)
            else:
                self._weak_c.pop(key, None)
        live.extend(self._strong_c.values())
        return iter(live)

    def __len__(self) -> int:
        for key in [k for k, r in self._weak_py.items() if r() is None]:
            self._weak_py.pop(key, None)
        for key in [k for k, (r, _n) in self._weak_c.items() if r() is None]:
            self._weak_c.pop(key, None)
        return len(self._strong) + len(self._weak_py) + len(self._weak_c) + len(self._strong_c)

    def __contains__(self, callback: typing.Callable[[dict], None]) -> bool:
        kind = self._classify(callback)
        if kind == "py_bound":
            ref = self._weak_py.get((id(callback.__self__), id(callback.__func__)))
            return ref is not None and ref() is not None
        elif kind == "c_bound":
            key = (id(callback.__self__), callback.__name__)
            if key in self._strong_c:
                return True
            entry = self._weak_c.get(key)
            return entry is not None and entry[0]() is not None
        return callback in self._strong
