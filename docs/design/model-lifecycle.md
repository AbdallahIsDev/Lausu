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

---

## Live verification (dated 2026-11-27)

Plain English first. Everything above this line is code reading; this section is
live evidence. Round 7 drove the real IPC entry on a running app and on scratch
backends built from current source. The result: the Round 5 lifecycle works
live **once the translator kind is registered**, and the cold-app case that
still failed was fixed and re-proven. Three real bugs were found and fixed.
Some things still cannot be proven on this machine; they are listed as
UNVERIFIED, not assumed. No locked product rule was rewritten, so no ADR change
was needed in Round 7.

Evidence sources (harness temp folder): `r7-s1-report.md` (17:40–18:10),
`r7-s2-report.md` (18:13–18:40 plus its 18:53 re-run) and `r7-s3-report.md`
(18:10–18:24). Commits: `996fd214e` (18:17:47, register translator before the
first press + single gate decision), `8349953c9` (17:41:29, GPU-switch
tooltip), `74b7043ee` (18:52:11, refuse no-model starts before the mic opens)
and `7444e820b` (19:05:08, keep the touched tests hermetic). Log excerpts below
are trimmed: no personal paths, no dictated/clipboard text, no keys.

### How to repeat (exact command shape; scratch paths are ephemeral)

The production entry is the sidecar's own WS `toggle_dictation` frame, which
sets origin `button`. No OS key was injected (C-HOOK-1). Start a scratch backend
from the repo venv with current source, its own token/port and only already
present model/runtime files:

```powershell
$env:VOICE_TYPER_CONFIG_DIR  = "<scratch>\cfgN"              # own config + logs
$env:VT_PACK_ROOT            = "<scratch>\pack"              # minimal local pack marker
$env:LAUSU_TRANSLATION_RUNTIME = "%APPDATA%\lausu\translation"  # existing runtime
$env:TRANSCRIBE_LIBRARY      = "<existing transcribe.dll>"
$env:PARAKEET_MODEL_PATH     = "<existing local snapshot>"
python -m voice_typer.server.ipc_server --ws
```

Drive it over its own socket, then read `<scratch>\cfgN\logs\lausu.log`:

```
{"type":"auth","token":<sidecar token>,"protocol_version":1}
{"type":"toggle_dictation"}   # start; same frame again after the hold = stop
```

Steps for the non-default cases:
- **GPU switch:** `set_config {"translation_gpu_enabled": false}` (then `true`),
  each followed by a start press; read the child command line from WMI
  (`CreationDate`, `CommandLine`, `ParentProcessId`), not from the config.
- **Delete while loaded / loading:** point `HF_HUB_CACHE` at a scratch hub on
  the same volume as the real cache and put a **hard link** to the GGUF there;
  leave `LAUSU_TRANSLATION_MODEL` unset; call `delete_model` over IPC. Never
  delete the real hub. Real GGUF stayed at 1,312,164,352 bytes throughout.
- **Focus change:** two text windows in separate processes; hold focus on A at
  stop, focus B 1.0 s later, then dump both windows and check the clipboard
  retention line. No window text is reproduced here.
- **Grouping:** call `translate_text()` with the real GGUF/runtime and a POST
  counter at `_complete`; feed 735 / 9,800 / 14,700 characters.
- **No-model:** `model_size=""`, `asr_backend="parakeet"` (empty is rejected by
  the validator), `translation_enabled=true`, `fast_startup=true`; drive the
  same `toggle_dictation` frame and count absence of mic/translator lines.

### What was PROVEN live

