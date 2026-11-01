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

`level_monitor/_state.py:46` sets `_level_bar_filtered = True`; `level_monitor/worker.py:342-348`
runs the full chain and computes RMS from `flat_filtered`. Display gain is 8.0 (`_state.py:31`).

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
3. **Level bar: read the raw device signal.** `_level_bar_filtered` should default to `False`. See
   2.2 for why, and what replaces the lost information.
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

1. **Collapse detection.** Raw indicates speech (raw RMS above the noise floor + margin, or VAD on
   raw says speech) while `filtered_db` sits more than 25 dB below `raw_db`, for more than 500 ms
   cumulative.
2. **Fail open.** When collapse is detected, stop filtering for the rest of the session, log one
   WARNING with both numbers and the preset name, and surface one toast: the recording continues
   unfiltered rather than silently dying.
3. **Never auto-stop on a collapse.** The silence timer is suspended while the guard is active, so
   the user cannot be stopped for silence that the filter invented.
4. **Never deliver an empty result silently.** If a recording ends with speech present on raw and no
   filtered content, the result screen says the filter removed the audio and offers the unfiltered
   take, instead of a blank transcript.
5. **Log one line per recording** with `raw_db`, `filtered_db`, gain delta, and guard state. That
   line is what makes the next report diagnosable without a probe script.

The guard is cheap (two RMS values per chunk), it makes the VAD question stop mattering, and it fails
in the direction the user can live with: more noise in the transcript instead of no transcript.

### 2.4 Make the presets honest

- Reduce `auto` to high-pass plus one suppressor. Drop the gate, the compressor, and the EQ shaping
  from the default; keep them in `custom` for people who want a podcast voice.
- Add a gain-staging test: feed speech at -20/-35/-50 dBFS and assert output within ±3 dB of input
  and zero exact-zero runs. That single test would have caught 1.1, 1.2, and 1.3.
- Any neural backend replaces the suppressor slot only (`noise_suppression_method`); it never joins a
  chain of two suppressors in series.

---

## 3. Verification

Per recording, log and compare:

| Case | Pass condition |
|---|---|
| Quiet speaker, -45 dBFS RMS | Level bar tracks speech; zero exact-zero runs; WER within 2 points of the same take with quality off |
| Normal speaker, -25 dBFS RMS | Output within ±3 dB of input RMS; no gate pumping |
| Second and third recording in one session | Identical output to the first (catches 1.3) |
| Background TV / other voices | No word loss; suppression may not exceed 10 dB on speech frames |
| Auto-stop check | No silence warning or auto-stop while speech is present |
| Toggle preset mid-recording | No click, no dropped chunk, no chain-state poison |
| Deliberately broken preset (open -10 dB) | Guard fires, chain bypasses, transcript still lands |

Run every case against all four presets and against `custom` defaults. Compare WER, not just how it
sounds.

---

## 4. Facts worth keeping

- Absolute gate thresholds make the chain level-dependent: it works at -20 dBFS RMS and mutes at
  -40 dBFS RMS. Any threshold added to this chain must be relative to the measured noise floor.
- A filter chain's output level is a poor health signal. Compare raw against filtered instead.
- `reset()` on a filter that caches derived arrays must rebuild them, not zero them.
- `FilterChain.process` returns `None` when any stage raises; `audio_pipeline` turns `None` into a
  pass-through, so a filter crash is silent. Log it.
