"""JSON export/import of the template list.

The string-level transfer format (what the export file and the clipboard
round-trip) as opposed to the on-disk persistence in ``templates``.
"""

import json
import logging

from voice_typer.server._lazy_import import lazy_module

log = logging.getLogger(__name__)

# Lazy proxy: ``templates`` imports this module, so a direct import would be circular.
_tmpl = lazy_module("voice_typer.server.templates")


class TemplateTransferMixin:
    """Export/import the template list as JSON text.

    Host contract (provided by ``TemplateManager``): ``_templates``,
    ``_lock``, ``_rebuild_indexes()``, ``_save()``.
    """

    def export_json(self) -> str:
        """Export templates as a JSON string.

        snapshot ``_templates`` under the lock before
        serializing so a concurrent CRUD mutation can't produce a
        half-serialized JSON (e.g. ``json.dumps`` observing a list
        mid-``pop``).
        """
        with self._lock:
            snapshot = list(self._templates)
        return json.dumps({"templates": snapshot}, indent=2, ensure_ascii=False)

    def import_json(self, json_str: str) -> int:
        """Import templates from a JSON string. Returns number imported.

        enforces SEC-011-style caps:
          - Drops templates whose trigger exceeds
            ``MAX_TRIGGER_LENGTH`` or output exceeds
            ``MAX_OUTPUT_LENGTH`` (mirrors
            ``text_cleanup._load_external_corrections``).
          - Truncates the import if it would exceed ``MAX_TEMPLATES``.
          - Logs a single warning summarising the dropped count.

        snapshots the list before appending and restores it on
        save failure so the in-memory state stays consistent with the
        on-disk state.

        the validate-extend-save-rebuild sequence runs
        under ``self._lock`` so a concurrent ``match`` can't observe
        a half-extended list.
        """
        with self._lock:
            try:
                data = json.loads(json_str)
                templates = data if isinstance(data, list) else data.get("templates", [])
                to_add: list[dict] = []
                dropped = 0
                for t in templates:
                    if not isinstance(t, dict) or "trigger" not in t or "output" not in t:
                        continue
                    trigger_raw = t.get("trigger", "")
                    output_raw = t.get("output", "")
                    trigger_str = trigger_raw if isinstance(trigger_raw, str) else str(trigger_raw)
                    output_str = output_raw if isinstance(output_raw, str) else str(output_raw)
                    # Use the stripped length for the trigger cap to match
                    if len(trigger_str.strip()) > _tmpl.MAX_TRIGGER_LENGTH:
                        dropped += 1
                        continue
                    if len(output_str) > _tmpl.MAX_OUTPUT_LENGTH:
                        dropped += 1
                        continue
                    to_add.append(t)
                if dropped:
                    log.warning(
                        "[TEMPLATES] Dropped %d templates from import (oversized)",
                        dropped,
                    )
                # Total-count cap: truncate to fit within MAX_TEMPLATES.
                current = len(self._templates)
                available = _tmpl.MAX_TEMPLATES - current
                if available <= 0:
                    log.warning(
                        "[TEMPLATES] Template count at MAX_TEMPLATES cap (%d), dropping all %d imported templates",
                        _tmpl.MAX_TEMPLATES,
                        len(to_add),
                    )
                    return 0
                if len(to_add) > available:
                    log.warning(
                        "[TEMPLATES] Import exceeds MAX_TEMPLATES cap, truncating %d -> %d",
                        len(to_add),
                        available,
                    )
                    to_add = to_add[:available]
                if not to_add:
                    return 0
                # Snapshot for rollback.
                old_len = len(self._templates)
                self._templates.extend(to_add)
                try:
                    self._save()
                except Exception:
                    # Rollback: truncate back to the pre-import length.
                    del self._templates[old_len:]
                    raise
                # rebuild match indexes after mutation.
                self._rebuild_indexes()
                return len(to_add)
            except Exception:
                log.exception("[TEMPLATES] Import failed")
                return 0
