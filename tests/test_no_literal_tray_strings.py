"""No hardcoded user-facing English in the server's UI calls (C-I18N-1).

Every tray / notification / state-machine message must go through
``i18n.t(...)``. A literal passed straight to one of those surfaces
bypasses the i18n layer entirely: the English user sees the right words
and every other locale silently falls back to English.

Detection notes (the two earlier drafts were both wrong, so both lessons
are encoded below):

* v1 watched five method names and found 14 -- it MISSED ``config_applier``'s
  bare ``notify(APP_NAME, msg)`` helper and several notice strings.
* v2 then matched any attribute call whose verb was in the list and
  returned 1,635 hits -- almost all of them ``log.info("[VOLUME] ...")``
  LOG LINES, which are developer diagnostics and must stay untranslated
  (translating them breaks log grepping).

So the test keys off the RECEIVER being a real UI object, and explicitly
excludes loggers. It also covers bare module-level helpers, and only
requires a literal to look like prose (letters plus a space) so that enum
values and identifiers are not false positives.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SERVER_ROOT = Path(__file__).resolve().parents[1] / "voice_typer" / "server"

# Receivers that can put text in front of a human.
_UI_RECEIVER = re.compile(r"\b(tray|dialog|notification|notifier|menubar|bubble)\b", re.I)
# Logger-ish receivers: log lines are never user-facing.
_LOG_RECEIVER = re.compile(r"\b(log|logger|_log|logging|audit)\b", re.I)
# Methods that surface text.
_UI_METHOD = re.compile(
    r"^(set_state|set_tooltip|show_tooltip|notify|show_balloon|send_notification"
    r"|show_message|show_error|show_info|show_dialog|set_label|set_subtitle"
    r"|set_body|set_description|set_message|set_text)$"
)
# Keywords that carry the message.
_UI_KWARG = {"message", "text", "title", "body", "label", "description", "detail", "reason_text"}
# Prose, not an identifier or a code fragment.
_PROSE = re.compile(r"[A-Za-z]{2,}.*\s")
# set_state(AppState.X, msg): index 0 is the enum, not prose.
_ENUM_FIRST = {"set_state", "set_tooltip"}


def _receiver(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return ""


def _ui_literals(tree: ast.AST) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            recv, attr = "", func.id
        elif isinstance(func, ast.Attribute):
            recv, attr = _receiver(func.value), func.attr
        else:
            continue
        if _LOG_RECEIVER.search(recv):
            continue
        if not (_UI_METHOD.match(attr) or _UI_RECEIVER.search(recv)):
            continue
        for i, arg in enumerate(node.args):
            if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                continue
            if i == 0 and attr in _ENUM_FIRST:
                continue
            if _PROSE.search(arg.value):
                hits.append((arg.lineno, arg.value))
        for kw in node.keywords:
            if kw.arg not in _UI_KWARG:
                continue
            v = kw.value
            if isinstance(v, ast.Constant) and isinstance(v.value, str) and _PROSE.search(v.value):
                hits.append((v.lineno, v.value))
    return hits


def _server_python_files() -> list[Path]:
    return sorted(p for p in SERVER_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


@pytest.mark.parametrize("path", _server_python_files(), ids=lambda p: p.name)
def test_no_literal_user_facing_string_in_gui_calls(path: Path):
    """Every tray/state message must be an i18n lookup, not a literal."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = _ui_literals(tree)
    assert not offenders, (
        f"{path.name}: user-facing string passed as a literal to a UI call (C-I18N-1). "
        f"Use i18n.t('<key>') and register the key in voice_typer/server/i18n.py, "
        f"map it in i18n/push.ts, and add it to all 8 renderer locales:\n"
        + "\n".join(f"  line {ln}: {val!r}" for ln, val in offenders)
    )


def test_server_catalog_keys_resolve_to_text():
    """Every key the server catalog declares must return a real string."""
    from voice_typer.server import i18n

    for key in [
        "notify.app.config_acl_failed",
        "notify.dictation_pipeline.no_speech_detected",
        "notify.permissions.global_hotkeys_disabled",
        "state.model_loading",
        "state.model_unloaded_idle",
    ]:
        assert key in i18n._INITIAL_LABELS, f"{key} missing from the server catalog"
        assert isinstance(i18n.t(key), str) and i18n.t(key).strip()


def test_pushed_notify_keys_exist_in_english_locale():
    """Each ``notify.<group>.<key>`` the publisher pushes must exist in en.json.

    The ``notify`` section is NESTED BY GROUP, which is what
    ``tests/regressions/test_i18n.py`` walks when it derives the renderer key
    set. A flat string directly under ``notify`` breaks that walk.
    """
    import json as _json

    en_path = (
        Path(__file__).resolve().parents[1]
        / "voice_typer"
        / "client"
        / "src"
        / "renderer"
        / "src"
        / "i18n"
        / "translations"
        / "en.json"
    )
    data = _json.loads(en_path.read_text(encoding="utf-8"))
    notify = data["notify"]

    assert all(isinstance(v, dict) for v in notify.values()), (
        "every notify entry must be a GROUP object, not a flat string "
        "(tests/regressions/test_i18n.py walks notify.<group>.<key>)"
    )

    for group, short in (
        ("dictation_pipeline", "llm_polish_failed"),
        ("dictation_pipeline", "history_save_failed"),
        ("dictation_pipeline", "crash_recovery_save_failed"),
        ("dictation_pipeline", "text_cleanup_failed"),
        ("dictation_pipeline", "vocab_correction_failed"),
        ("dictation_pipeline", "template_match_failed"),
        ("dictation_pipeline", "auto_punctuation_failed"),
        ("dictation_pipeline", "no_speech_detected"),
        ("dictation_pipeline", "no_transcription_produced"),
        ("app", "onboarding_kept_failing"),
        ("app", "onboarding_setup_failed"),
        ("app", "config_acl_failed"),
        ("hotkey_dispatcher", "wayland_hotkeys_may_fail"),
        ("permissions", "accessibility_granted"),
        ("permissions", "global_hotkeys_disabled"),
        ("recording_controller", "consent_not_verified"),
    ):
        assert short in notify.get(group, {}), f"en.json notify.{group}.{short} missing"

    assert "modelLoadRetry" in data["trayState"]["recordingController"], (
        "en.json trayState.recordingController.modelLoadRetry missing"
    )
