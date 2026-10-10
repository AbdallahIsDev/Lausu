"""Facade contracts of the wave-9 module splits (create-first, no behavior change).

``hotkey_dispatcher`` was split into five mixin modules (pool / registration /
dispatch / ptt-safety / lifecycle) composed into ``HotkeyDispatcher``. Three
contracts must hold:

1. every moved method resolves to the SAME function object as its owning
   mixin (composition, not delegation), so ``inspect.getsource``-based pins
   read the real body;
2. the runtime lookups tests monkeypatch ON the facade
   (``hotkey_dispatcher.create_hotkey_backend``, the PTT safety registry,
   ``concurrent.futures``) are read at call time by the mixin code;
3. the public method surface of ``HotkeyDispatcher`` is exactly the surface
   the facade had before the split (nothing dropped, nothing invented).

Logger names must stay ``voice_typer.server.hotkey_dispatcher`` everywhere
(C-LOG-1).

The same create-first contract covers the ``worker/_ws_server.py`` split
(frame-IO / samples / startup / shutdown siblings, plus the command
handlers in ``_ws_commands``): every moved name resolves to the SAME
object as its owning sibling, the accept seam (:func:`run_worker_server`)
stays on the facade, and the one global tests monkeypatch on the facade
(``transcribe_window_words``) is read at call time by the frame-IO
sibling through a lazy facade proxy.
"""

from __future__ import annotations

import concurrent.futures

import pytest

MIXIN_MODULES = [
    "voice_typer.server.hotkey_pool",
    "voice_typer.server.hotkey_registration",
    "voice_typer.server.hotkey_dispatch",
    "voice_typer.server.hotkey_ptt_safety",
    "voice_typer.server.hotkey_lifecycle",
]

# The facade class surface captured from the pre-split definition
# (HEAD: voice_typer/server/hotkey_dispatcher.py): 24 methods + the PTT
# timeout class constant.
EXPECTED_SURFACE = {
    "register",
    "_create_and_start_main_backend",
    "_track_pooled_backend",
    "_untrack_pooled_backend",
    "get_active_backend_count",
    "_native_of",
    "_shared_native",
    "_pool_aux_into_shared",
    "_repool_aux_into_shared",
    "_remove_shared_extra_matcher",
    "_handle_shared_native_state_changed",
    "_maybe_warn_wayland_caps_lock",
    "_start_ptt_safety_timer",
    "_cancel_ptt_safety_timer",
    "_on_ptt_safety_timeout",
    "_make_dictation_callback",
    "_make_repaste_callback",
    "register_esc",
    "_on_esc_release",
    "unregister_esc",
    "register_repaste",
    "restart",
    "stop_all",
    "_stop_one_backend",
    "_PTT_SAFETY_TIMEOUT_SECONDS",
}

# mixin module -> methods it owns (moved verbatim from the facade class)
OWNED: dict[str, set[str]] = {
    "voice_typer.server.hotkey_pool": {
        "_native_of",
        "_shared_native",
        "_pool_aux_into_shared",
        "_repool_aux_into_shared",
        "_remove_shared_extra_matcher",
        "_handle_shared_native_state_changed",
        "_maybe_warn_wayland_caps_lock",
        "_track_pooled_backend",
        "_untrack_pooled_backend",
        "get_active_backend_count",
    },
    "voice_typer.server.hotkey_registration": {
        "register",
        "_create_and_start_main_backend",
        "register_esc",
        "unregister_esc",
        "register_repaste",
    },
    "voice_typer.server.hotkey_ptt_safety": {
        "_start_ptt_safety_timer",
        "_cancel_ptt_safety_timer",
        "_on_ptt_safety_timeout",
    },
    "voice_typer.server.hotkey_dispatch": {
        "_make_dictation_callback",
        "_make_repaste_callback",
        "_on_esc_release",
    },
    "voice_typer.server.hotkey_lifecycle": {
        "restart",
        "stop_all",
        "_stop_one_backend",
    },
}


