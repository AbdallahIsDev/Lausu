# Microphone filter failures

Measured 2026-10-31 on this tree. Everything below is reproducible: `build_chain(cfg, 16000)` with
the shipped preset definitions, synthetic speech-like signal (120 Hz f0 + 40 harmonics, 4 Hz syllable
envelope, -65 dBFS room noise).

Symptom being explained: with Microphone Quality on Auto (the shipped default), the level bar sits at
zero while the user is talking, and words go missing from the transcript.

---

## 1. What is actually wrong

### 1.1 The noise gate hard-mutes quiet speech (primary cause)

`voice_typer/server/audio_filters/noise_gate.py` gates on **absolute dBFS** thresholds: open -26,
close -32 (`config/_schema.py:355-356`). A peak-hold envelope is compared against those numbers, so
any signal whose peaks sit below -26 dBFS never opens the gate, and anything below -32 dBFS is shut
completely. Speech RMS sits 10–18 dB below its peaks, so a perfectly audible mic at -40 dBFS RMS is
below the close threshold.

Auto preset, full chain, measured input → output:

| Input RMS | Input peak | Gate gain | Output RMS | Exact-zero samples | Level bar |
|---|---|---|---|---|---|
| -20 dBFS | -8.9 | 0.0 dB | -29.3 | 0.2 % | 27.4 % |
| -25 dBFS | -13.9 | 0.0 dB | -32.9 | 0.2 % | 18.1 % |
| -30 dBFS | -18.8 | 0.0 dB | -36.8 | 0.2 % | 11.6 % |
| -35 dBFS | -23.8 | 0.0 dB | -40.7 | 0.2 % | 7.4 % |
| **-40 dBFS** | -28.7 | **-13.5 dB** | -58.8 | **88.3 %** | **0.9 %** |
| **-45 dBFS** | -33.5 | **-15.3 dB** | -65.3 | **88.3 %** | **0.4 %** |
| **-50 dBFS** | -38.1 | **-19.0 dB** | -73.9 | **88.4 %** | **0.2 %** |
| **-60 dBFS** | -46.6 | **-22.0 dB** | -88.9 | **88.5 %** | **0.0 %** |

Noisy Room on the same signals fails one row earlier: at -35 dBFS RMS it already leaves 88.3 % of
samples at exact zero (gate gain -12.4 dB) while Auto is still passing everything.

Gate-only sweep, no suppressor in the path, same input at different thresholds:

| Input peak | open -26 dB | open -22 dB (Noisy Room) | open -40 dB |
|---|---|---|---|
| -18.9 | 0.0 dB | 0.0 dB | 0.0 dB |
| -24.8 | 0.0 dB | **-10.7 dB** | 0.0 dB |
| -30.7 | **-10.9 dB** | **-10.9 dB** | 0.0 dB |

Two things fall out of this:

1. Below roughly -35 dBFS RMS the gate stops passing speech, and the cut is total, not gradual.
2. `noisy_room` sets the open threshold to **-22 dB** with the comment "less sensitive"
   (`audio_presets.py:44`). That is backwards. Raising an absolute gate threshold makes it *more*
   aggressive: it now needs louder speech to open. That is why it starts muting a full 5 dB earlier
   than Auto on the same input.

### 1.2 The level bar shows post-filter energy

HISTORICAL (the mechanism below was removed on 2026-11-03: the flag is gone and the meter
follows the chain whenever a processor exists — see §2.6). At the time of measurement,
`level_monitor/_state.py:46` set `_level_bar_filtered = True`; `level_monitor/worker.py:342-348`
ran the full chain and computed RMS from `flat_filtered`. Display gain is 8.0 (`_state.py:31`).

That is why the bar reads 0.0–0.9 % while the user speaks, and why it recovers the instant
Microphone Quality is turned off: with the preset off the chain is empty and the meter sees the raw
device signal again.

Because the meter is the only live feedback a hands-free user has, a bar that reads zero is
indistinguishable from "the microphone is dead".

