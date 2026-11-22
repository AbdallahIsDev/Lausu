# review.md Audit — 2026-11-19

Scope: all 47 open tasks in `review.md` (11 High Priority + RH-1…RH-36).
Method: every claim re-checked against the **current working tree** (dirty), plus external
verification for framework/API/advisory claims. Seven specialists were dispatched; four
completed (free-tier limit killed the first batch, then 4 were re-run per owner
instruction). The orchestrator audited its own 13 items directly.

Scoring rubric (owner-specified):

| Band | Meaning |
|---|---|
| 90–100 | Real bug / high impact, safe to implement now |
| 50–89 | Valid secondary improvement |
| 10–49 | Low value or blocked (incl. host-only, cannot act headless) |
| 0 | False premise, breaking, or a downgrade |

Verdicts: **KEEP** (do it), **MODIFY** (do a changed/scoped version), **REJECT** (false
premise / not worth it / would break).

---

## Batch 1 — Rust host / Tauri (orchestrator)

### P0 — Windows/macOS host validation (all fixes tested on Linux sandbox only)

- **Premise:** TRUE.
- **Evidence:** `.github/workflows/host-validation.yml:1-20` is `workflow_dispatch` only
  (scope input: all/windows/macos/linux) and its own header says it "probes only what CI
  runners can prove; mic/display/TCC/logon stay VALIDATE-ON-HOST". Three host jobs exist
  (`:28` windows-2022, `:121` macos-14, `:267` ubuntu-22.04, `:329` summary with
  `if: always()`). What they actually run is import checks, binary/source presence, and
  headless pytest subsets (`:46-112`, `:140-256`, `:286-320`) — not live desktop flows.
  `tests/tauri/test_host_validation_workflow.py` holds **8** contract pins (claim of 8 is
  exact), including `test_linux_job_covers_wmclass_without_autofix` and
  `test_does_not_touch_fragile_pipelines`.
- **Behavior:** N/A — no code change proposed; it is a verification gate.
- **Rules:** C-TEST-6 (green on final state), E1, and the CI/CD sign-off rule.
- **Risk:** Low (documentation/verification only).
- **Verdict:** **KEEP**, reclassified explicitly as a **host gate**, not an implementable
  task. Nothing in this entry is actionable in a headless session: every remaining item
  needs a real Windows/macOS/Linux desktop (mic, TCC, logon, taskbar, X11/Wayland paste).
- **Score:** 75 — legitimate and load-bearing, but permanently blocked here.
- **Action plan:** leave open; dispatch `Host Validation (Cannot-Verify close-out)` per OS
  when a host is available; record evidence under `worklog.md`; never mark complete on a
  headless subset.

### S1-CR-146 — `StartupWMClass=Lausu` may not match the Tauri window class

- **Premise:** UNPROVEN (correctly framed as host-only).
- **Evidence:** `src-tauri/lausu.desktop.template:28` `StartupWMClass=Lausu`;
  `src-tauri/Cargo.toml:15` bin `lausu-tauri`; the template's own header (`:1-18`)
  documents that this file is the bundled menu entry while the runtime autostart entry is
  a different `.desktop`. `host-validation.yml:286` is literally "S1-CR-146 StartupWMClass
  evidence (warning, never auto-fix)", and `tests/tauri/test_host_validation_workflow.py:50`
  pins `StartupWMClass` presence. Upstream: `tauri-apps/tao` issue #1145 — Tauri's
  `window_classname` is **Windows-only**, so on Linux the class comes from tao/GTK, not
  `productName`. That makes a mismatch plausible; it does not settle the value.
- **Behavior:** A wrong value = duplicate/misgrouped launcher icon. No functional break.
- **Rules:** C-BRAND-1 (name constant), docs-only edit if proven.
- **Risk:** Low (cosmetic; the workflow already warns).
- **Verdict:** **KEEP** as host gate — do **not** rewrite blind. The repo is already
  correct to refuse an unverified edit.
- **Score:** 45 — plausible but unactionable headless and cosmetic.
- **Action plan:** on a Linux host run `xprop WM_CLASS` on a visible Tauri window; set
  `StartupWMClass` to the reported class; flip the workflow step from `::warning` to
  assert; keep the test pin.

### DC-15 — per-arch Tauri confs drop base window fields (array-replace)

- **Premise:** ALREADY FIXED (content), host visual check only.
- **Evidence:** All three configs that re-declare `app.windows` now carry all five base
  fields — `tauri.windows-x86_64.conf.json` (5/5), `tauri.windows-aarch64.conf.json`
  (5/5), `tauri.macos.conf.json` (5/5), plus the new
  `tauri.windows-x86_64-slim.conf.json` (5/5). `tauri.linux-x86_64.conf.json` and
  `tauri.linux-aarch64.conf.json` do **not** re-declare `app.windows`, so the base array
  is inherited untouched — nothing is lost there. Pinned by
  `tests/tauri/test_config_script_drift.py:614-640`
  (`test_per_arch_main_window_keeps_base_chrome_and_hardening`), which asserts the merge
  rule ("arrays replace wholesale") and requires each override to repeat the base-only
  fields.
