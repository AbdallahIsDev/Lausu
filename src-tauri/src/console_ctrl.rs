//! Console control handler (Windows): cooperative teardown before death.
//!
//! Ctrl+C in a dev terminal used to destroy webviews only, then return
//! false so the default termination hard-killed the process. The sidecar
//! never got its `{"type":"shutdown"}` frame: `shutdown_sidecar_for_exit`
//! (WAL checkpoint, crash-recovery flush, native hotkey teardown) was cut
//! off mid-flush. The tray-Quit path (`on_quit_app` + `RunEvent::Exit` →
//! `on_host_exit`) already runs the full ordered teardown; this installs
//! the same sequence for console kills by calling `on_quit_app` itself
//! (no second teardown copy to drift): arm `shutting_down`, destroy
//! webviews, then `app.exit(0)` so the Exit event drives the budgeted
//! sidecar/worker shutdown. Returning true swallows the OS default
//! `ExitProcess` so the teardown above owns process exit.

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
        CTRL_C_EVENT | CTRL_BREAK_EVENT => {
            if let Some(app) = APP.get() {
                // Same ordered sequence as tray Quit (`on_quit_app`:
                // arm `shutting_down`, destroy webviews, `app.exit(0)`
                // so `RunEvent::Exit` → `on_host_exit` runs the budgeted
                // sidecar/worker teardown). Best-effort off the OS
                // handler thread: `AppHandle` is thread-safe, failures
                // just log inside the callees.
                crate::sidecar::lifecycle::on_quit_app(app);
            }
            // true: swallow the OS default `ExitProcess` so the teardown
            // above (not the hard kill) owns process exit. `app.exit(0)`
            // ends the event loop after `on_host_exit` is dispatched.
            true.into()
        }
        CTRL_CLOSE_EVENT | CTRL_LOGOFF_EVENT | CTRL_SHUTDOWN_EVENT => {
            if let Some(app) = APP.get() {
                crate::sidecar::lifecycle::destroy_webview_windows(app);
            }
            // false: the OS imposes a seconds-long deadline on these
            // events (no 30s flush possible); default termination
            // proceeds, just with no live WebViews left behind.
            false.into()
        }
        _ => false.into(),
    }
}
