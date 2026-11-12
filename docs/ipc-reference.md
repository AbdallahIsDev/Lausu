# IPC Reference

Auto-generated reference for the Lausu IPC protocol.

**Source of truth:**

- [_COMMAND_REGISTRY](../voice_typer/server/ipc/registry.py): server-side handler map (canonical command list)
- [allowed_commands()](../src-tauri/src/commands/sidecar_cmds/allowlist.rs): Rust host's renderer-reachable allowlist gate (CR-4 / SEC-019)
- [types/ipc/](../voice_typer/client/src/renderer/src/types/ipc/): TypeScript subpackage: requests, push_events, bridge, enums, etc.

> This file is a human-readable summary. The sources above are the
> authoritative references; if this doc disagrees with any of them, the
> source files win.

## Two-allowlist contract (post-predecessor / post-TCP)

Every IPC command must exist in the places below to be reachable from
the renderer:

1. **Server registry** (`_COMMAND_REGISTRY` in `voice_typer/server/ipc/registry.py`):
   maps `command_name` to `_handler_method` on the `IPCServer` class.
   Without an entry here, the server returns
   `{type:"error", data:{code:"unknown_command"}}`.
2. **Rust allowlist** (`allowed_commands()` in
   `src-tauri/src/commands/sidecar_cmds/allowlist.rs`): defense-in-depth
   backstop for the Tauri host path (CR-4). The Rust host forwards only
   names in this set, so a compromised renderer cannot reach handlers it
   was never meant to invoke.
3. **Renderer types** (`PythonRequest` / `PythonPushEvent` in the
   `types/ipc/` subpackage): TypeScript unions that give the renderer
   compile-time type safety for the request/response shapes.

The TypeScript `ALLOWED_COMMANDS` Set is **gone** (predecessor main deleted
with the Tauri cutover). Do not reintroduce it.

The parity tests `tests/test_ipc_command_parity.py` and
`tests/test_security_doc_command_count.py` assert that the Rust
`allowed_commands()` set is a subset of `_COMMAND_REGISTRY` and that the
ONLY registry commands outside the Rust allowlist are the documented
host-dispatched / host-only set (`heartbeat`, `relaunch_ack`,
`shutdown`, `tray_click`). Commands in `_COMMAND_REGISTRY` but NOT in
`allowed_commands()` are host-internal (invoked by the Rust host via
`dispatch_inner` or host-supervised shutdown), never by the renderer.

## Commands (109 total: 105 renderer-reachable + 4 host-dispatched: shutdown, tray_click, heartbeat, relaunch_ack)

Grouped by namespace. "✓" in the Allowlist column means the command is
in `allowed_commands()` (renderer-reachable); "—" means host-dispatched
/ host-only.

### System / config / heartbeat

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `get_config` | `_handle_get_config` | ✓ |  |
| `get_defaults` | `_handle_get_defaults` | ✓ |  |
| `get_status` | `_handle_get_status` | ✓ | Also carries the denoiser truth (`C-UI-15`): `noise_suppression` for the dictation chain and `level_monitor_noise_suppression` for the level-meter/mic-test chain, each `{enabled, requested, effective, degraded, reason_code}` or `null` (see `audio_filters/effective_backend.py`). |
| `heartbeat` | `_handle_heartbeat` | — | Host-dispatched watchdog tick via `dispatch_inner`. Kept out of the renderer allowlist so a compromised WebView cannot spoof ticks. |
| `relaunch_ack` | `_handle_relaunch_ack` | — | Host-dispatched PERF-005 relaunch ack (fire-and-forget). Kept out of the renderer allowlist so a compromised WebView cannot race the restart-wait event. |
| `open_mic_settings` | `_handle_open_mic_settings` | ✓ | Opens the OS microphone-privacy settings page (the recovery path when the input device grant is missing). |
| `set_config` | `_handle_set_config` | ✓ |  |

### App control (toggle, undo, repaste, tray, force-cancel, restart/quit)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `force_cancel_transcription` | `_handle_force_cancel_transcription` | ✓ | 3×90s watchdog timeout. |
| `quit_app` | `_handle_quit_app` | ✓ |  |
| `repaste_last` | `_handle_repaste_last` | ✓ | UX-23: re-paste the last transcription (repaste_handlers mixin). |
| `restart_app` | `_handle_restart_app` | ✓ |  |
| `set_tray_locale` | `_handle_set_tray_locale` | ✓ | TRAY-008: allows set_tray_locale so tray labels update when the user changes the UI locale. |
| `shutdown` | `_handle_shutdown` | — | Cooperative shutdown: handler runs identically on TCP / stdin / WS. |
| `toggle_dictation` | `_handle_toggle_dictation` | ✓ |  |
| `tray_click` | `_handle_tray_click` | — | Host-only: Rust tray dispatcher invokes via `dispatch_inner`, so a renderer `dispatch` call returns "unknown command". |

### macOS permissions (accessibility troubleshooting)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `reset_macos_accessibility` | `_handle_reset_macos_accessibility` | ✓ | Finding #127 part b: Settings → Troubleshooting "Reset Accessibility Permission" button. Runs `tccutil reset Accessibility <bundle-id>` (bundle ID resolved at runtime via `macos_bundle_id.py` Never hardcoded) and re-opens System Settings → Privacy & Security → Accessibility. `ack` → `{ok, command, error}`. |
| `reset_linux_permissions` | `_handle_reset_linux_permissions` | ✓ | Finding #127 part b (Linux sibling), Settings → Troubleshooting "Reset Linux Permission" button. Clears a stale polkit authorization (`auth_admin_keep` is cached ~5 min by polkitd, see finding #134) by restarting the polkit daemon via `pkexec systemctl restart polkit` / `polkitd` / `service polkit restart`; `pkaction` enumerates the Lausu action (`com.Lausu.install-permissions` The only namespace the app ships since finding #54; the legacy pre-Tauri predecessor policy is removed at install/upgrade time) and `pkcheck` verifies the post-reset state. pkexec exit 126 (auth dismissed) is reported as such. `ack` → `{ok, command, error, actions, checks}`. |
| `check_accessibility` | `_handle_check_accessibility` | ✓ | Finding #919 part b: RE-ADDED 2026-08-10. Settings → Troubleshooting probes the macOS Accessibility grant on mount; on a confirmed stale grant (`AXIsProcessTrusted()` False) the `accessibility_status` response carries `suggest_reset: true` + the runtime `reset_command` string (`tccutil reset Accessibility <bundle-id>`, bundle ID resolved via `macos_bundle_id.py` Never hardcoded) so the section can surface it next to the "Reset Accessibility Permission" button. Was removed in the GT-32 stale-entry cleanup (no renderer caller); re-wired through the registry + TS + Rust allowlists in lockstep. `accessibility_status` → `{granted, platform, reason?, suggest_reset?, reset_command?}`. |
| `undo_last` | `_handle_undo_last` | ✓ |  |

