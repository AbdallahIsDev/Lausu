use serde_json::{json, Value};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use tauri::{Emitter, Manager};

use crate::state::SidecarState;

/// Who asked for the hide. Backend-initiated hides need the renderer
/// exit animation; host-initiated ones must NOT re-emit `bubble:hide`
/// (that would loop back into `bubble_hide_complete` forever).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum BubbleHideSource {
    Backend,
    RendererComplete,
    Dismiss,
}

#[cfg(target_os = "windows")]
use super::coalesce::{needs_follow_up, SingleFlight};

pub(crate) fn wants_bubble_show(event_type: &str) -> bool {
    event_type == "bubble_show"
}

/// `bubble_position` from a `bubble_config` payload, if it names an edge.
/// Anything else (missing key, wrong type, unknown keyword) yields
/// `None` so the reader places nothing (fail-closed, no guessed edge).
pub(crate) fn configured_edge_from_payload(payload: &Value) -> Option<&str> {
    match payload.get("bubble_position").and_then(|v| v.as_str()) {
        Some("top") => Some("top"),
        Some("bottom") => Some("bottom"),
        _ => None,
    }
}

/// Recording/transcribing implies a visible bubble. A host-side dismiss
/// (shortcut or Schneider button) hides the window without touching the
/// sidecar coordinator, so the next `bubble_show` would no-op there and
/// the bubble would stay hidden until restart. Re-showing on the active
/// states makes a fresh recording (or media transcription) always bring
/// the bubble back; `show_bubble_window` is idempotent when visible.
pub(crate) fn is_active_bubble_state(event_type: &str, payload: &Value) -> bool {
    event_type == "bubble_set_state"
        && matches!(
            payload.get("state").and_then(|s| s.as_str()),
            Some("recording") | Some("transcribing")
        )
}

/// Adds `WS_EX_NOACTIVATE` to a bubble's extended style. A show that activates
/// steals focus from the field being dictated, so the pill must never take the
/// foreground (A4). Kept pure so the invariant can be unit-tested.
#[cfg(target_os = "windows")]
pub(crate) fn bubble_no_activate_style(style: i32) -> i32 {
    use windows::Win32::UI::WindowsAndMessaging::WS_EX_NOACTIVATE;
    style | (WS_EX_NOACTIVATE.0 as i32)
}

#[cfg(target_os = "windows")]
fn apply_no_activate_style(window: &tauri::WebviewWindow) {
    use windows::Win32::Foundation::HWND;
    use windows::Win32::UI::WindowsAndMessaging::{
        GetWindowLongPtrW, SetWindowLongPtrW, GWL_EXSTYLE,
    };

    let raw = match window.hwnd() {
        Ok(hwnd) => hwnd.0 as isize,
        Err(e) => {
            log::warn!("[BUBBLE] no-activate style skipped (no HWND): {e}");
            return;
        }
    };
    let target = HWND(raw as *mut std::ffi::c_void);
    unsafe {
        let style = GetWindowLongPtrW(target, GWL_EXSTYLE);
        let updated = bubble_no_activate_style(style as i32) as isize;
        if updated != style {
            SetWindowLongPtrW(target, GWL_EXSTYLE, updated);
        }
    }
}

/// On-screen truth: Tauri state AND Win32 WS_VISIBLE AND not DWM-cloaked.
/// IsWindowVisible alone reports "visible" for cloaked windows (different
/// virtual desktop, minimized UWP-style presentation).
pub(crate) fn bubble_presented(tauri_visible: bool, is_window_visible: bool, cloaked: u32) -> bool {
    tauri_visible && is_window_visible && cloaked == 0
}

#[cfg(target_os = "windows")]
fn is_bubble_presented(window: &tauri::WebviewWindow) -> bool {
    use windows::Win32::Foundation::HWND;
    use windows::Win32::Graphics::Dwm::{DwmGetWindowAttribute, DWMWA_CLOAKED};
    use windows::Win32::UI::WindowsAndMessaging::IsWindowVisible;

    let Ok(hwnd) = window.hwnd() else {
        return false;
    };
    let raw = HWND(hwnd.0 as *mut std::ffi::c_void);
    let is_visible = unsafe { IsWindowVisible(raw).as_bool() };
    let mut cloaked = 0u32;
    let queried = unsafe {
        DwmGetWindowAttribute(
            raw,
            DWMWA_CLOAKED,
            &mut cloaked as *mut u32 as *mut std::ffi::c_void,
            std::mem::size_of::<u32>() as u32,
        )
    }
    .is_ok();
    bubble_presented(
        window.is_visible().unwrap_or(false),
        is_visible,
        if queried { cloaked } else { 0 },
    )
}

