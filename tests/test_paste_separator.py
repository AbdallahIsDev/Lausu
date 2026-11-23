"""Delivery formatting for a paste: separator space + first-letter case.

Behaviour pinned here (delivery only, never the stored transcription):

* field empty at the caret        -> capital first letter, no space
* text ends with whitespace       -> lowercase first letter, no extra space
* text reaches the caret unspaced -> lowercase first letter, one leading space
* unknown / unreadable            -> text untouched, no space
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call

import pytest
from voice_typer.server.clipboard.fingerprint import text_fingerprint
from voice_typer.server.clipboard.manager._errors import ClipboardCopyError
from voice_typer.server.clipboard_target_safety import caret_text
from voice_typer.server.clipboard_target_safety.caret_text import (
    _tail_needs_separator,
    delivery_text_for_target,
)
from voice_typer.server.dictation_pipeline.paste_step import _PasteStepMixin


@pytest.fixture()
def caret(monkeypatch):
    """Control the character/field text that precedes the caret."""

    def _set(value: str | None) -> None:
        monkeypatch.setattr(caret_text, "_char_before_caret", lambda: value)

    return _set


class TestTailDecision:
    @pytest.mark.parametrize(
        ("before", "expected"),
        [
            (None, False),
            ("", False),
            ("already spaced ", False),
            ("newline\n", False),
            ("tab\t", False),
            ("word", True),
            ("punctuation.", True),
            ("word ", False),
        ],
    )
    def test_tail_needs_separator(self, before, expected):
        assert _tail_needs_separator(before) is expected

    def test_pasted_text_gets_one_space(self, caret):
        caret("previous sentence")
        assert delivery_text_for_target("dictated words") == " dictated words"

    def test_empty_field_pastes_as_is(self, caret):
        caret("")
        assert delivery_text_for_target("dictated words") == "Dictated words"

    def test_unknown_context_pastes_as_is(self, caret):
        caret(None)
        assert delivery_text_for_target("dictated words") == "dictated words"

    def test_trailing_space_pastes_as_is(self, caret):
        caret("already spaced ")
        assert delivery_text_for_target("dictated words") == "dictated words"

    def test_text_starting_with_whitespace_is_not_doubled(self, caret):
        caret("previous sentence")
        assert delivery_text_for_target("  dictated") == "  dictated"


class TestWindowsCaretClassification:
    """Strict UIA fakes: every COM method has the REAL arity.

    A two-argument CompareEndpoints call raises here (and fails the test),
    unlike a MagicMock which silently accepts any call shape.
    """

    @staticmethod
    def _range(*, moved, text, comparison=-1, text_error=False, block_text=None,
               prefix_text=None, block_text_by_unit=None, expand_error_unit=None,
               document_range=None, doc_comparison=0):
        state = {"compare_calls": [], "expand_calls": [], "move_range_calls": []}

        def clone():
            return proxy

        def move(endpoint, unit, count):
            state["move_args"] = (endpoint, unit, count)
            return moved

        def get_text(max_count):
            if text_error:
                raise RuntimeError("unreadable caret text")
            if max_count == -1:
                if block_text_by_unit is not None:
                    return block_text_by_unit.get(state.get("current_unit"), block_text or text)
                return block_text if block_text is not None else text
            if max_count == caret_text._PREFIX_LIMIT and prefix_text is not None:
                return prefix_text
            return text

        def compare(endpoint, target_range, target_endpoint):
            state["compare_calls"].append((endpoint, target_range, target_endpoint))
            if document_range is not None and target_range is document_range:
                return doc_comparison
            return comparison

        def expand(unit):
            state["expand_calls"].append(unit)
            state["current_unit"] = unit
            if unit == expand_error_unit:
                raise RuntimeError("unit unsupported")

        def move_endpoint_by_range(endpoint, target_range, target_endpoint):
            state["move_range_calls"].append((endpoint, target_range, target_endpoint))

        proxy = SimpleNamespace()
        for name, fn in (
            ("Clone", clone),
            ("MoveEndpointByUnit", move),
            ("GetText", get_text),
            # Each COM method keeps its REAL arity: ExpandToEnclosingUnit(unit)=1,
            # MoveEndpointByRange(endpoint, range, endpoint)=3, CompareEndpoints=3.
            ("ExpandToEnclosingUnit", expand),
            ("MoveEndpointByRange", move_endpoint_by_range),
            ("CompareEndpoints", Mock(wraps=compare)),
        ):
            object.__setattr__(proxy, name, fn)
        proxy.state = state
        return proxy

    def _patch_windows(self, monkeypatch, *, caret_range, value=None, log=None, document_range=None):
        monkeypatch.setattr(caret_text._pkg, "is_windows", lambda: True)
        monkeypatch.setattr(caret_text._pkg, "_ensure_com_initialized", lambda: None)
        monkeypatch.setattr(caret_text._pkg, "_get_uia_focused_element", lambda: object())
        monkeypatch.setattr(caret_text._pkg, "_release_uia_pointer", lambda *_: None)
        if log is not None:
            monkeypatch.setattr(caret_text._pkg, "_log", lambda: log)

        def get_selection():
            holder = SimpleNamespace(Length=1)
            holder.GetElement = lambda _i: caret_range
            return holder

        def query_text(_iface):
            pattern = SimpleNamespace()
            pattern.GetSelection = get_selection
            if document_range is not None:
                pattern.DocumentRange = document_range
            return pattern

        def query_value(_iface):
            return SimpleNamespace(CurrentValue=value)

        def get_current_pattern(pattern_id):
            ptr = SimpleNamespace()
            if pattern_id == caret_text._UIA_TEXT_PATTERN_ID:
                ptr.QueryInterface = query_text
                return ptr
            if pattern_id == caret_text._UIA_VALUE_PATTERN_ID and value is not None:
                ptr.QueryInterface = query_value
                return ptr
            return None

        focused = SimpleNamespace()
        focused.GetCurrentPattern = get_current_pattern
        module = SimpleNamespace(
            IUIAutomationTextPattern=object(), IUIAutomationValuePattern=object()
        )
        monkeypatch.setattr(caret_text._pkg, "_UIA_MODULE", module)
        return focused

    def _install(self, monkeypatch, focused):
        monkeypatch.setattr(
            caret_text, "_windows_caret_before_context", lambda: _windows_path(focused)
        )

    def test_empty_field_with_truthy_clamped_move_has_no_separator(self, monkeypatch):
        r = self._range(moved=1, text="w", comparison=0)
        self._install(monkeypatch, self._patch_windows(monkeypatch, caret_range=r))
        assert delivery_text_for_target("dictated") == "Dictated"

    def test_move_proven_before_nonspace_gets_exactly_one_space(self, monkeypatch):
        r = self._range(moved=1, text="d", comparison=-1)
        self._install(monkeypatch, self._patch_windows(monkeypatch, caret_range=r))
        assert delivery_text_for_target("dictated") == " dictated"
        # The COM call must use the real three-argument signature.
        assert r.CompareEndpoints.call_args_list == [
            call(
                caret_text._UIA_TEXT_RANGE_COMPARE_START,
                r,
                caret_text._UIA_TEXT_RANGE_COMPARE_START,
            )
        ]

    def test_move_proven_before_whitespace_gets_no_space(self, monkeypatch):
        r = self._range(moved=1, text="\n", comparison=-1)
        self._install(monkeypatch, self._patch_windows(monkeypatch, caret_range=r))
        assert delivery_text_for_target("dictated") == "dictated"

    def test_unproven_move_gets_no_space(self, monkeypatch):
        r = self._range(moved=0, text="d", comparison=-1)
        self._install(monkeypatch, self._patch_windows(monkeypatch, caret_range=r))
        assert delivery_text_for_target("dictated") == "Dictated"

    def test_caret_at_start_with_content_after_has_no_separator(self, monkeypatch):
        r = self._range(moved=1, text="a", comparison=0)
        self._install(
            monkeypatch,
            self._patch_windows(monkeypatch, caret_range=r, value="abc"),
        )
        assert delivery_text_for_target("dictated") == "Dictated"

    def test_unreadable_range_gets_no_space_and_logs_one_debug_line(self, monkeypatch):
        r = self._range(moved=1, text="", text_error=True)
        log = MagicMock()
        focused = self._patch_windows(monkeypatch, caret_range=r, log=log)
        self._install(monkeypatch, focused)
        assert delivery_text_for_target("dictated") == "dictated"
        failure_lines = [
            c for c in log.debug.call_args_list
            if c.args[0] == "[CLIPBOARD] Windows caret read failed (%s), no separator added"
        ]
        assert len(failure_lines) == 1  # the paste read; the direct read below logs its own
        log.debug.reset_mock()
        assert caret_text._windows_caret_char(focused) == ""
        log.debug.assert_called_once()
        args = log.debug.call_args.args
        assert args[0] == "[CLIPBOARD] Windows caret read failed (%s), no separator added"
        assert "unreadable caret text" in str(args[1])


class TestBlockScopedSeparator:
    """The composer's own block, not page chrome, decides the separator."""

    @staticmethod
    def _page(text):
        return SimpleNamespace(GetText=lambda _n: text)

    def _install(self, monkeypatch, *, page_text="Home\nSearch sessions\nNew session\n",
                 log=None, same_as_document=False, **range_kwargs):
        helpers = TestWindowsCaretClassification()
        document = self._page(page_text)
        range_kwargs.setdefault("document_range", document)
        if same_as_document:
            range_kwargs["doc_comparison"] = 0
        caret_range = helpers._range(**range_kwargs)
        focused = helpers._patch_windows(
            monkeypatch, caret_range=caret_range, document_range=document, log=log
        )
        helpers._install(monkeypatch, focused)
        return caret_range

    def test_empty_composer_with_page_text_before_caret_has_no_separator(self, monkeypatch):
        page = "Home\nSearch sessions\nNew session\nV\nmedia-transcription work\nClose tab"
        log = MagicMock()
        r = self._install(
            monkeypatch, page_text=page, log=log, moved=1, text="w", comparison=-1,
            # An empty Electron composer exposes a zero-width marker, not "".
            block_text="\u200b", prefix_text="\u200b",
        )
        assert delivery_text_for_target("dictated") == "Dictated"
        assert r.state["expand_calls"][0] == caret_text._UIA_TEXT_UNIT_PARAGRAPH
        assert r.state["move_range_calls"] == [(
            caret_text._UIA_TEXT_RANGE_ENDPOINT_END, r,
            caret_text._UIA_TEXT_RANGE_ENDPOINT_START,
        )]
        message = log.debug.call_args_list[0].args[0] % log.debug.call_args_list[0].args[1:]
        assert f"doc={len(page)}" in message
        assert "para=1" in message
        assert "hex=U+200B" in message
        assert "verdict=empty" in message

    @pytest.mark.parametrize("marker", ["\u200b", "\ufeff", "\u2060", "\u00ad"])
    def test_invisible_prefix_adds_no_separator(self, monkeypatch, marker):
        self._install(
            monkeypatch, moved=1, text="w", comparison=-1,
            block_text=marker, prefix_text=marker,
        )
        assert delivery_text_for_target("dictated") == "Dictated"

    def test_real_prefix_gets_exactly_one_space(self, monkeypatch):
        self._install(
            monkeypatch, moved=1, text="w", comparison=-1,
            block_text="hello", prefix_text="hello",
        )
        assert delivery_text_for_target("dictated") == " dictated"

    @pytest.mark.parametrize("prefix", ["hello ", "hello\n"])
    def test_prefix_ending_in_whitespace_gets_no_space(self, monkeypatch, prefix):
        self._install(
            monkeypatch, moved=1, text="w", comparison=-1,
            block_text=prefix, prefix_text=prefix,
        )
        assert delivery_text_for_target("dictated") == "dictated"

    def test_paragraph_unavailable_falls_back_to_line(self, monkeypatch):
        r = self._install(
            monkeypatch, moved=1, text="w", comparison=-1,
            block_text_by_unit={caret_text._UIA_TEXT_UNIT_LINE: "hello"},
            expand_error_unit=caret_text._UIA_TEXT_UNIT_PARAGRAPH,
            prefix_text="hello",
        )
        assert delivery_text_for_target("dictated") == " dictated"
        assert r.state["expand_calls"] == [
            caret_text._UIA_TEXT_UNIT_PARAGRAPH, caret_text._UIA_TEXT_UNIT_LINE,
        ]

    def test_block_indistinguishable_from_document_is_unknown(self, monkeypatch):
        self._install(
            monkeypatch, page_text="Home\n" + "x" * 400, same_as_document=True,
            moved=1, text="w", comparison=-1,
            block_text="x" * 300, prefix_text="x" * 300,
        )
        assert delivery_text_for_target("dictated") == "dictated"

    def test_implausibly_large_block_is_unknown(self, monkeypatch):
        self._install(
            monkeypatch, moved=1, text="w", comparison=-1,
            block_text="x" * (caret_text._BLOCK_LIMIT + 1),
            prefix_text="x" * 10,
        )
        assert delivery_text_for_target("dictated") == "dictated"

    def test_diagnostic_logs_hex_not_text_and_exactly_one_line(self, monkeypatch):
        log = MagicMock()
        self._install(
            monkeypatch, log=log, moved=1, text="w", comparison=-1,
            block_text="hello", prefix_text="hello",
        )
        assert delivery_text_for_target("dictated") == " dictated"
        caret_lines = [c for c in log.debug.call_args_list if c.args[0] == caret_text._DIAG_MSG]
        assert len(caret_lines) == 1
        args = caret_lines[0].args
        assert args[0] == caret_text._DIAG_MSG
        message = args[0] % args[1:]
        assert "U+0068 U+0065" in message
        assert "verdict=needs-space" in message
        assert "hello" not in message
        delivery_lines = [c for c in log.debug.call_args_list if c.args[0] == caret_text._DELIVERY_DIAG_MSG]
        assert len(delivery_lines) == 1
        delivery_message = delivery_lines[0].args[0] % delivery_lines[0].args[1:]
        assert "verdict=needs-space case=lower reason=has-content" in delivery_message


