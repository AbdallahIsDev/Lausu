"""Delivery-time caret context: separator space and first-letter case.

Companion to :mod:`.focused_text`: that module answers "is the focused element
a text input", this one classifies the text before the caret. One classification
drives both delivery-only decisions in :func:`delivery_text_for_target`:

* empty prefix -> capital first letter, no leading space
* prefix with content -> lowercase first letter, one space unless it ends in
  whitespace
* unknown / page-scoped / unreadable -> neither space nor case is safe to
  change; paste the transcript exactly as decoded

The caret read, block scoping and invisible-marker stripping are unchanged from
the separator-only implementation. Cross-module references still go through
``_pkg.NAME`` at call time so test patches on the package propagate.
"""

from __future__ import annotations

import importlib
from typing import Any, NamedTuple

# Call-time _pkg lookups (C-ARCH-2): package is partial at module load.
import voice_typer.server.clipboard_target_safety as _pkg

# UIA ids/units, verified against UIAutomationCore.h + MS Learn: TextUnit_Paragraph=4,
# TextUnit_Line=3, endpoint Start=0/End=1, UIA_TextPattern2Id=10024.
_UIA_VALUE_PATTERN_ID = 10002
_UIA_TEXT_PATTERN_ID = 10014
_UIA_TEXT_PATTERN2_ID = 10024
_UIA_TEXT_UNIT_CHARACTER = 0
_UIA_TEXT_UNIT_LINE = 3
_UIA_TEXT_UNIT_PARAGRAPH = 4
_UIA_TEXT_RANGE_ENDPOINT_START = 0
_UIA_TEXT_RANGE_ENDPOINT_END = 1
_UIA_TEXT_RANGE_COMPARE_START = 0
_UIA_TEXT_RANGE_COMPARE_END = 1
_PREFIX_LIMIT = 256
_BLOCK_LIMIT = 4096
_ENDPOINT_COMPARE_MIN = 256
# Zero-width space / BOM / word joiner / soft hyphen: isspace() is False for all four.
# Zero-width markers plus U+FFFC, the embedded-object placeholder AX text
# uses for a widget inside a web editor. None of it is typed by the user.
_INVISIBLE = "\u200b\ufeff\u2060\u00ad\ufffc"
_FAIL_MSG = "[CLIPBOARD] Windows caret read failed (%s), no separator added"
_DIAG_MSG = "[CLIPBOARD] separator ct=%s class=%s doc=%d para=%d line=%d hex=%s verdict=%s"
_DELIVERY_DIAG_MSG = "[CLIPBOARD] delivery verdict=%s case=%s reason=%s textlen=%d hex=%s"


class _PrefixContext(NamedTuple):
    """Caret prefix plus the verdict the classifier already computed.

    ``before`` keeps the historical contract ("" for empty/unproven, None when
    there is no text surface). ``verdict`` carries the distinction the old
    return value lost: page-scoped/unreadable is UNKNOWN, not EMPTY, and a
    whitespace-ended prefix has content even though ``before`` is "".
    ``has_pattern`` drives ONLY the Windows ValuePattern fallback.
    """

    before: str | None
    verdict: str
    has_pattern: bool = True


def _hex_prefix(text: str) -> str:
    return " ".join(f"U+{ord(c):04X}" for c in text[:8]) or "-"


def _log_verdict(fields: dict[str, Any], raw: str, verdict: str) -> None:
    """One DEBUG line: lengths and hex codepoints only, never field text."""
    _pkg._log().debug(
        _DIAG_MSG,
        fields["ct"],
        fields["class"],
        fields["doc"],
        fields["para"],
        fields["line"],
        _hex_prefix(raw or ""),
        verdict,
    )