| Claim | Live fact | Source run |
| --- | --- | --- |
| Translator ready **before** stop when the kind is registered | start 18:04:36 → ready 18:04:51 (14.7 s) → stop 18:05:06; child created 18:04:36, i.e. at start | S1 cfg4, current source |
| `[TRANSLATE]` log tag | readiness line carries `[TRANSLATE]`; `[TTS]` untouched | S1/S2, many runs |
| Translator memory | 1,804.4 MB private / 1,403.5 MB working set at 18:05:47; `-ngl 0` 584 MB, `-ngl 99` 1,806–1,807 MB | S1 cfg4, S2 WMI |
| Fast Startup OFF | `[LIFECYCLE] optional startup preload skipped (fast_startup off)`; no translator | S1 cfg5, 18:06:25 |
| Translation OFF | no `[TRANSLATE]`, no new translator process, ASR still loads | S1 cfg7 18:08:08; S2 s2g 18:53:10 |
| Startup preload + guard | ready 2.1 s; free 2,470.1 MB vs 2,312 MB threshold (1,800 estimate + 512 MiB headroom, `model_lifecycle/memory.py:75-91`); no skip line | S1 cfg6 18:06:53–18:06:55; post-fix S2 s2b 18:21:24 |
| Per-kind ASR idle clock | unload 17:57:46, reload on next press 17:58:44 at `model_idle_unload_minutes=1` | S1 cfg2 |
| Translator "Always" never unloads (`=0`) | ready 18:06:55, still alive at 18:07:58 (63 s), no unload line | S1 cfg6 |
| Quit with translator loaded | quit 18:08:41 → shutdown complete 18:08:42 (0.7 s) → no scratch processes left at 18:08:52 (11 s later) | S1 cfg8 |
| GPU switch applies on **next load** | `set_config` alone does not stop the old process; next load's `get_service(config)` compares `_service_key()` (`translation/service.py:424-445`) and retires it | S2 s2a, WMI command lines |
| Delete while loaded / loading | one success result, no crash, no orphan, no later reload; real GGUF intact | S2 s2a |
| Rapid input | two presses 0.12 s apart = one recording + one stop; one `ignore-burst`; 0.6 s take accepted | S2 s2b 18:22:00 / 18:22:20 |
| Stop-time paste destination | focus changed after stop → paste aborted, text kept on clipboard, no refocus | S2 shared app 18:32:16 |
| Real translation service, grouped | 735/9,800 chars → 1 call; 14,700 chars → 2 groups / 2 POSTs; 0 double spaces | S2 s2c2 |
| No-model refusal | 18:53:39 `[DICTATION] no active engine; dictation not started`; mic never opened; no translator | S2 s2g after `74b7043ee` |

Trimmed excerpts:

```text
18:04:36  INFO  [DICTATION] start requested (cycle=#2, origin=button)
18:04:51  INFO  [TRANSLATE] translation ready on http://127.0.0.1:<port> in 14.7s
18:05:06  INFO  [DICTATION] Stopping recording... (cycle=#3)
```

```text
18:06:25  INFO  [ASR_REGISTRY] loaded backend: parakeet
18:06:25  DEBUG [LIFECYCLE] optional startup preload skipped (fast_startup off)
18:06:26  INFO  [UPDATE] no pack manifest published yet, nothing to download
```

```text
17:57:46  INFO  [MODEL] idle-unload: unloading active backend 'parakeet' after idle period
17:57:46  INFO  [ASR_REGISTRY] unloaded backend: parakeet
17:57:46  DEBUG [GPU] release_gpu_memory() is a no-op for ONNX Runtime
17:57:46  INFO  [VAD] Silero VAD model unloaded
17:58:44  INFO  [DICTATION] start requested (cycle=#1, origin=button)
17:58:44  INFO  [ASR_REGISTRY] loaded active backend: parakeet
```

```text
BEFORE_QUIT 18:08:40: translator PID 13228, working set 1464.4 MB
18:08:41  AUTH first=ready -> quit_app dispatched
18:08:42  INFO  [SHUTDOWN] Shutdown complete, exiting successfully 0.7s
AFTER_QUIT 18:08:52 (11 s later): no scratch sidecar / translator PIDs
```

GPU switch, from real WMI command lines: `set_config false` at 18:17:06, press
18:18:11 → ready 18:18:13 (2.5 s), child created 18:18:10 ending `-ngl 0`
(no `-fa on`); `set_config true` at 18:18:32, press 18:18:33 → ready 18:18:35
(1.5 s), child created 18:18:34 ending `-ngl 99 -fa on`. Commit `8349953c9`
gave the switch a plain-language tooltip in all 8 locales
(`i18n/translations/en.json:820`, `translationGpuInfo`): it now says the
processor path is about 10 times slower in the tests, without the old
"adds time after you speak" wording.

