"""Mocked modules must survive pytest's ``__dict__``-based patch undo.

pytest >= 9.2 records monkeypatch undo state from ``target.__dict__``. A
``MagicMock`` keeps auto-created children in ``_mock_children``, so patching
one was undone with ``delattr``: the child stayed deleted for the rest of the
session, and every later patch of that name raised ``AttributeError``. These
pins cover the module stand-in that replaced the ``MagicMock`` module mocks.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from voice_typer.server._lazy_import import lazy_module

from tests.fixtures.mock_modules import MockModule, mock_module


def test_children_are_real_dict_entries():
    module = mock_module("standin.example")

    child = module.query_devices

    assert isinstance(module, MockModule)
    assert isinstance(child, MagicMock)
    assert module.__dict__["query_devices"] is child
    assert module.query_devices is child


def test_dunder_probes_stay_absent():
    module = mock_module("standin.dunders")

    assert not hasattr(module, "__path__")


class TestPatchUndo:
    def test_patch_of_a_child_is_undone_in_place(self, monkeypatch):
        module = mock_module("standin.direct")
        original = module.InputStream

        monkeypatch.setattr(module, "InputStream", object())
        assert module.InputStream is not original

        monkeypatch.undo()
        assert module.InputStream is original

    def test_patch_through_a_lazy_proxy_keeps_the_attribute(self, monkeypatch):
        """The CI shape: tests patch ``recording.sd.InputStream``."""
        module = sys.modules["sounddevice"]
        proxy = lazy_module("sounddevice")
        original = proxy.InputStream

        monkeypatch.setattr(proxy, "InputStream", object())
        assert module.InputStream is not original

        monkeypatch.undo()
        # Restored in place, not deleted: a deleted child made every later
        # patch of this name raise AttributeError for the whole session.
        assert module.InputStream is original
        assert proxy.InputStream is original

    def test_access_after_unittest_patch_exit_still_resolves(self):
        module = mock_module("standin.unittest")

        with patch.object(module, "query_devices", "sentinel"):
            assert module.query_devices == "sentinel"

        assert isinstance(module.query_devices, MagicMock)
