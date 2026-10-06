"""Disk persistence for the template list.

Loads and saves ``templates.json`` through :class:`PersistedJSON` (atomic
write, single-slot ``.bak``, quarantine of a corrupt file). The public
manager class inherits these methods.
"""

import logging

log = logging.getLogger(__name__)

class TemplatePersistenceMixin:
    """Load/save the template list through the host's ``PersistedJSON``.

    Host contract (provided by ``TemplateManager``): ``_store``, ``_path``,
    ``_templates``, ``_lock``, ``_rebuild_indexes()``, ``_save()``.
    """

    def _load(self) -> None:
        """Load templates from JSON file.

        Persistence is routed through :class:`PersistedJSON`
        (``self._store``). On parse failure (corrupt JSON, OSError,
        symlink-TOCTOU raise), the helper quarantines the corrupt file
        to ``<path>.corrupt-<ts>`` for forensic recovery and returns
        the configured default. The previous implementation silently
        fell back to an empty list with a single WARNING log line, no
        quarantine, so the next ``_save`` would atomically overwrite
        the corrupt file with defaults, destroying any chance of
        forensic recovery. Mirrors ``config.py:1744-1763`` and
        ``crash_recovery.py:186-219``.

        SEC-audit-006 (Round 0 forward-port): the underlying read
        uses :func:`voice_typer.server.config._secure_read_text`
        (POSIX ``O_NOFOLLOW`` + inode re-verification) to prevent a
        symlink-TOCTOU attack where an attacker replaces the templates
        file with a symlink to a sensitive file (e.g.
        ``~/.ssh/id_rsa``).

        ``_load`` is called only from ``__init__`` (before
        the instance is published to other threads), so it does NOT
        acquire ``self._lock``: the lock guards public-method
        interleaving, not single-threaded construction.

        validate each item's structure (must be a dict with both
        ``trigger`` and ``output`` keys) BEFORE assigning to
        ``self._templates``. Pre-fix, a valid-JSON-but-wrong-structure
        file (e.g. ``{"templates": [42, "foo", null]}`` or
        ``{"templates": [{"trigger": "no_output"}]}``) passed the
        ``isinstance(data, list)`` / ``"templates" in data`` checks but
        then crashed ``_rebuild_indexes`` with
        ``AttributeError: 'int' object has no attribute 'get'`` (or
        ``match`` with ``KeyError: 'output'``), and since ``_load`` is
        called from ``__init__`` with no try/except, the constructor
        raised, crashing app startup with an opaque traceback and no
        recovery path (the file is NOT quarantined because the JSON
        itself is valid). The validation mirrors the one already
        enforced in ``import_json`` (line ~472) so the two load paths
        agree on what counts as a well-formed template.
        """
        data = self._store.load()
        if isinstance(data, list):
            raw_list = data
        elif isinstance(data, dict) and "templates" in data:
            raw_list = data["templates"]
        else:
            raw_list = []
        # per-item structural validation. Drop any item that
        if not isinstance(raw_list, list):
            raw_list = []
        validated: list[dict] = []
        dropped = 0
        for t in raw_list:
            if isinstance(t, dict) and "trigger" in t and "output" in t:
                validated.append(t)
            else:
                dropped += 1
        if dropped:
            log.warning(
                "[TEMPLATES] Dropped %d malformed templates from %s "
                "(each must be a dict with both 'trigger' and 'output' keys)",
                dropped,
                self._path,
            )
        self._templates = validated
        # rebuild match indexes after load.
        self._rebuild_indexes()
        log.info("[TEMPLATES] Loaded %d templates from %s", len(self._templates), self._path)

    def _save(self) -> None:
        """Save templates to JSON file.

        Persistence is routed through :class:`PersistedJSON`
        (``self._store``), which provides atomic write + single-slot
        ``.bak`` before overwrite + 0o600 perms (parity with
        ``config.py:1163-1182``). The shared ``_secure_atomic_write``
        applies ``O_NOFOLLOW`` on POSIX to prevent symlink TOCTOU
        attacks.

        previously this method caught *all* exceptions and
        silently logged them, returning ``None`` to callers. That
        meant a disk failure left the in-memory ``_templates`` list
        (already mutated by ``add``/``update``/``delete``) out of
        sync with what was actually on disk, the user's edit
        appeared to succeed (no error surfaced) but the next process
        restart would load the stale on-disk state and the edit
        would be lost. Now we log the error AND re-raise so callers
        can roll back their in-memory mutation and the IPC layer can
        surface the failure to the renderer.

        caller is expected to hold ``self._lock`` (all
        current callers, the public CRUD methods, already do).
        """
        try:
            # PersistedJSON.save handles atomic write + .bak
            self._store.save({"templates": self._templates}, durability=False)
        except Exception:
            # Log then re-raise so callers can roll back.
            log.exception("[TEMPLATES] Failed to save")
            raise
        log.debug("[TEMPLATES] Saved %d templates", len(self._templates))