def _caret_and_document(module: Any, focused: Any) -> tuple[Any, Any]:
    """Caret range + whole-document range, or (None, None) when absent.

    TextPattern2::GetCaretRange is the scoped caret; GetSelection(0) stays for
    providers without it.
    """
    caret = None
    document = None
    iface2 = getattr(module, "IUIAutomationTextPattern2", None)
    if iface2 is not None:
        ptr2 = focused.GetCurrentPattern(_UIA_TEXT_PATTERN2_ID)
        if ptr2 is not None:
            try:
                pattern2 = ptr2.QueryInterface(iface2)
                result = pattern2.GetCaretRange()
                if isinstance(result, tuple):
                    if result[0] is False:
                        return None, None  # caret inactive -> cannot justify a space
                    caret = result[1]
                else:
                    caret = result
                document = getattr(pattern2, "DocumentRange", None)
            except Exception:
                caret = None
    if caret is None:
        ptr = focused.GetCurrentPattern(_UIA_TEXT_PATTERN_ID)
        if ptr is None:
            return None, None
        pattern = ptr.QueryInterface(module.IUIAutomationTextPattern)
        ranges = pattern.GetSelection()
        if ranges is None or not ranges.Length:
            return None, None
        caret = ranges.GetElement(0)
        document = getattr(pattern, "DocumentRange", None)
    return caret, document


def _placeholder_texts(focused: Any) -> list[str]:
    """The element's own placeholder strings (Chrome maps them to Name/HelpText).

    A web editor's empty composer exposes its placeholder as the AX document
    text, so an empty field looked like it held "Ask ChatGPT" and every
    dictation started with a space.
    """
    out: list[str] = []
    for attr in ("CurrentName", "CurrentHelpText", "CurrentFullDescription"):
        value = getattr(focused, attr, "") or ""
        if isinstance(value, str):
            cleaned = value.strip()
            if len(cleaned) >= 2 and cleaned not in out:
                out.append(cleaned)
    return out


def _strip_placeholder(text: str, placeholders: list[str]) -> str:
    """Remove a leading placeholder from read text, if one is present."""
    stripped = text.lstrip(_INVISIBLE)
    for placeholder in placeholders:
        if stripped.startswith(placeholder):
            return stripped[len(placeholder) :]
    return stripped


def _field_text(document: Any) -> str:
    """The focused field's OWN text, read from its document range."""
    try:
        return str(document.GetText(-1) or "")
    except Exception:
        return ""


def _contained_in_document(block: Any, document: Any) -> bool:
    """A block is usable only when it stays inside the field's document range.

    Equality is too strict and one shared endpoint is too weak: Chromium can
    report a paragraph that STARTS before and ENDS after the composer while
    overlapping it, which previously leaked page text into the prefix.
    """
    if document is None:
        return False
    return (
        block.CompareEndpoints(
            _UIA_TEXT_RANGE_COMPARE_START, document, _UIA_TEXT_RANGE_COMPARE_START
        ) >= 0
        and block.CompareEndpoints(
            _UIA_TEXT_RANGE_COMPARE_END, document, _UIA_TEXT_RANGE_COMPARE_END
        ) <= 0
    )


def _spans_document(block: Any, document: Any, block_len: int) -> bool:
    """True when the "block" is page-scoped, escapes the field, or is huge."""
    if block_len > _BLOCK_LIMIT:
        return True
    if document is None or block_len <= _ENDPOINT_COMPARE_MIN:
        return False
    if not _contained_in_document(block, document):
        return True
    return (
        block.CompareEndpoints(
            _UIA_TEXT_RANGE_COMPARE_START, document, _UIA_TEXT_RANGE_COMPARE_START
        ) == 0
        and block.CompareEndpoints(
            _UIA_TEXT_RANGE_COMPARE_END, document, _UIA_TEXT_RANGE_COMPARE_END
        ) == 0
    )


def _block_prefix(caret: Any, original: Any, document: Any, unit: int) -> tuple[str | None, int]:
    """Text from the caret's own block start up to the caret, capped."""
    block = caret.Clone()
    try:
        block.ExpandToEnclosingUnit(unit)
    except Exception:
        return None, -1  # provider does not support this unit; try the next
    block_len = len(str(block.GetText(-1) or ""))
    if _spans_document(block, document, block_len):
        return None, block_len
    # Containment is proven above; an escaping block is rejected rather than
    # clamped, so no page text can be read past the field's own range.
    before = block.Clone()
    before.MoveEndpointByRange(
        _UIA_TEXT_RANGE_ENDPOINT_END, original, _UIA_TEXT_RANGE_ENDPOINT_START
    )
    return str(before.GetText(_PREFIX_LIMIT) or ""), block_len


