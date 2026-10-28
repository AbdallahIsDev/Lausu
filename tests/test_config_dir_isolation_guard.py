"""The config-dir isolation fixture must survive a leaked ``_config_dir`` patch.

When a test's ``monkeypatch.undo()`` aborts, its ``_config_dir`` lambda stays
installed on the paths module and every later test in that worker dies in
``cache_clear()``. The fixture repairs the leak before isolating the next test.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_heal_reinstalls_the_real_config_dir(monkeypatch):
    from voice_typer.server.config_internals import paths as paths_impl

    from tests.fixtures.config_helpers import (
        heal_leaked_config_dir_patch,
        real_config_dir_impl,
    )

    real = real_config_dir_impl()
    monkeypatch.setattr(paths_impl, "_config_dir", lambda: Path("leaked"))

    assert heal_leaked_config_dir_patch() is True
    assert paths_impl._config_dir is real
    assert heal_leaked_config_dir_patch() is False


def test_real_config_dir_impl_is_the_cached_production_function():
    from tests.fixtures.config_helpers import real_config_dir_impl

    impl = real_config_dir_impl()
    assert impl is real_config_dir_impl()
    assert callable(impl.cache_clear)


@pytest.mark.real_config_dir
def test_marked_test_sees_the_real_function_even_if_a_leak_preceded_it():
    """``real_config_dir`` tests skip the patch, so they must also be healed."""
    from voice_typer.server.config_internals import paths as paths_impl

    from tests.fixtures.config_helpers import real_config_dir_impl

    assert paths_impl._config_dir is real_config_dir_impl()
