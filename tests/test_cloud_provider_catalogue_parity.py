"""Cross-language parity: the cloud provider catalogue vs `_PROVIDER_DEFAULTS`.

Two tables describe the same four providers, and they must agree on the
endpoint and on the DEFAULT model:

  * the renderer's catalogue,
    ``client/src/renderer/src/lib/utils/models.ts`` → ``CLOUD_PROVIDERS``
    (what the Cloud tab lists, and what it marks as the active row);
  * the backend's ``voice_typer/server/cloud/_defaults.py`` →
    ``_PROVIDER_DEFAULTS`` (what the engine actually posts to).

They agree by necessity, not by coincidence. When ``config.cloud_model``
is empty — which is exactly the state the onboarding flow leaves behind,
because it picks a provider without picking a model — the backend serves
``_PROVIDER_DEFAULTS[provider]["model"]`` while the Cloud tab marks
``CloudProvider.defaultModel`` as the active row. A drift between the two
therefore shows the user one model as "Active" while transcribing with a
different one, silently.

This test parses the TypeScript source (no TS toolchain in the Python
suite) with a regex anchored on the three contiguous fields of each
provider entry, and fails loudly if the parse itself finds the wrong
number of entries — a catalogue that grows must not be able to pass by
being unparseable.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from voice_typer.server.cloud._defaults import _PROVIDER_DEFAULTS

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CATALOGUE_TS = (
    _REPO_ROOT
    / "voice_typer"
    / "client"
    / "src"
    / "renderer"
    / "src"
    / "lib"
    / "utils"
    / "models.ts"
)

# `key` → `url` → `defaultModel`, the three fields every provider entry
# opens with. The model ARRAYS that follow contain `id:`, never `key:`,
# so this cannot pick up a model row.
_ENTRY_RE = re.compile(
    r'key:\s*"(?P<key>[a-z0-9_-]+)"\s*,\s*'
    r'url:\s*"(?P<url>[^"]+)"\s*,\s*'
    r'defaultModel:\s*"(?P<model>[^"]+)"',
)


def _catalogue_entries() -> dict[str, dict[str, str]]:
    source = _CATALOGUE_TS.read_text(encoding="utf-8")
    entries: dict[str, dict[str, str]] = {}
    for match in _ENTRY_RE.finditer(source):
        key = match.group("key")
        # A duplicate key would mean the regex is matching something that
        # is not a provider entry (or the catalogue repeats a provider).
        assert key not in entries, f"duplicate provider key {key!r} in models.ts"
        entries[key] = {
            "url": match.group("url"),
            "model": match.group("model"),
        }
    return entries


def test_the_typescript_catalogue_is_parseable() -> None:
    """Guard the guard: a silently-empty parse would make every
    comparison below vacuous."""
    entries = _catalogue_entries()
    assert entries, f"no CLOUD_PROVIDERS entries parsed out of {_CATALOGUE_TS}"
    assert set(entries) == set(_PROVIDER_DEFAULTS), (
        "the renderer catalogue and _PROVIDER_DEFAULTS describe different "
        f"providers: ts={sorted(entries)} python={sorted(_PROVIDER_DEFAULTS)}"
    )


@pytest.mark.parametrize("provider", sorted(_PROVIDER_DEFAULTS))
def test_endpoint_matches(provider: str) -> None:
    assert _catalogue_entries()[provider]["url"] == _PROVIDER_DEFAULTS[provider]["url"]


@pytest.mark.parametrize("provider", sorted(_PROVIDER_DEFAULTS))
def test_default_model_matches(provider: str) -> None:
    """The load-bearing one: see the module docstring for why a drift here
    is a silent lie in the UI rather than a visible failure."""
    assert (
        _catalogue_entries()[provider]["model"]
        == _PROVIDER_DEFAULTS[provider]["model"]
    )
