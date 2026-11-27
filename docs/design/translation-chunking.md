# Translation chunking — design proposal (2026-11-26)

Status: **PARTLY SHIPPED (dated note 2026-11-27).** The 2026-11-26 proposal
below is kept intact as history. Two of its options are now SHIPPED product
changes on `main`: background translator warm-up on a genuine user recording
start with idle unload (Option 4 defaults: `translation_warm_on_record=True`,
`translation_idle_unload_seconds=600`, `0` disables), and bounded GROUP
chunking of over-long final text (Option 2, no new setting). Live per-chunk
translation DURING recording (Option 1), media Stage B (Option 3) and a shared
GPU lock/queue (Option 5) are still PROPOSALS, not shipped. The dated
"Decisions and evidence" section immediately below is the current state; older
sections still describe the 2026-11-26 design only.

**Round 5 (2026-11-27) supersedes part of that status:** the translator no
longer has its own warm/idle system or two settings, and browser plugins now
load it at record start through the shared lifecycle hook. See the short
"Round 5 note" immediately below and `docs/design/model-lifecycle.md` for the
current model-lifecycle design. The group-chunking contract in §10 of ADR-0021
is unchanged.

## Round 5 note (2026-11-27) — plugin warm restored, private lifecycle removed

Plain English: the owner tested a real browser-plugin dictation with
translation on. The translator did not start loading until he pressed stop, so
he waited 16.3 s before the text pasted, and the readiness line was labelled
`[TTS]`. This was exactly the gap created by Round 4's decision to keep plugins
lazy and give the translator a private warm/idle system.

Decided and shipped in Round 5:
- **Reversed:** plugins now trigger the same record-start load as local and
  cloud dictation. The hook is `dictation_gate.decide_toggle` on a user `start`
  decision (`voice_typer/server/dictation_gate.py:80-84`), which both the local
  app and the plugin wrapper call; it respects the user-origin guard and never
  fires from app start/recovery.
- **Removed:** the translator's private warm thread, idle thread, 45 s join and
  two settings (`translation_warm_on_record`, `translation_idle_unload_seconds`).
  It now registers a few lines of policy with the shared component. Old configs
  containing the keys load cleanly and the keys are dropped.
- **Logs:** translator readiness now reads `[TRANSLATE] translation ready ...`
  with its own terminal color; `[TTS]` and other domains are untouched.
- The shared idle duration is the existing "Keep Models in Memory" setting
  (`model_idle_unload_minutes`); the UI label was pluralised and both
  translation tooltips now say plainly that translation adds time after you
  speak and is about 10x slower without a graphics card (roughly 10+ s per
  paragraph). Static text only — no hardware detection.

Per-chunk translation DURING recording is still **NOT shipped**. The best
combination (CPU speech recognition + GPU translator) cut the wait for an
8-minute dictation from 31.5 s to 12.8 s, but 3 of 5 groups at 30/120 s and 29
of about 96 groups at 480 s were revised by later audio, and on a CPU-only
machine translation takes roughly 11-14 s per paragraph. A reconciliation pass
and an owner decision are still needed before that design changes.

## Live verification pointer (dated 2026-11-27, Round 7)

Plain English: the "plugins stay lazy-load" note in the 2026-11-26 proposal is
now history — Round 7 proved the reversal live. With the translator kind
registered, readiness came at **18:04:51, 15 s before the 18:05:06 stop**; the
old 17:47 replay loaded the translator 49.6 s *after* stop. Commit `996fd214e`
registers the kind before the first press and before the startup gate, and the
post-fix startup preload was ready in 2.1 s at 18:21:24. Full evidence and
repeat commands: `docs/design/model-lifecycle.md`, section "Live verification
(dated 2026-11-27)".

Two more live facts relevant here:
- Bounded GROUP chunking (Option 2) was exercised through the real translation
  service with real text and the real GGUF: 735 and 9,800 characters stayed in
  **one call**; 14,700 characters produced **2 groups / 2 POSTs** with **0
  double spaces** at the join. No setting or bound changed.
- The no-model refusal now works at **every** start entry, not just the hotkey.
  Commit `74b7043ee` added a pre-mic gate at
  `voice_typer/server/recording_lifecycle_start.py:59-71`; at 18:53:39 a
  no-model press logged `[DICTATION] no active engine; dictation not started`,
  opened no mic and loaded no translator.

No ADR change was needed: Round 7 verified existing owner decisions, it did not
make a new one.

Read first: `docs/design/translation-audit.md` (what exists today),
`docs/adr/0021-transcription-translation-split.md` (Stage A / Stage B contract),
`docs/adr/0030-one-asr-model-and-text-translator.md` (one ASR + one text model).
The full today-map with file:line for every claim is in
`C:\Users\11\AppData\Local\Temp\opencode\r3-s3-report.md`.

## Decisions and evidence (dated note 2026-11-27)

Everything in this section is a dated note layered on top of the 2026-11-26
proposal below. Where an older section says "not approved", "recommended" or
"UNVERIFIED", that was the 2026-11-26 state; this section is current.

### Plain English first

Last round this document was a proposal and nothing was shipped. This round the
owner approved two things and they are now in the product:

1. **Load the translator in the background when a real user starts recording.**
   Not at app start, not on the hotkey thread, and never as a model download.
   Stop using it after 10 minutes of inactivity. The advanced config keys are
   `translation_warm_on_record=True` and
   `translation_idle_unload_seconds=600` (`0` turns the unload off). No renderer
   setting was added.
2. **Translate only over-long finished text in groups.** If the complete text
   fits the model context, the app still makes exactly one translation call,
   byte-for-byte as before. Above the measured safe bound of **2,176 input
   tokens** it splits at paragraph, then sentence, then whitespace boundaries,
   translates one group at a time through the one loaded translator, and joins
   with **only the whitespace that was in the source** (including no space at
   all). No new setting: the split happens only when the text would not fit.
   The skip decision is made once on the whole text. Any group failure returns
   the entire original transcript with one notice and no retry.

**Not shipped:** translating text while the user is still recording. We
measured that design; it cuts the wait after stop a lot with a GPU translator,
but later audio windows changed already-translated text (3 of 5 groups at
30 s and 120 s, 29 of about 96 groups at 480 s), so a reconciliation pass and
an owner decision are still needed. Media transcription still never translates.
Browser plugins still load the translator lazily; they did not get a second
warm-up hook.

