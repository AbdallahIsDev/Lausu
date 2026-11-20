"""Environment-variable validation regressions (PLAT-008) for the platform layer."""

from __future__ import annotations

import os


class TestEnvVarValidation:
    """PLAT-008: _validate_env_vars rejects invalid values."""

    def test_valid_boolean_values_are_accepted(self, monkeypatch):
        from voice_typer.server.env_validation import _validate_env_vars

        monkeypatch.setenv("VOICE_TYPER_QUIET", "true")
        _validate_env_vars()
        assert os.environ.get("VOICE_TYPER_QUIET") == "true"

    def test_invalid_boolean_values_are_removed(self, monkeypatch):
        from voice_typer.server.env_validation import _validate_env_vars

        monkeypatch.setenv("VOICE_TYPER_QUIET", "invalid_value")
        _validate_env_vars()
        assert "VOICE_TYPER_QUIET" not in os.environ

    def test_invalid_restart_token_is_removed(self, monkeypatch):
        from voice_typer.server.env_validation import _validate_env_vars

        monkeypatch.setenv("VOICE_TYPER_RESTART", "'; DROP TABLE users; --")
        _validate_env_vars()
        assert "VOICE_TYPER_RESTART" not in os.environ

    def test_valid_restart_token_is_accepted(self, monkeypatch):
        from voice_typer.server.env_validation import _validate_env_vars

        monkeypatch.setenv("VOICE_TYPER_RESTART", "abc123_def")
        _validate_env_vars()
        assert os.environ.get("VOICE_TYPER_RESTART") == "abc123_def"

    def test_invalid_config_dir_is_removed(self, monkeypatch):
        from voice_typer.server.env_validation import _validate_env_vars

        monkeypatch.setenv("VOICE_TYPER_CONFIG_DIR", "")
        _validate_env_vars()
        long_path = "/a" * 3000
        monkeypatch.setenv("VOICE_TYPER_CONFIG_DIR", long_path)
        _validate_env_vars()
        assert "VOICE_TYPER_CONFIG_DIR" not in os.environ

    def test_invalid_ipc_token_is_removed(self, monkeypatch):
        from voice_typer.server.env_validation import _validate_env_vars

        monkeypatch.setenv("VOICE_TYPER_IPC_TOKEN", "'; rm -rf /")
        _validate_env_vars()
        assert "VOICE_TYPER_IPC_TOKEN" not in os.environ
