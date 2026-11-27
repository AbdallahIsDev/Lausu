# Model lifecycle: ASR, TTS, translation (audit, no code changes)

Plain English first. This is a read-only map of how each local model kind is loaded, kept resident, unloaded and awaited today, plus every reader of the two lifecycle settings, every recording-start entry point, the origin guard, and the Round 4 translator-specific code that a unified lifecycle would delete. Every claim has a `file:line`. Everything here is from code/docs reading only — no app was run, so runtime behavior is **UNVERIFIED** unless a test or code path proves it.

## 1. ASR (speech-to-text)

**Load at startup / Fast Startup.** After the ready marker, startup calls `app.models.start_background_load()` (`voice_typer/server/startup_sequence/_phases_late.py:389-391`), skipped when a browser plugin owns dictation (`:376-384`) or `VOICE_TYPER_DEFER_MODEL_LOAD=1` (`:385-388`). `start_background_load` spawns one daemon `ModelLoad` thread (`voice_typer/server/model_manager/_loading.py:281-314`), also skipping when a plugin owns the hotkey (`:283-289`, C-PLUGIN-1). `load_background` prechecks download state, then `load_with_fallback` (`:165-219`). An F2 press during load sets `_pending_dictation`; when the loader finishes it schedules `app._start_dictation` on a zero-delay timer (`:272-279`).

**Fast Startup prewarm is a different thing from ASR model load.** The `fast_startup` toggle gates the *worker's OS-file-cache warm phase* (`voice_typer/worker/_ws_startup.py:33-49`, check at `:81-84`, warm call at `:85-88`). Nothing in `model_manager/` reads `fast_startup`; the ASR model load is gated only by plugin ownership, the dev env var and shutdown state (`_phases_late.py:376-391`). Treating "Fast Startup off" as "no model load" would be wrong.

**Load at record start.** The start path does not block on a load: `recording_lifecycle.py:237-239` deliberately defers it, `_spawn_dictation_start_worker` starts a daemon `DictationStart` worker (recording_lifecycle_start.py:211-277), and the worker calls `app.models.ensure_active_engine_loaded()` (`recording_lifecycle.py:365-367`). `ensure_active_engine_loaded` joins an in-flight background loader instead of starting a duplicate (model_manager/_loading.py:513-521), cancels the idle-unload timer (`:522-523`), then reloads an unloaded engine under `_lazy_init_lock` (`:525-573`). A busy backend rejects and queues `_pending_dictation` (`:491-507`).

**Wait for load.** The stop/transcribe side waits: `dictation_pipeline/transcribe_step.py:104-115` calls `wait_for_active_engine_loaded()` and holds the buffered recording. That helper (`model_manager/_loading.py:443-486`) first returns a ready engine, else joins the background loader bounded by `MODEL_LOAD_TIMEOUT_SECONDS + MODEL_SLOW_LOAD_GRACE_SECONDS` (`:35-39`, constants `120`/`120.0` at `voice_typer/server/asr/registry.py:27,33`), else blocks on `_lazy_init_lock` for `MODEL_WAIT_FOR_READY_SECONDS = 60.0` (`_loading.py:35,473-486`). Media has its own bounded wait, `MEDIA_MODEL_LOAD_WAIT_S = 60.0` (`:41-43,627-641,652-662`), and passes `queue_pending_dictation=False` (`:644`) so no phantom dictation is queued.

**Kept resident + idle logic.** Residency is the active backend registered in `AsrBackendRegistry` (`model_manager/_base.py:138-140`). Every successful load touches LRU and re-arms idle unload (`_loading.py:122-131` → `_lifecycle.py:102-114`). The exact config key is **`model_idle_unload_minutes`** (default `60`, `voice_typer/server/config/_schema.py:372`; IPC-validated `0..1440`, `config_validators/allowlist.py:213`). `_schedule_idle_unload_timer` reads it and disarms when `<= 0` (`_lifecycle.py:138-150`); a single persistent daemon thread `_idle_unload_loop` waits on an Event and fires `_do_idle_unload` at the deadline (`:171-202`). `0` means keep loaded (no deadline, no thread) — pinned by `tests/test_model_idle_unload.py:60-75`. Cloud backend deliberately no-ops `unload()` so idle unload cannot demote it (`cloud_backend.py:146-156`).