In plain English, the numbers below come from two real bench days: Round 3 on
2026-11-26 (translator-only, short Arabic text) and Round 4 on 2026-11-27
(translator-only B1 plus real ASR/translation pipeline B2/B3). Some Round 4
pipeline runs fed audio instantly instead of on a clock — those are labelled
**virtual-paced**; only one 30 s set was **real-paced**. The machine was shared
with other Python and translator processes, and every VRAM figure is a
whole-GPU sample from `nvidia-smi`, not a per-app or peak measurement.

### One table per path

| Path | What happens today (shipped 2026-11-27) | DECIDED this round | NOT decided yet | Measured evidence (run file, date) |
| --- | --- | --- | --- | --- |
| **Local ASR** (hotkey / button / tray) | One translation of the finished transcript after stop; hidden 12/5/3/1.5 s audio windows only build the text. Translator warms on a genuine user recording start and unloads after 600 s idle. Over-long text is translated in bounded groups joined with exact source whitespace. | Warm-up only from a real user start, on a background daemon thread, never at app start, never a download; idle 600 s, `0` disables. Bounded GROUP chunking above 2,176 input tokens, no new setting, skip once, whole original text + one notice on any chunk failure, no retry, exact source whitespace on join. | Live per-chunk translation during recording; shared GPU lock/queue; per-script bound tuning. | Round 3 `bench/results/translation-compare.txt` + `translation-results.json` (2026-11-26): cold 15.4/33.9 s, whole 467 ms vs per-sentence 108 ms, `complete.Sentence` join bug, `slide/overlap` to `chip/interference`, cache_prompt no difference, 1.64x under CPU load. Round 4 `bench/results/b1-ar_one_paragraph_gpu/translation-compare.txt`, `bench/results/pipeline-translation-compare.txt`, `bench/results/pipeline-translation-results.json`, `bench/results/pipeline-real30/pipeline-translation-results.json` (2026-11-27). |
| **Cloud ASR** | Whole finished buffer, one request, one final text, then the same single Stage B call through the shared translation service. Warm-up applies if the translator's GGUF is present; cloud needs no local Stage A model. Group chunking applies to over-long text because it lives in the shared service. | Same bounded GROUP chunking and warm/idle contract as local; no cloud-specific branch or setting. | Live per-chunk translation of realtime WS bursts; any real cloud-provider A/B. | Round 3 code trace in §2.3 of this document (2026-11-26); no Round 4 cloud run — **UNVERIFIED**, no cloud credentials or network this round. |
| **Browser plugins** | `/stop` returns one string; plugin delivery translates once and the translator loads lazily. Group chunking applies to over-long text through the shared service, but there is no warm hook because the plugin session bypasses the recording lifecycle. | Explicitly decided: plugins stay lazy-load this round; no second warm hook and no second policy. | Plugin warm parity (needs the plugin session hook, files owned by another session); browser-side live STT algorithm still unaudited. | Worker A1 decision record `r4-s1-report.md` §2.8 (2026-11-27); Round 3 code trace §2.3 (2026-11-26); no plugin run — **UNVERIFIED**. |
| **Media** | 5 s pieces accumulate into 120 s windows, texts are joined, one flat string goes to History, decoder timestamps are off, and there is no translate call anywhere in media. | Nothing changed. Media Stage B stays unshipped and there is no new setting. | Per-segment translation with timestamps; a timestamped History/IPC output shape; toast + log failure routing. | Round 3 code trace §2.3 and §6 (2026-11-26) plus design `translation-audit.md`; no Round 4 media run — **UNVERIFIED** (no call site, no run). |

### Owner hypotheses and status

1. **"Translating per chunk is fine on GPU but may be slow on CPU" — TESTED.**
   Round 4 GPU translation is about **0.22–0.44 s per group** versus **1.6–2.0 s
   per group** on CPU. For a 480 s CPU-ASR dictation the wait after stop fell
   **31.5 s -> 12.8 s** with the GPU translator and **164.6 s -> 140.1 s** with
   the CPU translator (current whole-text design vs per-group, virtual-paced).
   Round 3 on short text went the other way: whole text **467 ms** vs per
   sentence **108 ms** each (8 sentences) and per chunk **268 ms** each (2
   chunks); chunking was not faster there. Sources:
   `bench/results/pipeline-translation-results.json` and S3 report §B3
   (2026-11-27); `bench/results/translation-compare.txt` (2026-11-26).
   The wait numbers are bench evidence for a possible future design, **not**
   shipped behavior.
2. **"Per-sentence chunking hurts quality" — TESTED, Round 3 exact example.**
   Whole text said "The window schedule starts a new slide every five
   seconds. Each slide contains three seconds of overlap." Per-sentence
   translation produced "The window layout starts a new slide every five
   seconds." and "Each chip tolerates three seconds of interference."
   (`bench/results/translation-results.json:61,68`, 2026-11-26). The same run
   also showed the join bug `complete.Sentence` instead of `complete. Sentence`
   (`bench/results/translation-compare.txt:22`); Round 4 showed the same input
   before and after the bench join fix in
   `bench/results/b1-ar_one_paragraph_gpu/translation-compare.txt`
   (2026-11-27). The whitespace bug was in the bench harness, not the product;
   the remaining wording drift is real and inherent to any multi-call
   translation. The shipped group join preserves source whitespace exactly.
3. **"cache_prompt helps" — NO CLEAR DIFFERENCE, stays OFF.** Round 3: OFF
   487.9/480.1 ms, ON 493.1/490.1 ms, outputs byte-identical (ON about 1.6%
   slower that run; an earlier run had ON about 3.6% faster). Round 4: OFF
   513.8/533.4 ms, ON 509.6/522.0 ms, again byte-identical. Sources:
   `bench/results/translation-compare.txt:49-61` (2026-11-26) and
   `bench/results/b1-ar_one_paragraph_gpu/translation-compare.txt:55-67`
   (2026-11-27). The production flag is unchanged.