pub(crate) fn reconcile_bubble_visibility(app: &tauri::AppHandle) -> bool {
    let state: tauri::State<'_, Arc<SidecarState>> = app.state();
    if !state.bubble_show_requested.load(Ordering::SeqCst) {
        return false;
    }
    let Some(window) = app.get_webview_window("bubble") else {
        return false;
    };
    #[cfg(target_os = "windows")]
    let presented = is_bubble_presented(&window);
    #[cfg(not(target_os = "windows"))]
    let presented = window.is_visible().unwrap_or(false);
    if presented {
        return false;
    }
    // One line per stuck episode: a per-tick INFO would spam the log while a
    // re-show is impossible (C-LOG-8).
    if reassert_log_due() {
        log::info!("[BUBBLE] visibility reassert: requested=visible actual=hidden");
    }
    match show_bubble_window(app) {
        Ok(()) => true,
        Err(e) => {
            log::warn!("[BUBBLE] visibility reassert failed: {e}");
            false
        }
    }
}

/// True at most once per 60 s, so a persistent mismatch logs one line a minute.
fn reassert_log_due() -> bool {
    static LAST_MS: AtomicU64 = AtomicU64::new(0);
    let now = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0);
    let last = LAST_MS.load(Ordering::Relaxed);
    if now.saturating_sub(last) < 60_000 {
        log::debug!("[BUBBLE] visibility still hidden (reassert in progress)");
        return false;
    }
    LAST_MS.store(now, Ordering::Relaxed);
    true
}

/// Level-triggered backstop: the host owns the HWND, so it re-asserts a
/// requested-visible bubble even if a hide notification was never sent.
pub(crate) fn start_bubble_reconciler(app: tauri::AppHandle) {
    tauri::async_runtime::spawn(async move {
        let mut ticker = tokio::time::interval(std::time::Duration::from_secs(2));
        loop {
            ticker.tick().await;
            reconcile_bubble_visibility(&app);
        }
    });
}

pub(crate) fn show_bubble_window(app: &tauri::AppHandle) -> Result<(), String> {
    let state: tauri::State<'_, Arc<SidecarState>> = app.state();
    state.bubble_show_requested.store(true, Ordering::SeqCst);
    let window = app
        .get_webview_window("bubble")
        .ok_or("bubble window not found")?;
    #[cfg(target_os = "windows")]
    apply_no_activate_style(&window);
    // Show never repositions: the pill stays where the user put it
    // across visibility and mode transitions. Initial placement runs
    // from the sidecar's `bubble_config` frame before the first show
    // (WS reader -> `apply_bubble_config_edge`); drags are session-local
    // and are never persisted. The one correction is the work-area clamp:
    // a pill left under the taskbar (or on a monitor that has since
    // changed) must not be shown unreachable — the clamp is a no-op when
    // the position is already inside.
    if let Err(e) = super::clamp::clamp_bubble_into_work_area(app) {
        log::debug!("[BUBBLE] work-area clamp before show skipped: {e}");
    }
    window.show().map_err(|e| e.to_string())?;
    #[cfg(target_os = "windows")]
    if !is_bubble_presented(&window) {
        // tao only issues ShowWindow when its TRACKED VISIBLE flag flips, so a
        // window hidden out of band stays hidden through `window.show()`.
        // Force the OS call (never activating) so the pill really appears.
        // DEBUG on purpose: a stuck window would otherwise log per 2 s tick;
        // `reconcile_bubble_visibility` owns the rate-limited INFO line.
        if force_show_no_activate(&window) {
            log::debug!("[BUBBLE] forced present after window.show() reported success");
        }
    }
    harden_bubble_chrome(&window, true);
    Ok(())
}

/// OS-level show that never activates, for windows whose tracked visibility
/// flag and real state disagree.
#[cfg(target_os = "windows")]
fn force_show_no_activate(window: &tauri::WebviewWindow) -> bool {
    use windows::Win32::Foundation::HWND;
    use windows::Win32::UI::WindowsAndMessaging::{IsWindowVisible, ShowWindow, SW_SHOWNOACTIVATE};

    let Ok(hwnd) = window.hwnd() else {
        return false;
    };
    let raw = HWND(hwnd.0 as *mut std::ffi::c_void);
    let _ = unsafe { ShowWindow(raw, SW_SHOWNOACTIVATE) };
    unsafe { IsWindowVisible(raw).as_bool() }
}

