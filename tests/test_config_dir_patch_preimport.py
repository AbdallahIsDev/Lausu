"""Config-dir patching must never run first-time imports inside fixture setup.

CPython 3.10 can raise ``KeyError: <thread id>`` from
``importlib._bootstrap._ModuleLock.acquire`` when an import callback
re-enters import machinery mid-acquire (bpo-43546 / cpython#87712).
Keeping those imports at session start removes the crash window.
"""

from __future__ import annotations

import importlib

import pytest

from tests.fixtures import config_helpers


def test_preimport_populates_every_patch_target(monkeypatch):
    monkeypatch.setattr(config_helpers, "_config_modules", {})

    config_helpers.preimport_config_modules()

    assert set(config_helpers._CONFIG_MODULE_NAMES) <= set(config_helpers._config_modules)


def test_patch_config_dir_refs_reuses_preimported_modules(monkeypatch, tmp_path):
    config_helpers.preimport_config_modules()

    def guarded_import(name, package=None):
        if name in config_helpers._CONFIG_MODULE_NAMES:
            raise AssertionError(f"fixture setup re-imported {name}")
        return real_import_module(name, package)

    real_import_module = importlib.import_module
    monkeypatch.setattr(config_helpers.importlib, "import_module", guarded_import)
    originals = {
        name: config_helpers._config_module(name)._config_dir
        for name in config_helpers._CONFIG_MODULE_NAMES
    }

    patch = pytest.MonkeyPatch()
    try:
        config_helpers.patch_config_dir_refs(patch, tmp_path)
        for name in config_helpers._CONFIG_MODULE_NAMES:
            assert config_helpers._config_module(name)._config_dir() == tmp_path
    finally:
        patch.undo()

    for name in config_helpers._CONFIG_MODULE_NAMES:
        assert config_helpers._config_module(name)._config_dir is originals[name]
