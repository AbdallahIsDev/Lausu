# Spontaneous plugin recording on app launch — 2026-11-27

## Evidence before the fix (read-only investigation)

- Owner log `2026-11-27 00:36:06..00:36:30` (Claude, visible): `start requested (cycle=#1)` at 00:36:06, BEFORE hotkey registration at 00:36:08/09. Then `Chrome launch ... caller=hotkey-start` (00:36:21), `recording started (cycle=#1)` + bubble + volume duck (00:36:24), ESC cancel (00:36:30). The excerpt the owner quoted omitted the early start line; it is in the full log.
- Reproduced deterministically at `00:44:16..00:44:29` with Google STT active and `plugin_visible=false`: same stale command, `start requested` at 00:44:16, `recording started` + `Bubble shown` + duck at 00:44:29; canceled at 00:44:42.

## Root cause

`voice_typer/server/plugin_dev_driver.py:64` reset `last_seq = 0` in every new process; `:69-73` executed ANY existing `debug/dev-command/command.json` with `seq > 0`. The file on disk was `{"seq":9,"cmd":"toggle"}` from 22:59:33 of the previous day; `result.json` was rewritten at 00:36:24 when the replayed toggle finished. `:83` calls the real wrapped `app.toggle_dictation()` installed by `voice_typer/server/internal_plugin_hook.py:343-386`, which reaches `PluginSession.start()` and `/start` (`tools/internal_plugins/_common/bridge/session.py:602-615,694-724,814`). Introduced by commit `d86b8adad` (`git blame -L 62,76`), 2026-11-26 23:06.

Ruled out with code evidence:

1. Pending start / activation: `sync_selection` → `_activate_plugin` → `activate()` → `session.activate_platform_async()` (`internal_plugin_hook.py:240-271`, `session.py:290-334`) calls `/warm` and `prepare_platform`, never `/start`, toggle or start. `PluginSession.start()` has one caller: `toggle()` (`session.py:615`).
2. Verified click / ready gate / relaunch: the only `/start` POST is `session.py:814` inside `_start()`; the ready gate and `RelaunchBudget` only launch/wait/re-resolve tabs. Becoming ready does not create a start.
3. Other non-key callers: hotkey (`hotkey_dispatch.py:70`), IPC button (`handlers/dictation_handlers.py:21` → `service/dictation.py:21`), tray (`tray_menu.py:263/410`), dev driver (`plugin_dev_driver.py:83`). Manual verifier scripts are not startup paths. The startup replay was the only non-user caller observed.

## Fix

- One origin authority: `voice_typer/server/dictation_origin.py` (`USER_ORIGINS`, `user_action(origin)`, `authorize(caller)`). Hotkey, IPC button, tray click and an explicit dev command set an origin; every other caller is refused at the application entry with one WARN naming the caller.
- Every start is logged with its origin: `start requested (cycle=#N, origin=hotkey|button|tray|dev-driver)`.
- Dev driver takes ownership of a fresh command by atomic rename, checks file mtime against process start, deletes a stale command without executing it, and deletes consumed claims/commands. Frozen builds and packaged installs cannot enable it.

## Verification

- Old code (detached worktree at `428685a06`, new tests copied in): 4 guard/dev-channel tests failed (stale toggle replayed, no-origin toggle accepted, missing origin line, command not consumed). New tree: 234 plugin tests plus 414 targeted tests (plugins/app/handlers/gate/hotkey/tray/packaging) pass; node bridge 109/109.
- An intermediate wide run was 1083 passed / 7 failed: 6 direct test calls lacked the new origin (wrapped in `user_action("hotkey")`), one was the unrelated `cublas64_12.dll is not found` environment error; focused reruns of all seven pass.
- mypy ratchet: current tree 554 errors, better than clean HEAD `60f26c27a` (555). The per-code `index` 9→10 FAIL already exists on clean HEAD, so it was not introduced here. pyrefly diagnostics decreased (3998 → 2803 lines).
