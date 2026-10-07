"""Screenshot config schema + allowlist tests."""

from voice_typer.server.config import Config
from voice_typer.server.config_validators import IPC_CONFIG_ALLOWLIST
from voice_typer.server.config_validators.scalar import _bool_validator


def test_screenshot_fields_default_off() -> None:
    cfg = Config()
    assert cfg.screenshot_beta_enabled is False
    assert cfg.screenshot_consent is False


def test_screenshot_fields_allowlisted_as_bool() -> None:
    for field in ("screenshot_beta_enabled", "screenshot_consent"):
        assert field in IPC_CONFIG_ALLOWLIST
        assert IPC_CONFIG_ALLOWLIST[field][1] is _bool_validator
