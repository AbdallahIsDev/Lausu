# Bubble overlay: right-click artifact hunt (DO NOT RETRY LISTED FIXES)

Status: RESOLVED 2026-10-12. The pill showed a small empty gray rounded
square (~40x22px) over its left text area on right-click WITH drag.
Root cause (§8). Everything below is the trail; read before touching
this area again.

## What it is NOT (proven live, 2026-10-12)

- NOT the Win32 system menu. Probed the live pill HWND twice
  (`GetWindowLongPtrW`): `WS_SYSMENU` absent. Posted the full OS
  sequences at it (`WM_NCRBUTTONDOWN/UP`, `WM_CONTEXTMENU`,
  `WM_SYSCOMMAND/SC_KEYMENU`, caption double-click): zero `#32768`
  menu windows, state stays NORMAL. Scripts used:
  `probe_click2_tmp.py` (deleted after use; pattern kept in §7).
- NOT WebView2's default context menu (has items; JS `contextmenu`
  prevention is on the pill).
- NOT the annotate button (recording-mode only; square shows in idle
  "Ready" mode) and NOT the visualizer (always renders bars).

## What reproduces it (proven live)

A real right-click WITH a few px of drag over the pill text paints a
gray box over ~1 char. A click with zero movement paints nothing.
Repro script pattern (`probe_seldrag_tmp.py`, deleted): move cursor
to pill text, `SendInput` right-down, move +9px, right-up, screenshot.
That is the signature of a **text-selection highlight**, but see §5.

## Tried, in order (do not repeat)

1. **Manual drag hook** (`useBubbleDrag`, rAF-coalesced `moveBy`).
   Removed OS drag entirely. REVERTED: janky vs OS drag, worse
   cross-platform. Files deleted.
2. **Conf flags** `maximizable/minimizable/closable: false` on all 5
   bubble blocks (`tauri.conf.json`, `tauri.macos.conf.json`,
   `tauri.windows-{x86_64,x86_64-slim,aarch64}.conf.json`). Only grays
   menu items. Pinned by `tests/tauri/test_bubble_window_flags.py`.
3. **WS_SYSMENU strip** (`SetWindowLongPtrW` + `SWP_FRAMECHANGED` in
   `commands/bubble/window.rs`, runs on setup + every show). Log
   marker: `[BUBBLE] bubble chrome hardened (system menu removed)`.
   Live probes show the bit absent afterwards. Did not stop the square.
4. **Why the strip can't hold**: tao 0.37.1 rebuilds the style WITH
   `WS_SYSMENU` baked in on every flag flip (`window_state.rs`,
   `to_window_styles` + `apply_diff` → `SetWindowLongW` +
   `SWP_FRAMECHANGED`). Any show/hide/resize can resurrect the shell.
   Mitigations landed: strip also runs on hide, resize
   (`bubble_resize`), setup (`harden_bubble_on_setup`), and bubble
   `Resized`/`Moved`/`ScaleFactorChanged` events (`window_events.rs`).
5. **DeleteMenu all 6 items** (same module). Deletions are durable
   (tao never calls `GetSystemMenu(TRUE)`), so a resurrected shell
   opens onto an empty menu. The square could be exactly this: an
   empty shell. Still not gone.
6. **wndproc subclass** (`swallow_bubble_caption_clicks`, same
   module): swallows `WM_NCRBUTTON*` so no trigger reaches
   `DefWindowProc` regardless of style bits. Log marker:
   `[BUBBLE] caption-click swallow installed (...)`. Still square.
7. **Text-selection kill** (`Bubble.tsx`): `selectstart` prevention
   on the pill + `removeAllRanges()` on contextmenu + `select-none`
   class retained. Pinned by
   `bubble/__tests__/bubble-text-selection.test.tsx`. Still square.

## 8. Resolution: right-mousedown word-select cascade

Decisive experiments (all live, same session):

- Motionless right-click: clean. Pure 4s hover: clean. Left
  double-click: clean (so `select-none` + `selectstart` prevention
  DO work for the left button).
- Right-click + ~9px drag over text: gray box, 4/4, always over the
  drag range. A separate OS window was ruled out (window census
  during button-hold and after release: no `#32768`, no tooltip
  class, no new window at all).
- Pixel forensics (`pill_sq.png`): fill `#2B2B2B`-ish, ZERO
  blue-dominant pixels → NOT a DOM `::selection` paint (which is
  blue) and NOT solved by the `#bubble-root ::selection`
  transparency rule that was added first (verified live in served
  CSS, square persisted).

Mechanism: right-mousedown word-selects for the context menu BEFORE
any `selectstart`/`contextmenu` handler can prevent it; the menu
itself dies to `preventDefault`, but the orphan range keeps a
browser-painted marker that `selectstart` prevention never saw
(the event fires for left-drag selection, evidently not for this
right-button path) and that `::selection` styling does not recolor
in this WebView2 (transparent overlay, never-focused document).

Fix (`Bubble.tsx`, renderer-only, HMR-live, no rebuild): cancel
right-mousedown at initiation —
`onMouseDown={e.button === 2 ? e.preventDefault() : undefined}`
semantics via `handlePillMouseDown`. No range ever exists, so no
paint and no menu cascade. Left button untouched (OS caption drag
preserved). Pinned by `bubble-text-selection.test.tsx` (right
canceled, left passes through).
Verified live: 2 consecutive right-drag probes photograph a clean
pill afterwards (was 4/4 square before).