### 1.3 `NoiseGate.reset()` destroys its own envelope ramp

`noise_gate.py:450` does `self._i_arr_buf.fill(0)`, justified in the comment as "not audio-derived,
no PII". But that buffer holds `np.arange(n)`, the ramp the peak-hold decay multiplies
(`noise_gate.py:193-199`), and `_ensure_buffers` only rebuilds it when capacity grows
(`noise_gate.py:93-95`).

`AudioProcessor.reset()` → `FilterChain.reset()` runs at the start of **every** recording
(`recording/session_state.py:203`, `audio_processor.py:161`) and on every level-monitor start
(`level_monitor/monitoring.py:425`). From the second recording onward the ramp is all zeros and the
envelope has no decay term.

Measured, gate-only chain, -15 dBFS speech then -45 dBFS speech, 32 ms chunks:

| Chain state | Quiet-tail output |
|---|---|
| First use (ramp intact) | -46.0 dBFS, gradual release |
| After one `reset()` (ramp zeroed) | **-240.0 dBFS, hard zero** |

So the first recording in a process behaves differently from every later one, and the later ones cut
harder. That is the "sometimes it works, sometimes it eats words" part.

### 1.4 VAD runs on filtered audio, and quiet chunks are replaced by digital silence

- `recording/audio_pipeline.py:271` computes `chunk_rms` from the filtered signal; the VAD state
  machine consumes it (`:350-351`). When the gate closes, VAD sees silence and starts the
  silence-warning and auto-stop timers while the user is still talking.
- `audio_pipeline.py:195-200`: chunks whose peak is under 0.002, or under 0.01 with RMS under
  0.0005, are replaced by `np.zeros_like(...)`. Quiet input is not passed through, it is deleted —
  and that behaviour is currently pinned by `tests/recording/test_silent_capture_overflow.py`.

### 1.5 Preset parameters silently revert

`config_applier.py:85-95` lists `_PRESET_OVERRIDE_KEYS` without any parameter key, so editing a
cutoff, threshold, or ratio under `auto`/`noisy_room` does not switch the preset to `custom`.
`config/loader.py:402-416` re-applies preset values on every load, so the edit evaporates on restart.
`noisy_room`'s 100 Hz cutoff, -22 dB gate, and 4.0 ratio come back every launch.

### 1.6 Even a healthy signal loses 5.5–9.3 dB

At -20 dBFS input, Auto outputs between -25.5 and -29.3 dBFS depending on spectral content: -3.0 dB
from RNNoise, -2.4 dB from the EQ's -3 dB low band, on top of an 80 Hz high-pass. Nobody asked for
that. Dictation is not broadcast; ASR wants level, not polish.

---

## 2. Fix plan

### 2.1 Stop the bleeding (no new dependency)

1. **Gate: relative thresholds, or no gate.** Compute open/close from a rolling noise floor in dB
   relative to it, never absolute dBFS. A gate that cannot open on speech is worse than no gate.
2. **Gate: make `reset()` regenerate the ramp.** Rebuild `_i_arr_buf` in `reset()` (or stop zeroing
   it), so recording N behaves like recording 1. Add a test that asserts the ramp after reset.
3. **Level bar: follow the selected signal.** ~~Read the raw device signal.~~ WITHDRAWN (owner
   spec 2026-11-03): the bar must follow the chain when one is active and the raw device when the
   preset is off. The flag that made this ambiguous is deleted; the processor's presence is the
   switch, and a divergence guard (§2.6) turns a starving chain into a visible event instead of a
   silently dead bar.
4. **Recording pipeline: keep VAD on filtered audio, add a divergence guard.** See 2.3.
5. **Kill the near-silence zeroing.** Bypass should pass the chunk through, not replace it with
   silence. Update `test_silent_capture_overflow.py` in the same change.
6. **Fix the Noisy Room comment or the value.** If "less sensitive" is the intent, the threshold goes
   *down*, not up.
