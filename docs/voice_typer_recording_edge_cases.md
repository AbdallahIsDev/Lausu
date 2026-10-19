# Voice Typer: Recording and Escape-Key Edge Cases — CLOSURE RECORD

Sections 1–4 were resolved in earlier sessions and removed from this
file (their pins live in code + tests, see `worklog.md`). The remaining
workstreams, §5 and §6, closed on 2026-10-19; §7's manual checks are now
automated regression tests. This file keeps the pre-fix problem text
next to what shipped, so a future reader can re-derive the reasoning —
it is not an open queue. Zero open boxes.

## 5. Cloud honesty + shutdown-during-transcription — FIXED (2026-10-19)

Two different problems share this section: (a) cloud cancel is
best-effort and the app never said so; (b) quitting mid-pipeline is a
whole family of stage × quit-path combinations, most of them unhandled.
Shutdown here means ALL ways the app can die, not just tray Quit.

**Quit paths (verified in code).** Graceful: tray Quit / Ctrl+C /
SIGTERM → `controller.quit()` → the 20s planned teardown
(`shutdown/cleanup.py::do_cleanup`: sequenced critical flushes, then
parallel teardowns). Violent: Task Manager kill, second Ctrl+C
(`os._exit(1)`, no cleanup at all), Windows logoff/shutdown (fast path:
`do_fast_cleanup()` — crash-recovery + history flushes at 1s timeouts,
`recorder.stop()`, then `os._exit(0)`), whole-OS power loss (nothing
runs). Console-window X on Windows only detaches the console; the tray
app survives.

**Cloud abort is best-effort (verified: `cloud/_engine.py`).** The abort
signal is checked BETWEEN attempts (`_transcribe_with_retry:266-274`),
never inside a live HTTP call (10s timeout; 120s for Gemini). Once a
request is in flight, the provider keeps processing and may return text
anyway; the pipeline drops the late result (the cycle is cancelled, so
the store/paste guards refuse it). Local models abort for real — this
item was cloud-only.

-   [x] Cloud requests already sent: app must not claim remote processing
    was stopped unless actually supported — no honest "cancel requested,
    provider may still complete; result will be dropped" feedback exists.
    **IMPLEMENTED 2026-10-19.** `server/cloud_backend.py`
    (`is_cloud_backend` / `active_engine_is_cloud`) detects the engine
    BEFORE the recovery unloads it; `recording_lifecycle_stop.py::_cancel_impl`
    passes `cloud_cancel_requested=` into
    `transcription_watchdog.py::force_recover`, which then surfaces tray
    `AppState.CANCELLING` +
    `state.recording_controller.cloud_cancel_requested` ("Cancel
    requested | cloud provider may still finish; result will be
    discarded"), the swapped notification, and bubble state
    `cloud_cancel_requested` (label `bubble.cloudCancelRequestedLabel`,
    "Cancel requested"). Keys ship in `server/i18n.py` + all 8 renderer
    locales (en/zh/hi/es/ar/fr/ru/de, genuine translations). Local
    engines keep the existing "Recovered | transcription timed out"
    surface unchanged. Tests: `tests/test_cloud_cancel_honesty.py`,
    `tests/server/test_recording_notification_i18n.py` (wrapper kwarg
    contract), `bubble-mid-flow-modes.test.tsx` (cloud-cancel block),
    `test_i18n_completeness.py` locale parity.

**Shutdown vs pipeline stage (verified against the teardown code).**
Transcription shutdown is GENERAL, not cloud-specific: the 3s join in
`shutdown/teardowns/recorder.py:84-94` fires for every engine, then
teardown continues around the still-live thread.

-   [x] Shutdown during active transcription: thread joined 3s, then
    shutdown continues and the late result may still complete store/paste
    after teardown started — against a half-closed history DB, a gone
    tray, a live clipboard. Define: discard-on-shutdown (mark the cycle
    cancelled first, let the existing guards drop the late result) vs
    finish-first (join without timeout).
    **IMPLEMENTED 2026-10-19 (discard-on-shutdown).**
    `shutdown/cleanup.py::_mark_active_cycle_cancelled` runs at the START
    of `do_cleanup` (and `do_fast_cleanup`) and marks `app._cycle_id`
    via the existing `_mark_cycle_cancelled`; the ALREADY-BUILT guards
    (`is_cycle_live` / store/paste refusal / clipboard fingerprint /
    conditional restore) then drop the orphan worker's late result — no
    new guard machinery. Finish-first was rejected: the 3s join sits
    inside the 20s shutdown budget and a hung engine (deadlocked
    ctranslate2) would stall quit indefinitely. Tests:
    `tests/test_shutdown_dictation_guards.py` (mark-before-phase
    ordering, orphan store+paste refusal via `CancellationGuard`, direct
    `_store_result` refusal).
-   [x] Shutdown during post-transcription stages (polish/vocab/store):
    narrower window, same root cause — a store may land in a DB that is
    mid-flush/close.
    **IMPLEMENTED 2026-10-19** by the same single mark: it covers every
    post-transcription stage because all of them re-check
    `is_cycle_live` at effect time (C-CONC-2). Pinned by
    `tests/test_shutdown_dictation_guards.py::TestOrphanWorkerRefusedAfterShutdown`.
-   [x] Shutdown during clipboard/paste (copy → Ctrl+V → delayed
    restore): a graceful quit kills the restore daemon thread, so the
    user's original clipboard is never restored (they keep our dictation
    text); the atexit restore (`_force_restore_pending_at_exit`) may
    fire into a half-torn-down world. A violent quit (kill, power loss)
    leaves our text on the clipboard with no possible recovery — state
    this as accepted, it cannot be fixed.
    **IMPLEMENTED 2026-10-19 (graceful) + ACCEPTED (violent).**
    `clipboard/restore.py::restore_pending_before_shutdown` runs
    synchronously, bounded (`_restore_clipboard_before_teardown`: 3s on
    the quit path, 1s on the fast path) BEFORE teardown can kill the
    daemon; it restores ONLY when the clipboard still holds the text
    this cycle wrote (fingerprint match — a newer copy is left alone).
    The atexit handler stays as a redundant backstop. A violent kill or
    power loss cannot run code at all: accepted-unfixable, the original
    clipboard is lost by construction. Tests:
    `tests/test_shutdown_clipboard_restore.py` (match restore,
    changed-clipboard left alone, unreadable clipboard still restores,
    idempotence, bounded hang warning).