**Unload.** `_do_idle_unload` marks deliberate unload, calls `registry.unload`, plus a direct `engine.unload()`, `release_gpu_memory()` and `vad.unload()`, and sets tray IDLE (`_lifecycle.py:204-277`). Model switch unloads+unregisters the old backend (`model_manager/_change.py:247-255`) after waiting for media leases (`:285-297`). Watchdog escalation uses `force_unload_active` (`_lifecycle.py:279-320`). LRU eviction can unload the least-recently-used backend (`_lifecycle.py:39-100`).

## 2. TTS (text-to-speech)

**Load at startup.** Post-ready only (C-START-1): `_phases_late.py:488-493` calls `start_prewarm(app)`. It runs only when `tts_enabled` is true and `tts_engine` is `audio8`/`magpie` (`voice_typer/server/tts/prewarm.py:18-20,37-49`), on a daemon thread (`:63-66`), reaching `service/tts.py:76-79` → `manager.py:517-525` → `TtsService.ensure_started` (`tts/service.py:54-67`) → `RuntimeServer.start`. Runtime specs come from `tts/engines.py` and one process per engine serves HTTP on a loopback port (`tts/runtime_server.py:1-7,43-51`).

**Resident / idle.** No idle timer exists. The `TtsService` is cached on the service instance (`service/tts.py:20-30`), each `RuntimeServer` stays alive and is reused while `server.running` (`tts/service.py:54-67`), and `atexit.register(service.stop)` is the only automatic teardown (`tts/manager.py:95-112`). A pack appearing/disappearing while running rebuilds the service and stops the old one (`manager.py:99-107`). Shutdown calls `manager.shutdown()` → `service.stop()` (`service/tts.py:81-86`, `manager.py:527-532`).

**Await / unload.** `RuntimeServer.start` spawns then blocks on `/health` up to `STARTUP_TIMEOUT_S = 180.0` (`runtime_server.py:24-27,71-96,98-112`). `stop()` terminates, waits `grace_s = 10.0`, then kills and waits again (`:127-138`). `TtsService.stop` stops playback and every runtime (tts/service.py:107-118). No config key controls TTS residency — UNVERIFIED that any exists (grep of config schema/allowlist found only `tts_enabled`, `tts_engine`, `tts_voice`, `tts_language` at `_schema.py:121-128`; the prewarm is opt-out by disabling TTS, not by an idle timeout).

## 3. Translation (Round 4 parallel system)

**Load.** Two entry points: `prewarm(config)` (`translation/service.py:520-538`), and lazy `_ensure_runtime()` inside a translate call (`:253-258,269-272`) via `RuntimeServer.start` with 180 s timeout (`:256`). Settings: `translation_enabled`, `translation_model`, `translation_model_path`, `translation_runtime_path`, `translation_gpu_enabled`, `translation_glossary` (`config/_schema.py:64-83`; cache key at `service.py:495-503`).

**Warm at user record start.** `recording_lifecycle.py:253-261` calls `warm_on_user_record(app.config)` right after `recorder.start()` succeeds. `warm_on_user_record` (service.py:559-597) checks the origin (`:567-575`), the `translation_warm_on_record` toggle (`:576-577`), and that a Stage A engine exists (`:578-581`), then coalesces one daemon `translation-warm` thread (`:544-547,582-597`). It never downloads (`prewarm` at `:527-532`). Browser plugins are deliberately not warmed (ADR `docs/adr/0021-transcription-translation-split.md:182-187`).

