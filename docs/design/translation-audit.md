# Translation path audit — 2026-11-24

## PLAIN-ENGLISH SUMMARY (read this first)

The app does two separate jobs. First it writes down what you said, word for word
(Stage A). Then, if you picked a different output language, a small text model
translates that written text (Stage B). Those two jobs must never be merged,
and the text model must never be downloaded or started without a real user
action.

Today the translation model is one local GGUF file served by one `llama-server`
process. The app keeps that process alive and reuses it. For every dictation it
decides whether translation is needed, masks URLs/numbers so the model cannot
change them, builds one prompt, sends one request, and puts the result in the
clipboard and History. If anything fails, your original words are kept and you
get one short notice. There is never an automatic retry.

What this audit found and changed in this pass:

- The skip rule is correct: the model is skipped **only** when the source
  language is confidently detected and already equals the target. Mixed,
  short, or ambiguous text is always translated.
- The unchanged parts of the prompt (target language, glossary, marker list)
  were being rebuilt on every call. They are now cached; the prompt text sent
  to the model is byte-for-byte unchanged.
- The model process was already reused; an explicit `prewarm()` helper now
  exists but is **not** wired into startup (startup files belong to another
  agent). Normal translation still lazy-loads on first use.
- Cancellation is now an **opt-in** token for callers that need it. The dictation
  pipeline does not pass one, so its behavior is unchanged.
- Timeout and HTTP failures now say what happened in the log ("within 120s",
  "HTTP 503"); the user-facing text is still the same short localized notice.
- An unsupported output language now refuses before starting the model.
- No retry was added. ADR-0021 forbids automatic retries and this pass keeps
  that lock. The test suite pins exactly one request per failed call.
- Sentence chunking and segment/timestamp helpers were added as **opt-in**
  utilities only. The dictation path still sends the whole Stage A text in one
  call, as ADR-0021 requires. Media Stage B does not exist yet, so timestamp
  preservation there is UNVERIFIED in a real run.
- A benchmark exists but every performance number in it is marked
  `LOCAL-RUN-REQUIRED`. Nothing was measured on the owner's machine here, and
  no model or binary was downloaded.

Biggest open risks, in plain words: a cold model can make a dictation wait a
long time before paste; the request is synchronous; a very long transcript can
exceed the runtime's context window; and identical text is translated again
every time. Those need an owner decision before any behavior change.

## Locked rules this audit obeys

- ADR-0021 §5.2 (`docs/adr/0021-transcription-translation-split.md:65-104`):
  Stage A is exact transcription; skip Stage B only on a confident same-language
  match; send the whole text otherwise; failure = original text + one notice,
  never empty and never auto-retry.
- ADR-0030 (`docs/adr/0030-one-asr-model-and-text-translator.md:27-39,110-139`):
  one ASR model plus at most one text translator; plugins that bypass the
  dictation pipeline must translate at their own call site.
- ADR-0031 (`docs/adr/0031-onnx-to-gguf-migration.md:216-219`): the translator
  GGUF and its `llama-server` runtime are explicitly KEEP assets during the GGUF
  ASR migration. This pass does not touch the model or its registry row.

## End-to-end file:line map

Line numbers are from this checkout after the changes in this pass.