/// Cross-platform bubble-chrome hardening. Runs on every show
/// (idempotent).
///
/// - Windows: the pill drags through an OS caption region, which
///   summons the system menu on right-click even on a frameless
///   window. The single mechanism is a thread-local `WH_GETMESSAGE`
///   hook (`ensure_bubble_msg_hook`) eating right-button queue
///   messages before any proc sees them — unlike subclassing, it
///   cannot be raced out by tao's proc restores. A one-shot menu
///   gutting covers the keyboard corner (Alt+Space sends
///   `WM_SYSCOMMAND` synchronously, which no queue hook can eat).
///   Left-button drag and double-click zoom are unaffected (zoom is
///   separately disabled by `maximizable/minimizable: false` in each
///   tauri conf bubble block).
/// - macOS: the bubble is borderless with no titlebar, so there is
///   no titlebar menu and no double-click zoom box. Nothing to do.
/// - Linux: frameless + skip-taskbar windows expose no caption menu
///   on right-click under X11 or Wayland. Nothing to do.
///
/// `sync_frame` requests a frame/input re-sync after tao's flag
/// flips (show/hide/resize/setup/scale). It MUST stay false for
/// `Moved`: a frame recalc inside an active user drag would fight
/// the move loop.
pub(crate) fn harden_bubble_chrome(window: &tauri::WebviewWindow, sync_frame: bool) {
    #[cfg(target_os = "windows")]
    {
        strip_bubble_system_menu(window, sync_frame);
        gut_bubble_system_menu(window);
        // A structural event is the trigger to re-enumerate late-created WebView
        // children; a pure move is not (that is the hot path we are coalescing).
        ensure_bubble_msg_hook(window, sync_frame);
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = window;
        let _ = sync_frame;
    }
}

#[cfg(target_os = "windows")]
static HARDEN_FLIGHT: SingleFlight = SingleFlight::new();
#[cfg(target_os = "windows")]
static HARDEN_SYNC_FRAME: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);

/// Coalesce geometry-event chrome hardening into one worker per settle burst.
///
/// The event handler runs on the main thread. Enumerating the bubble's child
/// tree there (and spawning a fresh OS thread per pointer sample) was pure
/// churn during a drag; one worker per burst covers the same structural work.
#[cfg(target_os = "windows")]
pub(crate) fn schedule_bubble_hardening(bubble: tauri::WebviewWindow, sync_frame: bool) {
    use std::sync::atomic::Ordering;
    use std::time::Duration;

    if sync_frame {
        HARDEN_SYNC_FRAME.store(true, Ordering::SeqCst);
    }
    if !HARDEN_FLIGHT.arrive() {
        return;
    }
    let worker = std::thread::Builder::new()
        .name("bubble-chrome-harden".into())
        .spawn(move || {
            let settle = Duration::from_millis(super::clamp::DRAG_SETTLE_MS);
            let settled;
            loop {
                let seen = HARDEN_FLIGHT.generation();
                std::thread::sleep(settle);
                if HARDEN_FLIGHT.generation() == seen {
                    settled = seen;
                    break;
                }
            }
            // Consume the structural flag before releasing so a Show/Resize
            // that lands during the burst is still honored by this worker.
            let structural = HARDEN_SYNC_FRAME.swap(false, Ordering::SeqCst);
            HARDEN_FLIGHT.release();
            harden_bubble_chrome(&bubble, structural);
            if needs_follow_up(settled, HARDEN_FLIGHT.generation()) {
                schedule_bubble_hardening(bubble, false);
            }
        });
    if worker.is_err() {
        HARDEN_FLIGHT.release();
        log::warn!("[BUBBLE] chrome-hardening worker could not start");
    }
}

/// Non-Windows: no caption menu, no hook, no worker to schedule.
#[cfg(not(target_os = "windows"))]
pub(crate) fn schedule_bubble_hardening(_bubble: tauri::WebviewWindow, _sync_frame: bool) {}

