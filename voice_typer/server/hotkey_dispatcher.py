"""#2 HotkeyDispatcher, extracted from LausuApp.

Owns global hotkey registration: dictation toggle hotkey, ESC cancel
hotkey, and repaste hotkey. Each hotkey gets its own HotkeyBackend
instance (Win32 native, pynput, or Wayland), unless an identical spec
is already tracked in ``_shared_backend_pool``, in which case the
existing backend is reused (rare; e.g. two roles bound to the same key).

Previously this concern lived in LausuApp as ~100 LOC across:
    _register_hotkey, _register_esc_hotkey, _unregister_esc_hotkey,
    _register_repaste_hotkey, _restart_hotkey

The bodies live in the split mixins composed below (pool / registration /
dispatch / ptt-safety / lifecycle); this module keeps the class, the
facade-owned state, and the module names tests monkeypatch.

TODO, full per-spec backend pooling (deferred; touches native binary
wire protocol)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The current implementation pools the THREE ROLES (dictation / ESC /
repaste) into a single native subprocess via the ``_shared_backend``
extra-matcher mechanism (see class docstring). It ALSO tracks every
created backend by spec in ``_shared_backend_pool`` so two roles that
happen to share the same spec (rare) reuse the same backend instance.
``get_active_backend_count()`` exposes the size of that pool.

The FULL refactor (deferred because it touches the native binary's
wire protocol) is to extend the binary's command-line surface to
accept a list of ``(role, hotkey_spec)`` pairs (e.g. via a startup
handshake frame) and emit wire events tagged with the originating
role (e.g. ``EVENT role=esc KEY_UP <esc>``). This would let the
binary itself handle suppression for all three specs (eliminating the
macOS / Windows suppression limitation noted in the class docstring)
and would let a SINGLE native binary serve an arbitrary number of
distinct specs, collapsing the per-spec pool to one process even
when the specs differ. The ``_shared_backend_pool`` dict established
here is the Python-side tracking infrastructure that the full
refactor will repurpose: each ``HotkeyBackend`` entry would become a
``(role, spec)`` registration against the single shared binary rather
than a distinct subprocess.

Stepping stones (no wire-protocol change required):
  1. (DONE) Pool the three roles into one subprocess via extra
     matchers on the dictation backend (``_shared_backend``).
  2. (DONE, minimal) Track every created backend by spec in
     ``_shared_backend_pool`` so identical specs reuse a backend.
  3. (DONE) Role-based extra-matcher teardown:
     ``SubprocessHotkeyBackend.remove_extra_matcher(role)`` drops a
     single pooled matcher from the shared subprocess without a
     restart. The dispatcher wraps it as
     :meth:`_remove_shared_extra_matcher` and calls it from every
     disable / teardown path (``unregister_esc``, the ESC / repaste
     disable branches in :meth:`register`, the empty-config branch of
     :meth:`register_repaste`, and the pool-then-start failure paths)
     so a disabled role stops firing while the shared backend stays
     alive. Re-enabling a role re-adds the matcher via
     :meth:`_pool_aux_into_shared` (no matcher leak: ``add`` is
     idempotent on role, ``remove`` is a no-op for an unknown role).
  4. (TODO, wire protocol change) Extend the native binary to accept
     multiple ``(role, spec)`` pairs at startup and emit role-tagged
     events. Replace the extra-matcher shim with direct role dispatch.
     This is the remaining cross-layer work: it touches the native
     binary sources and requires host validation (C-TDEV). Until then
     the macOS / Windows suppression limitation in the class docstring
     stands.
"""

from __future__ import annotations

import concurrent.futures  # noqa: F401  # facade attr: tests patch hotkey_dispatcher.concurrent.futures
import logging
import threading
import weakref
from typing import Any

from voice_typer.server.hotkey_dispatch import HotkeyDispatchMixin
from voice_typer.server.hotkey_lifecycle import HotkeyLifecycleMixin
from voice_typer.server.hotkey_pool import HotkeyPoolMixin
from voice_typer.server.hotkey_ptt_safety import HotkeyPttSafetyMixin
from voice_typer.server.hotkey_registration import HotkeyRegistrationMixin
from voice_typer.server.hotkeys import (  # noqa: F401
    HotkeyBackend,
    create_hotkey_backend,  # patch seam: tests patch this facade attribute
)

log = logging.getLogger(__name__)


# Registry of dispatchers with a live PTT safety timer. Lets the test
_LIVE_PTT_TIMER_DISPATCHERS: weakref.WeakSet = weakref.WeakSet()


# Short human label for a backend, used in the ``Backend created`` /