4. **"ASR and translator contend for the GPU" — PARTLY TESTED.** Across the 24
   virtual-paced Round 4 runs, ASR decode with translation running was
   **0.64–2.22x** the ASR-alone decode (worst case 2.22x at 30 s Vulkan ASR +
   GPU translator, current design). Round 3's CPU-load simulation, which was
   not real dictation, showed a **1.64x** per-request slowdown. Sampled
   whole-GPU VRAM was about **3.0–3.8 GB** with GPU translation and
   **1.6–2.3 GB** with CPU translation, including other processes on the
   shared GPU; that is not a per-app footprint or a peak. There is no real CUDA
   contention measurement (Round 3 had no CUDA here; Round 4 used Vulkan), so
   true GPU contention and a per-process VRAM figure remain UNVERIFIED. No
   shared lock or queue was built. Sources:
   `bench/results/pipeline-translation-results.json` and S3 report §B3
   (2026-11-27); `bench/results/translation-compare.txt:64-71` (2026-11-26).
5. **"Warming at recording start beats cold start" — MEASURED.** Round 3 cold
   launch to healthy runtime **15.4 s** warm file cache / **33.9 s** cold cache;
   launch to first response **16.2 s / 34.5 s**. Round 4 first GPU launch
   **44.8 s** vs warm launches **2.1–2.7 s** (a second translator process on
   the shared machine made one replayed CPU run pay 39.3 s cold). The warm hook
   waits at most 45 s at translate time before proceeding. Sources:
   `bench/results/translation-compare.txt:73-79` (2026-11-26), S3 report §B1
   (2026-11-27), worker A1 report §2.4.

### Round 4 real numbers (from S3's report, 2026-11-27)

Pacing and sharing caveats first. The table immediately below is translator-only
B1 data: cold-start, decode throughput and latency, no audio pacing involved.
The second table is the 24-run B2/B3 matrix with **virtual pacing**: real audio
fed in 0.5 s slices without sleeping, so decode and translation timings are
real but wall-clock audio cadence is not. The separate **real-paced** 30 s set
is listed after the tables. All runs shared this machine with other Python and
translator processes; absolute latencies are not idle-lab numbers. VRAM is
sampled whole-GPU via `nvidia-smi`, not per-process and not peak.

Paste-ready summary from S3 report §"Summary table for S4":

| finding | real number | source |
|---|---|---|
| translator cold start, first GPU launch vs warm | **44.8 s** vs **2.1-2.7 s** | `bench/results/b1-ar_two_sentences_gpu`, others |
| translator decode throughput GPU / CPU | **185-197 tok/s** / **16-19 tok/s** | 12 B1 JSONs |
| whole-text latency GPU / CPU, 2 sentences | **179-182 ms** / **1.68-1.72 s** | B1 |
| whole-text latency GPU / CPU, multi paragraph | **1.08-1.38 s** / **11.0-14.2 s** | B1 |
| join bug before vs after (same input) | `complete.Sentence` -> `complete. Sentence` | `bench/results/b1-ar_one_paragraph_gpu/translation-compare.txt` |
| ASR 30 s window decode, native CPU / Vulkan | **622.6 ms** / **146.8 ms** (median, ≈8-11 s windows) | `probe-b2-native` |
| ASR 30 s window decode, app ctypes CPU / Vulkan | **968.0 ms** / **799.1 ms** | `pipeline-app-b2-30` |
| wait after stop, current vs per-group (30 s, CPU ASR + GPU translator) | **1.514 s** -> **0.855 s** | `probe-b3` |
| translated groups revised by later windows (30 s probe) | **3 of 5** | `probe-b3` |

S3 report §B3 highlights (the 24-run final matrix, **virtual-paced**):

| duration | wait current -> stream (CPU ASR + GPU translator) | wait current -> stream (Vulkan ASR + GPU translator) | revised groups / translated groups | ASR decode stream vs alone (range over 24 runs) |
|---:|---:|---:|---:|---:|
| 30 s | 1.614 s -> 0.845 s | 1.574 s -> 0.598 s | 3 / 5 | 0.64-2.22x |
| 120 s | 3.827 s -> 0.807 s | 3.437 s -> 3.051 s | 3 / ~24 | 0.64-2.22x |
| 480 s | 31.506 s -> 12.788 s | 12.936 s -> 10.333 s | 29 / ~96 | 0.64-2.22x |

With the CPU translator, wait after stop is 10.8-164.6 s and per-group
translation is about 1.6-2.0 s/group; the GPU translator is about 0.22-0.44
s/group. That is the decision-relevant difference, not the small ASR decode
shift. **Real-paced** 30 s, current -> stream: CPU ASR + GPU translator
1.391 -> 0.866 s; CPU ASR + CPU translator 9.921 -> 2.957 s; Vulkan ASR + GPU
translator 1.069 -> 0.404 s; Vulkan ASR + CPU translator 8.831 -> 2.137 s
(`bench/results/pipeline-real30/pipeline-translation-results.json`). Every
stream run still revised 3 of 5 translated groups. Longer real-paced runs
(120 s / 480 s) were not run — UNVERIFIED by runtime-budget choice.

### Next decision gates

1. **Live per-chunk translation during recording (Option 1).** Owner decision
   required; not shipped. Needs a reconciliation pass for revised groups
   (3/5 at 30/120 s, 29/~96 at 480 s), one source-language decision per cycle,
   protected-span carry, and a proof that the production word stream exists —
   the app's GGUF adapter exposes no word timestamps, so production would take
   the batch-finalize path. Quality diff: `bench/results/pipeline-translation-compare.txt`.
2. **GPU contention lock or queue (Option 5 B/C).** Revisit only with a dedicated
   quiet-machine run; current evidence is shared-machine, VRAM is whole-GPU
   sampled, and 0.64–2.22x decode ratios are not proof of a VRAM or kernel
   conflict. A shared scheduler must not let two models decode at once
   (ADR-0030 §1). The existing `translation_gpu_enabled=false` switch stays the
   answer for now.
3. **Bound tuning for non-Latin/Arabic scripts.** Latin 0.20 and Arabic 0.32
   tokens/char were measured on the installed tokenizer; Cyrillic 0.60,
   Devanagari 0.80 and Han/other 1.00 are deliberately conservative guesses.
   Re-measure with the installed `/tokenize` endpoint before raising the char
   bound; no new setting is proposed.