/// Strip the OS system menu from the bubble window (Windows only).
///
/// This does two jobs, and the second is why it is back: besides
/// removing the menu shell, the `WS_SYSMENU` strip plus the
/// `FRAMECHANGED` pass re-syncs the frame and input routing that
/// caption drag depends on (verified live: sysmenu present → drag
/// frozen; sysmenu stripped → drag works; the queue hook alone
/// cannot restore it). The style edit runs only when dirty, so
/// steady-state calls (including per-tick `Moved` during a drag)
/// are pure reads. Dragging is unaffected by the strip itself.
#[cfg(target_os = "windows")]
fn strip_bubble_system_menu(window: &tauri::WebviewWindow, sync_frame: bool) {
    use std::sync::atomic::{AtomicBool, Ordering};

    use windows::Win32::Foundation::HWND;
    use windows::Win32::UI::WindowsAndMessaging::{
        GetWindowLongPtrW, SetWindowLongPtrW, SetWindowPos, GWL_STYLE, SWP_FRAMECHANGED,
        SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, WS_SYSMENU,
    };

    static HARDEN_LOGGED: AtomicBool = AtomicBool::new(false);

    // `window.hwnd()` returns tauri's own `windows`-crate HWND, which
    // may differ from ours: cross the boundary through the raw value.
    let raw = match window.hwnd() {
        Ok(hwnd) => hwnd.0 as isize,
        Err(e) => {
            log::warn!("[BUBBLE] system-menu strip skipped (no HWND): {}", e);
            return;
        }
    };
    // Reading the style is safe from any thread; only the mutation
    // must run where the window was created. The frame re-sync runs
    // only on structural hardens, never mid-drag.
    let had_menu = unsafe {
        GetWindowLongPtrW(HWND(raw as *mut std::ffi::c_void), GWL_STYLE) & (WS_SYSMENU.0 as isize)
            != 0
    };
    if had_menu && sync_frame {
        let dispatched = window
            .run_on_main_thread(move || unsafe {
                let hwnd = HWND(raw as *mut std::ffi::c_void);
                let style = GetWindowLongPtrW(hwnd, GWL_STYLE);
                SetWindowLongPtrW(hwnd, GWL_STYLE, style & !(WS_SYSMENU.0 as isize));
                let _ = SetWindowPos(
                    hwnd,
                    None,
                    0,
                    0,
                    0,
                    0,
                    SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE,
                );
            })
            .is_ok();
        if !HARDEN_LOGGED.swap(true, Ordering::SeqCst) {
            if dispatched {
                log::info!("[BUBBLE] bubble chrome hardened (system menu removed)");
            } else {
                log::warn!("[BUBBLE] system-menu strip dispatch failed (menu may still appear)");
            }
        }
    } else if !had_menu && !HARDEN_LOGGED.swap(true, Ordering::SeqCst) {
        // Genuinely clean (not a skipped dirty mid-drag: the next
        // structural harden re-strips then).
        log::info!("[BUBBLE] bubble chrome hardened (no system menu present)");
    }
}

