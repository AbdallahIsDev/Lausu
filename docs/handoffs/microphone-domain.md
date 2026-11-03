# Microphone domain — session handoff

**Date:** 2026-11-03
**Branch:** `main` (last commit `abb2164f feat(tts): ship local speech engines as model rows`)
**Working tree:** dirty by design. Never `reset`/`stash`/`revert`/`clean` (E18). See §6 for the file list.

**Read first:** `AGENTS.md` (binding), `docs/microphone-filter-failures.md` (evidence + design), `worklog.md` 2026-10-31 → 2026-11-03 entries.

---

## 0. TL;DR for the next agent

Done and green: DPDFNet2 replaces the `noise_suppression_method` slot, presets were slimmed, a divergence guard protects dictation, the full gate set passed.

Open:

| # | Item | Verdict | Severity |
|---|---|---|---|
| A1 | Monitor/test path has no divergence guard (a starving chain still shows a dead bar with no explanation) | **Genuine** | Medium |
| A2 | `level_bar_filtered` is a key nothing writes; `_state.py` default now contradicts the owner's spec | **Genuine, cosmetic** | Low |
| B | A chain built before DPDFNet preload finishes silently serves GTCRN **and can never promote**, while the UI shows "DPDFNet" | **Genuine, confirmed** | High |

**Do not "fix" A by forcing the meter to raw.** The owner's spec is the opposite: the bar follows the selected signal (§3.1). The earlier reading of A was a false alarm.

---

## 1. The original problems

### 1.1 Noise filters (the owner-reported failures)

Symptoms, all reproduced before the fix:

- Applying the **Auto** preset made the level / progress bar **collapse to ~0%** while the owner was speaking.
- Filtering **cut or weakened** the audio: the transcript came out short, quiet, or empty; the "Enhanced" clip sounded gutted.
- The damage was **invisible in the UI**: the meter followed the chain, so a suppressor eating the signal looked like the user had stopped talking.

Root causes, in order of impact:

1. `auto` stacked highpass + **noise gate** + EQ + compressor + limiter + a neural suppressor. The gate closed on real speech and the compressor squashed level.
2. The neural fallbacks (GTCRN, then ~10 dB of attenuation) were chosen at chain-build time without the caller knowing. A chain labelled `NoiseSuppressor(dpdfnet)` could be running GTCRN.
3. There was **no guard**: nothing compared raw vs filtered energy, so a suppressor could starve the pipeline silently (blank transcript, no toast, no log line).

### 1.2 DPDFNet (a feature, not a bug)

Request: a better commercially-licensed denoiser than GTCRN, causal, streaming, cheap enough that a 2 s dictation never costs ~10 s of denoise. DeepFilterNet**3** was explicitly out of scope (licence); DPDFNet2 (DeepFilterNet2) is the one in use.

---

## 2. What was shipped

### 2.1 DPDFNet2 backend

| Piece | Where |
|---|---|
| Streaming ONNX denoiser (16 kHz native, per-source-rate `_StreamingResampler`, sample-exact FIFO with one window of pre-roll) | `voice_typer/server/audio_filters/dpdfnet_backend.py` |
| Bundled weights (10,178,747 B) | `voice_typer/server/dpdfnet2.onnx` |
| Packaging | `MANIFEST.in:63`, `scripts/build/lausu.spec:94,257` |
| Startup preload (own daemon thread, after the handshake) | `voice_typer/server/startup_sequence/_phases_early.py:168-176` |
| RTF gate 0.30 | `dpdfnet_backend.py:123` (`_probe_realtime_factor`) |
| Fallback order | `dpdfnet → rnnoise → gtcrn → none` (`audio_filters/noise_suppressor.py`) |

Real-run evidence:

```
2026-11-03 15:02:36  [DPDFNET] model ready (win=320 samples, rtf=0.142, sr=16000) 0.5s
2026-11-01           Level processor updated: highpass=True, gate=False, method=dpdfnet
2026-11-01           Audio processor rebuilt: ['HighPass(80Hz)', 'NoiseSuppressor(dpdfnet)', 'Limiter(-6dB)']
```

Measured on real TTS speech (`bench-out/stress-results.json`):

