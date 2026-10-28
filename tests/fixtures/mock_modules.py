"""Module stand-ins for the heavy third-party imports tests replace.

A ``MagicMock`` keeps its auto-created children in ``_mock_children`` rather
than ``__dict__``. pytest >= 9.2 records patch undo state from
``target.__dict__``, so such a child reads as absent: ``monkeypatch.setattr``
with ``raising=True`` refuses the patch, and a patch that did apply is undone
with ``delattr``, which marks the child deleted for the rest of the session
(every later access raises ``AttributeError``).

A module stand-in keeps every materialized child in the real ``__dict__``, so
patch/undo round-trips exactly the way it does for a real module.
"""

from __future__ import annotations

from types import ModuleType
from unittest.mock import MagicMock


class MockModule(ModuleType):
    """Import stand-in that materializes attribute children on first access."""

    def __getattr__(self, name: str) -> MagicMock:
        # Dunders stay absent: the import machinery probes ``__path__`` and
        # ``__spec__``, and answering those turns the stand-in into a package.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        child = MagicMock(name=f"{self.__name__}.{name}")
        setattr(self, name, child)
        return child


def mock_module(name: str) -> MockModule:
    """Return the stand-in to register as ``sys.modules[name]``."""
    return MockModule(name)