/// Queue-level right-button backstop (Windows only, no-op elsewhere).
///
/// This is the single mechanism that keeps the system menu dead:
/// a thread-local `WH_GETMESSAGE` hook eats the six right-button
/// messages at the queue, before any proc sees them. Subclassing
/// was tried first and removed: tao rebuilds the window proc on
/// flag flips and re-arms it during drags, so any click between
/// tao's restore and the next harden reached DefWindowProc — and
/// the chained proc once deadlocked the UI on synchronous
/// cross-window sends. The hook cannot be raced out (tao
/// subclasses, it never unhooks) and holds no lock across calls.
/// Safe from any thread: the owning UI thread is resolved from the
/// bubble HWND itself. Registration covers top + every descendant
/// (input can land on WRY_WEBVIEW, any Chrome_WidgetWin_*, the
/// render host, or the D3D window).
#[cfg(target_os = "windows")]
pub(crate) fn ensure_bubble_msg_hook(window: &tauri::WebviewWindow, rescan_children: bool) {
    use std::sync::{
        atomic::{AtomicBool, Ordering},
        Mutex, OnceLock,
    };

    use windows::core::BOOL;
    use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
    use windows::Win32::UI::WindowsAndMessaging::{
        CallNextHookEx, EnumChildWindows, GetWindowThreadProcessId, SetWindowsHookExW, MSG,
        WH_GETMESSAGE, WM_CONTEXTMENU, WM_NCRBUTTONDOWN, WM_NCRBUTTONUP, WM_NULL, WM_RBUTTONDBLCLK,
        WM_RBUTTONDOWN, WM_RBUTTONUP,
    };

    static HOOK_HWNDS: OnceLock<Mutex<Vec<isize>>> = OnceLock::new();
    fn hook_hwnds() -> &'static Mutex<Vec<isize>> {
        HOOK_HWNDS.get_or_init(|| Mutex::new(Vec::new()))
    }
    static HOOK_INSTALLED: AtomicBool = AtomicBool::new(false);
    // Fast return BEFORE any child-tree enumeration: the hook and the watched
    // HWND set are process-lifetime, so a pure move needs no rescan. A
    // structural event asks for one so late-created WebView children register.
    if HOOK_INSTALLED.load(Ordering::SeqCst) && !rescan_children {
        return;
    }
    // Escape hatch (drag debugging): LAUSU_NO_BUBBLE_HOOK=1 skips the
    // install entirely; the one-shot gutting in harden still runs.
    // Read once per process; the geometry handler re-runs this on
    // every move, and getenv on every tick would be pure overhead.
    static HOOK_DISABLED: OnceLock<bool> = OnceLock::new();
    if *HOOK_DISABLED.get_or_init(|| std::env::var("LAUSU_NO_BUBBLE_HOOK").is_ok()) {
        return;
    }
    // Raw handle value: HHOOK itself is not Send+Sync (raw pointer),
    // so the static keeps the isize. The hook is process-lifetime;
    // the stored value is only for debuggability, never unhooked.
    static HOOK_HANDLE: OnceLock<Mutex<Option<isize>>> = OnceLock::new();

    // Runs on the UI thread for every queued message: two integer
    // compares, the HWND-set lookup only for the six eaten ids.
    // Never holds a lock across a call; never blocks. The owning
    // thread is resolved per harden call from the bubble HWND itself
    // (`GetWindowThreadProcessId`), so this works from any caller
    // thread — no main-thread witness needed.
    unsafe extern "system" fn bubble_getmsg_hook(
        code: i32,
        wparam: WPARAM,
        lparam: LPARAM,
    ) -> LRESULT {
        // HC_ACTION (0): the queue delivered a message.
        if code == 0 {
            let msg = &mut *(lparam.0 as *mut MSG);
            if matches!(
                msg.message,
                WM_NCRBUTTONDOWN
                    | WM_NCRBUTTONUP
                    | WM_RBUTTONDOWN
                    | WM_RBUTTONUP
                    | WM_RBUTTONDBLCLK
                    | WM_CONTEXTMENU
            ) {
                let raw = msg.hwnd.0 as isize;
                let watched = hook_hwnds()
                    .lock()
                    .map(|guard| guard.contains(&raw))
                    .unwrap_or(false);
                if watched {
                    // Strip the message in place: the queue keeps a
                    // harmless WM_NULL, no proc ever sees the button.
                    msg.message = WM_NULL;
                }
            }
        }
        CallNextHookEx(None, code, wparam, lparam)
    }

    unsafe extern "system" fn enum_all(hwnd: HWND, lparam: LPARAM) -> BOOL {
        let out = &mut *(lparam.0 as *mut Vec<isize>);
        out.push(hwnd.0 as isize);
        true.into()
    }

    let raw = match window.hwnd() {
        Ok(hwnd) => hwnd.0 as isize,
        Err(_) => return,
    };
    if rescan_children || !HOOK_INSTALLED.load(Ordering::SeqCst) {
        let mut hwnds = vec![raw];
        unsafe {
            let top = HWND(raw as *mut std::ffi::c_void);
            let _ = EnumChildWindows(
                Some(top),
                Some(enum_all),
                LPARAM(&mut hwnds as *mut Vec<isize> as isize),
            );
        }
        if let Ok(mut guard) = hook_hwnds().lock() {
            for hwnd in hwnds {
                if !guard.contains(&hwnd) {
                    guard.push(hwnd);
                }
            }
        }
    }
    if HOOK_INSTALLED.swap(true, Ordering::SeqCst) {
        return;
    }
    // The UI thread owns every tao window, so resolve it from the
    // bubble HWND itself: install works from any caller thread and
    // needs no main-thread witness. A zero id means the window is
    // gone; retry on the next harden.
    let ui_tid = unsafe { GetWindowThreadProcessId(HWND(raw as *mut std::ffi::c_void), None) };
    if ui_tid == 0 {
        HOOK_INSTALLED.store(false, Ordering::SeqCst);
        return;
    }
    unsafe {
        match SetWindowsHookExW(WH_GETMESSAGE, Some(bubble_getmsg_hook), None, ui_tid) {
            Ok(hook) => {
                let raw_hook = hook.0 as isize;
                if let Some(slot) = HOOK_HANDLE.get() {
                    if let Ok(mut guard) = slot.lock() {
                        *guard = Some(raw_hook);
                    }
                } else {
                    let _ = HOOK_HANDLE.set(Mutex::new(Some(raw_hook)));
                }
                log::info!("[BUBBLE] right-button input hook installed (queue-level backstop)");
            }
            Err(e) => {
                log::warn!(
                    "[BUBBLE] input hook install failed (retrying next event): {}",
                    e
                );
                HOOK_INSTALLED.store(false, Ordering::SeqCst);
            }
        }
    }
}