class TestHotkeyMixinComposition:
    """The facade class IS the composed mixins (no delegator indirection)."""

    def test_all_five_mixin_bases_are_composed(self):
        from voice_typer.server.hotkey_dispatch import HotkeyDispatchMixin
        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher
        from voice_typer.server.hotkey_lifecycle import HotkeyLifecycleMixin
        from voice_typer.server.hotkey_pool import HotkeyPoolMixin
        from voice_typer.server.hotkey_ptt_safety import HotkeyPttSafetyMixin
        from voice_typer.server.hotkey_registration import HotkeyRegistrationMixin

        for base in (
            HotkeyPoolMixin,
            HotkeyRegistrationMixin,
            HotkeyDispatchMixin,
            HotkeyPttSafetyMixin,
            HotkeyLifecycleMixin,
        ):
            assert base in HotkeyDispatcher.__mro__, base.__name__

    @pytest.mark.parametrize("module_path,owned", sorted(OWNED.items()))
    def test_each_method_is_the_mixin_function_itself(
        self, module_path: str, owned: set[str]
    ):
        import importlib

        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher

        mixin_mod = importlib.import_module(module_path)
        mixin_cls = next(
            v
            for k, v in vars(mixin_mod).items()
            if isinstance(v, type) and k.endswith("Mixin")
        )
        for name in owned:
            assert getattr(HotkeyDispatcher, name) is getattr(mixin_cls, name), (
                f"{module_path}.{name} must be the same function object "
                f"the facade resolves to"
            )

    def test_surface_matches_the_presplit_class(self):
        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher

        surface = {n for n in dir(HotkeyDispatcher) if not n.startswith("__")}
        assert surface == EXPECTED_SURFACE, (
            f"missing: {sorted(EXPECTED_SURFACE - surface)}; "
            f"unexpected: {sorted(surface - EXPECTED_SURFACE)}"
        )

    def test_module_level_state_stays_on_the_facade(self):
        from voice_typer.server import hotkey_dispatcher as hd

        assert hd.log.name == "voice_typer.server.hotkey_dispatcher"
        for module_path in MIXIN_MODULES:
            mod = __import__(module_path, fromlist=["x"])
            assert mod.log.name == "voice_typer.server.hotkey_dispatcher"
        assert hasattr(hd, "_LIVE_PTT_TIMER_DISPATCHERS")
        from voice_typer.server import hotkey_registration as hr

        # module-level helpers moved with the leaf and keep one logger/namespace
        assert hr._backend_kind_label.__module__.endswith("hotkey_registration")
        assert isinstance(hr._BACKEND_KIND_LABELS, dict)

    def test_ptt_timeout_constant_is_declared_on_the_mixin_and_valued_on_the_class(self):
        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher
        from voice_typer.server.hotkey_ptt_safety import HotkeyPttSafetyMixin

        assert "_PTT_SAFETY_TIMEOUT_SECONDS" in HotkeyPttSafetyMixin.__annotations__
        assert HotkeyDispatcher._PTT_SAFETY_TIMEOUT_SECONDS == 60.0


class TestHotkeyFacadePatchSeams:
    """Names tests monkeypatch on the facade are read at call time."""

    def test_create_hotkey_backend_seam_resolves_through_the_facade(
        self, monkeypatch
    ):
        from voice_typer.server import hotkey_dispatcher as hd, hotkey_registration as hr

        sentinel = object()
        monkeypatch.setattr(hd, "create_hotkey_backend", sentinel, raising=False)
        # the registration mixin resolves the seam lazily through the facade,
        # so a facade-level patch is what the call site sees
        assert hr._facade().create_hotkey_backend is sentinel

    def test_ptt_registry_is_read_off_the_facade_at_call_time(self, monkeypatch):
        from voice_typer.server import hotkey_dispatcher as hd
        from voice_typer.server.hotkey_ptt_safety import HotkeyPttSafetyMixin

        registry: set[object] = set()
        monkeypatch.setattr(hd, "_LIVE_PTT_TIMER_DISPATCHERS", registry)

        class _FakeDispatcher:
            _ptt_safety_timer = None

        fake = _FakeDispatcher()
        registry.add(fake)
        assert hd._LIVE_PTT_TIMER_DISPATCHERS is registry

        HotkeyPttSafetyMixin._cancel_ptt_safety_timer(fake)
        assert fake not in registry, (
            "the ptt mixin must discard from the facade registry"
        )

    def test_concurrent_futures_patch_reaches_the_lifecycle_leaf(self, monkeypatch):
        import voice_typer.server.hotkey_lifecycle as hl
        from voice_typer.server import hotkey_dispatcher as hd

        # both modules bind the SAME stdlib module object, so a patch through
        # the facade namespace is visible to the leaf's call sites
        assert hd.concurrent.futures is concurrent.futures
        assert hl.concurrent.futures is concurrent.futures

        sentinel = object()
        monkeypatch.setattr(hd.concurrent.futures, "wait", sentinel)
        assert concurrent.futures.wait is sentinel
        assert hl.concurrent.futures.wait is sentinel


