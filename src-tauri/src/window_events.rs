//! Window-event arm dispatch for the host's `.on_window_event` closure.
//!
//! Extracted verbatim from `main.rs`'s inline closure (pure move, no
//! behavior change) so the host entrypoint stays wiring-only (C-ARCH-1):
//! `main.rs` registers the closure, and each arm below forwards to the
//! focused module that owns the concern:
//!
//! - `CloseRequested` → `commands::sidecar_cmds::on_main_window_close`
//!   (close-to-tray semantics: see `commands/sidecar_cmds/
//!   window_close.rs`).
//! - `ThemeChanged` → `theme_icon::apply_to_window` (theme-reactive
//!   taskbar icon, `main` window only).
//! - `Moved` → unhandled (bubble drags are session-local, never persisted).

use tauri::{Manager, WindowEvent};

/// Route one window event to the module that owns its concern.
pub(crate) fn handle(window: &tauri::Window, event: &WindowEvent) {
    // Close-to-tray (ADR-0020 §10): the main
    // window's X button hides the window (prevent_close + hide)
    // unless a deliberate shutdown is in flight; the bubble
    // window closes normally. The branch logic lives in
    // `commands::sidecar_cmds::on_main_window_close`.
    if let WindowEvent::CloseRequested { api, .. } = event {
        crate::commands::sidecar_cmds::on_main_window_close(window.app_handle(), window, api);
    }
    // Theme flip at runtime: OS theme changed, swap the
    // main-window icon so the taskbar button + Alt-Tab tile keep
    // contrasting (white glyph on dark, black on light). The
    // bubble window is excluded: it is skipTaskbar, so it never
    // shows on the taskbar or in Alt-Tab. Body lives in
    // `theme_icon.rs`.
    if let WindowEvent::ThemeChanged(theme) = event {
        if window.label() == crate::theme_icon::MAIN_WINDOW_LABEL {
            crate::theme_icon::apply_to_window(window, theme);
        }
    }
    // Bubble drags are session-local by product decision: the pill
    // stays where the user puts it for this session, but drags are
    // never persisted, and every launch starts from the configured
    // default edge. No `Moved` persistence here. Geometry events ARE
    // the deterministic post-mutation point to re-harden: tao
    // rewrites the window under us on flag flips, so hardening must
    // run after tao, not just before. The frame re-sync is requested
    // for resizes and scale changes but NEVER for `Moved`: recalc
    // inside an active user drag would fight the move loop.
    let sync_frame = matches!(
        event,
        WindowEvent::Resized(_) | WindowEvent::ScaleFactorChanged { .. }
    );
    if window.label() == "bubble" && (sync_frame || matches!(event, WindowEvent::Moved(_))) {
        if let Some(bubble) = window.app_handle().get_webview_window("bubble") {
            // A `Moved` event is a user drag (OS caption region): clear the
            // edge preference so later auto-fit resizes never snap back.
            if matches!(event, WindowEvent::Moved(_)) {
                crate::commands::bubble::note_bubble_user_moved();
            }
            // Queue-level backstop first, synchronously: this handler
            // runs ON the main thread. Sync + non-blocking, then the
            // heavier hardening hops off-thread.
            crate::commands::bubble::ensure_bubble_msg_hook(&bubble);
            std::thread::spawn(move || {
                crate::commands::bubble::harden_bubble_chrome(&bubble, sync_frame);
            });
        }
    }
}