/// Non-Windows: no caption menu exists, nothing to hook.
#[cfg(not(target_os = "windows"))]
pub(crate) fn ensure_bubble_msg_hook(_window: &tauri::WebviewWindow, _rescan_children: bool) {}

// Right-button input used to die in a subclassed wndproc here. That
// whole layer is removed: tao rebuilds the proc under us (clicks in
// the gap reopened the menu) and the chained call once deadlocked
// the UI. `ensure_bubble_msg_hook` above owns this now.

/// Gut the OS system menu items once (Windows only). The style
/// strip this replaced lost a race to tao's flag flips, so it is
/// gone; the input hook owns the mouse path. What remains is the
/// keyboard corner: Alt+Space sends `WM_SYSCOMMAND` synchronously,
/// which no queue hook can eat. Deleting the items is permanent
/// for the window's lifetime (nothing calls `GetSystemMenu(TRUE)`),
/// so even that corner opens onto nothing.
#[cfg(target_os = "windows")]
fn gut_bubble_system_menu(window: &tauri::WebviewWindow) {
    use std::sync::atomic::{AtomicBool, Ordering};

    use windows::Win32::Foundation::HWND;
    use windows::Win32::UI::WindowsAndMessaging::{
        DeleteMenu, GetSystemMenu, MF_BYCOMMAND, SC_CLOSE, SC_MAXIMIZE, SC_MINIMIZE, SC_MOVE,
        SC_RESTORE, SC_SIZE,
    };

    static GUTTED: AtomicBool = AtomicBool::new(false);
    if GUTTED.swap(true, Ordering::SeqCst) {
        return;
    }
    // `window.hwnd()` returns tauri's own `windows`-crate HWND, which
    // may differ from ours: cross the boundary through the raw value.
    let raw = match window.hwnd() {
        Ok(hwnd) => hwnd.0 as isize,
        Err(e) => {
            log::warn!("[BUBBLE] system-menu gutting skipped (no HWND): {}", e);
            return;
        }
    };
    unsafe {
        let menu = GetSystemMenu(HWND(raw as *mut std::ffi::c_void), false.into());
        if menu.0.is_null() {
            return;
        }
        for item in [
            SC_RESTORE,
            SC_MOVE,
            SC_SIZE,
            SC_MINIMIZE,
            SC_MAXIMIZE,
            SC_CLOSE,
        ] {
            let _ = DeleteMenu(menu, item, MF_BYCOMMAND);
        }
    }
    log::info!("[BUBBLE] system menu gutted (Alt+Space corner covered)");
}

pub(crate) fn hide_bubble_window(
    app: &tauri::AppHandle,
    source: BubbleHideSource,
) -> Result<(), String> {
    let state: tauri::State<'_, Arc<SidecarState>> = app.state();
    if source == BubbleHideSource::Backend {
        // The renderer needs the exit animation while the window is
        // still visible. Its `hideComplete` then calls us again with
        // RendererComplete, which does NOT re-emit (no feedback loop).
        app.emit_to("bubble", "bubble:hide", ())
            .map_err(|e| e.to_string())?;
    } else {
        state.bubble_show_requested.store(false, Ordering::SeqCst);
        if source == BubbleHideSource::Dismiss {
            let shared = state.inner().clone();
            if let Err(e) = crate::commands::sidecar_cmds::dispatch_fire_and_forget(
                &shared,
                "bubble_host_hidden",
                Some(json!({"reason": "host-dismiss"})),
            ) {
                log::debug!("[BUBBLE] host-hide notification skipped: {e}");
            }
        }
    }
    let bubble = app
        .get_webview_window("bubble")
        .ok_or("bubble window not found")?;
    bubble.hide().map_err(|e| e.to_string())?;
    // Re-harden so the hook's HWND set stays current whatever
    // ordered the operations (idempotent, cheap when installed).
    harden_bubble_chrome(&bubble, true);
    Ok(())
}
