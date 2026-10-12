"""Stale-pack signal store for the host→sidecar outdated relay."""

from __future__ import annotations

import logging
import threading
from types import ModuleType

from .events import _publish_event

log = logging.getLogger(__name__)

PACK_OUTDATED_EVENT = "offline_pack_outdated"

_MAX_OUTDATED_ENTRIES = 8

_lock = threading.Lock()
_outdated: dict[str, dict[str, object]] = {}
_last_version: str | None = None


def outdated_from_pack_outdated(payload: object) -> dict[str, object] | None:
    """Extract ``{version, min_proto_version}`` from an outdated payload."""
    try:
        if not isinstance(payload, dict):
            return None
        version = payload.get("version")
        proto = payload.get("min_proto_version")
        # Inline narrowing (not helper calls) so mypy sees the types:
        # ``type(proto) is int`` rejects bools, unlike isinstance.
        if not isinstance(version, str) or not version:
            return None
        if type(proto) is not int or proto < 0:
            return None
        return {"version": version, "min_proto_version": proto}
    except Exception:
        return None


def record_outdated(version: object, min_proto_version: object) -> bool:
    """Store one outdated signal; evicts oldest past the cap. Never raises."""
    try:
        if not isinstance(version, str) or not version:
            return False
        if type(min_proto_version) is not int or min_proto_version < 0:
            return False
        ver = version
        global _last_version
        with _lock:
            if ver not in _outdated and len(_outdated) >= _MAX_OUTDATED_ENTRIES:
                oldest = next(iter(_outdated))
                del _outdated[oldest]
            _outdated[ver] = {"version": ver, "min_proto_version": min_proto_version}
            _last_version = ver
        return True
    except Exception:
        return False


def get_outdated_info(version: object = None) -> dict[str, object] | None:
    """Latest (or per-version) outdated entry copy; None when clear."""
    try:
        with _lock:
            if version is None:
                if _last_version is None:
                    return None
                entry = _outdated.get(_last_version)
                return dict(entry) if entry is not None else None
            if not isinstance(version, str):
                return None
            entry = _outdated.get(version)
            return dict(entry) if entry is not None else None
    except Exception:
        return None


def is_outdated(version: object = None) -> bool:
    """True when an outdated entry is stored."""
    return get_outdated_info(version) is not None


def clear_outdated(version: object = None) -> None:
    """Clear one version or the whole store. Never raises."""
    try:
        global _last_version
        with _lock:
            if version is None:
                _outdated.clear()
                _last_version = None
                return
            if isinstance(version, str) and version in _outdated:
                del _outdated[version]
            if _last_version == version:
                _last_version = next(reversed(_outdated), None) if _outdated else None
    except Exception:
        log.debug("[PACK] outdated clear failed", exc_info=True)


def clear_on_verified(version: object = None) -> None:
    """Reset signal for a verified pack. Never raises."""
    clear_outdated(version)


def clear_on_download_started(version: object = None) -> None:
    """Reset signal for a fresh download. Never raises."""
    clear_outdated(version)


def reset_for_tests() -> None:
    """Clear all outdated state; no production callers."""
    clear_outdated(None)


def note_pack_outdated(version: object, min_proto_version: object, event_bus: ModuleType | None) -> bool:
    """Record + publish one outdated signal. Never raises."""
    try:
        parsed = outdated_from_pack_outdated({"version": version, "min_proto_version": min_proto_version})
        if parsed is None:
            return False
        record_outdated(parsed["version"], parsed["min_proto_version"])
        _publish_event(event_bus, PACK_OUTDATED_EVENT, dict(parsed))
        log.warning(
            "[PACK] pack %s outdated (min_proto_version=%s)",
            parsed["version"],
            parsed["min_proto_version"],
        )
        return True
    except Exception:
        log.debug("[PACK] outdated note failed", exc_info=True)
        return False


def handle_host_frame(msg: object) -> bool:
    """Validate a host-relayed outdated frame, store + republish it."""
    try:
        if not isinstance(msg, dict):
            log.warning("[PACK] ignoring outdated relay: frame is not an object")
            return False
        data = msg.get("data")
        parsed = outdated_from_pack_outdated(data)
        if parsed is None:
            log.warning("[PACK] ignoring outdated relay: bad data=%r", data)
            return False
        from voice_typer.server import event_bus as _bus

        return note_pack_outdated(parsed["version"], parsed["min_proto_version"], _bus)
    except Exception:
        log.debug("[PACK] outdated relay failed", exc_info=True)
        return False


def get_outdated_count() -> int:
    """Number of stored outdated versions (bounded by the cap)."""
    with _lock:
        return len(_outdated)