| Stage | Where | What happens |
| --- | --- | --- |
| Settings schema | `voice_typer/server/config/_schema.py:63-76` | Seven translation fields; `translation_enabled` defaults `False`, target `""` means "same as spoken". |
| Settings validation | `voice_typer/server/config_validators/allowlist.py:75,160-168` | SEC-002 allowlist; model/target are enum-checked, paths are local-dir checked. |
| Renderer controls | `voice_typer/client/src/renderer/src/components/settings/PostProcessingSettingsSection.tsx:57-59,162-179,214-239` | Enable switch, target select, GPU switch, glossary field. Read-only in this audit; no UI files were edited. |
| Pipeline order | `voice_typer/server/dictation_stages.py:64-94,164,233` | `empty_check` → `translate` → `clean` → … → `store` → `paste`. Only sets `original_text` when the text actually changed. |
| Pipeline call site | `voice_typer/server/dictation_pipeline/translation_steps.py:21-35` | Reads `translation_enabled`, target, spoken language; calls `translate_text(..., app=app)`; any exception keeps Stage A text. |
| Plugin call site | `tools/internal_plugins/_common/delivery.py:32-54,93-103` | Chrome-profile STT plugins bypass the pipeline; they translate here and store `original_text` alongside the final text. |
| Public entry point | `voice_typer/server/translation/service.py:389-428` | Normalizes languages, refuses unsupported targets, applies the skip rule, returns original text on any failure. Opt-in `cancel_event` lives here. |
| Skip / detection | `voice_typer/server/translation/prompt.py:131-181` | Script-based detection; Arabic/Devanagari/Cyrillic/Han are confident, Latin is not; mixed/short/ambiguous text is translated. |
| Protected spans | `voice_typer/server/translation/preservation.py:20-57` | Masks URLs, emails, inline code and numbers to `⟦VTn⟧` markers before the call; restores them verbatim after. Detection uses the same regex with spans removed. |
| Prompt | `voice_typer/server/translation/prompt.py:18-20,70-129` | Evaluated instruction preserved byte-for-byte. Glossary parse and the static prompt shell are cached; only the source text is appended per call. |
| Chat template | `voice_typer/server/translation/chat_template.py:13-166` | Embedded Jinja template written to the work dir by `service.py:141-150` and passed with `--jinja --chat-template-file`. |
| Model catalogue | `voice_typer/server/translation/catalogue.py:17-25,30-42,62-87` | One model: `IndexTeam/Index-Translate-2B-GGUF`, exact file/size/SHA, 8 core targets, `""` = same as spoken. |
| Asset resolution | `voice_typer/server/translation/paths.py:27-30,37-77,92-127` | Config override → env override → shared HF hub → app-local hub; runtime from installer dirs, app-data last. |
| Download | `voice_typer/server/translation/download.py:30-88`; `voice_typer/server/service/model/_download_translation.py:27-55` | Consent-gated, verified download into the shared HF cache; separate from the ASR `download_model` dispatch at `service/model/_download_dispatch.py:270-282`. Service inference never downloads. |
| Runtime process | `voice_typer/server/translation/service.py:154-202,331-339`; `voice_typer/server/tts/runtime_server.py:43-144` | One `llama-server` per service, 180 s health timeout, free loopback port, log tail on failure, terminate→kill on stop. `-c 4096`, greedy decode, one request slot behind an `RLock`. |
| HTTP payload | `voice_typer/server/translation/service.py:217-261` | One `/v1/chat/completions` POST, 120 s timeout, `temperature 0`, `seed 0`, `stream: false`, `cache_prompt: false`, `max_tokens 1024` (`:182-183` sets the 4096-token context). |
| Failure notice | `voice_typer/server/translation/service.py:45-112`; `voice_typer/server/i18n.py:45-48` | One notice per broken episode, cleared by a success. Tauri publishes a `notification` event; standalone also calls `app.tray.notify`. |
| Caching / reuse | `voice_typer/server/translation/service.py:349-388` | Service cached by model/path/runtime/GPU/glossary; changed settings stop the old process. `prewarm()` is explicit and best-effort. |
| Opt-in helpers | `voice_typer/server/translation/chunking.py:15-71`; `service.py:314-330` | Sentence-bounded chunks and timestamp-preserving segment mapping; batch translate through one runtime. NOT used by the dictation pipeline. |
| Storage | `voice_typer/server/dictation_pipeline/storage_step.py:26-55`; `voice_typer/server/history_db_internals/schema.py:126-130,336`; `crud_writes.py:200-208`; `writer_inserts.py:48-53` | Final text is canonical; `original_text` is nullable, encrypted with the same DEK, and excluded from list/FTS projections. |
| History UI | `voice_typer/client/src/renderer/src/components/dashboard/ActivityList.tsx:542-574` | Final / Original / Compare views exist only when the row carries a raw original. Read-only here. |
| Media | `voice_typer/server/handlers/media_job_runners.py` and `voice_typer/server/media_ingest/**` | Media jobs transcribe Stage A only. No media Stage B call site exists today; timestamps come from the ASR segments, not from a text model. |
| Tests | `tests/test_translation.py:1-621`; `tests/translation/test_translation_optimizations.py:1-287` | Prompt, skip rule, preservation, payload, paths, failure notice, Undo, lock behavior; new fake-runtime tests for reuse, prewarm, cancellation, error mapping, no-retry, chunking, segment alignment. |

## Findings (verified from code unless marked UNVERIFIED)

1. **Skip rule matches the locked contract** — `prompt.py:161-181`, pinned by
   `tests/test_translation.py:95-110,497-511`. Latin-only text never skips
   unless the pinned speaking language confirms the target; short text never
   skips. No change made.
2. **Whole-text rule preserved** — the old `split_for_translation` routing was
   removed in commit `3ee11a7da`; this pass adds chunking only as an opt-in
   helper (`chunking.py`) and does not call it from `translate_text`.
3. **Repeated prompt work was real** — `parse_glossary` and the static prompt
   blocks were rebuilt on every call. Now cached at `prompt.py:70,101`; the
   emitted string is byte-identical (`test_prompt_without_glossary_or_markers_is_byte_identical`).
4. **Process reuse already existed** (`service.py:202-206,359-370`) and is now
   pinned by a fake-process test: two translations → one start, two POSTs.
   `prewarm()` starts it early but is deliberately not wired to startup.
