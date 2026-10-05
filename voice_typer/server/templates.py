"""Voice template manager: CRUD, match/expand, variable substitution.

Templates are trigger-phrase → output-text pairs stored in a JSON file.
When the user says a trigger phrase during dictation, the system replaces
the transcribed text with the stored output.

Pipeline order: transcribe → text cleanup → vocabulary → template match → auto-punctuate → paste

Variables supported in output text:
    {today}    , current date (e.g., "2026-06-03")
    {now}      , current time (e.g., "14:30")
    {clipboard}, current clipboard content
    {username} , system username
"""

import getpass
import logging
import re
import threading
from datetime import datetime
from pathlib import Path

from voice_typer.server.template_persistence import TemplatePersistenceMixin
from voice_typer.server.template_transfer import TemplateTransferMixin

log = logging.getLogger(__name__)

# precompiled regexes, was `re.sub(r"\s+", ...)` recompiled per call
_WHITESPACE_RE = re.compile(r"\s+")
# single regex pass for variable substitution with lazy resolution.
_TEMPLATE_VAR_RE = re.compile(r"\{(today|now|clipboard|username)\}")

TEMPLATES_FILENAME = "templates.json"
_LEGACY_TEMPLATES_FILENAME = "lausu-templates.json"

# SEC-011-style caps for templates to prevent resource
MAX_TEMPLATES = 1000
MAX_TRIGGER_LENGTH = 200
# Template OUTPUT is free-form text (a whole paragraph / document the
MAX_OUTPUT_LENGTH = 128 * 1024


def _get_clipboard_text() -> str:
    """Try to read current clipboard content."""
    try:
        import pyperclip

        text = pyperclip.paste()
        return str(text) if text and isinstance(text, str) else ""
    except Exception:
        return ""


def substitute_variables(text: str) -> str:
    """Replace template variables with their current values.

    Supported variables:
        {today}    , date in YYYY-MM-DD
        {now}      , time in HH:MM
        {clipboard}, current clipboard content
        {username} , OS username

    single regex pass with lazy variable resolution. The old code
    eagerly computed all 4 values (including a potentially-blocking
    _get_clipboard_text() call) even when the output text contained none
    of the variables. Now each variable is resolved only when its
    placeholder is actually present, and datetime.now() is called at most
    once (shared between {today} and {now}).
    """
    if "{" not in text:
        # Fast path: no placeholders at all.
        return text
    # Lazy: only fetch when the placeholder is present.
    _now: datetime | None = None

    def _resolve(match: re.Match) -> str:
        nonlocal _now
        var = match.group(1)
        if var == "today":
            if _now is None:
                _now = datetime.now()
            return _now.strftime("%Y-%m-%d")
        if var == "now":
            if _now is None:
                _now = datetime.now()
            return _now.strftime("%H:%M")
        if var == "clipboard":
            return _get_clipboard_text()
        # username
        return _safe_getuser()

    return _TEMPLATE_VAR_RE.sub(_resolve, text)


def _safe_getuser() -> str:
    """Get username safely, returning 'user' on any failure.

    ``getpass.getuser()`` always returns ``str`` (or raises).
    The previous ``isinstance(name, str)`` check was dead code. Simplified
    to a direct truthiness check.
    """
    try:
        name = getpass.getuser()
        return name if name else "user"
    except Exception:
        return "user"


