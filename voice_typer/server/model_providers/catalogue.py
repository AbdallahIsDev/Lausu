"""Persisted model-catalogue cache with a TTL and stale-tolerant reads.

A catalogue is expensive (one remote round-trip per provider) but not
authoritative: a stale entry must still let the user keep a previously chosen
model id, so :meth:`CatalogueCache.read` returns the stale snapshot with
``stale=True`` instead of raising.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from voice_typer.server._paths import config_dir

log = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 6 * 60 * 60
_CACHE_FILENAME = "provider_catalogue.json"


@dataclass(frozen=True)
class CatalogueSnapshot:
    """One provider's cached catalogue."""

    provider: str
    models: list[dict[str, Any]] = field(default_factory=list)
    fetched_at: float = 0.0
    ttl_seconds: float = DEFAULT_TTL_SECONDS

    @property
    def age_seconds(self) -> float:
        return max(0.0, time.time() - self.fetched_at)

    @property
    def stale(self) -> bool:
        return self.age_seconds > self.ttl_seconds

    def model_ids(self) -> list[str]:
        return [str(m.get("id", "")) for m in self.models if m.get("id")]


class CatalogueCache:
    """JSON-file cache keyed by provider id."""

    def __init__(self, path: Path | None = None, *, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
        self._path = path
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._memory: dict[str, CatalogueSnapshot] = {}

    def _cache_path(self) -> Path:
        return self._path or (config_dir() / _CACHE_FILENAME)

    def _load(self) -> dict[str, CatalogueSnapshot]:
        path = self._cache_path()
        if not path.is_file():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("[PROVIDERS] catalogue cache unreadable (%s), starting empty", exc)
            return {}
        snapshots: dict[str, CatalogueSnapshot] = {}
        for provider, entry in (raw or {}).items():
            if not isinstance(entry, dict):
                continue
            snapshots[provider] = CatalogueSnapshot(
                provider=provider,
                models=list(entry.get("models") or []),
                fetched_at=float(entry.get("fetched_at") or 0.0),
                ttl_seconds=float(entry.get("ttl_seconds") or self._ttl),
            )
        return snapshots

    def _save(self, snapshots: dict[str, CatalogueSnapshot]) -> None:
        path = self._cache_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                provider: {
                    "models": snap.models,
                    "fetched_at": snap.fetched_at,
                    "ttl_seconds": snap.ttl_seconds,
                }
                for provider, snap in snapshots.items()
            }
            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(path)
        except Exception as exc:
            log.debug("[PROVIDERS] catalogue cache write failed: %s", exc)

    def read(self, provider: str) -> CatalogueSnapshot | None:
        """Return the cached snapshot (fresh or stale), or ``None``."""
        with self._lock:
            snap = self._memory.get(provider)
            if snap is None:
                all_snaps = self._load()
                self._memory.update(all_snaps)
                snap = all_snaps.get(provider)
            return snap

    def write(self, provider: str, models: list[dict[str, Any]]) -> CatalogueSnapshot:
        """Persist a freshly fetched catalogue."""
        snap = CatalogueSnapshot(
            provider=provider,
            models=list(models),
            fetched_at=time.time(),
            ttl_seconds=self._ttl,
        )
        with self._lock:
            self._memory[provider] = snap
            all_snaps = self._load()
            all_snaps[provider] = snap
            self._save(all_snaps)
        return snap

    def invalidate(self, provider: str | None = None) -> None:
        """Drop one provider's snapshot (or every snapshot)."""
        with self._lock:
            if provider is None:
                self._memory.clear()
                self._save({})
            else:
                self._memory.pop(provider, None)
                all_snaps = self._load()
                all_snaps.pop(provider, None)
                self._save(all_snaps)


_SHARED: CatalogueCache | None = None
_SHARED_LOCK = threading.Lock()


def get_catalogue_cache() -> CatalogueCache:
    global _SHARED
    with _SHARED_LOCK:
        if _SHARED is None:
            _SHARED = CatalogueCache()
    return _SHARED


def clear_catalogue_cache() -> None:
    """Test hook: forget the shared cache instance."""
    global _SHARED
    with _SHARED_LOCK:
        _SHARED = None


__all__ = [
    "CatalogueCache",
    "CatalogueSnapshot",
    "DEFAULT_TTL_SECONDS",
    "clear_catalogue_cache",
    "get_catalogue_cache",
]