-   [x] Shutdown during recording: verified SAFE by design — no partial
    audio file is ever written; in-RAM audio is dropped on both paths
    (graceful discard, violent death). Pinned as a regression guard so
    nobody "fixes" it into existence.
    **VERIFIED + PINNED 2026-10-19.**
    `tests/test_shutdown_dictation_guards.py::TestRecordingQuitWritesNoAudioFile`
    fails if any shutdown path starts writing audio to disk.
-   [x] Hotkeys die late: `teardown_hotkeys` runs in the parallel phase
    while the sequenced phase is still joining the transcription thread
    — a hotkey press mid-shutdown can start a new cycle during teardown.
    **IMPLEMENTED 2026-10-19 (entry gate, not a reorder).**
    `recording_lifecycle.py::_run_public_entry` refuses when
    `app._shutting_down_event.is_set() is True` (strict identity keeps
    MagicMock unit stubs off the gate) and logs `[HOTKEY BLOCKED]`. An
    entry gate covers hotkey, tray AND bubble starts — a plan reorder
    would only move the hotkey window. Tests:
    `tests/test_shutdown_dictation_guards.py::TestCycleStartGateDuringShutdown`.
-   [x] Double-Ctrl+C (`os._exit(1)`) skips even the crash-recovery
    flush by design; a recording in flight at that moment leaves no
    trace at all. Stated so a future "lost dictation" report has its
    answer ready.
    **ACCEPTED 2026-10-19 — no code change.** `os._exit(1)` runs nothing
    by definition; the intentional second Ctrl+C IS the "kill it now"
    gesture.
-   [x] `recovery.json` crash tolerance: a kill mid-flush can leave the
    file partially written — verify the next-boot `_load()` tolerates
    corruption (truncate/JSON-decode failure) without losing the whole
    store.
    **VERIFIED + PINNED 2026-10-19.**
    `crash_recovery/_io.py::_load` catches every read/parse failure,
    quarantines the corrupt file to `<name>.corrupt.<ts>-<pid>-<ns>`
    (atomic `os.replace`) and starts a fresh store; the partial bytes are
    preserved in the quarantine file. Pins:
    `tests/test_crash_recovery.py::TestPartialWriteTolerance`
    (truncated mid-entry, zero-byte) + `TestCrashRecoveryQuarantineCorrupt`
    (broken JSON, wrong shape, next save starts fresh).
-   [x] Restart/crash recovery must not resubmit discarded or stale
    recordings: VERIFIED SAFE — `check_on_startup()`
    (`crash_recovery/_store.py:132`) only reads unpasted entries for
    display/export; no code path re-drives audio or re-submits. Pinned
    as a regression guard.
    **VERIFIED + PINNED 2026-10-19.**
    `tests/test_crash_recovery.py::TestStartupNeverReDrives` (store bytes
    untouched, no event-bus publish, `DictationPipeline` never
    constructed, no `_paste_from_clipboard` call).

## 6. Policy questions — RESOLVED (2026-10-19)

1.  **Shutdown policy:** discard-on-shutdown (mark-then-guard) chosen
    over finish-first for active transcription AND post-transcription
    stages (rationale in §5: 20s budget, hung-engine stall); clipboard
    semantics are restore-synchronously-on-graceful (matching text only)
    and lost-on-violent as accepted.
2.  **Cloud honesty wording:** exact user-facing text (all 8 locales):
    tray + trayState — "Cancel requested | cloud provider may still
    finish; result will be discarded"; bubble label — "Cancel
    requested"; notification — "Cancellation requested. The cloud
    provider may still finish processing; the result will be
    discarded."

## 7. Manual-test pointers — REPLACED BY AUTOMATED PINS (2026-10-19)

-   Shutdown during active transcription (discard vs finish-first) →
    `tests/test_shutdown_dictation_guards.py::TestDiscardOnShutdownMark`
    + `TestOrphanWorkerRefusedAfterShutdown`.
-   Shutdown during paste / clipboard outcome on quit →
    `tests/test_shutdown_clipboard_restore.py`.
-   Cloud-cancel honesty on the ESC path →
    `tests/test_cloud_cancel_honesty.py` + the bubble cloud-cancel
    vitest block.