- **Behavior:** IMPROVE — already delivered; merge semantics confirmed against the
  official doc: "Objects are merged key by key, but arrays are replaced as a whole"
  (https://v2.tauri.app/develop/configuration-files/).
- **Rules:** E7, C-DESIGN-* (no chrome drift), C-CI-10 (narrowing intact).
- **Risk:** Low.
- **Verdict:** **KEEP** — close on a 30-second host glance; no code work left.
- **Score:** 88 — high-value finding whose implementation is complete and pinned.
- **Action plan:** on Windows + macOS launch once and confirm centered window, no caption
  menu, traffic lights positioned; then mark the entry closed.

### RH-5 — Bubble hook installed and a thread spawned on every pointer-move event

- **Premise:** TRUE (mechanism verified; magnitude unmeasured, as the entry admits).
- **Evidence:** `src-tauri/src/window_events.rs:53-72` — every bubble `Moved` (and
  `Resized`/`ScaleFactorChanged`) runs: `note_bubble_user_moved()`,
  `schedule_work_area_clamp(...)`, **`ensure_bubble_msg_hook(&bubble)` synchronously on the
  main thread** (`:69`), then `std::thread::spawn(move || harden_bubble_chrome(&bubble, sync_frame))`
  (`:70-72`) — a fresh OS thread per event. `harden_bubble_chrome`
  (`commands/bubble/window.rs:76-88`) calls `ensure_bubble_msg_hook` **again** (`:81`).
  Inside `ensure_bubble_msg_hook`, `EnumChildWindows` fills a fresh `Vec<isize>` (`
  window.rs:255-263`), the mutex-guarded `contains`/push loop runs (`:264-270`), and only
  then does `HOOK_INSTALLED.swap(true, …)` return early (`:271-273`). So each pointer sample
  pays two full child-tree enumerations + one thread creation, and the fast path sits after
  the expensive work.
- **Behavior:** IMPROVE — no behavior change intended; the hook must still install on the
  first event and still catch late-created WebView children.
- **Rules:** W1 (working ≠ optimal), PERF-* class of hot-path work.
- **Risk:** Low-Medium — the trap is re-enumerating too rarely (late children unregistered),
  which the entry itself calls out.
- **Verdict:** **KEEP**.
- **Score:** 72 — real, cheap, self-contained; magnitude unprofiled.
- **Action plan:** (1) move the `HOOK_INSTALLED` fast return to the top of
  `ensure_bubble_msg_hook`; (2) re-enumerate only on `Resized`/`ScaleFactorChanged`/`Show`
  or on a coarse (≥1 s) throttle, not on every `Moved`; (3) replace the per-`Moved`
  `std::thread::spawn` with the generation-counter single-flight already used by
  `clamp.rs::schedule_work_area_clamp`; (4) add a Windows test counting enumerations/spawns
  across a synthetic burst; keep the hook-registration tests green.

### RH-6 — No-op bubble resize still performs the full re-anchor/clamp geometry read

- **Premise:** TRUE.
- **Evidence:** `commands/bubble/commands.rs:272-283` — the `resize_is_noop` guard (`:275`)
  skips `set_size` + `harden_bubble_chrome`, then execution continues into `:284-310`
  **unconditionally**: either `reanchor_bubble_after_resize` (`:288-299`, which at
  `:325-333` reads `outer_position`, resolves a monitor, reads `work_area()`, and reads
  `outer_size`) or `clamp_bubble_into_work_area` (`:303-309`, `clamp.rs:70-81` — same four
  reads). The comment at `:269-271` states the measured rate: "the same 71x47 request up to
  50 times a second".
- **Behavior:** IMPROVE — writes are already guarded (`anchor_moved`, `Ok(None)`), so this
  is pure redundant OS IPC; the entry is right that nothing is mispositioned.
- **Rules:** W1, C-LOG-8 (no-op must not re-apply).
- **Risk:** Low — but the early return must keep re-anchoring when edge/position state
  actually changed (a naive `return` on noop would skip a legitimate re-anchor after a mode
  change that did not alter size).
- **Verdict:** **KEEP**.
- **Score:** 68 — small, behavior-preserving, hot path.
- **Action plan:** return early from the no-op branch **only** when no edge/position state
  changed since the last applied resize; otherwise keep today's path. Keep the existing
  `resize_is_noop` tests (`commands/bubble/math.rs`) green; no new dependency.

### RH-7 — Clamp single-flight can drop a late move and leave the pill under the taskbar

- **Premise:** TRUE, but narrower than described.
- **Evidence:** `commands/bubble/clamp.rs:36-57`. The waiter bumps `GENERATION` (`:37`),
  single-flights on `WAITING.swap(true, …)` (`:38`), samples `seen` (`:44`), sleeps 250 ms,
  breaks on generation equality (`:46-48`), applies the clamp (`:50`), and clears `WAITING`
  **last** (`:55`). A `Moved` landing after the `:46` comparison but before `:55` bumps
  `GENERATION` and sees `WAITING == true`, so `schedule_work_area_clamp` returns at `:39`
  and **no replacement waiter is spawned**.
  Position is read inside `clamp_bubble_into_work_area` at `:70` (not captured at schedule
  time), which shrinks the hole: the unclamped outcome needs the drag's final `Moved` to
  land after that read and before `:55`, i.e. a sub-millisecond window at most, or the drag
  to end exactly inside the window. Real, but rarer than "High".
- **Behavior:** IMPROVE — restores the C-WIN-2 guarantee; must not clamp mid-drag.
- **Rules:** C-WIN-2 (work-area clamp is the owner-reported bug fix), C-LOG-8.
- **Risk:** Medium — a wrong fix (clamping mid-drag) fights the OS move loop, which the
  file's own header warns about.
- **Verdict:** **KEEP** (severity downgraded from High to Medium).
- **Score:** 70 — genuine residual hole in a shipped owner-reported fix; small change.
- **Action plan:** capture `seen`, clear `WAITING` **before** applying the clamp, then
  re-check `GENERATION` after the clamp and schedule a follow-up waiter when it advanced;
  never write an unchanged position. Add a `clamp_tests.rs` case that bumps the generation
  inside the clamp window and asserts a second clamp is scheduled. Host check remains
  (drag onto the taskbar, release, expect snap-back).

### RH-8 — Keyboard nudge and drag clamp pick different monitors

- **Premise:** TRUE.
- **Evidence:** `commands/bubble/commands.rs:207` resolves the monitor from the candidate
  **top-left** — `resolve_monitor_at_point(&app, target_x, target_y)` — then clamps with
  `clamp_candidate` (`:209-215`). `commands/bubble/clamp.rs:74-78` resolves from the
  **center** — `pos.x + w/2`, `pos.y + h/2` — with a comment stating center is the contract
  ("a pill dropped below a stacked monitor's top edge belongs to that monitor, not to the
  one its top-left was on"). Two anchors, one rule.
- **Behavior:** IMPROVE — makes keyboard and drag converge on one monitor rule.
- **Rules:** C-WIN-2 (center rule is the documented contract).
- **Risk:** Low — one-line alignment, no new geometry.
- **Verdict:** **KEEP**.
- **Score:** 74 — trivial, unambiguous, fixes real multi-monitor divergence.
- **Action plan:** in `bubble_move_by`, resolve from `target_x + w/2`, `target_y + h/2`;
  add a multi-monitor test driving both paths to the same target and asserting the same
  clamped rect.

### RH-15 — signCommand makes unsigned local Windows builds require the SDK

- **Premise:** TRUE as documented, unverified independently.
- **Evidence:** `src-tauri/tauri.conf.json:135` `"signCommand": "..\\scripts\\tauri-sign.cmd %1"`.
  `scripts/tauri-sign.cmd:19-26` states the caveat as **verified on-host**: the NSIS bundler
  locates `signtool.exe` on PATH before invoking the wrapper, so on a host without the
  Windows SDK `cargo tauri build` fails with "failed to bundle project: SignTool not found"
  even with no certs; `:27-28` exits 0 early only **after** that point. Upstream context
  confirms `signCommand` runs in a bundler-owned environment, not the caller's shell
  (tauri-apps/tauri#11754). I could not independently prove the locate-before-wrapper
  ordering from public docs — it rests on the repo's own on-host observation.
- **Behavior:** IMPROVE (DX) — moving `signCommand` to a signed-release-only config makes
  plain local builds SDK-free. No runtime change.
- **Rules:** CI/CD section (workflow/config edits need a full re-run + owner sign-off),
  C-TDEV-1 (local no-MSVC dev loop is the point of the GNU toolchain).
- **Risk:** Medium — this is load-bearing release config; a mistake silently produces
  unsigned installers or breaks the signing leg.
- **Verdict:** **MODIFY** — do the config split, but only paired with an assertion that the
  signed leg still signs (a release-only config file gated by the existing signing
  workflow), and only with owner sign-off.
- **Score:** 58 — real DX bug, low product severity, risky surface.
- **Action plan:** add `src-tauri/tauri.windows-signed.conf.json` (or equivalent) carrying
  `signCommand`; have the signed release leg consume it via `--config`; prove with one
  workflow dispatch that the installer is signed and that a plain local build on an
  SDK-less host succeeds; document in the runbook (keep the current workaround note).

### RH-16 — Parent-liveness checks can treat a zombie host as alive

- **Premise:** TRUE (narrow edge).
- **Evidence:** `voice_typer/server/parent_watch.py:74-83` — POSIX branch calls
  `kill(pid, 0)` and returns `True` on success, `False` only for `ProcessLookupError`,
  fail-alive for `PermissionError`/`OSError`. `kill(pid, 0)` does succeed for an unreaped
  zombie on Linux. Mirror check: `src-tauri/src/platform/process/posix.rs:11-24` reaper
  script uses `kill -0 "$orig_parent"` — same signal-0 semantics.
- **Behavior:** IMPROVE — closes a real liveness gap; must stay fail-alive for genuine
  permission/uncertainty so a false negative never kills a healthy child.
- **Rules:** C-HOST-1 (do not weaken the existing kill-binding/watchdog contract),
  RACE-008 (any daemon needs a why-comment).
- **Risk:** Medium — `/proc` state is Linux-specific, macOS needs a different API; a wrong
  implementation risks force-exiting children of a live host.
- **Verdict:** **KEEP** (scoped, keep fail-alive default).
- **Score:** 56 — correct diagnosis, rare trigger, cross-platform complexity.
- **Action plan:** on Linux read `/proc/<pid>/stat` and treat state `Z` as gone; on macOS
  use a `proc_pidinfo`-style liveness query; keep `PermissionError`/`OSError` fail-alive.
  Unit-test with a mocked `/proc` payload for `Z` and one for permission denied. Host
  validation on Linux/macOS.

### PK-3 — Rehearse the pack/worker failure table on all three systems

- **Premise:** PARTLY TRUE. The scripts exist and one matrix row is already recorded;
  the three-OS live matrix is not.
- **Evidence:** `scripts/verify_worker_bridge_live.py` (350 lines — drives real worker +
  real relay + two correlated `request_transcribe` calls),
  `scripts/verify_worker_degrade_live.py` (97 lines — "ADR-0024 Step 6 (c) live
  pack-missing degradation probe … no mocks on the decision path"),
  `scripts/verify_worker_handoff_live.py` (356 lines — spawns the real worker, reads the
  real `worker_started`, checks a real `transcribe_offline` round trip), plus
  `verify_worker_handoff_preflight.py`. ADR-0024 records: "Wire handoff - code done,
  **verification CLOSED 2026-09-26**. Steps 0-6 all signed off on a real Windows host …
  the pack-missing degradation matrix passed on a real pack root". `worklog.md` has no
  `PK-3` row (grep = 0 hits), so the remaining matrix cells (worker killed
  mid-transcription, corrupt pack checksum, pack folder deleted, first launch offline,
  stale pack after update) indeed have no recorded run — on any OS.
- **Behavior:** Verification-only. No code change.
- **Rules:** C-TEST-6 (evidence on the final state), C-LOG-5 (durable outcome lines).
- **Risk:** Medium — this is the failure surface that produced the last outages; skipping
  it is how the next one ships.
- **Verdict:** **KEEP** — host-only.
- **Score:** 65 — high value, zero headless actionability.
- **Action plan:** dispatch `host-validation.yml` per OS (or run locally on each host) and
  drive the five matrix rows using the three `verify_worker_*` harnesses; record each cell
  (behavior + log excerpt) in `worklog.md`; file deviations as follow-ups, never silently.

### SP-1 — Ship the split: slim installer + downloadable offline pack

- **Premise:** TRUE — and materially further along than its "OPEN" status implies.
- **Evidence:** The slim config already exists and is correct:
  `src-tauri/tauri.windows-x86_64-slim.conf.json` overrides `bundle.externalBin` to
  `["bin/python-sidecar"]` (sidecar only), while the base `tauri.conf.json:81-83` carries
  `["bin/python-sidecar", "bin/lausu-worker"]`. It is wired into CI:
  `tauri-windows-build.yml:502` `tauri_config: tauri.windows-x86_64-slim.conf.json`, with a
  hard assertion at `:826` ("must be sidecar-only"). Pins exist in
  `tests/tauri/test_slim_packaging.py`, `tests/tauri/mig18/test_per_triple_freeze.py:211-225`,
  `tests/tauri/mig19/test_windows_build_target_parameterization.py:32`,
  `tests/tauri/test_installer_naming.py:381-399`.
  `.github/workflows/runtime-pack-publish.yml:37-38` is `workflow_dispatch` only (its
  header cites C-CI-4: "manual `workflow_dispatch` ONLY - no push/PR triggers until Phase
  0-W host validation passes"). Scripts exist: `scripts/release/publish_pack_release.py`,
  `scripts/release/build_pack_manifest.py`, `scripts/windows/full-offline-installer.nsi`.
  Size numbers are recorded in `docs/plan-runtime-pack-split.md:257-287`
  (226 MB measured → ~102 MB slim core).
- **Behavior:** IMPROVE — halves every update (~226 MB → ~102 MB), owner-approved.
- **Rules:** C-CI-2 (never edit the tauri-*.yml family casually), C-CI-4 (manual dispatch
  only), C-AGENT-7 (no >1 GB downloads without approval).
- **Risk:** Medium-High — build + release + first-launch plumbing across three systems;
  `runtime-pack-publish` will publish real releases.
- **Verdict:** **KEEP** — the build side is done; the remaining work is execution, not design.
- **Score:** 82 — highest product impact on the board, blocked only by host runs and the
  PK-1/PK-2/PK-3 chain.
- **Action plan:** (1) dispatch `runtime-pack-publish.yml` once by hand and confirm manifest
  + pack download from a clean machine; (2) walk first-launch on a clean Windows box
  (offline day one, pack downloads quietly, honest locked states — no dead buttons);
  (3) mark `docs/plan-runtime-pack-split.md` §5 numbers as shipped-measured; (4) only then
  close, with PK-1/2/3 green.

### SP-2 — Move the sound filter chain to the worker (phase two)

- **Premise:** PARTLY TRUE. The chain exists and is scipy-backed, but the ≈29 MB figure is
  not verifiable from the tree and the entry must not start before SP-1 ships.
- **Evidence:** `voice_typer/server/audio_filters/` exists with `base.py` importing scipy
  **lazily** inside functions (`:181-232` — `sosfilt`, `sosfilt_zi`, `lfilter`), plus
  `dpdfnet_backend.py:14-21` (shared ONNX graph, "one ~10 MB graph … ships beside
  silero_vad.onnx / gtcrn_simple.onnx"). No `torch` import in the package. The savings
  figure comes from the plan, not from measured wheel sizes on this machine.
- **Behavior:** IMPROVE (installer size) — but it re-plumbs a timing-sensitive pipeline
  across a process boundary.
- **Rules:** E13 (preserve, don't fork), E15 (delete the replaced path), and the plan's own
  "do NOT interleave with the split".
- **Risk:** High — cross-process audio timing + mic-test scoring regression while the pack
  is absent.
- **Verdict:** **KEEP**, sequenced strictly after SP-1.
- **Score:** 52 — real saving, but premature now and the measured figure is unverified.
- **Action plan:** defer until SP-1 closes; before implementing, measure the actual
  compressed delta of `scipy` (and any filter deps) from the built artifacts, not the plan;
  then add worker filter commands with a sidecar fallback and byte-parity tests.

### RH-19 — Host-validation runbooks omit the two newest platform behaviors

- **Premise:** TRUE.
- **Evidence:** Grep across the three runbooks for
  `clamp|work area|taskbar|dock|orphan|parent PID`:
  `docs/migration/windows-validation-runbook.md` = 4 hits, all unrelated (taskbar
  notification icon `:890`, orphaned dirs `:1649`, `skipTaskbar`/`alwaysOnTop` config
  `:1717-1720`); `macos-validation-runbook.md` = 4 hits, all the S5-CR-83 LaunchAgent
  orphan gap (`:918-920`); `linux-validation-runbook.md` = **0 hits**. No runbook step
  exercises the C-WIN-2 work-area clamp or the C-HOST-1 host-loss self-exit.
- **Behavior:** IMPROVE (verification coverage) — docs only, no code path.
- **Rules:** C-WIN-2, C-HOST-1 (both need on-host proof), C-COMMENT-7 (don't drop anchors).
- **Risk:** Low.
- **Verdict:** **KEEP**.
- **Score:** 62 — two short steps that make the newest guarantees actually checkable.
- **Action plan:** add one step per OS: (a) drag the pill onto the taskbar/dock and release
  — it snaps back into the work area of the monitor holding its center, no persistence;
  (b) kill the host process (Task Manager / `kill -9`) with the app running — sidecar and
  worker both self-exit, no orphan keeps hotkeys or the single-instance lock. Record
  evidence in `worklog.md`. Cross-reference (do not duplicate) the existing
  S5-CR-83 step.

---

## Batch 2 — Python backend lifecycle (audited directly after sub-agent failure, 7 items)

### WL-1 — Load the no-pack Whisper model in the worker

- **Premise:** ALREADY FIXED (entry self-reports fixed 2026-10-15; code confirms).
- **Evidence:** `voice_typer/server/worker_client.py:167` `request_load_whisper_model`;
  `voice_typer/server/worker_protocol.py:58` cmd + `:197` result type;
  `voice_typer/worker/_ws_commands.py:149-200` handler; `_ws_connection.py:247-248`
  dispatch; `voice_typer/worker/_transcribe.py:165` loader;
  `voice_typer/server/system_whisper.py:135` routes through the client first;
  `voice_typer/server/asr/registry.py:244,333` keeps the in-process fallback. Tests:
  `tests/test_worker_load_whisper_model.py`, `tests/test_worker_load_parakeet_qwen.py`,
  `tests/test_language_auto_detect.py:179-211`.
- **Behavior:** IMPROVE — already shipped; nothing left to implement.
- **Rules:** E7 (one protocol shape), E15 (fallback retained intentionally).
- **Risk:** Low — only the review entry is stale.
- **Verdict:** **KEEP** — close as already-fixed; the residual "verify frozen worker
  ships faster_whisper" is a release-time check, not a code task.
- **Score:** 90 — high impact, already delivered and pinned.
- **Action plan:** mark closed in `review.md`; at packaging time confirm the frozen worker
  bundle contains `faster_whisper`/`ctranslate2` (WL-1 Round C's only open evidence).

### RH-20 — Worker model-load tasks escape the shutdown drain

- **Premise:** TRUE.
- **Evidence:** `voice_typer/worker/_ws_commands.py:203` and `:249` both end with a bare
  `_asyncio.ensure_future(_do())`; each `_do()` awaits `_asyncio.to_thread(run)` where
  `run` is a multi-GB `load_*_model` call. Only transcription paths register a task:
  `_ws_connection.py:151-153` / `:167-169` add to `in_flight` and discard on done. The
  graceful tail gathers **only** `in_flight` (`:234-236`, `asyncio.gather` with no timeout);
  the SIGTERM/parent-gone path `voice_typer/worker/_ws_server.py:157-164` just awaits
  `stop_event.wait()` and returns — **no gather at all**.
- **Behavior:** IMPROVE — bind model loads to the same lifecycle as transcription.
- **Rules:** C-HOST-1 (host-loss liveness), RACE-016 (cleanup must not block exit),
  C-TEST-16 (assert transition with deadline, not fixed sleeps).
- **Risk:** Medium — joining an in-progress model load can delay exit; must be bounded.
- **Verdict:** **KEEP**.
- **Score:** 76 — real lifecycle hole in a shipped worker; bounded fix needed.
- **Action plan:** register every `ensure_future(_do())` in `in_flight` (or a shared
  `background_tasks` set); on SIGTERM/parent-gone gather the same set with a deadline and
  a why-comment for any daemon; add a test issuing a slow fake model load then shutdown,
  asserting the task was awaited or explicitly cancelled with the deadline honored.

### RH-21 — Mic-level worker slot cleared while its thread is still alive

- **Premise:** TRUE.
- **Evidence:** `voice_typer/server/level_monitor/mic_level_push.py:_stop_mic_level_worker`
  sets the stop flag and wake event, joins with `timeout=1.0`, then **unconditionally**
  sets `_state._mic_level_worker_thread = None` and calls `_unregister_from_thread_registry`,
  with no `is_alive()` re-check. Siblings do guard: `level_monitor/worker.py:128-136` logs
  an error and `return`s before clearing the slot when the thread survives the join;
  `recording/capture_audio_worker.py:266-269` clears only `if not ...is_alive()`.
- **Behavior:** IMPROVE — prevents duplicate mic-level workers and a false registry state.
- **Rules:** C-ARCH-2 (no package-level indirection), RACE-008 (daemon why-comment).
- **Risk:** Low-Medium — reachable when PortAudio cleanup stalls >1 s.
- **Verdict:** **KEEP**.
- **Score:** 66 — real, narrow, mirrors an already-established sibling contract.
- **Action plan:** copy the sibling guard verbatim (keep the slot occupied + log when the
  thread survives); add a test with a fake thread that ignores the stop event, asserting
  the slot is retained and no duplicate worker spawns.

### RH-22 — Prewarm timeout bounds the waiter, not the PortAudio stream

- **Premise:** TRUE.
- **Evidence:** `voice_typer/server/recording/device_prewarm.py:~197-226`: a nested
  daemon thread opens `sd.InputStream` (no callback), calls `start()`/`stop()` with `close()`
  in its own `finally`, then `result["done"].set()`. The outer function waits
  `result["done"].wait(timeout=timeout_s)` and, on timeout, only logs "Input stream prewarm
  timed out … (device may be stuck, the first start() will retry)" and returns. There is no
  cancellation handle, no abort flag, and no registry entry for the leaked thread.
- **Behavior:** IMPROVE — stop a stuck prewarm thread from leaking past the timeout.
- **Rules:** RACE-008, E13 (no band-aids).
- **Risk:** Low — best-effort warm-up; a leak costs one daemon thread per stuck device.
- **Verdict:** **KEEP**.
- **Score:** 52 — valid but low user impact; easy to over-engineer.
- **Action plan:** pass a bounded `stop` Event into the inner open path where PortAudio
  permits, register the daemon with the ThreadRegistry (RACE-008 why-comment), and assert
  with a fake `sd.InputStream` that a timeout never leaves an untracked live thread.

### RH-23 — Startup daemons lack a uniform cancellation contract

- **Premise:** PARTLY TRUE — the entry overstates the unregistered set.
- **Evidence:** `_phases_early.py:125-129` and `:153-157` spawn `vad-preload-startup` and
  `gtcrn-preload-startup` through `registry.spawn_and_register(..., daemon=True,
  join_timeout=2.0)`; the bare `threading.Thread` at `:132` and `:160` are only the
  **fallback** when the registry is missing. `history-retention-apply` is registered at
  `:388-399`. `_phases_late.py:204,211,226` does pass `_shutdown_event` to the pack-check
  and extractor-refresh tasks. What genuinely lacks registration/shutdown wiring are six
  fire-and-forget late threads: `startup-autostart-sync` (`:178-183`), `startup-pack-check`
  (`:213-218`, event passed), `startup-extractor-refresh` (`:228-233`, event passed),
  `startup-probe-prewarm` (`:243-248`), `startup-desktop-shortcut` (`:290-295`),
  `startup-mic-guard` (`:315-320`). So: **6 unregistered late threads, 4 without a stop
  event**, not "~10 unregistered".
- **Behavior:** IMPROVE — unify the four outliers on the existing registry contract.
- **Rules:** RACE-020 (`_shutting_down` re-checked per step), RACE-008, E13.
- **Risk:** Medium — startup order is load-bearing; touching all 11 spawns at once is
  needless churn.
- **Verdict:** **MODIFY** — narrow scope to the four late threads with no stop event.
- **Score:** 62 — real but narrower than claimed.
- **Action plan:** route `startup-autostart-sync`, `startup-probe-prewarm`,
  `startup-desktop-shortcut`, `startup-mic-guard` through
  `registry.spawn_and_register(..., join_timeout=…)` and pass `_shutting_down_event`
  where the callee accepts one; leave the two registered early preloads and the two
  event-bearing late tasks untouched; pin the wiring with a registry-count test.

### RH-35 — Config pruning runs before migrations and backup

- **Premise:** TRUE — this is the real High-severity finding in the file.
- **Evidence:** `voice_typer/server/config/loader.py:225` calls
  `_filter_unknown_keys_impl(cls, parsed, config_file)` **before** `_run_migrations(...)`
  at `:243` and `_backup_before_migration_impl(...)` at `:246`. The filter (`:119-164`)
  drops every key not in `cls.__dataclass_fields__` or `_KNOWN_EXTERNAL_CONFIG_KEYS`
  (`:110-118`, only two credential flags) and `_remove_unknown_keys_from_disk` (`:164-190`)
  rewrites `config.json` — so the prune is on disk before any migration reads it.
  Migration source keys are all unknown to the schema: `silence_rms_threshold` /
  `normalize_audio` (`config_internals/migrations.py:101-113`), `runtime_pack_consent`
  (`:129-132`), `push_to_talk_hotkey` (`:144-147`), `sound_volume` (`:180-183`);
  `_schema.py:339,363` confirms the latter two families were *removed* fields. Consequence:
  the migration branches cannot fire on a real load, and the `.bak` taken at `:246`
  contains the already-pruned data. The existing test
  (`tests/config/test_config_schema_migration.py:283-317`) calls the migration helper
  directly, never `Config.load()`, so it cannot catch this.
- **Behavior:** BREAK-DOWNGRADE — real legacy settings are silently lost; migration
  warnings never appear; the safety backup is taken too late to help.
- **Rules:** C-CONF-5 (versioned migration with `.bak`, logged), E10 (investigation before
  implementation), C-TEST-10 (update all pins in one change).
- **Risk:** High — data loss for legacy configs; also affects downgrade edges.
- **Verdict:** **KEEP** — fix before any config-related release.
- **Score:** 92 — genuine high-impact data-loss bug, safe to fix with a load-order test.
- **Action plan:** run migrations on the **raw parsed dict first**, then prune unknown keys
  from the migrated result; move `_backup_before_migration_impl` before both; add a
  load-level regression test that writes a v3 config containing
  `runtime_pack_consent`/`sound_volume` and asserts the rename/prune warning, the emitted
  field, and a `.bak` that still contains the original keys. Grep every pin of the old
  order and update them in the same commit (C-TEST-10).

### RH-36 — `dictation_lost` published with no consumer, contradicting silent recovery

- **Premise:** TRUE.
- **Evidence:** `voice_typer/server/crash_recovery/_store.py:189-209` publishes
  `{"type":"dictation_lost", "data":{…}}` when the `.dictation-in-flight` sentinel is
  found; registered in `voice_typer/server/event_bus.py:248`; forwarded by
  `src-tauri/src/sidecar/ws/event_protocol.rs:73`; pinned by
  `tests/test_dictation_lost_message.py:48-93`. Across `voice_typer/client/src`, `src-tauri/src`,
  the server, and tests, **no renderer subscriber exists** (grep hits only the four sites
  above). Meanwhile `startup_sequence/_phases_early.py:345-352` says the path is "Fully
  silent (owner decision): no OS toast AND no event-bus notification", and
  `tests/test_notifications.py:48` / `tests/test_recovery_startup_notify.py:65` pin that
  silence — but only for `type == "notification"`, so the contradiction is invisible to
  them.
- **Behavior:** BREAK-DOWNGRADE (contract) — an internal event is shipped over the public
  WS surface with zero consumer while the docs/tests assert a silent path.
- **Rules:** C-CONF-3 (startup mic reconciliation is silent — same "no dialogs" spirit),
  E9 (every IPC message needs a matching type), C-TEST-10.
- **Risk:** Low — currently harmless because nobody renders it; becomes a surprise toast
  the moment a generic event handler is added.
- **Verdict:** **KEEP**.
- **Score:** 70 — real contract violation, cheap fix, no user-visible break.
- **Action plan:** pick one truth. Preferred: stop publishing `dictation_lost` from
  `_detect_and_notify_lost_dictation` (keep the log line), remove the Rust allowlist entry
  and the payload test, and add a test asserting no non-notification event is emitted on
  startup recovery. If the event is actually wanted, add a typed renderer consumer and
  update the owner-decision comment + tests instead.

## Batch 3 — Tests / CI hermeticity (audited directly, 7 items)

### RH-9 — CI failure-notification job is blind to six workflow jobs

- **Premise:** TRUE — all six jobs really are in the same workflow, so `needs:` is legal.
- **Evidence:** `build.yml` job keys: `test` (`:39`), `ci-errors-doc` (`:240`),
  `icons-drift` (`:291`), `product-namespace-drift` (`:315`), `pip-audit-weekly` (`:335`),
  `slow-tests` (`:382`), `version-check` (`:432`), `branding-check` (`:459`),
  `rust-lint` (`:479`), `client-build` (`:540`), `build-native` (`:586`),
  `pre-commit` (`:718`), `notify` (`:752`). The notify job at `:752-793` has
  `if: always()` and `needs: [test, client-build, version-check, branding-check,
  build-native, pre-commit]`; both the Markdown table and the `FAILURE_COUNT` loop repeat
  exactly those six. Gating is not a blocker: `pip-audit-weekly` is `if: schedule`,
  `slow-tests` is `if: push && ref==main`, `rust-lint`/`ci-errors-doc` are
  `if: event != schedule` — on a given run they are `skipped`, and the loop counts only
  the literal string `failure`. Official GitHub docs confirm `needs` references jobs in
  the same workflow and `if: always()` lets the dependent job run when upstream jobs fail
  (https://docs.github.com/actions/using-jobs/using-jobs-in-a-workflow).
- **Behavior:** IMPROVE — failures in lint/audit/drift jobs currently produce no red notify
  job and no summary row.
- **Rules:** C-TEST-11 (enumerate every non-success step before calling a job green),
  CI/CD sign-off rule for workflow edits.
- **Risk:** Low — additive `needs` entries, no ordering change; `always()` already in place.
- **Verdict:** **KEEP** — but edit the workflow with the usual full re-run + owner sign-off.
- **Score:** 80 — real observability hole, tiny fix.
- **Action plan:** add the six job ids to `needs:`, the summary table, and the
  `FAILURE_COUNT` loop in one change; keep counting only `failure`; verify with a forced
  `rust-lint` failure on a dispatch run that `notify` goes red and the row appears.

### RH-10 — CI-errors.md reports a failure that no longer exists

- **Premise:** TRUE — but the artifact is generated, so the fix is regeneration, not an edit.
- **Evidence:** `CI-errors.md:5-20` says "**1 failing/errored tests**" and names
  `tests.test_shutdown_fast.TestWin32RoutingFastCleanup.test_ctrl_c_still_routes_to_quit`
  at `tests/test_shutdown_fast.py:218`; line 218 is blank. The C-TEST-16 fix is at
  `:225-227` (`assert wait_until(lambda mock=quit_mock: mock.call_count > 0, timeout=5.0)`
  followed by `quit_mock.assert_called_once_with()`); the sibling
  `tests/test_shutdown_logoff_cleanup.py:324-331` has the same wait. The header of
  `CI-errors.md` itself says "Auto-generated … via `scripts/ci/write_ci_errors.py`.
  Do not edit by hand", and `scripts/ci/write_ci_errors.py:41` writes that exact file;
  `build.yml:240` (`ci-errors-doc`) regenerates and pushes it on non-schedule runs.
- **Behavior:** IMPROVE (docs accuracy only) — no runtime behavior.
- **Rules:** E10 (verified vs stale), CI/CD sign-off rule.
- **Risk:** Low.
- **Verdict:** **MODIFY** — regenerate from the latest green JUnit results; never hand-edit.
- **Score:** 52 — stale generated artifact; self-corrects on the next CI run.
- **Action plan:** run `python scripts/ci/write_ci_errors.py <latest junit files>` (or let
  the next CI run do it) and confirm the doc reports zero failures; add no new code.

### RH-11 — Type-check baselines: soft ratchet plus platform-only errors

- **Premise:** PARTLY TRUE — counts and mechanism are exact; "compares against base ref"
  is half right by design.
- **Evidence:** `build.yml:124` `pyrefly check … > pyrefly-current.json || true`; `:129-131`
  seeds `pyrefly-baseline.json` from the current output when absent; `:149-159` sets
  `OLD_COUNT` from the **current checkout** file when present, falling back to
  `git show "$BASE_REF:pyrefly-baseline.json"` only when absent; `:160` reads `NEW_COUNT`
  live; `:166-168` raises the floor with a `::warning` only; `:169-178` hard-fails only on
  `NEW_COUNT > OLD_COUNT`. `BASE_FLOOR` is in fact read from the base ref (`:162-164`) and
  compared at `:165-168` — so the soft ratchet is deliberate, not an oversight.
  Counts verified directly: `pyrefly-baseline.json` has **356** entries under `errors`;
  `mypy-baseline.json` has `total_count: 576`. Quoted examples present:
  "Cannot find module `pyatspi`" (`:1008`), "No attribute `flock` in module `fcntl`"
  (`:1104`), "No attribute `LOCK_EX` in module `fcntl`" (`:1116`).
- **Behavior:** IMPROVE only if changed carefully; a naive "always compare to base ref"
  would break the documented soft gate and force hundreds of platform-only errors into a
  hard failure.
- **Rules:** C-TEST-13 (count gates must not depend on optional runtime deps), E1, CI/CD
  sign-off rule.
- **Risk:** Medium — workflow change with cross-platform baseline semantics.
- **Verdict:** **MODIFY** — keep the soft ratchet; make the floor-raise actionable.
- **Score:** 58 — valid observation, but the proposed direction is partly wrong.
- **Action plan:** do **not** switch `OLD_COUNT` to base-ref-only. Instead, pair the
  existing `::warning` with a check-summary row naming the raised count and its
  justification, and add a ratchet test that fails if either baseline's count *decreases*
  without a regenerated `_comment`. Wide cleanup of the 356/576 platform-only errors is a
  separate, much larger product decision.

### RH-24 — Permission tests assert callback counts after fixed sleeps

- **Premise:** TRUE.
- **Evidence:** `tests/test_permissions.py:1014-1131` uses `time.sleep(0.10)` against
  `Timer(interval=0.01)` in the three cancel tests (`:1030`, `:1050`, `:1082`) and
  `sleep(0.002)/0.05/0.03` against `interval=0.005` in `TestConcurrentCancelRace`
  (`:1115`, `:1123`, `:1128`). Assertions depend directly on those sleeps:
  `assert callback.call_count == 0` (`:1032`), `assert callback.call_count == 1` (`:1052`),
  `assert timer_count["n"] == 1` (`:1085`), and the "no callbacks after cancel" delta
  (`:1130`). `wait_until` appears **0** times in this file, while
  `tests/fixtures/wait_helpers.py:33-40` provides a deadline-based helper.
- **Behavior:** IMPROVE (test determinism) — no production change.
- **Rules:** C-TEST-16 (prove negative by the worker still being in flight, not elapsed
  time; deadline generous enough for a loaded CI runner), C-TEST-17 (fix every copy).
- **Risk:** Low — test-only, but a bad rewrite can turn a race regression into a false green.
- **Verdict:** **KEEP**.
- **Score:** 66 — real flake/false-green class, small scope.
- **Action plan:** replace fixed sleeps with `wait_until` on the *state transition*; for
  negative assertions prove the negative by keeping the timer/poll observable and
  asserting no callback after a deadline that outlives a loaded runner (per C-TEST-16),
  not by "we waited 100 ms and nothing happened". Grep for sibling copies of these tests
  before editing (C-TEST-17).

### RH-25 — numpy lazy-import guard is a no-op in the full suite

- **Premise:** TRUE — the reachability argument holds.
- **Evidence:** `tests/test_numpy_lazy_import.py:21-22` returns `False` immediately when
  `"numpy" in sys.modules`; both tests gate their real assertions on `if clean_baseline:`
  (`:46-49` and `:82-92`). `tests/fixtures/ipc_test_helpers.py:9` has a module-level
  `import numpy as np`; `tests/handlers/conftest.py:7-10` imports that helper at module
  level. pytest loads conftest modules for the whole collected tree during collection —
  before any test body runs and on every xdist worker — so numpy is already in
  `sys.modules` when either test executes. The lazy-proxy shape assertions that are *not*
  gated still run, but the "numpy stays out" assertions never do.
- **Behavior:** IMPROVE (restore test coverage) — production code unaffected.
- **Rules:** C-TEST-9 (hermeticity must not depend on import order), C-TEST-8.
- **Risk:** Low.
- **Verdict:** **KEEP**.
- **Score:** 74 — a test that silently tests nothing in the canonical full-suite run.
- **Action plan:** stop gating. Give the test its own fresh interpreter (subprocess with
  `-c` importing only the target module) or patch the exact collection-time seam so numpy
  can be temporarily removed and restored safely; assert the negative unconditionally.
  Verify by running the file alone *and* after `tests/handlers/` in one pytest invocation.

### RH-26 — Collection-time bare `MagicMock` modules carry a pytest-9.2 undo hazard

- **Premise:** PARTLY TRUE — the pattern and upstream bug are real; reachability is low.
- **Evidence:** `tests/conftest.py:15-23` registers bare `MagicMock()` stand-ins for
  `pystray`, `pynput`, `pynput.keyboard`, `pyperclip` and mutates
  `_mock_pystray_collection.Menu.SEPARATOR = "SEP"`; `tests/test_logging_formatting.py:14-20`
  does the same. The safe stand-in exists at `tests/fixtures/mock_modules.py:19-35`
  (real `__dict__` children via `__getattr__` + `setattr`). Upstream
  https://github.com/pytest-dev/pytest/issues/15287 is real and states: "Since pytest
  9.2.0, undoing `monkeypatch.setattr` on an attribute of a `unittest.mock.MagicMock`
  deletes that attribute instead of restoring …"; repo pins `pytest>=9,<10` in
  `pyproject.toml:373` with CI installing unpinned latest. **Mitigation already present:**
  the session fixture at `tests/conftest.py:158-174` replaces `pystray`/`pyperclip` with
  `mock_module(...)` and the autouse per-test fixture at `:207-213` replaces the pynput
  modules before test bodies, so the bare mocks are only live during collection, where
  `monkeypatch.undo()` is not used. No current test patches a child of these bare mocks.
- **Behavior:** IMPROVE (latent hazard removal) — no production change.
- **Rules:** C-TEST-14, C-TEST-15 (exactly this failure class), W2 (reuse the helper).
- **Risk:** Low.
- **Verdict:** **KEEP** — cheap hygiene; treat as prevention, not a live bug.
- **Score:** 55 — hazard real, currently unreachable.
- **Action plan:** build the collection-time stand-ins with `mock_module()` in both files
  and keep the `Menu.SEPARATOR` assignment on the real stand-in; add a comment noting the
  pytest 9.2 undo reason. No fixture or test-order changes.

### RH-27 — conftest is a catch-all with silently swallowed teardown errors

- **Premise:** TRUE.
- **Evidence:** `tests/conftest.py` is **632** lines. Six autouse drainers use
  `with contextlib.suppress(Exception)` at `:362`, `:375`, `:390`, `:405`, `:419`, `:431`,
  each wrapping both the production import and the drain call; five more bare
  `except Exception` at `:470`, `:502`, `:504`, `:519`, `:536`. The diagnostic snapshot
  thread at `:521-527` is `daemon=True` with no RACE-008 why-comment (and a bare
  `except Exception: pass` at `:519`). An `ImportError` in a drain therefore silently
  skips that drain entirely, leaving threads/timers live for later tests — a real
  contamination path, though most of the suppressed exceptions are expected teardown
  races.
- **Behavior:** IMPROVE (test hygiene/diagnosability) — no production change.
- **Rules:** E13 (no blanket suppression unless a documented false positive), RACE-008,
  C-TEST-14/15 (this file already caused a broad CI failure class).
- **Risk:** Low-Medium — changing teardown in a shared conftest can shake loose latent
  cross-test dependencies.
- **Verdict:** **MODIFY** — narrow the suppressions instead of a mass rewrite.
- **Score:** 56 — real but diffuse.
- **Action plan:** in the six drainers, keep suppression only around the *expected* final
  teardown race and log at DEBUG when a drain is skipped (especially `ImportError`); add
  the RACE-008 why-comment to the snapshot thread; split the catch-all `conftest.py` into
  focused fixtures by concern (C-STRUCT-1) only as a separate, test-verified change.

## Batch 4 — Packaging / release / supply chain (audited directly, 10 items)

### DC-14 — Windows NSIS uninstaller leaves the Startup-folder `.bat` orphan

- **Premise:** ALREADY FIXED (status in review.md also says code done).
- **Evidence:** `scripts/windows/uninstaller.nsh:150-184` has a dedicated
  "Startup-folder .bat cleanup" block that enumerates and deletes **both**
  `com.Lausu.autostart_*.bat` and `Lausu_*.bat` via `FindFirst`/`FindNext`/`Delete`;
  the header (`:13-35`) documents the whole autostart surface, and verification steps at
  `:54-65` check both names. The sweep likewise covers both schemes
  (`_autostart_windows_sweep.py:182-200`).
- **Behavior:** IMPROVE — already shipped; residual is host validation.
- **Rules:** C-CROSS-1/2 (Windows autostart semantics), C-CROSS-4 (raw-string validation).
- **Risk:** Low.
- **Verdict:** **KEEP** — host-only close-out (uninstall on a Windows box where the
  Scheduler fallback actually wrote a `.bat`, confirm both names disappear).
- **Score:** 86 — real finding, code complete.
- **Action plan:** run the documented uninstall verification on a Windows host; close.

### RH-12 — Intel-Mac dependency pin carried advisories audit could not see on non-darwin legs

- **Premise:** PARTLY TRUE. The advisories were real; two supporting claims in the
  review were wrong. The finding is now RESOLVED by the owner's decision.
- **Evidence:** `pyproject.toml` pinned `cryptography>=48.0.1,<49` on Intel macOS with
  an accepted-risk comment, and the lock carried `cryptography==48.0.1` for that marker.
  **`build.yml:239-242` has no `if:` guard** on the `pip-audit --strict --require-hashes
  -r requirements-lock.txt` step: it runs on every `test` matrix leg, including macOS.
  The earlier "only on non-darwin matrix legs" claim was FALSE. The real blind spot was
  marker-based: non-darwin legs marker-excluded the darwin-only pin, so they could never
  audit it (a macOS x64 leg would have included it).
  **Verified online (all three ids are real, not invented):** PYSEC-2026-3552
  (Bleichenbacher oracle in PKCS#7 EnvelopedData, introduced 44.0.0, fixed 50.0.0),
  PYSEC-2026-3553 (duplicate self-signed intermediates → exponential path building,
  fixed 49.0.0), PYSEC-2026-3554 (wildcard SAN escapes `permittedSubtrees`, fixed
  49.0.0) — OSV `https://api.osv.dev/v1/vulns/PYSEC-2026-355{2,3,4}`; all list 48.0.1
  as affected. Official changelog confirms 49.0.0 removed macOS x86_64 wheels
  (https://cryptography.io/en/stable/changelog/#v49-0-0).
  **Corrections:** the review's addendum claimed the sidecar used Fernet in a module
  whose name never existed in the tree; the real module is
  `voice_typer/server/_text_crypto.py` and it used AES-GCM, not Fernet. The companion
  claim that no `voice_typer/` module imported cryptography was also false at the time
  (`_text_crypto.py` imported `AESGCM`); only the three advisory code paths were out
  of reach, not the whole package. Reachability of those paths was therefore low.
- **Behavior:** BREAK-DOWNGRADE (shipped a known-vulnerable version), but deliberately
  accepted with a documented rationale; C-TEST-12 forbids `--ignore-vuln` suppressions,
  and none was used.
- **Rules:** C-TEST-12, C-AGENT-7, CI/CD sign-off rule.
- **Risk:** REMOVED for the shipped dependency: the owner chose Option B (keep Intel-Mac
  support, replace cryptography with PyCryptodome, byte-compatible AES-256-GCM).
- **Verdict:** **RESOLVED** — direct dependency and Intel-Mac pin removed, no pin bump.
- **Score:** 66 — real supply-chain gap, closed without an audit suppression.
- **Action plan (done):** correct the stale Fernet/nonexistent-module comments; remove
  the pin and PYSEC acceptance; regenerate the lock; pin byte-compat fixtures. The lock
  still carries `cryptography==50.0.0` on Linux only, transitively via
  `keyring → secretstorage` (unrelated to our code; 50.0.0 has no advisory).
- **Verified:** OSV `query` for `cryptography` 50.0.0 / 50.0.1 / 50.0.2 returns
  no advisories; marker evaluation confirms the `cryptography`, `secretstorage`
  and `jeepney` lock entries are true only for `sys_platform == 'linux'` and
  false on macOS x86_64, macOS arm64 and Windows amd64. `cffi` is cross-platform
  but also comes from sounddevice/soundfile, so it is not chain evidence.

### RH-13 — npm audit skips the dev dependencies the overrides exist to pin

- **Premise:** PARTLY TRUE mechanically, FALSE as a finding — this is deliberate.
- **Evidence:** `.github/workflows/client-ci.yml:64-65` runs
  `npm audit --audit-level=high --omit=dev`; the immediately preceding comment
  (`:58-63`) says "never ship in the Tauri installer — only runtime deps are a"
  and lists the overrides as the accepted-findings list. `package.json:56-77` carries
  the overrides, several annotated `(dev-only)` (browserslist, qs,
  postcss-selector-parser). Official npm docs confirm `--omit=dev` removes the dev
  dependency tree from the audit (https://docs.npmjs.com/cli/v9/commands/npm-audit/).
- **Behavior:** KEEP AS-IS — changing the audit scope would make the documented
  accepted-dev-findings policy fail and would not change what ships.
- **Rules:** AGENTS.md "npm Overrides: DO NOT REMOVE", E13, CI/CD sign-off rule.
- **Risk:** Low.
- **Verdict:** **REJECT** — the "gap" is an intentional, documented scope choice;
  adding a second full-dev audit is optional bloat, not a bug fix.
- **Score:** 25 — mechanically correct observation, wrong conclusion.
- **Action plan:** none. If the owner wants dev-supply-chain visibility, file a separate
  non-blocking informational job — never as a change to this hard gate.

### RH-14 — pystray LGPL §4d obligation flagged but its analysis document is missing

- **Premise:** TRUE.
- **Evidence:** `pyproject.toml:141-149` flags pystray 0.19.5 as LGPL-3.0-or-later,
  says the §4d re-linking obligation "may not be satisfied" when statically bundled,
  and points at `docs/migration/signing-guide.md`. That guide has **0** hits for
  `LGPL|pystray|relink`; `docs/THIRD_PARTY_NOTICES.md:27` mentions LGPL only for FFmpeg.
  Verified online: PyPI lists pystray 0.19.5 as LGPLv3 (https://pypi.org/project/pystray/);
  0.19.5 is the current release.
- **Behavior:** IMPROVE (compliance documentation) — no code change.
- **Rules:** E13 (document genuine gaps), C-COMMENT-6 (long rationale belongs in docs).
- **Risk:** Low (legal review needed, not an engineering fix).
- **Verdict:** **KEEP**.
- **Score:** 60 — valid open obligation, but the resolution is a legal decision.
- **Action plan:** write the promised section in `signing-guide.md` (what ships, how
  relinking is offered — source offer / object files — and who signs off); add the same
  pointer from `THIRD_PARTY_NOTICES.md`; or replace pystray per the queued CR follow-up.

### RH-28 — Uninstall leaves the runtime pack and installer state behind

- **Premise:** TRUE.
- **Evidence:** The full-offline installer writes to `$LOCALAPPDATA\lausu`:
  `full-offline-installer.nsi:71` InstallDir, `:91-105` pack extraction and zip delete,
  `:120-126` `installer-state.json` with `pack_bundled: true`; the slim installer hook
  does the same at `installer-hooks.nsh:137-155`; authoritative pack root is
  `voice_typer/server/service/offline_pack/core.py:97-99`. Uninstall removes only the
  `%APPDATA%\lausu` tree (`uninstaller.nsh:185+`, `uninstall.bat`, `uninstall_permissions.py`).
  A grep across all of `scripts/windows/` finds **no** `Delete`/`RMDir` targeting
  `$LOCALAPPDATA\lausu`.
- **Behavior:** BREAK-DOWNGRADE — ~124 MB pack + state file survive uninstall; a later
  reinstall can pick up a stale pack version.
- **Rules:** E15 (delete replaced artifacts), C-AGENT-8 (do not delete user data — here
  the pack is app-owned, so explicit uninstall removal is correct).
- **Risk:** Medium — must not delete unrelated user files in `%LOCALAPPDATA%`.
- **Verdict:** **KEEP**.
- **Score:** 76 — real disk/consumer bug, narrow fix.
- **Action plan:** add an uninstall section that removes only
  `$LOCALAPPDATA\lausu\runtime-pack` and `$LOCALAPPDATA\lausu\installer-state.json` (never
  the whole LOCALAPPDATA\lausu if it gains user data later); pin with a Windows host test
  asserting both are gone, then close.

### RH-29 — "Torch-free" bundle gate only detects dotted module names

- **Premise:** TRUE.
- **Evidence:** `scripts/build/check_bundle_torch_free.sh:~59-74` defines
  `PATTERNS=("torch\\." "silero_vad\\.jit")` and scans with `grep -E` (and a Python
  fallback at `:112-120` using `re.compile(p.encode(...), re.IGNORECASE)`). In both,
  `torch\.` matches a literal dot only — it cannot match Nuitka's own documented
  `torch/__init__.py` or Windows `torch\` path forms, which the adjacent comment
  explicitly claims it catches. The gate is hard-fail in all three build workflows
  (`tauri-windows-build.yml:308-314`, `tauri-macos-build.yml:141-146,302-307`,
  `tauri-linux-build.yml:436-442`).
- **Behavior:** IMPROVE — broaden detection, never narrow it.
- **Rules:** E1 (wiring/gate verification), CI/CD sign-off rule.
- **Risk:** Medium — false positives would break all three release pipelines.
- **Verdict:** **KEEP**.
- **Score:** 68 — real false-negative in a load-bearing gate; safe additive fix.
- **Action plan:** change the pattern to a character class covering all three separators
  (e.g. `torch[./\\]`), keep the case-insensitive scan, add a fixture file containing
  `torch/__init__.py` and one containing `torch.nn` and assert both fail; full workflow
  re-run + owner sign-off before merge.

### RH-30 — Full-offline installer reports success on failed extraction or slim-core failure

- **Premise:** TRUE. (The review itself flags the PowerShell detail as suspected; the
  NSIS-level defect is independent of it.)
- **Evidence:** `full-offline-installer.nsi:99-105` runs `Expand-Archive`, pops the exit
  code into `$0`, emits only a `DetailPrint` warning on nonzero, then unconditionally
  deletes the zip. `:118-126` writes `installer-state.json` with `pack_bundled: true`
  regardless. `:144-148` `ExecWait`s the slim-core installer and again only warns on a
  nonzero `$0`, so the wrapper still exits 0. There is no `Abort` anywhere in those
  sections. Official PowerShell docs do not promise a nonzero exit for non-terminating
  `Expand-Archive` errors, so a corrupt zip can plausibly pass the `$0` check as well.
- **Behavior:** BREAK-DOWNGRADE — false success; user is told the pack is installed when
  it may be missing, and the app will skip downloading it because state says bundled.
- **Rules:** C-UXERR-2 (no success signal for an incomplete action), C-LOG-5, C-MEDIA-3
  (validate an ingest before reporting success — same principle).
- **Risk:** High — silent broken offline install.
- **Verdict:** **KEEP**.
- **Score:** 78 — high-impact false-success path, straightforward fix.
- **Action plan:** use `powershell -Command "$ErrorActionPreference='Stop'; Expand-Archive …"`
  and `Abort` on nonzero; only delete the zip after a successful extract; write
  `pack_bundled` from the *verified* outcome; `Abort` on a nonzero slim-core exit. Add a
  corrupt-zip host test asserting installer exit != 0 and no `pack_bundled: true` state.

### RH-31 — NSIS wrapper forwards `$CMDLINE` instead of the parameter string

- **Premise:** TRUE — confirmed from the official NSIS reference.
- **Evidence:** `full-offline-installer.nsi:139-148` comments "Forward the original
  cmdline so /S and /D=path propagate" and executes
  `ExecWait '"$PLUGINSDIR\slim-core-setup.exe" $CMDLINE' $0`. Official docs
  (https://nsis.sourceforge.io/Docs/Chapter4.html#$CMDLINE) give the format
  `"full\path to\installer.exe" PARAMETER PARAMETER …` and state verbatim: "If /D= is
  specified on the command line (to override the install directory) it won't show up in
  `$CMDLINE`." `${GetParameters}` (FileFunc) is the documented way to get only the
  parameters. So `/S` is forwarded, but the wrapper's own executable path is passed as
  an extra argument and `/D=` is silently dropped.
- **Behavior:** BREAK-DOWNGRADE — silent installs with a custom destination land in the
  default directory.
- **Rules:** C-CROSS-1 (platform-gate quoting/param helpers), E7.
- **Risk:** Medium — installer semantics; needs a Windows host check.
- **Verdict:** **KEEP**.
- **Score:** 80 — concrete, externally confirmed bug with a one-line fix.
- **Action plan:** use `${GetParameters}` into a variable and forward that (keeping
  `/D=` handled explicitly via the documented last-argument rule); test on Windows with
  `/S /D=C:\Custom\Path` and assert the slim core lands there.

### RH-32 — Release and architecture docs drifted from shipped pack flow and IPC surface

- **Premise:** TRUE (all three sub-claims verified).
- **Evidence:** (1) `RELEASING.md:113-123` says a tag push triggers `build.yml` to build
  and upload installers; `build.yml:38` says "quality gates only; installers live in
  tauri-*-build.yml" and `docs/code-notes/ci-workflows.md:65` confirms packaging jobs
  retired; `runtime-pack-publish.yml:37-38` is manual-only. (2) Stale "85-command /
  51-event" appears in `docs/API.md:11`, `docs/README.md:23`, `docs/adr/README.md:40`,
  `docs/migration/tauri-sidecar-bridge.md:16,204`, `docs/modules/sidecar_ws.md:13,26`;
  counted live: `_COMMAND_REGISTRY` in `voice_typer/server/ipc/registry.py` = **109**
  keys, Rust `allowlist.rs` = **105** command strings (108 literals minus
  `disallowed_command`, `disallowed_window`, `pending_full`), `event_bus.py` = **61**
  events. (3) `docs/adr/README.md` jumps 0028 → 0030 although `docs/adr/0029*` exists;
  `docs/README.md:58` links `adr/0014-tcp-ipc-session-token-auth.md` (file **missing**)
  and says ADRs are numbered `0000..0020`.
- **Behavior:** IMPROVE (docs accuracy) — no code change.
- **Rules:** E7 (one authority), C-DESIGN-1 analogue (showcase/docs must match shipped
  state), C-REVIEW-1 (do not touch Won't-Fix items).
- **Risk:** Low.
- **Verdict:** **KEEP**.
- **Score:** 64 — broad drift with real onboarding cost; mechanical edits.
- **Action plan:** update the six docs from the canonical registries (add a tiny script
  that regenerates the counts), fix RELEASING.md to point at the tauri-* workflows +
  manual pack publish, add ADR-0029 and remove the dead ADR-0014 link, fix the
  0000..0020 range.

### RH-33 — Release publisher is a 789-line module with two transports

- **Premise:** TRUE.
- **Evidence:** `scripts/release/publish_pack_release.py` is **789** lines. Boundaries
  match: `PublishResult` dataclass `:76-100`; gh command builders `:102-207`; urllib REST
  backend `:218-324`; `validate_assets` `:330`; `publish_release` `:354-446`; transport
  implementations `_publish_via_gh` `:447-507` and `_publish_via_api` `:508-617`; args
  `:618-696`; CLI `:697-789`. The two transports share only the data shape, not code.
- **Behavior:** IMPROVE (maintainability) — no behavior change intended.
- **Rules:** C-STRUCT-1/3/4 (one purpose per file, ~500-line budget), C-TEST-5.
- **Risk:** Medium — a broken release publisher blocks pack publishing; needs a dry run.
- **Verdict:** **KEEP**.
- **Score:** 58 — legitimate structural debt, low user impact; sequence after RH-28/30/31.
- **Action plan:** create-first split into `backends/gh.py`, `backends/api.py`,
  `publisher.py` (result + validation + dispatch), `cli.py`; keep re-exports so existing
  import sites resolve (C-STRUCT-3); prove both transports with mocked runners/HTTP and
  one dry run before removing the old module.

## Batch 5 — Plugins / comments / UI / docs (audited directly, 10 items)

### RH-1 — Internal STT plugins: one 961-line monolith and duplicated scaffolding

- **Premise:** TRUE.
- **Evidence:** `tools/internal_plugins/anthropic_stt/plugin.py` = **961** lines,
  `google_stt/plugin.py` = **461**. Shared scaffolding duplicated by name: `_post`
  (103 / 72), `_daemon_alive` (140 / 99), `shutdown_daemon` (162 / 107), `_node_exe`
  (174 / 119); Anthropic additionally owns `_daemon_status` (130), `_daemon_config`
  (144), `_bridge_ready` (154), `BridgeKeepalive` (189), `LevelMeter` (239). Both
  import `voice_typer.server.parent_watch.PARENT_PID_ENV_VAR` (`:33` / `:29`), so the
  host-liveness contract is already shared — the rest is copy/paste.
- **Behavior:** IMPROVE (maintainability) — no user-visible change intended.
- **Rules:** C-STRUCT-1/3/4, P2 (import the source, never copy logic), E7.
- **Risk:** Medium — plugin session lifecycle is timing-sensitive; the Google plugin's
  fixes (RH-2) must land on the shared version, not be lost in the split.
- **Verdict:** **KEEP** — sequence **after** RH-2 so the duplicated bugs are fixed once,
  then consolidated.
- **Score:** 64 — real structural debt with a clean shared seam.
- **Action plan:** create `tools/internal_plugins/_common/daemon.py` (HTTP + node
  resolution + keepalive + parent-watch wiring) and `_common/delivery.py` (paste +
  separator + bubble level), migrate both plugins onto them, delete the duplicates
  (E15), and keep both plugins' focused verification scripts green.

### RH-2 — Google STT plugin left behind by the sibling level-meter and separator fixes

- **Premise:** TRUE — current working tree still has both defects.
- **Evidence:** `google_stt/plugin.py:130-140` `_mute_bubble_levels` publishes a
  hardcoded `{"rms": 0.08, "peak": 0.12}` every 0.1 s; `:207` starts it as a daemon.
  `:254-259` `_deliver` calls `app.clipboard.paste(..., pasted_text=text)` with the raw
  text. Anthropic has the real `LevelMeter` (`:239-252`) and calls
  `pasted_text_with_separator` (`:689-691`); the shared helper lives at
  `voice_typer/server/clipboard_target_safety/caret_text.py:194` and
  `dictation_pipeline/paste_step.py:52`. Both plugin files are modified in the tree;
  the Google side was not updated.
- **Behavior:** BREAK-DOWNGRADE — fabricated bubble levels (contradicts C-UI-15: display
  what the system is actually using) and a missing paste separator (C-TRANS-2 class).
- **Rules:** C-UI-15, C-TRANS-2, P2 (import the source), E7.
- **Risk:** Medium — user-visible wrong state and spacing; low-risk fix.
- **Verdict:** **KEEP** — fix before RH-1's consolidation.
- **Score:** 78 — real user-facing defect with an already-proven sibling fix.
- **Action plan:** port the Anthropic `LevelMeter` (or reuse it from `_common`) and call
  `pasted_text_with_separator` in Google's `_deliver`; add tests pinning that the
  bubble level comes from real PCM and that the pasted text carries the separator;
  then proceed with RH-1.

### RH-3 — Dead HMR marker and truncated comment residue

- **Premise:** TRUE.
- **Evidence:** `voice_typer/client/src/renderer/src/lib/dictationStatus.ts:43,45,47,49`
  contains four near-identical markers (`// hmr reload marker`, `… 2`, `// hmr marker 3`,
  `// hmr marker 4`). `voice_typer/server/hotkeys/factory.py:29-32` has a docstring
  truncated mid-sentence (`"""``GetAsyncKeyState`` polling at ~125 Hz (8 ms cadence via
  ``kernel32.Sleep(8)`` with ``timeBeginPeriod(8)``, see`), several truncated inline
  comments (`# try the native subprocess backend first. It supports`,
  `# this is the polling fallback. It's`), and a task ID at `:78`
  (`# #4 PLAT-WAYLAND: detect Wayland …`). `tests/test_hotkeys.py:731,750` read
  `create_hotkey_backend.__doc__`, so any rewrite must keep the docstring contract.
  Real selection order from the code: mouse-button → mouse listener; native subprocess
  backend; Windows polling fallback; Wayland socket fallback; pynput.
- **Behavior:** IMPROVE (comment hygiene) — no behavior change; also removes a task ID
  from code (E4/C-STYLE-1/C-COMMENT-3).
- **Rules:** C-COMMENT-1/2/4/5, C-STYLE-1, E4.
- **Risk:** Low.
- **Verdict:** **KEEP**.
- **Score:** 60 — cheap cleanup with one pinned contract to preserve.
- **Action plan:** delete the four HMR comments; rewrite the docstring to one or two
  complete sentences describing the actual selection order; complete or delete the
  truncated comments; remove `#4 PLAT-WAYLAND`. Re-run the two hotkey docstring tests.

### RH-4 — Comment budget exceeded in Rust and renderer trees

- **Premise:** TRUE (numbers exact).
- **Evidence:** `python scripts/comment_ratio_metrics.py` reports `src-tauri/src`:
  144 files / 33,326 lines / 7,999 comments = **24.0%**; `voice_typer/client/src`:
  947 / 190,672 / 32,424 = **17.0%**; server 7.1%, workflows 17.5%, tests 3.8%.
  C-COMMENT-1's gate is ~10% per production tree. Densest files are tests embedded in
  `src-tauri/src` (`platform/logging_tests.rs` 705/2773) and type declarations
  (`push_events.ts` 407/983). No ratchet exists in scripts/workflows.
- **Behavior:** IMPROVE (maintainability) — no behavior change, but a mass rewrite risks
  deleting load-bearing SEC/RACE/C anchors (C-COMMENT-7).
- **Rules:** C-COMMENT-1, C-COMMENT-2, C-COMMENT-7 (never drop protected anchors), C-TEST-9
  (comment-pinned tests must stay green).
- **Risk:** High if done as a broad purge; Low if ratcheted.
- **Verdict:** **MODIFY** — record the baseline, fail on increase, chip away at the
  densest files; never bulk-delete.
- **Score:** 62 — real debt, but the fix must be a ratchet, not a cleanup sweep.
- **Action plan:** add a CI ratchet that asserts each production dir's ratio ≤ the
  recorded baseline and that protected tags (`SEC-`/`RACE-`/`PERF-`/`C-*`) are not
  removed; then shorten only comments that restate code, moving long rationales to
  `docs/code-notes/` with pointers (C-COMMENT-6).

### FV-31 — tests/ root holds a large flat pile of test files

- **Premise:** TRUE but stale; the entry's own recommendation is to defer.
- **Evidence:** current counts: **887** `test_*.py` directly under `tests/` and **253**
  in subdirectories (the entry says 716/243). It self-recommends "🟡 Defer — opportunistic
  migration only when a file is already being edited; bulk move is churn-for-churn."
- **Behavior:** NEUTRAL — a bulk move would be churn with no behavior gain.
- **Rules:** C-TEST-7 (test value over structure), C-STRUCT-1, C-AGENT-8 (no gratuitous moves).
- **Risk:** Low.
- **Verdict:** **REJECT** as standalone work — keep the opportunistic policy.
- **Score:** 30 — accurate observation, no actionable benefit; counts also stale.
- **Action plan:** none; migrate a file only when already editing it, and update the
  entry's counts if it stays in `review.md`.

### FV-37 — Entry modules carry `# noqa: F401` test-seam re-exports

- **Premise:** TRUE.
- **Evidence:** `voice_typer/server/ipc_server.py` has **18** `# noqa: F401`, `app.py`
  has **10**; they re-export names so tests can patch `ipc_server.<name>` /
  `app.<name>` (the C-ARCH-2 migration removed the `_pkg.X` indirection these replaced).
- **Behavior:** KEEP AS-IS — removing them breaks the documented test seams.
- **Rules:** C-ARCH-2 (tests patch the owning submodule; `__init__.py` stays a pure
  re-export), E13 (no noqa removal without cause), P1 (don't satisfy lint blindly).
- **Risk:** Low.
- **Verdict:** **REJECT** — the re-exports are deliberate and pinned by the migration.
- **Score:** 28 — cosmetic lint observation with a real regression cost.
- **Action plan:** none; if lint cleanliness matters, document the seam in a test rather
  than deleting the re-exports.

### RH-17 — Perf tests encode behavior as source-text assertions

- **Premise:** TRUE.
- **Evidence:** `tests/test_perf_fixes.py` + `tests/test_transcription_perf_fixes.py`
  contain **11** `inspect.getsource` uses out of **33** tests, including the literal
  source pins at `test_perf_fixes.py:24-31` and `test_transcription_perf_fixes.py:232-253`,
  `:306-337`, `:460-474`. Both files also hold real behavioral tests (e.g. lock-held-
  during-inference `:130-155`, unload drain `:161-209`). The migration is owned by
  `docs/adr/source-text-test-migration.md` and `CONTRIBUTING.md:1141+` ("No new
  `inspect.getsource` source-string tests"); note CONTRIBUTING.md:1150 points at an
  `arch-12` ADR filename that must be checked before relying on the link.
- **Behavior:** IMPROVE (refactor-safe tests) — no production change.
- **Rules:** C-TEST-7, C-TEST-10 (update every pin in the same change), C-COMMENT-7.
- **Risk:** Low-Medium — a few pins guard genuinely structural invariants.
- **Verdict:** **KEEP**.
- **Score:** 66 — real maintenance drag, bounded to two files.
- **Action plan:** classify each of the 11: delete those redundant with a behavioral
  test; convert the rest to probes with fakes/spies that observe the effect (single-
  flight, lock scope, env-var read) instead of the literal string; fix the stale ADR
  link in CONTRIBUTING.md; keep the 22 behavioral tests untouched.

### RH-18 — Catch-all regression dumps hide cross-domain mixing

- **Premise:** TRUE (count slightly stale: 532 lines, not 540).
- **Evidence:** `tests/test_platform_fix_regressions.py` = **532** lines / **22** classes
  spanning clipboard abstraction, empty clipboard, verification, safe key release,
  elevated/password targets, env-var validation, IME/AltGr, tray icon shapes, ICO
  support, MANIFEST.in, RDP, venv detection, mutex path/handle, VK fallback, macOS
  accessibility, contenteditable comment, clipboard sequence number, pynput docs.
  Siblings are also large catch-alls: `test_perf_clipboard_cred_security_fixes.py` 550,
  `test_service_vocab_template_privacy_fixes.py` 615, `test_config_group_fixes.py` 372.
  E3 explicitly exempts "cohesive single-domain test files" but calls out catch-all
  regression dumps as split candidates.
- **Behavior:** IMPROVE (test organization) — no behavior change.
- **Rules:** E3, C-STRUCT-1, C-TEST-5, C-TEST-7.
- **Risk:** Low — file moves only; keep test ids stable where possible.
- **Verdict:** **KEEP** (low priority).
- **Score:** 54 — real cohesion debt, zero user impact.
- **Action plan:** create-first split by domain under `tests/<domain>/` with re-exports
  or updated import paths; run the moved files only; no full-suite run from a worker.

### TTS-1 — TTS test cards: stats line, log colour, voice/language, icon-only test

- **Premise:** ALREADY FIXED in the working tree (almost entirely).
- **Evidence:** `TtsPanel.tsx:5-13` documents the shipped behavior — "icon-only voice
  test", "Failures become a plain-language toast; the card never renders engine text,
  timings or 'cached sample' diagnostics". Voice and language pickers ARE rendered,
  grouped by gender: `:402-448` voice `Select` with `t("tts.voice")` and gender groups,
  `:449-468` language `Select` with `t("tts.language")`. `[TTS]` is coloured in **both**
  tables (`server/log/formatters.py:71`, `src-tauri/src/platform/logging/color.rs:159`).
  Backend: `service.py:93` uses `wire_voice("magpie", chosen)`;
  `samples.py:34` `SAMPLE_CACHE_VERSION = 3`; `voices.py:12` documents Audio8 as a
  cloning engine with no preset speakers and `:47-59` lists **12** Magpie locales
  including `hi-IN`; `manager.py:405` `stop_playback`, `:437` `prewarm`,
  `tts/prewarm.py:37-48` non-blocking startup prewarm gated on `config.tts_enabled`
  (`:148` reports `tts_enabled`).
  **Still open:** playback is synchronous — `playback.py:75-76,106-107` `sd.play(data,
  sample_rate); sd.wait()` — so the "Generating" state covers playback.
- **Behavior:** IMPROVE — already delivered; one residual UX item.
- **Rules:** C-UI-1 (precise copy), C-UXERR-1/3 (plain language, details in logs),
  C-I18N-1 (new keys in all 8 locales — check `tts.voice`/`tts.language` coverage).
- **Risk:** Low.
- **Verdict:** **KEEP** — close all but the synchronous-playback item, which needs a
  separate owner decision (async playback changes the button state machine).
- **Score:** 84 — high-value UI/compliance work already shipped in the tree.
- **Action plan:** verify all 8 locales contain `tts.voice`/`tts.language`; decide
  separately whether to make playback non-blocking (would touch `playback.py` and the
  generate/playing button states); do not re-add the diagnostics line.

### RH-34 — Renderer request types lag the command allowlist

- **Premise:** TRUE — counts match exactly.
- **Evidence:** `voice_typer/client/src/renderer/src/types/ipc/requests.ts` has **93**
  `type: "..."` literals; Rust `allowlist.rs` has **105** commands (108 literals minus
  `disallowed_command`, `disallowed_window`, `pending_full`). Diff of the two sets gives
  exactly **12** missing: `get_microphone_volume`, `set_microphone_volume`,
  `set_output_volume`, `microphone_test_status`, `provider_list`, `provider_models`,
  `provider_test`, `provider_set_key`, `provider_clear_key`, `provider_set_domain`,
  `quit_app`, `restart_app`. They fall through the loose overload
  `lib/python-bridge/usePython.ts:167`
  `<T = unknown>(type: string, data?: Record<string, unknown>): Promise<T>`.
- **Behavior:** IMPROVE (type safety) — adding interfaces does **not** create a third
  allowlist: AGENTS.md says renderer types document the surface but are not an
  allowlist; enforcement stays the two existing registries.
- **Rules:** E9 (every IPC message needs matching send/receive types), C-PARITY-1
  (shared vocabulary in one table), AGENTS.md "renderer types are NOT an allowlist".
- **Risk:** Low.
- **Verdict:** **KEEP**.
- **Score:** 72 — concrete, mechanical typing gap with no enforcement change.
- **Action plan:** add request/response interfaces for the 12 commands in `requests.ts`
  using the existing shapes from the Python registry + Rust dispatch; add a round-trip
  test asserting every allowlisted command has a typed request (documentation-only pin,
  never a runtime gate); do not add a third allowlist.

---

## Executive summary — all 47 tasks

Verdict legend: KEEP = implement as filed; MODIFY = implement a narrowed/changed version;
REJECT = false premise / no standalone value; KEEP (host gate / already fixed) = no code
work left, close or verify on a host.

| Task | Category | Verdict | Score | Risk | Sub-agent / owner |
|---|---|---|---|---|---|
| P0 Windows/macOS host validation | Verification | KEEP (host gate) | 75 | Low | direct |
| S1-CR-146 StartupWMClass | Linux desktop | KEEP (host gate) | 45 | Low | direct |
| WL-1 Whisper load in worker | Backend | KEEP (already fixed) | 90 | Low | direct |
| PK-3 pack failure matrix | Verification | KEEP (host-only) | 65 | Medium | direct |
| SP-1 slim installer + pack | Release | KEEP | 82 | Medium-High | direct |
| SP-2 filter chain → worker | Architecture | KEEP (deferred) | 52 | High | direct |
| FV-31 flat tests root | Tests | REJECT | 30 | Low | direct |
| FV-37 F401 re-exports | Tests | REJECT | 28 | Low | direct |
| DC-14 uninstaller Startup .bat | Windows | KEEP (already fixed) | 86 | Low | direct |
| DC-15 per-arch conf fields | Tauri config | KEEP (already fixed) | 88 | Low | direct |
| TTS-1 TTS cards | UI/i18n | KEEP (mostly fixed) | 84 | Low | direct |
| RH-1 STT plugin monolith | Structure | KEEP | 64 | Medium | direct |
| RH-2 Google STT left behind | Correctness | KEEP | 78 | Medium | direct |
| RH-3 HMR marker / comments | Hygiene | KEEP | 60 | Low | direct |
| RH-4 comment budget | Hygiene | MODIFY | 62 | High if mass-purged | direct |
| RH-5 bubble hook per move | Perf | KEEP | 72 | Low-Medium | direct |
| RH-6 no-op resize reads | Perf | KEEP | 68 | Low | direct |
| RH-7 clamp single-flight | Correctness | KEEP | 70 | Medium | direct |
| RH-8 nudge monitor anchor | Correctness | KEEP | 74 | Low | direct |
| RH-9 notify job blind spots | CI | KEEP | 80 | Low | direct |
| RH-10 stale CI-errors.md | Docs | MODIFY | 52 | Low | direct |
| RH-11 type-check baselines | CI | MODIFY | 58 | Medium | direct |
| RH-12 Intel-Mac crypto pin | Supply chain | MODIFY | 66 | Medium | direct |
| RH-13 npm audit scope | Supply chain | REJECT | 25 | Low | direct |
| RH-14 pystray LGPL §4d | Compliance | KEEP | 60 | Low | direct |
| RH-15 signCommand | Release config | MODIFY | 58 | Medium | direct |
| RH-16 zombie parent PID | Lifecycle | KEEP | 56 | Medium | direct |
| RH-17 source-text pins | Tests | KEEP | 66 | Low-Medium | direct |
| RH-18 catch-all test dumps | Tests | KEEP | 54 | Low | direct |
| RH-19 runbook gaps | Docs | KEEP | 62 | Low | direct |
| RH-20 worker load drain | Lifecycle | KEEP | 76 | Medium | direct |
| RH-21 mic-level slot | Concurrency | KEEP | 66 | Low-Medium | direct |
| RH-22 prewarm timeout | Lifecycle | KEEP | 52 | Low | direct |
| RH-23 startup daemons | Lifecycle | MODIFY | 62 | Medium | direct |
| RH-24 fixed-sleep tests | Tests | KEEP | 66 | Low | direct |
| RH-25 numpy guard no-op | Tests | KEEP | 74 | Low | direct |
| RH-26 bare MagicMock modules | Tests | KEEP | 55 | Low | direct |
| RH-27 conftest suppressions | Tests | MODIFY | 56 | Low-Medium | direct |
| RH-28 uninstall pack leak | Windows | KEEP | 76 | Medium | direct |
| RH-29 torch-free gate | CI gate | KEEP | 68 | Medium | direct |
| RH-30 installer false success | Windows | KEEP | 78 | High | direct |
| RH-31 NSIS $CMDLINE | Windows | KEEP | 80 | Medium | direct |
| RH-32 docs drift | Docs | KEEP | 64 | Low | direct |
| RH-33 publisher 789 lines | Structure | KEEP | 58 | Medium | direct |
| RH-34 renderer IPC types | Types | KEEP | 72 | Low | direct |
| RH-35 config prune order | Data loss | KEEP | 92 | High | direct |
| RH-36 dictation_lost orphan | Contract | KEEP | 70 | Low | direct |

### Totals

- **47 tasks audited.** Verdicts: KEEP 37 (incl. SP-2 deferred; 7 are already-fixed,
  host-gate, or mostly-fixed), MODIFY 7, REJECT 3.
- **Top 5 by score:** RH-35 (92, config data loss), WL-1 (90, already fixed), DC-15 (88),
  DC-14 (86), TTS-1 (84).
- **Fabricated / wrong premises found:** RH-12's Fernet claim (the real module is
  `_text_crypto.py`, AES-GCM; no such Fernet module ever existed) and its
  "pip-audit only on non-darwin legs" claim (the step has no `if:` guard),
  RH-13's implied scope bug (deliberate), RH-23's "~10 unregistered
  threads" (actually 6 late, 4 without a stop event), FV-31's counts (716/243 → 887/253),
  RH-18's line count (540 → 532), RH-11's "compares against base ref" (half true by
  design), RH-29's comment claiming `torch\.` matches `torch/` (it does not).
- **Host-only, no headless action:** P0, S1-CR-146, PK-3, DC-15 residual, DC-14 residual,
  RH-7/RH-15/RH-16/RH-19/RH-28/RH-30/RH-31 host checks.
- **No code was changed.** Only this report file was created.
