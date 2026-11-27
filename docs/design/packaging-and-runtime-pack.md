# Packaging and runtime-pack architecture (evidence map, read-only)

Read-only audit, 2026-11-27. Everything below is from code, build config, workflow files,
local build outputs, GitHub REST metadata (read-only) and logs. `VERIFIED` means the
artifact was read or measured here; `UNVERIFIED` means the evidence was not available.
No build, download, install, repo edit outside this file, or process kill was performed.
Owner recollections and reviewer hypotheses are treated as unverified until proven.

## Plain English first

The split is real in source and CI config, but it is only half-wired:

* The Windows installer built by CI is the **slim** one. It carries the Rust host, the
  Python sidecar, ffmpeg, the native speech DLLs, the hotkey listener, notices and tray
  icons. It does **not** carry the worker (`src-tauri/tauri.windows-x86_64-slim.conf.json:48-57`,
  `.github/workflows/tauri-windows-build.yml:594,923-951`). VERIFIED.
* The "runtime pack" published by the other workflow is **a zip containing one file:
  the frozen worker exe** (`.github/workflows/runtime-pack-publish.yml:309-327`). It does
  **not** contain the speech DLLs, ffmpeg, or GGUF weights. VERIFIED.
* A downloader exists and runs on every launch, but **no pack manifest or pack zip has
  ever been published on GitHub**. Both manifest URLs 404 today. The app logs
  `no pack manifest published yet, nothing to download`. VERIFIED (GitHub REST +
  `%APPDATA%\lausu\logs\lausu.log`).
* Therefore a normal user **cannot obtain the pack today**, and a machine that has only
  the slim installer has no usable local ASR: the worker reports
  `The speech runtime is not installed. Reinstall the app or contact support.`
  (`voice_typer/worker/asr_runner/runner.py:171`). VERIFIED in live logs.
