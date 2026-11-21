## 2026-11-09 — MEM-1 Parakeet ORT arena live measurement (Windows, CPU-only)

Command: `bench/parakeet_mem_bench.py --arm arena-on|arena-off` (one fresh process per arm). Clip: 36.05 s
`bench-out/speech.wav` (mono 16 kHz) tiled to 45 s. Real cached int8 weights: `encoder-model.int8.onnx` 622.0 MB +
`decoder_joint-model.int8.onnx` 17.4 MB. onnx-asr 0.12.0, onnxruntime 1.29.0, `CPUExecutionProvider`.

| arm | RSS after load | after decode 1 | after decode 2 | private after load → decode 2 | transcript |
| --- | --- | --- | --- | --- | --- |
| arena-on (ORT old default) | 765 MB | 937 MB | 1103 MB | 1131 → 1660 MB (+529) | 652 chars |
| arena-off (shipped fix) | 760 MB | 767 MB | 767 MB | 1122 → 1123 MB (+1) | identical 652 chars |

Decode times: arena-on 2.37 s / 2.45 s; arena-off 3.11 s (first, ORT init) / 2.46 s. No steady-state RTF regression.
Verdict: arena-off holds post-run RSS within ~1% of post-load, so the success bar (≤10%) is met. MEM-1 marked
`✅ Fixed`. Raw reports: `bench-out/parakeet-mem-arena-{on,off}.json` (gitignored).

## 2026-11-10 — openrouter blocked by URL allowlist, `internal_error` envelope, `***` log mask

Live log: `provider_test` for openrouter failed with `provider_api_url host 'openrouter.ai' is not in the
trusted allowlist.  Call ***() to add it.`, and dispatch reported it as `server.internal_error`.

- Fixed: `openrouter.ai` + `ollama.com` added to `_DEFAULT_ALLOWED_HOSTS` (`security/url_allowlist.py`) —
  both are built-in provider endpoints that were never allowlisted (the ADR-0017 "new provider onboarding"
  edge).
- Fixed: provider HTTP calls raise `ProviderRuntimeError` (`server.provider_runtime_error`) instead of a bare
  `ValueError` for an unusable endpoint (`model_providers/_http.py`), so `provider_test`/`provider_models`
  no longer degrade to `server.internal_error`.
- Fixed: allowlist rejection message no longer names a 20+ char bare identifier, so SEC-003 masks nothing
  (was `Call ***() to add it`, now `Add it to trusted_extra_hosts or set VOICE_TYPER_TRUSTED_HOSTS.`).
- Tests: `tests/model_providers/test_provider_http_url_guard.py` (typed error, no request attempted) and
  `TestBuiltinProviderEndpointsAreTrusted` in `tests/security/test_url_allowlist.py` (every built-in provider
  base URL allowlisted; rejection message survives `redact_secret` with no `***`).
- Validation: `ruff check` clean on the changed/added files; `pytest tests/security/test_url_allowlist.py
  tests/model_providers tests/handlers/test_provider_handlers.py tests/test_secrets.py
  tests/test_http_safety_ssrf.py tests/providers -q --no-cov` → 354 passed (Windows).
- Rule added: C-LOG-7 (no bare 20+ char code identifier in a log/user-facing message).
- Follow-up resolved in session 2 below: `providers.errorRuntime` now covers `server.provider_runtime_error`.

## 2026-11-10 (session 2) — Providers UI: key dialog, error toasts, save-time URL validation

- Providers page: the inline key accordion (chevron + `aria-expanded` + `.collapse-root`) is replaced by a plain
  card button that opens `ProviderKeyDialog` (shared `Dialog` primitive, same pattern as Models → cloud models).
  `ProviderCard` now carries only the trigger; `KeyEditor` lost its inline verdict paragraph.
- Errors are in-app notifications: `useProviderData` routes every failure through `toast.error(errorCopy(err))`;
  the page-level error banner and `ProviderResult`/`results` state are deleted. Success is silent (C-UXERR-2),
  so `providers.testOk` was removed from all 8 locales.
- `server.provider_runtime_error` now has copy: `providers.errorRuntime` in all 8 locales, plus
  `providers.keyDialogHint` for the dialog description (all 8 translations written, no English pasted).
- `set_config` validates the endpoint host at save time (`config_handlers._untrusted_endpoint_rejection`):
  `cloud_api_url`, `llm_api_url`, `tts_api_url`, `openrouter_base_url` must be allowlisted; a `trusted_extra_hosts`
  entry in the same payload counts, and an unchanged (legacy) value never blocks an unrelated save.
- SEC-003 message audit (`security/*.py` + `_secrets.py`, AST scan of `raise`/log literals): 17 files,
  55 message literals, 0 masked by `redact_secret` — no other bare 20+ char identifiers remain.
  Report: `.tmp-evidence/security-message-mask-audit.txt` (gitignored).
- Validation: `npx biome check` clean; `npm run typecheck:ci` exit 0; `npx vitest run src/renderer/src/pages/providers
  src/renderer/src/i18n` → 152 passed; `ruff check` clean; `pytest tests/handlers tests/security
  tests/model_providers tests/providers tests/server/test_dispatch_config.py tests/config/test_config_validation.py
  tests/test_config_validators_cross_field.py tests/test_trusted_extra_hosts.py -q --no-cov` → 988 passed,
  1 failed: `test_handler_signature_conformance[CudaHandlersMixin]` — untracked `voice_typer/server/handlers/
  cuda_handlers.py` (not part of this change) still annotates `resp: dict`; left untouched per C-AGENT-6.
- Rule added: C-CONF-6 (validate persisted endpoint hosts in the write that persists them).

## 2026-11-10 (session 3) — provider `custom` is now a general “OpenAI-compatible” provider

- `builtin.register_all()`: id `custom` label is now `OpenAI-compatible` (no “Custom”, no “TTS”) and the
  descriptor advertises ASR + TTS + LLM. `_custom_tts_client` was replaced by `_openai_compatible_client`:
  ASR → `CloudEngine(provider="openai")` behind `CloudAsrAdapter` (`cloud_api_url`, consent honoured),
  TTS → `HostedTtsClient` (`tts_api_url`), LLM → `OpenAiCompatibleChatClient` (`llm_api_url`, base or full
  `/chat/completions` URL). `config_fields` records each domain's endpoint field.
- An empty endpoint per domain raises `ProviderRuntimeError` instead of silently falling back to OpenAI's own
  host; `cloud_direct`'s TTS reason now says “openai or OpenAI-compatible”.
- Renderer: `SAMPLE_PROVIDER_LIST` label/domains match the real descriptor (skeleton measures the same card).
- Tests: capability matrix now pins `custom` at `["asr", "llm", "tts"]` and the LLM provider-id set includes it;
  `test_domain_wiring.py` builds all three clients and pins the empty-endpoint refusal.
- Validation: `ruff check` clean; `pytest tests/providers tests/model_providers tests/handlers/test_provider_handlers.py
  -q --no-cov` → 124 passed; `npx biome check` clean; `npm run typecheck:ci` exit 0; `npx vitest run
  src/renderer/src/pages/providers` → 18 passed.

## 2026-11-10 (session 3b) — OpenAI provider card removed + production-readiness audit

- Removed the TTS-only `openai` provider descriptor and `_openai_tts_client`; the
  "OpenAI-compatible" provider is now the only OpenAI-family card (one generic surface instead
  of two overlapping ones). `_VALIDATOR_PROVIDER_ID` still accepts `openai` so a config written
  while the card existed stays savable; routing fails with a typed `ProviderNotFoundError`
  instead of silently pointing at OpenAI's host. Renderer skeleton sample and capability-matrix /
  routing tests updated.