4. **Plugin warm parity.** Only if the owner wants it; needs a hook in the
   plugin session (files owned by another session) and must not create a second
   warm policy.
5. **Media Stage B with timestamps.** Needs decoder timestamp preservation
   across 120 s windows, a new History/IPC output shape with matching send and
   receive types, and toast + log failure routing. No decision this round.
6. **Real-app verification.** The warm/idle shipped behavior was proven with
   integration tests at the real recording entry point, not in the GUI, and
   no real GGUF load was exercised by that worker; the bench runs used real
   binaries but not the packaged app. With a GUI session available, boot the
   app and confirm warm-on-record, idle unload and the group join on a real
   over-long dictation before calling the lifecycle fully verified.

## 1. PLAIN-ENGLISH SUMMARY

Today the app always translates **one finished piece of text**, once. If the
speech model streams while you talk, those audio windows are only used to build
the transcript; they are never translated. At stop, one final string is handed to
the text model. Cloud providers get the whole recording in one request. Browser
plugins get one string from the browser and translate it at their own call site.
Media transcription never translates at all.

The owner wants to know whether that can be improved without breaking the
locked rule that transcription and translation stay separate, and without
blocking the first dictation on a cold model. This document compares five ideas:

1. translate completed sentences while the local recording is still running;
2. split long final text into sentence-bounded pieces before translating;
3. translate media segment-by-segment with timestamps preserved;
4. start loading the translator in the background when recording starts, and
   unload it after an idle timeout;
5. deal with the ASR model and the translator both wanting the same GPU.

**Recommendation in one paragraph:** keep "translate once on the final text" as
the default and implement the two low-risk pieces first — background translator
warm-up at recording start with idle unload, and opt-in sentence-bounded chunking
only for texts that would exceed the model context. Do **not** translate audio
chunks during recording yet; live text is still being revised, and the ADR's
skip rule and protected-span masking were written for a whole utterance. Add
media Stage B later, only after media decoding is changed to emit timestamps.
For GPU contention, do not build a new scheduler: the existing
`translation_gpu_enabled` switch (CPU offload) is the cheap, proven lever; a
shared lock or queue should only be added if a real measurement shows VRAM or
kernel contention, because both would add latency to the dictation path.
Every new behavior gets a setting whose default is today's behavior.

## 2. WHAT TODAY'S CODE ACTUALLY DOES (with file:line)

### 2.1 Local dictation — audio chunking, not text chunking

- Recording start runs on a daemon worker so the hotkey thread is not blocked:
  `voice_typer/server/recording_lifecycle.py:315-349`, call at `:399-400`.
  The real-time callback only appends PCM to a ring buffer
  (`voice_typer/server/recording/recorder.py:75-88,417-424`); snapshots are
  zero-copy views (`:450-469`).
- Silero VAD runs on the audio worker for silence detection / auto-stop, not to
  cut dictation windows: `voice_typer/server/recording/audio_pipeline.py:352-456`;
  settings `voice_typer/server/config/_schema.py:82,367-370`.
- Hidden streaming windows are **fixed-length with a silence nudge**: 12 s chunk,
  5 s step, 3 s left overlap, 1.5 s right guard, 6 s first chunk, 0.003 RMS
  threshold — `voice_typer/server/config/_schema.py:90-96`,
  `voice_typer/server/streaming_windows.py:16-26`. The planner is at `:79-111`;
  the end-of-window search picks the end of the quietest 50 ms frame in the last
  1 s and falls back to the requested end (`:113-153`). Worker mirror:
  `voice_typer/worker/streaming.py:70-82,295-348`.
- The worker-backed session pushes recorder deltas every 0.5 s
  (`voice_typer/server/worker_streaming.py:27-35,222-240`), sends all six timing
  values in the open frame (`:187-199`), and gets ONE final text at finalize
  (`:130-157`). The in-process fallback does the same with
  `transcribe_words()` (`voice_typer/server/streaming.py:207-257`).
- Only words outside the 1.5 s guard are committed; dedup is by timestamp and
  word tokens are joined with punctuation attachment, not a plain space join:
  `voice_typer/server/streaming_assembler.py:26-43,46-80,93-156`. At stop, a tail
  starting 3 s before the last committed word is re-decoded and merged
  (`voice_typer/server/streaming.py:271-362`), so recently committed words can
  still be replaced. The pipeline pops the session and calls `finalize()`; an
  empty result on loud audio triggers one whole-buffer batch retry
  (`voice_typer/server/dictation_pipeline/transcribe_step.py:188-235`).
- Batch decode itself is one worker request for the whole buffer, capped by
  `MAX_SAMPLES_CHUNKS` (`voice_typer/server/worker_backed_asr.py:111-164`).

### 2.2 Where translation happens (once, on final text)

- Stage order: transcribe → empty_check → translate → clean → … → store → paste —
  `voice_typer/server/dictation_stages.py:225-244`.
- `TranslationStage` makes ONE `_translate(text)` call and only then records
  `original_text` (`voice_typer/server/dictation_stages.py:80-93`).
- `_translate` gates on `translation_enabled` and calls `translate_text` once:
  `voice_typer/server/dictation_pipeline/translation_steps.py:21-35`.
- `translate_text` validates target, applies the skip rule, then calls the
  service once: `voice_typer/server/translation/service.py:389-428`; skip /
  detection `voice_typer/server/translation/prompt.py:131-181`.
- One protected-span mask and one POST: `service.py:267-312` and `:217-261`.
  Runtime: `-c 4096`, `max_tokens 1024`, `temperature 0`, `seed 0`,
  `cache_prompt: false` — `service.py:176-200,221-237`.

### 2.3 Other providers

- Cloud: whole finished buffer → one WAV → one request
  (`voice_typer/server/cloud/_engine.py:152-179,205-223`). Realtime model IDs
  burst 200 ms frames AFTER stop into one WS session and take one final text
  (`:225-244`; `voice_typer/server/cloud/_realtime.py:113-118`;
  `voice_typer/server/cloud/_realtime_ws.py:201-252`). Cloud engines have no
  `transcribe_words`, so hidden streaming is skipped
  (`voice_typer/server/streaming_session_coordinator.py:121-132`). Same single
  Stage B call on final text.
