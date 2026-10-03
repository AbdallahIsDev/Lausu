"""mypy shadow stub for yt_dlp (PEP 561 Any-module).

yt_dlp ships without ``py.typed`` and no ``types-yt-dlp`` stub package
is installed here, so mypy reports ``import-untyped`` on every import.
This stub package shadows it for mypy only (via ``[tool.mypy]
mypy_path = ["voice_typer/mypy_stubs"]``, same mechanism as the numpy
shadow): every attribute resolves to ``Any`` through PEP 562
``__getattr__``. Runtime behaviour is unaffected (stubs are never
imported at runtime).

Must be a PACKAGE (``yt_dlp/__init__.pyi``), not a module file
(``yt_dlp.pyi``): mirrors the numpy shadow layout so any submodule
imports keep resolving consistently.
"""

from typing import Any

def __getattr__(name: str) -> Any: ...