Delete while loaded (18:18:58–18:18:59) and while loading (18:20:10–18:20:12):
the 2-second response gap on the loading case is the service lock waiting for
the in-flight load before stopping it. Rapid input: `start requested` at
18:22:00, `ignore-burst (generation=2)` on the second press 0.12 s later, one
stop at 18:22:02; a 0.6 s take at 18:22:20 was accepted and the load continued
without a crash.

Focus change, with the translation wait deliberately lengthened:

```text
18:32:16  INFO  [CLIPBOARD-AUDIT] Copied 78 chars to clipboard (seq=179, snapshot=captured)
18:32:16  WARN  [CLIPBOARD] Foreground window changed since dictation stop
          (stop_hwnd=330278 -> dispatch_hwnd=3213776), aborting paste ...
18:32:16  INFO  [CLIPBOARD] Paste delivery unconfirmed; keeping dictated text
          in clipboard for manual paste
```

`stop_hwnd=330278` is the window focused at stop, `dispatch_hwnd=3213776` the
one focused at delivery; both window dumps were unchanged. This matches
`tests/test_dictation_destination_stop_time.py`. An earlier run where focus
changed in the same second as the stop was a driving race (the stop snapshot
was already the new window), not a contradiction.

Grouping probe (real service, real text, no mocks of the service):

```text
735 chars   est_tokens=150   budget=2176  groups=1  posts=1  2.3s
9800 chars  est_tokens=1997  budget=2176  groups=1  posts=1  9.0s
14700 chars est_tokens=2994  budget=2176  groups=2  posts=2 10.6s
double-spaces: 0
```

The 2-group output had no missing separator and no added space, so the shipped
bounded group join preserves source whitespace end-to-end at the service
boundary.

### What FAILED and was FIXED

1. **Cold first dictation loaded the translator after stop.** Before the fix,
   the real app at 17:47:55 stopped, then at 17:48:46 logged
   `[TRANSLATE] translation ready ... in 49.6s` — the exact owner report.
   Cause: the policy module registers at import, and its only production
   importers were the first **post-stop** stage and the translation service, so
   the record-start hook (`dictation_gate.py:80-84`) could not see the kind on a
   cold process. Fix `996fd214e`: `ensure_kinds_registered()` at
   `model_lifecycle/registry.py:35`, called from the gate hook
   (`dictation_gate.py:88`) and at startup before the first press
   (`startup_sequence/_phases_late.py:495-503`). After: readiness 15 s before
   stop (18:04:51 vs 18:05:06), and post-fix startup preload at 18:21:24
   needed no scratch-only registration hack.

2. **Plugin hook with no plugin selected swallowed every local toggle.** Before
   the fix, each press produced `[DICTATION-GATE] ignore-burst (generation=1/2/3)`
   at 17:56:26 / 17:56:46 / 17:58:44 and no recording. Cause: the no-plugin
   branch decided the gate at `internal_plugin_hook.py:351`, then called the
   original toggle, which decided again at `app_dictation.py:25` inside the
   0.5 s debounce. Fix `996fd214e`: the no-session branch now releases any old
   owner, calls `orig_toggle()` and returns without a second decision
   (`internal_plugin_hook.py:355-363`); the one decision stays in the local
   entry. After: 18:21:35 `start requested`, `Recording started OK`, no
   ignore-burst.

3. **A no-model press opened the mic.** Before the fix (18:37:42):
   `start requested`, `Recording started OK`, then a generic transcription
   failure — the no-model notice never appeared. The old guard lived only on
   the hotkey path, so button/tray/plugin starts bypassed it. Fix `74b7043ee`:
   shared `no_active_engine()` / `notify_no_active_engine()` at
   `hotkey_dispatch.py:21,33`, plus the pre-mic refusal at
   `recording_lifecycle_start.py:59-71` for every start entry. After (18:53:39):

   ```text
   18:53:39  INFO  [DICTATION] start requested (cycle=#1, origin=button)
   18:53:39  INFO  [DICTATION] no active engine; dictation not started
   18:53:39  -> notification "No model selected. Go to the models page to select a model."
   ```

   Absence counts at/after that timestamp: `Recording started OK` 0,
   `Using device` 0, `Starting recording...` 0, `Audio stopped` 0,
   `[TRANSLATE]` 0, `no active engine` 1; no translator process appeared.
   A `DEBUG no-engine notification failed` line is only the headless scratch
   sidecar's tray call; the in-app notification was published.