- Browser plugins: `/stop` returns one string
  (`tools/internal_plugins/_common/bridge/session.py:900-954,964-989`), `_deliver`
  calls `deliver_transcription` (`:1135-1152`), which translates ONCE and keeps
  raw text as `original_text` (`tools/internal_plugins/_common/delivery.py:32-54`).
  This file is read-only for this agent; the browser-side live STT algorithm was
  not audited — UNVERIFIED, reason: another session owns those files.
- Media: 5 s chunks accumulate into 120 s windows
  (`voice_typer/server/media_ingest/engine_loop.py:18-22,236-365`); window texts
  are joined with spaces (`:34-65`) and written to History
  (`voice_typer/server/handlers/media_job_runners.py:282-323,561`). Decoder
  timestamps are disabled (`voice_typer/server/transcription_batching.py:41`).
  No `translate` call exists anywhere in `media_ingest` — confirmed by grep.
  Real media translation with timestamps is UNVERIFIED (no call site, no run).

### 2.4 Existing opt-in helpers (unused in production)

- `bounded_chunks(text, max_chars=1600)` splits on sentence boundaries, packs
  units up to `max_chars`, and guarantees `"".join(chunks) == text`:
  `voice_typer/server/translation/chunking.py:15-55`. Note: CHARACTERS, while the
  runtime context is 4096 TOKENS (`service.py:182-183`). Protected-span markers
  contain no whitespace so they are never cut (`:38-40`).
- `translate_segments(segments, translate_fn)` replaces only `text` and keeps
  every other field byte-identical: `voice_typer/server/translation/chunking.py:58-75`.
- `translate_batch` translates a list through one loaded runtime:
  `voice_typer/server/translation/service.py:314-330`. `prewarm()` exists but is
  deliberately not wired anywhere (`:372-386`). Neither is called by the
  dictation pipeline (`docs/design/translation-audit.md:36-39,98-100,139-141`).

### 2.5 Device facts

- `config.device` = cpu|vulkan|cuda, default cpu
  (`voice_typer/server/config/_schema.py:77`); `translation_gpu_enabled` is a
  separate bool, default True (`:70-72`); both are on the SEC-002 allowlist
  (`voice_typer/server/config_validators/allowlist.py:158-169`).
- Translator runs the Vulkan-capable llama-server binary with `-ngl 99 -fa on`
  when its flag is on, `-ngl 0` when off
  (`voice_typer/server/translation/service.py:154-200`;
  `docs/adr/0030-one-asr-model-and-text-translator.md:119-121`).
- Effective ASR device is read from the loaded engine's `device_info`
  (`voice_typer/server/active_device.py:18-55`;
  `voice_typer/server/worker_backed_asr.py:154-158`), not from the config request.
- No lock or queue spans both models: the translator's RLock is private to it
  (`service.py:165-169`), the ASR lane is ASR-only
  (`voice_typer/server/media_ingest/engine_loop.py:101-103`).
- Which device each model really selects on the owner's machine: UNVERIFIED
  (no model or runtime run in this session).

## 3. LOCKED RULES THIS DESIGN MUST NOT BREAK

| Rule | Source | Consequence here |
| --- | --- | --- |
| Stage A = exact transcript, Stage B = separate text model; never merge | `docs/adr/0021-transcription-translation-split.md:15-24` | No ASR model may translate, and no translator may decode audio. |
| Skip Stage B only on confident same-language match; otherwise send text | `docs/adr/0021-transcription-translation-split.md:65-104`; `voice_typer/server/translation/prompt.py:131-181` | Any chunking must decide skip ONCE for the whole utterance, not per fragment. |
| Failure = original text + one notice, never empty, never auto-retry | `docs/adr/0021-transcription-translation-split.md:90-100`; `service.py:267-312` | Each chunk failure must fall back to its own original fragment; no retry loop. |
| One ASR model + at most one text translator; no "language packs" | `docs/adr/0030-one-asr-model-and-text-translator.md:7-39` | Chunking must not create a second ASR or a second translator instance. |
| One final delivery, no live partial text | `docs/adr/0030-one-asr-model-and-text-translator.md:135-139`; C-TRANS-1 | Live translation must not surface text during recording. |
| Delivery formatting is clipboard-only | C-TRANS-2; `tools/internal_plugins/_common/delivery.py:1-9` | Chunk joins must not add separators to History / recovery / `_last_transcription`. |
| Single-flight dictation | C-CONC-1; C-CONC-2 | No overlapping translate cycles; late effects re-check cycle ownership. |
| No big download without owner approval | C-AGENT-7; ADR-0021 §3 HARD RULE | Warm-up may only use an already-present model; it must never trigger a download. |

## 4. OPTION 1 — PER-CHUNK TRANSLATE DURING RECORDING (LOCAL PATH)

### Idea

Use the existing audio windows (12 s / 5 s step, `streaming_windows.py:79-111`) as
a cue: translate only sentences that are complete in the committed text, carry
the unfinished tail into the next window, and keep only bounded context (last N
sentences) in the prompt. The translator would be warm by the time the user
stops, so Stage B latency at stop could shrink.

### What would have to change

- A sentence-boundary detector over `StreamingTextAssembler.committed_text`
  (`streaming_assembler.py:69-80`) that only emits text ending in `.!?。！？؟`
  (the same boundary set as `chunking.py:16`).
- An explicit tail buffer carried across windows; the tail must be re-sent with
  the next chunk, and any previously translated sentence must not be re-sent.
- A hook on the `transcription_partial` publisher
  (`voice_typer/server/streaming_broadcaster.py`; worker publishes at
  `voice_typer/worker/_ws_connection.py:350-372`) that runs translation off the
  hotkey and audio threads.
- A single source-language decision for the whole cycle (from
  `needs_translation`, `prompt.py:161-181`) reused for every chunk, plus one
  final reconciliation at stop.
- A protected-span carry: masking happens inside `TranslationService.translate`
  per call (`service.py:288-299`), so a URL or number split across windows must
  be held back until it is unambiguous.
- A way to bypass this on the worker-backed path without creating a second
  translator: the worker session returns only a final string
  (`worker_streaming.py:130-157`), so live word text is only available from the
  partial push frames. On plugin/cloud paths this option does not apply at all.

