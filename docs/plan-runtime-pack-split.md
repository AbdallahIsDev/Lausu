# Plan: shrink the installer, split core vs ML runtime pack

> **Scope map (2026-10-11 doc-sync; section numbers frozen):** this plan covers
> three concerns that share sections — (A) **runtime/worker split** (§4, §6,
> §7: worker exe, prewarm-as-startup-phase, slim-core↔worker IPC),
> (B) **offline-pack distribution** (§4.6, §4.7, §8, §10: manifest, paths,
> downloader, auto-update), (C) **installer packaging** (§5, §9 table row,
> §11: footprints, NSIS checkbox, CI gates). Concern labels inside existing
> sections mark which concern they serve; no section was renumbered or
> deleted (tests + scripts pin §4.4, §4.6, §4.8, §6.2, §11.x, §14 by number).

---

## 0. What changed since the 2026-08-12 version

The 2026-08-12 version was approved by the user as the direction. After
investigation, the direction stands (split the installer, ship a
runtime pack) but **many specific claims were wrong or under-specified**.
This rewrite corrects them:

| # | 2026-08-12 claim | Reality | Fix |
|---|---|---|---|
| 1 | "Qwen (LLM) converts to `onnxruntime-genai`. Real work: chat-template + sampling loop." | Qwen is an **ASR engine** (`qwen_asr.Qwen3ASRModel.transcribe(audio, sr)`). `onnxruntime-genai` has no Qwen3-ASR builder. | Defer Qwen to a separate phase. See `PLAN_ONNX_INTEGRATION.md` §4. |
| 2 | "Prewarm moves INTO the pack." | Prewarm is a **separate Nuitka-frozen binary** with 3 OS-level schedulers (Windows LogonTrigger, macOS LaunchAgent, Linux systemd). Moving it obsoletes 1,532 LOC of process tracking + 24 OS-scheduler tests + 3 build scripts. | §6 below: prewarm becomes a startup phase of the worker exe, not a separate binary. The OS schedulers are deleted. |
| 3 | "onnxruntime already sits in your venv unused." | It's a **transitive dep of `faster-whisper`**. After the split, faster-whisper moves to the pack, so the slim core loses it unless declared explicitly. | §5.3: declare `onnxruntime` explicitly in the slim core's deps for VAD. |
| 4 | "GPU variants source DLLs from the onnxruntime-gpu package." | `onnxruntime-gpu` does **not** bundle NVIDIA DLLs: it expects system CUDA. | `PLAN_ONNX_INTEGRATION.md` §6.1. Keep `nvidia_dll_paths.py` with `nvidia/*` paths. |
| 5 | "It already probes the network for update checks, same mechanism." | `docs/auto-update-feature.md` is explicitly **"NOT IMPLEMENTED (design only)"**. No GitHub Releases publishing step exists in CI. | §10: build the auto-update mechanism from scratch. |
| 6 | "The exact same websocket bridge." | Today's sidecar IS the WS server; Tauri is the client. Adding a worker means the slim core talks to TWO processes, a NEW second hop. | §7: define the worker IPC architecture explicitly. |
| 7 | "Three allowlists in lockstep." | There are **four** allowlists. The fourth (`ALLOWED_EVENT_TYPES` at `event_protocol.rs:49`) has no parity test. | §9.4: add the fourth allowlist + parity test. |
| 8 | "Pack auto-downloads on first launch by default... no progress bar, no dialog, no toast." | **NOW TRUE (user decision 2026-08):** pack download is always-on, silent, no consent gate. Historical note: it was temporarily consent-gated after the 2026-08-12 draft. | §8.4 superseded: always-on silent download. |
| 9 | "Installer drops to ~180 MB; disk drops from ~850 MB to ~430 MB." | Split adds a SECOND Python runtime (~50 MB) inside the worker onefile. Post-split disk is ~530 MB, not ~430 MB. | §5.5: corrected disk footprint. |
| 10 | "C-CI-8/NU-106 retire." | NU-106 is NOT a AGENTS.md rule, it's an inline evidence tag in the workflow YAML, cited in C-CI-8's rationale. Only C-CI-8 is the rule. | §11.2: correct the rule reference. |
| 11 | "Size gate asserts the sidecar stays ≤ ~185 MB." | No such size gate exists in CI today. `tauri-windows-build.yml:509-510` only `Write-Host`s the size. | §11.5: add the size gate. |
| 12 | "You already downloaded the ONNX version." | False. No `*.onnx` files, no `grikdotnet` reference, no manifest entry anywhere in the repo. | `PLAN_ONNX_INTEGRATION.md` §3.2. |
| 13 | 18 edge cases listed. | 0 fully handled by existing code, 5 partially handled, 13 unhandled. No tests exist for any. | §8: re-spec each edge case against the real codebase. |

---

## 1. The problem: current state (verified)

### 1.1 Installer size

The Windows installer is ~253-259 MB (NSIS 259 MB, MSI 257 MB, same content,
two installer wrappers). The Linux `.deb`/`.rpm`/AppImage and macOS
`.dmg`/`.app` are comparable in size. Inside the sidecar, measured from the
real dev environment:

| Component | What it is | Installed | In installer | Verdict |
|---|---|---|---|---|
| ctranslate2 | Lean whisper engine. Does NOT depend on torch. | 59.8 MB | 11.4 MB | **KEEP (in pack worker)** |
| faster-whisper | Whisper library talking to ctranslate2. | 1.3 MB | 1.0 MB | **KEEP (in pack worker)** |
| scipy + libs | Audio math: filters, resampling. Sidecar-side (audio pipeline, resampling) AND worker-bundled. | 115.5 MB | 31.7 MB | keep (sidecar-side + pack) |
| av + libs (PyAV) | Audio/video file reading. | 65.9 MB | 21.1 MB | keep (pack) |
| pyrnnoise | RNNoise background-noise removal. | 14.2 MB | 12.7 MB | keep (pack) |
| numpy + libs | Basic math. Sidecar-side (VAD state, audio, Parakeet/Qwen engines) AND worker-bundled. | 43.0 MB | 9.7 MB | keep (sidecar-side + pack) |
| onnxruntime | VAD inference + Parakeet/Qwen ONNX execution. Sidecar-side (`vad.py`, Parakeet/Qwen engines) AND worker-bundled. | — | — | keep (sidecar-side + pack) |
| PIL, huggingface_hub, glue libs | Icons, model downloader, plumbing. | ~30 MB | ~11 MB | keep (core + pack) |
| Compiled app code + Python runtime | Your own code, compiled, plus Python itself. | ~80 MB | ~50 MB | keep (core) |

### 1.2 Two structural problems

1. **Big download scares users.** A 259 MB installer looks bloated before users
   even try it.
2. **Every update = full re-download.** The Python sidecar is built by Nuitka
   as a "onefile": everything (Python, whisper, all libraries) is
   compressed into ONE single file. A one-line bug fix forces users to
   re-download ~200 MB because there is no way to "diff" compressed blobs.

---

## 2. The goal (revised)

1. **Split the app into two pieces**:
   - **Slim core** (~80-90 MB installer): the app itself, UI shell,
     settings, mic test, cloud engines, tray, hotkeys — PLUS the
     libraries the brain cannot run without (onnxruntime for the voice
     detector + Parakeet/Qwen, numpy/scipy for the sound pipeline;
     verified in code 2026-10-11, these never leave the sidecar).
     Updates cost ~80-90 MB forever. (Correction 2026-10-11: the old
     ~35 MB figure assumed those libraries move to the pack, but the
     brain imports them directly — see §5.3.)
   - **ML runtime pack** (~180-200 MB worker onefile, ~450 MB unpacked):
     all offline-transcription machinery (engines + libraries + VAD +
     Parakeet tokenizer). Downloaded ONCE, silently, in the background,
     with consent (see §8.4).
2. Keep everything local and offline-capable. Cloud providers
   (Groq/OpenAI/Deepgram) keep working with or without the pack.

---

## 3. Phase 1: the split: slim core + runtime pack

### 3.1 What "splitting" means

Today the installer is one big box. We split into two:

- **Box A: slim core.** Everything except offline-transcription machinery:
  window, settings, tray, hotkeys, mic test, cloud engines, config.
- **Box B: runtime pack (worker exe).** A frozen Nuitka onefile containing:
  onnxruntime, ctranslate2 + faster-whisper, numpy/scipy, av, pyrnnoise,
  Silero VAD ONNX, Parakeet tokenizer, the prewarm logic (absorbed as a
  startup phase: see §6).

