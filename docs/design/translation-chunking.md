# Translation chunking — design proposal (2026-11-26)

Status: **DESIGN ONLY.** No code, config, UI, behavior or ADR was changed by this
document. Every option below is a candidate; nothing here is approved until the
owner picks from §9.

Read first: `docs/design/translation-audit.md` (what exists today),
`docs/adr/0021-transcription-translation-split.md` (Stage A / Stage B contract),
`docs/adr/0030-one-asr-model-and-text-translator.md` (one ASR + one text model).
The full today-map with file:line for every claim is in
`C:\Users\11\AppData\Local\Temp\opencode\r3-s3-report.md`.

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
