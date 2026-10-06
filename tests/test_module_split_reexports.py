"""Facade re-exports of the split server modules keep resolving.

``event_bus``, ``vocabulary``, ``text_cleanup._engine``,
``clipboard_snapshot`` and ``segmented_download`` were split into focused
sibling modules. Callers (and tests) import names from the facades, so
two contracts must hold:

1. every moved symbol is re-exported by the facade as the SAME object as
   in its owning sibling module;
2. the runtime lookups that tests monkeypatch ON the facade
   (``segmented_download.MAX_REDIRECTS`` / ``RETRY_BACKOFF_S`` /
   ``_is_transient_http``, ``vocabulary.MAX_CORRECTIONS_ENTRIES``,
   ``text_cleanup._engine`` state, ``clipboard_snapshot.log``) are still
   read at call time by the sibling code.
"""

from __future__ import annotations

import pytest


class TestEventBusFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server import event_bus, event_bus_delivery, event_bus_subscribers

        assert event_bus._SubscriberSet is event_bus_subscribers._SubscriberSet
        assert event_bus._subscriber_key is event_bus_subscribers._subscriber_key
        assert event_bus._deliver is event_bus_delivery._deliver
        assert event_bus._deliver_deferred is event_bus_delivery._deliver_deferred
        assert event_bus._get_deferred_executor is event_bus_delivery._get_deferred_executor
        assert event_bus.shutdown is event_bus_delivery.shutdown

    def test_mutable_state_stays_on_the_facade(self):
        from voice_typer.server import event_bus, event_bus_delivery

        # ``subscribe``/``publish`` read these facade globals, and tests
        # rebind ``_lock`` / ``_subscribers`` / ``_transport_probes`` here.
        assert isinstance(event_bus._subscribers, event_bus._SubscriberSet)
        assert isinstance(event_bus._transport_probes, list)
        assert event_bus.subscribe.__module__ == "voice_typer.server.event_bus"
        assert event_bus.publish.__module__ == "voice_typer.server.event_bus"
        assert event_bus._subscriber_count.__module__ == "voice_typer.server.event_bus"
        # ``shutdown`` is re-exported but still a callable lifecycle hook.
        assert callable(event_bus_delivery.shutdown)


class TestTextCleanupEngineReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server.text_cleanup import _engine, _punctuation, _spacing, _token_rules

        assert _engine._normalize_spacing is _spacing._normalize_spacing
        assert _engine._RE_SPACING_PUNCT_BEFORE is _spacing._RE_SPACING_PUNCT_BEFORE
        assert _engine._token_key is _token_rules._token_key
        assert _engine._clean_self_corrections_tokens is _token_rules._clean_self_corrections_tokens
        assert _engine._remove_near_duplicate_words_tokens is _token_rules._remove_near_duplicate_words_tokens
        assert _engine._add_safe_terminal_punctuation is _punctuation._add_safe_terminal_punctuation
        assert _engine._looks_like_question is _punctuation._looks_like_question

    def test_active_state_and_caches_stay_on_the_engine(self):
        from voice_typer.server.text_cleanup import _engine

        saved = (_engine._active_phrases, _engine._phrases_re_cache)
        try:
            _engine._active_phrases = [("zz-phrase-alpha", "Z")]
            _engine._phrases_re_cache = (None, None, {})
            pattern, lookup = _engine._get_phrases_regex()
            assert pattern is not None
            assert lookup == {"zz-phrase-alpha": "Z"}
        finally:
            _engine._active_phrases, _engine._phrases_re_cache = saved


class TestClipboardSnapshotFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server import (
            clipboard_snapshot,
            clipboard_snapshot_formats,
            clipboard_snapshot_linux,
            clipboard_snapshot_macos,
            clipboard_snapshot_win32,
        )

        assert clipboard_snapshot._builtin_format_name is clipboard_snapshot_formats._builtin_format_name
        assert clipboard_snapshot._BUILTIN_FORMAT_NAMES is clipboard_snapshot_formats._BUILTIN_FORMAT_NAMES
        assert clipboard_snapshot._MAX_FORMAT_BYTES == clipboard_snapshot_formats._MAX_FORMAT_BYTES
        assert clipboard_snapshot._NON_RESTORABLE_FORMATS is clipboard_snapshot_formats._NON_RESTORABLE_FORMATS

        snapshot = clipboard_snapshot.ClipboardSnapshot
        win32 = clipboard_snapshot_win32.WindowsClipboardMixin
        macos = clipboard_snapshot_macos.MacosClipboardMixin
        linux = clipboard_snapshot_linux.LinuxClipboardMixin
        assert snapshot._capture_windows.__func__ is win32._capture_windows.__func__
        assert snapshot._restore_windows is win32._restore_windows
        assert snapshot._capture_macos.__func__ is macos._capture_macos.__func__
        assert snapshot._restore_macos is macos._restore_macos
        assert snapshot._restore_x11 is linux._restore_x11
        assert snapshot._restore_wayland is linux._restore_wayland

    def test_restore_lock_stays_module_level(self):
        from voice_typer.server import clipboard_snapshot

        assert hasattr(clipboard_snapshot._restore_lock, "acquire")


class TestSegmentedDownloadFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server import (
            segmented_download,
            segmented_download_base,
            segmented_download_fetch,
            segmented_download_files,
            segmented_download_http,
            segmented_download_state,
        )

        assert segmented_download.SegmentedDownloadError is segmented_download_base.SegmentedDownloadError
        assert segmented_download.SegmentRange is segmented_download_base.SegmentRange
        assert segmented_download.plan_segments is segmented_download_base.plan_segments
        assert segmented_download.resolve_download is segmented_download_http.resolve_download
        assert segmented_download._is_transient_http is segmented_download_http._is_transient_http
        assert segmented_download.write_state is segmented_download_state.write_state
        assert segmented_download.read_state is segmented_download_state.read_state
        assert segmented_download._fetch_segment is segmented_download_fetch._fetch_segment
        assert segmented_download.download_file_segmented is segmented_download_fetch.download_file_segmented
        assert segmented_download.install_blob_into_hf_cache is segmented_download_files.install_blob_into_hf_cache
        assert segmented_download.run_segmented_phase is segmented_download_files.run_segmented_phase

    def test_max_redirects_patch_on_facade_is_honoured(self, monkeypatch):
        from voice_typer.server import segmented_download as seg

        class _Resp:
            status = 302

            def getheader(self, name, default=None):
                return "https://example.test/next" if name == "Location" else default

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class _Opener:
            def __init__(self):
                self.requests = []

            def open(self, req, timeout=None):
                self.requests.append(req)
                return _Resp()

        opener = _Opener()
        monkeypatch.setattr(seg, "MAX_REDIRECTS", 0)
        with pytest.raises(seg.SegmentedDownloadError, match="too many redirects"):
            seg.resolve_download("https://example.test/start", opener_factory=lambda: opener)
        # Unpatched (MAX_REDIRECTS=5) this would take 6 HEAD requests.
        assert len(opener.requests) == 1

    def test_transient_status_patch_on_facade_is_honoured(self, monkeypatch, tmp_path):
        from voice_typer.server import segmented_download as seg
        from voice_typer.server.segmented_download_base import SegmentRange

        calls = {"n": 0}

        def spy(_status: int) -> bool:
            calls["n"] += 1
            return True

        class _Resp:
            status = 503

            def getheader(self, name, default=None):
                return default

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        class _Opener:
            def open(self, req, timeout=None):
                return _Resp()

        monkeypatch.setattr(seg, "_is_transient_http", spy)
        monkeypatch.setattr(seg, "RETRY_BACKOFF_S", (0.0,))
        with pytest.raises(seg.SegmentedDownloadError, match="failed after 3 attempts"):
            seg._fetch_segment(
                opener=_Opener(),
                url="https://example.test/file",
                seg=SegmentRange(index=0, start=0, end=9),
                part_path=tmp_path / "part0",
                headers={},
                timeout_s=1.0,
                gate_check=None,
                on_bytes=lambda _n: None,
            )
        assert calls["n"] == 3


class TestVocabularyFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server import vocabulary, vocabulary_apply, vocabulary_constants, vocabulary_persistence

        assert vocabulary.CATEGORIES is vocabulary_constants.CATEGORIES
        assert vocabulary.BUNDLED_CORRECTIONS_PATH is vocabulary_constants.BUNDLED_CORRECTIONS_PATH
        assert vocabulary.VOCAB_FILENAME == vocabulary_constants.VOCAB_FILENAME
        assert vocabulary.VocabularyManager._save_user is vocabulary_persistence.VocabularyPersistenceMixin._save_user
        assert vocabulary.VocabularyManager.apply_to_text is vocabulary_apply.VocabularyApplyMixin.apply_to_text
        assert (
            vocabulary.VocabularyManager._get_combined_phrase_pattern
            is vocabulary_apply.VocabularyApplyMixin._get_combined_phrase_pattern
        )

    def test_entry_limit_patch_on_facade_is_honoured(self, monkeypatch, tmp_path):
        from voice_typer.server import vocabulary as vocab_mod

        monkeypatch.setattr(vocab_mod, "MAX_CORRECTIONS_ENTRIES", 1)
        manager = vocab_mod.VocabularyManager(config_dir=tmp_path, bundled_path=tmp_path / "missing-bundled.json")
        assert manager.add_entry("misspellings", "teh", "the") is True
        assert manager.add_entry("misspellings", "recieve", "receive") is False