### Risks

1. **Text is still being revised.** Overlap dedup and the tail re-decode can
   replace words already committed (`streaming.py:340-358`;
   `streaming_assembler.py:93-156`). A sentence translated early could become
   wrong and there is no clean way to retract it from History/clipboard.
2. **Skip rule fragments badly.** Per-chunk script detection would re-run the
   "Latin alone proves nothing" logic on short fragments
   (`prompt.py:131-181`, ADR-0021 §5.2 table at
   `docs/adr/0021-transcription-translation-split.md:74-87`).
3. **Protected-span split.** `protect_spans` masks URLs/numbers per call
   (`service.py:288`; `translation/preservation.py:20-57` per the audit); a
   split marker either corrupts the output or changes the model's prompt bytes.
4. **Context drift.** Pronouns and product names in later chunks lose the
   earlier context; the glossary (`config._schema.py:67-69`) helps but is not a
   guarantee. This is a known open flaw even for whole-text translation
   (ADR-0030 §6 "shared pronoun-direction flaw", lines 150-152).
5. **Amends the ADR.** This is not compatible with the current whole-text rule
   (ADR-0021 §5.2:69-87; `docs/design/translation-audit.md:98-100`). Any ship
   requires the amendment draft in §8, owner-approved.
6. **No evidence of benefit.** The local run in §11a measured 8 per-sentence
   requests at ~108 ms median each and 2 chunk requests at ~268 ms median each;
   the joined chunk output differed from whole-text output (a lost boundary
   space and drifted wording). That is evidence AGAINST shipping live chunking
   yet, not for it.

### Verdict

**Do not ship as the first step.** At most, build it behind
`translation_live_chunking` (default `false`) as an experiment, with a hard rule
that only punctuation-terminated committed sentences are translated, tail is
carried, and a final reconciliation pass at stop fixes anything the assistant
later revised. Needs a real-model A/B before it can be recommended.

## 5. OPTION 2 — TEXT-SIDE SENTENCE CHUNKING FOR LONG FINAL TEXT

### Idea

Leave Stage A → Stage B ordering untouched. When the final text is too long for
the runtime context, split the TEXT (not the audio) on sentence boundaries,
translate each piece through the already-loaded service, and join results
byte-exactly. This covers dictation, cloud and plugins, because all three hand a
single final string to `translate_text`
(`voice_typer/server/dictation_pipeline/translation_steps.py:21-35`;
`tools/internal_plugins/_common/delivery.py:32-54`).

### Design details

- Keep the skip decision ONCE on the whole text
  (`service.py:406-415` → `needs_translation`, `prompt.py:161-181`). If it skips,
  do not chunk at all.
- Apply `protect_spans` to the whole text first, then chunk the protected text;
  units keep `⟦VTn⟧` markers intact because markers contain no whitespace
  (`chunking.py:36-55`, audit `:76`). Restore spans after each chunk translation
  through the existing call path (`service.py:288-299`).
- Size the bound by TOKENS, not only characters. `-c 4096` is the runtime context
  (`service.py:182-183`) and `max_tokens 1024` is reserved for the answer
  (`:235`); the prompt shell + glossary also consume context
  (`prompt.py:18-20,70-129`). A conservative starting bound is ~1600 characters
  (`chunking.py:15`), but this is UNVERIFIED for Arabic/CJK token density —
  measure with the real tokenizer before choosing the shipped number.
- Join with `"".join(results)` — `bounded_chunks` already guarantees the input
  is recovered exactly (`chunking.py:38-40`); adding spaces would violate
  C-TRANS-2 because History and recovery would gain characters that were never
  dictated.
- Failure: use the same per-chunk fallback to the original fragment and the same
  one-notice-per-episode rule (`service.py:300-312`); no retry.
- Setting: `translation_text_chunking` (bool, default **false** = today's
  whole-text behavior). Optionally `translation_max_input_tokens` (int, default
  = "no limit"/disabled) so the feature only engages when needed.

### Risks

- Cross-chunk context loss (see Option 1 risk 4); glossary mitigates.
- A protected span that spans a sentence boundary is still one marker in the
  masked text, so it stays in a single unit — verify with a real case before
  shipping.
- More POSTs mean more chances for one failure notice; the audit pins exactly
  one request per failed call today (`docs/design/translation-audit.md:105-108`),
  so tests must be updated to the new per-chunk contract without weakening the
  no-retry rule.
- `translate_batch` (`service.py:314-330`) already serializes through one
  runtime; it does not add concurrency, which is good for GPU safety but means
  N chunks cost N sequential latencies.

### Verdict

**Recommended first behavior change**, gated and default-off, applied only when
the input exceeds the measured safe bound. It changes no chunk boundary the user
can see, works for every provider, and keeps the single skip decision intact.

## 6. OPTION 3 — MEDIA: PER-SEGMENT TRANSLATE WITH TIMESTAMPS

### Idea

For media, ask the decoder for segment/word timestamps, translate each segment's
`text` via `translate_segments` (`chunking.py:58-75`), and keep start/end times,
ordering and unknown fields byte-identical. This would give a translated
transcript that still lines up with the audio.

### What would have to change

- Stop asking `without_timestamps=True`
  (`voice_typer/server/transcription_batching.py:32-51`, specifically `:41`) and
  carry segment structs through `WindowsState`, which currently stores only
  `" ".join(self.texts).strip()` (`media_ingest/engine_loop.py:34-65`).
- Preserve the 120 s window and lane/lease contract (C-MEDIA-1/2/4;
  `media_ingest/engine_loop.py:236-365`;
  `handlers/media_job_runners.py:282-323`). Translation must run OUTSIDE the ASR
  lane so a slow translator cannot starve other media jobs or a dictation.
- Decide where the translated result goes: History currently receives one flat
  `state.text` (`media_job_runners.py:311-321,561`). A timestamped view needs a
  new output shape, which is a renderer/IPC change (E9: matching send/receive
  types) and is out of scope here.
- Setting: `translation_media_segments` (bool, default **false** = no media
  translation today).

### Risks / Verdict