def _windows_caret_context(focused: Any) -> _PrefixContext:
    """Classified text before the caret in the focused element's own block.

    The read itself (TextPattern2 caret, block scoping, endpoint proof,
    invisible-marker stripping, diagnostic) is unchanged; only the verdict is
    now returned alongside the prefix instead of being logged and discarded.
    """
    fields: dict[str, Any] = {
        "ct": getattr(focused, "CurrentControlType", "?"),
        "class": getattr(focused, "CurrentClassName", "?"),
        "doc": -1,
        "para": -1,
        "line": -1,
    }
    module = _pkg._UIA_MODULE
    if module is None:
        return _PrefixContext(None, "unknown", False)
    raw: str | None = None
    try:
        caret, document = _caret_and_document(module, focused)
        if caret is None:
            return _PrefixContext(None, "unknown", False)  # no TextPattern: let ValuePattern answer
        own_text = ""
        placeholders = _placeholder_texts(focused)
        if document is not None:
            own_text = _strip_placeholder(_field_text(document), placeholders)
            fields["doc"] = len(own_text)
            # CASE 1: the field itself is empty (invisible markers, a web
            # editor's placeholder and a lone newline all count as empty).
            # Never consult the surrounding page in that state.
            if not own_text.strip(_INVISIBLE).strip():
                _log_verdict(fields, "", "empty")
                return _PrefixContext("", "empty")
        # The selection start is where a paste lands. Move one character back,
        # then prove the endpoint moved (providers clamp at boundaries yet
        # still report a truthy count) before trusting any read.
        original = caret.Clone()
        moved = caret.MoveEndpointByUnit(
            _UIA_TEXT_RANGE_ENDPOINT_START, _UIA_TEXT_UNIT_CHARACTER, -1
        )
        if not moved or caret.CompareEndpoints(
            _UIA_TEXT_RANGE_COMPARE_START, original, _UIA_TEXT_RANGE_COMPARE_START
        ) >= 0:
            raw = ""  # start of field: no separator
        else:
            # The one-character range keeps trailing whitespace that a block
            # read can trim (CASE 3).
            previous = str(caret.GetText(1) or "")
            if previous and previous[-1].isspace():
                raw = previous
            else:
                for label, unit in (
                    ("para", _UIA_TEXT_UNIT_PARAGRAPH),
                    ("line", _UIA_TEXT_UNIT_LINE),
                ):
                    text, length = _block_prefix(caret, original, document, unit)
                    fields[label] = length
                    if text is not None:
                        raw = text
                        break
    except Exception as exc:
        _pkg._log().debug(
            _FAIL_MSG,
            f"{exc} | ct={fields['ct']} class={fields['class']} doc={fields['doc']} "
            f"para={fields['para']} line={fields['line']} hex=- verdict=unknown",
        )
        return _PrefixContext("", "unknown")

    cleaned = ""
    if raw is None:
        verdict = "unknown"
    else:
        cleaned = _strip_placeholder(raw, placeholders).strip(_INVISIBLE)
        if not cleaned:
            verdict = "empty"
        elif cleaned[-1].isspace():
            verdict = "trailing-space"
        else:
            verdict = "needs-space"
    _log_verdict(fields, raw or "", verdict)
    return _PrefixContext(cleaned if verdict == "needs-space" else "", verdict)


def _windows_caret_char(focused: Any) -> str | None:
    """Prefix-only view of :func:`_windows_caret_context` (name pinned by tests)."""
    return _windows_caret_context(focused).before