def _windows_path(focused):
    """Exercise the real classifier against a mocked focused element."""
    context = caret_text._windows_caret_context(focused)
    if context.before is None:
        before = caret_text._windows_value_tail(focused)
        return caret_text._PrefixContext(before, caret_text._verdict_for(before), False)
    return context


class _FakeApp:
    def __init__(self, *, paste_on_stop: bool = True, clipboard_save_restore: bool = False):
        self.config = SimpleNamespace(
            paste_on_stop=paste_on_stop,
            clipboard_save_restore=clipboard_save_restore,
            crash_recovery_enabled=False,
        )
        self.clipboard = MagicMock()
        self.clipboard.copy.return_value = None
        self.clipboard._clipboard_seq = 11
        self.clipboard.paste.return_value = True
        self.tray = MagicMock()
        self._waveform_bubble = MagicMock()
        self._busyness = MagicMock()
        self._crash_recovery = MagicMock()
        self._schedule_timer = MagicMock()


class _PasteHost(_PasteStepMixin):
    def __init__(self, app):
        self._app = app
        self._cycle_id = "cycle-1"
        self._device_info = "cpu"

    def _hide_or_idle_bubble(self, *_args, **_kwargs):
        pass


class TestPasteStepSeparator:
    def test_paste_carries_one_leading_space(self, caret):
        caret("existing text")
        app = _FakeApp()
        _PasteHost(app)._copy_and_paste("dictated")

        app.clipboard.copy.assert_called_once_with(" dictated")
        paste_kwargs = app.clipboard.paste.call_args.kwargs
        assert paste_kwargs["pasted_text"] == " dictated"
        assert paste_kwargs["expected_fingerprint"] == text_fingerprint(" dictated")

    def test_empty_field_pastes_without_a_space(self, caret):
        caret("")
        app = _FakeApp()
        _PasteHost(app)._copy_and_paste("dictated")

        app.clipboard.copy.assert_called_once_with("Dictated")
        assert app.clipboard.paste.call_args.kwargs["pasted_text"] == "Dictated"

    def test_save_restore_skip_leaves_the_clipboard_alone(self, caret):
        caret("existing text")
        app = _FakeApp(paste_on_stop=False, clipboard_save_restore=True)
        _PasteHost(app)._copy_and_paste("dictated")

        app.clipboard.copy.assert_not_called()
        app.clipboard.paste.assert_not_called()

    def test_recovery_entry_keeps_the_decoded_text_byte_identical(self, caret):
        """C-TRANS-2: only clipboard + paste carry case and separator."""
        caret("say this ")
        app = _FakeApp()
        app.config.crash_recovery_enabled = True
        app.clipboard.copy.side_effect = ClipboardCopyError("clipboard blocked")
        _PasteHost(app)._copy_and_paste("Hello there")

        # Copy was attempted with the lowercased text but no extra space (the
        # prefix already ends in whitespace); recovery holds the decoded text.
        app.clipboard.copy.assert_called_once_with("hello there")
        app._crash_recovery.add.assert_called_once_with(
            "Hello there", pasted=False, cycle_id="cycle-1"
        )

    def test_clipboard_only_path_keeps_the_transcription_clean(self, caret):
        """paste_on_stop=False + save/restore OFF: the user pastes by hand, so
        the clipboard must hold the transcript itself, not a padded copy."""
        caret("existing text")
        app = _FakeApp(paste_on_stop=False, clipboard_save_restore=False)
        _PasteHost(app)._copy_and_paste("dictated")

        app.clipboard.copy.assert_called_once_with("dictated")
        app.clipboard.paste.assert_not_called()