7. **Default Microphone Quality to off** until 1–6 are green and measured on real recordings.

### 2.2 Why the bar reads raw, and what covers the gap

The bar has one job: "is the microphone alive right now". Post-filter energy answers a different
question ("did anything survive the chain"), and it answers it in a way the user cannot interpret:
zero looks identical for a muted mic, a closed gate, and a bad preset.

Reading raw makes the bar honest about the mic and completely immune to filter mistakes. The
information that is lost — "is the filtered signal healthy" — is not something a bar should carry
anyway, because the answer is not a level. It is a fault. That belongs in 2.3.

The mic test page keeps its filtered timeline; the live meter does not.

### 2.3 Keep VAD on filtered audio, and prove the filter is not lying

Moving VAD to raw would hide exactly the failure we are trying to make visible: the user talks for
ten minutes, VAD reports speech the whole time, and the transcript arrives empty because the chain
ate everything. Filtered VAD at least tells the truth about what is being recorded.

But filtered VAD on its own produces the current symptom: "no sound detected" while the user speaks,
an auto-stop on silence, and a silent empty delivery. So neither source is the answer on its own.
The fix is to keep filtered VAD as the source of truth for the recording state and add a guard that
detects the two signals disagreeing.

Per chunk, both are already available (`_pending_raw_chunk_rms` at `audio_pipeline.py:439`):

```
raw_db     = dbfs(peak and rms of the unfiltered chunk)
filtered_db = dbfs(peak and rms of the filtered chunk)
```

Guard rules:

1. **Collapse detection.** Raw indicates *voiced speech* while `filtered_db` sits more than 25 dB
   below `raw_db`, for more than 500 ms of voiced time inside the last 2 s, in one unbroken stretch of
   at least 300 ms. "Voiced speech" is a normalized autocorrelation peak of 0.35 or more in the
   80-400 Hz range over a 40 ms window (plus a -60 dBFS floor); level alone cannot separate "the filter
   deleted the speaker" from "the filter correctly removed the noise". Measured on the stress fixture:
   pitch strength clears 0.35 on 41-47% of speech chunks, on 10.7% of pink-noise chunks, and it never
   holds a noise run longer than 3 chunks (96 ms), while real speech holds 25 (800 ms).
2. **Fail open.** When collapse is detected, stop filtering for the rest of the recording, log one
   WARNING with both numbers and the preset name, and surface one toast: the recording continues
   unfiltered rather than silently dying.
3. **Never auto-stop on a collapse.** The silence timer is suspended while the guard is active, so
   the user cannot be stopped for silence that the filter invented.
4. **Never deliver an empty result silently.** If a recording ends with speech present on raw and no
   filtered content, the take is swapped to the unfiltered audio before the snapshot (and the toast
   says so), instead of a blank transcript. The rescue needs one 120 ms run of voiced raw audio, so a
   lucky noise spike cannot turn a silent take into raw noise.
5. **Log one line per recording** with `raw_db`, `filtered_db`, gain delta, and guard state. That
   line is what makes the next report diagnosable without a probe script.

The guard costs one RMS plus one FFT autocorrelation per chunk while a suppressor or gate is in the
chain (tens of microseconds, ~0.2% of a core at a 20 ms callback), it makes the VAD question stop
mattering, and it fails in the direction the user can live with: more noise in the transcript instead
of no transcript.

### 2.4 Make the presets honest

- Reduce `auto` to high-pass plus one suppressor. Drop the gate, the compressor, and the EQ shaping
  from the default; keep them in `custom` for people who want a podcast voice.
- Add a gain-staging test: feed speech at -20/-35/-50 dBFS and assert output within ±3 dB of input
  and zero exact-zero runs. That single test would have caught 1.1, 1.2, and 1.3.
- Any neural backend replaces the suppressor slot only (`noise_suppression_method`); it never joins a
  chain of two suppressors in series.