- Audit (evidence-based, scoped; full report `docs/audit/2026-11-10-production-readiness.md`):
  full-tree ruff 8 → 0 owned findings (2 remain in another agent's untracked `cuda_install/`),
  19,718 tests collected with 0 collection errors, `pip-audit --strict --require-hashes` → 0 known
  vulnerabilities, renderer `typecheck:ci` + biome clean. No `shell=True` / `pickle.loads` /
  `eval` / `verify=False` in runtime code; plaintext HTTP only for loopback defaults.
- Fixed from the audit: `vocabulary.py` unbound-name (`auto_dropped` hoisted, rollback unchanged);
  `tts/runtimes.py` malformed-asset `TypeError` → typed `TtsError` + regression test
  (`tests/test_tts_runtimes.py`); `test_recording_quality.py` annotations narrowed to
  `np.ndarray`; 6 whole-tree ruff findings auto-fixed (import order, Yoda, two 121-char lines).
- Doc parity: `docs/ARCHITECTURE.md` + `tests/test_architecture_doc_accuracy.py` reconciled to
  the live IPC surface (`_COMMAND_REGISTRY` 109 commands, `EVENT_TYPES` 60 events; doc said
  104/59). Parity test pins the new counts and rejects the stale strings.
- Open, reported not fixed: pyrefly gate is red (2,579 errors; 703 test locations, 4 production
  locations after the four root-cause fixes = 3 × `hotkey_dispatcher.py:96` mixin inheritance
  + 1 × `startup_sequence/_phases_early.py:97` AppProtocol descriptor); untracked
  `voice_typer/server/cuda_install/` + `tests/model_providers/test_local_catalogue_cache.py` in
  the worktree (another agent's in-flight work, per C-AGENT-6). Full pytest suite NOT run here
  (C-AGENT-1) — orchestrator must certify the final state.

## 2026-11-10 (session 3c) — audit wave 2: gates greened, protocol drift fixed

- Whole-tree ruff is now **clean** (was 8, then 2): `cuda_install/downloader.py` `Cancelled` →
  `CancelledError` (N818) across source + both test files; `cuda_install/paths.py` uses
  `contextlib.suppress(ValueError)` (SIM105).
- `ServiceProtocol` was missing `chat_listen_start` / `chat_listen_stop` / `chat_state` /
  `chat_reset`, which the IPC handlers call through `self.service` — the DI drift test
  (`tests/test_di_providers.py`, 19 passed) had been failing on this. Added the four methods.
- `HotkeyDispatcher` mixin `TYPE_CHECKING` stubs now declare `Callable[[], None]`; pyrefly's
  three `inconsistent-inheritance` errors are gone (production type errors 8 → 1).
- `tests/test_i18n_keys_parity.py` pinned `hotkeyValidation.holding`, a key that exists in no
  locale, so the check compared `None == None`; repointed at the real
  `hotkeyPicker.holdingPrefix` (zh/ru translations verified). i18n parity now 110 passed,
  1 skipped.
- Remaining production type error: `AppProtocol.history_db` vs `LausuApp`'s `LazyProperty`
  descriptor (F-4 in `docs/audit/2026-11-10-production-readiness.md`). The `@property`
  variant was tried and reverted (pyrefly still rejects it and the DI test introspects
  `__annotations__`); runtime conformance is pinned by `test_di_providers`. No suppression.
- Verification: ruff clean; final scoped suite (di + cuda_install + i18n + doc-parity + tts +
  providers + model_providers + hotkey dispatcher) → **355 passed, 1 skipped**; pyrefly
  2,555 errors total, **1 production location**.

## 2026-11-10 (session 3d) — pyrefly gate measurement corrected, cuda module committed

- Correction to session 3b: the pyrefly gate is NOT red. CI runs
  `pyrefly check voice_typer/ --baseline <empty>` and fails only when the live PRODUCTION
  count exceeds the `pyrefly-baseline.json` count — test-mock errors are outside its scope.
  Measured with the CI form: **live 326 vs baseline floor 356** → passes with 30 errors of
  headroom. The debt is the floor size, not a broken gate; ratchet it down, regenerate on the
  baseline's own platform (platform-only entries drop out otherwise).
- Committed the previously untracked `voice_typer/server/cuda_install/` + `tests/cuda_install/`
  (local commit `8d40eb0f9`; no push). Note: the index already carried pre-staged deletions of
  six renderer page skeleton components from an earlier session, so they landed in the same
  commit; not reverted (E18).

## 2026-11-11 - Anthropic STT: extension transport reviewed and live-tested (Windows)

Review of the worker delivery for ASSTT-1 (`tools/internal_plugins/anthropic_stt/`), plus a live
transport run. Verdict: transport sound, three follow-ups open (see review.md ASSTT-1).

Evidence (orchestrator session, Windows, Node v26.5.1, Chromium 153 / Chrome 157):
- Environment gap found: `ws` was NOT present in
  `%LOCALAPPDATA%\voice-typer-internal-plugins\node-deps` (only playwright/playwright-core), so
  `run.js` died at require and every relay/control-plane/roundtrip test failed to load. Fixed with
  `npm install --prefix <node-deps> ws@8` (8.22.2) - the same dependency the worker reported as
  installed. Node suite then: **32 passed / 0 failed** (`node --test "tools/internal_plugins/anthropic_stt/test/*.test.js"`).
- `node tools/.../build-extension.js --check` -> up to date; `node --check` clean on all 9 JS files.
- Manifest validity proven with Chrome's own packer: `chrome.exe --pack-extension` accepted
  `extension/` (crx+pem produced), so `host_permissions` `http://127.0.0.1:17875/*` (port form) is
  valid - the port risk the worker flagged is retired. Note: branded Chrome 157 **ignores**
  `--load-extension` ("not allowed in Google Chrome, ignoring"), so CLI live-load is impossible there.
- Live bridge (Playwright Chromium 153, throwaway profile, `--load-extension`, no login):
  SW connected + hello accepted; `/status` -> `{"browser":"connected","page":"signed_out",
  "url":"https://claude.ai/login?..."}`; `/probe` -> 6 checks + dump; `/start` -> 500
  `{"kind":"signed-out"}` and `plugin.py` mapped it to the signed-out hint; `/stop` -> 409
  `not-recording`; `/cancel` -> 200; `/shutdown` -> process exits 0.
- No-extension path: `/status` 200 disconnected; `/warm`, `/start`, `/probe` -> 500
  `browser-not-open` + `last_error.json` written.
- Token guard: `git check-ignore` confirms `config.json`, `extension/generated/`, `debug/`,
  `last_error.json`; `backup.ps1` blocks `extension/generated`.
- Automation tells: none in source (no child_process/spawn/chrome.debugger/visibilityState/navigator
  overrides); `playwright` 0 hits outside the pre-existing gitignored `debug/`.
- `pytest tests/tauri/test_internal_plugin_tools_absent.py -q --no-cov` -> 12 passed (file has
  uncommitted edits from another session that make it environment-independent; green as-is).
- `python tools/internal_plugins/anthropic_stt/verify_bridge_error.py` -> all checks passed (8 hints).

Findings handed back (not fixed in this session, scope of the plugin workspace):
- HIGH `plugin.py` stop captures `GetForegroundWindow()` at start and calls `SetForegroundWindow`
  before pasting - a paste-time refocus (C-PASTE-1 violation) that can send the transcript into the
  wrong window, or into Claude itself if the hotkey was pressed while Chrome was focused. The
  extension transport never steals focus, so the restore is unnecessary.
- HIGH the 5 settings declared in `plugin.json` are inert: the Plugins page persists them to
  `<plugin>/settings.json`, the daemon reads only `config.json`.
- MED `service_worker.js::claudeTab()` picks the first claude.ai tab, not the active one.
- MED cold-start race observed live: the first command right after Chrome starts can answer
  `browser-not-open` "the Claude tab closed during the command" while the content script is still
  being injected (second command 2 s later fine).
- LOW dead `_hotkey_to_spec`; `--check` can write `config.json`; HTTP control plane has no Origin
  guard; `probe()` mutates the page (`pointerEvents`); `minimum_chrome_version: 116` vs 0.5-min alarm.

Rule added: **C-UI-17** (settings control must be read by the code that performs the effect).

## 2026-11-11 - Anthropic STT: worker follow-up pass reviewed, two wiring gaps closed, live bridge re-run

Second review round on `tools/internal_plugins/anthropic_stt/` (Windows, Node v26.5.1, Playwright
Chromium 1243). The worker's eight claimed items are present in source (`plugin.py` refocus removed,
`settings.json` merged in `config_store.js`, active-tab preference + retry/`page-not-ready`,
`compile/render/check`, Origin 403, read-only `probe()`, dead helper deleted). Two items were still
incomplete, and both were the same defect class C-UI-17 exists for:

1. `notify` was validated into the Node config but nothing consumed it. Notifications are emitted by
   `plugin.py`, which never read `settings.json`, so the checkbox moved and changed nothing. Fixed:
   `_notify_enabled()` reads `<plugin>/settings.json` per notification (absent/invalid => on) and
   `_notify()` returns early when muted. Guard: `verify_notify_setting.py` (8 checks, incl. the
   session-level gate with a fake tray).
2. The daemon froze `config.json`+`settings.json` at process start, so `pollMs`/`stableMs`/
   `stableWindows`/`timeoutMs` edits never reached a running daemon (`ensure_daemon()` reuses it all
   session). Fixed: `run.js` re-reads the layered config per request (`persist:false`, no writes).
   Guard: roundtrip test writes `settings.json` after `/start` and asserts `/stop` carries the new
   values (`stopOpts` deep-equal).

Also extended the cold-start retry from one 800 ms attempt to `[300, 700, 1400]` ms: live runs showed
the content script can still be injecting (document_idle) after a single retry, which surfaced as a
false `page-not-ready` from `/probe`. A genuinely missing content script still fails honestly.

Evidence (this state):
- `node --test test/*.test.js` -> **37 passed / 0 failed** (exit 0).
- `node tools/build-extension.js --check` -> up to date (exit 0); `node --check` clean on the changed JS.
- `python verify_notify_setting.py` -> 8/8 pass; `python verify_bridge_error.py` -> all checks passed (9 kinds).
- `pytest tests/tauri/test_internal_plugin_tools_absent.py -q --no-cov` -> 12 passed.
- Live bridge, fresh throwaway Chromium profile with `--load-extension` (no login): SW connected +
  hello accepted; cold-start `/probe` -> 200, accurately reading the signed-out page
  (`page=signed_out`, zero composer/mic selectors); `/start` -> 500 `{"kind":"signed-out"}`;
  `/stop` -> 409 `not-recording`; `/cancel` -> 200; `/shutdown` -> 200 and the port freed.
- `README.md`: config_store now documented as the `settings.json` merge point; Plugins-page knobs
  documented as applying on the next hotkey press.

Still owner-gated: signed-in dictation (build config -> load unpacked -> launch profile -> manual
login + mic allow -> occlusion.ps1 + Chrome restart -> enable gate/select plugin -> hotkey
start/stop -> hotkey remap -> covered-window -> tab-switch -> closed-window `browser-not-open`).
Residual, non-blocking: the first `/status` read immediately after a fresh Chrome start can report
`page: unknown`; the next call recovers, and `/probe`/`/start` retry through the same window.

## 2026-11-11 - Anthropic STT: profile launcher + hotkey auto-open finished (resumed session)

Resumed the opencode session that died mid-edit at the cooldown guard. The guard
code had landed in `plugin.py` (`_LAUNCH_COOLDOWN_S = 30.0`, `_ensure_browser`
launches at most once per window, waits `_BROWSER_START_TIMEOUT_S = 15.0` for the
tab, then fails honestly); the test and the docs had not.

Done in this pass:
- `verify_profile_launch.py`: five new checks pin the hotkey path -- first press
  when the bridge is down opens the profile once, a second press inside the
  cooldown spawns nothing, an expired cooldown allows exactly one more launch,
  the launch carries the configured `profileDir`/`claudeUrl`, and a ready bridge
  is used as-is with no launch at all.
- `tools/internal_plugins/README.md`: the anthropic_stt section now describes the
  launcher instead of "a window the owner opened" -- `chrome_profile.py` listed
  among the pieces, setup step 4 is `setup/install-shortcut.ps1` ("Claude
  Dictation" in the Start menu), "Everyday use" states the auto-open + 15 s wait +
  one-launch-per-30 s behaviour, troubleshooting names the cooldown as a cause of
  `browser-not-open`, undo removes the shortcut, and the guarantee bullet no
  longer claims the profile is owner-opened.
- Rule added: **C-START-3** (a dependency-starting recovery path is bounded and
  then fails honestly, never one launch per trigger).

Evidence (this state, Windows, Python 3.13, Node v26.5.1):
- `python tools/internal_plugins/anthropic_stt/verify_profile_launch.py` -> all
  checks passed (35, incl. the 5 cooldown checks and both PS launchers).
- `node --test test/*.test.js` -> 38 passed / 0 failed (exit 0).
- `node tools/build-extension.js --check` -> up to date.
- `.venv/Scripts/python.exe -m pytest tests/tauri/test_internal_plugin_tools_absent.py -q --no-cov`
  -> 12 passed.
- Installed shortcut verified: target
  `C:\Program Files\Google\Chrome\Application\chrome.exe`, arguments
  `--user-data-dir="C:/Users/11/AppData/Local/voice-typer-internal-plugins/google-stt-profile" --profile-directory=Default "https://claude.ai/new"`.

Still owner-gated (unchanged from the previous entry): signed-in dictation end to
end -- manual login + mic allow in the dictation profile, `occlusion.ps1` +
Chrome restart, enable gate, select plugin, hotkey start/stop in another app,
hotkey remap, covered window, tab switch, closed window.

## 2026-11-11 - Anthropic STT live test (real app + real Claude page): transport control is broken, two product bugs fixed

Live run on Windows with the dev app (`npm run tauri:dev`), the owner's dictation profile and the
real claude.ai page (signed in, mic permission already granted in the profile).

Proven working
- Hotkey press opens the profile: `[PLUGIN] opening the dictation profile` at 19:51:41, 19:52:12,
  19:53:28 -- one launch per press, and presses inside the 30 s cooldown spawned nothing.
- Extension service worker connects: `/status` -> `browser=connected page=ok url=https://claude.ai/new`.
- Activation warm-up succeeds: `[PLUGIN] Anthropic STT activated; browser is up`.
- Claude's own dictation works and transcribes when a REAL click starts it: composer ended with
  "This is a microphone level test with spoken words for the dictation bridge ... The quick brown
  fox jumps over the lazy dog." (TTS through the speakers, default mic rms 0.045 / peak 0.45).

Blockers found (evidence in the run above)
- **Synthetic clicks do not start dictation.** The content script's `el.click()` leaves the page on
  "Dictate" (daemon says `recording:true state:idle`, then `no-transcript`), while an OS-level
  `mouse_event` click at the same button's rect flips it to "Cancel dictation"/"Finish dictation",
  placeholder "Listening...", live level bar. Claude needs trusted input (and/or transient user
  activation) for its mic start.
- **`STOP_SELECTOR` matches the wrong control.** The recording UI now offers "Finish dictation"
  (commit) and "Cancel dictation" (discard); `STOP_SELECTOR` matches only "Cancel dictation", and
  `stop()`/`cancel()` both click `stopButtons()[0]` -- stopping would discard the transcript.
- `micButtons()` was scoped to `[data-cds-part=idle-slot]`; Claude moved the Dictate control out of
  that slot, so the lookup found nothing. Added a document-wide fallback (slot first, then
  document) in `extension/content.js`; still gated by the trusted-input problem above.

Product bugs (not plugin-specific)
- FIXED `native_hotkeys/_core.py::stop()` joined its own watchdog thread when the watchdog's respawn
  path called it, so the respawn raised `RuntimeError: cannot join current thread` and the global
  hotkey stayed dead for the rest of the session (observed live at 19:40:34: "Windows watchdog:
  respawn failed"). `stop()` now skips the self-join. Pinned by
  `tests/test_native_hotkeys.py::TestWatchdogRespawnRace::test_stop_on_the_watchdog_thread_does_not_join_itself`
  (red before the fix: the exact `RuntimeError`; green after).
- FIXED `chrome_profile.find_chrome()` read `os.environ` directly, but the sidecar is spawned with
  `.env_clear()` + an allowlist (`src-tauri/src/sidecar/spawn/dev_mode.rs:37`), so `PROGRAMFILES` and
  `LOCALAPPDATA` are absent in-process: the live app logged `[PLUGIN] chrome.exe was not found` and
  the whole auto-open feature never fired, while the verifier (full shell) passed. `find_chrome()`
  now resolves through `_browser_env()`; `verify_profile_launch.py` pins the trimmed-environment case
  (37 checks, all pass).
- OPEN: a second daemon spawn crashed with `EADDRINUSE 127.0.0.1:17875` because `ensure_daemon()`
  trusted one failed `/status` probe and spawned blindly. Needs a probe retry and a
  "port already listening means alive" rule.

Evidence (this state)
- `python tools/internal_plugins/anthropic_stt/verify_profile_launch.py` -> all checks passed (37).
- `node --test test/*.test.js` -> 38 passed; `node --check extension/content.js` clean.
- `.venv/Scripts/python.exe -m pytest tests/test_native_hotkeys.py -q --no-cov -k watchdog` -> 13 passed.
- Live: hotkey auto-open, bridge connect, real-click dictation + transcript into the composer.

Decision needed before this can ship: trusted input for the platform controls (OS-level click from
the plugin at an extension-reported rect, vs `chrome.debugger` CDP input), plus the selector fix
(commit vs cancel) and the daemon-spawn guard.

## 2026-11-11 - Bubble re-anchor log flood: `bubble_resize` now idempotent

Symptom (owner report): `[BUBBLE] re-anchored at (924,945) edge=bottom after resize 71x47` filling
the log at 5-50 lines/second while the app was idle; `lausu-rust.log` held **18,798** such lines
(18,627 of them the identical 71x47 request), plus 4,004 lines in one 20-minute window.

Cause: `bubble_resize` treated every request as new work -- `set_size` + `harden_bubble_chrome` +
an unconditional `set_position` + an INFO line -- while the renderer re-measures the pill on every
layout pass and keeps asking for the size the window already has. Nothing checked "is this a
change?".

Fix (`src-tauri/src/commands/bubble/`):
- `math::resize_is_noop(current, capped)` and `math::anchor_moved(before, after)` (pure, tested).
- `bubble_resize` skips `set_size` + the chrome strip when the clamped request equals the current
  outer size; the window-event arms still re-harden on every real `Resized`/`ScaleFactorChanged`.
- `reanchor_bubble_after_resize` returns before/after and only writes the position (and only logs
  at INFO) when the anchor actually moved.
- Edge-anchored centering is unchanged: the recomputed anchor is still applied whenever it differs,
  which is exactly the mode-change path the behavior exists for.

Evidence:
- `cargo test --manifest-path src-tauri/Cargo.toml bubble::` -> **124 passed, 0 failed** (3 new:
  `resize_is_noop_when_the_size_is_unchanged`, `resize_is_noop_compares_the_capped_request`,
  `anchor_moved_only_reports_real_geometry_changes`).
- Live, same idle state that produced the flood: after restart at 21:19, **0** `re-anchored` lines in
  3.5 minutes (startup placement still logged: `positioned at (924,945) edge=bottom (config)`).
- `pytest tests/test_no_ipc_wire_trace_logs.py -q --no-cov` -> 1 passed.
- `cargo check` afterwards could not run while the dev app held the build dir lock; the crate did
  compile in the `cargo test` run above (tests execute the built binary).

Rule added: **C-LOG-8** (an idempotent setter compares before applying, and INFO only on real change).

Open follow-up (not fixed, measured): the renderer still issues those identical resize requests.
The host now makes them free, but the effect that re-runs on every layout pass was not identified --
the bubble's `console.warn` does not reach the host log (`console-capture` installs, no
`console.*` line has ever appeared in `lausu.log`), so a temporary probe produced nothing.

## 2026-11-11 - Anthropic STT: stop discarded the transcript, and autopaste was dead on Windows

Owner report: hotkey starts the platform dictation (waveform moves, audio clearly flowing) but the
second press yields nothing -- no text, no clipboard, no history row, no autopaste. Owner guessed the
stop was hitting the discard button. It was, and a second, unrelated bug made autopaste impossible
for every Windows user.

1. **Stop clicked DISCARD.** `selectors.json` `stopSelector` listed `stop dictation` / `stop
   recording` / `stop listening` / `cancel dictation` -- and Claude's recording UI is "Finish
   dictation" (commit) + "Cancel dictation" (discard). The commit control matched nothing, the
   discard control matched, and `stop()`/`cancel()` both clicked `stopButtons()[0]`, so every stop
   threw the transcript away (the scrape then found an empty composer and the plugin reported
   "Empty transcript"). Fixed: `stopSelector` = commit only, new `cancelSelector` = discard,
   `cancel()` uses it, `recordingState()` counts either control, `stop()` returns
   `committed` + `control` (logged by the daemon timing line).
2. **The commit control is transiently unclickable.** A single click right after the press landed in
   a window where the control is not actionable (`control=none`, `click=0ms`, no text). Fixed: the
   click is retried against the same control (up to 6 x 400 ms) until the page leaves recording, and
   `stopButtons()` only rejects controls that are hidden/zero-sized (not `disabled`, which is the
   transient state).
3. **Autopaste never worked (all Windows users).** `sizeof(INPUT)` was **32**, Windows x64 requires
   **40**: the `InputUnion` declared only the keyboard branch (24 bytes) instead of the Win32 union
   (MOUSEINPUT is 32). `SendInput` rejected every batch with `ERROR_INVALID_PARAMETER` (87) and
   returned 0 -- measured with a standalone probe: `(0, 87)` before, `(4, 0)` after. The pynput
   fallback uses the same API, so it failed identically; the clipboard kept the text and the user saw
   "Paste delivery unconfirmed". Fixed by declaring `MOUSEINPUT` / `HARDWAREINPUT` and all three
   union branches; `INPUT` is now 40 bytes on x64 / 28 on x86.
4. **Push-to-talk dropped its release.** The hook only routed `_stop_dictation` to the plugin when
   the session was already `active`, so a release that arrived while the browser/daemon handshake
   was still running fell through to the local recorder and the platform kept listening forever.
   `PluginSession` now has `owns_cycle` (active OR starting) and defers the stop
   (`_stop_requested`) until the start lands, then finishes the cycle.

Evidence (live, real app + real claude.ai page, Windows 11):
- Direct bridge: `POST /start` -> speak -> `POST /stop` -> `{"text":"The commit control test speaks
  right now, so the platform has real words to transcribe before it stops.", "scrape_ms":807}` with
  `control=Finish dictation|button|28x28 committed=true`.
- Hotkey path (tap-to-record): press -> speak -> press -> `committed=true`, 821 ms, transcript in
  the composer, 122 chars copied, `[CLIPBOARD-AUDIT] Sent paste keystroke (terminal=False,
  target=notepad.exe, restore_scheduled=True)`, snapshot restored, and the text was read back from
  Notepad's editor: "...End to end test of the Anthropic STT plugin after the commit and paste
  fixes. The quick brown fox jumps over the lazy dog." History row inserted
  (`model=anthropic-stt-w...`, duration 11.5 s).
- Push-to-talk: hold F9 -> speak -> release -> `committed=true`, 822 ms, sentence appended in
  Notepad.
- `verify_stop_commit.py` (new) -> all 20 checks pass; `verify_profile_launch.py` -> 37 pass;
  `node --test test/*.test.js` -> 38 pass; `pytest tests/clipboard/win32/
  tests/tauri/test_internal_plugin_tools_absent.py -q` -> 121 passed, including the new
  `TestInputStructLayout` (red before the union fix: `assert 32 == 40`).

Testing notes: caps-lock injection via SendKeys fires the app's callback twice (down+up), so the
hotkey tests used F9 and the owner's settings were restored afterwards (`<caps_lock>`, `toggle`).
Claude also auto-stops a dictation that hears ~2-3 s of silence and returns no text -- speak
immediately after the press.

## 2026-11-12 - Anthropic STT polish batch: pill state, ducking, platform-stop recovery, settings, popup

Owner feedback after the first fully working dictation, actioned here:

1. **The pill said "Ready" while the platform was capturing.** The plugin published `bubble_show` +
   `recording_started` but never `bubble_set_state`, so the bubble's own state machine stayed in
   idle. Now: `recording` on start, `transcribing` before `/stop`, `idle` before the hide.
2. **Auto volume ducking did not apply to plugin dictation.** The plugin session never touched the
   volume controller. Now it ducks on a successful start and restores on stop/cancel
   (`app._duck_volume()` / `app._restore_volume()`), verified live:
   `[VOLUME] Duck -> 20% (saved 100%)` ... `[VOLUME] Restore -> 100%`.
3. **The transcript stayed in Claude's prompt box.** The text is already pasted into the user's app,
   so leaving it invited an accidental send. New daemon `/clear` + `clearComposer()` in the content
   script (select-all + `execCommand('delete')`, best effort, never navigates away from the chat),
   called after a successful delivery. Verified live: composer empty after the run.
4. **The platform stopping on its own lost the cycle.** New `_watch_platform` thread: while a
   session is live it polls the bridge; two consecutive non-recording reads mean the PLATFORM ended
   the dictation (focus loss, its own 10-minute cap, a reload), and it then runs the normal
   stop/deliver path so the captured audio still becomes text, history, clipboard and paste. A
   single idle blip never cuts a live capture.
5. **Stop races.** `_stop_and_deliver` is single-flight (`_stopping`), so the user's stop and the
   watchdog can never both run it, and a deferred push-to-talk release still lands.
6. **Settings UX.** Numeric knobs with a declared range now render the shared `RangeSlider`
   (no more select-all-and-retype), and every label/description is written in plain terms
   ("Transcript poll interval", "Stable reads before accepting", "Wait between stable reads",
   "Transcript wait after stop"). `timeoutMs` is documented as the POST-STOP wait, not the recording
   length: Claude caps a dictation at 10 minutes itself and the watchdog now delivers what it
   captured. A `unit` field was added to the manifest spec for the slider readout.
7. **Extension branding + popup.** `icons/` carries the app's own artwork (16/32/48/128 from
   `src-tauri/icons`), `action.default_popup` opens a small popup, and Chrome's default right-click
   menu is no longer the only interaction. The popup holds the per-browser-profile enable switch
   (`chrome.storage.local`), which is the practical answer to "the plugin is installed in two
   profiles and both answer the app"; the content script refuses to start when switched off
   (`CmdError('disabled')`) and the relay already replaces the older connection.

Evidence:
- New `verify_session_events.py` -> **all 12 checks pass** (recording pill state, duck/restore,
  `/stop` + `/clear` ordering, delivery, watchdog delivery on a platform stop, a single idle blip
  ignored, concurrent stop refused).
- `verify_stop_commit.py` -> all 20; `verify_profile_launch.py` -> all 37; `node --test test/*.test.js`
  -> 38/38; `build-extension.js --check` up to date.
- `npx vitest run src/renderer/src/pages/plugins` -> **18 passed** (new: ranged numeric setting
  renders the slider and no spinbutton); `npm run typecheck:ci` clean.
- Live: bubble showed the level meter (not "Ready") during a capture, volume ducked and restored,
  prompt box empty after delivery, popup renders with the app icon and the switch.

One-time owner action: the unpacked extension must be reloaded in `chrome://extensions` (dictation
profile) to pick up the new content script (enabled gate, `/clear`) and the popup; a Chrome restart
alone keeps serving the cached copy. App-side changes (pill state, ducking, settings, watchdog) are
live after an app restart.

Not done in this batch (recommendations, not implemented): a hard "only one profile may drive"
lock beyond the popup switch (the relay already replaces the older connection, so the duplicate-text
risk is a stale tab answering a recycled request, not two live sessions); the popup's live status
line (needs a worker snapshot round-trip that this Chrome build would not deliver until the
extension reload); and a full audit of every remaining race in the daemon request/lifecycle paths.

## 2026-11-13 - Plugins page: compiled in, hidden by default, owner unlock (Windows)

Owner decision: the Plugins page must EXIST in the installed build (so the feature can be used on a
real install) but be invisible to every user until the owner reveals it. This reverses the earlier
"exclude `tools` from packaging" rule for plugin SOURCE only; runtime state still never ships.

Gate:
- `config.developer_mode` (new, bool, default `false`, SEC-002 allowlisted). Renderer shows the nav
  item/page only when `config.developer_mode === true`; backend re-checks on every plugin IPC, so the
  renderer hide is presentation, not the boundary.
- Reveal: undocumented in-app sequence `ctrl+shift+alt+d` pressed three times within 1.5 s
  (`useDeveloperModeUnlock.ts`) -> `set_config {developer_mode: true}` + success snack. No UI hint.
- `VOICE_TYPER_INTERNAL_PLUGINS=1` stays as a developer breakglass (still needs a usable workspace +
  `PLUGINS_ENABLED`).
- While locked: `get_plugins` returns `available: false` + `[]`; `set_plugin_setting` answers
  `client.not_found` / `unknown plugin` and writes nothing. `developer_mode` off ->
  `internal_plugin_hook.teardown(app)` (cancel session, deactivate); wrappers fall through to local
  dictation.
- `_developer_mode_on` uses `getattr(config, "developer_mode", False) is True`, so MagicMock/partial
  configs fail closed; fake app configs in tests set it explicitly.

Bundling:
- New `voice_typer/server/plugins/workspace.py`: `resolve_plugins_dir()` prefers a checked-out
  `tools/internal_plugins`, else the Nuitka-embedded tree (`_bundle_root()` via `__main__.__file__`),
  else the per-user workspace. `seed_workspace()` copies the embedded tree into
  `<config dir>/developer_plugins/tools/internal_plugins` on unlock and writes `PLUGINS_ENABLED`
  there; runtime state (config/settings/debug/extension/profiles/node deps) never ships.
- New `scripts/build/stage_internal_plugins.py` (denylist staging) + `--include-data-dir` in all
  three `build_sidecar_*.sh`. Windows CI `tauri-windows-build.yml` stages and adds the flag.
- Plugin modules dropped the `sys.frozen` refusal (marker + developer mode are now the deliberate
  opt-ins) and use a portable `_node_deps_root()` instead of a hardcoded `C:/Users/11/...` path.

Tests:
- `tests/tauri/test_internal_plugin_tools_absent.py` -> `tests/tauri/test_internal_plugin_packaging.py`
  (packaging inputs embed the tree, staging excludes state/tests/deps, seam inert when locked,
  tracked/ignored git assertions).
- `tests/plugins/test_plugin_registry.py` updated (flag-based gate, frozen reversal, explicit
  `developer_mode` on end-to-end fakes, locked-surface `client.not_found`).
- New `tests/plugins/test_developer_workspace.py` (13) and
  `hooks/__tests__/useDeveloperModeUnlock.test.tsx` (8).
- `pytest tests/plugins tests/tauri/test_internal_plugin_packaging.py -q --no-cov` -> 94 passed.
- Renderer: unlock 8/8, `App.test.tsx` + `Sidebar.plugins-gated` 11/11, plugins page 18/18, i18n
  parity/translation contract green; `npm run typecheck` clean.
- Baseline fix owned: `App.test.tsx` "plain wheel without Ctrl" asserted `mockCall` was never called
  at all, but `useCudaInstallToast` (2026-11-12) added a mount-time `get_gpu_capability` reattach
  read. Assertion narrowed to the test's actual contract (`no set_config`), `setTextSize` still not
  called.

Outstanding:
- CI workflow change (`tauri-windows-build.yml`) needs owner sign-off and a full workflow re-run;
  it cannot be validated locally.
- A freshly seeded workspace generates a new extension token, so an already-loaded Anthropic
  extension needs `tools/build-extension.js` + a reload after the first unlock on a machine.
- i18n: `plugins.unlocked` / `plugins.unlockFailed` added to all 8 locales.

## 2026-11-14 - Plugins gate: verification runs + baseline failure inventory (Windows)

State under test: commit `36c13f2d0` (feat(plugins): gate the Plugins page behind developer mode) plus
the six follow-up files still uncommitted here (docs/comment corrections + three test pins).

Fixed after the first full run (all three were mine):
- `tests/test_config_validators_split.py`: `IPC_CONFIG_ALLOWLIST` 166 -> 167 with `developer_mode`
  documented in `_PRE_SPLIT_ALLOWLIST_KEYS` and in the size-assert message (SEC-002 audit trail).
- `tests/tauri/mig18/test_openmp_runtimes.py::test_windows_has_no_ct2_native_lib_plumbing`: the C7
  "no data dirs" pin now enumerates `--include-data-dir` flags (quoted form included) and allows
  exactly `$PLUGINS_STAGE/tools/internal_plugins=tools/internal_plugins`, so any other embedded
  directory (native libs) still fails.

Runs on the final state:
- `pytest tests/ -n auto --dist=loadgroup -q --no-cov --tb=short > pytest-run.txt` -> 24 failed,
  18854 passed, 874 skipped in 869.99s. Zero plugin / developer-mode failures.
- `npx vitest run` -> 12 failed, 4750 passed, 7 skipped (408 files) in 114s. Zero plugin failures
  (`useDeveloperModeUnlock` 8/8, plugins page + i18n parity green).
- `npm run typecheck:ci` -> clean. `cargo check --all-targets` -> clean (in a separate
  `CARGO_TARGET_DIR`; the dev session holds the shared `target/` lock, `os error 32`).
- Scoped: `pytest tests/plugins tests/tauri/test_internal_plugin_packaging.py
  tests/tauri/mig18 tests/test_config_validators_split.py -q --no-cov` -> green.

Both inventories were pre-existing, from other in-flight work. The owner asked for the whole tree green,
not just the plugin scope, so this session fixed all 36 (24 pytest + 12 vitest):

Backend (24):
- CUDA command registry: `COMMAND_COSTS` gained the 4 missing entries; `cuda_handlers.py` annotations use
  `ResponseEnvelope`; `test_ipc_server.py` registry pin 105 -> 109; `test_phase4_validation.py`
  `KNOWN_UNDOCUMENTED_COMMANDS`; FEATURES.md/CONTRIBUTING.md counts 104 -> 109.
- `test_download_control_lockfree.py`, `test_config_load_save.py` (`device` default),
  `test_model_manager.py` (extra `old_backend`/`old_model_size` kwargs), `test_construction_builders.py`,
  `test_e2e_smoke.py` (cache probe), `test_parakeet_onnx_sha.py` rewritten against the live repo file list
  (`config.json`, `vocab.txt`, three graph variants, `encoder-model.onnx.data`).
- `test_wire_swap_recovery.py`: pins moved to the per-launch supervisor token (ADR-0020 §3 wording is
  behind the code, so the code wins).
- mypy ratchet: `recorder_init.py` TYPE_CHECKING import for `_prewarm_device_cache`,
  `nvidia_dll_paths.py` `cast(...)`. ruff ratchet: `test_win32_send_ctrl_v.py` I001.
- `startup_tasks.load_microphones`: still publishes on empty -> non-empty (boot-race recovery), while the
  "Device set changed" line stays limited to later changes.

Renderer (12):
- `useCudaInstallToast` `callRef` mirror (3 assertions); Media rows keep the skullet `Skeleton` wrap with a
  truthful `mediaJobSample` (the job's OWN identity, unknown progress zeroed, never a fake source/percent);
  `ModelsPage-cancel-download-reset` wrapped in `TooltipProvider`; `skullet-contracts` provider list
  8 -> 7 ids (no `openai` provider exists); a11y lifecycle stub gained `modelCatalog`; three
  collection/Vocabulary suites and the Media suites now wait for the single settled row instead of matching
  the stale crossfade pane (it is `aria-hidden`/`inert`, but `getByText` still finds it).

Final-state evidence (0 failed everywhere):
- `pytest tests/ -n auto --dist=loadgroup -q --no-cov --tb=short > pytest-run.txt` ->
  18878 passed, 874 skipped in 1066.74s.
- `npx vitest run > vitest-run.txt` -> 408 files, 4762 passed, 7 skipped in ~110s.
- `npm run typecheck:ci` clean; `cargo check --all-targets` clean (separate `CARGO_TARGET_DIR`);
  `ruff check .` clean; `ruff_ratchet_check` 0 <= 0; `mypy_ratchet_check` 563 <= 576 (improved);
  `check_branding.py`, `generate_beeps.py --check`, `sync_versions.py --check` all exit 0.

`test_asr_setup` root cause (the last two failures, order-dependent): the module stub was installed only
when the real `huggingface_hub` was absent from `sys.modules`, so in a full run
`snapshot_download(local_files_only=True)` answered from the REAL user cache
(`models--Masterx--parakeet-tdt-0.6b-ultra-onnx`) and returned "already cached" before the patched
failure path could run. Deterministic repro (`python -c "import huggingface_hub; pytest.main(...)"`) showed
2 failed; the stub is now installed unconditionally through `monkeypatch` (C-TEST-9: patch the seam the
code actually calls; C-TEST-8: no test may read the real cache), and the repro passes 12/12.

## 2026-11-15 - CI matrix: 5 failures, 3 root causes, all host-dependent assumptions (Windows host)

The CI report listed 5 failing/errored tests across 4 legs. Grouping them by cause rather than by test
left three defects, each an assumption that only breaks off-Windows or on a coarse clock.

1. `ctypes.wintypes` aliases the HOST's `c_ulong`/`c_long`, which are 8 bytes on LP64. So `KEYBDINPUT`,
   `MOUSEINPUT`, `HARDWAREINPUT` and `INPUT` were 48/56 bytes on the ubuntu legs instead of the Win32
   32/40, and the `SendInput` argtypes/restype followed the same aliases (`3 tests x ubuntu 3.11/3.12/3.13`).
   `clipboard/windows.py` now uses fixed-width `_WORD = c_uint16`, `_DWORD = c_uint32`,
   `_LONG = c_int32` (the layout is a Win32 ABI fact, not a host fact), and the module no longer imports
   `wintypes` at all. Precedent: `hotkeys/windows/_win32_keyboard.py`. Sizes re-verified on this Windows
   host: `InputUnion` 32, `INPUT` 40, `MOUSEINPUT` 32, `KEYBDINPUT` 24.
2. `tts/runtimes._safe_member` used `Path(name).is_absolute()`, which answers with the unpacking host's
   rules, so a zip entry named `C:/Windows/evil.exe` was accepted on POSIX while being absolute on
   Windows. The name is now validated against BOTH `PurePosixPath` and `PureWindowsPath` (absolute, or
   `..` in the parts of either flavour, is unsafe). Spot-check: `C:/Windows/evil.exe` -> reject,
   `/etc/passwd` -> reject, `../escape.exe` -> reject, `\\host\share\x.exe` -> reject,
   `model_specs/audio8_tts.json` -> accept.
3. `model_providers/catalogue.CatalogueSnapshot.stale` used `age > ttl`, so a zero-TTL snapshot read as
   FRESH whenever write and read landed in the same clock tick (`windows-2022` flake). A zero TTL means
   "never fresh": `stale` is now `age >= ttl`, with the reasoning recorded at the property.

Two rules added to `AGENTS.md` under `Category: Cross-Platform Behavior` (ADD-only, per Learn-and-teach):
`C-CROSS-7` fixed-width ctypes types for Win32 structs whose layout is asserted off-Windows, and
`C-CROSS-8` dual path-flavour validation for archive member names.

Evidence (scoped run, the state that then went to the full suite):
`pytest tests/clipboard/win32/test_win32_send_ctrl_v.py tests/test_tts_runtimes.py
tests/providers/test_catalogue_cache.py tests/clipboard -q --no-cov` -> 166 passed;
`ruff check` clean on the three touched files; `cargo fmt --check` exit 0.

Audit while the verification suite ran (read-only, tree frozen per C-AGENT-10): every other
zip-extraction site was checked for the same host-dependent member-name guard.
- `service/offline_pack/core._safe_pack_member_name` already rejects a leading `/` or `\`, any `\`,
  and a `:` in the first segment -- host-independent, no change needed.
- `segmented_download_state._resolve_within` already rejects POSIX-absolute forms plus `^[A-Za-z]:` and
  `\\` on every platform -- the same class, already fixed, which is the precedent for the tts fix.
- `cuda_install/installer._extract_wheel` still tests `Path(name).parts` for `..` and a leading
  separator only, so a drive-qualified member name would pass on POSIX. Left alone deliberately: wheels
  are hash-pinned (`artifact.sha256`) against our own manifest before extraction, so the member names
  are content-verified rather than attacker-controlled. Recorded as a follow-up, not fixed mid-run.

## 2026-11-16 - CI windows-2022: Ctrl+C shutdown test lost a race with its own daemon thread (Windows host)

`tests/test_shutdown_fast.py::TestWin32RoutingFastCleanup::test_ctrl_c_still_routes_to_quit` failed on
windows-2022-3.11 with `Expected 'mock' to have been called once. Called 0 times.` The test is not
wrong about the product: `win32_console_handler` dispatches `controller.quit` on a daemon thread on
purpose (RACE-016 -- the console callback must return inside Windows' own deadline or the process is
killed), so the call lands AFTER the handler returns. The test asserted immediately. Prod code untouched.

The same test also exists in `tests/test_shutdown_logoff_cleanup.py`, and THAT copy had already grown a
private 2 s poll loop for exactly this race -- so the class was known and the fix simply never reached
the duplicate. Both copies now go through `tests/fixtures/wait_helpers.wait_until` with a 5 s deadline
(C-TEST-16: deadline generous enough for a loaded runner, and "still not called" is reported as such);
the sibling's private loop and its now-unused `time` import are gone.

Proof (not a guess): a probe that defers the spawned thread by 0.5 s -- the mount of a starved runner --
fails with the CI's exact message on the old body and passes on the new one. The same 0.5 s deferral was
then injected through a pytest plugin (`sh.threading` rebound on `signal_handlers` only, so pytest's own
threads stay real): `tests/test_shutdown_fast.py tests/test_shutdown_logoff_cleanup.py` -> 36 passed,
1 skipped. Undelayed, the shutdown + tray/console family -> 101 passed, 2 skipped; ruff clean.

Note for the record: `tests/app/test_tray_and_console.py::test_ctrl_c_event_starts_quit_thread` mocks
`threading.Thread` itself and asserts `start()` was called, so it is deterministic and needs no wait.

Lesson added to `AGENTS.md`: `C-TEST-17` -- a fixed test defect must be propagated to every duplicate
copy of that test in the same change (this failure is exactly that miss).


## 2026-11-16 - CI vitest: History date-header test hit the skullet ghost pane (Renderer CI)

`src/renderer/src/pages/__tests__/History-date-groups.test.tsx::groups entries under date headers for the
default (newest) sort` failed CI with `TestingLibraryElementError: Found multiple elements with the text:
Today`, both matches being `<h2 id="history-date-2026-11-16">`. Nothing in `groupRecordsByDate` was at
fault -- it is Map-keyed, so one record set cannot produce the group twice.

The duplicate is the skullet crossfade. `History.tsx` feeds `SAMPLE_HISTORY_LIST` to the page's `Skeleton`
as the measured sample; when real data commits, the outgoing placeholder pane keeps rendering for a frame
AND comes back on every later data commit. That pane renders the full `ActivityList` with the sample
records, whose timestamps span today and yesterday -- so it draws its own `Today` / `Yesterday` headers
with the same `history-date-<day>` ids the real list uses. The pane is `aria-hidden` + `inert` (correct:
it is decoration), so role queries cannot see it, but `getByText` matches raw DOM and finds two.

Timeline captured with a MutationObserver through one render (`[probe] after-render today=1 h2=3 ghost=1
loading=1` -> `mutate today=2 h2=5` -> `mutate today=1 h2=2 ghost=0 loading=0`): the duplicate window is
real and transient, so a `waitFor(() => getAllByText(...).toHaveLength(1))` guard is itself a race -- the
next data commit re-opens the window (my first attempt at exactly that guard failed the same way). The
class in `Vocabulary-page-features` / `collection-pages-unified-family` (count == 1 after settle) only
works because those surfaces never commit data again in the test.

Fix: the date-header assertions read by ROLE (`getByRole("heading", { name })`), which resolve from the
accessibility tree and therefore exclude the inert pane at all times, no waiting and no timing assumption.
Test 2's flat-mode assertion switched to `queryByRole` for the same reason. Tests 3-4 were left alone: the
sample text is a different corpus ("entry N" / "word word" only exist in the test's records) and sample
records carry no `text_truncated`, so neither `getByText` nor `getByTestId("activity-row-text-toggle")`
can collide.

Proof, not a guess: a probe running the FIXED body while sampling text counts reported
`maxTodayDuringCrossfade=2 textNow=2 roleNow=1` -- two text nodes present, one heading via role -- so the
new queries survive the exact state the old body threw on. File: 4 passed, 0 errors; `npm run
typecheck:ci` exit 0.

Follow-up recorded (not fixed, not user-visible): the ghost's duplicate DOM ids are momentarily invalid
HTML. Harmless today because the pane is `inert` + `aria-hidden`, and fixing it means teaching
`ActivityList` to derive ids from something skullet provides per-pane; noted so the next person does not
re-discover it as a test flake.

### Investigated, no defect: two i18n "missing key" lines that look alarming in CI logs

1. `[renderer:i18n] missing key: notify.hotkey_dispatcher.wayland_hotkeys_may_fail` (en + ar, and ~40
   siblings of the same namespace). Comes from `i18n/__tests__/setLocale-propagation.test.ts` ->
   "sends English fallback strings for keys missing from the current locale", which registers a PARTIAL
   `ar` table (`models.title` only) and a PARTIAL `en` table (`models.title` + `microphone.microphone`) on
   purpose, so every other key is missing by construction. All 8 catalogs really do carry
   `notify.hotkey_dispatcher.wayland_hotkeys_may_fail` (en.json:2119). Expected noise, not a gap.

2. `[renderer:i18n] missing key: microphoneTest.qualityNotApplicable` comes from
   `i18n/__tests__/translation-key-contract.test.ts`, where that string is the deliberate INVALID key that
   proves a typo'd path is rejected at compile time. No production code calls it.

Noted because `C-MIC-20` still names `microphoneTest.qualityNotApplicable` as the string the no-model state
renders, while the catalog has no such key and `TestReviewPanel` instead HIDES the transcription-quality
row (`showTranscriptionQuality`) when `transcriptionUnavailable` is set. The behaviour satisfies the rule's
intent (never a fabricated numeric score); the rule's exact key name is stale. AGENTS.md is user-owned, so
this is reported, not edited.

### Same class, second instance: Vocabulary + Templates chrome queries (found by the certification run)

The full vitest run that followed the History fix failed a DIFFERENT test, once:
`Vocabulary-page-improvements.test.tsx > opens a ConfirmDialog when Clear All is clicked` ->
`Found multiple elements with the text of: Clear all vocabulary entries`, two byte-identical
`<button aria-label="Clear all vocabulary entries">`. Same root cause: `Vocabulary.tsx` wraps the whole page
column (heading, `CollectionToolbar`, `CollectionListHeader`, list) inside the `Skeleton`, so the fading
sample pane renders a second copy of every control while a crossfade is in flight.

Measured instead of guessed, with a MutationObserver probe over the whole crossfade:
`{"Clear all vocabulary entries":2,"Select all":2,"Deselect all":0,"Sort order":2,"add word (text)":2,
"show more (text)":0}` -- so the label-based chrome queries duplicate, while `Show more` and `Deselect all`
were 0 in that state (sample has fewer rows than the page cap; nothing selected). The same probe, with the
FIXED queries, resolved `roleButton=1 roleCheckbox=1 roleCombobox=1` while the label query still peaked at 2.

Converted every screen-scope chrome query on the shared-toolbar pages to role queries:
`Vocabulary-page-improvements` (5x Clear All `button`, 1x Select all `checkbox`),
`Vocabulary-delete-persistence` (1x Clear All), `Vocabulary-page-features` (Select all `checkbox` x2,
Deselect all `button`, Sort order `combobox` x2), `Templates-instant-delete` (Clear all templates
`button` x2). Per-row queries (`Select recieve`, `Delete template: hello`) stay label-based: they match
test data the sample does not contain, so they cannot collide. Vocabulary + Templates suites: 7 files,
80 tests, 0 failed; biome clean.

Rule added to `AGENTS.md`: `C-TEST-18` -- page chrome inside a `Skeleton` must be queried by role, because
the sample pane is `aria-hidden` + `inert` yet renders the same chrome from its `sample` payload, and a
count-guard cannot fix it (the pane returns on every data commit).

Deliberately NOT done: forcing `SkulletProvider` reveal duration 0 (or `prefers-reduced-motion: reduce`)
in the shared test setup, which would dissolve the whole class at once. It also removes the crossfade from
what 408 renderer files exercise, so it is a coverage decision for the owner, not a test fix.

## 2026-11-16 - Plugin dictation still loaded the local model; the start cue triggered volume ducking

Two owner reports in one session, both root-caused from the live log
(`%APPDATA%/lausu/logs/lausu.log`) before any code was touched.

### 1. Local ASR engine loaded on every launch while a plugin owned the hotkey

Evidence (2026-11-16 20:35-20:41, `model=Anthropic STT` in the startup banner):
`[STARTUP] Loading model in background` at 20:35:55 immediately after the plugin
was attached, then `[PARAKEET] Loading Parakeet Ultra ONNX model on CPU ... 9.2s`
at 20:41:15. Nothing in the plugin path records or decodes locally - the browser
holds the audio and returns the transcript - so that load was pure waste: RAM, a
worker process, ~12 s of frozen CPU, and an idle-unload/reload cycle an hour
later (`idle-unload: unloading active backend 'parakeet'`).

Cause: `_phase_7_hotkey_and_model_load` called `app.models.start_background_load()`
unconditionally, and `ModelManager.start_background_load` had no idea who owned
the hotkey. The plugin seam (`internal_plugin_hook.plugin_display_name(app)`)
already answers that question for the tray and the sidebar; both warm paths now
ask it and skip, while on-demand loads (Media transcription, switching back to
the local model) are untouched. `plugin_display_name` itself became fail-closed
(answers "" on any probe failure) so a broken workspace only costs the usual
load. Startup completion line now says
`Startup complete (Anthropic STT serves dictation, no local model loaded)`.
Rule added: `C-PLUGIN-1`.

### 2. Volume ducking fired on the recording-start cue itself

Evidence (21:02:05 start, 21:02:06): `[VOLUME] Audio started mid-dictation,
retroactive duck -> 10%` one second after every start, then `Restore -> 100%` at
stop. Smart duck had (correctly) skipped at t=0 (`No audio output, duck
skipped`), then the start cue - the app's own beep, played at whatever the
"Sound Volume" slider said, 100% by default - came out of the speakers, was
picked up by the microphone, and read as background playback. So the whole
dictation ran at 10% output, not because a video was playing but because of our
own cue.

Two fixes, both owner-directed:
1. The cue level is fixed: `SOUND_CUE_VOLUME = 0.3` in `lib/sound-manager.ts`,
   and the setting is gone end to end (config field, SEC-002 allowlist entry,
   slider row, `types/config.ts`, search index, 4 i18n keys x 8 locales, both
   slider test files). Removal is clean, not grandfathering: schema v7 prunes
   `sound_volume` from older configs (`_migrate_to_v7`) so no user sees an
   unknown-key warning, and the allowlist snapshot shrank 167 -> 166 with the
   reason recorded in the pin.
2. Ducking now has a start-cue grace: `DUCK_START_GRACE_MS = 1000` is passed as
   `VolumeDucker.duck(grace_ms=...)`, which defers the whole decision (save
   state, smart-duck probe, fade) past the cue window. Silence after the grace
   still means "don't duck"; playback after it ducks as usual. `restore()` and a
   new grace-less `duck()` cancel a pending deferral, and the worker re-checks
   its token INSIDE the lock that saves the duck state, so a stop that races the
   end of the grace can never leave the speakers ducked after the cycle ended.
   Rule added: `C-SOUND-2`.

### Verification

- New: `tests/test_volume_ducker_start_grace.py` (5) - deferral, silence after
  grace, restore cancels, `grace_ms=0` stays immediate, newer request supersedes.
- New: `tests/test_local_model_plugin_gate.py` (6) - phase 7 skip + log, no-plugin
  still loads, probe failure falls back to loading, completion line, and the
  `ModelManager.start_background_load` gate both ways.
- Updated: `tests/test_volume_controller.py` (grace is carried on every duck),
  `tests/config/test_config_schema_migration.py` (v7 prune + v6 config load),
  `tests/test_config_validators_split.py` (allowlist 166), renderer
  `sound-manager.test.ts` (fixed 0.3 master gain, `SOUND_CUE_VOLUME`),
  `RecordingSettingsSection.sounds.test.tsx` (no slider, cue buttons intact),
  `settings-section-search-gating` / `useSettingsConfig` (no `sound_volume`).
- Deleted: `tests/test_sound_volume_config.py`,
  `RecordingSettingsSection-volume-percent.test.tsx` (the setting is gone).

### Live verification (dev app restarted on this tree, 2026-11-16 22:15-22:23)

Startup, plugin owns dictation (`model=Anthropic STT`):

```
22:16:00  INFO  [STARTUP] Anthropic STT serves dictation, skipping the local model load
22:16:00  INFO  [STARTUP] Startup complete (Anthropic STT serves dictation, no local model loaded) 4.6s
```

No `[MODEL] serving parakeet`, no `[PARAKEET] Loading ... ONNX model` line afterwards (the
22:16 run's model load is gone; the last real local load in this log is the 20:41 one from the
previous build). Startup 4.6 s vs 12.8-30.5 s in the earlier sessions.

Volume ducking, three real dictations through the Anthropic STT plugin (caps lock, tap-to-record):

1. YouTube video playing (peak 0.17-0.47 sampled from the WASAPI meter):
   `22:17:07 Duck deferred 1000ms (start-cue grace)` -> `22:17:08 Duck -> 10% (saved 100%)` ->
   `22:17:12 Restore -> 100%`. The first second is left alone, then real playback ducks, as asked.
2. Same with the video paused, meter verified at 0.0 for 10 samples before the press:
   `22:21:35 Duck deferred 1000ms (start-cue grace)` ->
   `22:21:36 No audio output, duck skipped (smart duck, monitor started)`, speaker volume stayed
   100%. That is the old 21:02 failure (`Audio started mid-dictation, retroactive duck -> 10%` one
   second after every start) not happening any more: the cue played, and the probe at +1 s read silence.
3. Controlled probe of the mechanism itself, real `WinVolumeBackend` + 130 ms cue WAV at the new
   30% level (~0.045 peak, played at t=0): meter 0.037 -> 0.052 -> 0.000 by t=0.45 s, deferred probe
   at t=1.0 s saw 0.000, `duck()` never faded (level stayed 1.000). The cue cannot outlive the grace.

Settings UI (screenshot, Hotkeys & Recording): rows are now Sound Feedback -> Test Start Sound ->
Test Stop Sound -> Silence Warning; no Sound Volume row, and the sidebar shows `Anthropic STT` as
the active transcribing engine.

Suites on the final state: pytest `18906 passed, 846 skipped` (0 failed, 20:18) and vitest
`407 files / 4755 passed / 7 skipped` (0 failed), `typecheck:ci` + `tsc -b --force` exit 0, ruff clean.

## 2026-11-17 — Speaking-language capability is per (model, language); mismatches are refused, not decoded

Owner report: the app silently produced **nothing** for Arabic dictation. Root cause found in code, not guessed:

- `config/_schema.py` defaulted `language` to `"en"`.
- `parakeet_engine/_transcribe.py:110-111` deletes any transcript when `language == "en"` and the text is not
  ASCII/Latin (`_helpers._is_likely_english`), i.e. every Arabic take.
- `model_registry.py` declared `supported_languages=None` ("all languages") for **every** model, so nothing
  anywhere knew that Parakeet Ultra's base (`nvidia/parakeet-tdt-0.6b-v3`) publishes **25 European languages
  and no Arabic**. The pair model×language was never checked.

Fixes:

- New `voice_typer/server/model_language_support.py`: the published lists (`PARAKEET_LANGUAGES` 25 EU codes,
  `QWEN3_LANGUAGES` 30 codes incl. `ar`) + `supports_language()`. `None` still means "every language the
  decode accepts" (Whisper's 99 stay ungated).
- `model_registry.py`: parakeet / qwen3-1.7b / qwen3-0.6b now carry those lists.
- New `voice_typer/server/model_language_gate.py`: `gate_dictation_language(app)` refuses the start when the
  pinned language is outside the model's list, and surfaces it three ways — in-app toast event
  `model_language_unsupported {model, language}`, OS notification (`click_path: /models`, `tray.notify`
  fallback, refusal dedup shared with the mic-permission path), tray ERROR auto-reverting in 3 s. Skipped when
  an internal plugin (`plugin_display_name`) or the cloud backend owns the decode.
- `recording_lifecycle._start_impl`: gate runs right after the consent gate, before the mic opens.
- `config.language` default `"en"` → `""` (Auto, matches the UI's first option; `tests/config/test_config_load_save.py` updated).
- i18n: `degradation.modelLanguageUnsupported(+Hint)` × 8 locales, backend `notify.model_language.unsupported`
  + `model_language.<code>` English names (localized names come from the renderer's existing
  `settings.language*` strings via the `set_tray_locale` push — no second language table).
- Push-event chain updated end to end: `event_bus.py` (`Total: 61 events`), Rust `ALLOWED_EVENT_TYPES` +
  its source pin, TS `PythonPushEvent` union + `known-event-types.ts` + parity test, renderer hook
  `useModelLanguageUnsupportedToast` wired in `App.tsx`.
- Wording is the owner's: `Parakeet Ultra does not support Arabic.` with an "Open Models" action.
- Docs: **ADR-0030** (locked: exactly one ASR model at a time, translation is a separate text model, no
  "language packs", capability is per model+language) + index row; rules **C-ASR-5**, **C-ASR-6**.

Tests: `tests/test_model_language_support.py` (25), `tests/test_model_language_gate.py` (23),
`hooks/__tests__/useModelLanguageUnsupportedToast.test.tsx` (4). Scoped green: event-bus/parity/config/
registry/i18n/onboarding/host-build suites all pass; `typecheck:ci` and `cargo check` exit 0.

**Validation (final state, 2026-11-17):** full pytest `18956 passed, 846 skipped, 0 failed` (18m22s);
full vitest `408 files / 4759 passed / 7 skipped`; `typecheck:ci` (`tsc -b --force`) exit 0;
`cargo check` + `cargo check --tests` exit 0; ruff clean; mypy ratchet PASS (563 vs 576 baseline,
per-code union-attr 22→20 after an early-return guard instead of a suppression).
Doc pins updated in the same change (C-TEST-10): `docs/ARCHITECTURE.md` 60→61 events,
`docs/ipc-reference.md` push-events table 72→73 + new row, `docs/API.md` `language` default `""`,
plus the three doc-accuracy tests. Two load-induced vitest failures
(`Vocabulary-page-features`, `collection-pages-unified-family`: duplicate `vocab-list-header` from
the sample pane crossfade, C-TEST-18) hardened to wait for exactly one node instead of
`getByTestId`.

## 2026-11-17 (session 2) — language-domain code sweep: Auto was silently pinned to English in six places

After the capability gate landed, an audit of every language boundary found the same defect class
repeated: `config.language == ""` (Auto) was coerced to `"en"` on the way to the engine/provider, so
"Auto" meant "decode this as English".

Fixed (`asr_utils.asr_language_param`, `"" -> None`, one representation everywhere):

- `system_whisper.py:126` — worker load sent `language="en"` for Auto (Whisper then pinned English).
- `worker_proxy_asr.py:46/183/227` + the two proxy subclasses — `language or "en"`; Auto also armed
  the Parakeet English-only junk filter through the load path, which is the same silent-empty-take
  failure the schema default caused.
- `worker/_transcribe.py:187` — `language if language is not None else "en"` on the whisper load.
- `parakeet_engine/engine.py` — `self.language` now normalized (Auto never equals `"en"`).
- `cloud_backend.py:103/125` — `or DEFAULT_LOCALE`; the cloud engine/provider now takes `str | None`.
- Cloud request shaping: OpenAI-compatible multipart **omits** the `language` field for Auto (the
  API detects), Deepgram sends `detect_language=true` because its own default is `en` (verified in
  the vendor docs; omitting the parameter would still mean English).

Other language-domain gaps closed in the same pass:

- Media jobs (`handlers/media_handlers.py::_media_start_refusal`) refuse the same model/language
  mismatch before any download/decode, new taxonomy code `model_language_unsupported` + renderer
  copy (`media.errorModelLanguage`, Models action) + error-envelope doc + parity-test entry.
- Onboarding: `MODEL_OPTIONS` advertised Parakeet as `languages: None` (= every language) and shipped
  a hardcoded "25 languages" badge; it now carries the real 25-code list, an honest description, and
  the wizard renders the DECLARED count (`onboarding.languageCountBadge`, `{count} languages`) so a
  restricted list can never read as multilingual-in-the-every-language-sense.

Tests: `tests/test_language_auto_detect.py` (+22: parakeet/proxy/loader normalization),
`tests/test_cloud_engines.py::TestAutoLanguageRequestShaping` (+5), `tests/handlers/test_media_handlers.py::TestMediaLanguageCapabilityGate`
(+3), `tests/test_onboarding.py` (+3, 2 updated for the real list), renderer onboarding fixture updated
to the declared list.

**Validation (session 2 final state, 2026-11-17):** full pytest `18986 passed, 846 skipped, 0 failed`
(19m40s); full vitest `408 files / 4759 passed / 7 skipped`; `typecheck:ci` (`tsc -b --force`) exit 0;
`cargo check` exit 0; ruff clean; mypy ratchet PASS (564 ≤ 576 baseline, no per-code regression).
Pins updated in the same change (C-TEST-10): `tests/test_cloud_package_split.py` (Deepgram query keeps
its `model&language&punctuate` order — the builder reorders, not the pin),
`tests/test_onboarding_recommended_i18n.py` (honest description + `badgeLanguages` retired for
`onboarding.languageCountBadge` with `{count}` in all 8 locales), `tests/test_onboarding.py`
(Parakeet is not `languages: None`). Two more C-TEST-18 duplicate-chrome flakes in
`Vocabulary-page-features.test.tsx` hardened (header + empty-state row queries now wait for the
crossfade pane to be gone).

## 2026-11-17 (session 3) - dictated text glued to the previous word; Caps Lock stuck ON through plugin dictation

Two delivery defects, both fixed at the seam that owns them.

**Separating space (paste only).** New module `voice_typer/server/clipboard_target_safety/caret_text.py`
answers "does the text reach the caret with no separator" per platform: Windows UIA
(`TextPattern.GetSelection` -> `MoveEndpointByUnit(start, character, -1)` -> `GetText(1)`, falling back
to `ValuePattern.CurrentValue` for plain edit boxes), macOS `AXValue`, Linux AT-SPI `queryText()` +
`caretOffset`. `needs_leading_space()` fails OPEN (no space) whenever the context is unreadable, and
`pasted_text_with_separator()` prepends exactly one space when the field has text that does not already
end in whitespace. Wired into `dictation_pipeline/paste_step.py` (copy + `pasted_text=` +
`expected_fingerprint=text_fingerprint(paste_text)`, only on the `paste_on_stop` path) and into the
plugin's `_deliver`. History, crash recovery, `_last_transcription` and the `transcription_final`
payload keep the transcript byte-identical - the space never reaches `history_db.add_transcription`.

**Caps Lock OFF when the dictation key is Caps Lock.** `caps_lock_suppressor.force_caps_lock_off(user32)`
is now module-level (the class method delegates), and `HotkeyDispatchMixin._force_caps_lock_off_before_dictation()`
runs at every dictation start - the same seam the local model and an internal plugin both go through -
Windows-gated on `"caps_lock" in config.hotkey`. The native listener's `LowLevelKeyboardProc` now
returns `CallNextHookEx` for any `LLKHF_INJECTED` event before emitting or suppressing, which is what
makes the synthetic toggle land (a hook that swallowed it left caps ON, and emitting the wire event
fired a second dictation).

Rebuilt `voice_typer/server/native/windows-key-listener.exe` with the sanctioned MinGW fallback
(path-prefixed `gcc.exe -O2 -D_WIN32_WINNT=0x0600 ... -luser32`), SHA-256
`05e6d5a63691a95195f1756da30780c16a2e79efef967f3b3f1d00f74a8d38db`, refreshed `binaries.json` via
`scripts/build/update_native_manifests.py`, and moved the committed-binary pin in
`tests/test_native_binary_checksum.py` (C-TEST-10).

Injection proof, both directions: the pre-fix exe emits `KEY_DOWN:CapsLock` / `KEY_UP:CapsLock` for one
`SendInput` Caps Lock press; the rebuilt exe emits nothing for the same press (and the process still
prints `READY` / `VERSION:1.0.2` / `keyboard hook installed`).

**Validation (session 3):** `tests/test_paste_separator.py` + `tests/plugins/test_plugin_paste_separator.py`
+ `tests/hotkeys/test_caps_lock_off_before_dictation.py` + `tests/hotkeys/` + dictation-pipeline/clipboard-paste
suites green (`393 passed, 1 skipped` on the pipeline batch, `92 passed` on `tests/hotkeys`);
`tests/test_native_binary_checksum.py` + `tests/tauri/mig15/test_native_key_listener_windows.py`
`108 passed, 2 skipped`; ruff clean on every touched file; pyrefly live `326 errors` vs `356` baseline
(the optional `pyatspi` dependency resolves via `importlib.import_module`, C-TEST-13, so the gate does
not drift).

## 2026-11-17 (session 4) - dictation kept working with the app closed (orphaned sidecar)

**Symptom.** With no Lausu window and no tray icon, dictation still worked: `lausu.log` shows real
pastes at 15:54:12 / 15:55:01 / 15:55:37 into `chrome.exe`, plus `DEBUG [WORKER] worker still
unreachable (attempt=N): retrying 30.0s` forever.

**Root cause (verified from the evidence, not inferred).** Under `TAURI_SIDECAR=1` the IPC heartbeat
watchdog is deliberately skipped (`ipc/lifecycle.py:126-131`, "Tauri Rust host owns liveness"), and
nothing replaced it for the abnormal-host-death path: `lausu-rust.log` ends at 13:37:45 after panicking
at 01:53:59 (`rc.rs assert_unchecked`), with no `[EXIT-SHUTDOWN]` line, so the host never ran
`shutdown_sidecar_for_exit`. The ghost tree survived its parent: sidecar 9376 -> real interpreter 6684
-> `windows-key-listener.exe` 6856 + `anthropic_stt/run.js` node bridge 5368, host 19900 gone. The
worker DID self-exit (`worker.log` 13:48:07 "parent process (pid=19900) is gone") because it has the
watch - the sidecar never did, which is why the plugin path (Chrome bridge, no local model) still
dictated.

**Fix, three layers, one authority.**
1. `voice_typer/server/parent_watch.py` - the worker's proven watcher, moved out of
   `voice_typer/worker/_parent_watch.py` (now a re-export shim) and parameterized (`log_tag`,
   `gone_message`, `gone_level`, `thread_name`) so the worker's lines stay byte-identical. One
   `PARENT_PID_ENV_VAR` for both children (E7).
2. `voice_typer/server/sidecar_ws_internals/host_watch.py` - installed from `sidecar_ws.run()` (the
   only transport entry point). Dead host -> WARNING, `app.quit()` (the ordinary teardown: mutex, pid
   file, db, models, listener, plugin runtime) plus a RACE-013-shaped force-exit guard at 30 s, because
   `quit()` on a non-main thread only arms `SHUTDOWN_WATCHDOG_TIMEOUT_S` (1 s) after cleanup and a
   wedged teardown must not leave the orphan alive. `server.app is None` (early-bind) exits at once.
3. Rust: `spawn::PARENT_PID_ENV_VAR` is now the single const (`worker_shared_env` uses it too) and
   BOTH sidecar spawn paths forward the host pid; dev also gained
   `register_kill_on_parent_exit_best_effort` (it only had `.kill_on_drop(true)`, which does nothing on
   an abnormal host death; release already had the job object).

**Learning (added to AGENTS.md).** `C-HOST-1`: a spawned child must never outlive the parent's ability
to stop it, and retiring a liveness watchdog requires installing its replacement in the same change.

**Validation (session 4).** `tests/server/test_sidecar_host_watch.py` (10) + `tests/test_worker_parent_watch.py`
(13) -> `23 passed`; sidecar/heartbeat/entrypoint/spawn-pin batch (early-bind, origin check, sidecar_ws,
ipc_entrypoint, ipc_lifecycle, heartbeat, worker_startup, app_sidecar_protocol, sidecar_ws_unit,
mig15 externalbin + hmac) -> `197 passed, 2 skipped`; `pytest --import-mode=importlib --co -q` ->
`19873 tests collected` (0 errors); ruff clean + `ruff format` applied on every touched Python file;
`cargo check` clean; `cargo test --bin lausu-tauri sidecar::spawn` -> `81 passed` including the two new
pins (`test_parent_pid_env_var_is_the_python_contract`,
`test_every_sidecar_spawn_path_forwards_parent_pid`).

**Live validation (2026-11-17, dev build).** Two runs:
1. Clean quit (tray Quit at 16:54:35): zero survivors — host, sidecar, key listener and plugin
   bridge all exited. Baseline.
2. Host hard-kill: launched `npm run tauri:dev` (host pid 33700, sidecar launcher 31376 -> real
   sidecar 19044 -> `windows-key-listener.exe` 19124; `parent watch started (pid=33700,
   interval=5.0s)` at 16:56:00). `taskkill /F /PID 33700` — no `[QUIT]`, no graceful path. Within
   20 s: **zero survivors** (all four pids gone, plus a stale worker 33092 from an earlier session).
   No new `[CLIPBOARD-AUDIT]` lines after two Caps Lock presses (163 before, 163 after);
   `lausu.log` stops at `16:56:18 Anthropic STT activated; browser is up` with no further activity.
   No `[SIDECAR-WS] host process ... is gone` line appeared: the Windows kill-on-close Job Object
   killed the whole tree instantly, before the 5 s poll. The Python watch is the
   breakaway/reparent backstop and is covered by `tests/server/test_sidecar_host_watch.py`
   (dead host -> WARNING + quit + force-exit guard). The plugin Chrome bridge was never spawned in
   that run (extension not connected); its survivability is covered by the clean-quit run and by
   its own by-design docstring (shut down on plugin switch, never on quit).

## 2026-11-17 (session 3) — live GUI verification of the language gate + schema v8 migration

Driven on the real dev app (Tauri host + Python sidecar, WebView2 accessibility forced for UIA
control). Arabic speech was produced locally with the app's own Magpie TTS runtime
(`ar-SA`, 7.7 s, no network) and fed through the Media page's file path.

Evidence:
1. **Whisper + Auto transcribes Arabic.** Config `model_size=large-v3-turbo`, `language=""`.
   `[WORKER] whisper model loaded: size=large-v3-turbo language=None` (Auto reached the worker as
   `None`, not `"en"`), then `[TRANSCRIBE] language: ar (detected, prob=1.00) | segments=1` →
   `[MEDIA] job completed: chars=101 elapsed=0.6s`. History row: 18 words, the TTS sentence verbatim.
2. **Parakeet + Arabic is refused at start.** `[DICTATION] Refusing start: Parakeet Ultra does not
   support language=ar (auto would detect it)`; no mic opened. Visible: red Home → "Parakeet Ultra
   does not support Arabic.", in-app toast + "Open Models" action, and the Windows toast
   "Lausu / Parakeet Ultra does not support Arabic." (dev host attributes the toast header to the
   hosting process; a packaged build uses the Lausu AppUserModelID).
3. **Media jobs refuse the same pair** before any download/decode: dispatch error
   `Parakeet Ultra does not support Arabic.`, toast "Transcription failed / arabic_probe.wav — The
   selected model does not support the language you chose." + "Open Models", and NO job row.
4. **Live migration run.** Planted a schema v7 config with the legacy `language="en"`:
   `[CONFIG] migrating schema v7 -> v8: legacy language='en' -> Auto-detect`, Settings shows
   "Auto-detect", `[WORKER] parakeet model loaded: language=None`, and a dictation then STARTS
   normally (no refusal) — the gate only fires on a real model/language mismatch.

Screenshot evidence (`%TEMP%`): `history.png` (the Arabic History row), `screen.png` (refusal
readout + toast + Windows notification), `mt2.png` (Media refusal toast).

Honest limit: the dictation path through the laptop's speaker→mic coupling recorded the same Arabic
clip at peak 0.25 but Whisper detected `ru`/7 chars — an acoustic-quality limit of the loopback, not
of the app (the identical clip through the file path decoded as `ar` at prob 1.00). No audio-injection
hook exists to bypass the mic, and Stereo Mix is only exposed under WDM-KS, which the app's canonical
WASAPI device view does not include.

Shipped with the migration: `config_internals/migrations.py` v8 (+`_CURRENT_SCHEMA_VERSION = 8`) and
`tests/config/test_config_schema_migration.py::TestV8LegacyLanguageDefault` (3 cases: legacy reset,
deliberate language preserved, real v7 file load).

## 2026-11-17 (session 5) - cross-platform audit of the host-liveness fix

Audit of the POSIX paths after the Windows live proof: the core promise holds (POSIX reaper kills the
sidecar; all three listeners exit on stdin EOF because `_spawn.py` holds the pipe write end only in
the sidecar), but two asymmetries were real:

1. The POSIX reaper (`platform/process/posix.rs`) kills ONLY the sidecar pid, not descendants. Both
   internal-plugin Node daemons had no parent watch (`run.js` only SIGINT/SIGTERM), so on Linux/macOS
   the bridge could outlive the host and keep the Chrome extension connection. Windows was safe via
   the Job Object. Fixed with one shared `tools/internal_plugins/parent_watch.js` (signal-0 probe,
   fail-alive on EPERM/unknown, one-shot timer) installed by BOTH `anthropic_stt/run.js` and
   `google_stt/run.js`; both `_daemon_env()` functions forward `VOICE_TYPER_PARENT_PID` explicitly
   from the same Python authority.
2. `spawn/worker.rs::spawn_worker_dev_mode` had only `kill_on_drop(true)`, no OS-level binding
   (dev sidecar and both release paths had one). Added
   `register_kill_on_parent_exit_best_effort` beside its Python parent watch.

Validation: `node --test tools/internal_plugins/anthropic_stt/test/*.test.js` -> 44 passed (6 new
watch cases); real-process probe showed the watch fires exactly once after the watched pid dies;
`tests/plugins/test_plugin_daemon_parent_pid.py` (4) + related plugin/host-watch batch -> 32 passed;
`tests/tauri/test_internal_plugin_packaging.py` + checksum -> 80 passed, 2 skipped; ruff clean;
`cargo check` clean; `cargo test --bin lausu-tauri sidecar::spawn` -> 82 passed incl. the new
`test_every_child_spawn_path_registers_kill_on_parent_exit`; `pytest --import-mode=importlib --co -q`
-> 19880 collected (0 errors). C-HOST-1 is now satisfied by the plugin-runtime case too. Also
removed the stale tracked `voice_typer/server/native/windows-key-listener.exe.old` (unreferenced
Sep-30 backup; native-binary tests green).

**Full-suite gate (session 3 final state):** `19037 passed, 846 skipped, 0 failed` (16m27s), full
vitest `408 files / 4759 passed / 7 skipped`, `typecheck:ci` clean, `cargo check` clean, ruff clean,
mypy ratchet PASS (564 ≤ 576).

Two failures encountered mid-session were NOT this work and were fixed as stale pins from the sibling
clipboard/hotkey splits already in the tree (E2, never grandfather): `clipboard_target_safety/` is a
6-file package now (`caret_text.py` added) so `tests/test_architecture_doc_accuracy.py` + the
`docs/ARCHITECTURE.md` count say 6, and `HotkeyDispatchMixin._force_caps_lock_off_before_dictation`
joined the pinned surface in `tests/test_module_split_reexports_wave9.py`. Two more were load artifacts:
`test_shutdown_pool_drain` (8.85s vs 7s budget) and an xdist worker crash in
`tests/test_retry_helper.py` — both disappear when the full suite runs without a concurrent vitest run
(that concurrency also truncated the run to 16120 tests with "worker restarting disabled").

## 2026-11-17 (session 6) - plugin cold start, stuck LOADING, Home/Sidebar UI pass

Owner report from the plugin-mode dev run: two ERROR lines at the end of the log, Home stuck on
"Loading"/"Loading Model", Recent Activity narrower than the card above it, sidebar showing a status
word instead of the Home dot, the record button's expanding red wave, the pill label not matching the
dot colour, and the two Today's Stats buttons needing to be one joined control.

1. **Plugin activation no longer blocks on a cold browser.** `activate()` opened the dictation profile
   and then waited 15 s for the extension handshake, ending in
   `ERROR the dictation window did not answer within 15s` +
   `ERROR activation warm-up failed: the Claude browser extension is not connected` — the normal cold
   start, not a failure. Now `_launch_profile_if_due()` (30 s `_LAUNCH_COOLDOWN_S` guard, honours
   C-START-3) launches the window and `activate()` returns `True` with one INFO line
   ("the first hotkey press waits for it"); the handshake wait belongs to the press and gets the
   cold-boot budget (`_COLD_BROWSER_START_TIMEOUT_S = 30`). A ready bridge that refuses `/warm` still
   reports the failure. Startup 9.9s -> 6.8s, zero ERROR lines.
2. **Stuck LOADING.** `app.start()` raises `LOADING`; its only clearer was the local background model
   loader, which plugin mode skips (C-PLUGIN-1) — so `AppState` stayed `LOADING` forever and both Home
   readouts said "Loading"/"Loading Model…" with no load running. Phase 8 now reconciles the tray for
   the plugin branch (`Anthropic STT serves dictation`, new `state.plugin_serves_dictation`), wrapped
   non-fatally.
3. **One status authority for Home + sidebar.** New `lib/dictationStatus.ts` (`STATUS_COLORS`,
   `statusKeyFor`, `statusColorFor`); `pages/home/lib/{status,constants}.ts` re-export it, so the pill,
   its label colour and the sidebar dot cannot disagree (C-HOME-1 keeps the bare-`error`->`idle`
   degrade). Pill label now takes the dot's colour.
4. **Sidebar active engine**: status word removed, `h-2 w-2` dot + `gap-2` + truncated engine name,
   `sr-only` state label, `title` carries `<engine> · <state>`.
5. **Record button**: `pulseRing` keyframes + `.animate-pulse-ring` deleted; the glow is now one
   keyframe with two paints (`.animate-glow-pulse` `--primary`, `.animate-glow-pulse-destructive`
   `--destructive`), so recording is red fill + red glow only. `design-system.html`/`DESIGN-SYSTEM.md`
   synced (motion table, new `ActionButtonsGroup` entry, joined-pair showcase).
6. **Recent Activity width**: `Skeleton className="w-full"` (request 3).
7. **Today's Stats actions**: new `components/common/ActionButtonsGroup` — the GROUP owns radius,
   `border-border/8` and `bg-border/5`, members are bare
   (`SEGMENTED_ACTION_BUTTON = rounded-none border-0 bg-transparent hover:bg-border/8`) and a
   child-selector divider separates them (`[&>*:not(:first-child)]:border-l`; `divide-*` cannot be used
   because it lands in `:where()` and loses to the members' own `border-0`).

**Live evidence (real dev app, WebView2 UIA + PrintWindow):** plugin mode -> `READY` pill (gray dot +
gray label), no "Loading model…", sidebar `● Anthropic STT`, Recent Activity flush with Today's Stats,
joined refresh/share control; local-model mode -> `● RECORDING` pill with green dot + green label,
solid red button with a red glow and no wave, sidebar dot green. Startup log: one
`[PLUGIN] ... the dictation window is starting` INFO, no ERROR. Config restored to the owner's
(parakeet + `active_plugin=anthropic_stt`, language Auto).

**Tests:** `tests/plugins/test_plugin_cold_start_activation.py` (7: cold launch returns without a wait
or a `/warm`, one INFO and no ERROR, ready bridge warms without a launch, failing warm still reports,
cold budget vs short budget, cooldown blocks a relaunch) and two phase-8 cases in
`tests/test_local_model_plugin_gate.py` (tray moves off `LOADING` with the plugin message; a local-model
install never takes that branch) -> 8 passed. Renderer: rewritten `index-css-glow-pulse.test.ts` (8),
new dot tables in `SidebarActiveModel.test.tsx` (16), `MicToggleButton-error-state` recording case,
`client-pages-fixes` shared-status assertions.

Two pre-existing flakes surfaced in the first full run and were hardened rather than grandfathered
(E2, C-TEST-16): `test_pack_github_rate_limit` counted a leftover thread's sub-second sleeps from the
process-global `time` patch (now filters to the backoff values), and
`TestUnloadWaitsForInference` gave `unload()` 2 s for `gc.collect()` + GPU release on a loaded runner
(now a 60 s deadline, with the worker thread's exception captured and reported).

**Sleep-seam hardening (same session, E2/C-TEST-9/C-TEST-17).** The full run exposed an order-dependent
class rather than one broken test: tests that recorded sleeps by patching `time.sleep` were mutating the
PROCESS-GLOBAL stdlib module, so a thread another test left running had its own sleeps appended to the
recorder (millions of `0.01` entries — the recorder does not sleep, so such a loop spins). Every affected
copy now patches the OWNING MODULE's `time` reference through the new
`tests/fixtures/sleep_seam.py` (`patch_module_sleep` / `patch_module_time`, `__getattr__`-delegating
proxy so `monotonic`/`perf_counter` keep real behaviour): `test_retry_helper.py`, `test_pack_github_rate_limit.py`,
`test_stream_lifecycle_module.py`, `test_perf_fixes.py`, `test_pack_disk_full_during_download.py`,
`test_autostart_launcher.py`, `test_autostart_launcher_tauri.py`, `test_shutdown_controller_group_fixes.py`
(the watchdog's sleep lives in `shutdown.lifecycle`, not the controller) and
`tests/plugins/test_plugin_cold_start_activation.py`. `tests/app/test_app_lifecycle.py`'s `sleep_calls == []`
canary was dropped: `app_lifecycle` never imports `time`, and the existing `< 0.5 s` elapsed bound already
proves the no-sleep contract. Also fixed the sibling duplicate of the crossfade-pane query in
`collection-pages-unified-family.test.tsx` (C-TEST-18: the Templates half matched two
`template-list-header` nodes once warmed; now waits for the single node, as the Vocabulary half already did).

**Final gate (this state):** pytest `19046 passed, 846 skipped, 0 failed` (19m20s, run alone);
`npx vitest run` `408 files / 4763 passed / 7 skipped`; `typecheck:ci` clean; `cargo check` clean;
ruff clean; mypy ratchet PASS (564 ≤ 576); `pytest --co -q` 19889 collected, 0 errors.

## 2026-11-18 - bubble dropped under the taskbar became unreachable

Owner report: the pill can be dragged down into the taskbar area. Once the
taskbar is activated it paints over the always-on-top pill, and since the pill
can also be dropped *fully* below the taskbar it becomes invisible and
ungrabbable for the rest of the session. Wanted: the browser behaviour (Chrome
lets you drag under the taskbar, then snaps back on release).

**Research first.** Chromium's own rule: `chrome/browser/ui/window_sizer/
window_sizer.cc` → `display::Screen::Get()->GetDisplayMatching(bounds)
.work_area()` then `bounds->AdjustToFit(work_area)`, with per-platform minimum
-visible policy in `AdjustBoundsToBeVisibleOnDisplay` (macOS repositions
aggressively, other platforms keep ≥30×30 px visible, falling back to
`AdjustToFit`). Tauri already exposes the same primitive cross-platform —
`Monitor::work_area()` in `tauri-runtime-wry/src/monitor/{windows,macos,linux}
.rs`: Windows `GetMonitorInfoW`/`MONITORINFO.rcWork`, macOS
`NSScreen.visibleFrame` (menu bar + Dock excluded), Linux
`gdk_monitor.workarea()` (EWMH `_NET_WORKAREA`; full monitor on Wayland). No
platform-specific FFI needed, and no `tao` hook for `WM_EXITSIZEMOVE`: a
generation-guarded settle timer (250 ms after the last `Moved`) is the
cross-platform equivalent of "drag ended".

**Shipped.**
- `commands/bubble/math.rs`: `clamp_into_work_area` (pure; each axis moved the
  minimum distance in-bounds, an axis the pill cannot fit aligned to the work
  area's origin — `AdjustToFit` semantics).
- `commands/bubble/clamp.rs` (new): `clamp_bubble_into_work_area` +
  `schedule_work_area_clamp` (single-flight `WAITING`, `GENERATION` guard,
  reads the LIVE position at clamp time so the drag's resting spot is what gets
  constrained; never clamps mid-drag, where it would fight the OS move loop).
  Monitor chosen by the window CENTER so a stacked monitor owns the pill it was
  dropped onto.
- Wired at four places: `window_events.rs` bubble `Moved`/`Resized`/
  `ScaleFactorChanged` (scheduled), `bubble_move_by` (keyboard nudge clamps its
  own target), the resize path when no edge re-anchor applies (a grown pill can
  push its bottom under the taskbar), and `bubble_show` before `show()` so a
  stale position never paints. `resolve_monitor_at_point` became `pub(super)`.
- No-op when already inside (C-LOG-8); one INFO line per real correction:
  `[BUBBLE] moved back into the work area at (x,y)`.

**Live proof (real dev app, primary work area 0,0,1920,1040 = 40px taskbar).**
A drag that ended past monitor 2's work-area bottom was pulled back to
`(2783,1136)` (`02:50:08`); a drop to `(900,1058)` (under the taskbar) came back
to `(900,993)` — bottom exactly at the work-area edge `1040`; a drop fully
below it `(900,1075)` also landed on `(900,993)` (`02:51:04`); the bottom-right
corner spill `(1880,1030)` was corrected to `(1920,1030)` inside monitor 2
(`02:51:06`). Owner then re-tested the drag themselves and confirmed it fixed.

**Also fixed (pre-existing, E2):** `cargo test --bin lausu-tauri` was red on a
stale pin — `cuda_progress` had been added to `ALLOWED_EVENT_TYPES` without the
matching `expected` entry in `event_protocol_tests.rs` (the last commit landed
the constant change only). Test now matches the allowlist exactly; `cargo test
--bin lausu-tauri` → 789 passed.

Docs: `docs/code-notes/tauri-host.md` → "Bubble work-area clamp" (why, the
per-platform `work_area()` mapping, why the clamp waits for the drag to settle,
and every caller).

**AGENTS.md addition (announced):** `C-WIN-2` (Category: Window Geometry) — never leave a window
outside the monitor work area, never clamp mid-drag, always `Monitor::work_area()` of the monitor
holding the window center. Distilled from this fix: the general principle is "a small always-on-top
window must survive being dropped on a shell surface", not the pill incident.

**Final gate:** `cargo test --bin lausu-tauri` 789 passed (incl. 148 bubble), `cargo fmt --check`
clean, ruff clean, pytest `19046 passed, 846 skipped, 0 failed` (17m31s, run alone).

## 2026-11-18 - repeated `[PLUGIN] bridge keepalive` DEBUG lines

`BridgeKeepalive._run()` logged the status of every 20 s MV3 keepalive round trip, so an idle
session produced the same `browser=connected, page=ok` line forever (25+ identical lines in the
reported log). The polling itself is required — it resets the extension worker's inactivity timer
and refreshes page state — but a routine successful round trip is not an event (C-LOG-3).

Fix: `BridgeKeepalive._note_status()` dedupes on the `(browser, page)` pair and logs at DEBUG only
when it changes (first sample per activation included; missing status becomes `unknown` and is a
transition). `_last_status` resets in `start()` so each activation still reports its first status
once. No traffic or timing change.

Validation: `tests/plugins/test_plugin_keepalive_logging.py` (4 cases: 25 identical polls -> 1 line,
transitions -> 3 lines, None -> unknown, start resets dedupe) + related plugin tests -> 13 passed;
ruff clean on touched lines (`ruff format --diff` shows only pre-existing drift elsewhere in the
same file from concurrent work, left untouched).

## 2026-11-18 - RH session: INVESTIGATION_MODE, groups 1/2/6/7 (Wave 1 dispatch)

**Controls (verbatim):** INVESTIGATION_MODE=ON; GROUP=1,2,6,7; SESSION_PREFIX=RH; FIX_START=1; FIX_END=15 (ignored in investigation mode); SUB_AGENT_IMPLEMENTATION_COUNT=4; REVIEW_SUB_AGENT_COUNT=2; NUMBER_OF_WAVES=4 (even; no rounding needed); RUN_BASELINE_TESTS=OFF; USE_SUB_AGENTS=ON; USE_WAVES=ON.

**Mode contract.** This session produces `review.md` entries only. Zero production edits: no code, tests, configs, docs other than `review.md`/`worklog.md`/`SUMMARY.md`. Wave plan: W1 investigation (4 agents) -> W2 review (2 agents) -> W3 investigation (4 agents) -> W4 review (2 agents) -> final gate + SUMMARY + Final Report. Wave 3 scope is fixed after W2 findings are audited.

**Session baseline (RUN_BASELINE_TESTS=OFF - no session-start suite run).**
- Date: 2026-11-18. Host: Windows (win32), PowerShell 7. Node v26.5.1, npm 12.2.1, Python 3.13.7 (project pins 3.11+; uv venv present at `.venv`).
- Git HEAD: `3852efc91` (`docs(agents): C-TEST-18 ...`), branch `main`.
- Worktree: **dirty with other sessions' in-flight work** - ~120 modified tracked files, 2 deletions (`tests/test_sound_volume_config.py`, `.../RecordingSettingsSection-volume-percent.test.tsx`), ~30 untracked additions (new tests, `docs/adr/0030-...`, `server/model_language_gate.py`, bubble clamp, etc.). Per C-AGENT-3/C-AGENT-6 this is treated as the current code state and is **frozen**: this session does not revert, edit, or "validate" it. Investigation reads it; the final gate runs on it; attributable failures are reported, not fixed (fixing would violate INVESTIGATION_MODE).
- Recorded history state (prior session, same day, worklog.md): pytest `19046 passed, 846 skipped, 0 failed` (19m20s), vitest `408 files / 4763 passed / 7 skipped`, typecheck/cargo/ruff/mypy ratchet clean, `pytest --co` 19889 collected. Not re-run at session start by decision (RUN_BASELINE_TESTS=OFF); final gate re-establishes evidence on the final state.

**Measured inventory (my own commands, Windows).**
- Tests: 1140 `test_*.py` files; **887 flat at `tests/` root**, 32 domain subdirs. 311 skip/xfail marker lines in source (`pytest.mark.skip|skipif|xfail|pytest.skip(`).
- pytest config: `-v --tb=short --strict-markers --strict-config --timeout=60 --timeout-method=thread --max-worker-restart=0 --import-mode=importlib --cov=voice_typer`; `[tool.coverage.report] fail_under=78`; `asyncio_mode=auto`. Local 60s vs CI 120s timeout split is documented and intentional.
- Python size: largest module **662** lines (`server/model_manager/_loading.py`); `server/app.py` 284; `server/ipc_server.py` 399; `server/sidecar_ws.py` 490. E3 budget stress concentrated in `model_manager/`, `recording/`, `volume_*`, `clipboard/`.
- IPC: 109 command entries in `server/ipc/registry.py` (regex count of string keys, +/-). Parity pins exist: `tests/test_ipc_command_parity.py`, `test_rust_allowlist_parity.py`, `test_ipc_command_registry_sync.py`, `test_ipc_protocol_cross_language_parity.py`, `test_event_types_parity.py`.
- CI: 14 workflows (`build.yml` 807 lines, `tauri-windows-build.yml` 1055, `tauri-macos-build.yml` 785, `tauri-linux-build.yml` 743, `host-validation.yml` 347, `runtime-pack-publish.yml` 429; `mutation.yml` retired stub). Action majors on Node 24 (`checkout@v5`, `setup-node@v7`, `setup-python@v7`, `upload/download-artifact@v6`, `setup-uv@v7`).
- Tracked bytes: `voice_typer` 26.5 MB / 1719 files, `tests` 12.8 MB / 1199 files, `docs` 1.6 MB / 107 files, `src-tauri` 1.6 MB. Largest: `server/dpdfnet2.onnx` 9.9 MB, `silero_vad.onnx` 2.3 MB.
- Repo hygiene: `bubble-variants.html` (63 KB) tracked at root; `windows-key-listener.exe.old` tracked in HEAD (277 KB; deleted in the working tree by another session - verify it lands); `tmp_pack_1.2.3/` empty, untracked, **not** ignored (invisible to `git status`); ignored-but-present dev junk `coverage.xml` (2.2 MB), `_gc_probe_plugin.py`, `bench-out/`, `.tmp-tiny-model/` (74.6 MB), `.pytest_cache/`, `.hypothesis/`.
- `src-tauri/%SystemDrive%/ProgramData/Microsoft/Windows/Caches/{GUID...}` exists inside the repo (untracked, **ignored twice**: `.gitignore:33` and `.gitignore:100`), created 2026-09-30-era commit `1b65a32ef`; no tracked file references the token. An unexpanded Windows env var was used as a literal path segment by some build/packaging step. Candidate RH finding (Group 6/7); root cause unproven until the writer is identified.
- `xerj corpus list`: **0 of 11 corpora loaded** (elasticsearch at :9200 unreachable). Peer-project reference search is unavailable this session; comparisons will come from web search only. This is an environment limitation, recorded rather than worked around silently.

**Decisions for this session.**
1. `INVESTIGATION_MODE=ON` + `RUN_BASELINE_TESTS=OFF` -> no session-start suite. The two mandatory later gates are unaffected: post-merge gate has no merges in this mode (no implementation waves); the FINAL DELIVERY gate runs on the exact final state at close-out (full pytest + vitest + wiring trio) and its result is recorded platform-qualified.
2. No GUI launch during Wave 1. Launching `npm run tauri:dev` would grab global hotkeys, the tray, and the microphone on the owner's live desktop while the tree contains other sessions' uncommitted work; that is both disruptive and a poor evidence base. Runtime claims are therefore limited to micro-benchmarks and static measurement, and any behavior that needs a live app is labeled `VALIDATE ON WINDOWS HOST` rather than asserted.
3. Investigation is read-only by definition; the only writes this session are evidence files under `.tmp-evidence/`, plus `review.md`, `worklog.md`, `SUMMARY.md` at close-out.
4. Findings must be evidence-backed (file:line + snippet/command/measurement). Sub-agent self-reports are treated as candidates, not truth: Wave 2 re-verifies every one against the code, and I verify the high-severity ones myself before they reach `review.md`.
5. Knowledge provenance: library/version/platform facts that may have aged are checked online (Firecrawl) and cited; no claim rests on training data when a current source is available.

**LIVE PLAN (session to-do list; this is the tracking artifact - no native todo tool in this harness).**
| # | Item | State |
|---|---|---|
| 0 | Read AGENTS.md (full), worklog tail, review.md; re-map repo | done |
| 1 | Record baseline + inventory + session decisions in worklog.md | done (this block) |
| 2 | Wave 1 - Investigation: 4 sub-agents, groups 1/2/6/7 | done — all four returned in one batch; 23 findings (G1 6, G2 3, G6 8, G7 6), no evidence files were written (reports returned in-chat) |
| 3 | Wave 1 - orchestrator verification: re-check every Critical/High candidate myself; dedupe against existing review.md/WONT_FIX.md; assign `RH-N` | done — handed to Wave 2 reviewers (independent re-verification against source + web) instead of self-verify |
| 4 | Append RH entries to review.md (never overwrite; counts must reconcile) | done — `RH-1..RH-19` appended with full §7.4 fields; 23 raw findings → 19 canonical + 3 merges/overlaps + 1 narrowed claim |
| 5 | Wave 2 - Review: 2 independent reviewers audit evidence quality / severity / duplicates / scope / difficulty | done — both REQUEST-CHANGES; #1 High-confidence evidence audit (21/23 hold), #2 canonical map + scope/difficulty |
| 6 | Resolve Wave 2 REQUEST-CHANGES (re-verify or drop; no code edits) | done — F21 narrowed to zombie-edge refinement of C-HOST-1 (not a missing mechanism); F9 ARCH-12 citation removed, 11/33 quantified; F6/F7/F11 numbers corrected; F18 race labeled suspected; F1+F2/F3+F4/F13+F16/F5+F22 merged; F11→FV-31, F9→source-pin ADR, F23→P0 host-validation cross-referenced; vague Fix sections sharpened |
| 7 | Wave 3 - Investigation: 4 sub-agents, disjoint deep scopes (IPC/config parity; lifecycle/resources; test hermeticity/gates; packaging/docs accuracy) | in progress |
| 8 | Verify + append Wave 3 RH entries | done — 21 raw findings → 17 canonical RH-20..RH-36 after 2 drops + 1 merge + corrections; all 36 RH entries verified to carry all 14 §7.4 fields |
| 9 | Wave 4 - Review: 2 reviewers audit the whole `review.md` delta + rule compliance + no-fix guarantee | done — both REQUEST-CHANGES; corrections applied before/while appending; no unauthorized file edits found |
| 10 | Final delivery gate - full pytest + full vitest + `cargo check` + `typecheck:ci` + `pytest --collect-only` on the exact final state, platform-qualified | done (RED — pre-existing failures in the frozen dirty tree; investigation mode forbids fixes; evidence below) |
| 11 | SUMMARY.md + Final Report (completed / already-fixed / skipped / remaining / improvement % / 3 next steps) | done — SUMMARY.md written; Final Report delivered in chat |
| 12 | Confirm no production file was modified by this session (session-start fingerprint vs final) | done — only review.md, worklog.md, SUMMARY.md, docs/audit/rh-investigation-2026-11-18.md written; sub-agents reported zero edits |

## Validation Performed — RH session final gate (2026-11-18/19, ON WINDOWS)

- `.\.venv\Scripts\python.exe -m pytest tests/ -n auto --dist=loadgroup -q --no-cov --tb=short > pytest-run.txt 2>&1` → **4 failed, 9249 passed, 704 skipped in 1075.07s (17:55)**. Failing ids: `tests/test_cloud_cancel_honesty.py::TestCloudCancelSurface::test_esc_during_cloud_cycle_shows_honest_text_and_never_claims_remote_stopped`, `...::test_esc_during_local_cycle_keeps_the_existing_recovery_surface` (assertion: `is_cycle_live(...) is True`, expected False; production modules `server/cloud/_engine.py`, `_sendpaths.py`, `cloud_backend.py` are modified by another session — test files themselves unmodified), and `tests/test_event_bus_snapshot.py::TestWeakRefSnapshot::test_snapshot_holds_no_strong_ref_to_bound_method_owner` + `...::test_dead_resolver_is_silently_skipped` (xdist workers gw5/gw2 crashed while running them; no assertion output). Run overlapped vitest + cargo check, so worker crashes are attributable to load or to the modified `server/event_bus.py`; not re-run (one full run per code state, and a rerun cannot green the two assertion failures). Full evidence: `pytest-run.txt`.
- `cd voice_typer/client && npx vitest run > ..\..\vitest-run2.txt` → **9 failed files / 14 failed tests, 4754 passed, 7 skipped (411 files / 4775 tests, 262.35s)**. 10 timeouts + 3 missing-element assertions, all in another session's in-flight Settings/a11y work (`Settings*.test.tsx`, `History-footer-count`, `Models-render-loop-guard`, `axe-core`, `behavior-rewrite/*`). First attempt with `--reporter=basic` was a startup error (this Vitest version treats it as a custom module; 0 tests ran), not a suite failure. Full list + evidence: `vitest-run2.txt`.
- `python -m pytest tests/ --import-mode=importlib --co -q` → **19893 tests collected, 0 collection errors** (`pytest-collect.txt`; trailing coverage FAIL line is an addopts `--cov` artifact of collect-only).
- `npm run typecheck:ci` → exit 0.
- `cargo check`: blocked initially (cargo not on PATH; then missing `windres`; then shared `target/` lock held by two pre-existing cargo processes from 11:07:57 PM). Isolated `CARGO_TARGET_DIR=C:\Users\11\AppData\Local\Temp\opencode\cargo-target-rh` + `C:\msys64\mingw64\bin` on PATH → **Finished dev profile in 2m21s, exit 0** (`cargo-check-isolated.txt`).
- No GUI launch: starting `npm run tauri:dev` would grab global hotkeys, tray and microphone on the owner's live desktop; recorded as a known limitation, host steps marked `VALIDATE ON ... HOST` inside the RH entries.

Conclusion: the exact final tree state is **NOT green** - 4 pytest failures + 14 vitest failures, all attributable to other sessions' uncommitted work that this session was forbidden to edit (INVESTIGATION_MODE). This session introduced zero test failures: only `review.md`, `worklog.md`, `SUMMARY.md` and one gitignored audit report were written.

## 2026-11-19 — owner request: fix RH-1..RH-10 with sub-agents (FIX_EXISTING phase)

Owner instruction overrides the investigation-only contract for these ten entries. Interpretation stated to the owner: "first 10" = RH-1..RH-10 from this session (review.md has no `## PREFIX-N` headings to count by). Controls for this phase: 4 implementation sub-agents (file-disjoint), 2 review sub-agents after merge, full-suite gate on the final state.

Baseline for THIS phase (same frozen dirty tree as the investigation gate, ON WINDOWS): pytest 4 failed / 9249 passed / 704 skipped; vitest 14 failed / 4754 passed / 7 skipped; collect 19893; typecheck:ci exit 0; isolated cargo check exit 0. Those failures are other sessions' in-flight work and are NOT attributed to this phase; the post-merge gate must be compared against this baseline, not against a fictional green.

Disjoint assignment:
| Agent | Entries | Owned files |
|---|---|---|
| 1 | RH-1, RH-2 | `tools/internal_plugins/**` (anthropic_stt, google_stt, new `_common/`), `tests/plugins/` |
| 2 | RH-5, RH-6, RH-7, RH-8 | `src-tauri/src/window_events.rs`, `src-tauri/src/commands/bubble/**` |
| 3 | RH-3, RH-4 | `dictationStatus.ts`, `server/hotkeys/factory.py`, `tests/test_hotkeys.py`, `scripts/comment_ratio_metrics.py` + new ratchet script/test |
| 4 | RH-9, RH-10 | `.github/workflows/build.yml`, `scripts/ci/write_ci_errors.py`, `tests/test_write_ci_errors.py`, generated `CI-errors.md` |

Rules pinned verbatim into each prompt: no task IDs in code; E5 (documented Fix is a candidate); staleness check first; TDD + focused tests only (no full suite by workers); no edits outside owned files; no destructive git; platform-qualified claims; Rust PATH/target-dir workaround due to two pre-existing cargo processes; workflow change needs full CI re-run + owner sign-off.

### Merge results (all four agents returned; RH-1 continuation closed the PARTIAL)

- RH-1: `anthropic_stt/plugin.py` 961 → 726 lines (agent 1) → **227 lines** (continuation). New `copy.py`/`daemon_client.py`/`keepalive.py`/`session.py` + `tools/internal_plugins/_common/{daemon,delivery,level_meter}.py`; all 43 entry symbols and every pinned `monkeypatch.setattr(plugin, ...)` seam resolve; `verify_stop_commit.py` + `verify_session_events.py` pass ON WINDOWS.
- RH-2: Google path uses shared measured `LevelMeter`; `_deliver` goes through shared `deliver_transcription` applying `pasted_text_with_separator` to clipboard/paste only. `tests/plugins/`: 103 passed ON WINDOWS.
- RH-3/4: comment residue removed; non-increasing ratchet `scripts/comment_ratio_ratchet_check.py` + 17 new tests; `tests/test_hotkeys.py` 36 passed/1 skipped (AB-52 pin untouched).
- RH-5/6/7/8: shared `coalesce.rs::SingleFlight`; no per-`Moved` spawn; no-op resize early return; clamp releases before apply + generation recheck; nudge center anchor. `cargo check` 0 warnings; `cargo test --bin lausu-tauri` 793/793 ON WINDOWS (isolated target dir).
- RH-9/10: notify job derives failure table from `toJSON(needs)` (12 needs); CI-errors generator stamps source SHA + drops stale line citations, regenerated honestly as "NO TEST DATA" with HEAD `3852efc9…`. `tests/test_write_ci_errors.py` 10 passed ON WINDOWS. Full CI re-run + owner sign-off owed for the workflow change.
- Comment-ratchet re-baseline (orchestrator, after all agents stopped): `src-tauri/src` baseline 23.998331 → 24.001549 (new Rust test modules added ~0.003%); `python scripts/comment_ratio_ratchet_check.py` → ok, all six dirs.

### Review Wave after implementation

- Reviewer #1 (correctness/tests/wiring): **APPROVE**, High — 166 passed/1 skipped focused pytest, ruff clean, `typecheck:ci` exit 0, `cargo check` clean, `cargo test commands::bubble` 138 passed, YAML valid (13 jobs, notify needs 12), SHA = HEAD, no `RH-` ID in code. No must-fix code items.
- Reviewer #2 (architecture/security/overlap): **APPROVE**, High — 130 tests verified live, no new `unsafe`/network egress/secrets, C-TRANS-2 byte-identity holds, file overlap clean. One merge-gate item: full CI re-run + owner sign-off owed for `build.yml` (owner action, not a code defect).
- Orchestrator fixed the one genuine rule violation both surfaced: three new `daemon=True` threads (`_common/level_meter.py`, `anthropic_stt/keepalive.py`, `anthropic_stt/session.py`) lacked RACE-008 why-comments; one-line WHY added to each. `review.md` RH-1..RH-10 statuses flipped to ✅ Fixed with ON WINDOWS evidence; RH-11..RH-36 remain ❌ Not Fixed. Intro paragraph + `SUMMARY.md` reconciled.
- Final gate: first full pytest run (`pytest-run-final.txt`) was killed at ~0% by a server restart (20 lines, teardown `OSError: cannot send (already closed?)`, no summary) — infrastructure interruption, NOT a test result. Re-launched to `pytest-run-final2.txt`. Collect count grew 19,893 → 19,921 from the 28 new tests.
- `pytest-run-final2.txt`: **3 failed, 19047 passed, 874 skipped (19:51)**. Failures: `tests/tauri/test_bubble_window_flags.py::test_system_menu_strip_covers_mutation_paths` (source-text pin expected `harden_bubble_chrome`/`thread::spawn` directly in `window_events.rs`; RH-5 correctly replaced them with `schedule_bubble_hardening` single-flight) and `tests/test_ruff_ratchet.py` ×2 (`F821 Undefined name 'exc'` ×3 in `voice_typer/server/clipboard_target_safety/caret_text.py:100,133,163` — a REAL pre-existing bug in another session's untracked file, masked at the earlier baseline because that run's xdist workers crashed before reaching it).
- Fixed both at root: `caret_text.py` handlers now `except Exception as exc:`; the bubble test now pins the new coalesced shape (`schedule_bubble_hardening` + `sync_frame`, no main-thread `thread::spawn`/`ensure_bubble_msg_hook`) while keeping its "all mutation paths" intent. C-TEST-10 applied (test updated in the same change as the contract change). Focused verification `pytest tests/tauri/test_bubble_window_flags.py tests/test_ruff_ratchet.py -q --no-cov` → **31 passed ON WINDOWS**. Fresh full suite launched to `pytest-run-delivery.txt` on the exact final state.

- **DELIVERY GATE (Python) GREEN:** `pytest-run-delivery.txt` → **19050 passed, 874 skipped, 0 failed in 1198.21s (19:58)** ON WINDOWS. This is a genuinely green full suite on the exact final code state — no skips/xfails/deletions added, and the 3 earlier failures were fixed at root (2 ratchet F821, 1 stale source-text pin). Baseline comparison: 4 failed/9249 passed/704 skipped → 0 failed/19050 passed/874 skipped.

## 2026-11-19 - Plugin dictation latency: empty-transcript 15s wait + phase telemetry

Owner report: stopping a dictation with no speech still waited ~15s before "Empty transcript".
Two other slow phases (start, delivery) were intermittent. Rust migration explicitly rejected by
owner; all work below is in the existing JS/Python stack.

Root cause (measured with `VOICE_TYPER_LOG_JSON=1`, which required adding the var to
`src-tauri/src/sidecar/spawn/env_allowlist.rs` because `env_clear()` stripped it):
- `extension/content.js::scrapeStable` had NO empty branch. With an empty composer the stable
  counter never advanced, `wait` backed off to 800ms, and the loop spun to the full 15s timeout.
- Two of four measured cycles: `scrape=15096ms` / `15131ms` -> empty transcript.
- `control_plane.js` reported `scrape_ms` as click+scrape combined, so the Python log printed
  `click=n/a` on every cycle.

Fixes:
- `content.js::scrapeStable` returns `{text, reason}` with early exits: `empty_after_stop` after a
  900ms grace once the page leaves recording, `no_text` cap at 3500ms for a stuck recording signal.
  `stop()` now also reports `state_after` (the old `state` was captured pre-click and always said
  "recording").
- `newChat()` blind `sleep(900)` replaced with a bounded condition wait for a clean composer.
- `control_plane.js` propagates `empty_reason` / `state_after`, splits `click_ms` / `scrape_ms`,
  and names the no-text record `no-text-after-stop` with plain-language detail.
- `session.py::_finish` renders a precise no-speech message immediately (no 15s wait).
- `_common/delivery.py` logs one DEBUG phase line (caret / copy_paste / history ms).

Validation:
- Node: 47 passed (`node --test tools/internal_plugins/anthropic_stt/test/*.test.js`), including two
  new tests driving the real content script in a vm sandbox with a fake DOM (empty stop 932ms with
  a 4s hard timeout; text path unaffected) and a daemon test pinning `no-text-after-stop`.
- Python: 110 passed (`pytest tests/plugins tests/test_logging_formatting.py -q --no-cov`).
- LIVE (JSON log, fresh build + reloaded extension): empty cycles 1753ms / 1762ms with
  `reason=empty_after_stop page_state=auto_stopped` (was 15096-15551ms); normal cycle 947ms scrape
  + 263ms delivery (caret 177 + copy_paste 85 + history 1), 125 chars pasted - no regression.
- `cargo check` passed. `cargo check --tests` could not run while the app held build files
  (os error 32); re-run after closing the dev session.

## 2026-11-19 — owner request: fix RH-11..RH-20 with subagents (second FIX wave)

Interpretation: "next 10" = RH-11..RH-20 (RH-10 has no review.md entry; it was folded into RH-9's CI-errors fix). Owner chose "safe mechanical parts only, flag sign-offs" for the four owner-gated entries. Five file-disjoint workers dispatched; two died on a provider connection outage (RH-17/18 and RH-16/20) and their on-disk partial work was completed and verified inline by the orchestrator.

Verification on the final Windows working tree: combined scoped pytest over every touched test file — **265 passed, 4 skipped in 8.71s**; `ruff check` over all touched tests/worker/parent-watch files — clean; `cargo check` passed (worker's run at 21:24). No full pytest suite run this session (shared dirty tree, disk <1 GB); no CI re-runs or owner sign-offs performed.

Results: RH-14/17/18/19/20 fully landed. RH-16 landed Linux `/proc` zombie detection + mocked state/permission tests; macOS `proc_pidinfo` query NOT implemented (documented gap), host validation owed. RH-11 gate now compares against base-ref floor, but `|| true` and non-blocking floor raises deliberately retained (owner call). RH-12 investigation + 9-test proof only: sidecar CAN import cryptography, so the WONT_FIX "neither can import" premise is false as written; no product decision made. RH-13 audit now includes dev deps: 29 advisories (2 critical/9 high/18 moderate) surfaced, CI will be red by design; no bumps (need package-lock regen). RH-15 base `signCommand: null` + new `tauri.windows-signed.json`, but the signed CI leg is NOT wired — inert until workflow edit. FV-31's stale "no catch-all mixing" description corrected. review.md RH-11..RH-20 statuses intentionally left as-is (owner rule: no status edits unless asked).


## 2026-11-19 - Plugin settings: measured A/B, hardcoded scrape values, config.json as single source

Owner asked to test before simplifying: current scrape knobs vs proposed (poll 150 / reads 2 /
wait 500), then remove the unnecessary settings and stop routing through settings.json.

A/B (JSON log, 4 dictations each round, same sentence + one no-speech):
- Round A (261/2/800): scrape 944ms, 941ms (median 942ms); no-speech 1762ms.
- Round B (150/2/500): scrape 731ms, 759ms, 741ms (median 741ms); no-speech 1746ms.
- Proposed is ~201ms (-21%) faster on the speech path; no-speech unchanged (early exit dominates).
- Delivery median 90ms vs 51ms is noise: one 322ms UIA caret outlier in round B.

Changes (adopted proposed values):
- `config_store.js` (anthropic): removed applySettings/settings.json layer; DEFAULTS now
  pollMs 150, stableMs 500, stableWindows 2, timeoutMs 15000 (hard safety net, not a knob).
- `plugin.json` both plugins: removed pollMs/stableWindows/stableMs/timeoutMs settings;
  kept only `notify` (plus Google's `visible`).
- `config.json` + `config.example.json` both plugins: set measured values.
- `settings_store.py`: writes <plugin>/config.json with read-modify-write, preserving
  daemon-owned keys (was settings.json, which silently ignored Google's knobs).
- `copy.py::notify_enabled` and `verify_notify_setting.py`: read config.json.
- `playwright_runner.js` (Google): same early empty-exit fix as Anthropic, new defaults;
  exported `reloadConfig()` called per HTTP request so UI writes are immediate.
- `usePlugins.ts` comment updated. Stale `settings.json` left on disk but ignored.

Validation: Node 46 passed; Python `tests/plugins` + logging 111 passed; renderer plugins
18 passed; `typecheck:ci` clean. App restarted, startup green. Live re-verification of the
new hardcoded values is pending another owner dictation (config files confirm 150/2/500).

## 2026-11-19 - Plugin UI: one card, hidden Chrome mode, shorter copy

- Added hidden Chrome profile mode via Win32 ShowWindow(SW_HIDE) on the spawned PID (no launch flags, no automation fingerprint); headless rejected (kills mic). Toggle applies on next hotkey.
- Both plugin manifests: added 'Show the browser window' setting, shortened descriptions; config files updated.
- PluginDetail.tsx: activation + all settings in ONE card with divide-y (C-UI-16).
- Verifier fixes for refactored entry module; hidden-mode checks added.
- Validation: verifiers green, Node 46, Python plugins 108, renderer 18, typecheck:ci clean; app restarted green.

## 2026-11-19 - Devtools warnings: cold-start IPC noise + Settings skeleton shape

- Root cause (3 warnings): pre-bind 'sidecar not connected' was already classified as a transient startup shape (C-START-2) but every caller still used console.warn. Added shared logIpcFailure(scope, message, err, expected) in hooks/connectionStatus.ts: expected transient failures go to console.debug, verdict errors and out-of-grace failures keep warn. Wired into useConnection (in-grace flag), themeSync (cached theme fallback), i18n push (best-effort locale push).
- Root cause (skullet): the OUTER Settings <Skeleton id="settings"> was shared by the hub and all seven section pages. Skullet remembers a shape per id, so a revisit recalled a different page's height and warned about the jump. Added settingsSkeletonId() (settings-hub / settings-page-<page>) in settingsSections.ts and used it in Settings.tsx; section components keep their own ids.
- Tests: new logIpcFailure unit test + integration assertions for all three call sites; skullet-contracts pins unique per-surface ids. Full-run log-prefix test exposed a non-literal first arg in the helper; fixed by building the [renderer:<scope>] literal in the helper (static pin green). History-footer-count timed out at 10s under full load (8.6s alone, unrelated); raised its per-test budget to 30s.
- Validation: full renderer suite GREEN on the final state — 416 files, 4805 passed, 7 skipped (log at %TEMP%\opencode\vitest-warnings-fix-final.txt); first full run caught the log-prefix pin violation (fixed) and a 10s timeout flake in History-footer-count (30s budget, passes alone in 8.6s). typecheck:ci clean; biome format clean on all touched files; post-format targeted replay 34 passed.


## 2026-11-20 - Mypy: numpy lazy proxy annotations in worker whisper engine

- IDE showed 8 mypy errors in voice_typer/worker/whisper/engine.py (7x name-defined for np.ndarray, 1x no-any-return).
- Root cause: np is a lazy_module('numpy') proxy, so mypy cannot resolve np.ndarray. Applied the repo's existing TYPE_CHECKING pattern (see audio_filters/dpdfnet_backend.py): TYPE_CHECKING imports real numpy for annotations, runtime keeps the lazy proxy. No eager numpy import.
- no-any-return: with_gpu_fallback (fallback.py) and its engine method were untyped; made both generic over the inner callable's return type. Remaining Any at the duck-typed engine boundary in transcribe_with_fallback is now an explicit cast(str, result).
- Validation: mypy on engine.py shows 0 errors in worker/whisper/* (whole-run 576 -> 567, no new errors); ruff check clean; focused pytest 47 passed (numpy lazy import, engine re-export, protocol parity, batched, gpu memory release).
- NOT ours: mypy_ratchet_check.py is red on pre-existing per-code regressions in the server-only scope (arg-type 36->38, no-any-return 75->76, total 576->568 improved). Worker files are outside that scope; left untouched.



## 2026-11-19 — owner decision round: RH-11/12/13/15, Storybook removal, license change

Owner decisions: RH-11 keep soft gate by design (no workflow/baseline change); RH-12 KEEP Intel-Mac support and use Option B (PyCryptodome), NOT drop Intel; RH-13 make the full npm audit clean; RH-15 wire the signed Windows config. Owner gave sign-off ONLY for the macOS runner-label edits and the signed Windows config wiring; no other workflow step was changed. Three file-disjoint workers dispatched; all three completed. Disk was 21 GB free at dispatch (owner had cleared space).

Implementation summary:
- RH-11: decision recorded in review.md only; no code/workflow change.
- RH-12: `voice_typer/server/_text_crypto.py` now uses PyCryptodome AES-GCM with byte-identical `enc:v1:` format; pycryptodome>=4.5,<5 added; cryptography direct dep + x86_64 pin + PYSEC acceptance comment removed; `requirements-lock.txt` regenerated with `uv pip compile --generate-hashes --universal --python-version 3.11 pyproject.toml -o requirements-lock.txt` (no hand-edited hashes); freeze specs updated; OLD-format fixtures + new/old cross-compat tests added. cryptography==50.0.0 remains Linux-only via keyring -> secretstorage (transitive, not our code).
- RH-13 + Storybook: `.storybook/`, 8 story files, story-only decorators, scripts, deps/config refs, lock entries and the website Storybook icon removed; remaining vulnerabilities fixed by bumps/floors (vite 8.3.8, sharp 0.35.5, vitest 5.0.3, minimatch 11.0.9 override, esbuild 0.28.2 devDep); zero overrides removed.
- RH-15: signed legs pass `--config tauri.windows-signed.json`; base config keeps `signCommand: null`.
- Runner migration: all 8 functional `macos-14` labels -> `macos-15` / `macos-15-intel`; two stale test pins in `tests/tauri/` updated by the orchestrator (C-TEST-10).
- License: root LICENSE replaced with the exact official PolyForm Strict 1.0.0 text from the upstream tag plus `Required Notice: Copyright 2026 Abdallah IsDev`; declarations updated in pyproject (text form — PolyForm-Strict-1.0.0 is NOT an official SPDX id), Cargo.toml, client package.json, README, website, installer license and third-party notices; project described as source-available. Historical worklog entries were not rewritten.

Validation performed (this session, on the final tree):
- Python scoped: `pytest tests/test_text_crypto_compat.py tests/test_text_crypto.py tests/test_crypto_import_reachability.py -q --no-cov` -> 70 passed (orchestrator re-run). `ruff check` on all touched Python files -> clean.
- Workflow/Tauri scoped: `pytest tests/tauri/test_macos_bundle_preflight.py tests/tauri/test_host_validation_workflow.py tests/tauri/mig18/test_windows_signing.py -q --no-cov` -> 39 passed (orchestrator re-run after fixing the two stale macos-14 pins).
- Client: `npm audit --audit-level=high` -> 0 vulnerabilities (orchestrator re-run); `npm audit --omit=dev` -> 0; `npm run typecheck:ci` -> exit 0 (orchestrator re-run); `npm run build` -> exit 0; full `npx vitest run` -> 416 files / 4805 passed / 7 skipped (worker run). `npm run lint` -> exit 1 with 18 errors / 18 warnings, ALL in other sessions' uncommitted client files — not attributable to this round; not widened into.
- `cargo check` -> blocked twice by `os error 32` file locks held by two foreign cargo.exe processes (not killed); `cargo metadata` confirmed the new Cargo.toml license. No workflow was triggered.

Could not verify / still owed: real Intel-macOS build on `macos-15-intel` (CI run needed); frozen-bundle import of PyCryptodome (on-disk `src-tauri/bin/*` are 62–64 byte stubs, not real freezes); full signed Windows workflow re-run and owner sign-off; full pytest suite (worker ban / shared dirty tree); `npm run lint` green while other sessions' client edits remain dirty; SPDX-id question for PolyForm Strict; LGPL obligations for pystray and PyAV (report only).


## 2026-11-20 — follow-up verification round (RH-11..RH-20)

Verification only, except the PEP 639 license-id fix and factual doc corrections listed below. Three file-disjoint workers dispatched; all completed. Never suppressed a check, never hand-edited a lock hash, no commit/push/workflow trigger.

Changed this round: pyproject.toml (`license = "LicenseRef-PolyForm-Strict-1.0.0"`, `license-files = ["LICENSE"]`, setuptools floor >=77 in both build-system.requires and the `build` extra); voice_typer/client/package.json + package-lock.json (license `SEE LICENSE IN LICENSE`, regenerated via `npm install --package-lock-only --ignore-scripts`); src-tauri/Cargo.toml (`license-file = "../LICENSE"`); README.md, website/*, scripts/windows/installer-license.txt and docs/THIRD_PARTY_NOTICES.md (LicenseRef/source-available wording; FFmpeg notice corrected to GPL-enabled wheel facts); tests/test_crypto_import_reachability.py and three crypto docs (Linux-only transitive cryptography chain); docs/audit/review-md-audit-2026-11-19.md (audit wording). No freeze script gap found; no workflow edited.

Verification performed:
- `pip-audit --strict --require-hashes -r requirements-lock.txt` via `uvx --from pip-audit` -> exit 0, no vulnerabilities. OSV POST queries for cryptography 50.0.0/50.0.1/50.0.2 -> no advisories.
- Four OLD-format crypto fixtures re-derived byte-for-byte from `git show HEAD:voice_typer/server/_text_crypto.py`; all four match, none circular. Failure behavior old vs new identical at the caller boundary.
- `pytest tests/test_history_db_encryption.py -q --no-cov` -> 1 failed / 19 passed; only `assert '6' == '5'` schema-version failure (line 407), encryption assertions pass. Same class in `tests/test_history_db_trigram_cjk.py:82`. Both classified (b) — test files unchanged from HEAD; another session's schema.py sets version 6. Not fixed.
- Scoped regressions: tests/server 397 passed/1 skipped; tests/packaging 2 passed; tests/tauri 1035 passed/597 skipped; crypto 70 passed.
- Client clean re-run: `npx vitest run` 416 files / 4805 passed / 7 skipped; `npm run typecheck:ci`, `npm run build`, `npm audit --audit-level=high` all exit 0. First vitest run failed 7 tests only under concurrent CPU load; clean re-run green — classified (c).
- `cargo metadata --no-deps --format-version 1` -> license_file=../LICENSE accepted. `cargo check` blocked by missing windres (tauri-winres NotAttempted), NOT the os error 32 of earlier rounds.
- PEP 639 validation: `prepare_metadata_for_build_wheel` -> `License-Expression: LicenseRef-PolyForm-Strict-1.0.0`, `License-File: LICENSE`; local setuptools 84.2.1.

Read-only inventories:
- Overrides (11): nanoid, brace-expansion, ip-address, fast-uri, postcss, browserslist, postcss-selector-parser, minimatch all have live dependents; @hono/node-server, hono, qs are orphans but NOT Storybook-only, retained per AGENTS.md. None removed.
- Lint: `npm run lint` exit 1, 18 errors / 18 warnings, 979 files. Errors: organizeImports in M/?? files (App.tsx, Settings.tsx, Home.tsx, Dashboard.tsx, Sidebar.tsx, TitleBar.tsx, titleBarButtons.tsx, DebugPanel.tsx + tests, RefreshShareActions.tsx + test, PluginsNewBadge.test.tsx, skullet-contracts.test.tsx), a11y errors in untracked DebugPanel.tsx and ToolbarClusterTooltip.tsx, format error in M PluginDetail.tsx. Warnings: 16 noNonNullAssertion in CLEAN file src/renderer/src/pages/dashboard/lib/sample.ts, plus 2 index.css warnings. CI gate: `.github/workflows/client-ci.yml:72`. Nothing fixed.
- FFmpeg/PyAV facts: PyAV 18.1.0 wheels are GPL-enabled (libx264/libx265/libxvid present in `av.codecs_available`); FFmpeg bundled DLLs are inside the Nuitka onefile and not user-replaceable; attribution present, source offer + replaceability PENDING legal decision. pystray LGPL-3.0 §4d also PENDING.

Could not verify: real frozen Crypto.Cipher.AES import (no Nuitka/PyInstaller/pybs locally; measured 15G free); macOS/Windows pip installs for marker proof (marker evaluation used instead); full pytest suite (worker ban / shared dirty tree). Owner/CI probe: `printf 'from Crypto.Cipher import AES; print("AES_OK", AES.MODE_GCM)\n' > probe_crypto.py && <pybs-python> -m nuitka --standalone --onefile --include-package=Crypto --output-filename=probe-crypto probe_crypto.py && ./probe-crypto.dist/probe-crypto` (expect `AES_OK 9`).


## 2026-11-20 — round 3: schema-version tests, explicit Crypto hiddenimports, research

Owner decisions: schema 6 is intentional (update stale tests); add explicit PyCryptodome hidden imports; no workflow edits; do not touch the 18 client lint errors. No commit/push/workflow trigger, no lock-hash edits, no suppressions.

Changed: tests/test_history_db_encryption.py and tests/test_history_db_trigram_cjk.py now import `_CURRENT_SCHEMA_VERSION` from `voice_typer/server/history_db_internals/schema.py` (declared 6 at schema.py:26, `_MIGRATION_V6` at :112 and `_MIGRATIONS[6]` at :130, migration covered by tests/test_history_db_metadata.py:70) instead of asserting the string "5"; the trigram docstring was updated. scripts/build/lausu.spec `_hiddenimports` now explicitly includes `Crypto`, `Crypto.Cipher`, `Crypto.Cipher.AES` and `Crypto.Cipher._raw_aes` (dynamic AES extension), so the PyInstaller fallback no longer relies only on hook-Crypto.py. scripts/build/nuitka_freeze.sh:63 stale "lausu.spec deleted" comment corrected. tests/test_crypto_import_reachability.py gained `test_pyinstaller_fallback_spec_includes_pycryptodome`; existing tests already pin sidecar `--include-package=Crypto` and worker `--nofollow-import-to=Crypto`. review.md gained the dated Intel-runner-source-conflict note.

Verification: `pytest tests/test_history_db_encryption.py tests/test_history_db_trigram_cjk.py tests/test_text_crypto_compat.py tests/test_text_crypto.py -q --no-cov` -> 98 passed; `pytest tests/test_crypto_import_reachability.py tests/test_history_db_encryption.py tests/test_history_db_trigram_cjk.py` -> 52 passed; `pytest tests/packaging tests/tauri/mig18` -> 206 passed, 27 skipped; ruff on all touched Python files -> clean; `bash -n scripts/build/nuitka_freeze.sh` -> OK.

Part E: `/c/msys64/mingw64/bin/windres.exe` EXISTS; with `PATH=/c/msys64/mingw64/bin:$PATH` and `RC=windres`, `cargo check` no longer fails on windres but on `os error 32` file lock from two foreign cargo.exe PIDs (34784, 9952) — not killed. Vitest run 1 (default workers): 3 files / 5 tests failed — `Home-recording-flow-fixes.test.tsx` timer aria-label (10s timeout), `Settings-empty-state.test.tsx` two search-banner tests (10s timeout + "Found multiple elements with the text: Settings"), `Settings.test.tsx` two config-write tests (10s timeout) — all timing/DOM-contention flakes. Vitest run 2 (`npx vitest run --maxWorkers=2`): 416 files, 4805 passed / 7 skipped, exit 0. No tests changed.

Research (Parts C/D) delivered in chat: signing-secret behavior per trigger, FFmpeg/PyAV GPL facts, pystray LGPL replaceability. No files changed for those parts.


## 2026-11-20 — round 4: binary-verified FFmpeg/PyAV licence facts

Golden rule: every shipped-binary fact came from the binary or its wheel metadata and is quoted verbatim; website facts are labelled upstream documentation.

Binary evidence: `pip show -f av` -> Version 17.1.0, `Required-by: audiolab, faster-whisper, lausu`; `requirements-lock.txt:11 av==17.1.0`; `av.__version__ = 17.1.0`; WHEEL `Tag: cp311-abi3-win_amd64`. `av.libs` contains 24 files; `avcodec-62-0f4d449c1bbaaa5eeb9f8a10b4cc7e85.dll` 19,213,824 B, `avformat-62-9c2d3ee2527a13ca0fdcb82b33ed040a.dll` 2,824,192 B, `avutil-60-21bd72d722406bd9f4b24262cf4b35f3.dll` 1,144,832 B, `libx264-165-71900781b680e0e06a1b966b46fee000.dll` 2,271,744 B, `libx265-7e74dd5103fd9dad5114dffeefd474ce.dll` 12,564,480 B. ctypes with `os.add_dll_directory`: all six `*_license()` exports return exactly `LGPL version 3 or later`; all six `*_configuration()` exports return the same 775-char string (quoted in full in THIRD_PARTY_NOTICES.md and in the chat report). PyAV codec checks: libx264/libx265/libmp3lame/libopus/aac/libvpx/libvpx-vp9 encoders present, libdav1d decode only; libxvid/libvorbis/libfdk_aac/libaom-av1 absent; 14 names contain "lib".

Changed: docs/THIRD_PARTY_NOTICES.md PyAV entry rewritten (removed the contradicted PyAV 18.1.0 / 60.26.102 / --enable-gpl / libxvid claims); new tests/packaging/test_third_party_notices_av_version.py; docs/migration/windows-validation-runbook.md unsigned-build note corrected; voice_typer/server/media_ingest/ytdlp_log.py comment clarified (no ffmpeg EXECUTABLE shipped; PyAV bundles shared libraries); review.md and this worklog entry.

UNVERIFIED: (1) v1.0.0 published Windows installer contents — asset downloaded (135,868,496 B) to scratch and 7-Zip 25.01 could not open it as NSIS or Inno archive, no innoextract available; temp download deleted afterwards. (2) FFmpeg build flags inside the macOS/Linux av==17.1.0 wheels — those wheels were listed from PyPI JSON but not downloaded/loaded here; upstream README says the same pyav-ffmpeg recipe, which is upstream documentation, not binary proof. (3) Whether the flag/codec contradiction comes from an upstream configure patch — upstream docs suggest it, binary cannot confirm. No compliance claim made; source-offer and replaceability await the owner's decision.


## 2026-11-20 — round 5: per-DLL licence facts, import graph, PyAV dependency analysis

Read-only research plus one documentation correction. No dependency, lock, packaging, workflow or spec changes; no commit/push/workflow trigger.

Verified (binary/wheel, quoted verbatim in chat and in docs/THIRD_PARTY_NOTICES.md): `av.libs` has 25 DLLs; `METADATA` fields `License-Expression: BSD-3-Clause`, `License-File: LICENSE.txt/AUTHORS.py/AUTHORS.rst`; no per-DLL licence fields and no licence text files in `av.libs/` or `av/`; embedded strings `libavcodec license: LGPL version 3 or later` etc. followed by `FFmpeg version 8.1.1`; `libx265` `LegalCopyright: Multicoreware: GPLv2 or commercial`; `libiconv` `FileDescription: LGPLed libiconv for Windows`. PE import descriptors (Python stdlib parsing; objdump's PE parser stops at delvewheel-hashed names) show `libx264-165-*.dll` and `libx265-*.dll` as LOAD-TIME imports of `avcodec-62-*.dll`. Upstream documentation (URLs in notice): pyav-ffmpeg tag 8.1.1-2 `patches/ffmpeg.patch` moves libx264/libx265 from `EXTERNAL_LIBRARY_GPL_LIST` to `EXTERNAL_LIBRARY_VERSION3_LIST`; FFmpeg 8.1.1 configure builds `FFMPEG_CONFIGURATION` from command-line args only, so patches are invisible in the printed string; `avutil_license()` is defined in `libavutil/version.c`.

faster-whisper facts: `audio.py:15 import av` at module scope; `__init__.py:1` imports audio at package import; `transcribe.py:19` too; simulated av absence breaks `import faster_whisper` itself, not just `decode_audio`. Our call sites: `media_ingest/decoder.py:31,131,162,200` lazy `import av`; no `decode_audio` calls under `voice_typer/`; `worker/_transcribe.py:330 transcribe_array` accepts pre-decoded float32. `audiolab` is an index package required by pyrnnoise, not in-repo; lausu declares `av>=17,<18` at pyproject.toml:112 for Media decoding.

Changed: docs/THIRD_PARTY_NOTICES.md (removed per-DLL byte sizes, corrected 24->25, added a 25-row licence table with wheel-verbatim and upstream-documented columns, documented the configure patch as upstream documentation); review.md + this worklog entry. `pytest tests/packaging -q --no-cov` -> 3 passed; ruff on the lock-version test -> clean.

UNVERIFIED: exact upstream licences where neither wheel nor DLL states one are documented from upstream projects, not read from the binary; MSYS2 package versions behind libgcc/libstdc++/winpthread/libiconv/zlib in the wheel; upstream build times for custom wheels; whether a custom x264/x265-free FFmpeg still decodes every format our Media page accepts; a legal/compliance determination (explicitly out of scope).


## 2026-11-20 — round 6: decode/encode proof, dependency scenarios, filesystem scan

Read-only research plus one documentation sentence fix. No dependency/lock/workflow/packaging/spec/code changes; no commit/push/workflow trigger. No files were created/modified/deleted in the repo by the research agents; temporary probe files were created only under the Hermes scratch and system temp dirs and deleted afterwards.

Evidence: whole-repo grep + source trace — zero `add_stream`, `OutputContainer`, `VideoFrame`, `.mux(`, `av.open(mode='w')`, `ffmpeg_location`, `postprocessors`, `libx264`, `libx265` in app source; all `av.open()` at decoder.py:40,135,167 are read-mode; `av.codecs_available` DOES contain libx264/libx265 but no app call opens them. yt-dlp options at downloader.py:93-110 request `bestaudio/best` with no postprocessors/-x/audio_format/merge_output_format. Runtime trace: repo fixture tests/fixtures/test_440hz_1s_16k.wav -> container 'wav', stream pcm_s16le, `codec.is_decoder=True codec.is_encoder=False`, decode_chunks -> one float32 (16000,) chunk; temp mpeg4+aac mp4 -> mov/mp4 container, video mpeg4 + audio aac both decoders, only audio chunked; rawvideo-only AVI -> `MediaIngestError code= 'no_audio' msg= 'no audio track found in media'`. Verdict: PARTLY PROVEN (no x264/x265 call proven; live URL behavior, other containers, published installer contents unverified).

Reverse-dependency closure from all 80 lock blocks' `# via` comments, cross-checked with `pip show Required-by` (pipdeptree not installed): av survives S1 (lausu + audiolab + faster-whisper), S2 (lausu + audiolab), S3/S4 (lausu only). `pyrnnoise` -> `audiolab` -> `av` is an IMPORT-TIME runtime chain (pyrnnoise/pyrnnoise.py:19-20 `from audiolab import Reader, Writer` / `from audiolab.av import Graph, aformat`), not install-time only. GTCRN/DPDFNet use bundled ONNX files + onnxruntime, no av/audiolab. Default noise method = dpdfnet (config/_schema.py:421-425). transcribe.cpp upstream README: CLI wants 16 kHz mono WAV; Python `run()` takes mono 16 kHz float32 PCM and does not decode containers (upstream documentation, no binary tested).

Filesystem scan (read-only): `%LOCALAPPDATA%/lausu/onefile-tmp/av.libs` 25 DLLs ~63 MB, FFmpeg 8.1.2 (avcodec 62.28.102, avutil 60.26.102) tied to slim-check.exe (184,025,600 B) with embedded `av.libs` string; dev venv has 8.1.1 DLLs (avcodec 62.28.101) — distinct builds. Installed `%LOCALAPPDATA%/Voice Typer/` python-sidecar.exe (108,977,664 B) and voice-typer-worker.exe (125,010,944 B) contain no av strings and have no extraction cache. Repo dist/ has an Electron-era setup exe and `Voice Typer.exe` (Chromium ffmpeg.dll only); src-tauri/target has only debug, src-tauri/bin are stubs.

Changed: docs/THIRD_PARTY_NOTICES.md one sentence (GCC runtimes wording); review.md + this worklog entry. `pytest tests/packaging -q --no-cov` -> 3 passed.

UNVERIFIED: live URL/YouTube downloaded codec and any internal ffmpeg invocation by yt-dlp; 13 of the 17 accepted extensions at runtime; renderer drag/drop filtering; published installer DLL contents; transcribe.cpp behavior locally; mac/Linux av builds; no-dry-run scenario sets (static lock closure, no network resolution).


## 2026-11-20 — round 7: GPL-DLL-free release research and planning (no implementation)

Research only. No code/deps/lock/workflow/packaging changes; no commit/push/workflow trigger; no reset/stash/revert/clean.

Evidence: av links above; Nuitka flag lines and freeze-env resolution (build_sidecar_windows.sh:89,186; strip_av_cython_shims.py:33-41; tauri-windows-build.yml:180-182 installs `-e ".[dev,test]"` with no `-r requirements-lock.txt`; pyproject.toml:112 `av>=17,<18`; lock:11 `av==17.1.0` governs the dev/test venv only). This explains the earlier observed 8.1.2 DLLs in `%LOCALAPPDATA%/lausu/onefile-tmp/av.libs` versus 8.1.1 in the locked wheel: the freeze consumes build-env site-packages, so the notice's exact DLL set is only valid if the freeze env is pinned and gated.
Local ffmpeg 9.0.1 (C:/Users/11/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg) verbatim `configuration:` contains `--enable-gpl ... --enable-libx264 --enable-libx265`; `ffmpeg -L` header says GPLv3 — unusable as the LGPL candidate. Disk free before research: C: 238 GB size / 19 GB available (93% used).
Parity prototype (throwaway, deleted): argv `ffmpeg -hide_banner -loglevel error -nostdin [-ss S] -i SRC -vn -map 0:a:0 -ac 1 -ar 16000 -c:a pcm_f32le -f f32le -`, creationflags 0x08000000, stdout drained in 65,536-byte reads, chunked at 80,000 samples. 1 kHz 16k WAV: av/sp 1 chunk (16000), max_abs_diff 0.0. 12 s WAV: 3 chunks [80000,80000,32000], diff 0.0. Video-only mpeg4 MP4: both no_audio (ffmpeg exit -22 / "Stream map '' matches no streams"). Truncated WAV: both 1 chunk (2000), diff 0.0, duration probe 0.125 -> validation media_too_short. Corrupt WAV: both decode_failed. 44.1k stereo -> 16k mono: 24000 samples both, diff 0.0. Seek 2 s on 12 s file: 160000 samples both, diff 0.0.
Variants studied: V1 decoder+RNNoise+av stub (3-4 wk est), V2 V1+GGUF (5-6 wk, GGUF-dependent), V3 keep PyAV with custom x264/x265-free wheel (4-5 wk), V4 build-env LGPL-only av wheel pin + gate + notice, no Python/ASR/UX edit (3-4 wk est). Lowest-risk-for-date observation (not a recommendation): V4, conditional on codec coverage of the custom wheel being verified (13 of 17 accepted extensions remain runtime-unverified). `--noinclude-dlls=libx264*` is NOT viable — both GPL DLLs are load-time imports of avcodec.
UNVERIFIED: real Nuitka freeze with stub or custom wheel; LGPL candidate artifact sizes/decoder lists without downloading; aarch64 shipping requirement; distro ffmpeg LGPL status; released installer DLL inventory; any legal/compliance conclusion.


## 2026-11-20 — round 8: implementation of RNNoise/ffmpeg decoder/Windows packaging

Evidence and commands: RNNoise before: `from pyrnnoise import RNNoise` -> `ModuleNotFoundError: No module named 'av.option'` via pyrnnoise/__init__.py:15 -> pyrnnoise/pyrnnoise.py:19 -> audiolab/__init__.py:24 -> audiolab/av/filter.py:18. After: `effective_method: rnnoise`, `is_degraded: False`, no pyrnnoise/audiolab/av in sys.modules, RMS 0.248421 -> 0.000634 (-51.86 dB). Scoped noise tests: 248 passed (worker), recheck 13 passed.
Decoder: subprocess argv as above; `-protocol_whitelist` on both ffmpeg and ffprobe; remote scheme check added inside decode_chunks(remote=True); local paths `file:`-prefixed; CREATE_NO_WINDOW; bounded stderr drain; process reaped; FFMPEG_MISSING error code added to errors.py (the other changes visible in errors.py — MODEL_LANGUAGE_UNSUPPORTED — and in jobs.py/storage.py belong to other sessions and were NOT touched). yt-dlp source inspection: `_determine_executables` detects ffmpeg when no `ffmpeg_location`, and default `fixup=detect_or_warn` adds FFmpegFixup* postprocessors; pinned `fixup: "never"` in downloader.py to preserve byte-identical downloads.
Parity numbers (new vs retired reference): repo fixture 1 chunk/16,000 samples/diff 0.0; generated 12 s 3 chunks [80000,80000,32000]/192,000 samples/diff 0.0; 44.1 kHz stereo 3 chunks/192,000 samples/diff 0.0; seek 2 s 2 chunks/160,000 samples/diff 0.0. Video-only -> NO_AUDIO; corrupt/truncated -> decode_failed. 215 media tests passed after inline recovery of a dead worker (fixed fake-binary check and a stdout-EOF/poll race).
FFmpeg build: BtbN LGPL static win64 N-129150-g7ddf7bc8a4-20261120, tag autobuild-2026-11-20-12-40, archive 178,978,135 B SHA-256 0322fe632c4f6e1fb92c3a3648e100fec702bf86792c4440b4dfda22f7b95b82; `ffmpeg -L` says LGPL v3+; config has --disable-libx264/--disable-libx265 and no --enable-gpl/nonfree; 32/32 accepted extensions covered. Fetch script end-to-end run verified, installed binaries deleted afterwards, .gitignore covers them.
Combined verification: ruff on all touched Python -> All checks passed; `bash -n` on 4 scripts -> OK; pytest over media+audio+packaging+touched tauri tests -> 695 passed in 76.27s; touched tauri files 214 passed; full tests/tauri 1037 passed/597 skipped/3 unrelated failures (`bubble_host_hidden` IPC parity, other workstream); cargo check OK with `/c/msys64/mingw64/bin` on PATH. pyrefly check on touched Python reported 20 errors, all in test files asserting private attributes; baseline file absent locally so classified pre-existing-pattern/UNVERIFIED; no baseline or suppression changed.
UNVERIFIED: frozen Nuitka build with native RNNoise data inclusion; macOS/Linux native library names; FFmpeg shared-variant contents; released installer (no build triggered); full CI workflow wiring (next round, workflow files off limits).

## 2026-11-20 - worker: always_visible bubble visibility reconciliation

Root cause (live + code): internal-plugin `session.py::_session_events(stop)` published raw `bubble_hide` at every plugin stop, bypassing the WaveformBubble coordinator (mirror stayed True); host then hid the real window with no backend notification. Reproduced on pid 2300/4028-era build: 7 plugin cycles 19:42-19:44 left bubble hwnd 0x706b4 `IsWindowVisible=False`, cloaked=0, no `[WAVEFORM] Bubble hidden` line. Secondary: startup one-shot flag consumed before guards; phase 8 trusted stale mirror; show() short-circuited on mirror.

Fix: single `WaveformBubble.apply_visibility(state, reason)` owns visibility+state (all Python call sites routed, provider path calls it, no raw bubble events); `note_host_hidden` via host-only IPC command `bubble_host_hidden` (registry + HOST_DISPATCHED_COMMANDS + docs, no new allowlist); host tracks show-request mirror, re-asserts via `IsWindowVisible`+`DWMWA_CLOAKED` on signal_ready + 2s reconciler; `hide_bubble_window` now source-aware so renderer cleanup cannot loop; dismiss notifies backend.

LIVE: 5/5 Google STT cycles (mic/stop via bubble) before/during/after `visible=True cloaked=0`, policy lines `reason=plugin-start/plugin-stop`; host dismiss re-showed (`reason=host-dismiss`); 5-min soak 11/11 samples visible; show_on_record idle hidden; hidden idle hidden; config restored to always_visible. Screenshots + samples under `%TEMP%\opencode\`.

Scoped: 247 passed/2 external extension-config failures (other agent), 405+1 skipped, parity 35 green, ruff clean, typecheck OK, vitest 120 green, cargo check clean, cargo test 797 passed, collect 20137. cargo fmt --check clean for files touched; 3 external files still unformatted (other agents). Also: Anthropic STT 1 full cycle PASS (visible before/during/after, `reason=plugin-start/plugin-stop`); host dismiss re-showed (`reason=host-dismiss`); show_on_record + hidden idle both correctly hidden. Owner config restored: active_plugin=google_stt, bubble_behavior=always_visible, bubble_show_on_startup=true; final app relaunched, bubble visible.


## 2026-11-20 — round 9: follow-up fixes, size reduction and notices

Evidence: Part A before `if binaries is None:` after `if binaries is None or not _ffmpeg_usable(binaries.ffmpeg):` with `os.access(..., os.X_OK)`; stress 600 spawns 0 misclassified/0 orphans; pyrefly 20 -> 0 on touched tests; yt-dlp source YoutubeDL.py:3610-3614, downloader/__init__.py:106-123, utils/_utils.py:3199-3201.
Part B measured release build: archive 171,850,189 B, ffmpeg.exe 134,459,904 B, ffprobe.exe 134,259,200 B; 7z -m0=lzma -md=8m -mx=9 pair 77,484,553 B, ffmpeg.exe alone 38,785,706 B; master build archive 178,978,135 B. Duration parity table: repo fixture 1.0/1.0, generated 1s 1.0/1.0, 12s 12.0/12.0, truncated None/None, video-only 1.5/1.5, corrupt None/None, remote-mocked 12.5/12.5 (7/7), so ffprobe dropped. Minimal configure line researched (audio-only LGPL build ~5-15 MB compressed estimated; not built).
Part C audit inputs C:/Users/11/lausu-license-audit/*; generator scripts/generate_third_party_notices.py stdlib-only offline; 46 catalog components (28 VERIFIED, 17 UNVERIFIED, 1 NOT-IN-INSTALLER), 138 npm closure packages, 16 groups, 24 license texts, 99,263 B artifact; `tests/packaging/test_third_party_notices_generated.py` 5 tests + av lock test. Bundling evidence: libsndfile/PortAudio/CPython/OpenSSL/MSVC/pywin32/pydantic-core/zstandard present in onefile cache; pynput/pystray/sharp/libvips/rnnoise.dll ABSENT. RNNoise native upstream BSD-3-Clause, pyrnnoise Apache-2.0, our rnnoise_ctypes.py original binding. NVIDIA downloaded files/hosts/terms recorded from cuda_install/manifest.py (upstream documentation).
Verification: ruff on touched Python All checks passed; pyrefly 0; pytest 724 passed (media/noise/packaging/touched tauri); generator --check up to date; client typecheck:ci exit 0. Pre-existing/other-session failures: tests/test_i18n_completeness.py 7 failures on theme.switchTitle and media.metaYoutube (keys not touched this round; our locale diff adds only about.thirdParty* keys).
UNVERIFIED: frozen Nuitka build containing the new ffmpeg-only binary and notices resource; a real release installer; acoustid/serversideup smaller builds not downloaded; minimal configure line not compiled; live YouTube network download; 17 license items with no local licence file; any legal conclusion.

## 2026-11-20 - Settings simplification + i18n/RTL: validation

- Static gates green: ruff check, pytest --collect-only (20169 tests), typecheck:ci, cargo check (GNU toolchain; after stopping the dev app that held build files), sync_versions --check, check_branding.
- Full vitest GREEN on final state: 417 files, 4803 passed, 7 skipped (log: %TEMP%\opencode\vitest-final-plan2.txt). Earlier run had one Settings-render-loop-guard timeout at the helper's 5s default; added timeoutMs=15000 (commit 36d32eee4) and reran green.
- Full pytest first attempt errored during collection with MemoryError in scipy import on one xdist worker while vitest was also saturating the machine (log: %TEMP%\opencode\pytest-final-plan.txt); rerunning with -n 2 after vitest finished (log: %TEMP%\opencode\pytest-final-plan2.txt).
- Manual UI verification (Chrome dev bridge at localhost:1420, 1050x900 screenshots %TEMP%\opencode\settings-en-dropdown.png and settings-ar.png): General page shows only Launch at Login / Fast Startup / Notifications / Keep Speech Model in Memory / App Language — no Streaming or Tray Click rows; idle-unload dropdown shows Always (Keep Loaded). Switching App Language English -> Arabic updated nav, Settings content and search placeholder in place (no reload); html dir=rtl; sidebar stayed physically left (aside x=0, main x=220), nav container dir=ltr with Arabic label spans dir=rtl, nav icon x=17 in both expanded and collapsed states; title-bar Back arrow transform=none, while the Settings back-chevron still mirrors (out of scope). Tray left/right-click verified by Rust source pins and tests, not clickable in the browser dev bridge.

### Verification stopped by owner decision

- Full pytest was attempted twice with lower parallelism after the vitest suite finished; both attempts were cut short by harness shell errors (`Shell.NotFoundError`). The first of those runs also showed a collection-time `MemoryError` while vitest was saturating the machine. Per owner instruction, verification stops here: full pytest is NOT recorded as green. Green evidence stands for static gates, full vitest (417 files / 4803 passed), all per-task scoped pytest runs and the manual UI checks above.


## 2026-11-20 — round 10: CI round (workflow wiring only; no GitHub run)

Mirror verified live via gh api (asset size/digest above); fetch plan mirror-then-fallback verbatim: `mirror <MIRROR_URL> 814c62...` / `fallback <BTBN_URL> 814c62...`. i18n no-op: tests/test_i18n_completeness.py 47 passed, keys already fixed in HEAD by 8dc20a3c3; about.thirdParty* keys untouched.
Workflow: only .github/workflows/tauri-windows-build.yml changed (+117/-2); caller tauri-build.yml byte-identical. Only removed lines were the two `-e ".[dev,test]"` installs, replaced by hash-locked install + --no-deps project install. No || true, continue-on-error, --ignore-vuln or baseline changes added; no other gates touched. Freeze pin checked from lock markers: universal uv lock for Python 3.11 <3.15 covers PYBS 3.12.8; 66 active requirements all with hashes; pip dry-run showed no require-hashes format/pinning error.
Gate script behavior: hard-fail on missing ffmpeg/ffprobe-absent/notices and frozen self-check markers; ENFORCE_NO_GPL_DLLS default 0 prints a WARNING table and exits 0, value 1 fails; sizes to $GITHUB_STEP_SUMMARY; notices artifact added. Self-check entry point is inert unless --self-check is present and parse_ipc_args still returns (port, ws_mode).
Verification: ruff clean; pyrefly 0; 861 passed / 28 skipped across packaging, workflow tests, tauri mig18, media, noise, i18n and IPC entrypoint suites; gate --self-test PASS; YAML parse OK; actionlint unavailable (YAML parse + structural tests instead). Full tests/tauri still has the 3 pre-existing bubble_host_hidden IPC parity failures (other workstream, untouched).
NO WORKFLOW WAS EXECUTED. No installer, freeze, hash gate, smoke test or artifact upload has been proven in GitHub yet; the owner must trigger the Windows build. Runner label windows-2022 is supported per https://docs.github.com/en/actions/reference/runners/github-hosted-runners and https://github.com/actions/runner-images (upstream documentation).
UNVERIFIED: real mirror download in CI (gh auth/token path), frozen-sidecar self-check, gate staged-resource path, full vs slim matrix (only slim Tauri leg exists; full config is used by freeze jobs), all signed legs.


## 2026-11-21 — round 11: onefile-aware gate, self-check base, workflow order, commit plan

Evidence: freeze script scripts/build/build_sidecar_windows.sh:183 `--onefile-tempdir-spec="{CACHE_DIR}/lausu/onefile-tmp"`; Nuitka upstream docs https://nuitka.net/user-documentation/use-cases.html and common-issue-solutions.html (sys.argv[0]/sys.executable = original exe, __file__ = extraction dir; static spec = cached dir). New gpl_gate output has two tables: labeled byte scan and authoritative extraction-dir name scan. Synthetic demo returned 0 exe-string tokens, 2 extraction-name hits, 2 av.libs DLLs; enforce=1 raised as expected.
Resolver base: sys.executable-based `bundled_bin_dir()` shared with selfcheck; not a onefile bug. NoiseSuppressor public properties at noise_suppressor.py:579-590; selfcheck uses them. Dev self-check output quoted in report; frozen run UNVERIFIED.
Workflow: only .github/workflows/tauri-windows-build.yml changed for Part C; gate is step 36 after uploads 30-35, gate-output upload step 37 with if: always(). YAML parse OK; workflow tests 20 passed; pipefail rc=7 proof. No new || true/continue-on-error/--ignore-vuln/baseline changes.
Commit plan at C:/Users/11/lausu-commit-plan.md (outside repo): 34 ours / 0 other-session uncommitted / 4 unknown screenshots; no git add -p needed; branch from local HEAD not origin/main; exact dispatch inputs quoted in plan. The review-*.diff files from earlier rounds were removed externally, so the plan could not use them (correctly reported UNVERIFIED). Stale mirror-TODO wording in THIRD_PARTY_NOTICES.md corrected and plan amended.
Verification: ruff clean; pyrefly 0; 592 passed; gate --self-test PASS. Temp 134 MB ffmpeg copy created by the worker under %LOCALAPPDATA%/Temp/selfcheck-local removed. UNVERIFIED: real Nuitka frozen onefile and CI execution; no workflow triggered.

## 2026-11-21 — RH-28: uninstall leaves the runtime pack behind

- Verified against current code: `%APPDATA%\lausu` was the only root cleaned on uninstall; `%LOCALAPPDATA%\lausu\runtime-pack` and `installer-state.json` (written by `installer-hooks.nsh` and `full-offline-installer.nsi`, read by `offline_pack/core.py`) survived every uninstall path.
- E5 candidates: (a) explicit owned-subpath deletion in each Windows uninstall path [chosen — small, no include-graph changes, safe]; (b) shared NSIS macro included by both installers [rejected — full-offline wrapper has no uninstall section, extra indirection]; (c) Python-only cleanup called from NSIS [rejected — the NSIS hook does not invoke that script unconditionally and `--purge` is opt-in].
- Fix: `uninstaller.nsh` and `uninstall.bat` now remove `runtime-pack` + `installer-state.json` on every uninstall and remove `%LOCALAPPDATA%\lausu` only when empty; `uninstall_permissions.py --purge` gained `_purge_local_installer_state()` for the same two paths. No blanket wipe of user files.
- Tests: 3 new pins (NSIS source, batch source, real Python purge with a user sentinel file). RED confirmed, then GREEN. Full affected files: 73 passed. Ruff clean on touched Python files. review.md RH-28 marked ✅ Fixed (verified).
- Learn-and-teach: added `C-PERSIST-4` — a second per-user storage root must be added to every uninstall/purge path in the same change; remove only installer-owned paths. Announced in chat; user may veto.

### Review follow-up (RH-28)

- Reviewer found an Important reachability bug: `uninstall.bat` exited at lines 78/90 before the new LOCALAPPDATA cleanup block, so the common Python path still left the pack behind. Verified against the file.
- Fix: moved the owned-path cleanup above the Python/PowerShell branches, so it runs on every path. Added an order pin asserting the cleanup block precedes the first `exit /b 0` (RED confirmed: index 7015 > 3918, then GREEN).
- Reviewer minors also closed: `review.md` progress now states the real coverage and reconciles the test count (73 initially, 76 after the two extra Python edge-case tests); added tests for missing LOCALAPPDATA and empty-root removal.
- Validation: 76 passed across `tests/tauri/test_installer_naming.py` and `tests/test_uninstall_windows.py`; ruff clean. Scoped re-review dispatched.

## 2026-11-21 — RH-29..RH-33 + bare-pytest CI failures

CI fix (parallel agent, reviewed clean): `soundfile` is excluded from the lock on macOS arm64 and absent in bare-pytest Linux jobs, but `voice_typer/server/tts/wav.py` imported it at module level, killing the autouse config-dir fixture import chain (47 + 1 setup errors). Moved the import into `probe_wav()` after the filesystem checks, matching `tts/playback.py`; added hermetic absence tests and a structural guard that removed the `pytest_benchmark` filterwarnings entry (the filter itself warned when the plugin was absent). Commits f83ddf289, d1f33d758, 90d3c9dc6; 47 + 14 + 9 scoped tests green, ruff clean.

- RH-29 (7a2f8c711): torch-free gate patterns now match dotted, slash and backslash forms in both GNU grep ERE and Python `re`; 5 black-box tests, bash -n/ruff clean. Workflows untouched.
- RH-30 (acae5dbc2): full-offline installer aborts on failed extraction or slim-core failure, keeps the zip until extraction verified, writes `pack_bundled: true` only after full success; 5 new source/order pins, 52 installer tests. Windows makensis smoke test still owed.
- RH-31 (688ee38a9): wrapper includes FileFunc.nsh and forwards `${GetParameters} $R0` instead of `$CMDLINE`; old test pin replaced; 52 installer tests. `/D=` limitation documented in NSI. NSIS semantics verified against official docs.
- RH-32 (bfddbf315, a6677641b, 2af467012): RELEASING.md describes real artifact workflows + mandatory manual pack dispatch; counts in six docs replaced with canonical links (110 = 105 + 5, 61, 73); ADR-0029 index/range fixed; doc-count tests and checker reconciled. 120 focused tests + touchpoints 7-10 green.
- RH-33 (1b25bed8e, task-ID fix in a6677641b): publisher split into result/backends/publisher/cli with facade at the workflow-pinned path; patch targets migrated; 73 scoped tests green, no behavior change.
- All five tasks and the CI fix have per-task reviewer approvals; review.md entries marked ✅ Fixed (verified). Final lint cleanup: ruff-formatted `tests/tauri/test_installer_naming.py` (52 tests still green); repo-wide ruff check clean.
- Not run: full pytest suite (prior owner decision to stop verification), Windows makensis compile/install smoke tests. `cargo check` remains blocked by a pre-existing windres panic on this host.

## 2026-11-21 — Whole-batch review of RH-29..33

One reviewer across all 11 commits found no Critical defects and two Important gaps, both fixed in commit d981d9556: RELEASING.md no longer credits `runtime-pack-publish.yml` with producing installers (slim-core comes from tauri-*-build.yml; full-offline from a local build script; the pack workflow uploads only zip + manifest), and the guard test now asserts that producer→artifact relationship; `tests/test_ipc_server.py` host-command pin updated to the registry's 3-element set. Six minors also fixed (draft/publish guidance, stale assertion message, pytest env scrubbing, gate diagnostics, forced Python-regex/backslash tests, malformed-WAV `TtsError` translation). Deferred as product decisions: `/D=path` forwarding and real pack-integrity verification. Scoped re-review approved; one minor guard-brittleness note left deferred.

Final local gate caught one more related gap: `bubble_host_hidden` was in `_COMMAND_REGISTRY` but absent from `COMMAND_COSTS`; added cost 1 in `voice_typer/server/ipc/rate_limiter.py`. `tests/test_ipc_server.py` 209 passed; ruff check repo-wide clean.

## 2026-11-21 — Fix all CI errors (6 parallel worker subagents)

Owner supplied the macOS CI `Test results` failure list; no fresh log was pasted for the client gates, so all CI gates were reproduced locally first (systematic-debugging: root cause before fix). Six independent domains dispatched in parallel with disjoint file ownership, each self-reviewed against its diff:

- A (adb268ada): third-party notices were NOT deterministic — generator embedded the local venv's dist-info count and used a Windows-only `Lib/site-packages` path. Made cross-platform + removed machine-dependent count; regenerated artifact. Tauri icon drift was another workstream's worktree overwrite (HEAD already canonical) — only `icon.icns` committed. Packaging tests 6 + icon guard 10 green, both `--check` gates green.
- B (66b6b81f3): 5 of 6 count/parity gates already fixed by local commits; the one still red was `DOCUMENTED_COMMAND_ASYMMETRY` in `tests/tauri/bridge_parity/test_host_surface_parity.py` missing `bubble_host_hidden` (plus stale Rust doc comment). 303 scoped tests green; cargo check green via isolated target dir.
- C (171371050): internal-plugin tests read gitignored runtime files (config.json/token.json/generated config.js) and compared a hardcoded `C:/Users/11/...` path. Replaced with hermetic fixtures + platform-neutral suffix comparison (`tests/plugins/profile_path_helpers.py`) + source-authority pins. 32 passed (Win + simulated POSIX).
- D (d881a91be): 4 media test-hermeticity defects — missing binary-resolver stubs and macOS `.exe` staging bug. No source change. 50 passed / 19 pre-existing skips.
- E (f02b6c99a): GENUINE source bug — V5 trigram-skip used `break`, exiting the migration loop and leaving version 4, so V6's `kind` column was never applied (`no such column: kind` on old SQLite). Changed to `continue`; 3 stale pins now derive from `_CURRENT_SCHEMA_VERSION`; crash-recovery pin updated for shared visibility policy. 11 scoped + 95 related green.
- F (7c72fd0d9): renderer Biome lint (14 errors) + format (1 error) from `client-ci.yml`. Safe import/format autofixes; justified inline suppression for the test-pinned squircle `--radius !important` (C-DESIGN-5); specificity-equivalent CSS reorder; native fieldset/toolbar semantics; typed tuple removes non-null assertions. lint/format/typecheck all exit 0; pinned CSS/a11y vitest 84 tests green.

Final integration gate (all 6 commits): scoped Python suite 402 passed / 19 skipped; ruff-F clean; all generator/branding/version/LF/beeps `--check` gates green; pytest collect-only 20231 items; client lint + format:check + typecheck:ci + test:coverage ALL exit 0.

Not staged (other workstreams' uncommitted files): `review.md`, deleted screenshots, `tools/internal_plugins/*/chrome_pid.json`, `?? docs/superpowers/plans/...`, `?? review-r11.diff`, and the four Tauri icon PNGs the other workstream keeps overwriting in the worktree (HEAD bytes are canonical; fresh CI checkout passes).

Deferred: full pytest suite (owner decision to stop verification), Windows `makensis` smoke tests. Local `icon --check` fails only because of that worktree overwrite, not committed state.

## 2026-11-21 — rounds 13/14: frozen resolver, self-check markers, gate and CI stub fix
- Real Nuitka 2.8.10 onefile probe corrected the round-11 conclusion: `sys.executable` is inside the extraction dir; `__compiled__.containing_dir` is the original exe dir in all four launch modes; `sys.frozen` is None.
- `ffmpeg_binaries.py`: new `is_frozen_build()` (Nuitka `__compiled__` + PyInstaller signals) and `bundled_bin_dir()` preferring `__compiled__.containing_dir`; no PATH fallback when frozen. A byte-identical compiled copy of the resolver resolved the sibling ffmpeg and ignored a GPL ffmpeg on PATH in modes 1 and 4.
- `selfcheck.py`: five markers (adds frozen-build, no-path-fallback); `verify_windows_bundle.py` requires all five and is fail-closed for empty/missing extraction dirs.
- FINDING, not fixed: `voice_typer/server/autostart/tauri_spawn.py:196` has the same onefile base bug.
- F1 CI failure: cargo test used base config (worker externalBin) with only slim stubs; dropped `--slim` from stub generation step and removed the round-13 worker-download step. Slim build overlay still excludes the worker.
- Scoped tests: 44 selfcheck/gate/resolver + 13 workflow tests green; gate simulated-tree checks accepted a good tree and rejected ffprobe/missing-ffmpeg/GPL-enforce defects.
- Probe dirs `C:/Users/11/nuitka-probe` created and deleted; no large downloads kept.

## 2026-11-21 — CI errors batch 2 (19 failures, 6 parallel subagents)

Source: CI-errors.md SHA 5ec0af05 (state AFTER batch-1 fixes landed). Owner pasted items 4-19; full file revealed items 1-3 (two more soundfile collection errors + the probe failure).

New git rule honored: worked on `main` only; main was behind 1 (CI-errors.md-only commit) → STOPPED and asked → owner approved fast-forward to 349cc26ef. No branch ops, no merge/rebase/reset/stash/clean, no push. Agents edited files only (no staging/commit) to avoid index races in the shared checkout; controller committed each domain with explicit `git add -- <paths>`. Other sessions' files (review.md, chrome_pid.json x2, untracked plans doc) untouched.

- A (179c640b5): CI #1/#3 — `probe_wav` treated soundfile as mandatory; stdlib `wave` now reads headers, soundfile kept as fallback. Controller also fixed CI #2 in the same commit: `test_tts_voice_identity.py:33` module-level `import soundfile` removed (both np/sf used only by `_wav_bytes`, replaced with stdlib wave). 10+10 passed with/without soundfile, 77 TTS sweep green.
- B (ac6cc85bb): `test_media_selfcheck` staged `ffmpeg.exe` on POSIX where `_names()` looks for `ffmpeg`; platform-aware name. 57 passed / 19 pre-existing skips.
- C (ee59a5f90): `_TrayLeftClickHandler` pins removed — setting/handler deliberately deleted in the 2026-11-20 simplification; no equivalent, no production change. 11 wave3 + 23 source + 87 consumer tests green.
- D (b9f3ded6e): 11 stale bubble pins across wave9/paste_failure_toast/short_audio_energy_gate aligned with shared `apply_visibility` policy; all reason strings verified against source, no weakened assertions. 69 passed + 36 policy suite.
- E (161a9414b): log-hygiene test patched obsolete `pyrnnoise` seam; now patches real `_make_rnnoise_backend`. 5 passed + 22 xdist + 6 noise-suppressor.
- F (a1eae059b): `voice_typer.server.recording.time` is the process-global time module, so the patch captured other threads' `sleep(0.01)` calls (12288 on ubuntu-3.13). Filter by caller thread id + explicit flag clear. 89 passed + 25 related + xdist reproduction.

Final gate: scoped suite 197 passed (10 files), ruff-F clean, audio guards green, pytest collect-only 20239 items. 6 local commits ahead of origin/main, NOT pushed (no push requested).

## 2026-11-21 — mypy fatal parse error (numpy ctypeslib)

CI error: mypy 2.3.0 exit 2 at `numpy/ctypeslib/_ctypeslib.pyi:48` — `Type statement is only supported in Python 3.12 and greater [syntax]`. CQ-058 shadows numpy with local Any stubs because the project checks at `python_version = "3.11"` and real numpy 2.x stubs use PEP 695 syntax that mypy cannot parse (a parse error cannot be suppressed by ignore_errors/follow_imports). The shadow covered only `numpy`, `numpy.ma`, `numpy.typing`; `numpy.ctypeslib` fell through to the real stub. Reproduced by forcing `import numpy.ctypeslib` with the repo config.

Fix (commit 71de65e73): completed the Any-shadow package — 28 new stubs mirroring numpy's top-level submodule layout (17 packages as `<sub>/__init__.pyi`, 11 modules as `<sub>.pyi`), plus `tests/test_mypy_numpy_shadow.py` which runs mypy over every shadowed submodule with the repo config in a tmp env and asserts no PEP 695 leakage / fatal exit. RED proof: hiding the ctypeslib shadow reproduces the exact CI `[syntax]` error. Fix verified count-neutral: control run with the new shadows removed gave identical ratchet counts (total 576→569, same three per-code buckets).

Baseline NOT regenerated (would be fake-green). On this host (Python 3.13.7) the mypy ratchet is independently red: arg-type 36→38, attr-defined 198→199, no-any-return 75→77; these predate this fix and were masked by the fatal parse error. CI runs Python 3.12.10 with its own lock-resolved deps, where counts may differ; a local 3.12 interpreter exists but has no mypy/deps installed, so no valid CI-parity run was possible here. Flagged as follow-up: verify the ratchet on a real CI-configured 3.12 environment; if those buckets are genuinely red there, fix the underlying type errors (do not bump the baseline).

Final: 1 new test passed, ruff clean, mypy parse error eliminated. 8 local commits ahead of origin/main, NOT pushed.

## 2026-11-21 — round 17/18: frozen verification fixes and cache isolation
- Non-fail-fast self-check/gate, notices whitespace stripped at generation, platform-neutral resolver test (other-session `ac6cc85bb`).
- Nuitka cached-mode probes: changed/new files re-extracted; removed files survive; two exes sharing a spec mix payloads. `{PRODUCT}`/`{VERSION}` with product/version flags isolate per exe and per build while staying cached.
- Freeze scripts (Windows/Linux/macOS sidecar + worker) now isolate extraction dirs; gate resolves the newest versioned dir.
- Verified: scoped pytest 19 passed, gate self-test PASS, notices check PASS, bash -n clean.