### Onboarding wizard

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `onboarding_apply` | `_handle_onboarding_apply` | ✓ |  |
| `onboarding_check_permissions` | `_handle_onboarding_check_permissions` | ✓ | Probes the OS keyboard-monitoring permission state (macOS Accessibility / Linux input group). Consumed by the Dashboard/Settings `KeyboardPermissionBanner`; the wizard's dedicated Permissions step was removed (2026-09-14). |
| `onboarding_get_hotkey_presets` | `_handle_onboarding_get_hotkey_presets` | ✓ |  |
| `onboarding_get_microphones` | `_handle_onboarding_get_microphones` | ✓ |  |
| `onboarding_get_model_options` | `_handle_onboarding_get_model_options` | ✓ |  |
| `onboarding_is_first_run` | `_handle_onboarding_is_first_run` | ✓ |  |
| `onboarding_next_step` | `_handle_onboarding_next_step` | ✓ |  |
| `onboarding_prev_step` | `_handle_onboarding_prev_step` | ✓ |  |
| `onboarding_reset` | `_handle_onboarding_reset` | ✓ | G4-M-10 + PVT-G5-025 (session-3 + 5): onboarding reset, invoked by the Onboarding wizard's "Start over" button. |
| `onboarding_set_hotkey` | `_handle_onboarding_set_hotkey` | ✓ |  |
| `onboarding_set_microphone` | `_handle_onboarding_set_microphone` | ✓ |  |
| `onboarding_set_model` | `_handle_onboarding_set_model` | ✓ |  |
| `onboarding_set_backend` | `_handle_onboarding_set_backend` | ✓ | Persists the Model step's explicit local-vs-cloud backend choice. |
| `onboarding_skip` | `_handle_onboarding_skip` | ✓ | Marks onboarding complete without persisting selections. The renderer no longer calls it (onboarding is mandatory since 2026-09-14); the backend route stays for backward compatibility. |
| `onboarding_start` | `_handle_onboarding_start` | ✓ |  |

### Models (download, import, delete, status, prewarm, cloud test, trusted endpoints)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `cancel_model_download` | `_handle_cancel_model_download` | ✓ | NEW-PRIV-011: allows cancel_model_download so the renderer can cancel an in-progress download. |
| `delete_model` | `_handle_delete_model` | ✓ | NEW-UX-005: allows delete_model so the renderer can actually delete model files from disk. |
| `download_model` | `_handle_download_model` | ✓ |  |
| `get_download_queue` | `_handle_get_download_queue` | ✓ | Models page: read-only pending-download FIFO snapshot (model names, front first) for mount hydration of the queue chips. |
| `get_model_catalog` | `_handle_get_model_catalog` | ✓ | Models page: VRAM, languages, speed/accuracy ratings. |
| `get_model_status` | `_handle_get_model_status` | ✓ |  |
| `get_volume_backend_status` | `_handle_get_volume_backend_status` | ✓ | Ducking-backend name + capability flags, plus a LIVE `output_level` (never cached — the Microphone page decides its one-time "your speakers are loud" offer from it). |
| `set_output_volume` | `_handle_set_output_volume` | ✓ | Listen-Live S1 `[Lower to 75%]` offer: the only user-pressed speaker-knob write outside dictation ducking. Payload `{ level }` clamped to `[0, 1]`. Response: `{ ok, level }`. |
| `get_prewarm_status` | `_handle_get_prewarm_status` | ✓ | RESTORED 2026-08-14 (plan §6.3 addendum): Cache Status card probe, reads the worker's cache stats (status file `prewarm-status.json` under the config dir). Response: `{ enabled, cache_ratio, cache_label, cached_bytes, total_bytes, last_run, elapsed_s }`. |
| `open_prewarm_log` | `_handle_open_prewarm_log` | ✓ | RESTORED 2026-08-14 (plan §6.3 addendum): opens the worker log (`worker.log` The retired `prewarm.log` no longer exists). |
| `open_data_folder` | `_handle_open_data_folder` | ✓ | Models storage card + Diagnostics button: opens the app config (data) dir in the OS file manager (support case, not the raw hub). Response: `{ opened, path, reason? }`. |
| `run_prewarm` | `_handle_run_prewarm` | ✓ | RESTORED 2026-08-14 (plan §6.3 addendum 2nd half): re-implemented. The handler re-runs the worker's warm phase in-process via `prewarm.status.run_prewarm_now()` (warm_imports_for_worker on a daemon thread + status-file refresh) instead of spawning the retired standalone-prewarm subprocess. Response: `{ started: bool }`. |
| `import_model` | `_handle_import_model` | ✓ | MODEL-IMPORT: allows import_model so the Models page can scan and import pre-downloaded model directories. |
| `pause_model_download` | `_handle_pause_model_download` | ✓ | NEW-PAUSE-001: pause/resume in-progress model downloads. |
| `resume_model_download` | `_handle_resume_model_download` | ✓ |  |
| `test_cloud_connection` | `_handle_test_cloud_connection` | ✓ | Cloud ASR/LLM endpoint reachability probe: invoked from Settings → Models → Cloud "Test connection" button. Handler: `cloud_test_handlers.py`. |
| `add_trusted_endpoint` | `_handle_add_trusted_endpoint` | ✓ | ADR-0017 §"Runtime Extensions": extends the per-process URL allowlist at runtime so users can configure self-hosted ASR/LLM endpoints. Handler: `config_handlers.py`. |