### 2.5 What shipped against this plan (2026-11-02)

| Plan item | State |
|---|---|
| 2.1.1 gate relative / no gate | `auto` and `noisy_room` no longer contain the gate; `custom` keeps it unchanged (still absolute dBFS) |
| 2.1.2 `reset()` regenerates the ramp | done (`noise_gate.reset()`), covered by `tests/test_audio_filters.py` |
| 2.1.3 level bar reads raw | superseded: `_level_bar_filtered` is deleted; the meter follows the chain when a processor exists, the raw device when the preset is off (owner spec 2026-11-03), and `level_monitor/divergence.py` fails open to raw for the rest of the session if that chain starves (see §2.6) |
| 2.1.4 divergence guard | done (`recording/filter_divergence.py`, see 2.3) |
| 2.1.5 near-silence pass-through | done (the bypass returns a copy of the raw chunk, never zeros) |
| 2.1.6 Noisy Room honest | done - the whole preset is rewritten around DPDFNet, not retuned |
| 2.1.7 default Quality off | NOT done, and no longer needed: the stock presets carry no gate or compressor, and the guard fails open if a chain still eats speech |
| 2.3 guard | shipped with the pitch criterion + unbroken-run requirement described above |
| 2.4 presets / suppressor-slot rule | done: `auto` = high-pass + DPDFNet + limiter, `noisy_room` = notch + high-pass(100 Hz) + DPDFNet + limiter, `noise_suppression_method` default `dpdfnet` |

Backend: DPDFNet2 (DeepFilterNet2, 16 kHz streaming ONNX), bundled at
`voice_typer/server/dpdfnet2.onnx`, adapter in `audio_filters/dpdfnet_backend.py`. NVIDIA RE-USE was
evaluated and rejected (offline-only, ~0.9x real time on CPU, the real-time variant is
non-commercial, and the ASR gain was negligible).

### 2.6 The 2026-11-03 closure (meter guard, dead flag, silent GTCRN)

| Issue | State |
|---|---|
| Monitor / mic-test chain had no divergence guard | fixed: `level_monitor/divergence.py` reuses `FilterDivergenceGuard` with its constants (no forked thresholds), armed per monitoring or test session, one WARNING with both levels + preset/method, one `filter_collapse` toast (`reason: "monitor_collapse"`), then `_state._level_processor = None` so the bar and the Enhanced clip read the raw device for the rest of the session. Re-armed only by `start_monitoring` / `_begin_test_locked`, never by a config change. |
| `_level_bar_filtered` was dead configuration | deleted (`_state.py`, `monitoring_queries.py`, `worker.py`); the processor's presence encodes the decision. A legacy `level_bar_filtered` key in a filter payload is inert (`test_legacy_flag_key_is_inert`). |
| A chain could serve GTCRN while the UI said DPDFNet | `_promote_dpdfnet` gates on `_dpdfnet_pending` + `has_runtime()` (never on `_method == "rnnoise"`), so promotion also works from the gtcrn substitute; `NoiseSuppressor.name` / `effective_method` follow the effective backend. |
| A landed preload was deduped away | `AudioProcessor.refresh_backends()`; `update_level_processor` converges the live chain on a dedupe hit, and `level_monitor/monitoring.py`'s bounded watcher does it when the preload lands mid-session. |
| Requested ≠ effective was invisible | `get_audio_status()` reports `noise_suppression` for BOTH processors (`requested` / `effective` / `degraded` / `reason_code`), `get_status()` carries the dictation block + `level_monitor_noise_suppression`, and the Microphone page renders `settings.audioEnhancement.denoiserFallback` when they differ. |
| A cold RTF probe could disable DPDFNet for the whole boot | the probe excludes 5 warm-up windows from the timing, takes two more readings when the first is over the ceiling, and their median decides; the ceiling itself is unchanged at 0.30. |

