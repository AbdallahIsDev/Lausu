# Runtime delivery options — read-only decision brief

Read-only research, 2026-11-28. No code, workflow, test or settings file was changed. Only this
document was written. Evidence labels: **MEASURED** = read from this machine or GitHub REST
metadata; **VERIFIED** = proven from source/workflow/config or a fetched primary web page;
**ESTIMATE** = arithmetic from measured inputs, no installer built in this round; **UNVERIFIED**
= no evidence available, do not treat as fact. `firecrawl` was used for the one external source
(Tauri v2 config reference); no CI run results were consumed, only workflow files and read-only
GitHub release metadata.

Out of scope by instruction: no full pytest, no downloads, no new dependencies, no git writes, no
touching other sessions' files. Terms of the removed legacy speech stack are deliberately not used
here; see ADR-0031 for that history.

---

## Plain English first

The app is currently **uninstallable in working order** for a normal user. The Windows installer
built by CI is the slim one: host + sidecar + native speech DLLs + ffmpeg, **no worker**. The
worker is published as a separate "runtime pack" zip. That pack has **never been published** — the
two manifest URLs 404 today — so a fresh install has no local speech engine and the worker reports
`The speech runtime is not installed. Reinstall the app or contact support.` (packaging audit
§"Plain English", `voice_typer/worker/asr_runner/runner.py:171`). VERIFIED; GitHub REST
`repos/AbdallahIsDev/Lausu/releases` on 2026-11-28 returns three releases, none with
`pack-manifest.json`, `pack-<n>.zip` or `lausu-runtime-pack-*.zip`.

Several other things a normal user needs have **no delivery path at all**: the translation runtime
(`llama-server`), a published extractor-freshness manifest, the full-offline installer, and TTS
runtime binaries in the installer. Translation and TTS models do have user-triggered, hash/size-
verified download paths; they are not bundled.

**Recommendation (decision-grade, evidence below):** ship **Option 4 — publish the current
worker-only pack — as the immediate fix**, and keep bulk (ffmpeg, speech DLLs, ONNX assets) in the
installer for now. Then move to **Option 2 only after** a clean end-to-end run proves the pack
pipeline, and give `llama-server` an explicit delivery path in the same change. Reasons:

1. It is the only option that fixes the one **verified** broken flow without changing the most
   fragile boundary in the app (two frozen Python processes, pack-protocol gate, WS auth,
   200 MB worker gate). VERIFIED from `worker.rs:175-215`, `runtime-pack-publish.yml:259-273`.
2. First-install bytes are smaller than Option 2: ~282 MiB ESTIMATE (163.66 MiB slim installer
   artifact + 117.82 MiB worker artifact) vs ~380-480 MiB ESTIMATE for a bulk pack that also
   carries ffmpeg + translation runtime + ONNX assets. No installer was built in this round.
3. Code-only updates stay at the current 163.66 MiB installer artifact (MEASURED CI metadata) and
   need **no** pack download while the worker version is unchanged.
4. Every hash, protocol and seed/verify gate this path needs already exists and is wired
   (`build_pack_manifest.py:96-127`, `download.py`, `install.py`, `checksum.py`, `worker.rs:185`).
   The other options require new gates or new UX before they are safe.

Not recommended now: folding the worker into one frozen exe (Option 1) — high risk, no measured
benefit; everything in the installer (Option 3) — ~400 MiB ESTIMATE first install and every code
change repays it; moving all bulk into a first-launch pack immediately (Option 2) — larger first
download than today, pack size exceeds its own 180 MB budget constant
(`voice_typer/server/service/offline_pack/core.py:36-39`).

---

## B4. Delivery inventory — what a normal user needs and how it reaches them today