class TestHotkeyGetSourcePinsStillReadRealBodies:
    """inspect.getsource-based regression pins keep pointing at real code."""

    def test_ptt_wiring_strings_live_in_the_composed_methods(self):
        import inspect

        from voice_typer.server.hotkey_dispatcher import HotkeyDispatcher

        combined = inspect.getsource(
            HotkeyDispatcher.register
        ) + inspect.getsource(HotkeyDispatcher._create_and_start_main_backend)
        assert "set_on_release" in combined
        assert "push_to_talk" in combined
        assert "_stop_dictation" in combined


# ---------------------------------------------------------------------------
# ``service/model/_downloads.py`` -> four concern mixins + composite
# (preflight / queue / dispatch / qwen-parakeet; ``_download_whisper_family``
# stays pinned to the composite file by the segmented-download source pins).
# ---------------------------------------------------------------------------

DOWNLOAD_GROUP_OWNERS = {
    "voice_typer.server.service.model._download_preflight": (
        "DownloadPreflightMixin",
        {"test_llm_connection", "_require_huggingface_consent"},
    ),
    "voice_typer.server.service.model._download_queue": (
        "DownloadQueueMixin",
        {
            "cancel_model_download",
            "get_download_queue",
            "_enqueue_download",
            "_remove_queued_download",
            "_push_queue_positions",
            "_is_active_download_model",
            "_start_next_queued_download",
            "_queued_download_runner",
            "pause_model_download",
            "resume_model_download",
        },
    ),
    "voice_typer.server.service.model._download_dispatch": (
        "DownloadDispatchMixin",
        {"download_model"},
    ),
    "voice_typer.server.service.model._download_qwen_parakeet": (
        "QwenParakeetDownloadMixin",
        {"_download_qwen", "_download_parakeet"},
    ),
}

EXPECTED_DOWNLOAD_SURFACE = set().union(
    *(owned for _, owned in DOWNLOAD_GROUP_OWNERS.values()))
EXPECTED_DOWNLOAD_SURFACE.add("_download_whisper_family")


class TestDownloadsComposite:
    """``DownloadsMixin`` composes the concern mixins; no seam to patch here
    (STEP 0: zero ``setattr``/``patch`` targets reference this module)."""

    @pytest.mark.parametrize("module_path,pair", sorted(DOWNLOAD_GROUP_OWNERS.items()))
    def test_methods_resolve_to_the_owning_mixin(self, module_path: str, pair):
        import importlib

        from voice_typer.server.service.model import ModelMixin

        cls_name, owned = pair
        mixin_cls = getattr(importlib.import_module(module_path), cls_name)
        for name in owned:
            assert getattr(ModelMixin, name) is getattr(mixin_cls, name)

    def test_whisper_family_stays_on_the_composite(self):
        from voice_typer.server.service.model import ModelMixin
        from voice_typer.server.service.model._downloads import DownloadsMixin

        assert ModelMixin._download_whisper_family is DownloadsMixin._download_whisper_family

    def test_surface_matches_the_presplit_mixin(self):
        from voice_typer.server.service.model import ModelMixin
        from voice_typer.server.service.model._downloads import DownloadsMixin

        surface = {n for n in dir(DownloadsMixin) if not n.startswith("__")}
        assert surface == EXPECTED_DOWNLOAD_SURFACE, (
            f"missing: {sorted(EXPECTED_DOWNLOAD_SURFACE - surface)}; "
            f"unexpected: {sorted(surface - EXPECTED_DOWNLOAD_SURFACE)}"
        )
        # the same surface must be reachable on the assembled facade class
        assert {n for n in dir(ModelMixin) if not n.startswith("__")} >= EXPECTED_DOWNLOAD_SURFACE

    def test_source_text_pins_keep_their_anchors(self):
        """The segmented-download pins read ``_downloads.py`` as text."""
        from pathlib import Path

        src = (
            Path(__file__).resolve().parent.parent
            / "voice_typer"
            / "server"
            / "service"
            / "model"
            / "_downloads.py"
        ).read_text(encoding="utf-8")
        assert "poll_outcome, last_total_bytes_seen = poll_download_progress(" in src
        assert src.count("clear_download_pause_state()") >= 4

    def test_download_model_dispatch_still_delegates_to_three_branches(self):
        import inspect

        from voice_typer.server.service.model import ModelMixin

        src = inspect.getsource(ModelMixin.download_model)
        assert "_download_whisper_family" in src
        assert "_download_qwen" in src
        assert "_download_parakeet" in src