class TestDeliveryCase:
    """Both rules come from the one caret verdict, through the public API."""

    def test_empty_field_capitalizes_without_a_space(self, caret):
        caret("")
        assert delivery_text_for_target("hello") == "Hello"

    def test_empty_field_with_capitalized_text_is_unchanged(self, caret):
        caret("")
        assert delivery_text_for_target("Hello") == "Hello"

    def test_field_with_text_lowercases_and_adds_one_space(self, caret):
        caret("say this")
        assert delivery_text_for_target("hello there") == " hello there"

    def test_field_ending_in_space_lowercases_without_extra_space(self, caret):
        caret("say this ")
        assert delivery_text_for_target("Hello there") == "hello there"

    @pytest.mark.parametrize("text", ["Hello", "hello"])
    def test_unknown_field_never_mutates(self, caret, text):
        caret(None)
        assert delivery_text_for_target(text) == text

    @pytest.mark.parametrize("text", ["\u0645\u0631\u062d\u0628\u0627", "\u4f60\u597d"])
    def test_caseless_script_is_unchanged(self, caret, text):
        caret("")
        assert delivery_text_for_target(text) == text
        caret("say this")
        assert delivery_text_for_target(text) == " " + text

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("42 is the answer", "42 Is the answer"),
            ('"quoted" words', '"Quoted" words'),
            ("https://example.com/path", "https://example.com/path"),
            ("iPhone", "IPhone"),  # only first letter changes; rest preserved
            ("USA", "USA"),
        ],
    )
    def test_first_eligible_letter_only(self, caret, text, expected):
        caret("")
        assert delivery_text_for_target(text) == expected

    def test_auto_capitalize_off_keeps_empty_field_text(self, caret):
        caret("")
        assert delivery_text_for_target("hello", auto_capitalize=False) == "hello"

    def test_auto_capitalize_off_does_not_block_lowercase_or_separator(self, caret):
        caret("say this")
        assert delivery_text_for_target("Hello there", auto_capitalize=False) == " hello there"

    def test_caret_at_position_zero_with_text_after_is_empty_prefix(self, caret):
        """Accepted case: nothing before the caret -> capital, no space."""
        caret("")
        assert delivery_text_for_target("hello") == "Hello"


