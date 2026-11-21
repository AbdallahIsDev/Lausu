"""Deterministic subprocess env for tests that spawn pytest.

This module exists so a CI-provided PYTEST_* override cannot silently change
the behaviour of a nested pytest run.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

# Vars pytest reads directly; CI may set them globally and leak into the
# nested run (extra addopts/plugins, autoload disabled, forced xdist workers).
PYTEST_ENV_KEYS = (
    "PYTEST_ADDOPTS",
    "PYTEST_PLUGINS",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
    "PYTEST_DEBUG",
    "PYTEST_XDIST_AUTO_NUM_WORKERS",
)


def scrub_pytest_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy ``base`` (default: ``os.environ``) with every PYTEST_* override removed."""
    env = dict(os.environ if base is None else base)
    for key in PYTEST_ENV_KEYS:
        env.pop(key, None)
    return env