| Component | Delivery path today | Size | Update frequency | Hash / signature verification | Offline behavior | User-visible state when missing | Evidence & label |
|---|---|---:|---|---|---|---|---|
| **ASR worker** (separate frozen Python process) | Runtime-pack zip **only**; never published. CI builds `windows-worker-exe`, zips one file as `lausu-runtime-pack-<n>-<triple>.zip` and aliases `pack-<n>.zip`. | 123,540,191 B / 117.82 MiB CI artifact zip (MEASURED); worker onefile gated ≤200 MB | Packs are manual `workflow_dispatch` (`runtime-pack-publish.yml:37-38,40-42`); code changes need a new pack version | Client verifies archive SHA-256 + per-file SHA/size (`build_pack_manifest.py:117-127`, `download.py:280-302`, `install.py:109-175`); Windows exe is Authenticode-signed when secrets set (`:279-296`); host re-checks pack manifest before spawn (`worker.rs:181-198`) | After one successful install, worker runs offline; no pack = no local ASR | `The speech runtime is not installed…` (worker); toast "Preparing offline engine…"; Settings card "Not downloaded" | `.github/workflows/runtime-pack-publish.yml:243-257,309-327,364-398`; `voice_typer/client/src/renderer/src/i18n/translations/en.json:2238-2259`; VERIFIED + MEASURED |
| **Speech DLLs + `contract.json`** (GGUF runner asset) | Slim installer resource `resources/transcribe-cpp`; CI fetch step stages 13 DLLs + contract from pinned upstream archive. **Not** in the pack. | 56,234,621 B / 53.63 MiB extracted (MEASURED local spike dir); archive 18,052,817 B (pinned) | Manual pin bump in `scripts/transcribe-cpp-win64.json` when upstream releases | Fetch script checks SHA-256 (`:16,37`); runtime checks contract `version` and `header_hash` against compiled constants (`contract.py:58-74`); no per-DLL runtime hash or signature check found — UNVERIFIED | Files are local once installed; no network | Worker load raises `The installed speech runtime is the wrong version.` / ABI mismatch; generic ASR failure notice, not a targeted "DLLs missing" copy | `scripts/transcribe-cpp-win64.json:5-31`; `voice_typer/worker/asr_runner/contract.py:58-74`; `tauri.windows-x86_64-slim.conf.json:52-57`; VERIFIED + MEASURED |
| **`llama-server`** (translation runtime) | **NO PATH.** Not in installer config, not in pack, no CI step stages it. Present on this machine only as manually placed app-data files; app-data dir is the last resolver fallback. | `%APPDATA%\lausu\translation` part of 124,984,387 B root; `ggml-vulkan.dll` 41.10 MiB (MEASURED); service docstring says ~39 MB (VERIFIED text) | None wired; manual file copy today | No version or hash pin found for the runtime (VERIFIED absence); the **model** SHA is pinned separately | Runtime cannot be fetched at runtime; translation silently degrades to original text | Error raised `translation runtime not installed; bundle …`, caught and shown as generic **"Translation failed. Your original transcription was kept…"** — no "download runtime" action | `voice_typer/server/translation/paths.py:8-11,92-127`; `service.py:150-158,374-383`; `en.json:2211`; `.github/workflows/*` grep: no match; VERIFIED |
| **ffmpeg** (media decode) | Slim installer `externalBin` (`bin/ffmpeg`); fetched from pinned mirror/upstream at build time. **Not** in the pack. | 134,459,904 B / 128.23 MiB (MEASURED `src-tauri/bin`); pinned archive 171,850,189 B | Manual pin bump in `scripts/ffmpeg-lgpl-win64.json` (`version`, tag, SHA, size, config) | Fetch script enforces SHA-256 + mirror equality + forbidden config tokens (`:65-77,153`); **no runtime hash check** (`ffmpeg_binaries.py` has no hash/verify); CI bundle gate checks names/GPL pattern | Local once installed; URL media needs network for the stream itself | No targeted missing-codec UI; media job fails as `The media could not be decoded…` (`en.json:84`) | `scripts/ffmpeg-lgpl-win64.json:5-29`; `scripts/build/fetch_ffmpeg_lgpl_win64.sh:65-77,153`; `tauri.windows-x86_64-slim.conf.json:48-51`; VERIFIED + MEASURED |
| **ONNX noise/VAD models + ONNX Runtime** (real-time path) | Frozen into **both** onefiles via package data / `--include-package=onnxruntime`; not in installer resources or pack. | `dpdfnet2.onnx` 10,178,747 B, `silero_vad.onnx` 2,327,524 B, `gtcrn_simple.onnx` 535,190 B (MEASURED ADR inventory); stale extraction ORT pyd 17.88 MiB + ORT dll 17.26 MiB (MEASURED, stale) | Python dependency bumps / freeze flags; no user-facing updater | Package-data inclusion (`build_sidecar_windows.sh:164`, `build_worker_windows.sh:241-244`); no per-file hash check found — UNVERIFIED for current frozen payload | Fully local after install | `vad_processor.py:191` warns "unavailable (onnxruntime missing or bundled …)"; default denoiser availability is probed, not downloaded | `voice_typer/server/{vad.py,audio_filters/dpdfnet_backend.py,gtcrn_backend.py}` imports; ADR-0031 Phase-1 decision (ORT stays); VERIFIED + MEASURED |
| **yt-dlp + EJS solver** (media URL extractor) | Frozen into the sidecar via `--include-package-data=yt_dlp`; freshness check reads `media-extractor.json` from a GitHub Release URL. **That manifest is not published**; the check is check-only, and no IPC command installs extractor updates. | Python package bytes inside onefile: UNVERIFIED current split | Advisory check on launch (`startup_launch_checks.py:142-169`); user-initiated install path documented but not wired in `_COMMAND_REGISTRY` | Check compares versions against remote JSON (`mini_update.py:130-185`); no hash/signature of extractor updates in this flow | yt-dlp itself works offline for already-downloaded media; sites need network | 404 is a DEBUG line only (`mini_update.py:159-163`); no UI notice — UNVERIFIED user-visible | `mini_update.py:19-20,153-191`; `startup_launch_checks.py:142-149`; `voice_typer/server/ipc/registry.py:113-249`; VERIFIED |
| **TTS runtimes** (`audiocpp_server`, `nemo-speech`) | **NO installer path.** `tts_prepare` resolves the newest matching GitHub release by asset pattern, downloads (byte-count check only), unpacks into `<HF root>/tts/bin/<engine>`. | Publisher asset sizes vary; UNVERIFIED on a clean profile | Latest-release lookup at prepare time, not pinned (`tts/runtimes.py:26,39-54,69-84`) | Size check only (`:87-109`); no hash/signature check for the runtime archive (VERIFIED absence) | Needs network on prepare; after that local | `tts_status.engines[*].available` is a filesystem probe (`manager.py:137-186`); renderer label `{name} (unavailable)` (`en.json:1013`); prepare error is a row error, no cross-page toast found — UNVERIFIED | `voice_typer/server/tts/runtimes.py:1-9,39-54,87-109`; `tts/paths.py:43-75`; `tts/manager.py:114-133`; VERIFIED |
| **TTS GGUF packs** (Audio8, Magpie+codec) | User-triggered `tts_prepare` into `<HF root>/tts/models/<engine>`; never bundled. | Pinned sizes: Audio8 1,890,480,128 B; Magpie 568,663,328 B; codec 78,823,104 B (PINNED constants, not re-measured) | On demand via Models page | Exact pinned size + `GGUF` magic + plausibility floor (`tts/packs.py:29-64`); Magpie's own `pull` also checks size + publisher SHA (`manager.py:245-268`) | Local after download | `tts_prepare_progress` events; Models row progress; failure surfaces on that row — no global toast found (UNVERIFIED) | `voice_typer/server/tts/packs.py:105-140`; `tts/manager.py:228-269`; VERIFIED |
| **ASR GGUF weights** (Parakeet, Whisper family, Qwen3-ASR) | User-triggered `download_model` into shared HF cache, consent-gated; never bundled. | Parakeet 740,363,168 B; Whisper turbo 886,381,728 B; Qwen 1.7B 1,319,830,496 B; Qwen 0.6B 850,423,456 B (registry sizes, Parakeet MEASURED) | On demand; registry pins repo + file + SHA + size | `huggingface_consent` gate, SHA-256 + size before accept (`gguf_download.py:100-139`); registry rejects placeholder hash/size (`gguf_model_registry.py:349-356`) | After download, `local_files_only=True` at inference — fully offline | Models page `notDownloaded` / `downloadFailed` (`en.json:1412-1417`); no-model notice (`en.json:2138`); tray `modelIntegrityFailed` (`en.json:2350`) | `voice_typer/server/gguf_model_registry.py:43-101,296,349-356`; `gguf_download.py:100-139`; VERIFIED + MEASURED |
| **Translator GGUF** | User-triggered settings download into shared HF cache; never bundled. | 1,312,164,352 B (MEASURED) | On demand | Catalogue pins filename, size and SHA (`translation/catalogue.py:17-25`); download verifies size + SHA (`translation/download.py:103-133`) | Local after download; runtime still missing (see above) | `translationDownload` / `translationDownloadFailed` / `translationDownloaded` (`en.json:823-830`); missing notice (`en.json:2212`) | `translation/catalogue.py:62-72`; `translation/download.py:75-136`; VERIFIED + MEASURED |
| **Native hotkey listener** | Installer resource, compiled in CI; not in pack. | Small binary; exact size UNVERIFIED this round | Build-time compile | SHA-256 + version + protocol pin in `native/binaries.json:15-19,40-49`; runtime verifies with fail-closed fallback (`_comment` line 2) | Local once installed | No dedicated UI; falls back to the non-native input backend on mismatch | `native/binaries.json:1-51`; `tauri.windows-x86_64-slim.conf.json:55`; VERIFIED |
| **Full-offline installer** (slim + pack, writes `pack_bundled`) | Scripts exist; **no workflow calls them**. | Not shipped this round | n/a | n/a | Intended to be fully offline | No user-visible state | `scripts/build/build_full_offline_installer_windows.sh`, `scripts/windows/full-offline-installer.nsi`; grep of `.github/workflows/`: no caller; VERIFIED |