def _windows_value_tail(focused: Any) -> str | None:
    """Whole field value for controls without TextPattern (plain edit boxes).

    A caret offset is not observable without TextPattern, so the value's tail
    stands in for "text before the caret" - the normal shape for an edit box
    the user keeps typing into.
    """
    module = _pkg._UIA_MODULE
    if module is None:
        return None
    pattern_ptr = focused.GetCurrentPattern(_UIA_VALUE_PATTERN_ID)
    if pattern_ptr is None:
        return None
    pattern = pattern_ptr.QueryInterface(module.IUIAutomationValuePattern)
    value = pattern.CurrentValue
    return value if isinstance(value, str) else None


def _windows_caret_before_context() -> _PrefixContext:
    if not _pkg.is_windows():
        return _PrefixContext(None, "unknown", False)
    try:
        import comtypes  # noqa: F401  (availability probe; the helper owns init)
    except ImportError:
        return _PrefixContext(None, "unknown", False)
    try:
        _pkg._ensure_com_initialized()
        focused = _pkg._get_uia_focused_element()
        if focused is None:
            return _PrefixContext(None, "unknown", False)
        try:
            context = _windows_caret_context(focused)
            # Only fall back when TextPattern is genuinely absent. An empty
            # prefix means "start of field / unproven" - falling back to the
            # whole value there would reintroduce the leading-space bug.
            if not context.has_pattern:
                before = _windows_value_tail(focused)
                if before is not None:
                    before = _strip_placeholder(before, _placeholder_texts(focused))
                return _PrefixContext(before, _verdict_for(before), False)
            return context
        finally:
            # Release while the apartment is still up (see ``_release_uia_pointer``).
            _pkg._release_uia_pointer(focused)
    except Exception as exc:
        # One line, no traceback: an app whose caret surface exposes no
        # text is normal (it only costs the separating space).
        _pkg._log().debug(_FAIL_MSG, exc)
        return _PrefixContext(None, "unknown", False)


def _windows_char_before_caret() -> str | None:
    return _windows_caret_before_context().before


def _macos_char_before_caret() -> str | None:
    try:
        import AppKit
        import ApplicationServices
    except ImportError:
        return None
    try:
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        if workspace is None:
            return None
        front_app = workspace.frontmostApplication()
        if front_app is None:
            return None
        pid = front_app.processIdentifier()
        if not pid or pid <= 0:
            return None
        app_elem = ApplicationServices.AXUIElementCreateApplication(pid)
        if app_elem is None:
            return None
        focused = _pkg._ax_result_value(
            ApplicationServices.AXUIElementCopyAttributeValue(app_elem, "AXFocusedUIElement", None)
        )
        if focused is None:
            return None
        value = _pkg._ax_result_value(ApplicationServices.AXUIElementCopyAttributeValue(focused, "AXValue", None))
        return value if isinstance(value, str) else None
    except Exception as exc:
        # One line, no traceback: an app whose caret surface exposes no
        # text is normal (it only costs the separating space).
        _pkg._log().debug("[CLIPBOARD] macOS caret read failed (%s), no separator added", exc)
        return None


def _linux_char_before_caret() -> str | None:
    try:
        pyatspi = importlib.import_module("pyatspi")
    except ImportError:
        return None
    try:
        state_focused = getattr(pyatspi, "STATE_FOCUSED", 1 << 10)
        _pkg._PYATSPI_STATE_FOCUSED = state_focused
        desktop = pyatspi.Registry.getDesktop(0)
        if desktop is None:
            return None
        focused = _pkg._find_focused_atspi_accessible(desktop, state_focused, max_depth=10)
        if focused is None:
            return None
        text = focused.queryText()
        if text is None:
            return None
        caret = text.caretOffset
        if caret is None or caret < 0:
            return None  # caret offset unknown: no separator
        if caret == 0:
            return ""
        return str(text.getText(caret - 1, caret) or "")
    except Exception as exc:
        # One line, no traceback: an app whose caret surface exposes no
        # text is normal (it only costs the separating space).
        _pkg._log().debug("[CLIPBOARD] Linux caret read failed (%s), no separator added", exc)
        return None


