"""mypy shadow stub for ``numpy.rec`` (CQ-058, see ``numpy/__init__.pyi``).

Real stub uses PEP 695 ``type`` statements, unparseable at the project's
``python_version = "3.11"``. Any-``__getattr__`` keeps submodule resolution
inside the shadow package.
"""

from typing import Any

def __getattr__(name: str) -> Any: ...
