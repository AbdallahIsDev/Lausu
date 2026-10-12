use serde_json::Value;
use tauri::{Emitter, Manager};

pub(crate) fn wants_bubble_show(event_type: &str) -> bool {
    event_type == "bubble_show"
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

pub(crate) fn show_bubble_window(app: &tauri::AppHandle) -> Result<(), String> {
    let window = app
        .get_webview_window("bubble")
        .ok_or("bubble window not found")?;
    // Show never repositions: the pill stays where the user put it
    // across visibility and mode transitions. Initial placement is the
    // configured default edge (bubble_set_position from the main
    // window's connection hydration); drags are session-local and are
    // never persisted.
    window.show().map_err(|e| e.to_string())?;
    harden_bubble_chrome(&window);
    Ok(())
}

/// Cross-platform bubble-chrome hardening. Runs on every show
/// (idempotent), which also self-heals if anything restores the style.
///
/// - Windows: the pill drags through an OS caption region, which
///   summons the system menu on right-click even on a frameless
///   window. Two independent kills: the `WS_SYSMENU` style is
///   removed AND the caption right-button messages are swallowed in
///   our own window proc, so no style race can ever resurrect the
///   menu. Left-button drag and double-click zoom are unaffected
///   (zoom is separately disabled by `maximizable/minimizable:
///   false` in each tauri conf bubble block).
/// - macOS: the bubble is borderless with no titlebar, so there is
///   no titlebar menu and no double-click zoom box. Nothing to do.
/// - Linux: frameless + skip-taskbar windows expose no caption menu
///   on right-click under X11 or Wayland. Nothing to do.
pub(crate) fn harden_bubble_chrome(window: &tauri::WebviewWindow) {
    #[cfg(target_os = "windows")]
    {
        strip_bubble_system_menu(window);
        swallow_bubble_caption_clicks(window);
    }
    #[cfg(not(target_os = "windows"))]
    let _ = window;
}

/// Swallow right-button messages on the bubble (Windows only).
///
/// Two layers, because neither alone covers every path:
/// - Top-level: `WM_NCRBUTTONDOWN/UP` (the dead system menu trigger).
/// - Render-host child (`Chrome_RenderWidgetHostHWND`, the true input
///   surface): `WM_RBUTTONDOWN/UP/DBLCLK` + `WM_CONTEXTMENU`. Input
///   goes straight to this child, bypassing the top proc, so page
///   guards (`selectstart`, `contextmenu`, `user-select`) never see
///   right-button gestures that start here. Killing them at entry
///   means no word-select, no menu cascade, no artifact, no matter
///   which paint path the browser would have taken.
/// Left-button drag and clicks are untouched on both layers, and the
/// previous procs stay chained for every other message. Re-runs on
/// every harden call so a recreated child gets re-armed; install is
/// skipped when our proc is already in place (live check, no stale
/// state). No restore on destroy: the install is process-lifetime
/// (the exe never unloads) and dead HWNDs never dispatch.
#[cfg(target_os = "windows")]
fn swallow_bubble_caption_clicks(window: &tauri::WebviewWindow) {
    use std::sync::{Mutex, OnceLock};

    use windows::core::BOOL;
    use windows::Win32::Foundation::{HWND, LPARAM, LRESULT, WPARAM};
    use windows::Win32::UI::WindowsAndMessaging::{
        CallWindowProcW, DefWindowProcW, EnumChildWindows, GetWindowLongPtrW, SetWindowLongPtrW,
        GWLP_WNDPROC, WM_CONTEXTMENU, WM_NCDESTROY, WM_NCRBUTTONDOWN, WM_NCRBUTTONUP,
        WM_RBUTTONDBLCLK, WM_RBUTTONDOWN, WM_RBUTTONUP, WNDPROC,
    };

    static PREV_PROCS: OnceLock<Mutex<Vec<(isize, WNDPROC)>>> = OnceLock::new();
    fn prev_procs() -> &'static Mutex<Vec<(isize, WNDPROC)>> {
        PREV_PROCS.get_or_init(|| Mutex::new(Vec::new()))
    }

    // SAFETY: process-lifetime install; the previous proc stays chained
    // for every other message.
    unsafe extern "system" fn bubble_wndproc(
        hwnd: HWND,
        msg: u32,
        wparam: WPARAM,
        lparam: LPARAM,
    ) -> LRESULT {
        if msg == WM_NCRBUTTONDOWN
            || msg == WM_NCRBUTTONUP
            || msg == WM_RBUTTONDOWN
            || msg == WM_RBUTTONUP
            || msg == WM_RBUTTONDBLCLK
            || msg == WM_CONTEXTMENU
        {
            return LRESULT(0);
        }
        if msg == WM_NCDESTROY {
            if let Ok(mut guard) = prev_procs().lock() {
                guard.retain(|(h, _)| *h != hwnd.0 as isize);
            }
        }
        // Copy the previous proc out and DROP the guard before
        // calling it: the previous proc (tao / Chromium) routinely
        // sends messages synchronously to our OTHER subclassed window,
        // which re-enters this proc on the same thread. Calling out
        // while holding a non-reentrant std Mutex deadlocks the UI
        // thread on itself (frozen splash, "Not Responding", ~0 CPU).
        let prev = prev_procs()
            .lock()
            .ok()
            .and_then(|guard| {
                guard
                    .iter()
                    .find(|(h, _)| *h == hwnd.0 as isize)
                    .map(|(_, p)| *p)
            })
            .flatten();
        match prev {
            Some(p) => CallWindowProcW(Some(p), hwnd, msg, wparam, lparam),
            None => DefWindowProcW(hwnd, msg, wparam, lparam),
        }
    }

    // fn item to integer: coerce to the nullable-pointer alias first,
    // then transmute (same width both ways).
    fn ours() -> isize {
        let proc: WNDPROC = Some(bubble_wndproc);
        unsafe { std::mem::transmute(proc) }
    }

    // Install our proc on `hwnd` unless already installed (live check,
    // no stale state). Returns true when a fresh install happened.
    fn install_on(hwnd: HWND) -> bool {
        let ours = ours();
        let cur = unsafe { GetWindowLongPtrW(hwnd, GWLP_WNDPROC) };
        if cur == ours {
            return false;
        }
        let prev = unsafe { SetWindowLongPtrW(hwnd, GWLP_WNDPROC, ours) };
        // A zero return MIGHT be a valid previous proc (NULL is never
        // a real proc); transmute unconditionally, chaining falls back
        // to DefWindowProc only when no entry exists.
        let prev: WNDPROC = unsafe { std::mem::transmute(prev) };
        if let Ok(mut guard) = prev_procs().lock() {
            guard.retain(|(h, _)| *h != hwnd.0 as isize);
            guard.push((hwnd.0 as isize, prev));
        }
        true
    }

    unsafe extern "system" fn enum_child(hwnd: HWND, lparam: LPARAM) -> BOOL {
        use std::cell::Cell;

        use windows::Win32::UI::WindowsAndMessaging::GetClassNameW;
        // Class names are short; a fixed stack buffer avoids allocation
        // on every enumeration.
        let mut buf = [0u16; 64];
        let len = GetClassNameW(hwnd, &mut buf);
        let name = String::from_utf16_lossy(&buf[..len as usize]);
        if name == "Chrome_RenderWidgetHostHWND" {
            let found = &*(lparam.0 as *const Cell<Option<isize>>);
            found.set(Some(hwnd.0 as isize));
            return false.into();
        }
        true.into()
    }

    let raw = match window.hwnd() {
        Ok(hwnd) => hwnd.0 as isize,
        Err(e) => {
            log::warn!("[BUBBLE] caption-click swallow skipped (no HWND): {}", e);
            return;
        }
    };
    // The actual input surface is the render-host child: real button
    // messages go straight to it and never pass the top proc. Install
    // on both so neither layer can start the menu cascade.
    //
    // The liveness reads below are pure Win32 queries: safe on ANY
    // thread, main included. Only the SetWindowLongPtrW mutation needs
    // the window thread, so steady-state calls dispatch nothing at
    // all. That keeps this safe for main-thread callers (window
    // geometry events): an unconditional dispatch would block the main
    // thread waiting on itself forever.
    let ours = ours();
    let (need_top, need_child): (bool, Option<isize>) = unsafe {
        let top = HWND(raw as *mut std::ffi::c_void);
        let need_top = GetWindowLongPtrW(top, GWLP_WNDPROC) != ours;
        let found: std::cell::Cell<Option<isize>> = std::cell::Cell::new(None);
        let _ = EnumChildWindows(
            Some(top),
            Some(enum_child),
            LPARAM(&found as *const _ as isize),
        );
        let need_child = found
            .get()
            .filter(|c| GetWindowLongPtrW(HWND(*c as *mut std::ffi::c_void), GWLP_WNDPROC) != ours);
        (need_top, need_child)
    };
    if !(need_top || need_child.is_some()) {
        return;
    }
    window
        .run_on_main_thread(move || {
            // `install_on` re-checks liveness, and dead HWNDs are
            // skipped: the child may have died between the pre-check
            // above and this closure (never attach to a recycled HWND).
            unsafe {
                use windows::Win32::UI::WindowsAndMessaging::IsWindow;
                let mut fresh = false;
                if need_top {
                    let top = HWND(raw as *mut std::ffi::c_void);
                    if IsWindow(Some(top)).as_bool() {
                        fresh |= install_on(top);
                    }
                }
                if let Some(child_raw) = need_child {
                    let child = HWND(child_raw as *mut std::ffi::c_void);
                    if IsWindow(Some(child)).as_bool() {
                        fresh |= install_on(child);
                    }
                }
                if fresh {
                    log::info!(
                        "[BUBBLE] caption-click swallow installed (right-button messages die in our wndproc)"
                    );
                }
            }
        })
        .unwrap_or_else(|e| {
            log::warn!("[BUBBLE] caption-click swallow dispatch failed: {}", e);
        });
}

