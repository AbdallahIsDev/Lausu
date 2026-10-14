"""Cross-language parity: the cloud provider catalogue vs `_PROVIDER_DEFAULTS`.

Two tables describe the same four providers, and they must agree on the
endpoint and on the DEFAULT model:

  * the renderer's catalogue,
    ``client/src/renderer/src/lib/utils/cloudCatalog.ts`` → ``CLOUD_PROVIDERS``
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
from voice_typer.server.cloud._realtime import REALTIME_MODELS, WS_REALTIME_MODELS

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
    / "cloudCatalog.ts"
)

# `key` → `url` → `defaultModel`, the three fields every provider entry
# opens with. The model ARRAYS that follow contain `id:`, never `key:`,
# so this cannot pick up a model row.
_ENTRY_RE = re.compile(
    r'key:\s*"(?P<key>[a-z0-9_-]+)"\s*,\s*'
    r'url:\s*"(?P<url>[^"]+)"\s*,\s*'
    r'defaultModel:\s*"(?P<model>[^"]+)"',
)

# Model blocks are the only `{ id: "...", ... }` shapes in the catalogue;
# the non-greedy body stops at the block's own close (fields are scalars).
_MODEL_BLOCK_RE = re.compile(
    r'\{\s*id:\s*"(?P<id>[^"]+)"(?P<body>.*?)\}',
    re.DOTALL,
)
_PROVIDER_KEY_RE = re.compile(r'key:\s*"(?P<key>[a-z0-9_-]+)"')
_REALTIME_FLAG_RE = re.compile(r"realtimeOnly:\s*true")
_WS_FLAG_RE = re.compile(r"realtimeWs:\s*true")


def _catalogue_realtime_ids() -> set[tuple[str, str]]:
    """(provider, id) pairs the renderer flags `realtimeOnly`."""
    source = _CATALOGUE_TS.read_text(encoding="utf-8")
    flagged: set[tuple[str, str]] = set()
    for block in _MODEL_BLOCK_RE.finditer(source):
        if not _REALTIME_FLAG_RE.search(block.group("body")):
            continue
        keys = [m.group("key") for m in _PROVIDER_KEY_RE.finditer(source, 0, block.start())]
        assert keys, f"model {block.group('id')!r} sits outside any provider block"
        flagged.add((keys[-1], block.group("id")))
    return flagged


def _catalogue_ws_ids() -> set[tuple[str, str]]:
    """(provider, id) pairs the renderer flags `realtimeWs`."""
    source = _CATALOGUE_TS.read_text(encoding="utf-8")
    flagged: set[tuple[str, str]] = set()
    for block in _MODEL_BLOCK_RE.finditer(source):
        if not _WS_FLAG_RE.search(block.group("body")):
            continue
        keys = [m.group("key") for m in _PROVIDER_KEY_RE.finditer(source, 0, block.start())]
        assert keys, f"model {block.group('id')!r} sits outside any provider block"
        flagged.add((keys[-1], block.group("id")))
    return flagged


def _catalogue_entries() -> dict[str, dict[str, str]]:
    source = _CATALOGUE_TS.read_text(encoding="utf-8")
    entries: dict[str, dict[str, str]] = {}
    for match in _ENTRY_RE.finditer(source):
        key = match.group("key")
        # A duplicate key would mean the regex is matching something that
        # is not a provider entry (or the catalogue repeats a provider).
        assert key not in entries, f"duplicate provider key {key!r} in cloudCatalog.ts"
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


def test_realtime_flags_match_backend_capability_set() -> None:
    """The renderer's `realtimeOnly` rows and `REALTIME_MODELS` name the
    same ids: a model flagged on one side only is either selectable-but-
    untranscribable or guarded-nowhere (both silent)."""
    assert _catalogue_realtime_ids() == set(REALTIME_MODELS)


def test_ws_flags_match_backend_ws_capability_set() -> None:
    """The renderer's `realtimeWs` rows and `WS_REALTIME_MODELS` name the
    same ids: the app WS transport covers exactly these OpenAI sessions."""
    assert _catalogue_ws_ids() == set(WS_REALTIME_MODELS)