class TestFieldOwnTextWins:
    """CASE 1: the field's own text is authoritative, not its surroundings."""

    def test_empty_document_range_ignores_an_escaped_block(self, monkeypatch):
        helper = TestBlockScopedSeparator()
        helper._install(
            monkeypatch,
            page_text="",  # the field itself is empty
            moved=1,
            text="w",
            comparison=-1,
            block_text="Ask Chat",  # the paragraph escaped into page content
            prefix_text="Ask Chat",
        )
        assert delivery_text_for_target("dictated") == "Dictated"

    @pytest.mark.parametrize("marker", ["\u200b", "\ufeff", "\u2060", "\u00ad"])
    def test_invisible_only_field_is_empty(self, monkeypatch, marker):
        helper = TestBlockScopedSeparator()
        helper._install(
            monkeypatch,
            page_text=marker,
            moved=1,
            text="w",
            comparison=-1,
            block_text="page text",
            prefix_text="page text",
        )
        assert delivery_text_for_target("dictated") == "Dictated"

    def test_block_outside_document_range_is_rejected(self):
        from types import SimpleNamespace

        escaping = SimpleNamespace(
            CompareEndpoints=lambda which, _doc, _target: -1
            if which == caret_text._UIA_TEXT_RANGE_COMPARE_START
            else 1,
        )
        assert caret_text._contained_in_document(escaping, object()) is False

    def test_value_pattern_empty_field_is_empty(self, monkeypatch):
        monkeypatch.setattr(caret_text, "_char_before_caret", lambda: "")
        assert delivery_text_for_target("dictated") == "Dictated"


