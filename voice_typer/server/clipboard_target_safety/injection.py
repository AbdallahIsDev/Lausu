"""UIA singleton + focused-element fetching (clipboard injection infrastructure)."""

from __future__ import annotations

import atexit
import contextlib
import ctypes
from typing import Any, cast

# Call-time _pkg lookups (C-ARCH-2).
import voice_typer.server._com as _com
import voice_typer.server.clipboard_target_safety as _pkg


def _ensure_com_initialized() -> None:
    """Enter a COM apartment on this thread, once, and never leave it.

    Thin alias for :func:`voice_typer.server._com.ensure_com_initialized`, kept
    because every clipboard call site resolves it through the package. The
    apartment is never torn down: ``CoUninitialize()`` invalidates every proxy
    in it, and our UIA wrappers outlive the call by design (a ``LogRecord``'s
    ``exc_info`` traceback pins the frame that holds one), so the eventual
    ``comtypes`` ``__del__`` would call ``Release()`` through freed memory.
    """
    _com.ensure_com_initialized()


def _release_uia_pointer(obj: Any) -> None:
    """Release a UIA interface pointer *while its COM apartment is still up*.

    comtypes releases the COM refcount from ``_compointer_base.__del__``, which
    is too late for us: the wrapper can outlive the call that fetched it (a
    ``LogRecord``'s ``exc_info`` traceback pins the frame that holds it), so the
    finaliser runs at an arbitrary later point, on someone else's stack. Doing
    it here — while we know the apartment is up — keeps that ordering under our
    control. comtypes only guards the finaliser with ``_com_shutting_down``,
    which it sets at *atexit*.

    The apartment itself is never torn down (see
    ``_ensure_com_initialized``), so a late ``Release()`` is safe as long as it
    happens exactly once; that is what the pointer-clearing below guarantees.

    So: release here, then clear the raw pointer. ``__del__`` guards on
    truthiness, so clearing it turns the finaliser into a no-op instead of a
    second ``Release()``.

    Test doubles have no ``c_void_p`` value to clear; the explicit ``Release()``
    is then all that happens, which is exactly what they assert on.
    """
    if obj is None:
        return
    with contextlib.suppress(Exception):
        obj.Release()
    with contextlib.suppress(Exception):
        # ``_compointer_base`` re-declares ``value`` as a read-only property, so
        # this has to go through the base descriptor. ``cast`` keeps mypy out of
        # the "generic instance variable via class" hole.
        cast(Any, ctypes.c_void_p).value.__set__(obj, None)


def _release_uia_resources_at_exit() -> None:
    """Release the cached UIA COM references before interpreter teardown."""
    # Narrow suppression only: the assignments cannot raise in
    with contextlib.suppress(AttributeError):
        _pkg._UIA_SINGLETON = None
    with contextlib.suppress(AttributeError):
        _pkg._UIA_MODULE = None


atexit.register(_release_uia_resources_at_exit)


def _get_uia_singleton():
    """Return the cached IUIAutomation instance, or None if unavailable."""
    # Fast path: init already completed, no lock needed.
    if _pkg._UIA_SINGLETON_INIT_ATTEMPTED:
        return _pkg._UIA_SINGLETON
    # Cold path: acquire the lock and re-check (another thread may
    with _pkg._UIA_SINGLETON_LOCK:
        if _pkg._UIA_SINGLETON_INIT_ATTEMPTED:
            return _pkg._UIA_SINGLETON
        try:
            if not _pkg.is_windows():
                return None
            try:
                import comtypes.client

                _pkg._UIA_MODULE = comtypes.client.GetModule("UIAutomationCore.dll")
                _pkg._UIA_SINGLETON = comtypes.CoCreateInstance(
                    _pkg._UIA_MODULE.CUIAutomation._reg_clsid_,
                    interface=_pkg._UIA_MODULE.IUIAutomation,
                )
            except Exception as exc:
                _pkg._log().debug(
                    "[CLIPBOARD] IUIAutomation singleton init failed: %s. UIA checks disabled",
                    exc,
                )
                _pkg._UIA_SINGLETON = None
            return _pkg._UIA_SINGLETON
        finally:
            # Set the flag LAST so racing fast-path readers never see
            _pkg._UIA_SINGLETON_INIT_ATTEMPTED = True


class UiaUnavailableError(RuntimeError):
    """Raised when UI Automation cannot answer at all.

    Distinguishes "the accessibility API could not tell us" from "no element
    is focused" (which is a plain ``None`` return). Callers that use the
    answer as a SECURITY decision must treat this as \"unknown\" and fail
    closed; a swallowed failure here used to look exactly like "not a
    password field".
    """


def _get_uia_focused_element():
    """Return the focused UI element, or ``None`` when none is focused.

    Raises :class:`UiaUnavailableError` when UIA itself is unavailable or the
    query failed (see the class docstring for the security contract).
    """
    uia = _pkg._get_uia_singleton()
    if uia is None:
        raise UiaUnavailableError("IUIAutomation singleton unavailable")
    try:
        return uia.GetFocusedElement()
    except Exception as exc:
        raise UiaUnavailableError(f"GetFocusedElement failed: {exc}") from exc