### Text-to-speech (local TTS engines)

Both engines run natively from a `nemo-speech` binary (no Python/ONNX model
runtime). Packs live under `<HF cache>/tts/{bin,models}/<engine>`.

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `tts_status` | `_handle_tts_status` | ✓ | Models page TTS card: `{ engine, enabled, voice, language, voices, languages, sample_cached, engines }` where `sample_cached` is `engine → voice → language → bool` computed from the sample resolver without rendering. Read-only. |
| `tts_prepare` | `_handle_tts_prepare` | ✓ | Downloads one engine's runtime + pack. Payload `{ engine }`; idempotent. |
| `tts_speak` | `_handle_tts_speak` | ✓ | Renders a clip (or plays the cached sample) and starts playback, returning as soon as audio STARTS: `{ ok: true, engine, voice, duration_s, cached, ... }`. A failure is `{ ok: false, error }` where `error` ∈ `not_installed` / `no_output` / `generic` (the renderer maps it to plain-language copy; the raw engine message, HTTP status and body tail stay in the log). Payload `{ text?, engine?, voice?, sample? }`. |
| `tts_stop` | `_handle_tts_stop` | ✓ | Interrupts the clip that is playing. No payload; response `{ stopped: bool }`. |

### Model providers (registry, keys, per-domain routing)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `provider_list` | `_handle_provider_list` | ✓ | Provider rows (capability badges, masked key status) plus the three domain selections. Read-only. |
| `provider_models` | `_handle_provider_models` | ✓ | `{ provider, domain?, refresh? }` → catalogue from the persisted TTL cache (stale entries still list the selected model). |
| `provider_test` | `_handle_provider_test` | ✓ | Real connection probe. A keyed provider runs its authenticated probe (`openrouter` → `GET /api/v1/key`, because `/models` is public and cannot prove a key), so a revoked key returns `server.provider_auth_required`; the response carries `auth` with the probe result. Typed provider envelope on failure. |
| `provider_set_key` | `_handle_provider_set_key` | ✓ | `{ provider, key }` → stored in the credential store, never echoed (masked read only). Invalidates that provider's catalogue. |
| `provider_clear_key` | `_handle_provider_clear_key` | ✓ | Deletes one provider key without touching the others. |
| `provider_set_domain` | `_handle_provider_set_domain` | ✓ | `{ domain, provider?, model_id?, enabled?, consent? }` → persists through the validated `set_config` path (SEC-002); rejects an unknown provider, an unadvertised domain or a model the catalogue does not list. |

### Offline transcription (runtime-pack worker)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `transcribe_offline` | `_handle_transcribe_offline` | ✓ | Master plan §7.4: slim core forwards this request to the runtime-pack worker over the worker's dedicated WS hop. The worker may take seconds to minutes to transcribe, so the result is returned asynchronously via the `transcribe_offline_result` push event rather than a synchronous response. |
| `check_offline_pack_update` | `_handle_check_offline_pack_update` | ✓ | Auto-update feature (docs/auto-update-feature.md): runtime-pack manifest check against GitHub Releases + always-on background download (no consent gate). |

### Media transcription (ADR-0023 universal media-to-text, local files first)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `media_transcribe_start` | `_handle_media_transcribe_start` | ✓ | ADR-0023: start a background media job (`{source, export_path?, export_format?, use_subtitles?, client_id?}`); `source` is a local media path or a remote URL (URL jobs are gated by `media_url_consent`, consent error code `client.consent_required`; `server.no_model` when no speech model is selected; `server.job_busy` at the concurrency cap). Up to `max_jobs` jobs run at once — the ack is immediate and URL resolution/download happen inside the job thread. `client_id` is the renderer's own correlation token (optional, ≤64 chars); it is echoed on the ack and on every event for that job so a push that beats the ack still lands on the right row. Ack: `{job_id, client_id, status: "running"}`. Progress/completion/failure arrive via `media_transcribe_progress` / `media_transcribe_complete` / `media_transcribe_error`, each carrying the `job_id` and `client_id` that produced it. |
| `media_transcribe_cancel` | `_handle_media_transcribe_cancel` | ✓ | ADR-0023: cooperative cancel of ONE job (`{job_id}`) or of every running job (no `data`); returns `{cancelled: <count>, job_ids: [...]}`. |
| `media_transcribe_status` | `_handle_media_transcribe_status` | ✓ | ADR-0023: `{jobs: [snapshot...], max_jobs: <int>}` for every RUNNING job, in start order. `max_jobs` is the backend's concurrency cap — the renderer disables its inputs from it instead of hardcoding a number. |

### History (CRUD, favorites, search, today stats, count, transcription text)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `clear_history` | `_handle_clear_history` | ✓ |  |
| `delete_history` | `_handle_delete_history` | ✓ |  |
| `get_favorites` | `_handle_get_favorites` | ✓ |  |
| `get_history` | `_handle_get_history` | ✓ |  |
| `get_history_count` | `_handle_get_history_count` | ✓ | Dashboard "Total Dictations" stat: returns the count of stored history rows without transferring the full row list. |
| `get_transcription_text` | `_handle_get_transcription_text` | ✓ | History page expansion: fetches the full transcription text for a single history row by id. |
| `get_today_stats` | `_handle_get_today_stats` | ✓ |  |
| `restore_history` | `_handle_restore_history` | ✓ |  |
| `search_history` | `_handle_search_history` | ✓ |  |
| `toggle_favorite` | `_handle_toggle_favorite` | ✓ |  |