**Later phase, not now.** The decode change affects every media job, and there
is no real-run evidence that segment timestamps survive the 120 s window merge
(UNVERIFIED — no call site and no model run;
`docs/design/translation-audit.md:139-141`). If built, keep Stage A timestamps
and `original_text`, and route failures through a toast per C-UI-11 and logs per
C-LOG-5.

## 7. OPTION 4 — WHEN TO LOAD THE TRANSLATOR

Owner decision already made: **no load at app start**, and **no blocking of the
first dictation**. Current code lazy-loads on first use
(`service.py:202-206`); `prewarm()` exists but is not wired
(`service.py:372-386`), and `ensure_runtime()` allows 180 s
(`service.py:202-205`) — calling it on the hotkey thread would repeat the
documented hotkey-blocking failure (`recording_lifecycle.py:315-331`).

### Proposal

1. At **recording start** (hotkey press), if `translation_enabled` is true and
   the pinned GGUF is already on disk, spawn a **daemon thread** that calls the
   existing `prewarm(config)` (`service.py:372-386`). No new process type, no
   second runtime: `get_service()` already caches one service
   (`service.py:359-369`).
2. Check the file locally via the existing resolver
   (`voice_typer/server/translation/paths.py:27-30,37-77`; catalogue
   `translation/catalogue.py:17-25,30-42`). If missing, do nothing: the download
   path is consent-gated and separate (`translation/download.py:30-88`;
   `service/model/_download_translation.py:27-55`), and warm-up must never
   trigger it (C-AGENT-7, ADR-0021 §3).
3. The warm-up thread must never hold `_toggle_lock` or the translation
   service's RLock beyond its own POST-free start call (the service lock at
   `service.py:165-169` is fine; it is short). Never let a warm-up failure
   produce a user notice — `prewarm()` already logs and returns False
   (`service.py:381-386`).
4. **Idle unload:** stop the cached runtime after a configurable idle period.
   Proposed value: **600 s (10 minutes)**. Shipped default: **`0` = disabled**,
   which preserves today's behavior (the service stays loaded until a settings
   key changes — cache key at `service.py:349-369` — or `shutdown()` at
   `:430-439`). The 600 s value is the recommendation for users who opt in;
   the owner may choose to make 600 the shipped default, but that is a behavior
   change from today and must be an explicit decision (§9).
   Implementation note: the cache key omits `translation_enabled`
   (`service.py:349-356`), so an idle timer must invalidate the same service the
   pipeline uses; do not create a second service object.
5. Reset the idle timer on each successful translate and on each warm-up; if a
   `stop()` races a POST, the existing RLock already waits for the request
   (`service.py:331-341`).
6. Plugin paths: `deliver_transcription` translates from the sidecar
   (`tools/internal_plugins/_common/delivery.py:32-54`) and its session start
   does not pass through `recording_lifecycle.py`. A pipeline-only hook will not
   warm up for plugins — either call the same background warm-up from the plugin
   session start, or accept lazy-load for plugins and record that as a known
   limitation. Which one is chosen is an owner decision (§9).