H2 (swallow input at the true entry point) IMPLEMENTED after the
in-page layers proved insufficient: real button messages go
straight to the `Chrome_RenderWidgetHostHWND` child and never pass
the top-level proc, so the top-level `NCRBUTTON` swallow only ever
caught synthetic posts. `swallow_bubble_caption_clicks` now
installs the same proc on the render-host child (found live via
`EnumChildWindows` on every harden call, skipped when already
installed, no restore on destroy: process-lifetime install).
Swallowed there: `WM_RBUTTONDOWN/UP/DBLCLK` + `WM_CONTEXTMENU`
(left input untouched). The old pill-level `onMouseDown` guard and
`selectstart`/`contextmenu` prevention stay as backup for anything
that still reaches the page.

§8 Deadlock (2026-10-12): `harden` ran synchronously inside the
`on_window_event` Resized/Moved handler, which executes ON the main
thread, while both harden halves dispatched unconditionally via
`run_on_main_thread` (blocks until the main thread runs the
closure). First bubble show → Resized → main thread waits on
itself → permanent hang ("Not Responding", frozen splash, ~0 CPU).
Two fixes, both kept: (1) the event handler hops off-thread
(`std::thread::spawn`, work is idempotent); (2) the swallow does
its liveness reads (proc check + child lookup) on the caller
thread and dispatches only when an install is actually needed, so
steady-state event calls never touch the main thread at all (and
a dead child HWND is re-checked with `IsWindow` inside the
closure, never attaching to a recycled handle).

§9 The real hang (2026-10-12): the wndproc held the `PREV_PROCS`
std-Mutex guard ACROSS the chained `CallWindowProcW`. tao /
Chromium routinely send messages synchronously to our OTHER
subclassed window (top ↔ render-host child), re-entering the proc
on the same thread; the non-reentrant relock deadlocked the UI
thread at the first bubble show, every run: frozen splash,
"Not Responding", ~0 CPU, then worker exhaustion as tokio threads
parked on the dead main thread (heartbeat timeouts, keepalive
death, pointless respawns — all fallout, not separate bugs).
Fix: copy the previous proc out, drop the guard, THEN call.
Pinned by the `CallWindowProcW(*prev`-absent /
`CallWindowProcW(Some(p)`-present asserts in
`tests/tauri/test_bubble_window_flags.py`.

## Former hypothesis stack (kept for the trail)

- H1: the running binary predates a fix. Rust changes need a host
  rebuild + relaunch; renderer changes need Vite HMR. ALWAYS verify
  FIRST via log markers before any new theory:
  `[BUBBLE] bubble chrome hardened (...)` AND
  `[BUBBLE] caption-click swallow installed (...)`.
  If either is absent, the session is stale: Ctrl+C, `npm run
  tauri:dev`, wait for the cargo rebuild to finish relaunching.
- H2: the square is painted by WebView2/Chromium itself (selection
  paint or drag feedback that ignores page CSS/`selectstart` in this
  build). Next step if H1 is ruled out: extend the wndproc swallow
  to `WM_RBUTTONDOWN/UP/DBLCLK` so the webview never sees the right
  button at all (left drag/click untouched). Drafted, NOT yet
  implemented.
- H3: the square is not click-caused (always present, only noticed
  while right-clicking). Check: photograph the pill untouched for
  10s. If present without input, inspect pill DOM/CSS (tooltip with
  empty text, `title=""`, badge, shimmer) instead of input paths.

## 2026-10-12: "markers absent" episode (read before re-testing!)

The user reported NEITHER log marker present
(`[BUBBLE] bubble chrome hardened (...)`,
`[BUBBLE] caption-click swallow installed (...)`) while the square
persisted. Measured on the machine: `target/debug/lausu-tauri.exe`
mtime NEWER than `window.rs` mtime, host PID started after the
build. So the code WAS live — markers print exactly once per
process on the first harden run (setup if the bubble window exists
yet, otherwise first show). Absent markers therefore mean one of:

- The log being searched is not the current run's (terminal
  scrollback vs `%APPDATA%\lausu\logs\lausu.log` vs `worker.log` —
  the markers come from the Rust host, never the worker log).
- The startup lines scrolled past (markers print at 07:00:10-style
  boot, buried under hundreds of later lines).
- `get_webview_window("bubble")` returned `None` in setup AND no
  `show_bubble_window` ran yet (impossible while the pill is
  visible — every show hardens).

Verification commands (PowerShell):

```powershell
Select-String -Path "$env:APPDATA\lausu\logs\lausu.log" -Pattern 'caption-click swallow|chrome hardened'
tasklist /FI "IMAGENAME eq lausu-tauri.exe"
```

Exactly ONE host PID is healthy. Two means a stale pre-fix host is
still alive owning the visible pill — kill the older PID, the square
goes with it. If markers are present and the square persists, continue
at H2/H3 above.

## Live-probe recipe (Python, ctypes, production shape)

- Find pill: `EnumWindows` over the `lausu-tauri.exe` PID, visible
  window 60-600px wide × 20-140px high.
- Read style: `GetWindowLongPtrW(hwnd, GWL_STYLE) & WS_SYSMENU`.
- Fire OS messages with `PostMessageW` (`WM_NCRBUTTONDOWN/UP`,
  `WM_CONTEXTMENU`, `WM_SYSCOMMAND/SC_KEYMENU`, double-click
  sequence), then poll `EnumWindows` for visible `#32768` class.
- Screenshot regions with PIL `ImageGrab`; move the real cursor
  with correct 40-byte `INPUT` structs (`SendInput` returns 1 per
  event — see `INPUT_SIZE` saga in `hotkeys/windows/_win32_keyboard.py`,
  where a 32-byte struct silently broke every synthetic keypress);
  always save/restore cursor with `GetCursorPos`/`SetCursorPos`.
- Never left-click/drag the pill (moves the user's window), never
  trigger dictation (pastes into their focused field).