**Resident / idle.** One cached module-level service (`service.py:490-517`); `get_service` recreates it when its key changes (`:506-517`). Idle setting **`translation_idle_unload_seconds`** (default `600`, `0` disables; `_schema.py:80`, clamp helper `service.py:53-54,149-154`). `note_activity` resets the deadline (`:319-325`), `start_idle_monitor` starts one daemon watcher (`:327-341`), `_idle_loop` fires `_try_idle_stop` only when it can take the request lock (`:343-376`), and a successful POST calls `note_activity` via `_ensure_runtime` (`:257`). `stop()` signals the watcher and stops the runtime under the shared lock (`:475-487`); `atexit.register(shutdown)` (`:665-684`).

**Await.** `translate_text` waits up to `_WARM_JOIN_TIMEOUT_S = 45.0` for the in-flight warm thread before Stage B (`:56-62,600-611,650-652`). A translate call holds `_lock` for the whole POST so a config change/shutdown cannot tear down the process mid-request (`:260-267`). Disabling translation does not invalidate the cached service (`docs/design/translation-audit.md:136-138`) — UNVERIFIED in the running app.

## 4. Every reader of the two lifecycle settings

**`model_idle_unload_minutes`** (keep-in-memory; `0` = never unload):
- Backend: definition `voice_typer/server/config/_schema.py:372`; validator `voice_typer/server/config_validators/allowlist.py:213`; **only production read** `voice_typer/server/model_manager/_lifecycle.py:144`; comment only at `model_manager/_base.py:78-79` and `cloud_backend.py:150`.
- Renderer: type `types/config.ts:185-190`; option table + normalizer `lib/utils/modelIdleUnload.ts:20-37,47-57`; write on change `components/settings/GeneralSettingsSection.tsx:106-107`; read for the Select value `:165-171`; label/info `:87-88`, i18n copy `i18n/translations/en.json:1333`.
- Tests pinning it: `tests/test_model_idle_unload.py:29,60-109,494-552`; `tests/test_model_idle_unload_ui_options.py:29-32`; `tests/test_model_manager_load_races.py:28,113,198`; `test_model_manager_background_change.py:28`; `test_model_manager_load_success_ritual.py:18`; `test_model_manager_vad_idle_unload.py:27`; `test_config_validators_split.py:86`.

**`fast_startup`**:
- Backend: default `config/_schema.py:113`; validator `config_validators/allowlist.py:199`; worker read `voice_typer/worker/_ws_startup.py:33-49` used at `:81-84`; status read `prewarm/status.py:98-105` used at `:180-186`; change side effect `config_applier_handlers.py:208-231` → `startup_tasks.sync_prewarm_task` (`voice_typer/server/startup_tasks.py:54`); status IPC response `handlers/status_handlers.py:171-181`; comment only `handlers/status_handlers.py:335`.
- Renderer: type `types/config.ts:247`; toggle write `GeneralSettingsSection.tsx:102-103`; checked read `:136-140`; labels `:85-86`; response type includes `enabled` at `components/settings/PrewarmAndUpdates.tsx:54,58` but the card never branches on it (no `.enabled` use — verified by grep).
- Tests: `test_prewarm_status.py:22,42,57,64-68,90,153,166,186`; `test_worker_startup.py:315`; `test_dispatch_config.py:660-675`; `test_protocol_payload_typeddicts.py:54`; `test_config_validators_split.py:65`; `types/__tests__/config-parity.test.ts:275`.

Neither `translation_warm_on_record` nor `translation_idle_unload_seconds` is read anywhere in `voice_typer/client/` (grep: no matches) — both are backend-only today.

## 5. Recording-start entry points