- whole-signal delta **−0.41 dB** for `auto` and `noisy_room` (level-transparent)
- SNR improvement **+67.9 dB** on the synthetic noisy-room mix
- RTF **0.118**, no drift over 180 s

Cross-check in a fresh process at the monitor's 48 kHz, 20 ms chunks: `off` 0.0 dB, `studio` −1.4 dB, DPDFNet `auto` ≈ −0.4 dB.

### 2.2 Preset simplification

`voice_typer/server/audio_presets.py`:

- `auto` / `noisy_room` = highpass + **DPDFNet** + limiter only. Gate, EQ and compressor are **off** (owner-visible behaviour: nothing shapes a healthy signal).
- `studio` = highpass + EQ + compressor + limiter, **no suppressor** (quiet room, good mic).
- `off` = nothing; the level processor is not even built (`[LEVEL-MON] Level processor bypassed: raw meter (noise filter off)`).
- `custom` keeps every field individually editable.

### 2.3 Divergence guard (dictation path)

`voice_typer/server/recording/filter_divergence.py`, wired in `recording/audio_pipeline.py:108,226,242-270`:

- criterion: raw speech while filtered sits **>25 dB down for >500 ms**;
- action: **fail open**, one WARNING containing both dB values + the preset, one user toast, silence timer suspended, never a blank transcript;
- the VAD decision stays on the **filtered** audio.

### 2.4 Microphone-page wiring (it is wired — verified end to end)

| Step | Evidence |
|---|---|
| Preset click → `set_config` | Microphone page → `updateConfig({ audio_preset })` |
| Preset expands first | `config_applier.py:135` (`_AudioPresetHandler`) before `config_applier.py:136` (`_FilterChainHandler`) |
| Both keys rebuild the chain | `_FILTER_CHAIN_KEYS` (`config_applier_handlers.py:50-65`) contains `audio_preset` **and** `noise_suppression_method` |
| Live meter rebuilt | `config_applier_handlers.py:471` → `update_level_processor(...)` |
| Test filters refreshed | `update_test_filters(...)` on the same path |
| Method forwarded to the test | `pages/microphone/lib/buildTestFilters.ts:24` |
| Test quality graded from **raw** | `level_monitor/worker.py:379-386` |
| "Enhanced" clip = live filtered capture (stitched per chunk across toggles) | `worker.py:360-364` + `test_recording.py:146-154` |
| Post-hoc re-filter only when the chain never ran | `test_recording.py:173` |

A preset change takes effect within ~1 s, no restart, no reconnect.

### 2.5 Improvements beyond the original bugs

- Presets are now short and predictable; the owner can hear what each stage does.
- One suppressor slot with an explicit fallback chain and a preload, so the first recording never pays the session build.
- A guard that converts "silent audio destruction" into a visible, logged, recoverable event.
- A real stress harness (`bench/stress_mic_filters.py`) and a written evidence base (`docs/microphone-filter-failures.md`) instead of ad-hoc listening tests.
- `get_audio_status()` (`service/status.py:347-367`) now reports `filter_chain`, `degraded`, `degraded_reasons`, `latency_ms`, `vad_backend` for the dictation processor.

---

## 3. What is still open

> **CLOSED 2026-11-03** — every item below is implemented, pinned by a regression test, and recorded
> with its evidence in §8. Read §8 first; the sections below stay as the original analysis.

### 3.1 Issue A — "the level bar follows the filter chain, not the raw signal"

**Verdict: FALSE ALARM.** Keep the current behaviour.

The owner's spec, stated explicitly on 2026-11-03:

> With no filter, the bar must follow the raw microphone. With a preset on, it must follow the processed audio — less fluctuation because the noise was actually reduced.

The code does exactly that:

- `noise_filter_enabled == False` (preset `off`) → `update_level_processor` sets `_state._level_processor = None` (`monitoring_queries.py:93-98`) → the worker's `run_filter_chain` is `False` → raw RMS (`worker.py:365-368`).
- A preset is on → the processor exists, `_level_bar_filtered` is `True` → filtered RMS (`worker.py:341-344`).
- During a mic test the chain is always used (`worker.py:342`, `test_mode or _level_bar_filtered`), which is required so the Enhanced clip is the real processed capture.