### Vocabulary (save, get)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `get_vocabulary` | `_handle_get_vocabulary` | ✓ |  |
| `save_vocabulary` | `_handle_save_vocabulary` | ✓ |  |
| `get_correction_usage` | `_handle_get_correction_usage` | ✓ |  |
| `test_vocabulary_correction` | `_handle_test_vocabulary_correction` | ✓ |  |

### Templates

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `get_templates` | `_handle_get_templates` | ✓ |  |
| `save_templates` | `_handle_save_templates` | ✓ |  |

### Microphones (list)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `get_microphones` | `_handle_get_microphones` | ✓ |  |
| `get_plugins` | `_handle_get_plugins` | ✓ | Installed plugins, their manifests, each one's active flag, and its persisted setting values. |
| `set_plugin_setting` | `_handle_set_plugin_setting` | ✓ | Persists one manifest-declared setting. Payload `{plugin_id, key, value}`; the key must exist in that plugin's manifest and the value must match its declared type/range. Stored in the plugin workspace (`settings.json`), never app config. |

### Microphone test (start, stop, cancel, level)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `microphone_test_cancel` | `_handle_microphone_test_cancel` | ✓ |  |
| `microphone_test_get_level` | `_handle_microphone_test_get_level` | ✓ |  |
| `microphone_test_start` | `_handle_microphone_test_start` | ✓ | Microphone test commands |
| `microphone_test_status` | `_handle_microphone_test_status` | ✓ | Running-state read used by the Microphone page on mount to re-attach to a test already in flight. |
| `microphone_test_stop` | `_handle_microphone_test_stop` | ✓ |  |
| `microphone_test_read_audio` | `_handle_microphone_test_read_audio` | ✓ | Chunked slice of a persisted mic-test WAV (path/offset/length); recordings-dir containment enforced |
| `get_microphone_volume` | `_handle_get_microphone_volume` | ✓ | Mic guard (S5): reads the real OS capture gain. Response: `{ available, level, supports_set, name }`; `supports_set: false` (most built-in macOS mics) means the renderer shows the guard message WITHOUT a restore button. |
| `set_microphone_volume` | `_handle_set_microphone_volume` | ✓ | Mic guard (S5): the `[Back to 100%]` write. Payload `{ level }` clamped to `[0, 1]`; always writes (the guard's anti-flap budget only bounds its OWN automatic restores). Response: `{ ok, level }`. |

### Screenshot (beta capture + consent)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `screenshot_capture` | `_handle_screenshot_capture` | ✓ | Screenshot beta: capture the current screen for the OCR/vision path. |
| `screenshot_clear_cycle` | `_handle_screenshot_clear_cycle` | ✓ | Screenshot beta: drop the current capture cycle's staged files. |
| `screenshot_get_status` | `_handle_screenshot_get_status` | ✓ | Screenshot beta: enabled flag + whether consent has been recorded. |
| `screenshot_set_consent` | `_handle_screenshot_set_consent` | ✓ | Screenshot beta: persist the user's consent decision (reads are still gated by the beta flag). |

### Continuous level monitor

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `level_monitor_start` | `_handle_level_monitor_start` | ✓ | Continuous level monitor |
| `level_monitor_stop` | `_handle_level_monitor_stop` | ✓ |  |
| `live_preview` | `_handle_live_preview` | ✓ | `{enabled: bool}` → `{active, monitoring, sample_rate, filtered}`; frames arrive as `live_preview_audio` push events (post-chain PCM16, base64) |

### Hotkey / ESC cancel

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `set_esc_cancel_paused` | `_handle_set_esc_cancel_paused` | ✓ | Pauses ESC-cancel while the UI is capturing a custom hotkey. |

### Voice conversation (push-to-talk STT → LLM → TTS)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `chat_listen_start` | `_handle_chat_listen_start` | ✓ | Arms capture on the level monitor's single `InputStream` (never a second stream). Refused while a turn is in flight (`{started: false, sample_rate: 0}`). Gated by `voice_biometric_consent`, like dictation and the mic test. Response `{started: bool, sample_rate: int}`; publishes `chat_turn` with `phase: "listening"` on success. |
| `chat_listen_stop` | `_handle_chat_listen_stop` | ✓ | Disarms capture and starts the turn on a daemon thread; returns `{accepted: bool}` immediately. A capture nobody released (page unmounted mid-hold) is auto-finished at the 30 s cap. |
| `chat_state` | `_handle_chat_state` | ✓ | Read-only reattach snapshot: `{messages: [{role, text}], busy: bool, phase: str}`. |
| `chat_reset` | `_handle_chat_reset` | ✓ | Aborts any in-flight turn, clears the message list and cancels capture; publishes `phase: "idle"`. Response `{ok: bool}`. |

### GPU / CUDA install (device switch)

| Command | Handler | Allowlist | Notes |
|---------|---------|-----------|-------|
| `get_gpu_capability` | `_handle_get_gpu_capability` | ✓ | Read-only capability snapshot: `{state, hardware_present, driver_present, gpu_names, cuda_ready, stack_complete, backends: [{name, local, gpu_capable, gpu_ready, detail}], download: {supported, reason, total_bytes, python, installed, progress}, driver_url, activation, active_backend, active_backend_gpu_ready}`. **Two readiness signals, deliberately different.** `cuda_ready` = ANY gpu-capable local backend is ready — coarse, kept for the state verdict, and **never** a gate. `stack_complete` = EVERY gpu-capable local backend is ready (CTranslate2 **and** ORT) — the signal an install must satisfy before `device: "cuda"` is persisted, and what `set_config` + activation require. `active_backend_gpu_ready` = the backend named by `asr_backend` can serve GPU; always a boolean (falls back to `stack_complete` when no backend is known) and the signal the sidebar toggle and the request dialog use. `state` is the four-value coarse verdict (`no_nvidia_gpu` / `driver_missing` / `gpu_present_cuda_missing` / `gpu_ready`) and **may be `gpu_ready` while `stack_complete` is false** — a machine where CTranslate2 sees the GPU but the installed `onnxruntime` is the CPU-only wheel. Hardware presence is an OS probe; per-backend readiness is the DLL/provider check. |
| `start_cuda_download` | `_handle_start_cuda_download` | ✓ | Starts the single-flight install job (pinned CUDA 12 wheels + the CUDA-12 ONNX Runtime wheel). Returns the live job snapshot; a second call while running returns the same snapshot instead of opening a second transfer. Never writes `config.device`. |
| `cancel_cuda_download` | `_handle_cancel_cuda_download` | ✓ | Instant control: sets the job's cancel event, stops at the next chunk boundary. Returns the snapshot. |
| `ack_cuda_activation` | `_handle_ack_cuda_activation` | ✓ | Clears a recorded activation failure after the renderer has shown it. Response `{ok: bool}`. |

### Removed / never-existed commands (documented for searchability, do NOT re-add)

The following command names appear in older drafts of this document but
are **not** present in `_COMMAND_REGISTRY` and were never reachable from
the renderer. They are listed here so search-engine queries landing on
this page find the canonical "this command does not exist" answer:

`apply_vocabulary_suggestion`,
`delete_all_personal_data`, `dismiss_vocabulary_suggestion`,
`export_diagnostics`, `export_gdpr_bundle`, `get_audio_status`,
`get_rms_level`, `get_vocabulary_suggestions`,
`level_monitor_status`,
`onboarding_get_model_catalog`, `onboarding_get_step`,
`onboarding_request_keyboard_permission`,
`refresh_microphones`, `test_llm_connection`.

> Note: microphone_test_status was listed here (YJ-10 cleanup, zero
> renderer callers) but was RESTORED: the Microphone page reads it on
> mount to re-attach to a test already in flight. It now has a live row
> in the Microphone test table above.

> Note: `check_accessibility` was previously listed here (removed in the
> GT-32 cleanup) but was RE-ADDED on 2026-08-10 (finding #919 part b) —
> it now has a live row in the macOS permissions table above.
>
> Note: `get_prewarm_status` / `open_prewarm_log` / `run_prewarm`
> were listed here (retired with the standalone-prewarm pipeline —
> master plan §6.2 P-1) but were RESTORED on 2026-08-14 (plan §6.3
> addendum: Settings → About Cache Status card, verbatim from
> 5a319872): they now have live rows in the Models table above and
> probe the worker's cache via `prewarm-status.json`. `run_prewarm`
> was restored the same day (addendum 2nd half) as a RE-IMPLEMENTATION
> It re-runs the worker's warm phase in-process via
> `prewarm.status.run_prewarm_now()` (no deleted-subprocess spawn).

> Note: `tts_compare` was added with the first TTS wiring and REMOVED the
> same day — an A/B comparison is not a feature this app needs. The Models
> page drives TTS with the same per-row Download → Select / Active + Test
> actions as the local ASR models, so the A/B machinery (server method,
> registry entry, allowlist entry, renderer call, i18n string) is gone. Do
> not re-add it; the three surviving commands are `tts_status`,
> `tts_prepare` and `tts_speak` (table above).

The corresponding host-side workflows (vocabulary automation pipeline,
GDPR export/delete, diagnostics export, LLM
connection test, onboarding step / model-catalog reads, microphone
refresh, predecessor notification, RMS / audio-status reads, microphone
test status, level monitor status) are all handled
by dedicated service modules invoked directly by the host (not via
the IPC `dispatch` path) or by renderer-reachable substitutes listed
in the tables above: the worker-based prewarm path is reached via
the `transcribe_offline` command and observed via the `pack_*` /
`worker_*` push events; the cache-state read + manual re-warm are the
restored `get_prewarm_status` / `run_prewarm` (worker status file +
in-process warm pass), not the old
`sentinel` / `PID`-file probe.

## Push events (72 typed)

Push events flow server to renderer via `window.python.onEvent(callback)`.
The `PythonPushEvent` union in `types/ipc/push_events.ts` is the canonical
list: events not in the union fall through to the `string` overload of
`usePythonEvent` (BG-84) and lose compile-time typo detection.

| Event type | Interface | Data shape |
|------------|-----------|------------|
| `status_change` | `StatusChangeEvent` | `{ status: string }` |
| `error` | `ErrorEvent` | `{ code: ErrorCodes, message, command?, field?, id? }` |
| `transcription_final` | `TranscriptionFinalEvent` | `{ text: string, ... }` |
| `recording_started` | `RecordingStartedEvent` | bare `{ type: "recording_started" }` Fires when recording actually starts; backs the start sound cue. |
| `recording_stopped` | `RecordingStoppedEvent` | bare `{ type: "recording_stopped" }` Fires when recording actually stops; backs the stop sound cue. |
| `config_changed` | `ConfigChangedEvent` | `{ key?: string, ... }` Emitted after `set_config` so subscribers can refetch without polling. |
| `hotkey_capture_cancel` | `HotkeyCaptureCancelEvent` | bare frame: cancels the Settings hotkey-picker capture dialog. |
| `history_changed` | `HistoryChangedEvent` | `{ reason: string }` |
| `state_changed` | `StateChangedEvent` | `Record<string, unknown>` |
| `paste_failed` | `PasteFailedEvent` | `Record<string, unknown>` |
| `download_progress` | `DownloadProgressEvent` | `Record<string, unknown>` |
| `notification` | `NotificationEvent` | `Record<string, unknown>` |
| `vocabulary_suggestion` | `VocabularySuggestionEvent` | `Record<string, unknown>` |
| `microphones_changed` | `MicrophonesChangedEvent` | `Record<string, unknown>` |
| `microphone_test_complete` | `MicrophoneTestCompleteEvent` | `Record<string, unknown>` |
| `audio_clip` | `AudioClipEvent` | `Record<string, unknown>` |
| `tray_menu` | `TrayMenuEvent` | `Record<string, unknown>` |
| `navigate` | `NavigateEvent` | `Record<string, unknown>` |
| `ready` | `ReadyEvent` | `Record<string, unknown>` |
| `bubble_show` | `BubbleShowEvent` | `Record<string, unknown>` |
| `bubble_hide` | `BubbleHideEvent` | `Record<string, unknown>` |
| `bubble_set_state` | `BubbleSetStateEvent` | `Record<string, unknown>` |
| `bubble_level` | `BubbleLevelEvent` | `Record<string, unknown>` |
| `bubble_config` | `BubbleConfigEvent` | `Record<string, unknown>` |
| `show_window` | `ShowWindowEvent` | `Record<string, unknown>` |
| `quit_app` | `QuitAppEvent` | `Record<string, unknown>` |
| `relaunch_app` | `RelaunchAppEvent` | `Record<string, unknown>` |
| `tray_state` | `TrayStateEvent` | `{ icon?: string, label?: string, ... }` |
| `consent_required` | `ConsentRequiredEvent` | `{ provider: string, ... }` |
| `parakeet_cpu_fallback` | `ParakeetCpuFallbackEvent` | `{ device: string, ... }` |
| `asr_backend_disabled` | `AsrBackendDisabledEvent` | `{ backend: string, reason: string, ... }` Emitted from `asr_registry._record_failure` when a backend trips its failure threshold. |
| `asr_last_resort_unloaded` | `AsrLastResortUnloadedEvent` | `{ backend: string, reason: string, ... }` Emitted when the last-resort ASR backend is force-unloaded. |
| `llm_polish_failed` | `LlmPolishFailedEvent` | `{ reason: string, ... }` Emitted when LLM polishing fails so the UI can fall back to raw transcription. |
| `provider_local_onnx_state` | `ProviderLocalOnnxStateEvent` | `{ model: string, state: string, error?: string }` Model-load lifecycle of the local ONNX text provider (`loading` / `ready` / `failed`), published by `model_providers/local_onnx/client.py`; the Providers page renders the "loading model…" state from it. |
| `reconnecting` | `ReconnectingEvent` | `{ reason: string }` |
| `reconnected` | `ReconnectedEvent` | `{ reason: string }` |
| `mic_level` | `MicLevelEvent` | `{ rms: number, peak: number, active: boolean }` Continuous level monitor stream for the Settings microphone level meter. |
| `device_lost` | `DeviceLostEvent` | `{ source: string }` The active input device disappeared mid-monitoring; the level monitor auto-stops and the Microphone page surfaces a recovery banner + toast. |
| `live_preview_audio` | `LivePreviewAudioEvent` | `{ pcm: string, sample_rate: number, seq: number }` Listen-Live filtered preview frames: one base64 PCM16 LE mono frame per processed chunk while `live_preview` is enabled; published from the level monitor's own `AudioProcessor` chain (`level_monitor/preview_stream.py`) and scheduled for playback by the renderer only. |
| `transcription_partial` | `TranscriptionPartialEvent` | `{ text: string, cycle_id: string, supported?: boolean }` Live partial text pushed ≤4 Hz by the hidden streaming session's coalescing broadcaster; mirrored onto the bubble channel as a `bubble_set_state` transcript so the pill paints words mid-recording. One-time `supported: false` payload signals engines without word-level transcription. |
| `offline_pack_download_started` | `OfflinePackDownloadStartedEvent` | `{ version: string, url: string, total_bytes: number }` Runtime-pack download began; payload mirrors the model-download `download_progress` shape so a `useOfflinePackDownload` hook can reuse the `useModelDownload` UI pattern. |
| `offline_pack_download_progress` | `OfflinePackDownloadProgressEvent` | `{ version: string, progress: number, downloaded_bytes: number, total_bytes: number, speed_bytes_per_sec: number, eta_seconds: number }` Emitted ~1 Hz while the pack is downloading (currently silent, no UI surface, surfaced for diagnostics). |
| `offline_pack_download_completed` | `OfflinePackDownloadCompletedEvent` | `{ version: string, sha256: string }` Download finished; verification is the next step (`offline_pack_verified` / `offline_pack_corrupt`). |
| `offline_pack_download_failed` | `OfflinePackDownloadFailedEvent` | `{ version: string, reason: string, attempts: number }` Download gave up after exhausting the §8.2 / §8.7 retry budgets (corruption recovery + GitHub rate-limit backoff). |
| `offline_pack_verified` | `OfflinePackVerifiedEvent` | `{ version: string, sha256: string }` SHA256 + signature (Windows Authenticode / macOS notarization) both pass; the renderer's "Pack status" badge flips green. |
| `offline_pack_missing` | `OfflinePackMissingEvent` | `{ version: string, path: string }` Expected pack file not found at startup (user deleted it, or a cleaner / AV quarantined it). |
| `offline_pack_corrupt` | `OfflinePackCorruptEvent` | `{ version: string, path: string, reason: string }` SHA256 mismatch or signature verification failed (background checksum §8.16). |
| `offline_pack_ready` | `OfflinePackReadyEvent` | `{ version: string, worker_pid: number }` Worker process started AND prewarmed the ASR engine (Phase 2 of the worker lifecycle per §6.2); queued `transcribe_offline` requests can now be dispatched. |
| `offline_pack_outdated` | `OfflinePackOutdatedEvent` | `{ version: string, min_proto_version: number }` Stale-pack fast-refuse signal from the Tauri host when the pack's `min_proto_version` is outside the host range; the Settings surface offers re-download. |
| `worker_started` | `WorkerStartedEvent` | `{ pid: number, version: string }` Worker process spawned and completed its WS handshake with the slim core; prewarm NOT yet done (see `offline_pack_ready` for that signal). |
| `worker_crashed` | `WorkerCrashedEvent` | `{ pid: number, exit_code: number }` Worker process exited non-zero (or was killed by a signal); the slim core's supervisor restarts it with exponential backoff. |
| `worker_unloaded` | `WorkerUnloadedEvent` | `{ reason: string }` Worker unloaded via idle-timeout path or explicit user action ("Keep offline engine running" toggle off). |
| `transcribe_offline_result` | `TranscribeOfflineResultEvent` | `{ text: string, latency_ms: number }` Pushed by the worker via the slim core when a `transcribe_offline` request completes; delivered as a push event because the worker may take seconds to minutes (a synchronous request/response would time out). |
| `asr_backend_ready` | `AsrBackendReadyEvent` | `{ backend: string, model_size: string }` Background model load finished successfully; the renderer's backend-failure toast surface (if shown) is dismissed. |
| `asr_backend_load_failed` | `AsrBackendLoadFailedEvent` | `{ backend: string, model_size: string, failure_reason: string }` Background model load failed after `set_config` already acked; surfaced as an error toast with an Open Models action. |
| `microphone_permission_revoked` | `MicrophonePermissionRevokedEvent` | bare frame: OS microphone permission was revoked mid-session; the renderer shows the localized permission-revoked bubble surface. |
| `microphone_disconnected` | `MicrophoneDisconnectedEvent` | bare frame: the active recording stream lost the selected device (distinct from `device_lost`, which covers level-monitor paths); renderer shows the shared device-lost toast (deduplicated). |
| `microphone_volume_lowered` | `MicrophoneVolumeLoweredEvent` | `{ level: number, restored: boolean, can_set: boolean }` Mic guard (S5): an outside write moved the OS capture gain off 100%. `restored: true` means the guard already wrote it back (renderer stays silent); otherwise the renderer shows the sticky `[Back to 100%]` note, with the button only when `can_set` (a device with no writable gain gets the message alone). |
| `cloud_fallback_used` | `CloudFallbackUsedEvent` | `{ provider: string, kind: "key" \| "provider" \| "network", reason: string }` A cloud ASR provider failed and the pipeline fell back (typed in the union; renderer consumer optional). |
| `dictation_suppressed` | `DictationSuppressedEvent` | `{ duration: number, recorded_rms: number, reason: string }` A dictation was suppressed before transcription (typed in the union; renderer consumer optional). |
| `tts_playback_state` | `TtsPlaybackStateEvent` | `{ engine: string, voice: string, state: "playing" \| "stopped" \| "finished", cached: boolean }` Local TTS playback transition, published by `server/tts/manager.py` on start, on `tts_stop`, and on natural end, so the icon-only control returns to play without polling. |
| `chat_turn` | `ChatTurnEvent` | `{ phase: "listening" \| "transcribing" \| "thinking" \| "speaking" \| "idle" \| "error", role?: "user" \| "assistant", text?: string, error_code?: string }` Push-to-talk conversation turn (`conversation/manager.py` → `service/chat.py`). `phase` drives the Chat page's indicator; `role`+`text` ride the `thinking` (user transcript) and `speaking` (assistant reply) phases; `error_code` is a namespaced IPC code (`no_speech`, `no_engine_loaded`, `transcription_failed`, `server.internal_error`, or a `ProviderError.code`), never a raw exception string. |
| `cuda_progress` | `CudaProgressEvent` | `{ status: "idle" \| "downloading" \| "verifying" \| "installing" \| "completed" \| "failed" \| "cancelled", artifact: string \| null, artifact_index: number, artifact_count: number, bytes_done: number, bytes_total: number, percent: number, speed_bps: number, eta_seconds: number \| null, error: string \| null }` CUDA install job progress (`cuda_install/service.py`, state changes plus at most 10 Hz while bytes move). The renderer's sticky toast renders this snapshot and never polls; `error` is a namespaced job code (`insufficient_disk`, `unsupported_python`, `unsupported_platform`, `download_failed`, `checksum_mismatch`, `install_failed`, `internal`). |
| `filter_collapse` | `FilterCollapseEvent` | `{ reason: "collapse" \| "silent_take" \| "monitor_collapse", raw_db: number, filtered_db: number, delta_db: number, preset: string, method: string }` The microphone filter chain provably removed the speech. `collapse` / `silent_take` (`recording/filter_divergence.py`, once per process per reason): that take is delivered UNFILTERED (`set_filter_bypass` + raw-shadow swap) instead of arriving blank. `monitor_collapse` (`level_monitor/divergence.py`, once per monitoring or test session): the level meter and mic test bypass the chain and read the raw device for the rest of the session. The renderer shows one toast naming the state and offering the Microphone page, while `preset` / `method` / the dB values stay in the log line. |
| `history_corrupted` | `HistoryCorruptedEvent` | `{ path: string, db_path: string, recovered_count: number }` History DB corruption was detected and recovered (typed in the union; renderer consumer optional). |
| `paste_deferred` | `PasteDeferredEvent` | `{ reason: string, message?: string }` Paste was deferred (e.g. clipboard safety validation held it back; typed in the union; renderer consumer optional). |
| `tray_fallback_notification` | `TrayFallbackNotificationEvent` | `{ title?: string, message?: string }` Tray notification fallback path fired (headless / pystray-only runtimes; Tauri host owns the tray). Generic toast consumer. |
| `media_transcribe_progress` | `MediaTranscribeProgressEvent` | `{ job_id: string, client_id: string \| null, progress: number, phase: "starting" \| "preparing" \| "downloading" \| "loading_model" \| "transcribing", eta_seconds: number \| null, duration_seconds: number \| null, tier: "subtitles" \| "download" \| "stream" \| null, note: string \| null }` ADR-0023 media job progress (0-1); renderer drives a progress bar + cancel. `client_id` is the echo of the start request's token (null when the caller sent none). `tier` is the ingest path in use and `note` a machine-readable degradation tag (e.g. `stream_fallback`); the ROW collapses the internal phases to "Preparing…" / "Transcribing…". |
| `media_transcribe_complete` | `MediaTranscribeCompleteEvent` | `{ job_id: string, client_id: string \| null, row_id: number \| null, chars: number, partial: boolean, tier: "subtitles" \| "download" \| "stream" \| null, quality: {avg_logprob?, no_speech_prob?, chars_per_second?} \| null, note: string \| null, title: string \| null, thumbnail_data_url: string \| null }` ADR-0023 media job done; renderer refreshes History. `partial` marks a cancelled job's saved partial transcript; `row_id: null` means the transcript was empty (nothing persisted). `tier`/`quality`/`note` let the page show the degraded ingest path and the low-confidence tag without a second read. `note: "model_changed"` marks a job cancelled because the active engine changed. `title: null` when the extractor gave none (a local file, or an unnamed stream) — the page then falls back to the source label. `thumbnail_data_url` is an inline `data:<mime>;base64,...` preview, NOT a link: the CSP is `img-src 'self' data:`, and an extractor-supplied remote URL would be an arbitrary third-party image load. `null` means no preview (no thumbnail, or the fetch was refused/too large/not an image) — never a broken image element. |
| `media_transcribe_error` | `MediaTranscribeErrorEvent` | `{ job_id: string, client_id: string \| null, code: string, message: string, details: object \| null }` ADR-0023 media job failed; pushed by `media_ingest/jobs.py` from the job-thread exception handler (E13). `details` carries structured copy inputs (`{count}` for `multi_item_url`). |
| `media_jobs_cancelled_for_model_change` | `MediaJobsCancelledForModelChangeEvent` | `{ count: number }` A model switch waited for the running media jobs, then cancelled them so the engine could be unloaded; each cancelled job still publishes its completion with the partial transcript and `note: "model_changed"`. The renderer shows one toast naming the count. |
| `media_model_switch_refused` | `MediaModelSwitchRefusedEvent` | `{ count: number }` A model switch gave up waiting for media jobs that still hold the engine, so nothing was unloaded or persisted and the current model stays active. Published because the `set_config` ack already reported `status: "loading"`; the renderer shows one toast naming the count. |

## Server-only push events (string-overload, not in the typed union)

These events are published on the server's `EVENT_TYPES` registry and
forwarded over the WS transport, but have no interface in
`types/ipc/push_events.ts` The renderer receives them through the
`usePythonEvent` string overload (BG-84). Documented here for
searchability; promote one to the typed union only when a renderer
consumer needs compile-time typo detection.

| Event type | Emitter | Data shape |
|------------|---------|------------|
| `gpu_cpu_fallback` | `transcription_fallback.py` | `{ device: string, reason: string, ... }` The ASR engine fell back from GPU to CPU; also consumed in-process by the tray notification path (`tray_notifications.on_gpu_cpu_fallback`). |
| `dictation_lost` | `crash_recovery/_store.py` | `{ message: string, recoverable: boolean, recovery_type: string, cycle_id: string }` A dictation was interrupted by a crash; partial text may be recoverable, audio is not. |

## WebSocket transport (Tauri sidecar)

Under the Tauri v2 host (ADR-0020), the renderer↔backend transport
switches from TCP-on-loopback to a localhost WebSocket. The WS transport
reuses the same `_COMMAND_REGISTRY` and the same per-connection rate
limiter as the TCP transport: the only differences are the framing and
the auth handshake.

- **URL scheme**: `ws://127.0.0.1:<ephemeral>`. The Python sidecar binds
  `127.0.0.1:0` (OS-assigned port) and emits
  `{"event":"server_started","port":N}` to stdout for the Rust host to
  discover (no port is hard-coded).
- **Auth frame**: the first frame on a new connection MUST be a JSON
  object of the shape `{type:"auth", token:<hex>, protocol_version?:<int>}`.
  The server compares `token` against `VOICE_TYPER_IPC_TOKEN` using
  `hmac.compare_digest` (constant-time). `protocol_version` is optional
 Older hosts that don't send it continue to function.
- **Protocol version**: `PROTOCOL_VERSION = 1` (see `sidecar_ws.py`).
  When the host sends a `protocol_version` that doesn't match the
  sidecar's, the server logs a `protocol_version_mismatch` WARNING
  (visible in diagnostics as the `[SIDECAR-WS] protocol version skew`
  line) but does NOT reject the connection, version negotiation is
  defense-in-depth, not a security gate.
- **Frame cap**: 1 MiB (`_MAX_FRAME_BYTES = 1 * 1024 * 1024`). Frames
  exceeding the cap are dropped with a `[SIDECAR-WS] frame too large`
  log line and a `dropped` outcome is reported on the send path.
- **Cooperative shutdown**: the host sends a bare
  `{type:"shutdown"}` frame to request graceful teardown; the sidecar
  closes its accept loop, drains in-flight handlers, and exits. This is
  the same `shutdown` handler documented in the App-control table
  above: the WS transport just dispatches it via a synthetic frame
  type rather than the regular `dispatch` envelope.

For the full Python-side module deep dive, see
[`docs/modules/sidecar_ws.md`](modules/sidecar_ws.md); for the Rust host
side, see [`docs/migration/tauri-sidecar-bridge.md`](migration/tauri-sidecar-bridge.md).

## See also

- [python-api.md](./python-api.md): Python class API reference
  (`LausuApp`, `Recorder`, `IpcServer`, etc.).
- [ARCHITECTURE.md](./ARCHITECTURE.md): high-level architecture
  overview (renderer <-> Tauri host <-> Python sidecar).
- [modules/sidecar_ws.md](./modules/sidecar_ws.md): Tauri sidecar
  WebSocket transport module reference.
- [migration/tauri-sidecar-bridge.md](./migration/tauri-sidecar-bridge.md) —
  Tauri ↔ Python sidecar bridge architecture + Rust host layout.
- [CONTRIBUTING.md §6.4](../CONTRIBUTING.md): IPC command parity
  contract (the four-allowlist rule enforced here).
- [SECURITY.md](../SECURITY.md): security model (SEC-002 allowlist,
  SEC-018 TCP auth, SEC-019 renderer gate, SEC-026 sandboxed bubble).