**User origins are set in exactly four places:** hotkey `hotkey_dispatch.py:70-73` (`"hotkey"`), button `handlers/dictation_handlers.py:21-24` (`"button"`), tray `tray_menu.py:261-265` and Tauri tray dispatch `tray_menu.py:460-464` (`"tray"`), dev driver `plugin_dev_driver.py:123-131` (`"dev-driver"`/`hotkey`/`button`/`tray` per command). Service layer just delegates (`service/dictation.py:19-21`); protocol declaration `providers.py:167,280`.

**Local + cloud ASR:** all those entry points call `app.toggle_dictation` (`app_dictation.py:17-34`) → `dictation_gate.decide_toggle` (`:25`) → `recording.toggle()` (`:34`) → `RecordingLifecycle.toggle` (`recording_lifecycle.py:178-191`) → `_toggle_impl` (`recording_lifecycle_start.py:37-121`) → `app._start_dictation()` (`:121`, defined `app_dictation.py:36-38`) → `recording.start()` → `_start_impl` (`recording_lifecycle.py:193-264`). Cloud ASR uses this same path; it is a registered backend selected by config (`cloud_backend.py:130-156`, `hotkey_dispatch.py:87`) — no separate cloud start entry. One non-user path exists: the deferred-load timer calls `app._start_dictation` directly (`model_manager/_loading.py:272-279`).

**Plugins:** `internal_plugin_hook.install` *replaces* `app.toggle_dictation`, `_stop_dictation`, `_cancel_dictation` (`internal_plugin_hook.py:339-394`). Its wrapper authorizes the origin (`:344-350`), calls `decide_toggle` (`:351`), and either routes to the selected browser session `session.toggle()` (`:353-368`) or falls back to the original local toggle when no plugin is selected (`:365-366`). Sessions are built per plugin (`tools/internal_plugins/anthropic_stt/plugin.py:283`, `google_stt/plugin.py:251`, `chatgpt_stt/plugin.py:251`). `PluginSession.toggle/start/_start` (`tools/internal_plugins/_common/bridge/session.py:608-624,702-721,722-886`) sets `_active = True` at `:871-873` and logs the start at `:874-879`. The plugin files are owned/dirty by another session — read-only here; line numbers may move.

**Is there one shared "dictation started" point? No single synchronous call site covers all three families.** Proof:
- Local/cloud start moment is after `recorder.start()` in `_start_impl` (`recording_lifecycle.py:249,253-264`); deferred-load starts bypass `app.toggle_dictation` entirely (`_loading.py:279`).
- Plugin start moment is `_active = True` in the browser session (`session.py:871-873`); it never touches the local recorder.
- Their only common *decision* is `DictationGate.decide` / `decide_toggle` (`dictation_gate.py:48-84`), called from both `app.toggle_dictation` (`app_dictation.py:25`) and the plugin wrapper (`internal_plugin_hook.py:351`). It is a press decision (start **or** stop), not a confirmed start.
- Their only common *published signal* is the `recording_started` event: local publishes it optimistically before the mic opens (`recording_lifecycle.py:245` → `:289` → `recording_lifecycle_start.py:201-209`, rolled back on failure at `recording_lifecycle.py:293-298`); plugin publishes it after a real start (`session.py:881,1234-1252`). `event_bus.publish` is synchronous by default (`event_bus.py:438-484`), so a subscriber *could* be a hook, but the local event is not proof of a successful start.

**Closest server-side seam for a shared hook:** `dictation_gate.decide_toggle` (`dictation_gate.py:80-84`) for "user asked to start" (covers local, cloud and plugin user paths, carries origin via contextvar), paired with a confirmed-start hook at the two real start moments (`recording_lifecycle.py:253-264` and `session.py:871-881`) if confirmation is required. Do not use the `recording_started` event alone as the lifecycle trigger — it fires before the local mic opens and again on plugin starts with different payloads (`recording_lifecycle_start.py:204` has no data; `session.py:1247-1251` adds `{"source": label}`).

## 6. Origin guard and how a shared hook must respect it