* That message is **fully explained by the missing runtime directory**, not by a bad
  model or a broken decoder: with a scratch pack root pointing at the already-present
  real DLLs, Parakeet loaded and decoded 12 s of real audio in 1.85 s on CPU, and a
  source-app dictation produced bubble show → recording → stop → transcribe → bubble
  hide. VERIFIED in this session (scratch evidence:
  `C:\Users\11\AppData\Local\Temp\opencode\r8-s1-scratch\`).
* Full hardware-hotkey → on-screen bubble → paste with LOCAL provider remains
  **UNVERIFIED**: OS key injection is barred by the worker rules, the scratch take was
  near-silent (no text to paste), and no Tauri host window was driven.

## What ships where (diagram-like table)

| Product | Where built | What is inside | Evidence |
| --- | --- | --- | --- |
| Slim NSIS installer (`Lausu-Windows-Installer`) | `tauri-windows-build` → `cargo tauri build --config tauri.windows-x86_64-slim.conf.json` (`.github/workflows/tauri-windows-build.yml:834-846`) | Rust host + WebView assets; `python-sidecar-*.exe` and `ffmpeg.exe` as `externalBin`; `resources/transcribe-cpp/` (13 DLLs + `contract.json`), `windows-key-listener.exe`, `THIRD_PARTY_NOTICES.md`, `icons/tray/` as resources. **No worker.** | VERIFIED config `:48-57`; gate `:923-951` |
| MSI installer (`Lausu-Windows-MSI`) | same `cargo tauri build` | same payload as NSIS, different container | VERIFIED workflow `:1088-1093` |
| Intermediate sidecar artifact (`windows-sidecar-exe`) | `build-sidecar-exe` Nuitka freeze | onefile Python sidecar containing `voice_typer`, `websockets`, `Crypto`, yt-dlp, package data (`*.onnx`, JSON), numpy/scipy/ORT transitive deps | VERIFIED `.github/workflows/tauri-windows-build.yml:286-329`; `scripts/build/build_sidecar_windows.sh:154-164` |
| Intermediate worker artifact (`windows-worker-exe`) | `build-worker-exe` Nuitka freeze | onefile Python worker: `voice_typer`, `onnxruntime`, `websockets`, numpy/scipy, package data. **No native speech DLLs, no ffmpeg, no GGUF weights.** | VERIFIED `.github/workflows/tauri-windows-build.yml:526-562`; `scripts/build/build_worker_windows.sh:200-252` |
| Runtime-pack zip (`lausu-runtime-pack-<n>-<triple>.zip`) | `runtime-pack-publish` | the worker exe only (one `zipfile.write`) | VERIFIED `.github/workflows/runtime-pack-publish.yml:309-327` |
| Downloader alias (`pack-<n>.zip`) | `publish` job | byte-identical copy of the primary triple's zip | VERIFIED `runtime-pack-publish.yml:377-379` |
| `pack-manifest.json` | `publish` job | `{version, sha256 of ARCHIVE, files:[{name,sha256,size}], min_proto_version}` | VERIFIED `scripts/release/build_pack_manifest.py:96-127`, `voice_typer/server/service/offline_pack/core.py:27-34` |
| Full-offline installer | `scripts/build/build_full_offline_installer_windows.sh` + `scripts/windows/full-offline-installer.nsi` | slim installer + pack zip, intended to write `pack_bundled: true` | Scripts VERIFIED; **not invoked by any workflow** (grep of `.github/workflows/`). UNVERIFIED as a shipped artifact. |
| Translation runtime (`llama-server.exe` + ggml DLLs) | no workflow stages it | installed into `%APPDATA%\lausu\translation`; app resolves writable app-data dir last | VERIFIED `voice_typer/server/translation/paths.py:92-106,123-127`; present on this machine (%APPDATA% listing). NOT in installer config. |

### Measured sizes

`MEASURED` = read from the local filesystem; `CI METADATA` = GitHub REST artifact zip
size of run `45024128135` (latest completed `Build Windows`, 2026-11-22, head
`9c099320`), **not** the uncompressed payload. `ESTIMATED` = inferred from freeze flags.

| Artifact / file | Size | Label |
| --- | ---: | --- |
| CI `Lausu-Windows-MSI` artifact zip | 185,345,958 B / 176.76 MiB | CI METADATA |
| CI `Lausu-Windows-Installer` artifact zip | 171,607,767 B / 163.66 MiB | CI METADATA |
| CI `Lausu-Windows-Sidecar-Binaries` artifact zip | 124,534,220 B / 118.77 MiB | CI METADATA |
| CI `windows-sidecar-exe` artifact zip | 124,442,947 B / 118.68 MiB | CI METADATA |
| CI `windows-worker-exe` artifact zip | 123,540,191 B / 117.82 MiB | CI METADATA |
| `ffmpeg-x86_64-pc-windows-msvc.exe` in `src-tauri/bin` | 134,459,904 B / 128.23 MiB | MEASURED |
| `onefile-tmp/slim-check.exe` (old local extraction) | 175.50 MiB | MEASURED, stale local artifact |
| `onefile-tmp/python-sidecar-*.exe` (old local extraction) | 144.19 MiB | MEASURED, stale local artifact |
| `%APPDATA%\lausu\translation\ggml-vulkan.dll` | 41.10 MiB | MEASURED |
| `onefile-tmp\numpy.libs\libopenblas…dll` | 36.40 MiB | MEASURED |
| `onefile-tmp\onnxruntime\capi\onnxruntime_pybind11_state.pyd` | 17.88 MiB | MEASURED |
| `onefile-tmp\voice_typer\server\dpdfnet2.onnx` | 9.71 MiB | MEASURED |
| `src-tauri\resources\transcribe-cpp\STUB.txt` | 134 B | MEASURED, placeholder |
| `src-tauri\bin\lausu-worker-x86_64-pc-windows-msvc.exe` | 63 B | MEASURED, placeholder |

Top-30 local file scan (largest 30 under `src-tauri/{bin,resources}`,
`%LOCALAPPDATA%\lausu\onefile-tmp`, `%APPDATA%\lausu\translation`) is dominated by:
`slim-check.exe` 175.50, sidecar 144.19, ffmpeg 128.23, translation ggml-vulkan 41.10,
three OpenBLAS DLLs 36.40/19.55/19.32/19.32, stale media codec DLLs 18.37/18.32/12.16/
11.98, ORT pybind 17.88, ORT dll 17.26, llama-connect 10.94, llama-server-impl 10.00,
DPDFNet 9.71, cryptography `_rust.pyd` 9.48, `hf_xet.pyd` 9.06, llama-common 8.22,
more stale codec DLLs 7.32/5.62, tokenizers 7.21, python312.dll 6.61, highspy 6.40,
two probe exes 6.35/6.27, libcrypto 5.66, python311.dll 5.58 MiB. All MEASURED.
The **current** installer's internal sidecar byte split is NOT measurable locally: the
one exe is a compressed Nuitka bundle; only the CI artifact zip size is known.
Estimated pack-zip contents: one worker exe ≈118 MiB compressed (from the CI artifact),
plus zip overhead. ESTIMATED.

## First-launch flow (code-verified)

1. **Trigger.** Startup phase calls `startup_tasks.check_offline_pack_on_launch`
   (`voice_typer/server/startup_sequence/_phases_late.py:211`) on a fire-and-forget
   daemon thread. Renderer also calls `check_offline_pack_update` on network-online and
   on a manual Settings action (`voice_typer/client/src/renderer/src/hooks/useNetworkOnline.ts:124-152`,
   `components/settings/OfflinePackSection.tsx:166`). VERIFIED.
2. **Local scan.** `_local_offline_pack_version()` scans the pack root for a version dir
   whose `pack-manifest.json` + every declared file exist
   (`update_check.py:59-83`, `offline_pack/core.py:279-291`). Root is
   `%LOCALAPPDATA%\lausu\runtime-pack` on Windows, overridable by `VT_PACK_ROOT`
   (`core.py:91-104`). VERIFIED.
3. **Manifest fetch.** Ordered candidates: explicit arg → `VT_PACK_MANIFEST_URL` →
   `https://github.com/AbdallahIsDev/Lausu/releases/latest/download/pack-manifest.json`
   → `https://github.com/AbdallahIsDev/Lausu/releases/download/offline-pack/pack-manifest.json`
   (`update_check_urls.py:13-34`, `branding.APP_REPO`). 1 MiB cap, SSRF allowlist + HTTPS
   (`gates.py:68-91`, `urls:42-43`). VERIFIED.
4. **404 handling.** If *all* default candidates are 404, the check returns
   `success=True, reason="no_remote_manifest"` and logs
   `[UPDATE] no pack manifest published yet, nothing to download`
   (`update_check.py:243-254`). This exact line is in the live log at 2026-11-27
   22:18:49, 22:29:11, 22:47:32, 23:54:48, and in `docs/design/model-lifecycle.md:248`.
   VERIFIED. No error toast for this benign case.
5. **Download.** URL is derived by replacing `pack-manifest.json` with
   `pack-<version>.zip` in the fetched URL (`update_check.py:118-125`). Resume with
   Range, SHA-256 of the archive, rate-limit backoff, disk-space gate, cross-process
   lock (`offline_pack/download.py:35-105`, `gates.py:25-53`, `core.py:45-52`).
   VERIFIED from code; never exercised against a real published asset (see below).
6. **Install.** Extract to `<root>/<version>.new`, check every file against manifest
   hashes, write `pack-manifest.json` after verification, atomic swap, emit
   `offline_pack_verified` (`offline_pack/install.py:93-175`). VERIFIED from code.
7. **Worker.** Rust host spawns the worker on `offline_pack_verified`
   (`src-tauri/src/sidecar/ws/reader.rs:188-189`, `src-tauri/src/sidecar/spawn/worker.rs:534`);
   sidecar learns the port from a host-relayed `worker_started` frame
   (`voice_typer/server/sidecar_ws_internals/read_loop.py:103-109`, `worker_relay.py:59-107`).
   Scratch probe verified this relay and `get_status` reported `offline_pack.state="ready"`.
8. **UI.** `useOfflinePackDownload` tracks 12 lifecycle events with a progress percent
   (`voice_typer/client/src/renderer/src/hooks/useOfflinePackDownload.ts:88-128,167-347`);
   Settings card shows status and re-check button (`OfflinePackSection.tsx:101-175`).
   The hook's own header says "silent-mode" and "no progress bar in the main UI"
   (`:1-11`), which conflicts with the progress-bearing code path. VERIFIED text drift.

### Can a user get the pack today?

**No.** GitHub REST (read-only, 2026-11-27):
`/releases?per_page=30` returned exactly three releases — two old app releases with a
setup exe, and one prerelease holding only the pinned ffmpeg archive. No release has
`pack-manifest.json`, `pack-<n>.zip` or `lausu-runtime-pack-*.zip`. `/releases/latest`
resolves to `v1.1.0` (2026-06-02), which has no pack asset. `git/ref/tags/offline-pack`
is 404. VERIFIED. `runtime-pack-publish.yml` is `workflow_dispatch`-only
(`:37-38`) and defaults to `draft: true` (`:58-62`), so even a manual run would be
invisible to `/releases/latest` until published (file comment `:29-33`). The
end-to-end download→verify→install→worker path has only been driven with synthetic
manifests (`scripts/verify_pack_failure_matrix.py`, `tests/test_pack_manifest_builder.py`,
`tests/test_frozen_slim_live_gate.py`) and scratch pack roots
(`scripts/verify_worker_degrade_live.py`, ADR-0024 Step 6/7). **UNVERIFIED** against a
real published asset.

## Runtime lookup seams (A3)

| Asset | Installer or pack? | Resolver | Mismatch |
| --- | --- | --- | --- |
| ffmpeg | Slim installer `externalBin` (`tauri.windows-x86_64-slim.conf.json:50`); fetch step `tauri-windows-build.yml:816-822` | `ffmpeg_binaries.py:157-163` → `LAUSU_FFMPEG` → shipped dirs → dev-only PATH (`:142-154`) | Pack workflow never fetches or stages ffmpeg (`runtime-pack-publish.yml:243-257`). A pack-only download has no ffmpeg. |
| `transcribe.dll` + ggml DLLs + `contract.json` | Slim installer resource (`slim conf:53`); fetch step `tauri-windows-build.yml:227-231,828-832`; pin `scripts/transcribe-cpp-win64.json:15-30` | `voice_typer/worker/asr_runner/runner.py:103-121,167-203` → `TRANSCRIBE_LIBRARY` → shipped dirs incl. `transcribe-cpp/`; contract check `contract.py:54-74` | Pack workflow does **not** fetch/stage the native bundle. The worker exe has no DLLs. This is the direct cause of the shipped-app error. |
| `llama-server.exe` | Neither installer config nor pack | `translation/paths.py:27-30,92-106,109-127` → `LAUSU_TRANSLATION_RUNTIME` → shipped dirs → `%APPDATA%\lausu\translation` | Present locally only as manually installed app-data files; no CI step produces it. Frozen builds have no bundled translator. |
| ONNX Runtime + noise models | Slim sidecar (VAD/noise on real-time path) and worker (`--include-package=onnxruntime`, `build_worker_windows.sh:242`, `--include-package-data=voice_typer.server:244`) | package imports | Consistent with ADR-0031 Phase 1 (ORT stays for noise). No regression found. |
| GGUF weights | Neither; downloaded on first use into HF cache | `gguf_download.py:56-79` (`local_files_only=True`) | Registry complete (`gguf_model_registry.py:43-108,366-374`). VERIFIED on this machine: parakeet GGUF 740,363,168 B resolves from `~/.cache/huggingface/hub`. |

## Live proof: missing runtime vs. bad decoder (A6)

Paths the app checks on Windows: `%LOCALAPPDATA%\lausu\runtime-pack` (`core.py:97-99`),
fallback `%APPDATA%\lausu\runtime-pack` (`:129-134`), plus `VT_PACK_ROOT` override
(`:93-95`). Actual state: the Local root exists and contains empty version dirs
`1.2.3`, `2.0.0`, `2.1.0` plus three `.lock` files and `media-extractor.json`; it has
**no** `pack-manifest.json` and no worker. Roaming root does not exist. VERIFIED.
Real runtime elsewhere on this machine (not in the app bundle):
`C:\Users\11\gguf-spike\bin\cpu-vulkan\out\transcribe-native-windows-x86_64-cpu-vulkan\`
contains `transcribe.dll` 2,052,608 B, 12 ggml DLLs (ggml-vulkan 43,652,608 B), and
`contract.json` 125 B; HF cache holds the parakeet GGUF. VERIFIED.

Scratch probe (own processes, hard links only, scratch config, nothing downloaded,
committed or copied): `VOICE_TYPER_CONFIG_DIR=<scratch>\cfg`,
`VT_PACK_ROOT=<scratch>\pack`, `TRANSCRIBE_LIBRARY=<scratch>\pack\v9\transcribe.dll`,
`HF_HUB_CACHE=<real HF cache>`, `PYTHONPATH=<repo>`. Source sidecar + source worker were
spawned from the repo venv and terminated by the probe afterwards.

* **PASS — worker load:** `load_parakeet_model_result {loaded:true, backend:"parakeet",
  device_info:"auto (transcribe.cpp)"}` in **0.44 s**; worker log
  `23:55:54 INFO [WORKER] parakeet model loaded: language=None`,
  `load_backend: loaded Vulkan backend from …\pack\v9\ggml-vulkan.dll`,
  `load_backend: loaded CPU backend from …\pack\v9\ggml-cpu-cascadelake.dll`.
  Worker RSS 5.7 MiB before and after load (weights are mmap'd; resident pages are
  touched at decode, not at open). MEASURED.
* **PASS — real decode:** 12.0 s / 192,000 samples from `test16k.wav` through
  `transcribe_samples` returned 259 chars in **1.85 s**,
  `device_info:"cpu (transcribe.cpp)"`, `error:null`; worker log
  `[GGUF] run complete: status=0 segments=1` and
  `[WORKER] offline transcription complete (len=259 chars) 1.9s`. MEASURED.
* **PASS — production dictation entry (no OS key):** sidecar WS `toggle_dictation`
  (origin `button`) produced `23:55:56 [DICTATION] start requested`,
  `[DICTATION] Recording started OK`, `[WAVEFORM] Bubble shown`,
  `[STREAMING] worker streaming session started`, then stop at 23:55:59,
  `[DICTATION] Recording stopped 3.0s of audio`, `[TRANSCRIBE] Transcription complete
  (len=0) 0.8s`, `[WORKER] offline transcription complete (len=0 chars) 0.7s`, bubble
  hide. VERIFIED.
* **FAIL/UNVERIFIED — paste:** the mic take was near-silent (rms 0.0049), so there was
  no text to deliver (`dictation_suppressed`). `paste_on_stop` was set false in the
  scratch config to avoid pasting into another session's window, and no hardware hotkey
  or Tauri bubble window was driven (C-HOOK-1). Paste path is therefore UNVERIFIED, not
  failed by the runtime.
* **Conclusion:** the missing pack/runtime directory fully explains
  `The speech runtime is not installed` in the live profile. With the seam in place the
  same code loads and decodes correctly. VERIFIED.

## Findings and proposed fixes (fix NONE applied)

1. **Pack zip omits the native runtime.** `runtime-pack-publish.yml:243-257` builds only
   the worker; `build_worker_windows.sh:200-252` includes no DLLs; the installer fetch
   steps (`tauri-windows-build.yml:227-231,828-832`) are the only places that stage
   `transcribe.dll`/ggml DLLs. Proposed: make the pack contain the pinned native bundle
   + ffmpeg (or make the worker resolve them from the installer and document that the
   pack is worker-only), and add a pack-level gate. UNVERIFIED which the owner intends.
2. **No published manifest.** `runtime-pack-publish.yml:37-38,58-62` is dispatch-only and
   draft-by-default; GitHub has no pack assets. Proposed: publish a real `offline-pack`
   tag once the pack contents are decided, then run the download path end to end.
3. **"worker exe 0.00 MB" in the gate table is the local stub, not the CI worker.**
   `verify_windows_bundle.py:546-561` sizes `src-tauri/bin/lausu-worker-<target>.exe`;
   locally that file is 63 B (`gen_tauri_icons_stub.py:656-725`), so it prints 0.00 MB.
   The real 117.82 MiB artifact comes from the separate `build-worker-exe` job
   (`tauri-windows-build.yml:556-562`), which the installer job does not depend on
   (`:576`). Not a bug in the gate, but the table is easy to misread. Proposed: label
   the row `worker exe (slim bundle: stub)` or show the artifact size separately.
4. **Redundant artifacts.** `windows-sidecar-exe` duplicates
   `Lausu-Windows-Sidecar-Binaries` (`:363-369` vs `:1095-1108`); `windows-worker-exe`
   duplicates the zip's single payload (`runtime-pack-publish.yml:309-335`); two
   `windows-pybs-freeze-x86_64` uploads share one name in the same run. Additive naming
   is required by C-CI-13, so these are kept, not deleted.
5. **Signature claim not wired.** IPC docs claim `offline_pack_verified` means SHA256 +
   Authenticode/notarization (`docs/ipc-reference.md:377`), but the only signature
   helper is `offline_pack/core.py:304-333` (macOS) and it has **no production caller**
   (grep across `voice_typer/`). Proposed: wire it or correct the doc.
6. **Soft GPL gate still default 0.** `.github/workflows/tauri-windows-build.yml:1158`
   and `scripts/verify_windows_bundle.py:25-29`. ADR-0031's last step says flip after a
   real frozen build; no frozen build was made this round, so status is UNVERIFIED, not
   a regression.
7. **Full/full-offline configs exist but are not shipped.** `tauri.windows-x86_64.conf.json:50`
   still lists the worker; CI builds the slim overlay (`:594`) and asserts no worker in
   the bundle (`:923-951`). `build_full_offline_installer_windows.sh` has no workflow
   caller. Proposed: document that these are test/optional paths, not release paths.
8. **No stale retired-stack build refs found.** Production build scripts and workflows
   contain no import/include/fetch of the retired ASR stack (grep of `*.py,*.sh,*.yml,*.json,*.ps1,*.nsi,*.toml`);
   the only remaining mentions are prohibition tests and the soft gate's pattern list.
   Hidden-import regression in the frozen worker: UNVERIFIED (no build produced).
9. **Doc drift:** `useOfflinePackDownload.ts:1-11` says consent-gated/silent/no progress
   bar; backend is always-on (`offline_pack/gates.py:56-65`) and the hook tracks a
   progress percentage (`:118-122,189-200`). Proposed: update the header comment.

## Open questions

* Should the runtime pack own the native speech runtime (and ffmpeg), or only the
  Python worker, with DLLs always installed by the slim installer? Evidence for both
  exists; no owner decision found in code or docs.
* If the pack stays worker-only, what is the supported upgrade path when the pinned
  DLL version changes? No version-gate was found between `contract.json` (version
  0.4.2, header hash pin) and the pack manifest's `min_proto_version`.
* Should `llama-server` be bundled, or stay a manual app-data install? No CI step
  ships it today.
* Who publishes `offline-pack`, and who runs the download path end to end once the
  manifest exists? Not answerable from the repo.