class HotkeyDispatcher(
    HotkeyPoolMixin, HotkeyRegistrationMixin, HotkeyDispatchMixin, HotkeyPttSafetyMixin, HotkeyLifecycleMixin
):
    """Owns the three global hotkey backends (dictation / ESC / repaste).

    #2 extracted from LausuApp. The app passes itself
    (``app``) so HotkeyDispatcher can:
    - Read ``app.config`` (hotkey, recording_mode, esc_cancel_enabled, repaste_hotkey)
    - Call ``app.toggle_dictation`` / ``app._stop_dictation`` /
      ``app._cancel_dictation`` / ``app.repaste_last`` as hotkey callbacks
    - Call ``app.tray.notify`` on registration failure
    - Call ``app.tray.set_hotkey`` after a hotkey restart

    Architecture note, pooled subprocess (one process for all three roles)
    ----------------------------------------------------------------
    ``register`` creates the dictation backend via
    ``create_hotkey_backend(hotkey, role="dictation")`` and stashes it
    on ``self._shared_backend``. On platforms that select the native
    ``SubprocessHotkeyBackend`` (macOS / Windows / Linux), that backend
    owns the SINGLE native listener process. ``register_esc`` and
    ``register_repaste`` STILL call ``create_hotkey_backend`` (for API
    compatibility with code that asserts ``_esc_backend is mock_backend``)
    but the returned backends are marked ``_delegated=True``, their
    ``start()`` skips spawning a subprocess, and the actual matching for
    ESC / repaste happens via extra matchers on the shared (dictation)
    backend's event stream. The native binary emits ALL keystroke
    events on stdout (it does not filter to the matched spec, the
    Python side does the matching), so one process is sufficient.

    Resource reduction: 1 native binary subprocess instead of 3, 1
    reader thread instead of 3, 1 watchdog thread instead of 3, 1 IPC
    pipe instead of 3, 1 TOCTOU-verify cycle instead of 3. On Linux
    this means 1× opens ``/dev/input/event*`` (was 3×); on Windows 1×
    WH_KEYBOARD_LL hook (was 3×); on macOS 1× CGEventTap + 1× NSEvent
    monitor (was 3× each).

    Known limitation (macOS / Windows suppression): the native binary
    uses argv[1] (the dictation spec) to decide which keystrokes to
    suppress via the CGEventTap (macOS) / WH_KEYBOARD_LL hook
    (Windows). Extra matchers' specs are NOT known to the binary, so
    their keystrokes are NOT suppressed. On Linux this is a non-issue
    (evdev is read-only, no suppression). On macOS / Windows, the
    keystroke for an extra matcher (e.g. ESC, repaste combo) will
    reach the foreground app. This is acceptable for ESC (foreground
    apps handle ESC themselves) but may cause double-paste for repaste
    combos (the foreground app sees the combo AND the Python-side
    repaste fires). A future session can extend the binary's
    command-line surface to accept multiple specs for suppression.

    Fallback: if the shared backend's native doesn't support extra
    matchers (e.g. legacy ``PynputHotkey`` / ``WaylandHotkey`` /
    ``WindowsNativeHotkey`` selected by the factory because the native
    binary is missing), pooling is silently skipped and the per-role
    subprocess model is used (3 subprocesses). This preserves the
    pre-refactor behavior on platforms without the native binary.

    Planned future refactor (deferred, touches native binary wire protocol)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Extend the native binary's command-line surface to accept a list
    of ``(role, hotkey_spec)`` pairs (e.g. via a startup handshake
    frame) and emit wire events tagged with the originating role
    (e.g. ``EVENT role=esc KEY_UP <esc>``). This would let the binary
    itself handle suppression for all three specs (eliminating the
    macOS / Windows suppression limitation above) and simplify the
    Python-side dispatch (role tag on each event instead of running
    every matcher against every event). The current extra-matcher
    approach is the no-wire-protocol-change stepping stone toward
    that goal.
    """

    def __init__(self, app: Any) -> None:
        self._app = app
        self._hotkey_backend: HotkeyBackend | None = None
        self._esc_backend: HotkeyBackend | None = None
        self._repaste_backend: HotkeyBackend | None = None
        # Shared backend handle, the dictation backend, whose native
        self._shared_backend: HotkeyBackend | None = None
        # Per-spec backend pool, tracks every live backend by its
        self._shared_backend_pool: dict[str, HotkeyBackend] = {}
        # Stashed ESC / repaste callbacks so :meth:`_repool_aux_into_shared`
        self._esc_callback: Any = None
        self._repaste_callback: Any = None
        # track the last-registered ESC and repaste specs so
        self._esc_spec: str | None = None
        self._repaste_spec: str | None = None
        # re-entrancy guard for
        self._resyncing_aux = False
        # threading.Event for atomic cross-
        self._esc_pending_capture_exit_event: threading.Event = threading.Event()
        # PTT safety timer. None when not armed (toggle mode,
        self._ptt_safety_timer: threading.Timer | None = None

    # PTT safety timeout. Push-to-talk starts recording on key-down
    _PTT_SAFETY_TIMEOUT_SECONDS: float = 60.0