# ---------------------------------------------------------------------------
# ``worker/_ws_server.py`` -> frame-IO (``_ws_connection``) + samples
# (``_ws_samples``) + startup (``_ws_startup``) + shutdown
# (``_ws_shutdown``) siblings, with the offline/samples/abort command
# bodies in ``_ws_commands``. The facade keeps the accept seam
# (``run_worker_server``), the module names and the one monkeypatch seam.
# ---------------------------------------------------------------------------

# sibling module -> the moved names it owns (the facade re-exports them)
WS_SERVER_OWNERS: dict[str, tuple[str, ...]] = {
    "voice_typer.worker._ws_connection": ("_handle_connection",),
    "voice_typer.worker._ws_samples": ("_SamplesBuffer", "_valid_samples_header"),
    "voice_typer.worker._ws_shutdown": ("_ShutdownTimer", "_install_sigterm_handler"),
    "voice_typer.worker._ws_startup": (
        "_emit_worker_started",
        "_force_line_buffered_stdout",
        "_run_prewarm_phase",
    ),
}

# Every sibling that logs must carry the facade's logger namespace.
WS_SERVER_LOGGING_SIBLINGS = (
    "voice_typer.worker._ws_connection",
    "voice_typer.worker._ws_commands",
    "voice_typer.worker._ws_shutdown",
    "voice_typer.worker._ws_startup",
)


class TestWorkerWsServerFacade:
    """The facade re-exports the moved bodies (same object, no wrapper)."""

    @pytest.mark.parametrize("module_path,names", sorted(WS_SERVER_OWNERS.items()))
    def test_moved_names_resolve_to_the_sibling_object(self, module_path: str, names: tuple[str, ...]):
        import importlib

        from voice_typer.worker import _ws_server

        sibling = importlib.import_module(module_path)
        for name in names:
            assert getattr(_ws_server, name) is getattr(sibling, name), (
                f"{module_path}.{name} must be the same object the facade resolves to"
            )

    def test_frame_cap_and_protocol_survive_on_the_facade(self):
        from voice_typer.server.ipc.protocol_version import (
            MAX_WS_FRAME_BYTES,
            PROTOCOL_VERSION,
        )
        from voice_typer.worker import _ws_server

        assert _ws_server._MAX_FRAME_BYTES == MAX_WS_FRAME_BYTES == 1 * 1024 * 1024
        assert _ws_server.PROTOCOL_VERSION is PROTOCOL_VERSION

    def test_accept_seam_stays_on_the_facade(self):
        from voice_typer.worker import _ws_server

        assert hasattr(_ws_server, "run_worker_server")
        assert _ws_server.run_worker_server.__module__ == "voice_typer.worker._ws_server"

    def test_logger_names_stay_the_facade_namespace(self):
        from voice_typer.worker import _ws_server

        assert _ws_server.log.name == "voice_typer.worker"
        for module_path in WS_SERVER_LOGGING_SIBLINGS:
            mod = __import__(module_path, fromlist=["x"])
            assert mod.log.name == "voice_typer.worker"


class TestWorkerWsServerPatchSeams:
    """Names tests monkeypatch ON the facade are read at call time.

    STEP-0 grep: ``transcribe_window_words`` is the ONLY global patched on
    ``voice_typer.worker._ws_server`` (``tests/test_worker_streaming.py``
    patches it for the push/finalize windows); the other facade names are
    read-only (``_MAX_FRAME_BYTES``, ``_SamplesBuffer``,
    ``_valid_samples_header``, ``_ShutdownTimer``, ``_handle_connection``).
    """

    def test_transcribe_window_words_patch_on_the_facade_reaches_the_frame_io(self, monkeypatch):
        from voice_typer.worker import _ws_connection, _ws_server

        sentinel = object()
        monkeypatch.setattr(_ws_server, "transcribe_window_words", sentinel, raising=False)
        # the frame-IO sibling resolves the seam lazily through the facade,
        # so a facade-level patch is what the streaming call sites see
        assert _ws_connection._facade.transcribe_window_words is sentinel

