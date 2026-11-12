# Lifecycle state machines

Normative contract: ADR-0029. This file is the inventory an agent reads
before changing any lifecycle: find the machine, use its owner vocabulary,
run its pinned tests, and update its row in the same change.

## Contract (ADR-0029)

1. **The producer owns a closed vocabulary.** Cross-boundary states are a
   `StrEnum` (Python) or a literal union derived from an array (TS). Wire
   values are the enum values; no free-form status strings.
2. **Consumers validate; they never cast through.** An unknown value keeps
   the consumer's last known state (`isMediaJobPhase`, `parse_job_phase`);
   it is never rendered, stored, or forwarded.
3. **Non-linear transitions get one pure table/reducer** beside the
   vocabulary. Effects (I/O, timers, tray writes) stay at the caller.
4. **A boundary publishes a snapshot, not a flag pair.** Fields that only
   make sense together move together (C-HOME-1, C-PARITY-2).
5. **No state-machine library.** The app's existing reducers are the
   pattern (`nextBubbleMode`, `chart-phase`); a dependency would add bundle
   cost and a second vocabulary without solving a real problem.

## Inventory

| # | Lifecycle | Owner / vocabulary | States | Encoded as | Verdict |
|---|-----------|--------------------|--------|------------|---------|
| 1 | Dictation / recording | `AppState` (`voice_typer/server/tray_types.py:16`); renderer `RecordingState` (`types/ipc/enums.ts:21`) | 6 | Explicit enum + mirror union | Explicit vocabulary, **implicit transitions** (set from `recording_lifecycle*.py`, `dictation_pipeline/*`, `transcription_watchdog.py`; tray side effects in `tray_state.py:19`) |
| 2 | Waveform bubble | `waveform.py:65` producer; renderer `BubbleMode` + `nextBubbleMode` (`bubble/constants.ts:3,107`) | 10 renderer modes, 11 producer strings | Producer **free string**; renderer pure reducer + exhaustiveness guard | Biggest producer-side offender; reducer already explicit. Migrate next |
| 3 | Media transcription job | `JobStatus` / `JobPhase` (`media_ingest/lifecycle.py`); `MediaJob` (`jobs.py:54-56`); renderer `MEDIA_JOB_PHASES` (`useMediaJobs.ts:37`) | 4 statuses, 7 phases | **Closed enums** (this change) + boundary parser + renderer guard | Fixed pilot (ADR-0029) |
| 4 | Local ONNX polish provider | `_load_state` (`model_providers/local_onnx/client.py:66`), published as `provider_local_onnx_state` | 4 (`unloaded`/`loading`/`ready`/`failed`) | **Free string** field + event | Typed enum + transition table next |
| 5 | Native hotkey backend | `_STATE_*` constants (`hotkeys/native_adapter.py:38-42`) | 5 (`NATIVE`, `FALLING_BACK`, `FALLBACK`, `FAILED`, `STOPPED`) | **String constants** + 5-minute retry `Timer` | Enum + explicit table (`stop`/fallback/retry edges) |
| 6 | Chat push-to-talk turn | `phase` + `busy` + `_listening` (`conversation/manager.py:63`); `chat_turn` event | 6 phases (`listening`/`transcribing`/`thinking`/`speaking`/`idle`/`error`) | **Free string + flag pair** | Enum; derive `busy` from phase (they can currently disagree) |
| 7 | TTS playback | `tts/manager.py:393,402`; `tts_playback_state` event | 3 (`playing`/`stopped`/`finished`) | Free strings, event-driven | Small enum; snapshot at the event boundary |
| 8 | CUDA install activation | `cuda_install/state.py:24-25` persisted record | 2 (`pending`/`failed`) + job progress | Module string constants; read validates membership | Fine as a persisted sum type; add a job-status enum when jobs grow |
| 9 | Renderer connection | `ConnectionStatus` (`stores/appStore.ts:5`); `status_change` / `state_changed` / `get_status` | `connecting`/`connected`/error family | Union **derived by event handlers** | Explicit union; snapshot rule lives in C-HOME-1/C-PARITY-2 |
| 10 | Microphone test | Renderer `pages/microphone/hooks/useMicrophoneTest` + backend handlers | idle → recording → finalizing → result | Derived from start/stop acks + one 10 s timer | Pinned by C-MIC-18/C-MIC-19; keep the single readout |
| 11 | Sidecar + worker processes | Rust `SidecarState` (`src-tauri/src/state.rs:41`), `WorkerState` (`:160`); Python worker session (port/generation) | shutdown, respawn, auth, generation | **Flag cluster** (`shutting_down`, `respawn_in_progress`, `ws_generation`, heartbeat handle …) | Highest-risk implicit machine; guarded by RACE/SEC tests, do not refactor casually |
| 12 | Chart visuals | `ChartPhase` + orchestrator (`components/charts/chart-phase.ts:8`) | 10 visual phases | Explicit union + single reducer | **Good exemplar**: pure transition helpers |
| 13 | Sidebar Settings submenu | C-SIDEBAR-17 (one `submenuOpen`, three transitions) | open/closed + flyout | Explicit state, no persistence | **Good exemplar**: navigation is the source of truth |
| 14 | Model load / switch | `AppState.LOADING` + `model_manager/*` leases, idle-unload deadline | loading/idle/error + lease holders | Enum + counters/leases | Explicit priority rules (C-MEDIA-4); no single table |

## Priority

1. **Dictation transition table** (highest UX blast radius: tray, Home,
   bubble, a11y regions). Add a pure `next_dictation_state(prev, event)`
   table validated by tests before touching call sites.
2. **Bubble producer vocabulary** (`BubbleState` enum at every `set_state`
   site). The renderer reducer and exhaustive guard already exist; only the
   producer is free text. Cover `still_transcribing` /
   `cloud_cancel_requested` as label-only events, not modes.
3. **Connection/recording snapshots** — one payload, one writer, per
   C-HOME-1/C-PARITY-2 (the surfaces already derive from the pair).
4. Local ONNX, hotkey adapter, chat phase, TTS: contained enum migrations.
5. Sidecar/worker: only with the existing RACE/SEC suites in the loop.

## Agent checklist

- New lifecycle or state value → update the owner vocabulary + this table.
- Wire value changed → grep the string and update every pin (C-TEST-10).
- Cross-boundary state → add a value/parse test and a consumer guard test.
- Non-linear transitions → one pure function + a table test; effects at the
  caller, never inside the table.