### Critical findings from the inventory

1. **The published pack is worker-only** (`runtime-pack-publish.yml:309-327`): one `zipfile.write`
   of the worker exe. A reviewer hypothesis that "the pack already carries ffmpeg / speech DLLs /
   GGUFs" is **false**. Consequence: even after publishing, the pack cannot run ASR unless the
   installer's native bundle is present — which it is in the slim installer. VERIFIED.
2. **`offline-pack` tag is 404 and releases hold no pack assets** (read-only `gh api`, 2026-11-28).
   `releases/latest` resolves to `v1.1.0` with only a setup exe. The workflow is dispatch-only and
   defaults to `draft: true` (`runtime-pack-publish.yml:58-62`), so a validation run is invisible to
   the downloader until published. VERIFIED.
3. **The signature claim is not wired.** Renderer types say `offline_pack_verified` means SHA256 +
   Authenticode/notarization (`types/ipc/push_events.ts:461-462`), but the only signature helper is
   `offline_pack/core.py:304-333` with no production caller (grep across `voice_typer/`). The
   downloader verifies **hash only**. VERIFIED. Either wire it or correct the doc; do not claim
   signature verification to users.
4. **No runtime delivery for translation.** `translation/paths.py:8-11` calls llama-server
   "installer-bundled", but no Tauri config or workflow bundles it. VERIFIED contradiction.
5. **Never run end to end** (all UNVERIFIED, do not report as working):
   - real manifest → archive download → per-file verify → atomic swap → worker spawn;
   - hardware hotkey → bubble → **local** ASR → paste (OS key injection barred here, plugin profile
     active, no local runtime in the app bundle — `performance-measurements.md` §A2/UNVERIFIED);
   - translation runtime install on a clean profile; TTS runtime+pack prepare on a clean profile;
   - frozen bundle with the GPL-DLL gate enforced (ADR-0031 last step still pending a real build).

---

## B5. First-launch UX today

