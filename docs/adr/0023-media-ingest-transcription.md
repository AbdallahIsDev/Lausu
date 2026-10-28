# ADR-0023: Universal Media-to-Text Transcription

## Status

Accepted

## Context

Users want to turn any video or audio into text: a pasted link (YouTube,
Vimeo, TikTok, X, Instagram, podcast feeds, direct `.mp3`/`.mp4` URLs, ...)
or a dropped local file, in any container/codec. The transcript is produced
by the existing local transcription engine and saved like any other
dictation (History + optional file export).

Constraints shaping this decision:

- **Reliability bar (product):** the feature must work the same for every
  user, every day. A "works today, broken tomorrow" runtime is rejected.
- **Small installer (XS-28):** the user-downloaded installer stays slim
  (~40 MB max). The heavy offline pack downloads silently after install.
  Rarely-used weight must NOT ride along with every app update.
- **Zero-reinvent (E13):** extraction logic comes from the community
  (yt-dlp, ~1000 supported sites), not a home-grown scraper.
- **User-initiated network only (C-DATA-1):** fetching a pasted URL is
  user-initiated and allowed; unsolicited egress stays forbidden.
- **Just-in-time consent (C-MIC-3):** first URL ingestion goes through the
  existing `openConsentGate()`; local files need no consent.
- **Dual allowlist lockstep (CONTRIBUTING §6.4):** new IPC commands land in
  both `voice_typer/server/ipc/registry.py` and
  `src-tauri/src/commands/sidecar_cmds/allowlist.rs`.

Key verified facts (web-checked, not assumed):

- `faster-whisper` already pulls **PyAV 18.1.0** (locked). Its wheels bundle
  full FFmpeg: any-format decode with zero new heavy deps and zero external
  `ffmpeg` binary. `av.open()` reads local files AND remote HTTPS URLs
  directly, with `open_timeout`/`read_timeout` options.
