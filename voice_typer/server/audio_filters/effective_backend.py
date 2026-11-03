"""Report which denoiser a built chain is ACTUALLY serving (C-UI-15).

Config names the denoiser the user asked for; the chain may be serving a
different one (no onnxruntime, a preload that has not landed, an RTF gate that
refused the model). The UI must never print the requested name as if it were
the running one, so both the dictation and the level-monitor status surfaces
build their ``noise_suppression`` block here.

Only reason CODES reach the renderer: the copy is translated plain language,
while the exception detail stays in the backend log (C-UXERR-1, C-UXERR-3).
"""

from __future__ import annotations

from typing import Any

#: The runtime is missing, still loading, or was refused by a gate.
REASON_BACKEND_UNAVAILABLE = "backend_unavailable"
#: Any other fallback (unknown method, legacy value, init failure).
REASON_FALLBACK = "fallback"

#: Model-backend methods that can be substituted by another denoiser.
_MODEL_METHODS = frozenset({"dpdfnet", "dpdfnet2", "rnnoise", "deepfilternet"})


def _requested_method(processor: Any, requested: str | None) -> str:
    if requested:
        return str(requested)
    config = getattr(processor, "_config", None)
    return str(getattr(config, "noise_suppression_method", "") or "")


def _suppressors(processor: Any) -> list[Any]:
    """Every suppressor in the chain, tolerant of a broken chain object.

    A chain attribute that RAISES (not just an absent one) would otherwise
    take the whole status block down, and a status probe must never fail loudly.
    """
    try:
        chain = getattr(processor, "_chain", None)
        filters = list(chain.filters) if chain is not None else []
    except Exception:
        return []
    return [filter_ for filter_ in filters if hasattr(filter_, "effective_method")]


def effective_noise_suppression(
    processor: Any,
    requested: str | None = None,
    *,
    enabled: bool = True,
) -> dict[str, object]:
    """Describe requested vs effective denoiser for ``processor``.

    ``effective`` is ``"none"`` when nothing in the chain denoises. With
    ``enabled=False`` (the noise filter is off) that is the intended state, not
    a degradation: ``degraded`` stays ``False`` so the UI never reports a
    fallback that did not happen.
    """
    method = _requested_method(processor, requested)
    if not enabled:
        return {
            "enabled": False,
            "requested": method,
            "effective": "none",
            "degraded": False,
            "reason_code": "",
        }
    suppressors = _suppressors(processor)
    effective = str(getattr(suppressors[0], "effective_method", "") or "none") if suppressors else "none"
    degraded = effective != method or any(bool(getattr(item, "is_degraded", False)) for item in suppressors)
    reason = ""
    if effective != method:
        reason = REASON_BACKEND_UNAVAILABLE if method in _MODEL_METHODS else REASON_FALLBACK
    return {
        "enabled": True,
        "requested": method,
        "effective": effective,
        "degraded": degraded,
        "reason_code": reason,
    }


__all__ = [
    "REASON_BACKEND_UNAVAILABLE",
    "REASON_FALLBACK",
    "effective_noise_suppression",
]