### 3.2 Why a "worker exe" and not loose files

A compiled Python program knows where its libraries are only because they
were baked in at build time. Packing Box B as one frozen worker program
means: it always finds its own libraries, nothing can be accidentally lost,
and it can be verified as one file via SHA-256.

### 3.3 The worker is NOT "the same kind of thing as the current sidecar"

The 2026-08-12 version said "the worker is the same kind of thing as the
current sidecar, just smaller in scope." This is architecturally wrong and
must be corrected:

- **Today:** Tauri spawns ONE sidecar. The sidecar IS the websocket server;
  Tauri is the client (`src-tauri/src/sidecar/spawn/release_mode.rs:49,71`).
- **After split:** Tauri spawns the slim-core sidecar (same as today) AND
  the worker exe (new). The slim-core sidecar talks to the worker over a
  SECOND websocket connection. This is a **new 1-host↔2-processes pattern**,
  not "the same bridge."

### 3.4 Worker exe build: concrete specification (concern A: runtime/worker split)

The 2026-08-12 version gave no Nuitka flags, no entry point, no build script
for the worker. This rewrite specifies them. The `--nofollow-import-to=torch`
/ `--nofollow-import-to=transformers` flags below stay as normative build spec
(tamper guard: the torch sweep itself is DONE 2026-08-15, verified by
`scripts/build/check_bundle_torch_free.sh`, plan §11.3):

- **Entry point:** `voice_typer/worker/__main__.py` (implemented 2026-08-15). A thin launcher
  that sets up the websocket server, loads the engines on demand, and
  exposes the transcription API.
- **Build script:** `scripts/build/build_worker_windows.sh` (implemented), plus
  `build_worker_linux.sh` and `build_worker_macos.sh`. Modeled on the
  existing `build_prewarm_*.sh` scripts (which are the closest existing
  analog: a separate Nuitka onefile).
- **Nuitka flags:**
  ```bash
  nuitka --standalone --onefile \
    --include-data-files=voice_typer/server/silero_vad.onnx=voice_typer/server/silero_vad.onnx \
    --include-package=onnxruntime \
    --include-package=ctranslate2 \
    --include-package=faster_whisper \
    --include-package=numpy \
    --include-package=scipy \
    --include-package=av \
    --include-package=pyrnnoise \
    --nofollow-import-to=torch \
    --nofollow-import-to=transformers \
    --onefile-tempdir-spec=%LOCALAPPDATA%/lausu/worker-tmp \
    --output-filename=lausu-worker-$TARGET_TRIPLE.exe \
    voice_typer/worker/__main__.py
  ```
- **Tauri `externalBin`:** add the worker to ALL FIVE platform tauri conf
  files (`tauri.windows-x86_64.conf.json`, `tauri.windows-aarch64.conf.json`,
  `tauri.linux-x86_64.conf.json`, `tauri.linux-aarch64.conf.json`,
  `tauri.macos.conf.json`). Also add to `plugins.shell.scope` in
  `tauri.conf.json:60-62,127-138`.
- **macOS bundle id:** `com.Lausu.worker` (parallel to the host's
  `com.Lausu`).
- **PyInstaller fallback:** add a `lausu-worker.spec` (parallel to
  `lausu.spec`) for environments where Nuitka fails.

### 3.5 How updates work after the split

- The pack gets its **own version number** (e.g., "runtime-pack v3"),
  separate from the app's version. This version only changes when the
  engines/libraries inside it change: which is rare.
- **App update** → download the new slim core only (~80-90 MB). The pack on
  the user's disk keeps working.
- **Pack update** → the app checks the pack version on launch, and if a
  newer pack exists, downloads it in the background (with consent, see §8.4).

### 3.6 Integrity: verify-before-use (concern B: offline-pack distribution)

The 2026-08-12 version said the pack "reuses existing `tauri-binaries.json`
machinery." This is misleading: the codebase has **three separate
integrity systems**, and the pack would be a fourth:

1. `model_hashes.json` + `verify_model_integrity()` For HF model files.
2. `tauri-binaries.json` + `verify_tauri_binary_or_skip()` For the Tauri
   host binary (only 3 entries: `lausu-tauri` / `.exe` / `.app`).
3. `voice_typer/server/native/binaries.json` + `update_native_manifests.py`
 For the native hotkey listener.

**Decision:** create a fourth manifest `pack-manifest.json` at
`%LOCALAPPDATA%\lausu\runtime-pack\<version>\pack-manifest.json`
(schema: `{version, sha256, files: [{name, sha256, size}], min_proto_version}`).
Do NOT extend `tauri-binaries.json` Its schema is scoped to a single host
binary spawned by the launcher, and extending it creates coupling between
unrelated systems.

The `autostart_launcher.py` verify-before-use logic is reused as a pattern
(not as code): the worker launcher gets its own `verify_pack_or_skip()`
function modeled on `verify_tauri_binary_or_skip()`.

### 3.7 Where the pack lives (cross-platform) (concern B: offline-pack distribution)