### What stays UNVERIFIED, and why

- **End-to-end hotkey → bubble and a real local-ASR decode.** Scratch had no
  worker relay (`[WORKER-PATH] gate off: no worker port`), so
  `[TRANSCRIBE] Transcription FAILED` on every cycle; driving OS keys is also
  barred by C-HOOK-1. Presses were real WS frames with origin `button`, not
  hardware keystrokes.
- **Cloud ASR.** No provider configured (`asr_provider=local`, empty URL and
  model); no key was read, printed or used; no provider call was made.
- **TTS per-kind idle.** TTS was disabled in scratch to isolate translation;
  only the app's dedicated TTS prewarm was observed, not the shared clock.
- **Terminal color.** File logs intentionally strip ANSI (C-LOG-1) and no TTY
  was captured, so the `[TRANSLATE]` **tag** is verified but its color is not.
- **Press during a live translation POST.** Only a press during an in-flight
  *load* was exercised; no Stage-B POST was ever in flight without a worker.
- **Real Parakeet weight load / RSS and per-process VRAM.** No worker attached,
  so no weights were loaded. The whole-GPU sample at 18:07:25
  (4,411 MiB / 8,151 MiB) includes other processes and is not per-app or peak.
- **Sequential vs parallel ASR+translator loading.** No real ASR load to
  compare; the conservative sequential-by-need order stays as designed.
- **Sleep/resume.** Not driven in this round.
- **`0x80010108`.** Not reproduced in 6 plugin dictations (3 with translation
  on, 18:33:46–18:34:45; 3 off, 18:35:29–18:36:17) with STDERR captured:
  grep for `80010108|Fatal Python error|Current thread|Thread 0x|0x800` gave 0
  matches. The only COM-ish line is the known, logged caret probe. This adds no
  evidence to the note at `docs/design/model-lifecycle.md:154`; changing
  clipboard/COM code on suspicion is not justified.

### Deferred-load origin gap: real in code, unreachable live

The code hole is real: `model_manager/_loading.py:272-279` puts a pending press
on a zero-delay timer with no origin, and `app_dictation.py:36-38` calls
`recording.start()` without re-checking `dictation_origin.authorize(...)`
(`recording_lifecycle_start.py:193-265` checks state, consent, language and
permission but not origin). The only production writer of `_pending_dictation`
is the busy-rejection branch at `_loading.py:505-506`.

Both live attempts to reach it failed for the same reason:
- Immediate press on a cold sidecar (18:20:07 press → 18:20:10 mic): the load
  finished 3 s before the press landed; `Pending dictation` 0,
  `Recording started OK` 1.
- Press during a media job (18:17:19 press → mic in the same second): media
  calls the backend directly (`media_ingest/engine_loop.py:285`), bypassing the
  registry busy flag; no queuing line, and a later model switch at 18:17:27
  produced no deferred start. The app gate also refuses presses while busy
  (`recording_lifecycle_start.py:54-57`).

So the branch is effectively dead code on this machine today, but it remains a
C-START-USER-1 landmine: a timer thread with `dictation_origin.current() == ""`
could open the mic if a Timer/concurrency change armed it. Per the owner rule,
this is documented here and **the code was left unchanged** in Round 7; a fix
would need to carry the press-time origin through the existing 60 s wait
(`MODEL_WAIT_FOR_READY_SECONDS`, `_loading.py:35`) with a real-entry test.

### Stale-app caveat

The shared app was launched at 15:23:59/15:24:00 on HEAD `76cc13081`
(15:01:32). Round 5 commits landed at 15:33:12 / 15:39:36 / 15:43:12; the
verification fixes landed at 18:17:47 (`996fd214e`), 18:52:11 (`74b7043ee`)
and 19:05:08 (`7444e820b`). That process cannot contain those commits, so its
logs are **stale-code evidence only**. Final-code checks were therefore made on
scratch sidecars spawned after 17:55 from current source (S1 cfg4 onward; S2
s2b 18:21:20, s2d 18:33:26, s2e 18:35:11, s2f 18:37:19, s2g 18:53:09; S3
18:20:05). A "real app PASS" without checking the process start time against
commit times is not evidence of final code. The shared app was never stopped or
killed by this work; S2 briefly changed `translation_gpu_enabled` for the GPU
test and restored it, leaving that process's translator on its old flag until
its next dictation.