class TestDeliveryOnlyContract:
    def test_both_delivery_paths_call_the_single_entry_point(self):
        root = Path(__file__).resolve().parents[1]
        sources = (
            root / "voice_typer" / "server" / "dictation_pipeline" / "paste_step.py",
            root / "tools" / "internal_plugins" / "_common" / "delivery.py",
        )
        for source in sources:
            body = source.read_text(encoding="utf-8")
            assert "delivery_text_for_target(" in body, source.name
            assert "pasted_text_with_separator" not in body, source.name


class TestUnicodeAndStopSnapshotDelivery:
    """R2 Unicode whitespace / Bidi marks / non-Latin / brackets & stop-time prefix_context."""

    @pytest.mark.parametrize("ws", ["\xa0", "\u2003", "\u202f", "\u3000"])
    def test_unicode_trailing_whitespace_avoids_double_space(self, caret, ws):
        caret(f"hello{ws}")
        assert delivery_text_for_target("Dictated words") == "dictated words"

    @pytest.mark.parametrize("ws", ["\xa0", "\u2003", "\u3000"])
    def test_text_starting_with_unicode_whitespace_is_not_doubled(self, caret, ws):
        caret("previous")
        assert delivery_text_for_target(f"{ws}dictated") == f"{ws}dictated"

    @pytest.mark.parametrize("bidi", ["\u200e", "\u200f", "\u061c", "\u202b", "\u2067"])
    def test_bidi_only_prefix_classifies_as_empty(self, caret, bidi):
        caret(bidi)
        assert delivery_text_for_target("hello") == "Hello"
        assert delivery_text_for_target("مرحبا") == "مرحبا"

    @pytest.mark.parametrize("bidi", ["\u200e", "\u200f", "\u061c", "\u2067"])
    def test_trailing_space_plus_bidi_mark_avoids_double_space(self, caret, bidi):
        caret(f"مرحبا {bidi}")
        assert delivery_text_for_target("بالعالم") == "بالعالم"
        caret(f"hello {bidi}")
        assert delivery_text_for_target("World") == "world"

    def test_windows_text_pattern_strips_bidi_trailing_and_empty(self, monkeypatch):
        helper = TestBlockScopedSeparator()
        helper._install(
            monkeypatch,
            page_text="\u200f",
            moved=1,
            text="w",
            comparison=-1,
            block_text="\u200f",
            prefix_text="\u200f",
        )
        assert delivery_text_for_target("hello") == "Hello"

        helper._install(
            monkeypatch,
            page_text="hello \u200f",
            moved=1,
            text="w",
            comparison=-1,
            block_text="hello \u200f",
            prefix_text="hello \u200f",
        )
        assert delivery_text_for_target("World") == "world"

    def test_zwnj_inside_or_at_end_is_not_treated_as_empty_invisible(self, caret):
        caret("می\u200c")
        assert delivery_text_for_target("خواهم") == " خواهم"

    def test_quotes_and_brackets_keep_leading_delimiter(self, caret):
        caret("")
        assert delivery_text_for_target("(hello)") == "(Hello)"
        assert delivery_text_for_target("«bonjour»") == "«Bonjour»"
        caret("word")
        assert delivery_text_for_target("(Hello)") == " (hello)"

    def test_explicit_prefix_context_skips_live_caret_probe(self, monkeypatch):
        def _boom():
            raise AssertionError("live _char_before_caret must not run when prefix_context is given")

        monkeypatch.setattr(caret_text, "_char_before_caret", _boom)
        snap_ctx = caret_text._PrefixContext("existing", "needs-space", True)
        assert delivery_text_for_target("Hello", prefix_context=snap_ctx) == " hello"
        empty_ctx = caret_text._PrefixContext("", "empty", True)
        assert delivery_text_for_target("hello", prefix_context=empty_ctx) == "Hello"
        unknown_ctx = caret_text._PrefixContext(None, "unknown", False)
        assert delivery_text_for_target("hello", prefix_context=unknown_ctx) == "hello"