The 2026-08-12 version hardcoded `%LOCALAPPDATA%\lausu\runtime-pack\`.
This is Windows-only. The actual paths (per `src-tauri/src/platform/paths.rs:163-356`):

| Platform | Path |
|---|---|
| Windows | `%LOCALAPPDATA%\lausu\runtime-pack\<version>\` |
| Linux | `$XDG_DATA_HOME/lausu/runtime-pack/<version>/` (default `~/.local/share/lausu/runtime-pack/<version>/`) |
| macOS | `~/Library/Application Support/lausu/runtime-pack/<version>/` |

The worker exe path is resolved per-platform via a new
`src-tauri/src/platform/worker_path.rs` (modeled on `paths.rs`).

### 3.8 The download experience (revised) (concern B: offline-pack distribution)

- First launch → pack download starts in the background **silently**
  (always-on, see §8.4). Behaves like infrastructure (think WebView2).
- **No progress bar in the main UI**, but a small "Preparing offline engine…"
  line appears in the mic test / transcription areas if the user tries to use
  offline transcription before the pack is ready.
- Safety net: if the pack is missing and the user tries offline
  transcription → the download starts (or resumes) silently and the UI shows
  the "Preparing…" line.
- Metered connection: a setting "Download offline engine later", default off
  (auto-download). On Windows, detect metered via `NLM` API; on Linux/macOS,
  no reliable detection: the setting is manual.

### 3.9 What works without the pack (concerns A+B: split behavior without the worker)

| User action | Pack present | Pack missing |
|---|---|---|
| Mic test page | full levels + VAD sensitivity | RMS meter works; the Silero VAD detector stays sidecar-side (`vad.py` + onnxruntime), so levels + VAD sensitivity keep working without the pack |
| Cloud transcription (Groq/OpenAI/Deepgram) | works | **works: cloud never needs the pack** (verified: `cloud_engines.py` + `llm_polish.py` have zero torch/ctranslate2/onnxruntime imports) |
| Local whisper / Parakeet | instant | silent download starts, "Preparing…" line, then works |
| Check for updates | downloads slim core only | same |

**Correction (extended 2026-10-11):** the 2026-08-12 version said "mic test...
VAD smartness degrades silently (VAD is in the pack)." That is wrong twice:
the mic test (`voice_typer/server/service/microphone_test.py`) uses RMS only
(no VAD), AND the Silero VAD detector is sidecar-side
(`voice_typer/server/vad.py` via onnxruntime — verified in code, with
numpy/scipy for the sound pipeline), never pack-side. Without the pack,
levels work and VAD sensitivity keeps working; what is missing is offline
transcription (whisper/Parakeet/Qwen engines live in the worker). The plan
must not over-promise VAD features in mic test, nor place VAD in the pack.

---

## 4. Disk footprint (corrected)

### 4.1 After Phase 2 (split, both installed)

> **Correction 2026-10-11:** the old ~35 MB slim-installer figure assumed
> onnxruntime + numpy/scipy move to the pack, but the sidecar imports
> them directly (Silero detector, sound pipeline, Parakeet/Qwen engines —
> verified in code), so they stay in the base. The numbers below reflect
> that; the 35 MB target is unachievable as specified.
- Slim core installer: ~102 MB real (measured 2026-10-04: 226 MB
  installer − 124 MB worker = host + brain; host + brain +
  onnxruntime/numpy/scipy for the detector/sound/engines that stay
  sidecar-side).
- Pack (worker onefile, downloaded): ~124 MB real (measured 2026-10-04
  `windows-worker-exe`; the old 180-200 MB guess was pessimistic).
- Slim core installed: ~250-320 MB (app + Python runtime + onnxruntime +
  numpy/scipy + glue libs).
- Pack installed (unpacked): ~450 MB (onnxruntime + ctranslate2 + scipy + av
  + pyrnnoise + numpy + engines + **second Python runtime ~50 MB**).
- **Total installed: ~700-770 MB.** Exact figures to confirm at build time;
  treat these as direction, not quote.

### 4.2 Why the second Python runtime

The worker is a Nuitka onefile, it bundles its own Python runtime (~50 MB)
because Nuitka compiles Python to C and links against libpython. This is
unavoidable for a standalone frozen binary. The slim core also has its own
Python runtime. Hence two runtimes.

### 4.3 Net win

- Installer download: 226 MB real (2026-10-04) → ~102 MB (slim core,
  host + sidecar 96.8 MB) + ~124 MB (pack, once) = ~226 MB first-time,
  ~102 MB thereafter.
- Updates: ~226 MB → ~102 MB (slim core) per release. Pack updates are rare.
- Disk: 850 MB → ~700-770 MB (torch gone, second runtime added, detector/
  sound libraries duplicated across both programs).

The disk win is smaller than the old plan claimed, but the **update win**
is the real prize: ~102 MB per release vs ~226 MB per release. (Correction
2026-10-11: the old 35 MB figures assumed onnxruntime/numpy/scipy leave the
base, which the sidecar's direct imports rule out — see §5.3. SP-1 status:
slim config + pack-dir spawn + ready/progress landed; publish run pending.)

---

## 5. Prewarm: re-architected (not just "moved")

### 5.1 What prewarm was (historical: standalone binary RETIRED 2026-09-27)

Prewarm was a **separate Nuitka-frozen binary** (`prewarm-<target-triple>[.exe]`)
launched by THREE OS-level schedulers:

- Windows: Task Scheduler with LogonTrigger.
- macOS: LaunchAgent (`RunAtLoad`).
- Linux: systemd user timer (`OnBootSec=10s`).

It was bundled as a Tauri **resource** (not `externalBin`), and the Rust
sidecar only passed its path to Python via the `VOICE_TYPER_PREWARM_EXE` env
var (`src-tauri/src/sidecar/spawn/prewarm.rs`, deleted).

The prewarm binary warmed the OS file cache by paging the heavy libraries'
files into RAM before the user actually transcribed. At plan time it paged
torch's 37 warmable files (945 MB) + transformers (when the backend is
Parakeet/Qwen).

### 5.2 What "moves INTO the pack" actually means

The 2026-08-12 version's "prewarm moves INTO the pack" hides a substantial
re-architecture. Three options:

#### Option P-1 (DECIDED; see §14): prewarm becomes a worker startup phase

The worker exe runs a prewarm phase on startup. Since 2026-10-27 that phase
is **backgrounded behind the WS bind**: the worker binds its listener, prints
the `worker_started` handshake, and only then starts the warm pass on a daemon
thread, so the slim core can connect and begin the model load immediately
instead of waiting 5-10s for imports. The phase also skips the model-weights
read (`include_model_weights=False`): the integrity gate a few seconds later
re-hashes those same multi-GB files, so warming them here was a second full
read for no benefit (mtime/size caching of the integrity verdict stays
rejected — the verifier deliberately re-hashes bytes). This eliminates:

- `prewarm-<triple>[.exe]` binary (3 build scripts deleted).
- `src-tauri/src/sidecar/spawn/prewarm.rs` (54 LOC).
- `prewarm_resolver.py` (242 LOC).
- `task_scheduler.py`, `prewarm_scheduler_posix.py`.
- PID-file + sentinel + completion-event machinery (1,532 LOC across
  `process_tracker.py` + `completion_events.py` + `paths.py`).
- 24 OS-scheduler tests (`mig15/test_prewarm_logontrigger_windows.py`,
  `mig16/test_prewarm_launchagent_macos.py`,
  `mig17/test_prewarm_systemd_linux.py`).
- `test_uninstall_prewarm_cleanup.py` (387 lines).
- `test_prewarm_spawn_resolver.py` (227 lines).

The prewarm logic itself (`cache_probe.py:_warm_imports`) moves into the
worker's startup sequence. The `_warm_imports` package list becomes
worker-internal (onnxruntime + ctranslate2 + numpy/scipy).

**Trade-off:** the worker warms imports after its listener is up, so the first
transcription request can arrive slightly ahead of the warm pass. That is the
intended trade: the model load dominates the cold path anyway (device probe +
integrity hash + weight load + CUDA smoke), and it no longer queues behind a
warm pass that re-read the same weights.

#### Option P-2: keep prewarm as a separate binary

Contradicts the "one frozen worker program file" claim in §4. Not
recommended.

#### Option P-3: `prewarm_now` RPC over the worker's `--ws`

The worker exposes a `prewarm_now` RPC that the slim core can call. The
worker warms itself on-demand. This is a variant of P-1 with lazier warming.

### 5.3 Decision: P-1

Prewarm becomes a worker startup phase. The OS schedulers are deleted. The
existing prewarm tests are deleted (or rewritten as worker-startup tests).
The `bench/bench_startup.py` target is updated to measure worker-startup
time (including prewarm), not tray-import time.

---

#### §6.3 addendum 2026-08-14: Cache Status surface restored (user-facing)

P-1's retirement collateral removed the Settings → About **"Cache Status"
card** along with the standalone-prewarm process machinery
(`get_prewarm_status` / `run_prewarm` / `open_prewarm_log`). The user
re-opened that decision: the card is a user-facing feature, so the IPC
surface was **restored verbatim from commit 5a319872** (per user
instruction: restore the deleted surface, do not reimplement, do not
revert any unrelated session work). What was restored:

- `voice_typer/server/prewarm/status.py` `get_prewarm_status`,
  `_probe_cache_status` + TTL probe cache, file read/write helpers;
  adapted to read/write the **worker status file** `prewarm-status.json`
  under the config dir (written by the worker warm phase, see
  `voice_typer/worker/_ws_server.py`) instead of the deleted
  sentinel/PID machinery. `prewarm_running` field dropped (no more
  process-tracker).
- `_handle_get_prewarm_status` + `_handle_open_prewarm_log` +
  `_handle_run_prewarm` in `status_handlers.py`; registry +
  rate-limiter + TS/Rust allowlist entries;
  `GetPrewarmStatusRequest` / `OpenPrewarmLogRequest` /
  `RunPrewarmRequest` types; `PrewarmAndUpdates.tsx` Cache Status
  card (badge, rows, **Run Prewarm Now**, Refresh, View log).
- `open_prewarm_log` now opens `worker.log` (the retired `prewarm.log`
  no longer exists).

`run_prewarm` was restored the same day (§6.3 addendum 2nd half) as a
**RE-IMPLEMENTATION**, not a verbatim copy: the pre-P-1 handler spawned
a detached `pythonw -m voice_typer.server.prewarm --force` subprocess,
and that module is deleted by design (P-1). The restored handler
instead runs the warm phase in-process via
`prewarm.status.run_prewarm_now()` `warm_imports_for_worker` (the
same file-paging pass the worker runs at startup) on a daemon thread,
plus a status-file refresh: so "Run Prewarm Now" re-warms the OS
standby cache on demand with zero deleted machinery. Start/stop of the
AUTOMATIC warm phase remains the `fast_startup` toggle.

Counts after the full restoration (2026-08-14 snapshot, preserved as history):
Python registry **71** (69 renderer + 2 host-only), TS **69**, Rust **67**
(`EXPECTED_COMMANDS` in `tests/tauri/mig19/test_phase4_validation.py` = 67;
see ADR-0020 §16 addendum 2026-08-14).
> **Superseded 2026-10-11:** live counts are Python registry **85**,
> Rust renderer allowlist **81**, bus events **51** (verified:
> `_COMMAND_REGISTRY` / `allowed_commands()` / `EVENT_TYPES`). The TS
> renderer allowlist was deleted at the 2026-09-17 Electron cutover
> (`voice_typer/client/src/main` gone); the live command contract is TWO
> allowlists (`ipc/registry.py` + `allowlist.rs`).

---

## 6. Worker IPC architecture (new, was under-specified)

### 6.1 The new 1-host↔2-processes pattern

Today: Tauri (client) → sidecar (WS server). The `SidecarState` struct
(`src-tauri/src/sidecar/spawn.rs:200-203`) is hardwired for ONE child, ONE
`ws_tx`, ONE heartbeat task, ONE pending map, ONE `respawn_in_progress`
flag.

After split: Tauri (client) → slim-core sidecar (WS server) AND slim-core
sidecar (client) → worker (WS server). The worker is a second WS server
that the slim-core sidecar connects to as a client.

### 6.2 What the worker needs

- **WS server:** the worker listens on a port (negotiated via the same
  `--ws` mechanism the sidecar uses). The slim-core sidecar connects as a
  client.
- **Heartbeat:** the worker needs its own heartbeat (parallel to
  `src-tauri/src/sidecar/ws/heartbeat.rs`). The slim-core sidecar sends
  pings; the worker responds.
- **Respawn scheduler:** if the worker crashes, the slim-core sidecar
  restarts it (parallel to `respawn_scheduler.rs`). Must NOT trip the
  sidecar's circuit breaker.
- **Auth:** the worker inherits the bearer-token / `hmac.compare_digest`
  pattern from `voice_typer/server/ipc/auth.py:61-70`. A shared token is
  passed via env var (same as today's sidecar auth).
- **Shutdown:** the worker shuts down when the slim-core sidecar shuts down
  (graceful via WS close, or forceful via SIGTERM/taskkill).
- **Single-instance:** the worker takes a lock file to prevent parallel
  spawns (parallel to `LausuSingleInstance`).

### 6.3 Worker lifecycle (the plan's biggest hole)

The 2026-08-12 version never specified: when does the worker start? When
does it stop? Does it stay running between transcriptions?

**Decision: long-lived worker, started after pack download.**

- The worker starts once (after the pack is downloaded + verified) and
  stays running for the app's lifetime.
- It holds ~450 MB of RAM (unpacked pack + loaded models).
- If RAM pressure is high, the slim-core sidecar can unload the worker
  (send a `worker_unload` RPC) and restart it on next transcription.
- The worker's prewarm phase runs once at startup (Option P-1).

**Trade-off:** 450 MB RAM is significant. The plan should add a setting
"Keep offline engine running" (default on) vs "Start on demand" (default
off for low-RAM machines).

### 6.4 New IPC events (the plan introduces ~13) (concern A: runtime/worker split)

The 2026-08-12 version's 18 edge cases implicitly introduce new IPC events.
As IMPLEMENTED (`voice_typer/server/service/offline_pack/events.py`
`OFFLINE_PACK_EVENT_TYPES`, 13 entries), the pack family uses the
**`offline_pack_` prefix** (not bare `pack_`):

1. `offline_pack_download_started` (push)
2. `offline_pack_download_progress` (push, silent: no UI)
3. `offline_pack_download_completed` (push)
4. `offline_pack_download_failed` (push)
5. `offline_pack_verified` (push)
6. `offline_pack_missing` (push)
7. `offline_pack_corrupt` (push)
8. `offline_pack_ready` (push: worker started + prewarmed)
9. `worker_started` (push)
10. `worker_crashed` (push)
11. `worker_unloaded` (push)
12. `transcribe_offline` (request: slim core → worker)
13. `transcribe_offline_result` (push: worker → slim core)

Each was added to (DONE 2026-08-15; TS entry historical — the TS renderer
allowlist `voice_typer/client/src/main/allowed-commands.ts` was deleted at
the 2026-09-17 cutover; the live command contract is TWO allowlists):
- `_COMMAND_REGISTRY` (`voice_typer/server/ipc/registry.py`).
- `allowed_commands()` Rust (`src-tauri/src/commands/sidecar_cmds/allowlist.rs`).
- `ALLOWED_EVENT_TYPES` Rust (`src-tauri/src/sidecar/ws/event_protocol.rs`, event gate).
- `PythonRequest` / `PythonPushEvent` TS unions.
- `hooks/usePython.ts` `KNOWN_EVENT_TYPES` list.
- `event_bus.py` canonical catalogue docstring.

Plus the parity tests:
- `tests/test_ipc_command_registry_sync.py`.
- `tests/test_command_registry_parity.py`.
- `tests/test_relaunch_event_name_parity.py`.
- `tests/test_notification_event_name.py`.
- A `tests/test_event_types_parity.py` (DONE: pins `OFFLINE_PACK_EVENT_TYPES`).

---

## 7. Edge cases: re-verified against the codebase

The 2026-08-12 version listed 18 edge cases. The investigation found: 0
fully handled by existing code, 5 partially handled, 13 unhandled. This
section re-specifies each against the real codebase.

### 7.1 Partial download resume

- **Codebase state:** `service/model.py` has resume logic for HF model
  downloads (via `snapshot_download`'s `resume_download=True`). No resume
  for the pack (no pack downloader exists yet).
- **Plan:** the pack downloader reuses the resume pattern from
  `service/model.py:_download_whisper_family`. The partial file is saved as
  `pack-<version>.partial`; on next launch, it continues from the byte
  offset. The partial file is never trusted, only a fully downloaded,
  checksum-verified pack is ever used.
- **Test:** `tests/test_pack_download_resume.py` (new).

### 7.2 Pack arrives corrupted

- **Codebase state:** `verify_tauri_binary_or_skip()` exists for the Tauri
  host binary. No equivalent for the pack.
- **Plan:** `verify_pack_or_skip()` (new, modeled on
  `verify_tauri_binary_or_skip`). Mismatch → discard + re-download (up to 3
  attempts, with exponential backoff).
- **Test:** `tests/test_pack_corruption_recovery.py` (new).

### 7.3 Atomic swap (crash during replacement)

- **Codebase state:** `security/file_io.py:266` documents that `os.replace`
  raises `PermissionError` on Windows when the destination is open. No
  `MoveFileEx(MOVEFILE_DELAY_UNTIL_REBOOT)` anywhere.
- **Plan:** on Windows, the worker exe must be stopped BEFORE the swap. The
  swap is: download to `pack-<new-version>/` → verify → stop worker →
  `rename pack-<old> pack-<old>.trash` → `rename pack-<new> pack-<current>`
  → start worker → delete `pack-<old>.trash`. On POSIX, the rename-over is
  atomic and the worker can keep running (the old inode stays alive until
  the process exits).
- **Test:** `tests/test_pack_atomic_swap.py` (new, Windows + POSIX).

### 7.4 Consent gate (DONE 2026-08-15; always-on silent download)

- **Codebase state:** `service/model.py` `_require_huggingface_consent()`
  blocks all HF model downloads without consent (GDPR-driven, CR-11).
  `tests/test_service_download_consent.py` enforces it.
- **2026-08-12 plan said:** "no progress bar, no dialog, no toast" for the
  pack. This **violated** the consent pattern at the time: the pack download
  phones home to GitHub Releases, revealing user IP to Microsoft.
- **Decided (user decision 2026-08, DONE 2026-08-15):** the pack download is
  **always-on** (silent background download, no consent gate, no progress bar
  in the main UI; a "Preparing…" line appears in the relevant areas). The
  earlier consent-gated design is superseded; the leftover "consent is
  requested once" sentences from the interim draft are void.
- **AGENTS.md:** C-DATA-1 DONE 2026-08-15 — the USER added category (4)
  "offline-pack download from GitHub Releases", so the pack download is
  explicitly permitted whether or not it is consent-gated (see
  `docs/auto-update-feature.md`). The `offline_pack_consent` toggle remains
  as a product/UX opt-in (default OFF), not a rule requirement.

### 7.5 Metered connection

- **Codebase state:** no metered detection exists.
- **Plan:** Windows, `NLM` API via `ctypes`/`comtypes`. Linux/macOS, no
  reliable detection; the setting is manual ("Download offline engine
  later"). Default: auto-download on Windows, manual on Linux/macOS (until
  a reliable detection API is found).
- **Test:** `tests/test_pack_metered_detection.py` (new, Windows only).

### 7.6 Corporate networks / proxies

- **Codebase state:** the update check (implemented 2026-08-13, see §10)
  handles proxies. The pack downloader uses the same
  `requests`/`httpx` stack with system proxy env vars (`HTTP_PROXY`,
  `HTTPS_PROXY`).
- **Plan:** the pack downloader inherits `assert_url_allowed()` from
  `tests/test_http_safety_ssrf.py` (SSRF protection) and respects system
  proxy env vars.
- **Test:** `tests/test_pack_proxy.py` (new).

### 7.7 GitHub rate limit

- **Codebase state:** no GitHub Releases download logic exists today.
- **Plan:** automatic retries with exponential backoff (1s, 2s, 4s, 8s, max
  3 attempts). On 403 (rate limit), respect the `X-RateLimit-Reset` header.
- **Test:** `tests/test_pack_github_rate_limit.py` (new).

### 7.8 Disk space check (before download)

- **Codebase state:** `asr_utils._check_disk_space_for_download()` exists
  for model downloads. Not reused for the pack.
- **Plan:** reuse `_check_disk_space_for_download()` with the pack size
  (180 MB compressed + 450 MB unpacked = 630 MB required). If insufficient,
  the download fails with a disk-space error; there is no user consent gate.
  show one tray notification + defer.
- **Test:** `tests/test_pack_disk_space_check.py` (new).

### 7.9 Disk fills during download

- **Codebase state:** no handling for disk-full mid-download.
- **Plan:** the download stops gracefully on `OSError` (disk full), the
  partial file is deleted, one notification is shown, retried later.
- **Test:** `tests/test_pack_disk_full_during_download.py` (new).

### 7.10 Pack deleted by cleaner/AV

- **Codebase state:** `autostart_launcher.py` does a cheap existence check
  for the Tauri binary on launch. No equivalent for the pack.
- **Plan:** at every launch, the slim-core sidecar checks
  `pack-<version>/worker.exe` existence. Missing → silent re-download. A
  full checksum check runs in the background so startup is never slowed.
- **Test:** `tests/test_pack_missing_on_launch.py` (new).

### 7.11 App-data folder write blocked

- **Codebase state:** `src-tauri/src/platform/paths.rs` resolves the data
  dir per-platform. No fallback for write-blocked dirs.
- **Plan:** fall back to the user's roaming folder (Windows) / `~/.lausu`
  (POSIX). If that's blocked too, run in "core-only mode" with one clear
  message. Rare, but handled.
- **Test:** `tests/test_pack_fallback_dir.py` (new).

### 7.12 Update during download

- **Codebase state:** no update mechanism exists (see §10).
- **Plan:** partial downloads are saved per pack-version. If the needed
  version is still the same, the download continues. If the version
  changed, the old partial is discarded.
- **Test:** `tests/test_pack_version_change_during_download.py` (new).

### 7.13 Dual instance race

- **Codebase state:** `LausuSingleInstance` enforces a single app
  instance via mutex (Windows) / lockfile (POSIX, best-effort).
- **Plan:** the pack downloader takes its own lock file
  (`pack-<version>.lock`) to serialize downloads across instances.
- **Test:** `tests/test_pack_dual_instance.py` (new).

### 7.14 Race: transcribe-at-finish

- **Codebase state:** no pack-ready state exists.
- **Plan:** "ready" is a single definition: downloaded + verified + worker
  started + prewarmed. All features check that state. Clicking early queues
  the request and it auto-continues when ready.
- **Test:** `tests/test_pack_transcribe_at_finish.py` (new).

### 7.15 Transcribe 2s after first launch

- **Codebase state:** no handling.
- **Plan:** the "Preparing offline engine…" line appears, the request is
  queued, and it auto-continues when the pack is ready.
- **Test:** `tests/test_pack_early_transcribe.py` (new).

### 7.16 Checksum slows startup

- **Codebase state:** `verify_tauri_binary_or_skip()` runs on startup for
  the Tauri binary.
- **Plan:** the pack checksum check runs in the background after startup,
  never blocking the window from opening. A cheap existence check runs
  synchronously.
- **Test:** `tests/test_pack_checksum_background.py` (new).

### 7.17 Pack download competes with model download

- **Codebase state:** each `download_model` call spawns its own thread. No
  shared queue.
- **Plan:** a shared download queue (`download_queue.py`, new). The pack is
  always lowest-priority and pauses while a user-initiated download runs.
  Both are resumable.
- **Test:** `tests/test_pack_download_queue.py` (new).

### 7.18 SmartScreen / MOTW / Gatekeeper

- **Codebase state:** `scripts/windows/sign-authenticode.ps1` signs the
  installer. `scripts/macos/install.sh:135-136` removes the quarantine
  xattr.
- **Plan:**
  - **Windows:** the worker exe is signed with the same Authenticode
    certificate (added to the signing foreach in
    `tauri-windows-build.yml:620-624`). The MOTW is removed after
    verification.
  - **macOS:** the worker is signed with Developer ID + notarized via
    `notarytool` + stapled (added to `tauri-macos-build.yml:661-667`).
    Gatekeeper handles the quarantine.
  - **Linux:** unsigned by design (per `tauri-linux-build.yml:393-397`).
- **Test:** `tests/test_pack_signing.py` (new, Windows + macOS).

---

## 8. Already exists: reuse, don't rebuild (verified)

The 2026-08-12 version listed 12 existing pieces. The investigation verified
them and corrected the claims:

| Existing piece | Where | What we reuse it for | Verified? |
|---|---|---|---|
| Download-progress events + resume | `useModelDownload.ts`, `event_bus.py`, `download_progress` push | Pattern (not code) for the pack downloader. `useModelDownload.ts` does NOT support silent mode: implemented as a separate `useOfflinePackDownload` hook. | ✅ pattern, ❌ direct reuse |
| Model download service | `service/model.py` | Pattern for the pack downloader (implemented as `service/offline_pack/`). Only `DownloadOutcome`, `push_progress`, `notify`, `poll_download_progress` are reusable; transport, manifest format, polling strategy are new. | ✅ pattern, ❌ direct reuse |
| Integrity manifest | `tauri-binaries.json`, `autostart_launcher.py`, `update_tauri_manifests.py` | Pattern for `pack-manifest.json` (new file). Do NOT extend `tauri-binaries.json` Different scope. | ✅ pattern, ❌ direct reuse |
| Websocket IPC bridge | `--ws` flag, `websockets` package, IPC registry | Pattern for the worker's WS server. The slim-core sidecar becomes a WS CLIENT of the worker, a new second hop. | ✅ pattern, ❌ direct reuse |
| Prewarm tooling | `voice_typer/server/prewarm/` | Logic moves INTO the worker as a startup phase. The separate binary + OS schedulers are DELETED. | ✅ logic, ❌ binary |
| Single-instance mutex | `LausuSingleInstance` | Pattern for the worker's own lock file. | ✅ pattern |
| Auto-update mechanism | `docs/auto-update-feature.md` | **BUILT 2026-08-13** (was "NOT IMPLEMENTED (design only)" in the 2026-08-12 draft). See §10. | ✅ built |
| Code-signing pipeline | `tauri-windows-build.yml` (4 steps) | Extend to sign the worker exe (5th binary). | ✅ exists, needs extension |
| Cloud engines | `cloud_engines.py`, `llm_polish.py` | Core works without the pack (verified: zero torch/ctranslate2/onnxruntime imports). | ✅ verified |
| Mic test service | `service/microphone_test.py` | Degraded mode when pack is absent (RMS only, no VAD). | ✅ verified |
| NSIS installer config | `tauri.windows-x86_64.conf.json` + `scripts/windows/installer-hooks.nsh` | "Include offline engine pack" checkbox via custom `Page custom` + nsDialogs (Tauri has no Components page; a Section would expose Tauri's Install section). Wired as `NSIS_HOOK_POSTINSTALL` → `installer-state.json`. | ✅ done 2026-09-30 |

### 8.1 The "three allowlists in lockstep" claim is understated (historical; live contract is TWO)

At the 2026-08-13 rewrite there were **four allowlists** + auxiliary sync
points (counts preserved as history: `_COMMAND_REGISTRY` 65 entries, TS
`ALLOWED_COMMANDS`, Rust `allowed_commands()`, Rust `ALLOWED_EVENT_TYPES`
40 entries with no parity test). At the 2026-09-17 Electron cutover the TS
renderer allowlist (`voice_typer/client/src/main/allowed-commands.ts`) was
DELETED with `voice_typer/client/src/main`. The live command contract is
TWO allowlists — `_COMMAND_REGISTRY` (`voice_typer/server/ipc/registry.py`,
85 entries) + `allowed_commands()` (Rust,
`src-tauri/src/commands/sidecar_cmds/allowlist.rs`, 81 renderer-reachable;
4 host-dispatched commands stay Rust-internal by design) — plus the distinct
Rust event gate `ALLOWED_EVENT_TYPES`
(`src-tauri/src/sidecar/ws/event_protocol.rs`) and the auxiliary sync points:

Plus:
- `PythonRequest` / `PythonPushEvent` TS discriminated unions.
- `hooks/usePython.ts` `KNOWN_EVENT_TYPES` list.
- `event_bus.py` canonical catalogue docstring.

And the parity tests:
- `tests/test_ipc_command_registry_sync.py`.
- `tests/test_command_registry_parity.py`.
- `tests/test_relaunch_event_name_parity.py`.
- `tests/test_notification_event_name.py`.
- `tests/test_event_types_parity.py` (pins the event gate).

### 8.2 The 8 locale files

Verified at `voice_typer/client/src/renderer/src/i18n/translations/{ar,de,en,es,fr,hi,ru,zh}.json`
(all 1,918 lines). Parity enforced by `tests/test_i18n_keys_parity.py` +
`tests/test_i18n_completeness.py` + renderer `locale-key-parity.test.ts`.
Helper scripts: `scripts/add_i18n_keys.py`, `backfill_i18n_keys.py`,
`apply_translations.py`, `_i18n_common.py`,
`client/scripts/translate-i18n{,-all}.js`.

### 8.3 New user-visible strings (must be added to all 8 locales)

- `"Preparing offline engine…"` (transcription area)
- `"Download offline engine later"` (settings checkbox label)
- `"Pack missing"` (tray notification)
- `"Pack corrupt"` (tray notification)
- `"Disk space low"` (tray notification)
- `"Pack download complete"` (tray notification)
- `"Include offline engine pack"` (NSIS installer text: NOT covered by
  renderer i18n parity test; needs separate installer-i18n story +
  `scripts/check_branding.py` `BUILD_CONFIG_FILES` allowlist entry)
- `"Keep offline engine running"` (settings checkbox, per §7.3)

All strings must use `{appName}` placeholder (C-BRAND-1, `APP_NAME = "Lausu"`
at `voice_typer/server/branding.py`).

---

## 9. Auto-update mechanism (BUILT 2026-08-13) (concern B: offline-pack distribution)

The 2026-08-12 version claimed "it already probes the network for update
checks: same mechanism." That was **false at the time**:

- `docs/auto-update-feature.md` was explicitly **"NOT IMPLEMENTED (design only)"**.
- No GitHub Releases publishing step existed in CI, only
  `actions/upload-artifact`.
- No "network is back" retry trigger existed.

Sub-agent 13 built the mechanism from scratch (DONE 2026-08-13; header of
`docs/auto-update-feature.md` now reads "Implemented 2026-08-13").

### 9.1 What was built

- **GitHub Releases publishing:** add a `softprops/action-gh-release` step
  to the release workflow. Upload the slim-core installer + the pack
  onefile + `pack-manifest.json` as release assets.
- **Pack-version check:** on launch, the slim core fetches the latest
  `pack-manifest.json` from the GitHub Releases URL (always-on silent, §8.4).
  If the version is newer than the local pack, download in the background.
- **Network-is-back trigger:** use Tauri's `window.addEventListener('online')`
  in the renderer (or `tauri-plugin-network` on the Rust side) to retry
  deferred downloads.
- **Proxy support:** respect `HTTP_PROXY`/`HTTPS_PROXY` env vars.
- **SSRF protection:** inherit `assert_url_allowed()` from
  `tests/test_http_safety_ssrf.py`.
- **Max-bytes limit:** inherit `_secure_read_text(max_bytes=)` from
  `tests/test_secure_file_io_max_bytes.py`.

### 9.2 C-DATA-1 constraint (DONE 2026-08-15)

C-DATA-1 (rule on allowed network calls) NOW explicitly permits the pack
download: the USER added category (4) "offline-pack download from GitHub
Releases" on 2026-08-15, whether or not it is consent-gated (see
`docs/auto-update-feature.md`). The "USER must extend" TODO from the
2026-08-13 draft is closed. Agents cannot edit AGENTS.md.

---

## 10. CI/CD (the 2026-08-12 version's biggest gap)

The user explicitly noted: "some of them don't handle the ci action, cicd
part." This section specifies the CI changes.

### 10.1 The constraint rule references (corrected)

The 2026-08-12 version cited "C-CI-8/NU-106." This is imprecise:

- **C-CI-8** is a AGENTS.md rule that mandates `--module-parameter=torch-disable-jit=no`
  to protect the Nuitka bundle while torch is shipped.
- **NU-106** is NOT a standalone AGENTS.md rule, it's an inline
  evidence tag in `tauri-windows-build.yml:422-448` and
  `build_sidecar_windows.sh:155-166`, cited in C-CI-8's rationale.

Only C-CI-8 is the rule. The user retires C-CI-8 after Phase 1c
verification (agents cannot edit AGENTS.md).

### 10.2 `tests/tauri/test_config_script_drift.py` HARD-FAIL (resolved in Phase 1c)

`TestNuitkaSidecarBuildsDoNotExcludeTorchDistributed` HARD-ENFORCED the
`--module-parameter=torch-disable-jit=no` flag and FORBADE 5
`--nofollow-import-to=torch.*` flags at plan time. Retiring the flag REQUIRED
deleting/updating this test class (DONE in Phase 1c: the class now asserts
the torch-free world — bare `--nofollow-import-to=torch` present).
C-CI-8 itself retires only by user direction (still pending; agents cannot
edit AGENTS.md).

### 10.3 "Grep frozen bundle for torch", implementation

No existing CI step does this. Nuitka onefile is a single ~100 MB PE binary.
The grep requires `strings` (Linux/macOS) or a Python script that extracts
the payload. Concrete implementation:

```bash
# scripts/build/check_bundle_torch_free.sh (new)
strings lausu-sidecar-$TARGET_TRIPLE.exe | grep -i "torch\." && exit 1
strings lausu-sidecar-$TARGET_TRIPLE.exe | grep -i "silero_vad.jit" && exit 1
echo "Bundle is torch-free."
```

Add as a CI step in `tauri-windows-build.yml` (and macOS/Linux equivalents)
after the sidecar build.

### 10.4 Size gate (concern C: installer packaging; implemented, see workflow)

`tauri-windows-build.yml` only `Write-Host`ed the size at plan time. The real
gates now live in CI (sidecar ≤ 185 MB torch-free gate, plan §11.3; worker
onefile ≤ 200 MB, Phase 2c target; slim-core installer ≤ 80 MB informational):

```yaml
- name: Assert sidecar size ≤ 185 MB
  run: |
    $size = (Get-Item lausu-sidecar-x86_64-pc-windows-msvc.exe).Length / 1MB
    Write-Host "Sidecar size: $size MB"
    if ($size -gt 185) {
      Write-Error "Sidecar exceeds 185 MB limit (got $size MB)"
      exit 1
    }
