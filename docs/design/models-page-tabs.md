# Models page tabs

The Models page has three tabs for everyone — **Local**, **Cloud** and
**Text-to-Speech** — plus a fourth, **Plugins**, that only the owner can see.
The title-bar switcher and the page share one zustand store
(`stores/useModelsTab.ts`), so the selected tab survives navigation within a
session. The switcher uses the recessed ToggleGroup variant; the panels are
named regions, not `tabpanel`s (there is no `tablist` to belong to).

## Hidden Plugins tab

Plugins used to be a standalone page. Their content now lives in
`components/models/PluginsPanel.tsx`, mounted only on the hidden tab. The old
route is an alias to Models (`router/routes.ts`), and App redirects a stale
`plugins` route to Models without opening the tab.

Two gates must both pass for the tab to exist:

1. **Client:** `developer_mode` is on. The owner reveals it with
   Ctrl+Shift+Alt+D pressed three times in 1.5 s
   (`hooks/useDeveloperModeUnlock.ts`).
2. **Server:** the `get_plugins` payload answers `available: true`. A frozen
   build or an end user answers false, and no Plugins option is rendered at
   all.

`hooks/usePluginCatalog.ts::usePluginsUnlocked` combines them. The switcher
hides the option; the Models page also refuses to render the panel if the flag
drops while the tab is selected. Neither gate is a security boundary — the
backend still refuses plugin commands when `developer_mode` is off. Plugin
settings remain the two shared config fields (`plugin_visible`,
`plugin_notify`); there is no per-plugin store.

Verification evidence: `ModelsTabSwitcher.plugins.test.tsx` proves the option
is absent with the server flag off and present + selectable with both flags on;
`PluginsPanel.test.tsx` proves the cards, activation toggles and shared
settings still work with fake data; `PageSwitch.test.tsx` proves the legacy
route lands on Models.

## Text-to-Speech tab

Engine ids come from `tts_status.engines`, which is built from the backend's
own engine/pack registry — the renderer has no second id list. Each row is a
shared `ModelVariantRow` with the same action buttons as an ASR row:
**Download** while the pack is missing, **Select** once installed, **Active**
on the running engine, and **Delete** on an installed, non-active engine.
Selection is the `tts_engine` config value; deleting the active engine clears
it through the service's canonical `apply_config` path.

`tts_prepare` streams `tts_prepare_progress` events (`percent` 0–100 across the
whole pack, with the artifact name and byte counts). The row shows a real
determinate `LevelBar` while the download runs, so "downloading" is not just a
spinner. Magpie's `nemo-speech pull` gives no byte stream; that pack reports a
start and a completion step instead of inventing a percentage curve.

Downloads are verified before use: Audio8's pinned GGUF is fetched to
`.partial`, checked for exact publisher-pinned size and `GGUF` magic, then
atomically renamed; Magpie's runtime verifies size + publisher SHA itself. No
new hash was invented for either pack.

## License / dependency notes

Both TTS packs are downloaded from their publishers' Hugging Face repos by the
existing `tts/packs.py` manifest; this change adds no new dependency and no
new network destination. The plugin workloads still run in the user's browser
through their own manifests — the Models tab only changes where their controls
are shown.