`dictation_origin.py:17-42` defines `USER_ORIGINS = {"hotkey", "button", "tray", "dev-driver"}`, a `ContextVar`, `user_action(origin)` and `authorize(caller)` which returns `""` and logs a WARN for a missing origin. `authorize` is called at `app_dictation.py:22-24` and `internal_plugin_hook.py:344-350`; the plugin session only *reads* `current()` for logging (`session.py:723-734`; per-plugin callers at `anthropic_stt/plugin.py:248-252`, `google_stt/plugin.py:221-223`, `chatgpt_stt/plugin.py:221-223`); the translator warm path checks membership itself (`translation/service.py:567-575`).

C-START-USER-1 (AGENTS.md) says starts without a user origin are rejected at the single start entry and every start is logged with its origin. A shared hook must therefore:
1. Be invoked inside an existing `dictation_origin.user_action(...)` context, or call `dictation_origin.authorize(...)` itself and no-op on `""` — never mint an origin of its own.
2. Never be fired from app start, activation, recovery, relaunch, reconnect, page-ready or media (`startup_sequence/_phases_late.py:376-391`, `media` path `_loading.py:593-650`).
3. Carry the origin into any new thread it spawns; `_schedule_timer` starts a fresh thread with no `copy_context()` (`timer_coordinator.py:137-166`), so a deferred timer loses the contextvar. Note the existing deferred start at `_loading.py:279` has **no** `authorize` call in `app_dictation.py:36-38` — flag this as a guard gap (UNVERIFIED whether it is intended to inherit the press; rule text says reject).
4. Keep the gate shared for all engines (`dictation_gate.py:1-7` states local/cloud/plugin all reach it) so a rapid burst cannot fire the hook twice.

## 7. What must be removed (Round 4 translator-specific)

Scope A — the Round 4 lifecycle additions only (the likely target of a unified lifecycle):
- `voice_typer/server/translation/service.py`: idle constants `_IDLE_UNLOAD_DEFAULT_S`, `_IDLE_UNLOAD_MAX_S` (`:53-54`), warm-join constant `_WARM_JOIN_TIMEOUT_S` (`:62`), `_idle_seconds` (`:149-154`), idle fields in `__init__` (`:215-220`), `note_activity` (`:319-325`) and its call in `_ensure_runtime` (`:257`), `start_idle_monitor` (`:327-341`), `_idle_loop` (`:343-362`), `_try_idle_stop` (`:364-376`), idle-stop in `stop()` (`:481-482`), `_idle_seconds` in `_service_key` (`:502`), `prewarm` (`:520-538`), `_warm_lock/_warm_thread/_warm_done/_warm_key` (`:541-547`), `_warm_worker` (`:550-556`), `warm_on_user_record` (`:559-597`), `_wait_for_inflight_warm` (`:600-611`) and its call (`:650`), warm cleanup in `shutdown()` (`:667-678`).
- Call site `voice_typer/server/recording_lifecycle.py:253-261` (the comment + `warm_on_user_record` try/except).
- Config fields `translation_warm_on_record` (`config/_schema.py:76`), `translation_idle_unload_seconds` (`config/_schema.py:80`), validators `config_validators/allowlist.py:168-169`, and test pins `tests/test_config_validators_split.py:138-140,279-280`.
- Whole test file `tests/translation/test_translation_warm_on_record.py` (it exists only for these two settings/lifecycle; `:78-85,318-331,408-428`).
- Docs: ADR-0021 §10(b) `docs/adr/0021-transcription-translation-split.md:182-187`; warm/idle proposal text in `docs/design/translation-chunking.md:6-7,34-35,525,560-561,619-622`; idle-memory note `docs/design/translation-audit.md:136-138`.
- Renderer: **nothing** — neither setting is read in `voice_typer/client/` (verified).