def _char_before_caret() -> _PrefixContext:
    """Platform dispatch. Never raises: undetectable context is UNKNOWN."""
    try:
        if _pkg.is_windows():
            return _windows_caret_before_context()
        if _pkg.is_macos():
            before = _macos_char_before_caret()
        elif _pkg.is_linux():
            before = _linux_char_before_caret()
        else:
            before = None
        return _PrefixContext(before, _verdict_for(before), before is not None)
    except Exception:
        _pkg._log().debug("[CLIPBOARD] caret-read dispatch failed, no separator added", exc_info=True)
        return _PrefixContext(None, "unknown", False)


def _verdict_for(before: str | None) -> str:
    """The single classification shared by the separator and the case rule."""
    if before is None:
        return "unknown"
    if not before:
        return "empty"
    if before[-1].isspace():
        return "trailing-space"
    return "needs-space"


def _as_context(value: _PrefixContext | str | None) -> _PrefixContext:
    """Accept test doubles that still return the old text/None shape."""
    if isinstance(value, _PrefixContext):
        return value
    return _PrefixContext(value, _verdict_for(value), value is not None)


def _tail_needs_separator(before: str | None) -> bool:
    """Decide from the text/character in front of the caret."""
    return _verdict_for(before) == "needs-space"


def needs_leading_space() -> bool:
    """True when the pasted text must be preceded by exactly one space."""
    return _as_context(_char_before_caret()).verdict == "needs-space"


def _case_first_letter(text: str, *, upper: bool) -> tuple[str, str, bool]:
    """Change only the first cased letter; return (text, verdict, caseless).

    Mirrors ``auto_capitalize`` step 1's scan (leading quotes/brackets skipped)
    and its leading-URL guard. ``capitalize()``/``title()`` are never used:
    they rewrite the rest of the string and destroy "iPhone"/"USA".
    """
    from voice_typer.server.ai_enhancement import _RE_LEADING_URL

    if not text or _RE_LEADING_URL.match(text):
        return text, "unchanged", True
    for i, ch in enumerate(text):
        if ch.isalpha():
            if not (ch.islower() or ch.isupper()):
                return text, "unchanged", True  # uncased script
            cased = ch.upper() if upper else ch.lower()
            return text[:i] + cased + text[i + 1 :], ("upper" if upper else "lower"), False
        if ch.isspace():
            continue
        # Non-alpha, non-space (quote, bracket, digit): keep scanning.
    return text, "unchanged", True


def delivery_text_for_target(text: str, *, auto_capitalize: bool = True) -> str:
    """Format the transcript for the focused field, delivery-only.

    Text is returned for the clipboard copy and paste keystroke; history,
    crash recovery, ``_last_transcription`` and ``transcription_final`` keep
    the decoded text byte-identical (C-TRANS-2).
    """
    if not text:
        return text
    try:
        context = _as_context(_char_before_caret())
    except Exception:
        context = _PrefixContext(None, "unknown", False)

    verdict = context.verdict
    reason = "has-content"
    case_verdict = "unchanged"
    if verdict == "unknown":
        reason = "unknown"
        formatted = text  # never mutate on a guess
    else:
        upper = verdict == "empty"
        reason = "empty-field" if upper else "has-content"
        if upper and not auto_capitalize:
            reason = "auto-capitalize-off"
            formatted = text
        else:
            formatted, case_verdict, caseless = _case_first_letter(text, upper=upper)
            if caseless:
                reason = "caseless"

    _pkg._log().debug(
        _DELIVERY_DIAG_MSG,
        verdict,
        case_verdict,
        reason,
        len(text),
        _hex_prefix(text),
    )

    if formatted[0].isspace():
        return formatted  # text already carries its own leading whitespace
    if verdict == "needs-space":
        return " " + formatted
    return formatted


__all__ = [
    "_caret_and_document",
    "_char_before_caret",
    "_linux_char_before_caret",
    "_macos_char_before_caret",
    "_tail_needs_separator",
    "_verdict_for",
    "_windows_caret_char",
    "_windows_caret_context",
    "_windows_char_before_caret",
    "needs_leading_space",
    "delivery_text_for_target",
]