- Since yt-dlp 2025.11.12 (issue #15012), full YouTube support requires an
  external JS runtime. Supported: Deno >= 2.0 (recommended, default-enabled),
  Node >= 20 (explicit opt-in), QuickJS, Bun (deprecated). Without one,
  YouTube degrades over time; this is by upstream design, not a bug.
- YouTube's protection is a **program to run, not a question to answer**:
  solver scripts need a complete runtime *plus* browser/network abilities
  (fetch, crypto, on-the-fly npm). Bare language engines (MiniRacer,
  pythonmonkey, js2py) cannot satisfy this — verified in the EJS wiki.
  The old pure-Python solver is exactly what YouTube defeated in 2025.
- A second layer (PO token / BotGuard attestation, per-video badge) is
  handled by yt-dlp plugins maintained by the yt-dlp team, on the same
  runtime. Phase 2 of this feature.
- `yt-dlp` itself is Unlicense; the `yt-dlp-ejs` solver package bundles
  ISC/MIT code and needs third-party attribution.

## Decision

### Ingestion ladder (cheapest path wins; video bytes are never fetched)

1. **Tier 0 — zero-download streaming (default for URLs).** yt-dlp runs in
   resolve-only mode (`download=False`) and returns the direct **audio-only**
   CDN URL. PyAV opens that URL and stream-decodes over HTTPS range reads;
   16 kHz mono PCM chunks flow straight into the engine in ~30 s windows.
   A 2 GB video moves ~40-70 MB of streamed audio; **nothing is written to
   disk**.
2. **Tier 1 — audio-only download.** If streaming stalls or ranges are
   unsupported, download `bestaudio` to temp, decode locally, delete temp.
3. **Tier 2 — smallest muxed.** Only when no audio-only format exists
   (rare): smallest format containing an audio stream.
4. **Local files:** decoded in place, never copied.
5. **Subtitle fast-path (opt-in):** when a video ships manual captions,
   offer "Use subtitles (instant)" vs "Transcribe audio (accurate)".
   Instant, zero model load; accuracy tradeoff is explicit in the UI copy.

### Backend layout (`voice_typer/server/media_ingest/`, one concern per file)

`sources.py` (classify file/URL) · `url_resolver.py` (yt-dlp library mode,
format selector `bestaudio[protocol^=http]/bestaudio/best`, metadata) ·
`decoder.py` (PyAV to PCM chunk generator, local + remote) · `engine_loop.py`
(chunk windows to existing model + Silero VAD, cancellable, progress events) ·
`jobs.py` (single active job + cancel) · `storage.py` (History + optional
txt/srt/vtt/json export).

### IPC surface (both allowlists, §6.4)

`media_transcribe_start {source, options}` · `media_transcribe_cancel` ·
pushes `media_transcribe_progress` (percent, ETA) /
`media_transcribe_complete` / `media_transcribe_error` (user-readable
reason, never raw tracebacks).

### Packaging and updates (user-confirmed 2026-09-23)

- **Deno binary to offline pack.** ~40 MB, frozen, downloaded once with the
  pack. Rarely used (YouTube-only), almost never changes, never
  re-downloaded with app updates.
- **yt-dlp + solver scripts to the fast-moving side with their own silent
  mini-update channel** (few MB, no reinstall). YouTube breaks every few
  weeks; fixes ship in hours, not at the next full release. Deno is the
  player, solver scripts are the discs: YouTube changes are absorbed by
  script updates, the runtime stays put.
- **PO-token plugin is phase 2**, same runtime, same update channel.

## Consequences

Easier: one code path for all ~1000 sites; installer stays slim; YouTube
breakage heals via tiny silent updates (the SnapTube model); local-file and
non-YouTube flows never depend on the JS runtime.

Harder / risks: new deps (`yt-dlp`, `yt-dlp-ejs`, ISC/MIT attribution);
Nuitka must include yt-dlp package data (verify in CI build); Deno binary
per platform triple in the offline pack manifest; YouTube *will* break
periodically (hours-days) — surfaced as a clear "update the app" message,
never silent; DRM content is refused, not circumvented.

## Appendix: Edge-Case Catalog

| # | Case | Handling |
|---|------|----------|
| E1 | DRM / encrypted HLS (Widevine etc.) | Hard-fail, clear copy. Never circumvented. |
| E2 | Live / ongoing streams | v1: reject ("live streams unsupported"); capture-first-N-minutes is phase 2. |
| E3 | Age-gated / login-walled / private / deleted | Surface yt-dlp error with guidance. No cookie import in v1. |
| E4 | Geo-blocked | Surface region error verbatim. |
| E5 | Playlists / channels | v1: single item only ("paste one video link"). Expand-and-queue is phase 2. |
| E6 | Multi-audio-track containers | Decode default track; track picker is phase 2. |
| E7 | Video with no audio track | Fail fast: "no audio found". |
| E8 | Corrupt / truncated local file | PyAV error becomes a clean failure naming the file. |
| E9 | Mid-stream stall (Tier 0) | `read_timeout` fires, Range-resume retry, then Tier 1 fallback. |
| E10 | CDN URL expires mid-job | Re-resolve via yt-dlp, resume from last completed window. |
| E11 | Very long media (>~4 h) | Chunked windows keep memory flat; UI warns duration + ETA. |
| E12 | No JS runtime present | Non-YouTube unaffected; YouTube returns actionable error, never a hang. |
| E13 | Subtitle fast-path accuracy | Opt-in only; copy states captions are author-provided. |
| E14 | User cancels job | Token stops decode + engine; temps removed; partial transcript kept, marked partial. |
| E15 | Model not loaded | Lazy-load per job; "loading model" shown as its own progress phase. |

## Implementation record (2026-09-25)

v1 scope as built (verified against the tree, not the plan above):

- **URL ladder implemented**, not punted: resolve-only extraction
  (`url_resolver.py`, `skip_download`, `bestaudio[protocol^=http]`
  selector), Tier-0 PyAV range streaming with open/read timeouts +
  seek-resume (`decoder.py`), Tier-1/2 temp-download fallback
  (`downloader.py`), stall/expiry taxonomy with re-resolve (`E9/E10`),
  full edge taxonomy E1–E8/E11–E15, subtitle availability flag +
  opt-in UI + fetch path (`subtitles.py`, Media page checkbox).
  The `registry.py` / `allowlist.rs` comments saying "local-file jobs
  first, URLs in Phase 2" are stale and contradict this; URL jobs run
  end-to-end through `media_transcribe_start`.
- **JS runtime**: probed pack-first, then PATH deno, then Node ≥ 20
  (`runtime.py`); YouTube without any runtime fails loudly (E12),
  never hangs. Test battery green on 2026-09-25 (57 Python + 9
  renderer cases).

Open (not built; do not claim otherwise):

- **Deno in the offline pack**: `runtime.py` probes
  `<pack>/bin/deno[.exe]`, but no pack-assembly step ships it yet
  (no builder writes a Deno binary into the runtime-pack zip). Until
  then YouTube depends on a user-installed Deno/Node.
- **Mini-update surfacing**: `mini_update.check_refresh()` runs at
  startup and persists `update_available`, but nothing reads it back
  (no UI surface, no silent install — installs stay user-initiated
  by explicit decision). Wiring the Media page banner to it is the
  remaining half of the "fixes ship in hours" story.
- **Phase 2 per the Decision section**: PO-token plugin, playlists /
  channels, live capture, track picker.

## Addendum (2026-10-27): download-first tier order + batched windows

Measured on a 17-minute YouTube job: streaming the resolved signed audio URL
(`decode_chunks(..., remote=True)`) cost ~15 s of ingest per 30 s of audio
(~0.5x realtime) while each window's ASR cost <1 s — ASR was ~5% of wall time.
The tier order is therefore inverted: `downloader.temp_audio_download`
(audio-only, yt-dlp `bestaudio`) is the PRIMARY tier and the resume-aware
stream loop is the FALLBACK (E9/E10 semantics unchanged, just demoted).
Media windows are now one batched decode call (`WINDOW_SECONDS =
transcription_batching._BATCHED_SUPER_CHUNK_S`, above the engine's batched
minimum), so the parallel `BatchedInferencePipeline` (batch_size=8) runs per
window and chunk boundaries come from VAD speech timestamps rather than a hard
30 s cut. The batched pipeline requires `vad_filter` (or `clip_timestamps`),
so VAD-off audio stays on the sequential call.

## Addendum (2026-10-27, later): concurrent jobs with a serialized ASR lane

E14's "one active job" is replaced by a bounded concurrent manager
(`media_ingest/jobs.py`, `MAX_CONCURRENT_JOBS = 4`). Two different limits
apply, and conflating them would be a correctness bug:

* **Ingest is concurrent.** URL resolve, audio download and container decode
  are I/O plus cheap CPU, so up to four jobs run at once. The IPC ack is
  immediate: `resolve_media_url` moved into the job thread, so pasting four
  links enqueues four jobs without four network round trips in the handler.
* **ASR is serialized.** Every job decodes against ONE ctranslate2 model that
  is not thread-safe (`SystemWhisperEngine._inference_lock`), so a job takes
  `manager.asr_lane()` around each window decode. The lane is a
  `Semaphore(1)` re-entered once per WINDOW, not once per job: a job's windows
  interleave with another job's ingests but never with another decode. That is
  also why concurrency cannot change transcript quality: each window is still
  decoded by the same model, with the same settings, alone. The measured win
  is the ingest overlap, not the inference.

Cap semantics: `start` raises `job_busy` at the cap, `media_transcribe_status`
reports `{jobs, max_jobs}` so the renderer disables its inputs from the
backend's number, and a finished job frees its slot immediately. Cancel takes
an optional `job_id` (one job) or none (all).

**Cancel is scoped, and the target set is chosen under the manager lock.**
`cancel()` selects its targets and sets each job's `cancel_event` inside one
`with self._lock:` block. That Event is the abort source threaded into the
job's own decode, so the window stops between segments and nothing else is
touched. The lane neither reads nor writes the engine's abort flag, so there is
nothing to clear on entry and no stale flag can leak into the next job's first
window (the engine only checks abort BETWEEN segments, so a leftover flag used
to truncate exactly that first window). The engine-wide `request_abort()` /
`clear_abort()` pair is never called from here: one shared flag is exactly how
cancelling one media job truncated an in-flight dictation recording.
All four built-in backends take the keyword — whisper threads it into its
decode loop, parakeet and qwen poll it between chunks, cloud uses it for the
retry skeleton — and the probe stays feature-detected (`inspect.signature`:
a literal `abort_event` parameter or `**kwargs`), so a third-party backend that
only implements `transcribe_with_fallback(audio)` still decodes, just without
scoped cancellation.
Cancelling every job (`cancel(None)`) and `force_cancel_transcription()` both
go through this path.

**Job↔row ownership is explicit, never inferred.** Every start carries a
renderer-minted `client_id`; the backend echoes it on the ack and on all three
events (`progress`/`complete`/`error`), and the renderer resolves a row by
`client_id` first and `job_id` second. An earlier "adopt the only row still
waiting for an ack" heuristic is gone: with two starts in flight it dropped
every event for both rows (rows pinned in `starting`, `activeCount` never
dropping, the page permanently at capacity with no Cancel to escape) or bound
a late event to an unrelated fresh row.

**The picker's combined filter must stay first.** The native dialog pre-selects
filter 0, so "Audio" in that slot hid every video in the folder (C-UI-13). The
combined list is derived as audio ++ video with duplicates removed, and an
"All files" escape hatch is appended last.

**Multi-source text is links-only.** The field accepts several SOURCES only as
links (two or more real URLs become one job each), because a refused remainder
is written back space-joined so a single-line input cannot glue tokens — which
also means several local PATHS are not round-trippable after a partial batch;
multiple files go through the picker or drag-drop, which hand over a real path
list.

Stress evidence (real model, real PyAV decoder, real job manager + engine
loop; 6 jobs × 240 s clip, cap 4). `bench/media_concurrency_stress.py` prints
`RESULT: PASS` on each of these runs:

| model / device | flags | serial | concurrent | speedup | transcripts |
| --- | --- | --- | --- | --- | --- |
| `faster-whisper-tiny` int8 / CPU | `--device cpu --compute int8` | 57.6 s | 30.9 s | 1.86× | 6/6, 5060 chars each, identical to the serial baseline |
| `faster-whisper-large-v3-turbo` float16 / CUDA | `--device cuda --compute float16` | 66.2 s | 39.1 s | 1.69× | 6/6, 5087 chars each, identical to the serial baseline |

Each row is its own comparison: the speedup is serial → concurrent on the SAME
model and compute type. The rows are not comparable to each other — the tiny
int8 model spends far less time inferring per window, so a larger share of its
wall time is the ingest that concurrency overlaps, and its speedup is higher for
that reason alone. The `--device`/`--compute` defaults (`auto`, model default)
are what the app would pick; pass the flags above to reproduce a row exactly.

Re-measured 2026-10-28 (same host, same clips, `RESULT: PASS` on every
scenario in both runs):

| model / device | flags | serial | concurrent | speedup | transcripts |
| --- | --- | --- | --- | --- | --- |
| `faster-whisper-tiny` int8 / CPU | `--device cpu --compute int8` | 112.3 s | 83.7 s | 1.34× | 6/6, 5087 chars, identical to that run's serial baseline |
| `faster-whisper-large-v3-turbo` float16 / CUDA | `--device cuda --compute float16` | 66.9 s | 41.7 s | 1.60× | 6/6, 5087 chars, identical to that run's serial baseline |

Read the two sets as "concurrency wins", not as a benchmark score. The CUDA row
reproduced within 1%; the CPU row's absolute wall time roughly doubled under
normal desktop load, so its ratio fell with it — the win is the ingest overlap,
and on a CPU the ASR half of each job moves with whatever else is running. The
tiny row's transcript also came out 5087 chars here against 5060 in the record
above; the harness validates identity against the run's OWN serial baseline and
this work changes no decode setting, so the count is recorded as measured rather
than explained.

Reproduce:

```
.venv/Scripts/python.exe bench/media_concurrency_stress.py \
    --jobs 6 --clip 240 --cap 4 --device cpu --compute int8
```

The harness also asserts the cap refuses past the limit and refills, that a
per-job cancel leaves the survivors at full length, that the same clip decoded
concurrently is byte-identical, and that the log contract holds (one start
line + one outcome line per job). Its own run logs are gitignored
(`bench/*.log`); the numbers above are the record, not the files.

**The speedup ratio is measured, never gated (2026-10-28).** Identical flags on
this host produced 1.34× and then 0.76× — one FAIL line from an otherwise green
run — while every correctness scenario passed both times (serial 113.0 s
against the recorded 112.3 s), and a third run on the same idle box gave 1.41×
(serial 98.2 s → concurrent 69.5 s, 12 logical CPUs, 6/6 jobs at 5087 chars,
identical to that run's serial baseline, `RESULT: PASS`). Wall clock on a shared
CPU moves with every other process, so the harness prints the ratio and the
logical CPU count as `[INFO]` and gates only the correctness invariants.