The comment at `monitoring_queries.py:70-74` already documents this: the choke-point default `True` makes the bar follow the preset.

**Do not implement "raw meter".** An earlier audit note recommended it; that recommendation is withdrawn.

#### A1 — Residual gap, genuine: the monitor path has no divergence guard

`filter_divergence.py` protects **dictation only**. The level monitor / mic test (`worker.py:341-368`) has no raw-vs-filtered comparison, so if a chain starves the signal the bar still collapses and nothing explains it — the exact historic symptom, just without a toast. This is the mechanism by which Issue A can look "unfixed" again.

**Fix direction**

1. In `worker.py`, after `raw` and `flat_filtered` are both available (they already are, `worker.py:344-368`), run the same criterion as `filter_divergence` — reuse its constants, do not fork thresholds:
   - raw chunk RMS above the speech floor (reuse `vad_policy._SILENCE_AMP_FLOOR`, see `C-MEDIA-5`), **and**
   - filtered RMS >25 dB below raw for >500 ms of continuous chunks (use the **instantaneous** RMS, not the EMA at `worker.py:399`, or the guard lags).
2. On trip: one WARNING with both dB values + `method` + preset, fail open for the remainder of the monitoring session (`_state._level_processor = None` is the existing raw escape hatch), and emit exactly one toast through the existing notification path.
3. Reset the trip state on `start_monitoring` / `microphone_test_start`, never on a config change (a preset change must be able to retry the chain).
4. Tests: starving fake filter trips after ~500 ms; genuine silence does not trip; trip happens once per session; the bar recovers to raw.

#### A2 — Genuine, cosmetic: `level_bar_filtered` is dead configuration

- `monitoring_queries.py:74` defaults it to `True`; `to_filter_dict()` never emits it; no IPC writes it.
- The `_state.py` default was flipped to `False` during the DPDFNet work (`voice_typer/server/level_monitor/_state.py:45-52`), which now contradicts the owner's spec and is masked only because `update_level_processor` overwrites it on the first call.