7. New settings (draft): `translation_warm_on_record` (bool, default **false** =
   today's lazy load), `translation_idle_unload_seconds` (int, default `0`).
   Both must be added to the config schema
   (`voice_typer/server/config/_schema.py:63-76`) and the SEC-002 allowlist
   (`voice_typer/server/config_validators/allowlist.py:158-168`) in the same
   change; renderer controls belong in
   `voice_typer/client/src/renderer/src/components/settings/PostProcessingSettingsSection.tsx:57-59,162-179,214-239`.
   String changes must go to all 8 locales (C-I18N-1).

### Risks / Verdict

**Recommended.** It is the only option that reduces cold-start pain without
touching the hotkey thread, without a download, and without changing when the
transcript is delivered. The idle unload is optional so the shipped default is
byte-for-byte today's lifecycle.

## 8. OPTION 5 — GPU CONTENTION (ASR + TRANSLATOR)

### The problem

`config.device` (default cpu) and `translation_gpu_enabled` (default true) are
independent (`config/_schema.py:70-77`; allowlist `:158-169`). The translator is
a Vulkan llama-server with `-ngl 99 -fa on` (`service.py:154-200`), while the ASR
engine may also be on Vulkan/CUDA (`active_device.py:18-55`). Two 1-3 GB models
on one 8 GB-class adapter can compete for VRAM and compute. Actual contention on
the owner's machine is UNVERIFIED (no run).

### Options evaluated

| Option | Feasibility from code | Cost / risk | User-visible behavior |
| --- | --- | --- | --- |
| **A. Translator on CPU while ASR on GPU** | Already supported: set `translation_gpu_enabled=false` → `-ngl 0` (`service.py:196-199`); setting exists in schema/allowlist/UI. | No new code. Slower translation per call; unknown magnitude (UNVERIFIED — no benchmark run). | Same text, possibly longer wait before paste. User controls it. |
| **B. Serialize ASR and translator behind one shared lock** | Would need a new cross-model gate; today the translator RLock is private (`service.py:165-169`) and ASR has its own lane (`media_ingest/engine_loop.py:101-103`). | Moderate code, high latency risk: translation already runs synchronously before paste (`dictation_stages.py:80-93`), so serializing would also block the next ASR start. No evidence it is needed. | Longer waits, especially on repeated dictations. |
| **C. Queue translation jobs with ordered delivery** | Needs an event loop, bounded queue, cycle ownership checks (C-CONC-2) and paste ordering (C-TRANS-1, C-PASTE-1). | Highest complexity: late effects, undo isolation, cancellation, stale cycles (C-CONC-2). No measurement yet. | Could feel faster if overlapped, but risks out-of-order paste — a correctness regression. |

### Verdict

**Recommend A as the default answer, do not build B or C yet.** Keep the
existing switch, document "if both models fight over the GPU, turn the
translator GPU switch off". The local run in §11a simulated ASR-like CPU load
and measured a 1.64x median slowdown per translation request — a reason to
measure before adding concurrency, but not proof of real GPU contention
(no CUDA on this machine). Revisit B/C only if a real ASR + translator run
shows contention. A shared scheduler would also risk violating ADR-0030 §1
if it ever let two models decode at once.

## 9. DECISIONS FOR THE OWNER

Each decision has a recommendation; nothing below has been implemented.

1. **Ship order** — recommend: (4) background warm-up + optional idle unload,
   then (2) long-text chunking; defer (1) live per-chunk and (3) media.
2. **`translation_text_chunking`** — recommend bool, default **false**; engage
   only above a measured safe bound. Accept the ADR-0021 amendment in §10 only
   if this ships.
3. **Bound** — recommend starting at ~1600 characters
   (`translation/chunking.py:15`) but require a tokenizer measurement against
   `-c 4096` / `max_tokens 1024` (`service.py:182-183,235`) before picking the
   shipped constant; current token density for Arabic/CJK is UNVERIFIED.
4. **`translation_warm_on_record`** — recommend bool, default **false** today,
   flip to true only after a real cold-start measurement; warm-up must be a
   daemon thread (`recording_lifecycle.py:315-331`).
5. **`translation_idle_unload_seconds`** — propose 600 s as the suggested value;
   recommend shipped default `0` (disabled = today's behavior), unless the owner
   explicitly accepts a lifecycle change.
6. **Plugins** — recommend waiting for lazy load on plugin paths in phase 1
   (the shared delivery helper stays untouched); wiring a second warm-up hook in
   the plugin session is a separate, later decision.
7. **GPU contention** — recommend the existing CPU-offload switch as the answer;
   no shared lock or queue until measured.
8. **Media Stage B** — recommend deferring until timestamped decode is proven;
   keep the current "no media translation" behavior as the default.

## 10. DRAFT AMENDMENT TO ADR-0021 (inside this doc ONLY — ADR not edited)

Proposed insertion after ADR-0021 §5.2
(`docs/adr/0021-transcription-translation-split.md:65-104`), to be applied only
if the owner approves Option 2/1:

> **§5.2a Bounded translation chunking (amendment, owner approval required).**
> The whole-text rule remains the default. When `translation_text_chunking` is
> enabled AND the protected Stage A text exceeds the configured safe bound, the
> service MAY translate sentence-bounded chunks (`translation/chunking.py:36-55`)
> through the single loaded runtime (`translation/service.py:314-330`). The skip
> decision is made ONCE on the whole text with the locked detection rules; a
> skipped utterance is never chunked. Protected spans are masked on the whole
> text before chunking and restored after translation; chunk units never cut a
> marker. Results are joined with `"".join()` so the delivered text differs from
> the original only by translation — no added separators, casing or spacing
> (C-TRANS-2). Each chunk that fails returns its own original fragment and
> contributes to the single per-episode notice; there is no automatic retry.
> `original_text` in History remains the complete Stage A text. A future
> live-per-chunk mode additionally requires: translate only punctuation-terminated
> committed sentences, carry the unfinished tail forward, bound carried context,
> and reconcile against the final text at stop before delivery. Two ASR models
> and two translator runtimes remain forbidden (ADR-0030 §1).

No file under `docs/adr/` was modified by this proposal.

## 11. VERIFICATION STATUS / UNVERIFIED ITEMS

- Verified from code: all file:line claims in §2, §3, §4, §5, §6, §7 and §8;
  the absence of any media translation call; the existence and non-use of
  `bounded_chunks`, `translate_segments`, `translate_batch` and `prewarm`.
- UNVERIFIED (reason stated):
  - real latency, cold start and CPU-load contention were MEASURED locally in
    §11a; real GPU contention remains UNVERIFIED (CUDA unavailable here).
  - token count of 1600 characters of Arabic/CJK against `-c 4096` — no
    tokenizer run.
  - the browser plugins' live STT algorithm — owned by another session, not
    needed for locating the translation call site.
  - media segment timestamp survival across 120 s windows — no call site and
    no real run (`docs/design/translation-audit.md:139-141`).
  - actual GPU selection by ASR and llama-server on the owner's machine — no run.
- No tests were run for this design-only change; no config, code, IPC surface,
  locale, ADR or existing document was edited.

## 11a. LOCAL BENCHMARK EVIDENCE (measured 2026-11-26, real GGUF + llama-server)

The translator GGUF (1,312,164,352 bytes) and `llama-server.exe` were already on
this machine and were resolved through the app's own
`voice_typer/server/translation/paths.py`; nothing was downloaded. The harness
`bench/bench_translation.py` ran 10 iterations with 2 warmups on `ar_long`
(361 characters, 8 sentences, 2 bounded chunks) and exited 0. All numbers below
are real; the readable output comparison is in `bench/results/translation-compare.txt`.

- Cold `llama-server` launch → healthy `/health`: **15.4 s** with a warm OS file
  cache; an earlier cold-cache run measured **33.9 s**. Launch → first complete
  response: **16.2 s** / **34.5 s**. Cold start dominates the wait — this is why
  background warm-up at recording start is the recommended first change.
- Whole-text translation: **467 ms median** (p90 493 ms). Per-sentence:
  **108 ms median** × 8. Per-chunk: **268 ms median** × 2. Batching both chunks
  through one runtime cost **498 ms** total. Chunking was not faster here.
- Throughput: **181 tokens/s wall**, **212 tokens/s decode**. Bench-process peak
  RSS **49 MB**; sampled `llama-server` child RSS **1405 → 1625 MB**.
- Whole-text vs joined chunks on the SAME input: outputs **differ**. The joined
  output lost the space at the boundary (`complete.Sentence`) and drifted the
  wording (`Sentence splitting` vs `Splitting sentences`). C-TRANS-2 forbids
  storing a separator that was never dictated, so any shipped chunking must
  define joins explicitly and be A/B'd for quality.
- `cache_prompt` ON vs OFF, two runs each: outputs were byte-identical between
  runs in both modes and between modes. Speed direction was noisy (this run ON
  ~1.6% slower; an earlier run ON ~3.6% faster). Do not flip the production flag
  on this evidence. In plain English: the instruction part of each request is
  the same, so caching lets the model skip re-reading it (usually faster), but
  a cached prefix can take a slightly different floating-point path and change
  the output text between runs.
- ASR-like CPU load (2 math worker threads, SIMULATION only): chunk median rose
  from **268 ms → 440 ms**, a **1.64x** slowdown; outputs stayed byte-identical.
  GPU-load simulation is UNVERIFIED (torch is CPU-only). English and short
  samples were not run — UNVERIFIED.
