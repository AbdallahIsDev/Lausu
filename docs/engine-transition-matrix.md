# Engine transition matrix

One engine serves dictation at a time: `{local model X | plugin P | none}`.
`config.active_plugin` is the ownership flag; `config.model_size` names the
local model. A plugin taking ownership clears `active_plugin` on local-model
selection; a plugin being enabled never clears `model_size`, but the engine
identity is derived from `active_plugin` first everywhere.

| Source state | User action | Result | Authority |
|---|---|---|---|
| Local model X | Select local model X (same model) | Local X stays active; plugin (if any) released; tray/renderer IDLE | `set_config` payload includes `active_plugin: ""`; `_apply_set_config_under_lock` normalises it even for a no-op model change |
| Plugin P + local model X selected | Select local model X | X becomes active; `active_plugin` persisted as `""`; P browser/daemon shut down via `sync_selection`; sidebar shows X + CPU/GPU; tray shows X | same as above + `sync_selection` |
| Local model X | Enable plugin P | P owns dictation; X is no longer shown as Active; sidebar/tray show P | `set_config {active_plugin: P}` → `sync_selection`; `activeEngine()` and `applyActiveState()` |
| Plugin P | Disable P, no local model selected | Engine NONE; sidebar "No model selected", no loading dot, no CPU/GPU; tray IDLE + no-model message; hotkey refuses with in-app + OS notification | `reconcile_status()` + `activeEngine()` + `hotkey_dispatch` |
| Plugin P | Disable P, local model X installed | X active (normal local load UX) | `sync_selection` releases P; local loader owns LOADING→READY |
| Plugin P | Switch to plugin Q | Old daemon/browser down, Q up; tray/renderer name Q | `sync_selection` deactivate→activate; `reconcile_status()` |
| Any | Startup with plugin P active | No local load; status IDLE named P, not stale LOADING | `_phases_late` + shared `reconcile_status()` |

Status (`idle`/`loading`/`ready`/`error`) belongs only to a LOCAL model load.
The renderer never paints a loading dot when `activeEngine(config).kind !==
"local"`.