**Fix direction:** revert the `_state.py` default to `True` with a comment saying "the meter follows the chain by design (owner spec 2026-11-03); the pre-seed window reads raw because the processor is `None`", **or** delete the flag entirely and drop the branch at `worker.py:342` (`test_mode or True` → the processor's presence already encodes the decision). Deleting is cleaner; keep the escape hatch only if a real settings toggle is planned.

---

### 3.2 Issue B — a chain can silently serve GTCRN while the UI says DPDFNet

**Verdict: GENUINE, confirmed by construction and by probe.** This violates the new `C-UI-15`.

#### Evidence

Fresh process, no preload, 36 s of real speech resampled to 48 kHz, 20 ms chunks, `auto` preset:

```
chain      : ['HighPass(80Hz)', 'NoiseSuppressor(dpdfnet)', 'Limiter(-6dB)']
suppressor : method=['gtcrn'] backend=['GtcrnBackend']      <-- label lies
whole-signal: raw -20.3 dBFS -> filtered -30.9 dBFS   delta -10.6 dB
meter      : raw p50 7%  ->  filtered p50 2%   min 0%
```

Real boot where the gate refused DPDFNet:

```
2026-11-02 11:05:31  dpdfnet real-time factor 0.346 exceeds the 0.30 ceiling
```

On that boot every DPDFNet request was served by GTCRN for the whole session.

#### Root causes (all four must be addressed)

1. **Cold-start build.** `DpdfnetBackend.__init__` raises when the runtime is absent (`dpdfnet_backend.py:302-305`). `_init_dpdfnet` then sets `_dpdfnet_pending = True`, `_method = "rnnoise"` (`noise_suppressor.py:227-228`) and calls `_init_rnnoise()`.
2. **The promotion gate can never open after the GTCRN substitute.** `_try_gtcrn_substitute()` sets `self._method = "gtcrn"`, but `_promote_dpdfnet` early-returns on `self._method != "rnnoise"` (`noise_suppressor.py:244`). On this machine `pyrnnoise` is not installed, so the substitute path is the normal path → **the instance stays GTCRN forever**. Promotion is only attempted from `reset()` (`noise_suppressor.py:500`), which for the level processor happens on **stop** (`monitoring.py:425`) — too late anyway.
3. **The level processor is never rebuilt.** `update_level_processor` dedupes on the **config dict**, not the effective backend (`monitoring_queries.py:80-91`). Identical config + preload finished later → early return → the meter (and the mic test, which reuses `_state._level_processor`, `worker.py:341`) keeps the stale backend for the session.
4. **The RTF gate is a boot-wide, silent disable.** `_probe_realtime_factor` runs on a cold first pass; 0.346 on this CPU killed DPDFNet for the process, and nothing told the UI.

Compounding: the UI renders `config.noise_suppression_method` (`audioFilterRowDescriptors.ts:142`), i.e. the **requested** value. `get_audio_status()` reports `degraded` / `degraded_reasons` for the dictation processor only, and the Microphone page does not consume it. The level/test processor has no status surface at all.

#### Fix direction (cheapest first)

1. **One-line correctness fix:** `_promote_dpdfnet` must gate on `_dpdfnet_pending and dpdfnet_backend.has_runtime()`, never on `_method == "rnnoise"`. Add a regression test that promotes **from** the gtcrn substitute.
2. **Rebuild on reality change:** give `AudioProcessor` a `backend_fingerprint` (effective method + backend class per suppressor) and include it in the `update_level_processor` dedupe key (`monitoring_queries.py:82-88`), so a landed preload rebuilds the meter/test chain instead of being deduped away. Alternative: subscribe to preload completion and call `update_level_processor` with a bypassed dedupe. Prefer the fingerprint — it also covers future backend changes.
3. **Show the truth (`C-UI-15`):** extend `get_audio_status()` to return the effective method for **both** processors, e.g.
   `{"noise_suppression": {"requested": "dpdfnet", "effective": "gtcrn", "degraded": true, "reason_code": "backend_unavailable"}}`
   Render the effective name next to the selector; when `effective != requested`, say so in plain language (`C-UXERR-1`/`C-UXERR-3`: no class names, no exception text — e.g. "DPDFNet isn't available on this device — using GTCRN."). One toast per session, not per chunk.
4. **RTF gate:** measure on a **warm** pass (the 0.346 reading looks like cold-cache noise; the same machine reports 0.118–0.142 when warm), retry once, and if it still fails, report it through the status surface from (3).
5. **Tests to add**
   - `_promote_dpdfnet` promotes from a gtcrn substitute once `has_runtime()` is true.
   - `update_level_processor` rebuilds when the fingerprint changes with an **identical** config dict.
   - `get_audio_status()` reports `requested != effective` on a forced fallback.
   - Renderer: the Microphone page renders the effective backend and the plain-language note.
   - Preload-failure path: no crash, status explains it.

#### Definition of done for Issue B

Any boot in which the page says "DPDFNet" has `get_audio_status().noise_suppression.effective == "dpdfnet"` **and** the meter + Enhanced clip come from that backend. Every other case names the backend that is actually serving, and why.

---

### 3.3 Other open items (low priority)

- `bench-out/` and `bench/stress_mic_filters.py` are untracked; decide whether the harness ships (recommended: yes, it is the only repeatable regression tool for this domain) and gitignore `bench-out/` artifacts.
- `docs/microphone-filter-failures.md` §1.2 records the zeroed-meter evidence; keep it even after A1 lands.
- `monitoring.py:191` and `:425` call `_level_processor.reset()`; after the fix in B1 that becomes a legitimate promotion point, so verify it does not double-promote.

---

## 4. Verification recipe (do this before claiming anything)

**Log truth** (the only reliable way to know which backend is live):

```powershell
Select-String -Path "$env:APPDATA\lausu\logs\lausu.log" `
  -Pattern "DPDFNET|NOISE-SUPPRESS|Level processor updated|real-time factor" |
  Select-Object -Last 20
```

- Healthy: `[DPDFNET] model ready ... sr=16000` **and** `Level processor updated: ... method=dpdfnet`.
- Bad: `serving bundled gtcrn instead` or `real-time factor ... exceeds the 0.30 ceiling`.

**Manual pass** (Microphone page, real microphone):

1. Preset `off` → speak → bar tracks speech, no filtering.
2. Preset `auto` → the bar should look **nearly identical during speech** (DPDFNet is level-transparent by design; that is the fix, not a failure) and drop during noise-only passages. The Enhanced clip keeps the same loudness with a quieter background.
3. Preset `studio` → EQ/compressor colour the tone, no denoiser.
4. Preset `noisy_room` → noise floor drops, speech level kept.
5. 10 s test → quality grade comes from raw; Enhanced = the live filtered capture; switching presets mid-test splices correctly (no silence, no smear).

**Probe** (read-only, reproduces B):

```powershell
.venv\Scripts\python.exe C:\Users\11\AppData\Local\Temp\opencode\probe_meter.py
```

Recreate it if missing: it builds `AudioProcessor` at 48 kHz per preset, feeds 20 ms chunks of `bench-out/speech.wav`, and prints the effective method + whole-signal delta + meter percentiles. Expected on a healthy preloaded process: `method=['dpdfnet']`, delta ≈ −0.4 dB, meter ≈ raw.

**Gates (green on the current state, before this handoff's doc-only edits):**

- `pytest` full: **18497 passed, 875 skipped**, coverage 84.56 %
- `vitest`: **401 files / 4641 passed**
- `typecheck:ci`, `format:check`, `ruff`, coverage + ruff ratchets, `cargo check` — clean

---

## 5. Rules that bind this area

- **`C-UI-15` (new, 2026-11-03):** the UI must never display a value/name/state that differs from what the backend is actually running. Silent fallbacks and deferred loads are displayed as what they are.
- `C-AUDIO`-family behaviour lives in `docs/microphone-filter-failures.md`; `C-MEDIA-5` forbids sending a window the decoder already measured as silent to the model.
- `C-UXERR-1..6`: plain-language user copy, full detail in the logs, always a recovery action.
- `C-UI-12`: progress/level bars use the shared `LevelBar`; never hand-roll the bar.
- `C-MIC-18`: fixed 10 s test duration, one readout, no duplicated timers.
- `C-TEST-6`: no "done" without a recorded green full run on the final state.
- `C-TEST-15`/`C-TEST-14`: never patch auto-created mock children or package-facade virtual names (pytest ≥ 9.2 undo semantics).

---

## 6. Working-tree state — do not lose it

Modified: `AGENTS.md`, `docs/microphone-filter-failures.md`, `tests/test_audio_filter_prealloc.py`, `tests/test_audio_filters.py`, `tests/test_audio_pipeline_regressions.py`, `client/src/renderer/src/components/audio/audioFilterRowDescriptors.ts`, `server/audio_filters/dpdfnet_backend.py`, `server/audio_filters/noise_gate.py`, `server/audio_filters/noise_suppressor.py`, `server/audio_presets.py`, `server/audio_processor.py`, `server/level_monitor/_state.py`, `server/recording/audio_pipeline.py`, `worklog.md`.

Untracked: `bench-out/`, `bench/stress_mic_filters.py`, `tests/test_dpdfnet_backend.py`, `server/dpdfnet2.onnx`.

A parallel session also has provider/TTS work uncommitted in the same tree. Fix forward; never reset (E18).

---

## 7. Suggested order for the next agent

1. B1 (`_promote_dpdfnet` gate) — one line, highest impact, unlocks everything else.
2. B2 (fingerprint in the dedupe) — makes the meter/test chain converge to reality.
3. B3 (status + UI truth) — satisfies `C-UI-15`, and is what the owner will judge.
4. A1 (monitor divergence guard) — stops the dead-bar symptom from ever being silent again.
5. A2 (`_state.py` default revert or flag deletion) — cleanup, do it with A1.
6. B4 (warm RTF probe) — last, it is the noisiest to validate.
7. Full gate run on the final state, then ask the owner to do the manual pass in §4.

---

## 8. Closure record (2026-11-03)

Every item from §3, what shipped, and the test that keeps it shipped.

| Item | Shipped | Pinned by |
|---|---|---|
| A1 monitor / mic-test divergence guard | `level_monitor/divergence.py` reuses `FilterDivergenceGuard` (same constants, no forked thresholds). Armed per session in `start_monitoring` and `_begin_test_locked`, never by a config change. On the trip: that chunk is measured from the raw signal, `_state._level_processor = None` (the existing raw escape hatch), one WARNING carrying both levels + preset + method, one `filter_collapse` toast with `reason: "monitor_collapse"`. | `tests/test_level_monitor_divergence.py` (starving chain trips once, bar recovers to raw, silence never trips, an unarmed guard never trips, re-arm on `begin_session`) |
| A2 dead `_level_bar_filtered` | Deleted from `_state.py`, `monitoring_queries.py`, `worker.py`. The processor's presence is the only switch (`test_mode or processor is not None`), which is exactly the owner's spec: chain on -> filtered bar, preset off -> raw. | `tests/test_level_monitor_lightweight_bar.py` (`test_legacy_flag_key_is_inert`, `test_filter_off_leaves_no_processor`, `test_no_processor_reads_the_raw_meter`) |
| B1 promotion gate | `_promote_dpdfnet` gates on `_dpdfnet_pending` + `dpdfnet_backend.has_runtime()`, never on `_method == "rnnoise"`, so the shipped gtcrn substitute promotes too. `name` / `effective_method` follow the backend actually serving. | `tests/test_noise_suppressor_promotion.py` (promotes from the substitute, one-shot, no promotion without a runtime, `reset()` does not double-promote) |
| B2 dedupe on config only | `AudioProcessor.refresh_backends()` (the read-none fingerprint was deleted); `update_level_processor` converges the live chain on a dedupe hit instead of returning early (no second model built), and `level_monitor/monitoring.py`'s bounded watcher converges a chain that was built BEFORE the preload landed, with no config change and no page reload. The page-open path (`service/microphone_test.level_monitor_start`) refreshes the dictation chain too. | `tests/test_level_monitor_processor_converge.py` (promotes in place, keeps the chain when nothing landed, a raising refresh is swallowed, a real config change still rebuilds, watcher promotes / times out / stops with the session / never starts for a healthy chain), `tests/test_level_monitor.py` (start_monitoring spawns it with the committed epoch) |
| B3 requested != effective | `audio_filters/effective_backend.py`; `get_audio_status()` reports `noise_suppression` for the dictation AND meter chains, `get_status()` carries the dictation block plus `level_monitor_noise_suppression` (no new IPC route, so no Rust/doc registration). Renderer: `useDenoiserFallbackNote` reads the METER block (`level_monitor_noise_suppression`, falling back to the dictation one) and re-reads it every 3 s while mounted, so the note disappears on its own once the watcher promotes; the card renders `settings.audioEnhancement.denoiserFallback` ("DPDFNet isn't available on this device - using GTCRN."). The toast branches on `monitor_collapse`. | `tests/test_audio_status_effective.py`, `useDenoiserFallbackNote.test.ts`, `useFilterCollapseToast.test.tsx` |
| B4 cold RTF probe | The probe excludes 5 warm-up windows from the timing, re-runs once when the first reading is over the ceiling, and a median-of-3 verdict decides (one INFO line names every reading); the ceiling itself is unchanged at 0.30. | `tests/test_dpdfnet_backend.py` (warm-up exclusion, one probe when the first passes, median verdict, ceiling pinned at 0.3) |
| §3.3 bench harness | Kept (`bench/stress_mic_filters.py` is the only repeatable regression tool for this domain); its `bench-out/` artifacts stay local. | — |

Evidence on the final state:

- `python bench/stress_mic_filters.py --no-asr --long-seconds 90` -> **ALL GATES PASSED (14 rows)**; the chain
  reported `NoiseSuppressor(dpdfnet)` on a cold start (the same boot used to report `gtcrn`), RTF 0.098-0.107,
  drift 1.001x, broken-gate preset still tripping at delta 171 dB with the take swapped to raw.
- `pytest` on the closure batches (levels, noise/audio/status, config, service, microphones, recording, server, regressions, parity, dead-code) is green: 1 616 passed, 10 skipped; the whole `npx vitest run` is green (403 files, 4 654 passed). Commands and counts in `worklog.md`.
- The manual pass in §4 still needs a human at a real microphone; the automated gates cannot hear.

Known limitation, unchanged: with `pyrnnoise` absent, a machine whose DPDFNet runtime cannot load at all
(no bundled ONNX, probe still over the gate when warm) now says so on the page instead of claiming DPDFNet.