class TemplateManager(TemplatePersistenceMixin, TemplateTransferMixin):
    """Manages voice templates: CRUD, persistence, matching."""

    def __init__(self, config_dir: Path | None = None):
        if config_dir is None:
            from voice_typer.server.config import _config_dir

            config_dir = _config_dir()
        self._path = config_dir / TEMPLATES_FILENAME
        # One-time migration of the legacy prefixed name
        _legacy = config_dir / _LEGACY_TEMPLATES_FILENAME
        if _legacy.exists() and not self._path.exists():
            try:
                _legacy.rename(self._path)
                log.debug(
                    "[TEMPLATES] migrated legacy %s -> %s",
                    _LEGACY_TEMPLATES_FILENAME,
                    TEMPLATES_FILENAME,
                )
            except OSError as exc:
                log.debug("[TEMPLATES] legacy file migration failed: %s", exc)
        # Route persistence through PersistedJSON so templates
        from voice_typer.server.secure_file_io import PersistedJSON

        self._store = PersistedJSON(self._path, default={"templates": []})
        self._templates: list[dict] = []
        # re-entrant lock guarding ``_templates`` +
        self._lock = threading.RLock()
        # match indexes for O(1) exact lookup + reduced-scan
        self._exact_index: dict[str, dict] = {}
        self._contains_list: list[tuple[str, dict]] = []
        # _load() calls _rebuild_indexes() at its end so the
        self._load()

    def _rebuild_indexes(self) -> None:
        """rebuild the match indexes from ``self._templates``.

        Called after ``_load`` and after every mutation (add/update/
        delete/import). The indexes let ``match`` do an O(1) dict lookup
        for exact-mode templates and a reduced-scan linear search over
        ONLY contains-mode templates (sorted by trigger length ascending
        so the early-exit in ``match`` is safe).

        Behavior preservation:
        - Exact mode: only one template can match a given input (the one
          whose normalized trigger equals the normalized input). If two
          templates share a normalized trigger, the FIRST one in
          ``self._templates`` order wins (we skip the duplicate insert),
          matching the pre-fix linear scan's strict ``<`` comparison.
        - Contains mode: the list is sorted by trigger length ascending.
          Python's ``sort`` is stable, so templates at the same length
          preserve their original order, matching the pre-fix behavior
          where the first template at the shortest matching length wins.
        - Cross-mode: the docstring contract "shortest trigger wins when
          multiple templates match" is preserved by checking the exact
          index first (setting the upper-bound length) then scanning
          contains templates strictly shorter than that bound.
        """
        self._exact_index = {}
        self._contains_list = []
        for t in self._templates:
            # skip templates without a usable ``output`` field.
            if not t.get("output"):
                continue
            trigger = t.get("trigger", "")
            if not trigger:
                continue
            trigger_norm = _WHITESPACE_RE.sub(" ", trigger.strip()).lower()
            mode = t.get("match_mode", "exact")
            if mode == "contains":
                self._contains_list.append((trigger_norm, t))
            else:
                # Exact: first-wins for duplicate normalized triggers
                if trigger_norm not in self._exact_index:
                    self._exact_index[trigger_norm] = t
        # Sort contains list by trigger length ascending so ``match``
        self._contains_list.sort(key=lambda pair: len(pair[0]))

    @property
    def templates(self) -> list[dict]:
        """Public read accessor for the templates list.

        the previous public ``templates`` attribute was renamed
        to ``_templates`` (private) without a property shim, breaking
        every caller, tests, IPC handlers, the tray menu builder, and
        the on-disk persistence round-trip in
        ``tests/test_history_and_models.py::TestTemplatesPersistToDisk``.

        Returns a SHALLOW COPY of the underlying list so callers can
        iterate / index / clear the returned list without mutating the
        manager's internal state (per the
        ``test_templates_property_returns_copy`` contract: modifying the
        returned object must not affect the manager).

        The individual template dicts inside the list are NOT copied
        (shallow copy), callers that need to mutate a template should
        use :meth:`update` so the change persists to disk.

        copies under the lock so a concurrent CRUD mutation
        can't observe a half-updated list (e.g. ``_templates.pop``
        mid-iteration by ``delete``).
        """
        with self._lock:
            return list(self._templates)

    def add(self, trigger: str, output: str, *, match_mode: str = "exact") -> dict | None:
        """Add a new template. Returns the created template dict, or
        ``None`` if rejected.

        enforces SEC-011-style caps:
          - Per-field length cap: ``MAX_TRIGGER_LENGTH``,
            ``MAX_OUTPUT_LENGTH``. Oversized entries are rejected with
            a logged warning.
          - Total count cap: ``MAX_TEMPLATES``. Once the cap is reached
            the new template is dropped (rejected with a warning).

        persists first-then-mutates with rollback. If ``_save``
        raises, the appended entry is popped back off so the
        in-memory state stays consistent with the on-disk state.

        the entire read-validate-mutate-save-rebuild
        sequence runs under ``self._lock`` so a concurrent ``match``
        or CRUD call can't observe a half-applied mutation.
        """
        trigger_stripped = trigger.strip() if isinstance(trigger, str) else str(trigger).strip()
        output_str = output if isinstance(output, str) else str(output)
        with self._lock:
            if len(trigger_stripped) > MAX_TRIGGER_LENGTH:
                log.warning(
                    "[TEMPLATES] Trigger exceeds MAX_TRIGGER_LENGTH (%d > %d), rejecting",
                    len(trigger_stripped),
                    MAX_TRIGGER_LENGTH,
                )
                return None
            if len(output_str) > MAX_OUTPUT_LENGTH:
                log.warning(
                    "[TEMPLATES] Output exceeds MAX_OUTPUT_LENGTH (%d > %d), rejecting",
                    len(output_str),
                    MAX_OUTPUT_LENGTH,
                )
                return None
            if len(self._templates) >= MAX_TEMPLATES:
                log.warning(
                    "[TEMPLATES] Template count at MAX_TEMPLATES cap (%d), rejecting new template",
                    MAX_TEMPLATES,
                )
                return None
            template = {
                "trigger": trigger_stripped,
                "output": output_str,
                "match_mode": match_mode,  # "exact" or "contains"
                "created_at": datetime.now().isoformat(),
            }
            self._templates.append(template)
            try:
                self._save()
            except Exception:
                # Rollback: remove the template we just appended.
                for i in range(len(self._templates) - 1, -1, -1):
                    if self._templates[i] is template:
                        del self._templates[i]
                        break
                raise
            # rebuild match indexes after mutation.
            self._rebuild_indexes()
            return template

    def update(self, index: int, trigger: str, output: str, *, match_mode: str = "exact") -> dict | None:
        """Update a template by index. Returns the updated template or None.

        snapshots the original field values and restores them
        on save failure so the in-memory state stays consistent with
        the on-disk state.

        the snapshot-mutate-save-rebuild sequence runs
        under ``self._lock`` so a concurrent ``match`` can't observe
        a half-updated entry.
        """
        with self._lock:
            if not (0 <= index < len(self._templates)):
                return None
            entry = self._templates[index]
            # Snapshot originals for rollback.
            old_trigger = entry.get("trigger")
            old_output = entry.get("output")
            old_match_mode = entry.get("match_mode")
            entry["trigger"] = trigger.strip()
            entry["output"] = output
            entry["match_mode"] = match_mode
            try:
                self._save()
            except Exception:
                entry["trigger"] = old_trigger
                entry["output"] = old_output
                entry["match_mode"] = old_match_mode
                raise
            # rebuild match indexes after mutation.
            self._rebuild_indexes()
            return entry

    def delete(self, index: int) -> bool:
        """Delete a template by index.

        snapshots the deleted entry and re-inserts it at the
        same index on save failure so the in-memory state stays
        consistent with the on-disk state.

        the pop-save-rebuild sequence runs under
        ``self._lock`` so a concurrent ``match`` can't observe the
        list mid-pop.
        """
        with self._lock:
            if not (0 <= index < len(self._templates)):
                return False
            removed = self._templates.pop(index)
            try:
                self._save()
            except Exception:
                # Rollback: re-insert at the original index.
                self._templates.insert(index, removed)
                raise
            # rebuild match indexes after mutation.
            self._rebuild_indexes()
            return True

    def replace_all(self, templates: list[dict]) -> None:
        """Atomically replace the entire template list.

        Replaces ``self._templates`` with ``templates`` in a single
        locked transaction: acquires ``self._lock``, swaps the list,
        calls :meth:`_rebuild_indexes` (so ``match`` sees the new
        templates immediately) and then calls :meth:`_save` (so the
        on-disk file is updated atomically). If ``_save`` raises, the
        previous in-memory list is restored before re-raising so the
        in-memory state stays consistent with the on-disk state
        (mirrors the rollback pattern used by :meth:`add` /
        :meth:`update` / :meth:`delete` / :meth:`import_json`).

        Pre-fix callers (e.g. ``service.TemplateMixin.save_templates``)
        directly assigned to the internal list and called the internal
        save method themselves, which:

        1. Bypassed ``self._lock``: a concurrent ``match`` could
           observe a half-swapped list (the swap + ``_rebuild_indexes``
           + ``_save`` sequence was not atomic, so ``match`` could
           read the new ``_templates`` list but the OLD
           ``_exact_index`` / ``_contains_list`` indexes, causing a
           stale-match / missed-match window).
        2. Skipped ``_rebuild_indexes``: the match indexes still
           pointed at the OLD templates until the next ``add`` /
           ``update`` / ``delete`` / ``import_json`` / ``_load`` call
           rebuilt them, so the just-saved templates would not be
           matchable until a process restart.

        Caller contract: ``templates`` MUST already be normalized
        (trigger / output / match_mode validated, length-capped). The
        service mixin is responsible for that normalization.
        """
        with self._lock:
            old_templates = self._templates
            self._templates = list(templates)
            try:
                self._save()
            except Exception:
                # Rollback: restore the previous in-memory list so the
                self._templates = old_templates
                raise
            # rebuild match indexes after the swap so ``match`` sees
            self._rebuild_indexes()

    def match(self, text: str) -> str | None:
        """Try to match *text* against any template trigger.

        Returns the expanded output text (with variables substituted)
        if a match is found, or None if no template matches.

        Matching rules:
        - Whitespace-normalized, case-insensitive comparison
        - "exact" mode: the whole text must match the trigger
        - "contains" mode: the trigger must be found anywhere in the text
        - Shortest trigger wins when multiple templates match

        pre-fix this method did an O(N) linear scan of
        ``self._templates`` on every dictation. With MAX_TEMPLATES=1000
        that was up to 1000 iterations per call (re-normalizing each
        trigger's text on every call too). Now the exact-mode templates
        are in ``_exact_index`` (O(1) dict lookup) and the contains-mode
        templates are in ``_contains_list`` (sorted by trigger length
        ascending so we can early-exit once we see a trigger >= the
        current best length). The docstring's "shortest trigger wins"
        contract is preserved: the exact match (if any) sets the upper
        bound, and contains templates strictly shorter than that bound
        can still win, matching the pre-fix behavior where a short
        contains trigger beats a long exact trigger.

        the match indexes are read under ``self._lock`` so a
        concurrent CRUD mutation (which rebuilds ``_exact_index`` /
        ``_contains_list`` via ``_rebuild_indexes``, also under the
        lock) can't leave ``match`` iterating a half-rebuilt index.
        ``substitute_variables`` is called OUTSIDE
        the lock so the (potentially blocking) clipboard read in
        ``{clipboard}`` doesn't block concurrent CRUD calls.
        """
        with self._lock:
            if not text or not self._templates:
                return None

            normalized = _WHITESPACE_RE.sub(" ", text.strip()).lower()  #

            best_match: dict | None = None
            best_len = float("inf")

            # O(1) exact lookup. The exact match (if any) sets
            exact_t = self._exact_index.get(normalized)
            if exact_t is not None:
                best_match = exact_t
                best_len = len(normalized)

            # reduced-scan contains lookup. The list is sorted by
            for trigger_norm, t in self._contains_list:
                if len(trigger_norm) >= best_len:
                    break
                if trigger_norm in normalized:
                    best_match = t
                    best_len = len(trigger_norm)

            if best_match is None:
                return None
            # always have one, but a defensive ``.get`` keeps
            output = best_match.get("output", "")

        # Substitute variables OUTSIDE the lock so the (potentially
        return substitute_variables(output)