Scope B — only if the owner also retires the entire second text model (do not assume this from Round 4 alone): the `voice_typer/server/translation/` package (9 modules), `dictation_pipeline/translation_steps.py:21-35`, `tools/internal_plugins/_common/delivery.py:43`, `service/model/_delete_import.py:51,114-141`, renderer settings `PostProcessingSettingsSection.tsx:55-59,158,210,228-231` and `TranslationModelDownloadRow.tsx:161`, `types/config.ts:165-170`, i18n `translation_model_missing` in all 8 locales (`en.json:2212` and siblings), benches `bench/bench_translation.py`, `bench/bench_pipeline_translation.py`, `bench/pipeline_bench_common.py:71-90`, and `tests/test_translation.py`, `tests/translation/*`.

## 8. Concerns / UNVERIFIED

- No runtime verification was done; all behavior above is code-derived. Mark UNSPECIFIED-IN-APP: actual idle-unload timing, TTS warm success on a cold machine, translator warm join under load.
- The deferred-load start (`_loading.py:279`) reaches `recording.start()` without an origin check in `app_dictation.py:36-38`; C-START-USER-1 says such starts must be refused at the single entry. Needs an owner decision (honour the earlier press by capturing context, or reject).
- `recording_started` is not a reliable "dictation really started" signal for a lifecycle hook (optimistic local publish at `recording_lifecycle.py:245,289` before `recorder.start()` at `:249`, with rollback at `:293-298`).
- Plugin files are read-only in this session and may be concurrently edited; their line numbers are a snapshot.
- `fast_startup` and ASR model residency are unrelated today (`_ws_startup.py:81-88` vs `_phases_late.py:389-391`); a unified "keep in memory" control must not silently repurpose the Fast Startup toggle.

---

## Round 5 decisions and evidence (dated note 2026-11-27)

This note is layered on the 2026-11-27 audit above. The audit was a snapshot;
the implementation decisions below are current. No previously locked product
rule was rewritten.

### Plain English first

The owner reported that a real browser-plugin dictation with translation on
did not load the translator until AFTER he stopped speaking. He waited 16.3 s
for the translation and saw a log line labelled `[TTS]`. Investigation showed
three separate problems: the Round 4 warm-up hook was only on the local
recorder path, the translator borrowed the text-to-speech runtime logger, and
each model kind had its own lifecycle rules.

Round 5 replaces those with ONE small component:
`voice_typer/server/model_lifecycle/`. A local model kind now registers a short
policy (what it is, how much private memory it needs, when it applies, and how
to load/unload/wait/use it) and inherits the shared start hook, memory guard,
wait rule, per-kind idle clock and shutdown. Adding a kind needs a few lines of
registration, not a new lifecycle system.

### Per-kind policy table (shipped)

| Kind | Residency | Startup preload | Record-start load | Idle clock | Measured private memory |
|---|---|---|---|---|---|
| ASR (speech recognition) | `core` | Unconditional post-ready load, exactly as today (`_phases_late.py:389-391`). `fast_startup` gates only the worker file-cache warm (`_ws_startup.py:81-88`) and OPTIONAL kinds — it never gated ASR residency. | Delegates to existing `ensure_active_engine_loaded`; no second loader. | Existing `model_idle_unload_minutes` clock in `model_manager` (0 = Always). | UNVERIFIED — no runtime DLL on this machine; file is 740 MB. |
| Translation | `optional` | Only if Fast Startup is on AND memory guard passes. | YES on EVERY user start through the shared `dictation_gate.decide_toggle` hook — local, cloud and browser plugins. | Shared component, own clock from last translation use. | ~1.8 GB private / 1404 MB working set (MEASURED 2026-11-27). |
| Text-to-speech | `optional` | Only if `tts_enabled`, valid engine, Fast Startup on AND guard passes; otherwise first actual use. Kept its dedicated post-ready prewarm call site so two threads cannot race the same runtime port. | Not at record start; loaded on first use. | Shared component, own clock from last TTS use. | Magpie ~1.3 GB private; Audio8 ~5.9 GB private after first synthesis (MEASURED 2026-11-27). |