```

Also add a pack size gate (≤ 200 MB compressed) and a slim-core size gate
(≤ 80-90 MB per ADR-0026; the old 45 MB target assumed onnxruntime +
numpy/scipy leave the sidecar, which §5.3 rules out — superseded 2026-10-11).

### 10.5 Worker exe signing

C-CI-11 enumerated exactly 4 code-signing steps at plan time (sidecar+prewarm+native
listener; NSIS; MSI; standalone exe). The worker exe is a **5th binary**,
added to C-CI-11 by user direction 2026-08-15 (the retired prewarm binary is
NOT a signing target). In CI:

- **Windows:** add the worker to the foreach array at
  `tauri-windows-build.yml:620-624`.
- **macOS:** add to `tauri-macos-build.yml:661-667` (currently hardcoded
  list: needs a new entry).
- **Linux:** unsigned by design (`tauri-linux-build.yml:393-397`).

### 10.6 Cross-platform CI

The 2026-08-12 version was Windows-only. The plan must address:

- **macOS:** `tauri-macos-build.yml` Notarization + stapling for the
  worker. New `entitlements.plist` entry if the worker needs mic access.
- **Linux:** `tauri-linux-build.yml` `.deb`/`.rpm`/AppImage packaging for
  the slim core. The pack is a separate download (not in the `.deb`).

### 10.7 Ratchet baselines

After the migration, regenerate all 4 ratchet baselines:

- `coverage-baseline.json` (65.23% today: removing torch tests may drop
  coverage; run `scripts/coverage_ratchet_check.py --regenerate --force`).
- `mypy-baseline.json` (696 errors: torch-specific ignores go stale).
- `pyrefly-baseline.json` (~276 entries: 14+ for parakeet/qwen/prewarm go
  stale).
- `ruff-baseline.json` (torch-specific noqa comments go stale).

**Note:** ratchets refuse to auto-regenerate on improvement, the
`--regenerate --force` flag is required.

### 10.8 `.husky/pre-push` no longer runs pytest

The pre-push hook was leaned down: pytest (even the fast subset) was
removed: the full suite is greened at the end of every task
(AGENTS.md working convention), so push-time verification keeps only
the cached client typecheck + the mypy ratchet. The torch-import
concern below is now moot for pre-push; it applies to local
`pytest` runs and CI instead.

### 10.9 New artifact naming (C-CI-13)

C-CI-13 forbids renaming existing artifacts but allows adding new ones.
New artifact names:

- `lausu-slim-core-<version>-<triple>.exe` (Windows slim core).
- `lausu-runtime-pack-<pack-version>-<triple>.zip` (pack, platform-agnostic zip).
- `pack-manifest.json` (manifest, uploaded as a release asset).

Update `tauri-build.yml` download steps in lockstep.

---

## 11. Execution order (revised)

> **Status (2026-08-15):** Phases 1a–1d, 2a–2b implemented. Updated:
> (a) Phase 1d Qwen → ONNX is DONE, torch engine removed entirely
> (``qwen_onnx_model.py``); (b) the Rust host's worker *spawn* is
> IMPLEMENTED (`spawn_worker_release` / `spawn_worker_dev_mode` in
> `src-tauri/src/sidecar/spawn/worker.rs`, `parse_worker_started`
> handshake, 6 unit tests: committed 2026-08-15); the remaining gap is
> main.rs WIRING: `WorkerState` is not yet `app.manage()`d and nothing
> calls `initialize_worker` (the pack-verified spawn trigger), and the
> slim-core → worker ``transcribe_offline`` forwarding hop is still a
> stub ack: the runtime split is NOT yet end-to-end; (c) Phase 2c/2d:
> Phase 2d launch-time existence checks IMPLEMENTED 2026-08-15
> (``startup_tasks.check_offline_pack_on_launch`` wired into
> ``StartupSequence`` Cheap existence check, background checksum,
> ``offline_pack_missing`` event, always-on silent re-download (§8.4 DONE);
> ``get_status`` now carries ``offline_pack`` state; degradation markers
> in ``transcribe_offline`` + mic-test auto-transcribe). Phase 2c CI
> gates are PRE-WIRED (worker build + signing + torch-free + size gates +
> artifact uploads: all conditional on ``build_worker_*.sh``). The
> slim-core BUILD (sidecar without ML libs) + full-offline artifact remain
> BLOCKED on the runtime handoff: the slim-core server still imports the
> ML stack in 10 files (vad.py, transcription.py, parakeet_engine.py,
> qwen_onnx_model.py, …), so slimming the sidecar before the runtime
> handoff is verified would break the running app — complete the main.rs
> worker-spawn trigger + transcribe_offline forwarding first (see
> "Remaining work" below). The custom installer checkbox is DONE
> 2026-09-30: `scripts/windows/installer-hooks.nsh` shows a custom-page
> "Include offline engine pack" checkbox (default ticked) and writes
> `installer-state.json` via Tauri's real `NSIS_HOOK_POSTINSTALL` hook
> (the previous `customInstall`-only name was never invoked by Tauri v2).
> C-CI-11 (5th binary) + C-CI-13 (worker binary name) updated 2026-08-15
> by the user's direction; (d) the C-DATA-1 rule-text extension, DONE
> 2026-08-15: the USER added category (4) "offline-pack download from
> GitHub Releases" to C-DATA-1 in AGENTS.md, so the pack download is
> explicitly permitted whether or not it is consent-gated (see
> `docs/auto-update-feature.md`).
>
> > **Status (2026-10-11 doc-sync):** no code changed in this pass; the plan
> > text is reconciled with the built reality — (e) torch directives (§1.1,
> > §2.1, §3.3, §4.4 flags) marked DONE 2026-08-15 with the flags kept as
> > normative build spec; auto-update marked BUILT 2026-08-13 (§9 table, §10);
> > consent TODOs closed (§8.4, §10.2); Qwen decided C-2 + prewarm decided
> > P-1 (binary retired 2026-09-27), see §14; VAD placed sidecar-side (§4.9);
> > slim-core gates fixed to 80-90 MB per ADR-0026 (§11.4); brand Lausu (§9.3);
> > TS allowlist marked deleted at the 2026-09-17 cutover with the live
> > TWO-allowlist command contract (§7.4, §9.1, §15); pack events use the
> > `offline_pack_` prefix (§7.4); counts reconciled to registry 85 / Rust 81
> > / events 51 (§6.3 addendum). Section numbers and anchors unchanged.

1. **Phase 1a: Silero VAD → ONNX.** See `PLAN_ONNX_INTEGRATION.md` §2.
   - Rewrite `vad.py` (ORT backend + hidden state threading).
   - Add `silero_vad.onnx` + packaging (`MANIFEST.in`, `lausu.spec`,
     `build_sidecar_*.sh`).
   - Rewrite `tests/test_vad.py`, delete `tests/test_vad_dtype_optimization.py`.
   - Update `docs/adr/0005-silero-vad.md`.
   - **Gate:** VAD tests pass with ORT; `bench/bench_vad.py` latency ≤ torch baseline.
2. **Phase 1b: Parakeet → ONNX.** See `PLAN_ONNX_INTEGRATION.md` §3.
   - Rewrite `parakeet_engine.py` (use `onnx-asr` Option B-1).
   - Add `voice_typer/stubs/onnx_asr.pyi`.
   - Repopulate `model_hashes.json` via `scripts/populate_model_hashes.py`.
   - Update `MODEL_REGISTRY["parakeet"]` (repo_id, download_size_mb,
     network_behavior → consent-gated, fixes G4-H-04).
   - Add `ALLOW_PATTERNS_PARAKEET_ONNX` to `security/model_integrity.py`.
   - Add 5 new `tests/test_parakeet_onnx_*.py`.
   - **Gate:** Parakeet parity test passes (edit distance ≤ threshold).
3. **Phase 1c: torch sweep (except Qwen) — DONE 2026-08-15.** See `PLAN_ONNX_INTEGRATION.md` §8.3.
   - Sweep the 30+ torch import sites (§3.3).
   - Update `scripts/diagnostics.py:175-199`.
   - Update `pyproject.toml` (drop `torch>=2.0,<3.0`; keep `transformers`
     for Qwen).
   - Regenerate `requirements-lock.txt`.
   - Delete/update `tests/tauri/test_config_script_drift.py:437-512`.
   - Regenerate all 4 ratchet baselines.
   - Update doc-accuracy tests + tech-debt TODO freshness test.
   - Add `scripts/build/check_bundle_torch_free.sh` + CI step.
   - Add size gate to `tauri-windows-build.yml` (≤ 185 MB).
   - **Gate (superseded by Phase 1d):** `grep -ri "import torch" voice_typer/` → zero hits except
     `qwen_engine.py`. Full workflow run, confirmed with user (C-CI-2). Met at the time, then superseded: zero hits total after Phase 1d.
   - **USER action:** retire C-CI-8 in AGENTS.md.
4. **Phase 2a: worker exe skeleton.** See §4.4, §7.
   - New `voice_typer/worker/__main__.py` entry point.
   - New `scripts/build/build_worker_*.sh` (3 platforms).
   - New `src-tauri/src/platform/worker_path.rs`.
   - Add worker to all 5 platform tauri conf files (`externalBin`).
   - Pack manifest (`pack-manifest.json`) + `verify_pack_or_skip()`.
5. **Phase 2b: silent background downloader.** See §8, §10.
    - Implemented as `voice_typer/server/service/offline_pack/` (pack downloader, modeled on
      `service/model.py` but separate).
    - Implemented as `useOfflinePackDownload.ts` hook (silent mode).
    - IPC events (13 `offline_pack_*`/worker events: see §7.4) in the command
      allowlists + event gate + parity tests (DONE; TS entry historical —
      live contract is TWO allowlists).
    - `tests/test_event_types_parity.py` (pins the event gate).
   - All 18 edge-case tests (§8).
   - Auto-update mechanism (§10): GitHub Releases publishing, pack-version
     check, network-is-back trigger.
   - All 8 locale files updated with new strings (§9.3).
   - **USER action (DONE 2026-08-15):** C-DATA-1 in AGENTS.md extended
     with category (4): offline-pack download from GitHub Releases.
6. **Phase 2c: slim core build.** See §4, §11.
   - Sidecar build without ML libraries. (still open)
   - Custom installer checkbox for "Include offline engine pack" —
     **DONE 2026-09-30** (`scripts/windows/installer-hooks.nsh` custom
     page + `NSIS_HOOK_POSTINSTALL` → `installer-state.json`).
   - Full-offline artifact (slim core + pack bundled). (still open)
   - Worker exe signing added to CI (Windows + macOS).
   - New artifact names (C-CI-13).
   - **USER action:** update C-CI-11 in AGENTS.md (5th binary).
   - Publish path: `.github/workflows/runtime-pack-publish.yml` is wired
     (manual dispatch, draft default). **No pack asset exists on Releases
     yet** (verified 2026-09-30: only v1.0.0 / v1.1.0 installers). First
     real pack requires a live dispatch (build ~90–110 min).
7. **Phase 2d: launch-time existence check + degradation matrix.** See §8.10.
   - Cheap existence check on launch.
   - Background checksum check.
   - Degradation matrix live in mic test + cloud paths.
8. **Phase 1d: Qwen → ONNX — DONE 2026-08-15 (Option C-2).** See `PLAN_ONNX_INTEGRATION.md` §4.
   - Decided Option C-2 (pre-exported `andrewleech/qwen3-asr-*-onnx` via
     `qwen_onnx_model.py`); torch `qwen-asr` path removed.
   - Final torch sweep on `qwen_engine.py` complete + `transformers` dep dropped.

---

## 12. Out of scope (not part of this plan)

- Converting whisper to ONNX (decided: no, ctranslate2 already torch-free).
- Removing av / pyrnnoise / PIL (open decision 3 in the 2026-08-12 version —
  optional later pass).
- **GPU runtime pack** (open follow-up: CPU pack is the default; a GPU pack
  variant is a separate project. Note: `onnxruntime-gpu` does NOT bundle
  NVIDIA DLLs, see `PLAN_ONNX_INTEGRATION.md` §6.1. A GPU pack must bundle
  `nvidia-*-cu12` wheels or expect system CUDA.).
- Cloud-only / streaming transcription alternatives.
- Removing `sys.path` hacks used by `nvidia_dll_paths.py` (the `nvidia/*`
  paths survive torch removal, see `PLAN_ONNX_INTEGRATION.md` §6.2).

---

## 13. Open decisions (revised; items 1–2 DECIDED, rest open)

1. **Qwen migration option.** DECIDED 2026-08-15: C-2 (pre-exported
   `andrewleech/qwen3-asr-*-onnx` via `qwen_onnx_model.py`, Phase 1d DONE;
   torch `qwen-asr` path removed). See `PLAN_ONNX_INTEGRATION.md` §4.3.
2. **Prewarm architecture.** DECIDED: P-1 (worker startup phase). See §6.2.
   The standalone `prewarm-<triple>[.exe]` binary is RETIRED (build scripts
   deleted 2026-09-27); start/stop of the automatic warm phase is the
   `fast_startup` toggle, and "Run Prewarm Now" re-runs the worker warm
   phase in-process (§6.3 addendum).
3. **Worker lifecycle.** Long-lived vs. on-demand. Recommendation: long-lived
   with a "Keep offline engine running" setting. See §7.3.
4. **Metered-connection default.** Auto-download on Windows (NLM detection),
   manual on Linux/macOS. See §8.5.
5. **Full-offline installer as permanent second artifact.** Yes, always
   publish both. The slim core is the default; the full-offline installer
   exists for offline-install scenarios.
6. **The optional parallel cut list** (av / pyrnnoise / PIL). Same as the
   2026-08-12 version: optional later pass, each cut takes a feature.
7. **macOS GPU for Parakeet.** Test `CoreMLExecutionProvider` speedup. If
   <20% faster than CPU, ship CPU-only. See `PLAN_ONNX_INTEGRATION.md` §6.6.
8. **Pack source.** GitHub Releases vs. a CDN. Recommendation: GitHub
   Releases (no new infrastructure, free for open source).

---

## 14. Summary of file changes (this plan, excluding Phase 1)

| Action | File | Phase |
|---|---|---|
| **NEW** | `voice_typer/worker/__main__.py` | 2a |
| **NEW** | `voice_typer/server/service/offline_pack/` (implemented; planned as `service/pack.py`) | 2b |
| **NEW** | `voice_typer/client/src/renderer/src/hooks/useOfflinePackDownload.ts` (implemented; planned as `usePackDownload.ts`) | 2b |
| **NEW** | `src-tauri/src/platform/worker_path.rs` | 2a |
| **NEW** | `scripts/build/build_worker_windows.sh` | 2a |
| **NEW** | `scripts/build/build_worker_linux.sh` | 2a |
| **NEW** | `scripts/build/build_worker_macos.sh` | 2a |
| **NEW** | `scripts/build/lausu-worker.spec` (PyInstaller fallback) | 2a |
| **NEW** | `scripts/build/check_bundle_torch_free.sh` | 1c |
| **NEW** | `tests/test_event_types_parity.py` (pins the event gate) | 2b |
| **NEW** | 18 edge-case tests (`tests/test_pack_*.py`) | 2b |
| **MODIFY** | `src-tauri/tauri.{windows-x86_64,windows-aarch64,linux-x86_64,linux-aarch64,macos}.conf.json` (add worker `externalBin`) | 2a |
| **MODIFY** | `src-tauri/tauri.conf.json` (`plugins.shell.scope`) | 2a |
| **MODIFY** | `src-tauri/src/sidecar/spawn.rs` (generalize `SidecarState` for 2 children) | 2a |
| **MODIFY** | `src-tauri/src/sidecar/ws/event_protocol.rs` (`ALLOWED_EVENT_TYPES` event gate) | 2b |
| **MODIFY** | `voice_typer/server/ipc/registry.py` (`_COMMAND_REGISTRY`, 85 entries) | 2b |
| **DELETED** | `voice_typer/client/src/main/allowed-commands.ts` (TS allowlist deleted at the 2026-09-17 cutover; live command contract is TWO allowlists) | 2b |
| **MODIFY** | `src-tauri/src/commands/sidecar_cmds/allowlist.rs` (81 renderer-reachable) | 2b |
| **MODIFY** | All 8 locale files (`i18n/translations/*.json`) | 2b |
| **MODIFY** | `.github/workflows/tauri-windows-build.yml` (worker signing, size gate, torch-free check) | 1c/2c |
| **MODIFY** | `.github/workflows/tauri-macos-build.yml` (worker notarization) | 2c |
| **MODIFY** | `.github/workflows/tauri-linux-build.yml` (worker packaging) | 2c |
| **MODIFY** | `voice_typer/client/src/renderer/src/types/ipc/{requests,push_events}.ts` | 2b |
| **MODIFY** | `voice_typer/client/src/renderer/src/hooks/usePython.ts` (`KNOWN_EVENT_TYPES`) | 2b |
| **MODIFY** | `voice_typer/server/event_bus.py` (catalogue docstring) | 2b |
| **DELETE** | `voice_typer/server/prewarm/` standalone binary + schedulers (P-1 DECIDED; binary retired 2026-09-27; Cache Status surface restored per §6.3 addendum) | 2a |
| **DELETE** | `src-tauri/src/sidecar/spawn/prewarm.rs` | 2a |
| **DELETE** | `tests/tauri/mig15/test_prewarm_logontrigger_windows.py` | 2a |
| **DELETE** | `tests/tauri/mig16/test_prewarm_launchagent_macos.py` | 2a |
| **DELETE** | `tests/tauri/mig17/test_prewarm_systemd_linux.py` | 2a |
| **DELETE** | `tests/test_prewarm_spawn_resolver.py` | 2a |
| **DELETE** | `tests/test_uninstall_prewarm_cleanup.py` | 2a |
| **USER-ONLY** | `AGENTS.md` (retire C-CI-8; update C-CI-11, C-DATA-1) | 1c/2c |
