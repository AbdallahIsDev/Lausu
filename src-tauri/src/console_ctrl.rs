//! Console control handler (Windows): destroy webviews before death.
//!
//! Ctrl+C in a dev terminal kills the host with live WebView HWNDs,
//! and Chromium's AtExit then logs `Failed to unregister class
//! Chrome_WidgetWin_0` (harmless but alarming). The tray-Quit path
//! already destroys webviews first (`on_quit_app`); this installs the
//! same ordering for console kills. Best-effort: failures just log,
//! and the default termination always proceeds afterwards.

#[cfg(target_os = "windows")]
static APP: std::sync::OnceLock<tauri::AppHandle> = std::sync::OnceLock::new();

/// Install the handler. Call once from `setup`; the `AppHandle` is
/// stashed because the OS invokes the callback without context.
#[cfg(target_os = "windows")]
pub(crate) fn install(app: &tauri::AppHandle) {
    use windows::Win32::System::Console::SetConsoleCtrlHandler;
    let _ = APP.set(app.clone());
    unsafe {
        // Failure (no console attached, e.g. GUI-subsystem release
        // builds) just means there is nothing to handle.
        let _ = SetConsoleCtrlHandler(Some(ctrl_handler), true.into());
    }
}

/// No-op on other platforms (Ctrl+C there is SIGINT, same class of
/// noise from a different subsystem, out of scope for this module).
#[cfg(not(target_os = "windows"))]
pub(crate) fn install(_app: &tauri::AppHandle) {}

#[cfg(target_os = "windows")]
unsafe extern "system" fn ctrl_handler(ctrl_type: u32) -> windows::core::BOOL {
    use windows::Win32::System::Console::{
        CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT, CTRL_C_EVENT, CTRL_LOGOFF_EVENT, CTRL_SHUTDOWN_EVENT,
    };
    match ctrl_type {
        CTRL_C_EVENT | CTRL_BREAK_EVENT | CTRL_CLOSE_EVENT | CTRL_LOGOFF_EVENT
        | CTRL_SHUTDOWN_EVENT => {
            if let Some(app) = APP.get() {
                crate::sidecar::lifecycle::destroy_webview_windows(app);
            }
            // false: default termination proceeds, just with no live
            // WebViews left for Chromium's AtExit to trip over.
            false.into()
        }
        _ => false.into(),
    }
}