/// Strip the OS system menu from the bubble window (Windows only).
///
/// The pill drags through an OS caption region, which summons the
/// system menu on right-click even on a frameless window. Removing
/// `WS_SYSMENU` kills the menu entirely (right-click and Alt+Space
/// do nothing); dragging is unaffected. Idempotent: runs on every
/// show, which also self-heals if anything restores the style.
#[cfg(target_os = "windows")]
fn strip_bubble_system_menu(window: &tauri::WebviewWindow) {
    use std::sync::atomic::{AtomicBool, Ordering};

    use windows::Win32::Foundation::HWND;
    use windows::Win32::UI::WindowsAndMessaging::{
        DeleteMenu, GetSystemMenu, GetWindowLongPtrW, SetWindowLongPtrW, SetWindowPos, GWL_STYLE,
        MF_BYCOMMAND, SC_CLOSE, SC_MAXIMIZE, SC_MINIMIZE, SC_MOVE, SC_RESTORE, SC_SIZE,
        SWP_FRAMECHANGED, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, SWP_NOZORDER, WS_SYSMENU,
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
    // must run where the window was created.
    let had_menu = unsafe {
        GetWindowLongPtrW(HWND(raw as *mut std::ffi::c_void), GWL_STYLE) & (WS_SYSMENU.0 as isize)
            != 0
    };
    if had_menu {
        let dispatched = window
            .run_on_main_thread(move || {
                unsafe {
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
                    // Belt and suspenders: tao rebuilds the style (with
                    // WS_SYSMENU) on every flag flip (show/hide/...), so a
                    // bare style strip can lose a race. Gutted menu items
                    // stay deleted for the window's lifetime (nothing
                    // calls GetSystemMenu(TRUE)), so even a resurrected
                    // shell opens onto an empty menu.
                    let menu = GetSystemMenu(hwnd, false.into());
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
            })
            .is_ok();
        if !HARDEN_LOGGED.swap(true, Ordering::SeqCst) {
            if dispatched {
                log::info!("[BUBBLE] bubble chrome hardened (system menu removed)");
            } else {
                log::warn!("[BUBBLE] system-menu strip dispatch failed (menu may still appear)");
            }
        }
    } else if !HARDEN_LOGGED.swap(true, Ordering::SeqCst) {
        log::info!("[BUBBLE] bubble chrome hardened (no system menu present)");
    }
}

pub(crate) fn hide_bubble_window(app: &tauri::AppHandle) -> Result<(), String> {
    //emit FIRST so the renderer's cleanup runs while the
    // window is still visible.
    app.emit_to("bubble", "bubble:hide", ())
        .map_err(|e| e.to_string())?;
    let bubble = app
        .get_webview_window("bubble")
        .ok_or("bubble window not found")?;
    bubble.hide().map_err(|e| e.to_string())?;
    // tao rewrites the full style (WS_SYSMENU included) on every
    // flag flip, hide included. Re-strip so a later show can never
    // observe a resurrected menu, whatever ordered the operations.
    harden_bubble_chrome(&bubble);
    Ok(())
}
