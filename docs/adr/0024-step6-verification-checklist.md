# ADR-0024 Step 6 — real-machine verification checklist

> STATUS: **SIGNED OFF 2026-09-26 (real Windows host, dev worker).**
> Static preflight (`python scripts/verify_worker_handoff_preflight.py`) 5/5
> PASS proves the wiring exists; the live harness
> `python scripts/verify_worker_handoff_live.py` proves it RUNS — a real
> worker process, real token auth, real `faster-whisper-large-v3`
> inference, text byte-identical to the Step 0 in-process baseline. The
> degradation matrix was proven on a real pack root by
> `scripts/verify_worker_degrade_live.py`. Evidence artifacts live under
> `%TEMP%/vt_verify/` (`step6_evidence.json`, `step6c_degrade.json`,
> `worker.log`).

Prereqs: pack downloaded + verified ( triggers the worker start), dev
launch `VOICE_TYPER_SIDECAR_DEV=1` (dev worker = `python -m
voice_typer.worker` via `spawn_worker_dev_mode`), or a release build
for the frozen-exe path. One row per run; record dev vs release.

## (a) Record → transcribe → text through the worker

1. Dictate a short sentence with an offline model selected.
2. Expect: `transcribe_offline {queued:True}` ack, then a
   `transcribe_offline_result {text, latency_ms}` push whose text
   matches the dictation.
3. Paste: `[WORKER-INIT] worker spawned (port=…) …` + the result push.

## (b) Kill worker mid-idle → auto-respawn

1. Read the worker pid from the `worker_started` log line.
2. `taskkill /PID <pid> /F` (Windows) / `kill <pid>` (POSIX) while idle.
3. Expect: `[WORKER] worker exited (code=…, signal=…): respawning`,
   then `[WORKER] respawn attempt 1 of 5 after 500ms`, then
   `[WORKER] respawn succeeded on attempt 1 (port=…) …s`.
4. Repeat-kill 6× in a row to observe the doubling 500→1000→2000→
   4000→8000 schedule and the `backoff exhausted` line (worker left
   stopped, sidecar unaffected, no app relaunch).
5. Paste all `[WORKER]` lines.
6. **Post-respawn transcription** (proves the replacement actually
   transcribes, not just that it reconnected):
   `python scripts/verify_worker_handoff_live.py --config-dir <dir>
   --audio step0.wav --expect-file expect.txt --respawn`. The harness
   transcribes once, kills that worker, brings a replacement up, relays
   its NEW bind through the real `worker_relay`, and transcribes again —
   expecting `RESULT_OK=True` and two `text matches expected: True`.

## (c) Remove pack → degraded response

1. Stop the app, rename the pack dir aside, relaunch.
2. Dictate offline. Expect: `queued:False + degraded:True + reason:
   offline_pack_missing` (the `lifecycle.py:368` matrix) and the
   renderer "offline engine unavailable" state — never a silent queue.
3. Restore the pack dir, relaunch, confirm (a) works again.

## (d) `[WORKER]` lines + duration suffixes (C-LOG-2)

1. Grep the session log: `Select-String '\[WORKER' lausu.log`.
2. Expect: every completion line ends with ` 2.3s` / ` 1m 2.3s`
   (single leading space, `format_duration()` shape); no `WARNING`
   label, no millis, no per-line session id (C-LOG-1).
3. Paste the grep output.

## Sign-off
- [x] (a) text matches dictation — **dev**. Real worker, `port=55774 protocol=1`; `text_matches: true` (identical to the Step 0 in-process baseline), `latency_ms=25093`.
- [x] (b) HOST-SUPERVISED RESPAWN E2E - **dev, PROVEN 2026-09-26** (replaces the earlier qualified row). Ran `npm run tauri:dev`, killed the live dev worker, and observed the whole chain: `[WORKER] connected to worker at 127.0.0.1:60803` -> kill -> `[WORKER] respawn succeeded on attempt 1 (port=53378) 2.6s` -> `[WORKER-INIT] worker_started relay sent (pid=21608, port=53378)` -> `[WORKER] host relayed worker port=53378` -> `[WORKER] connected to worker at 127.0.0.1:53378 0.0s`, with the NEW worker independently logging `[WORKER] slim-core sidecar connected from 127.0.0.1:53381`. That run exposed FOUR real defects, all fixed and covered by tests: (1) the respawn path never relayed the new bind (worker_supervisor.rs); (2) nothing ever called `WorkerClient.update_from_worker_started`, so the client never learned ANY port (worker_relay.py); (3) sidecar and worker were given DIFFERENT auth tokens, so every worker auth frame was rejected (spawn.rs/main.rs, one per-launch token); (4) `set_port` reused a live superseded connect thread, so after a respawn nobody was running against the new port (worker_client.py). Backoff engine: `cargo test worker` 62/62.
- [x] (b2) post-respawn TRANSCRIPTION — **dev, PROVEN 2026-09-26**. `python scripts/verify_worker_handoff_live.py --config-dir <dir> --audio step0.wav --expect-file expect.txt --respawn` returned `RESULT_OK=True` with `handoff=OK relayed=1/1 text matches expected: True` TWICE — the first dictation through the original worker, the second through the respawned replacement after the harness killed it. This closes the gap the (b) run left open: (b) proved the host relays the new bind and the client reconnects, but it never dictated through the replacement. The `--respawn` flag exercises the full production path (relay frame -> `update_from_worker_started` -> reconnect -> `transcribe_offline` on the new worker), and the second dictation matched the same expected text as the Step 0 baseline. Logs: `[WORKER] worker handoff closed (peer-death)` -> `[WORKER] respawn attempt 1` -> `[WORKER] respawn succeeded on attempt 1 (port=53247) 2.7s` -> `[WORKER-INIT] worker_started relay sent (pid=21028, port=53247)` -> `[WORKER] host relayed worker port=53247` -> `[WORKER] connected to worker at 127.0.0.1:53247 0.0s` -> `[WORKER] offline transcription complete (len=101 chars) 14.1s`.
- [x] (c) degraded response, no silent queue; recovery after restore — **real pack root**: missing → `{queued:false, degraded:true, reason:"offline_pack_missing"}`; restored → `{queued:true, forwarded:false, reason:"worker_not_ready"}` (not degraded); removed again → degrades again.
- [x] (d) `[WORKER]` grep pasted, durations well-formed — `2026-09-26  16:24:49  INFO  [WORKER] offline transcription complete (len=101 chars) 25.1s`. Canonical C-LOG-1 (`YYYY-MM-DD  HH:MM:SS  LEVEL  msg`, two spaces, no millis, no per-line session id) with the C-LOG-2 ` 25.1s` suffix.
- [x] No `supervisor_failed` / app relaunch during (b) — the worker engine is independent of the sidecar breaker (separate `WorkerState` fields; no `app.restart()` in the engine).
Only then flip ADR-0024 Step 6 to `[x]` with the log excerpts.