---

## Provider ownership rule (dated 2026-11-28, Round 8)

Plain English first. The owner saw a browser plugin serving dictation while the
app still tried to load the local speech model on every hotkey press, produced
"offline pack is not installed" warnings and showed a no-model notice. That was
a real regression, not a misunderstanding: the startup path and the record-start
path disagreed about who owns dictation.

### Root cause

Commit `afe72f7e6` (2026-11-27 15:39, the Round 5 lifecycle work) added the
record-start hook at `dictation_gate.py:80-94` with `_AsrPolicy.applicable()`
returning `True` unconditionally. Startup had an older plugin-only skip
(`_phases_late.py:376-391`, commit `32ecd9915`), and the model manager had
another plugin-only probe (`_loading.py:283-289`). A plugin press therefore
passed the startup skip, hit the record-start hook, created `WorkerBackedAsr`
and tried to load weights that the shipped slim installer does not provide —
exactly the owner's log shape. `git log -S` confirms only `afe72f7e6` added
`class _AsrPolicy` and `on_dictation_start(app)`.

### Decision: one shared provider definition

`voice_typer/server/dictation_provider.py` is now the single answer to "who
serves dictation right now" (kinds: `local`, `cloud`, `plugin`, `remote`,
`none`). It reads fresh config/plugin state on every call, checks the plugin
surface visibility FIRST, and never starts a browser profile just to answer.
Consumers: `_AsrPolicy.applicable()`, startup phases 7/8, model-manager warm
paths, the no-engine refusal/notices, tray status and tray label, and the
local-fallback guard at the shared start entry. Translator and TTS policies are
untouched — translation is independent of which provider writes Stage A.

Consequences, all verified with real-entry tests in
`tests/test_dictation_provider_ownership.py`:
- plugin, remote or cloud provider selected -> local ASR kind is NOT
  applicable: no `WorkerBackedAsr` creation, no load attempt, no idle reload,
  no local-model notice, no OS toast, no `[ASR_REGISTRY] refused` warnings. A
  cloud ENGINE still activates; that is not a local model.
- plugin selected but its session is not ready -> local recorder refuses with
  one warning; there is no hidden switch to local ASR.
- local provider selected with pack/model/runtime missing -> one actionable
  notice per episode (what is missing and where to click), deduplicated until a
  successful load, and the microphone is not opened.
- visible plugin surface off -> no plugin code is imported or profile touched.

### Live re-run

Three scratch sidecars from current source, plugin selected, three start/stop
pairs each (boundary-only launcher patches; no OS key injection): before the
fix 1 backend was created, with 6 `refused to load` and 6 `reload refused`
warnings; after the fix all three counts were **0**, with zero no-model notices.
The local converse produced exactly one pack-missing notice and no microphone
open. OS toast delivery is UNVERIFIED headless; the in-app notice event was
verified. Full trimmed log excerpts and commands are in
`C:\Users\11\AppData\Local\Temp\opencode\r8-s2-report.md`.

### Edge-case matrix

| Case | Covered by |
| --- | --- |
| provider local / cloud / plugin / remote / none | `test_dictation_provider_ownership.py` (23 tests) |
| plugin -> local, with and without pack | ownership tests + local converse live re-run |
| local -> plugin while ASR loaded | lifecycle idle tests (unload stays owned by model_manager) |
| plugin area hidden | visibility-first probe in provider tests |
| plugin fails to start | plugin-not-ready branch test (no hidden local fallback) |
| model present but pack missing / pack present but model missing | applicability tests + live local converse |
| translation on with each provider | translation policy untouched; translation lifecycle tests |
| two quick presses | dictation gate tests |
| shutdown during load | lifecycle shutdown tests |

Follow-up, not done here: renderer label parity for a remote `asr_provider`
(the renderer still treats some remote ids as "custom" in one label path); no
user-visible behavior is wrong, so this is cosmetic.