5. **No automatic retry** — ADR-0021 §5.2 forbids it. `test_failed_request_is_never_auto_retried`
   pins one POST for a failed call. Nothing in this pass adds a retry path.
6. **Cancellation is opt-in** — `TranslationCancelledError` (`service.py:50`) is
   raised before start, after the POST if the token fired mid-flight, and never
   treated as a failure notice. The dictation and plugin call sites do not pass
   a token, so user-visible behavior is unchanged.
7. **Clearer logs, same user copy** — timeout/HTTP/status are now named in the
   log (`service.py:244-254`); the localized one-per-episode notice is unchanged
   (`i18n.py:45-48`). No raw exception text reaches the user.
8. **Target validation added** — an unsupported target now returns the original
   and notifies once without starting the model (`service.py:410-413`). The
   config validator already restricted this; direct callers are now safe too.
9. **llama prompt caching stays OFF** — `cache_prompt: false` is intentional.
   Upstream documents that prefix KV reuse can make logits non-bit-identical
   for different batch shapes (llama.cpp server README and discussion #8947),
   while this path pins `temperature 0` / `seed 0` for deterministic output.
   Flipping it is a measured product decision, not a free optimization.
10. **Synchronous latency is the largest open risk** — `_translate` runs on the
    dictation path before paste (`dictation_stages.py:86-93`). A cold
    `RuntimeServer.start` allows 180 s (`runtime_server.py:27`), plus 120 s per
    POST (`service.py:43`): worst case ~300 s before text appears. No timing
    claim is made; UNVERIFIED without the real model and a local run.
11. **Context bound exists but no input bound** — `-c 4096` and
    `max_tokens 1024` (`service.py:182-183,235`) bound the runtime, but a Stage A
    text longer than the window is not split. Chunking would change the locked
    whole-text rule, so it stays opt-in pending an owner decision.
12. **No translation result cache** — identical text is re-translated. A bounded
    LRU keyed by (text, target, glossary) is plausible, but glossary edits and
    memory make it a product decision; not added here.
13. **Service cache key omits `translation_enabled`** — disabling translation
    leaves the runtime loaded until `shutdown()`/config-key change. Harmless for
    correctness; a possible idle-memory item.
14. **Media Stage B is absent** — `chunking.py:58-71` preserves timestamps and
    unknown fields for a future media call site, but no production caller uses
    it. Real media translation with aligned timestamps is UNVERIFIED.
15. **Two translation call sites must stay in sync** — pipeline
    (`translation_steps.py`) and plugin delivery (`delivery.py:39-49`). Both
    already pass `app=app`; new opt-in parameters were added with defaults so
    neither call site needed edits.
16. **Recent commit scope** — `32ecd9915` introduced the translation package and
    pipeline stage; `3ee11a7da` replaced per-sentence routing with whole-text
    detection and added shared-hub resolution; `b5c25e2ef` added the tray
    fallback and `original_text` storage; `87483f319` localized the download
    notice. All edits in this pass stay inside those files plus the two new
    opt-in helper/test files.

## Prioritized plan

**P0 — do now, no model needed (done in this pass)**
- Cache the static prompt shell and glossary parse; keep the emitted prompt
  byte-identical.
- Pin process reuse, one-request serialization, no-retry, and failure notice
  with a fake llama-server.
- Add explicit cancellation, prewarm, target validation, and specific timeout /
  HTTP log messages without changing the dictation path.
- Add the opt-in chunking / segment helpers and keep them out of Stage B.

**P1 — needs owner decision before any behavior change**
- Decide whether a cold translator may block the hotkey path. Options: keep
  synchronous; prewarm at startup (requires wiring a startup file owned by
  another agent); or make Stage B asynchronous with paste ordering guarantees.
  Measure first with `bench/bench_translation.py`.
- Decide whether whole-text translation may become bounded sentence batching
  for over-long inputs. This amends ADR-0021 §5.2 and must be written there.
- Decide whether `cache_prompt` may be enabled after an A/B quality check on
  the real model.

**P2 — later, low risk**
- Wire media Stage B through `translate_segments()` when a media translation
  feature is actually built; keep Stage A timestamps and `original_text`.
- Consider a small, bounded translation cache with explicit invalidation on
  glossary/config changes, with regression tests.
- Re-check the 120 s POST timeout and 180 s start timeout against the local
  benchmark's cold-start distribution.

## Verification status

Verified in this session: scoped pytest (`tests/test_translation.py` plus the
new focused file), 38 passed; fake process/server only, no network, no model.
UNVERIFIED: every performance figure, real `llama-server` behavior, real
translation quality, and any media Stage B integration. No model, binary or
dependency was downloaded or changed.
