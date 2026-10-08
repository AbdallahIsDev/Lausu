"""Facade re-exports + patch seams of the Wave 6 split security modules.

``voice_typer.server.security.redaction`` and
``voice_typer.server.security.file_io`` each lost their cohesive concerns
to focused sibling modules. Callers (and tests) import names from the
facades, so two contracts must hold:

1. every moved symbol is re-exported by the facade as the SAME object as
   in its owning sibling module;
2. runtime lookups that tests monkeypatch ON the facade are still read at
   call time by the sibling code (never captured by value at import).

The redaction pipeline also depends on pattern ORDER (specific
flag/prefixed forms before bare/generic forms, home-path scrub before the
PII patterns); the order-sensitive fixtures below compare facade output
against sibling output byte-for-byte and pin the order semantics.
"""

from __future__ import annotations

import logging

# Fixtures that exercise every ORDER-sensitive boundary in the pipeline:
# flag form before prefixed patterns, prefixed patterns before the
# generic catch-all, home-path scrub before the PII patterns, PII
# patterns before secret redaction, labeled-value shields, and the
# public-vocabulary exemptions.
_ORDER_FIXTURES = (
    "Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz1234567890",
    "--token=Bearer sk-abcdefghijklmnopqrstuvwxyz1234567890",
    "contact john.doe@example.com, auth=Bearer sk-abcdefghijklmnopqrstuvwxyz1234567890",
    "loaded config: token=abc123-secret-value",
    "https://alice:secret@localhost:8080/v1/audio",
    "sha256=" + "a" * 64 + " thread=abc123 binary=worker.exe prop_set={0123456789abcdef0123456789abcdef}",
    "teardown_some_state_thing " + "x" * 20,
    "models--Systran--faster-whisper-large-v3",
    "CUDA_VISIBLE_DEVICES=''",
    "/home/alice/.lausu/foo.log",
    "/home/alice/contact@example.com",
)


class TestRedactionFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server.security import (
            export_redaction,
            home_path_redaction,
            pii_redaction,
            redaction,
            secret_patterns,
            secret_redaction,
        )

        for name in (
            "_KEY_PATTERNS",
            "_DASH_JOINED_FULL_RE",
            "_HASH_LABEL_RE",
            "_PROPSET_LABEL_RE",
            "_THREAD_LABEL_RE",
            "_BINARY_LABEL_RE",
            "_TEARDOWN_LABEL_RE",
            "_PUBLIC_ENV_VAR_NAMES",
            "_SECRET_KEYWORDS",
            "_KEYWORD_ALT",
            "_FLAG_VALUE_PATTERN",
            "_BARE_KEY_VALUE_PATTERN",
            "_FLAG_KEY_PATTERNS",
            "_flag_sub",
            "_MIN_REDACT_LEN",
            "_public_config_field_names",
            "_public_ipc_command_names",
        ):
            assert getattr(redaction, name) is getattr(secret_patterns, name), name
        for name in ("redact_secret", "redact_api_keys", "redact_url"):
            assert getattr(redaction, name) is getattr(secret_redaction, name), name
        for name in ("_resolve_home_dirs", "_redact_home_path", "_redact_home_path_in_text"):
            assert getattr(redaction, name) is getattr(home_path_redaction, name), name
        for name in (
            "_FAST_TRIGGER",
            "_CONTROL_CHAR_RE",
            "_escape_control_chars",
            "_redact_text",
            "PIIRedactionFilter",
            "redact_pii",
            "install_lastresort_pii_filter",
        ):
            assert getattr(redaction, name) is getattr(pii_redaction, name), name
        assert redaction.redact_for_export is export_redaction.redact_for_export
        # Mutable cache globals stay owned by their sibling (the facade
        # re-export is an attribute-surface snapshot, not live state).
        assert hasattr(redaction, "_HOME_PATH_RE_CACHE")
        assert hasattr(redaction, "_PUBLIC_CONFIG_FIELD_NAMES_CACHE")
        assert hasattr(redaction, "_PUBLIC_IPC_COMMAND_NAMES_CACHE")

    def test_legacy_import_paths_still_resolve(self):
        from voice_typer.server import _secrets
        from voice_typer.server.security import redaction

        assert _secrets.redact_secret is redaction.redact_secret
        assert _secrets.redact_api_keys is redaction.redact_api_keys
        assert _secrets.redact_url is redaction.redact_url
        assert _secrets.redact_for_export is redaction.redact_for_export
        assert _secrets._FLAG_KEY_PATTERNS is redaction._FLAG_KEY_PATTERNS
        assert _secrets._MIN_REDACT_LEN == redaction._MIN_REDACT_LEN

    def test_aliases_used_by_production_callers_resolve_to_the_same_objects(self):
        from voice_typer.server import security
        from voice_typer.server.handlers._base import _redact_home_path_in_text
        from voice_typer.server.security import http_safety, redaction

        assert security.redact_pii is redaction.redact_pii
        assert security.PIIRedactionFilter is redaction.PIIRedactionFilter
        assert _redact_home_path_in_text is redaction._redact_home_path_in_text
        assert http_safety.redact_url is redaction.redact_url