### Hook, timing and memory guard

- Single shared start-intent seam: `dictation_gate.decide_toggle` (`dictation_gate.py:80-84`) on action `start`, called by `app_dictation.py:25` and `internal_plugin_hook.py:351` with `app`. It fires on USER INTENT, earlier than a confirmed mic open, which is better for preloading. It checks `dictation_origin.current()` and no-ops without a user origin; it never mints one and never runs from app start/recovery. Starting loads happen on one daemon thread, never on the hotkey/UI thread.
- Load order is by need: ASR, translation, then TTS last; sequential, with per-kind single-flight. The stop side waits on one shared rule with one 45 s timeout; on failure/timeout the original text is kept and one notice is shown.
- Memory guard (`model_lifecycle/memory.py`): `available > estimate + 512 MiB`, using physical RAM from fixed-width `GlobalMemoryStatusEx` on Windows. 512 MiB covers the app baseline, allocator overhead and a concurrent dictation. If memory cannot be read the guard FAILS CLOSED and logs one INFO line; the user sees no error, and a real need later still loads the kind. VRAM per process cannot be read reliably here (only whole-GPU samples exist); the guard uses host RAM only.
- Shutdown calls `shutdown_all()` from `shutdown/cleanup.py`, cancelling loads and stopping runtimes so a load in flight cannot leave an orphan process.

### What was removed

The Round 4 translator-specific warm/idle system in `translation/service.py`
(idle constants and thread, `warm_on_user_record`, `_wait_for_inflight_warm`,
its idle keys in the config) was deleted, along with its call site in
`recording_lifecycle.py`, its 433-line test file and the two settings
`translation_warm_on_record` / `translation_idle_unload_seconds`. Old configs
containing those keys still load; the keys are dropped. The translator keeps
its own GPU-switch/cache-key behavior and now logs `[TRANSLATE]` with a distinct
terminal color; `[TTS]` and every other domain's color are unchanged.

### Verdicts and evidence

- Reviewed design D2's premise that ASR was preloaded under Fast Startup was WRONG (audit §4/§5). Kept ASR behavior exactly as today and applied Fast Startup only to optional kinds.
- Reviewer's "one shared idle clock reset by any model use" idea was REJECTED: ASR use would keep an unused TTS model resident forever. Each kind has its own clock from its own last use; "Always" never unloads.
- Parallel vs sequential ASR+translator loading: UNVERIFIED for real ASR (no runtime DLL on this machine); chose sequential-by-need, the conservative option, and documented the gap.
- Per-chunk translation DURING recording remains NOT SHIPPED. Round 4 measured a small gain on the best combination (480 s CPU-ASR + GPU translator: 31.5 s -> 12.8 s wait) but 3 of 5 groups at 30/120 s and 29 of about 96 groups at 480 s were revised after translation; CPU translation costs ~1.6-2.0 s per group (~11-14 s per paragraph), so a CPU-only machine is slow. A reconciliation pass and an owner decision are still required.
- Translator readiness delay explained (MEASURED 2026-11-27): a timed cold read of the 1.31 GB GGUF took 15.47 s (81 MB/s) versus 0.15 s warm; spawn-to-healthy was 13.78 s cold and 2.06-2.70 s warm; the health poll adds at most 0.5 s; mmap/mlock/flash-attention/context flags gave no cold-load win. It is the FILE SIZE plus a cold OS cache, not the runtime settings. Hence the shared record-start preload is useful only when there is speaking time before stop.
- The `0x80010108` COM message is NOT a Round 4 regression: the same class was documented in git history on 2026-08-06 with an existing atexit mitigation; the 2026-11-27 event was a handled first-chance exception printed by faulthandler (app kept working). The exact faulting frame is UNVERIFIED; capture dev sidecar stderr during a repro before changing clipboard/COM code.