Evidence: `python bench/stress_mic_filters.py --no-asr --long-seconds 90` -> ALL GATES PASSED (14 rows)
with the chain reporting `NoiseSuppressor(dpdfnet)` from a cold start (the same boot reported `gtcrn`
before this change), RTF 0.098-0.107, drift 1.001x, and the broken-gate preset still tripping at
delta 171 dB with the take swapped to raw. Regression pins: `tests/test_level_monitor_divergence.py`,
`tests/test_level_monitor_processor_converge.py`, `tests/test_noise_suppressor_promotion.py`,
`tests/test_audio_status_effective.py`.

---

## 3. Verification

Measured on this machine (Windows, CPU-only, `.venv`) by `bench/stress_mic_filters.py`, which drives the
real `AudioProcessor` + `AudioPipeline` with real speech (Windows SAPI TTS, 16 kHz mono, 36 s) and the
live `faster-whisper` tiny model. Re-run it with:

```
python bench/stress_mic_filters.py                  # full matrix + live model
python bench/stress_mic_filters.py --no-asr         # chain/perf only
python bench/stress_mic_filters.py --long-seconds 600 --json bench-out/stress.json
```

| Case | Pass condition | Measured |
|---|---|---|
| 2 s take, 10/20/32/64/128 ms chunks | 2 s must not cost seconds | RTF 0.100-0.145 (0.20-0.29 s wall for 2.0 s), length exact every chunk size |
| 180 s take, 32 ms chunks | no drift | 21.18 s wall, RTF 0.118, per-minute 0.1167/0.1181/0.1182 (drift 1.013x), 2 880 000/2 880 000 samples |
| Speech + 5 dB pink noise, `auto` | keep speech, remove noise | speech -0.41 dB, noise -68.37 dB, **+67.97 dB SNR**, no guard trip |
| Speech + 5 dB pink noise, `noisy_room` | same | speech -0.41 dB, noise -68.33 dB, **+67.92 dB SNR**, no guard trip |
| 57 s of loud noise only (-36 dBFS), suppressor removes 60+ dB | guard stays quiet | no trip (21-case unit suite + live run) |
| Pauses inside speech | guard stays quiet | no trip; hammered by `test_pauses_between_sentences_do_not_accumulate` |
| Deliberately broken preset (gate open -10 dBFS) | guard fires, take still lands | trips at `delta=171 dB`, take swapped to raw, live WER 0.0 |
| Live model on the delivered 2 s take | no word loss | WER 0.0 vs the raw baseline for `auto`, `noisy_room`, and the recovered broken-gate take (`bench-out/take_*.wav`) |
| Guard cost while a suppressor/gate is in the chain | negligible | 43-51 us per chunk = 0.26% of a core at 20 ms chunks, 0.07% at 64 ms |
| dPDFNet preload RTF probe | under the 0.3 gate | 0.101 (probe), 0.118 sustained on 180 s |

The guard was redesigned during this verification: the first version judged "raw indicates speech"
from a rolling envelope max/min. The harness proved that wrong on real audio — 35 s of pink noise
reached 0.5 s of "voiced" time and tripped the guard on an honest preset, and 2 s pauses inside
speech let a noisy room look like a collapse. The shipped version requires *voiced* raw audio
(pitch strength, 80-400 Hz autocorrelation) plus one unbroken 300 ms stretch of deleted voiced
speech. Both false-positive classes now have a regression test.

Run every case against all presets and against `custom` defaults. Compare WER, not just how it
sounds.

---

## 4. Facts worth keeping

- Absolute gate thresholds make the chain level-dependent: it works at -20 dBFS RMS and mutes at
  -40 dBFS RMS. Any threshold added to this chain must be relative to the measured noise floor.
- A filter chain's output level is a poor health signal. Compare raw against filtered instead.
- `reset()` on a filter that caches derived arrays must rebuild them, not zero them.
- `FilterChain.process` returns `None` when any stage raises; `audio_pipeline` turns `None` into a
  pass-through, so a filter crash is silent. Log it.