class TestRedactionOrderEquivalence:
    def test_facade_and_sibling_output_match_byte_for_byte(self, monkeypatch):
        monkeypatch.setenv("HOME", "/home/alice")
        from voice_typer.server.security import (
            export_redaction,
            home_path_redaction,
            pii_redaction,
            redaction,
            secret_redaction,
        )

        pairs = (
            (redaction.redact_secret, secret_redaction.redact_secret),
            (redaction.redact_api_keys, secret_redaction.redact_api_keys),
            (redaction.redact_url, secret_redaction.redact_url),
            (redaction.redact_pii, pii_redaction.redact_pii),
            (redaction._redact_text, pii_redaction._redact_text),
            (redaction._escape_control_chars, pii_redaction._escape_control_chars),
            (redaction.redact_for_export, export_redaction.redact_for_export),
            (redaction._redact_home_path, home_path_redaction._redact_home_path),
            (redaction._redact_home_path_in_text, home_path_redaction._redact_home_path_in_text),
        )
        for text in _ORDER_FIXTURES:
            for facade_fn, sibling_fn in pairs:
                assert facade_fn(text) == sibling_fn(text), (
                    f"{facade_fn.__name__} diverged from its sibling on {text!r}"
                )

    def test_flag_form_runs_before_the_prefixed_patterns(self):
        from voice_typer.server.security import redaction

        text = "--token=Bearer sk-abcdefghijklmnopqrstuvwxyz1234567890"
        assert redaction.redact_for_export(text) == "--token=*** ***"

    def test_prefixed_patterns_run_before_the_generic_catch_all(self):
        from voice_typer.server.security import redaction

        text = "Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz1234567890"
        assert redaction.redact_api_keys(text) == "Authorization: Bearer ***"

    def test_home_path_scrub_runs_before_the_pii_patterns(self, monkeypatch):
        monkeypatch.setenv("HOME", "/home/alice")
        from voice_typer.server.security import redaction

        out = redaction._redact_text("/home/alice/contact@example.com")
        # PII-first ordering would have produced just "[EMAIL]" and dropped
        # the path prefix entirely; the home-path scrub must run first.
        assert out != "[EMAIL]"
        assert out.endswith("[EMAIL]")
        assert "alice" not in out


class TestRedactionPatchSeams:
    def test_pii_filter_reads_redact_text_from_the_facade(self, monkeypatch):
        from voice_typer.server.security import redaction

        calls: list[str] = []
        real_redact_text = redaction._redact_text

        def counting_redact_text(text, *args, **kwargs):
            calls.append(text)
            return real_redact_text(text, *args, **kwargs)

        monkeypatch.setattr(redaction, "_redact_text", counting_redact_text)

        record = logging.LogRecord(
            "wave6.split",
            logging.INFO,
            __file__,
            1,
            "User test@example.com logged in",
            (),
            None,
        )
        assert redaction.PIIRedactionFilter().filter(record) is True

        assert calls, "PIIRedactionFilter must resolve _redact_text through the facade at call time"
        assert "[EMAIL]" in record.msg


class TestFileIoFacadeReexports:
    def test_moved_symbols_resolve_to_the_sibling_modules(self):
        from voice_typer.server.security import atomic_write, file_io, persisted_json, secure_read

        for name in (
            "_windows_fsync_directory",
            "_secure_atomic_write",
            "_chmod_owner_only",
            "_OS_REPLACE_MAX_ATTEMPTS",
            "_OS_REPLACE_RETRY_DELAY_S",
        ):
            assert getattr(file_io, name) is getattr(atomic_write, name), name
        for name in ("_DEFAULT_MAX_READ_BYTES", "_read_with_byte_limit", "_secure_read_text"):
            assert getattr(file_io, name) is getattr(secure_read, name), name
        for name in ("_QUARANTINE_SUFFIX_SEQ", "PersistedJSON", "T"):
            assert getattr(file_io, name) is getattr(persisted_json, name), name

    def test_legacy_shims_reexport_the_facade_objects(self):
        import voice_typer.server.secure_file_io as shim
        from voice_typer.server import config, security
        from voice_typer.server.security import file_io

        assert shim.PersistedJSON is file_io.PersistedJSON
        assert shim._secure_read_text is file_io._secure_read_text
        assert shim._secure_atomic_write is file_io._secure_atomic_write
        assert shim._chmod_owner_only is file_io._chmod_owner_only
        assert config._secure_atomic_write is file_io._secure_atomic_write
        assert config._secure_read_text is file_io._secure_read_text
        assert security._windows_fsync_directory is file_io._windows_fsync_directory


class TestFileIoPatchSeams:
    def test_secure_atomic_write_reads_chmod_seam_from_the_facade(self, monkeypatch, tmp_path):
        from voice_typer.server.security import file_io

        calls: list[str] = []
        real_chmod = file_io._chmod_owner_only

        def counting_chmod(path):
            calls.append(str(path))
            return real_chmod(path)

        monkeypatch.setattr(file_io, "_chmod_owner_only", counting_chmod)

        target = tmp_path / "wave6-out.json"
        file_io._secure_atomic_write(target, '{"ok": true}')

        assert calls == [str(target)], (
            "_secure_atomic_write must resolve _chmod_owner_only through the facade at call time"
        )
        assert target.read_text(encoding="utf-8") == '{"ok": true}'