| Situation | Backend behavior (file:line) | What the user actually sees | Effect on dictation / translation | Gaps |
|---|---|---|---|---|
| **Fresh install, pack missing** | Launch scan finds no version dir → publishes `offline_pack_missing`, then fires the remote check (`startup_launch_checks.py:22-39,70-83`); dictation's worker gate returns `("offline_pack_missing")` (`worker_path.py:42`) | App-level non-persistent toast `pack.updateTitle` + `pack.preparingOfflineEngine` (`usePackUpdateToast.ts:127-138`); Settings card `packStateMissing` = "Not downloaded" with **Download offline engine** (`OfflinePackSection.tsx:174-221`); tray/notice `notify.model_manager.offline_pack_missing` (`en.json:2139`) | Local dictation refused before the mic opens when no model/pack (`model-lifecycle.md` provider-ownership section); translation still runs if its own assets exist | The toast says "Preparing…" even when **no download is possible** (404/offline). VERIFIED text drift. |
| **Manifest 404 (today's normal state)** | Both default candidates return 404 → `success=True, reason="no_remote_manifest"`, one INFO line `no pack manifest published yet, nothing to download` (`update_check.py:243-254`; URLs at `update_check_urls.py:14-34`) | **No error toast**; About check outcome would report `about.updateOutcome.upToDate` ("Up to date…") because `success` is true (`AboutAndPrivacy.tsx:121-128`) | No pack; local dictation unavailable | This is a **benign pre-publish state by design**, not a bug — reject "404 is broken UI" hypotheses. But "Up to date" is misleading when nothing is installed. VERIFIED. |
| **Offline / network failure (not 404)** | Fetch returns `fetch_failed` (`update_check.py:255-264`); pack download failure publishes `offline_pack_download_failed` | About outcome `about.updateOutcome.failed` = "Check failed. Verify your internet connection and try again." (`en.json:590`); pack toast `pack.updateFailed` = "Voice update failed" (`usePackUpdateToast.ts:104-110`); Settings `packStateFailed` + **Retry download** | No pack → no local dictation; already-installed pack keeps working | Error detail is stored in the hook but **not shown in the toast** (`useOfflinePackDownload.ts:213-223` vs `usePackUpdateToast.ts:104-110`). VERIFIED. |
| **Download in progress** | `offline_pack_download_progress` events (`download.py:219-250`) | Sticky toast `pack.updateTitle` + `pack.downloadingOfflineEngine` with live percent (`usePackUpdateToast.ts:44-78`); Settings card percent (`OfflinePackSection.tsx:181-188`) | Local dictation still unavailable until ready | Header comment in `useOfflinePackDownload.ts:1-11` still says "silent-mode / no progress bar in main UI" — stale text (packaging audit finding 9). VERIFIED. |
| **Download completed / verifying** | `offline_pack_download_completed` → checksum pass → `offline_pack_verified` (`checksum.py:48-70`, `install.py:171`) | Sticky toast `pack.updateVerifying` then silent on `offline_pack_verified` (`usePackUpdateToast.ts:80-91,140-145`) | Worker not yet usable; short window | `offline_pack_verified` is deliberately silent even though it is a real integrity event. Product choice; VERIFIED. |
| **Runtime missing (worker/native DLLs)** | Worker load raises a hard error (`runner.py:171`); contract mismatch raises `The installed speech runtime is the wrong version.` (`contract.py:68-74`); host refuses spawn on bad pack manifest (`worker.rs:181-198`) | Generic ASR failure notice `notify.model_manager.load_failed` / `backend_init_failed` (`en.json:2128-2141`); pack card state may still read "Ready" if only DLLs are missing | Local dictation fails; translation unaffected | No dedicated "speech DLLs missing" copy, no link to a repair action for the native bundle. VERIFIED absence. |
| **Runtime missing (translation)** | `resolve_runtime_path` raises `TranslationError` (`service.py:150-158`), caught at `:374-383` → generic `notify.dictation_pipeline.translation_failed` | "Translation failed. Your original transcription was kept…; check the log file for details." (`en.json:2211`) | Original text kept; dictation text still delivered | The notice **does not tell the user the runtime is missing or how to install it**; no runtime-download action exists. VERIFIED gap. |
| **ASR model missing** | Shared no-engine refusal before mic open (`model-lifecycle.md` Round 7 fix); provider-ownership notice (`model-lifecycle.md` Round 8) | Toast/notice `notify.model_manager.no_model_selected` / `model_not_downloaded` (`en.json:2138,2140`); Models row `notDownloaded` (`en.json:1412`); tray `modelNotDownloaded` (`en.json:2348`) | Mic is not opened; no wasted recording | Correct behavior; VERIFIED in source and prior live runs. |
| **Hash mismatch — pack** | `verify_offline_pack_or_skip` fails → `offline_pack_corrupt` (`checksum.py:48-70`; install path `install.py:135-165`) | Toast `pack.updateFailed` ("Voice update failed", no cause); Settings `packStateCorrupt` = "Pack corrupt" + **Repair pack** (`en.json:2255,2259`) | Pack unusable until repair; dictation blocked | Cause (which file, expected vs actual hash) is log-only. VERIFIED. |
| **Hash mismatch — ASR / translation / TTS GGUF** | Downloaders return `sha256_mismatch` / `size_mismatch` (`gguf_download.py:130-139`, `translation/download.py:130-133`, `tts/packs.py:39-51`) | Generic `models.downloadFailed` / `translationDownloadFailed` (`en.json:1415-1417,824`); tray `modelIntegrityFailed` tells user to delete and re-download (`en.json:2350`) | That model unavailable; other providers still work | No "keep partial / retry verified" UI; consistent with security contract. VERIFIED. |
| **Stale/outdated pack** | Host refuses old `min_proto_version`, emits `offline_pack_outdated` (`read_loop.py:103-109`, `outdated.py:13`) | Persistent warning toast `pack.updateTitle` + `pack.outdatedDescription`; Settings `packStateOutdated` = "Update available" (`usePackUpdateToast.ts:117-125`; `en.json:2252,2264`) | Local dictation blocked until fresh pack | New download replaces the warning. VERIFIED. |

All 8 locales have the pack/model keys cited above (e.g. `zh.json:2139,2245-2259,2349`,
`ar.json` siblings). No new user-facing strings are needed for Option 4; a new runtime-download
notice **would** require all 8 locales (C-I18N-1). VERIFIED.

---

## B6. Options table

Size inputs (all from measured/public metadata; **no installer built in this round**):

| Input | Value | Label / source |
|---|---:|---|
| Slim NSIS installer (CI artifact zip, run 45024128135) | 171,607,767 B / 163.66 MiB | MEASURED artifact metadata, `packaging-and-runtime-pack.md:58-64` |
| Slim MSI installer (CI artifact zip) | 185,345,958 B / 176.76 MiB | MEASURED artifact metadata, same |
| Worker artifact zip | 123,540,191 B / 117.82 MiB | MEASURED artifact metadata, same |
| ffmpeg.exe | 134,459,904 B / 128.23 MiB | MEASURED `src-tauri/bin` |
| Native speech bundle extracted | 56,234,621 B / 53.63 MiB | MEASURED local spike dir (13 DLLs + contract) |
| Translation app-data dir | part of 124,984,387 B root; `ggml-vulkan.dll` 41.10 MiB | MEASURED, ADR-0031 inventory + packaging audit |
| Current-code installer size | **UNVERIFIED** (CI sizes predate Phase 1) | performance-measurements.md:461-466 |

| Option | First-install size | Typical code-only update | Offline behavior | Moving parts | Test effort | Risk | Verdict |
|---|---|---|---|---|---|---|---|
| **1. Single frozen exe with worker mode, no worker pack** | ~160-170 MiB ESTIMATE, if the worker really folds into the existing sidecar onefile (no second frozen runtime) | Same ~160-170 MiB ESTIMATE | Best: one local install covers code; native DLLs still resources; no pack download | New in-process worker mode in the frozen sidecar; must replace host `WorkerLaunchTarget::{PackExe,Bundled,Absent}` (`worker.rs:175-215`), keep separate WS/auth, parent-watch, 200 MB gate; no CLI flag exists today (`worker/__main__.py:189-228`) | High: new process topology + frozen-build parity + all local-ASR paths | **High** — touches the most fragile boundary; no measurement showing a user-felt gain | **No now.** Revisit only with a measured installer/startup win and a dedicated spike. |
| **2. First-launch pack for bulk (ffmpeg, llama-server, speech DLLs, ONNX/ORT), hash-verified, code-only installer** | ~180 MiB installer + ~200-300 MiB pack = **~380-480 MiB ESTIMATE** | ~180 MiB installer ESTIMATE; pack unchanged if its hash/version stays | Code works offline; ASR blocked until pack lands; media/translation blocked until their pack assets exist (same as today) | Move worker into installer (full-config path already exists: `tauri.windows-x86_64.conf.json:50`), add 4 asset classes to pack zip, bump pack budget constants (`core.py:36-39`: 180/450 MB), new pack-level gate, new "which feature needs the pack" copy in 8 locales | High: new pack contents, gate, UX, llama-server path, plus the full fresh-profile matrix | Medium-high: pack exceeds its own size budget; translation runtime has no pin today | **Later.** Target only after Option 4 runs clean end to end and bulk-update frequency is known. |
| **3. Everything in installer** | ~163.66 + 117.82 + ~125 MiB ≈ **~400 MiB ESTIMATE** | Same ~400 MiB ESTIMATE (every code change pays for all bulk) | Best offline story, one download, no pack at all | Add worker + translation runtime to resources/externalBin; keep plugin/ORT defaults; MSI grows too | Medium: config + workflow + gate changes, no new downloader | Medium: install size and antivirus/SmartScreen surface; signing more binaries | **No.** No offline advantage over a completed Option 4, and every update repays the bytes. |
| **4. Keep current worker-only pack and publish it** | ~163.66 + 117.82 ≈ **~282 MiB ESTIMATE** | **163.66 MiB installer** (MEASURED artifact); 0 pack bytes while worker unchanged | After pack install, full local dictation offline; before it, no local ASR (today's state) | Zero code change: dispatch `runtime-pack-publish` with `draft=false`, publish `offline-pack` tag, keep `pack_bundled` installer as optional | Low-medium: one clean-profile end-to-end + update-N→N+1 check; no new gates | **Low** — reuses every existing hash/protocol gate | **RECOMMENDED NOW.** Unblocks the one verified broken flow. |
| **5. Discovered alternative: tiered packs (baseline worker+native+ORT; ffmpeg and llama-server on demand)** | ~163.66 + ~90-120 MiB baseline pack ESTIMATE; feature packs only on first media/translation use | 163.66 MiB installer ESTIMATE; baseline pack unchanged if worker unchanged | Local dictation after the smaller baseline pack; media/translation need extra downloads, with explicit notices | New manifest/URL per tier, consent/URL allowlist entries, feature-triggered download IPC and 8-locale copy; llama-server still needs a pin | High: new IPC surface + 3 download paths + tests | Medium-high: more states for users to get stuck in | **Later**, only if Option 4's first-install size becomes a product blocker. |

### Sub-decisions checked

| Sub-decision | Evidence | Verdict |
|---|---|---|
| **Audio-only ffmpeg** (45-75 MiB installer ESTIMATE vs 128.23 MiB MEASURED today) | Manifest config enables nearly every LGPL codec/filter (`ffmpeg-lgpl-win64.json:13`); app only needs audio demux/decode + aresample + f32le + five protocols (`ADR-0031:245-257`); upstream declined an audio-only flavor (issue #5), so the owner's acceptable path is a pinned-source CI recipe with `--disable-everything`; size **ESTIMATE 10-30 MB static**, no build made (`ADR-0031:259-280`) | **Later, separate decision.** Do not block Option 4 on it; owner maintains a pinned commit + configure line, not a fork. |
| **Retired media libraries removal** | Phase 1 deletes them from deps/freeze (`ADR-0031:113-124`); stale frozen extraction measured 64.91 MiB, installer saving ~25-35 MiB ESTIMATE using the 0.45-0.59 payload→installer ratio (`performance-measurements.md:437-457`) | **Already in source; verify saving on the next real build.** Not a reason to redesign delivery. |
| **NSIS/MSI compression knobs** | Tauri v2 `NsisCompression` allows `zlib`/`bzip2`/`lzma`/`none`, **default `lzma`** (`https://v2.tauri.app/reference/config/#nsiscompression`, Firecrawl 2026-11-28); `WixConfig` object has no compression property (`#wixconfig`) | **Not worth it.** ~0 MB expected; MSI has no config lever. |
| **Bundled-worker installer path** | Full config already lists `bin/lausu-worker` (`tauri.windows-x86_64.conf.json:48-52`); host already implements `WorkerLaunchTarget::Bundled` (`worker.rs:200-212`); CI deliberately builds the slim overlay (`tauri-windows-build.yml:594,923-951`, packaging audit) | Use only if Option 2 is chosen; it still ships **two** exes, not Option 1's single exe. |

---

## Recommended design — Option 4 now, Option 2 as a gated follow-up

### Migration order

1. **Unblock publishing (owner action).** Dispatch `runtime-pack-publish` with a real integer pack
   version, `draft=false`, `sign=true`; wait for the release; re-dispatch/publish the rolling
   `offline-pack` tag so `releases/latest/download/pack-manifest.json` also resolves
   (`runtime-pack-publish.yml:29-33,364-418`). Reject hypotheses that a draft release is enough —
   the comment at `:29-31` says explicitly it is invisible to `/releases/latest`.
2. **Publish contract.** Exactly three asset names must exist on both the versioned tag and the
   rolling tag: `pack-manifest.json`, `pack-<n>.zip`, and the canonical
   `lausu-runtime-pack-<n>-<triple>.zip` (`:16-27,388-418`). Manifest top-level `sha256` is the
   **archive** hash; `files[]` are post-extract per-file hashes/sizes
   (`build_pack_manifest.py:5-11,117-127`). No hash is invented; the builder computes from bytes.
3. **Verify on a clean profile** with the end-to-end plan below. Do not call delivery "fixed"
   until the real asset has been fetched and the worker has started.
4. **Separate decision: translation runtime.** Either add `llama-server.exe` (plus the ggml DLLs it
   needs) to installer resources with a version/SHA pin, or add an explicit download-and-verify
   IPC path. Until one exists, mark translation runtime delivery **UNVERIFIED / no path** in
   release notes. Do not silently let the app claim it is "installer-bundled"
   (`translation/paths.py:8-11` vs `service.py:150-158`).
5. **Only after step 3 passes**, evaluate Option 2 with measurements: count how often ffmpeg,
   speech DLLs, ORT/ONNX and llama-server pins actually change; build one installer with and one
   without bulk; measure real bytes and cold-start cost. If the bulk pack exceeds 180 MB
   compressed, bump the budget deliberately and re-test the disk gate. If not, keep Option 4.

### What must be published, and where

| Artifact | Where | Who produces it | Verified by |
|---|---|---|---|
| `pack-manifest.json` | GitHub Release `offline-pack` (rolling) **and** versioned tag | `build_pack_manifest.py` in `runtime-pack-publish.yml:364-379` | Client schema validator `core.py:159-227`; archive SHA at download; per-file SHA at install |
| `pack-<n>.zip` | Same releases, byte-identical alias of primary triple zip | `runtime-pack-publish.yml:377-379` | Archive SHA vs manifest; URL derived in `update_check.py:118-125` |
| `lausu-runtime-pack-<n>-<triple>.zip` | Same releases (canonical, additive name) | `runtime-pack-publish.yml:309-327` | Artifact naming gate; per-triple selection is intentionally not implemented (`:26-27`) |
| Signed worker exe | Inside each pack zip; signed at build when secrets exist | `runtime-pack-publish.yml:279-296` | Signing is build-time; **client does not verify signature** (finding 3) |
| `media-extractor.json` (optional) | `releases/latest/download/…` | No workflow publishes it today — owner decision | Check-only consumer (`mini_update.py:188-191`) |
| ffmpeg pinned archive + mirror | Already published under `ffmpeg-lgpl-n9.0.2-20261120` prerelease (read-only `gh api`, 2026-11-28) | `fetch_ffmpeg_lgpl_win64.sh` | Manifest SHA + mirror equality |
| llama-server runtime pin | **Nothing published today** | Owner must choose installer pin or download path | None until implemented |

---

## End-to-end test plan — fresh-user install (all steps UNVERIFIED until executed)

Environment: clean Windows profile or VM with **no** `%APPDATA%\lausu`, `%LOCALAPPDATA%\lausu`,
HF cache, `VT_PACK_ROOT`, `VT_PACK_MANIFEST_URL` or `LAUSU_*` overrides. Real key injection must be
driven by a human tester (C-HOOK-1); an agent must not synthesize hotkeys.

| # | Step | Pass evidence |
|---|---|---|
| 0 | From current HEAD, build the NSIS installer with `tauri-windows-build`; record artifact name, byte size, gate output, and signing result. Run `cargo check`, `npm run typecheck:ci`, `pytest --collect-only`, scoped tests for touched files. | Build log + artifact metadata; 0 gate failures. No full-suite result claimed by this worker. |
| 1 | Before publishing a pack: install on clean profile, launch, confirm startup completes and the manifest-404 path logs exactly `no pack manifest published yet, nothing to download`. Capture timestamped `lausu.log` and screenshots. | 404 is benign; no error toast; local dictation unavailable with an actionable no-pack/no-model notice. |
| 2 | Publish the pack per migration steps 1-2. Read-only `gh api` asserts manifest + `pack-<n>.zip` on both tags and captures their SHAs. | Release metadata; computed SHA equals manifest top-level SHA. |
| 3 | Fresh profile again → install → launch. Observe `offline_pack_missing`, the toast "Preparing offline engine…", Settings card "Not downloaded" / "Download offline engine", download progress percent, `offline_pack_download_completed`, `offline_pack_verified`, `worker_started`, `offline_pack_ready` in timestamped logs and UI. | Full state chain; Settings card ends "Ready"; worker.log shows authenticated `worker_started`. |
| 4 | Corrupt case: delete/rename one installed pack file, relaunch; expect `offline_pack_corrupt`, Settings "Pack corrupt" + **Repair pack**, and repair re-download restores a verified pack. | Manifest per-file hash failure proven in log; repair ends "Ready". |
| 5 | Manifest/zip hash mismatch: serve a deliberately wrong `VT_PACK_MANIFEST_URL` in a **scratch** profile; expect download abort, `offline_pack_corrupt` / `download_failed`, no installed version bump. | No unverified files installed. |
| 6 | Offline with **pack installed**: enable airplane mode, press the real hotkey, speak, stop, confirm transcript pastes into Notepad. | Log timestamps for hotkey → bubble → record → transcribe → paste; text in Notepad. Anything missing is UNVERIFIED, not a pass. |
| 7 | Offline with **pack missing**: clean profile, airplane mode, attempt dictation; expect refusal with no mic open and an actionable notice; no infinite "Preparing…" spinner. | Mic never opened; notice shown. |
| 8 | Model consent flow: with internet, select and download the Parakeet GGUF from Models; assert SHA/size verified, then repeat step 6. | HF cache hash matches registry; local decode works with `local_files_only=True`. |
| 9 | Translation: make llama-server available by the path chosen in migration step 4; download translator GGUF; press hotkey; assert translator ready **before** stop (prior measured cold 12-15 s, warm 2-3 s — `performance-measurements.md:362-435`), translated text pasted. Then remove only the runtime and assert the "Translation failed… original kept" notice with no raw path in UI. | Both paths proven; log context retained. |
| 10 | Media: transcribe a local audio file and a URL with the shipped ffmpeg; then temporarily hide ffmpeg and assert the user-facing decode error, not a stack trace. | Decode log with sample count; error copy matches `en.json:84`. |
| 11 | Update N→N+1, **code-only**: make a harmless code/version change, build new installer, install over the clean profile **without changing pack version**. Assert pack version and files unchanged, no pack download, model cache untouched, and record the new installer byte size. | `get_status.offline_pack.installed_version` unchanged; no `offline_pack_download_*` events; measured size delta. |
| 12 | Update with a **worker change**: bump pack version, publish, update app; assert pack download triggered, old version replaced atomically, dictation still works. | New version "Ready"; old pack dir retired as designed. |
| 13 | Regression gates in the shipped artifact: notices/source offer present, branding constant used, i18n completeness across all 8 locales, IPC allowlist parity, GPL-DLL gate result. | Logs/artifacts; owner decides when to flip the enforcement default after a real frozen build (ADR-0031 last step). |

### What the owner must do by hand

1. **Choose** Option 4 now vs a different target; this document recommends Option 4 and defers
   Option 2/5 pending measurements. No agent should pick a new delivery topology by itself.
2. **Dispatch and publish** `runtime-pack-publish` with `draft=false` and signing enabled; publish
   the rolling `offline-pack` tag. Provide the pack version number and confirm the exact asset set.
3. **Provide a clean Windows VM or profile** and a human tester for real hotkey/paste steps; agents
   cannot inject OS keys (C-HOOK-1) and the current profile has a browser plugin owning dictation.
4. **Decide llama-server delivery** (installer pin vs explicit download path) and TTS runtime
   delivery; neither has a shipping path today. Approve any new notice copy in all 8 locales.
5. **Decide the ffmpeg path** (keep pinned upstream build vs fund a pinned-source audio-only recipe)
   and whether to spend a real build on measuring retired-library savings.
6. **Approve any large download** (>1 GB, including a VM image or new model/runtime pack) and any
   disk cleanup; no agent may delete existing user artifacts to make room (C-AGENT-7/8).
7. **Run or delegate the full pytest suite** on the final state (orchestrator only), and record
   validation evidence in `worklog.md`. This read-only worker ran no suites and made no commits.

---

## Hypotheses checked and rejected (with evidence)

| Hypothesis | Verdict | Evidence |
|---|---|---|
| "The published pack already contains ffmpeg / speech DLLs / GGUFs." | **False** | Pack job writes exactly one file into the zip: `runtime-pack-publish.yml:309-327`. |
| "Manifest 404 is a user-visible bug." | **False** | Benign pre-publish branch returns success and logs one INFO line: `update_check.py:243-254`. The misleading part is About's "Up to date" copy, not the fetch logic. |
| "`offline_pack_verified` proves Authenticode/notarization." | **False** | Only SHA is verified; signature helper has no caller (`core.py:304-333`, `types/ipc/push_events.ts:461-462`). |
| "llama-server is installer-bundled." | **False** | No workflow/Tauri config stages it; app-data is a last-resort fallback (`translation/paths.py:8-11,92-127`). |
| "A published pack alone fixes everything." | **False** | It fixes local ASR, not translation runtime, extractor manifest, TTS runtime, or media ffmpeg-update frequency. |
| "NSIS compression tuning will materially shrink the installer." | **False** | LZMA is already the Tauri default; alternatives are zlib/bzip2/none; MSI/WiX has no compression key (Firecrawl scrape of `v2.tauri.app/reference/config`, 2026-11-28). |
| "The 128 MiB ffmpeg is already audio-only." | **False** | Pinned config enables nearly all LGPL codecs/filters (`ffmpeg-lgpl-win64.json:13`); upstream has no audio-only flavor; a pinned-source recipe is a future owner decision (ADR-0031:259-280). |
| "Retired media libraries still account for 64.91 MiB of the current installer." | **False / stale** | That number came from an old onefile extraction; Phase 1 removed them from source (`ADR-0031:113-124`, `performance-measurements.md:437-466`). Current-code size is UNVERIFIED. |

## UNVERIFIED list (do not promote to fact)

- Real pack download/verify/install/worker-start against a published GitHub asset; today's normal
  state is 404 and the only live proof used scratch pack roots and synthetic manifests.
- Actual size of a current-code installer; all CI sizes predate Phase 1.
- Whether the current frozen payload contains a runtime hash check for ffmpeg / speech DLLs /
  ONNX assets (none found in source; a frozen build would settle it).
- Extractor-update installation: the freshness check exists, but no IPC command or published
  `media-extractor.json` was found.
- TTS runtime/model prepare and translation runtime install on a genuinely clean profile.
- Hardware hotkey → bubble → paste end to end for local ASR (plugin-owned profile, no OS key
  injection allowed here).
- MSI/NSIS on-disk size after any of the options; all option totals are ESTIMATE from artifact
  metadata and raw file sizes, not from a build made in this round.

---

## C. llama-server delivery — provenance, inventory and design options (Worker S4)

Read-only, 2026-11-28; no download, build, workflow edit or installer was made. Labels as above.
This section answers the one asset class the parent brief left undecided: the text-translation
runtime. Related measured numbers live in `docs/design/installer-size-audit.md`.

### C1. How a normal user gets it today: nothing

A clean install gets **no `llama-server` at all**. It is absent from both Tauri configurations
(`tauri.windows-x86_64-slim.conf.json:48-57` lists only the sidecar + ffmpeg, plus resources),
absent from the worker-only runtime pack (`runtime-pack-publish.yml:309-327` writes one file), and
no workflow or script stages it (grep of `.github/workflows/` and `scripts/`; **VERIFIED**). The
resolver searches shipped dirs, then the writable `%APPDATA%\lausu\translation` as a **last
fallback** (`translation/paths.py:92-127`), so the docstring's "installer-bundled" claim
(`:8-11`) is false — the contradiction is already recorded at `runtime-delivery-options.md:90`.

When missing, `resolve_runtime_path()` raises `TranslationError`
(`translation/service.py:150-158`), caught at `:374-383` and shown as the generic
"Translation failed. Your original transcription was kept…" notice (`en.json:2211`). The user is
not told the runtime is missing and gets no install/repair action. **VERIFIED**.

### C2. How this machine got it

The app-data directory was populated by hand on 2026-11-22 21:44–21:53 (file mtimes, **MEASURED**).
The installed process reports `build_info: b12521-6f311d7ad` through its live `/props` endpoint
(`C:\Users\11\AppData\Local\Temp\opencode\r4-s2-token-evidence.txt:6`; also
`tests/translation/test_translation_group_chunking.py:124` and `translation/chunking.py:26`),
so the binary identity is **VERIFIED**. GitHub release metadata for tag `b12521` (read-only
`gh api`, 2026-11-28) shows the matching upstream asset
`llama-b12521-bin-win-vulkan-x64.zip`, 38,757,221 B, SHA-256
`d2498cfdd7973e0c14e832dbd1db7f5d8f409ebb08df27abfc5c54dfc3161c6a`, published
2026-11-18. **VERIFIED** metadata; the exact command/zip used to place the files is
**UNVERIFIED** — no install script exists in the repo (`git log -S 'llama-b12521'` finds only
docs that cite the build), the PowerShell history contains no such download, and the separate
`C:\Users\11\gguf-spike\releases\llama-vulkan.zip` (38,932,073 B) is a *different* build whose
`ggml-vulkan.dll` is 44,867,072 B versus 43,092,480 B installed. Do not present the spike zip as
the source of the installed runtime.

### C3. Exact installed inventory and what is actually needed

`%APPDATA%\lausu\translation`: **54 files, 108,776,009 B / 103.74 MiB MEASURED** (plus the
app-written `index_translate_chat_template.jinja` 7,755 B and `llama-server.log`). Groups:

| Group | Files | Bytes | MiB | Needed? |
|---|---:|---:|---:|---|
| `ggml-vulkan.dll` | 1 | 43,092,480 | 41.10 | **Yes** when GPU mode on (`-ngl 99 -fa on`, `service.py:228-229`) |
| `ggml-cpu-*.dll` (14 variants) | 14 | 20,944,384 | 19.97 | **One** for CPU mode (`-ngl 0`); variant chosen by CPUID. Keep one, not all 14 |
| `llama-*-impl.dll` (8) | 8 | 14,877,184 | 14.19 | `llama-server-impl.dll` 10,482,176 B **yes**; the other seven are tools/benchmarks — no |
| llama core (`llama.dll` 3,942,912; `llama-common.dll` 8,616,960; `llama.exe` 105,984; `ggml.dll` 78,848) | 4 | 12,668,414 | 12.08 | `llama.dll`, `llama-common.dll`, `ggml.dll` yes; `llama.exe` no |
| `llama-*.exe` CLI tools (20) | 20 | 12,291,584 | 11.72 | No — includes `llama-connect.exe` 11,473,920 B, `llama-tts.exe`, quantize/bench/imatrix/rpc tools |
| `mtmd.dll` | 1 | 2,863,104 | 2.73 | Multimodal support; text-only translation probably does not need it, but the runtime's load-time dependency is **UNVERIFIED** (no PE import table was readable with the local tooling) |
| `ggml-base.dll` + `libomp.dll` | 2 | 1,600,512 | 1.53 | Yes (base runtime + OpenMP) |
| `ggml-rpc.dll` | 1 | 234,496 | 0.22 | No |

Minimal translation set: **~67.8 MiB** with Vulkan, **~25.2 MiB** with one CPU backend, plus an
uncertain 2.73 MiB for `mtmd.dll` — **ESTIMATE** from the measured file sizes and the resolver's
argv. TTS does **not** use this runtime: `tts/runtime_server.py:43-51` starts `audiocpp_server` /
`nemo-speech` from its own GitHub release assets; the bundled `llama-tts.exe` is llama.cpp's own
example and is unused. "Future polish" is the local ONNX LLM provider
(`model_providers/local_onnx/client.py:117-123`), which could move to a GGUF model served by this
same `llama-server` — that is a code/model change, not a packaging detail (**VERIFIED** from the
call sites; model availability **UNVERIFIED**, `partA-inventory.md:32`).

### C4. Three delivery options, compared

| | **(a) Hash-pinned first-launch pack, CI-built from upstream release** | **(b) User-triggered consent-gated download row** | **(c) Inside the installer** |
|---|---|---|---|
| What ships | Worker pack zip gains an allowlisted `llama-server/` subtree, built in CI from the pinned upstream zip; per-file SHA-256 in `pack-manifest.json` | New IPC command downloads the pinned zip on button press, verifies SHA/size, unpacks into `<config>/translation` | `externalBin`/resources entries + CI fetch, mirroring ffmpeg |
| First-install bytes | 163.66 MiB installer (unchanged) + worker pack 117.82 MiB + ~25–35 MiB llama compressed → **~305–320 MiB ESTIMATE** | 163.66 MiB installer + 117.82 MiB worker pack; +37 MiB only if the user opts in | **~190–205 MiB ESTIMATE** installer (MEASURED 163.66 + ~37 MiB compressed asset) |
| Code-only update | Installer only; pack unchanged | Installer only; no re-download | Every update repays the runtime bytes |
| Offline | Full translation offline after pack install; unavailable before it | Full translation offline after opt-in download; unavailable before it | Best: present from first launch, no pack dependency |
| Update frequency | Pin bump → new pack version → existing hash/protocol gates | Pin bump → new catalogue row → user must click again | Pin bump → new installer build |
| Licensing / notices | Needs new MIT entries for llama.cpp, vendored ggml and LLVM OpenMP (`THIRD_PARTY_NOTICES.md` has no llama.cpp row today — **VERIFIED**); LGPL-style source offer not required for MIT code, but attribution is | same | same, plus notices must be in the signed installer resource |
| Security | Archive SHA + per-file SHA/size already verified (`build_pack_manifest.py:96-127`, `checksum.py:48-70`); URL from GitHub Release, host allowlist via `offline_pack/gates.py:68-91`; **no arbitrary EXE download**. Client verifies hash only — do not claim Authenticode (`runtime-delivery-options.md:85`) | Same hash/size discipline if it reuses the pack downloader; needs its own allowlist path and a new SEC-002 consent field; no arbitrary URL from config | Build-time SHA only; no runtime hash check (same as ffmpeg/native DLLs); unsigned DLLs may affect SmartScreen; no runtime download surface |
| Failure UX | Reuses pack states (Downloading / Verifying / Corrupt / Ready) but needs a new "translation runtime not ready" notice with a Models action, in 8 locales (C-I18N-1) | Natural row state (Download / progress / failed / installed), like `TranslationModelDownloadRow.tsx`; most new states and most new IPC surface | No install UX; a missing/corrupt DLL still needs a repair notice — today it is the generic translation-failure toast |
| Moving parts / risk | Low: reuses every existing gate; blocked until a pack is actually published (404 today) | Medium-high: new renderer row, new IPC command in Python + Rust allowlist + renderer types, new consent field, 8 locale keys | Medium: config + CI + notices + bundle gate; largest first download |

### C5. Recommendation and later-round change list

**Recommend option (a), gated behind the parent brief's step 3 (publish the worker pack first).**
It is the only path that adds no new IPC surface or consent field, reuses the manifest/hash/SSRF
gates that already exist, and keeps code-only updates at the current installer size. Option (b)
is a reasonable fallback if the pack stays worker-only for other reasons and translation is treated
as strictly opt-in, but it is the most expensive surface to get right (SEC-002 allowlist, IPC
parity, 8 locales, consent dialog). Option (c) is not justified: it makes every code update pay
~37 MiB and gives no offline advantage over a completed (a).

A later implementation round would change exactly these places (none changed here):

1. **`scripts/llama-vulkan-win64.json` (new)** — pin `version: b12521`, tag, asset name, URL,
   SHA-256 `d2498cfd…`, size 38,757,221, upstream MIT source URLs, and an explicit `install_names`
   allowlist containing only the files listed as needed in C3. Never invent a hash.
2. **`.github/workflows/runtime-pack-publish.yml`** — add a fetch-and-verify step before
   "Resolve canonical zip name + pack the worker" (`:309`), using the same SHA check pattern as
   `tauri-windows-build.yml:227-231,816-832`; stage only allowlisted files; add a pack-content gate.
   `build_pack_manifest.py` needs no change — it hashes every zip member generically.
3. **`offline_pack/core.py:36-39`** — re-check the 180 MB compressed / 450 MB unpacked budgets with
   real bytes; do not bump them speculatively.
4. **`translation/paths.py:92-127`** — add the installed pack root as an authoritative resolver
   seam (single source of truth: the same `core.py` root the downloader uses), keeping app-data as
   the last fallback for dev/manual installs. `service.py:150-158,374-383` gets a structured
   "runtime not ready" outcome so UI copy can name the real state.
5. **Renderer** — translation status reads the resolver's real state; one missing-runtime notice
   with a Models/settings action, translated into all 8 locales (C-UI-1, C-I18N-1). No second
   download button: the pack owns the transfer.
6. **`docs/THIRD_PARTY_NOTICES.md` + `scripts/generate_third_party_notices.py`** — add llama.cpp
   (MIT), ggml (MIT) and LLVM OpenMP entries; re-run notices `--check`.
7. **Tests** — pack manifest includes/excludes the right names, resolver finds pack root before
   app-data, hash mismatch refuses to install, missing runtime notice copy, i18n completeness; end
   to end per the parent brief's fresh-profile step 9.

**Owner must do by hand:** choose the pin version and CPU/Vulkan target; confirm the release digest
(the values above are read-only GitHub metadata, not an agent download); publish the worker pack so
the path exists; approve the new notice copy in all 8 locales; provide a clean Windows profile and
a human tester for the real hotkey/paste step (C-HOOK-1). No agent should download or ship the
runtime in this round.
