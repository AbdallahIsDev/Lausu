use serde::Deserialize;
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use tauri::{AppHandle, Emitter, Listener, Manager};

/// Pending OS-toast click intents: notification id -> action.
/// Written at show-time, consumed when the plugin reports a tap.
fn pending_tap_actions() -> &'static Mutex<HashMap<i32, TapAction>> {
    static PENDING: OnceLock<Mutex<HashMap<i32, TapAction>>> = OnceLock::new();
    PENDING.get_or_init(|| Mutex::new(HashMap::new()))
}

#[derive(Debug, Clone)]
enum TapAction {
    /// Open the OS microphone privacy page (mirrors `open_mic_settings`).
    OpenMicSettings,
    /// Emit a renderer `navigate` event (in-app destination).
    Navigate(serde_json::Value),
}

/// Next notification id for id-tagged toasts.
fn next_notification_id() -> &'static Mutex<i32> {
    static NEXT_ID: OnceLock<Mutex<i32>> = OnceLock::new();
    NEXT_ID.get_or_init(|| Mutex::new(1))
}

#[derive(Debug, Clone, Deserialize)]
struct NotificationPayload {
    #[serde(default)]
    title: String,
    #[serde(default)]
    message: String,
    #[serde(default)]
    click_path: Option<String>,
    #[serde(default)]
    click_consent_field: Option<String>,
    #[serde(default)]
    duration_ms: u64,
}

impl Default for NotificationPayload {
    fn default() -> Self {
        Self {
            title: String::new(),
            message: String::new(),
            click_path: None,
            click_consent_field: None,
            duration_ms: 0,
        }
    }
}

fn parse_notification(raw: &str) -> Option<NotificationPayload> {
    let payload: NotificationPayload = match serde_json::from_str(raw) {
        Ok(p) => p,
        Err(e) => {
            log::warn!("[HOST-EVENTS] failed to parse notification payload: {}", e);
            return None;
        }
    };
    if payload.title.is_empty() && payload.message.is_empty() {
        return None;
    }
    Some(payload)
}

fn navigate_payload(payload: &NotificationPayload) -> serde_json::Value {
    match &payload.click_consent_field {
        Some(field) => serde_json::json!({
            "path": "/settings",
            "consent_field": field,
        }),
        None => serde_json::json!({
            "path": payload.click_path.clone().unwrap_or_default(),
        }),
    }
}

/// Tap intent for a payload: mic-settings opens the OS page,
/// everything else navigates in-app.
fn tap_action_for(payload: &NotificationPayload) -> Option<TapAction> {
    if payload.click_path.as_deref() == Some("/microphone") && payload.click_consent_field.is_none()
    {
        return Some(TapAction::OpenMicSettings);
    }
    if payload.click_path.is_some() || payload.click_consent_field.is_some() {
        return Some(TapAction::Navigate(navigate_payload(payload)));
    }
    None
}

/// Open the OS microphone privacy page (mirrors the Python
/// `open_os_microphone_settings` IPC: ms-settings on Windows,
/// System Settings on macOS, sound panel on Linux).
fn open_os_microphone_settings() {
    #[cfg(target_os = "windows")]
    {
        let child = std::process::Command::new("explorer.exe")
            .arg("ms-settings:privacy-microphone")
            .spawn();
        match child {
            Ok(mut c) => {
                std::thread::spawn(move || {
                    let _ = c.wait();
                });
                log::info!("[HOST-EVENTS] toast tap opened OS mic privacy settings");
            }
            Err(e) => log::warn!("[HOST-EVENTS] toast tap failed to open mic settings: {e}"),
        }
    }
    #[cfg(target_os = "macos")]
    {
        let child = std::process::Command::new("open")
            .arg("x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone")
            .spawn();
        match child {
            Ok(mut c) => {
                std::thread::spawn(move || {
                    let _ = c.wait();
                });
                log::info!("[HOST-EVENTS] toast tap opened OS mic privacy settings");
            }
            Err(e) => log::warn!("[HOST-EVENTS] toast tap failed to open mic settings: {e}"),
        }
    }
    #[cfg(target_os = "linux")]
    {
        let child = std::process::Command::new("xdg-open")
            .arg("gnome-control-center sound")
            .spawn();
        match child {
            Ok(mut c) => {
                std::thread::spawn(move || {
                    let _ = c.wait();
                });
                log::info!("[HOST-EVENTS] toast tap opened OS mic privacy settings");
            }
            Err(e) => log::warn!("[HOST-EVENTS] toast tap failed to open mic settings: {e}"),
        }
    }
}

/// Handle a plugin `tap` on notification `id`: run the pending intent.
fn handle_notification_tap(app: &AppHandle, id: i32) {
    let action = pending_tap_actions()
        .lock()
        .map(|mut map| map.remove(&id))
        .unwrap_or(None);
    match action {
        Some(TapAction::OpenMicSettings) => open_os_microphone_settings(),
        Some(TapAction::Navigate(nav)) => {
            // Raise the window first so the navigation lands visible.
            show_main_window(app);
            if let Err(e) = app.emit("navigate", nav) {
                log::warn!("[HOST-EVENTS] tap navigate emit failed: {}", e);
            }
        }
        None => {
            log::debug!("[HOST-EVENTS] tap on untracked notification id={}", id);
        }
    }
}

fn show_notification(app: &AppHandle, payload: &NotificationPayload) {
    use tauri_plugin_notification::NotificationExt;

    let app = app.clone();
    let title = payload.title.clone();
    let message = payload.message.clone();
    let tap_action = tap_action_for(payload);
    let duration_ms = payload.duration_ms;
    #[allow(clippy::let_underscore_future)] // intentional fire-and-forget
    let _ = tauri::async_runtime::spawn_blocking(move || {
        // Id-tag + intent BEFORE show so a fast tap cannot miss the map.
        let id = {
            let mut next = next_notification_id()
                .lock()
                .unwrap_or_else(|e| e.into_inner());
            let id = *next;
            *next = next.wrapping_add(1).max(1);
            id
        };
        if let Some(action) = tap_action {
            if let Ok(mut map) = pending_tap_actions().lock() {
                map.insert(id, action);
            }
        }
        if let Err(e) = app
            .notification()
            .builder()
            .id(id)
            .title(&title)
            .body(&message)
            .show()
        {
            log::warn!("[HOST-EVENTS] notification show failed: {}", e);
            if let Ok(mut map) = pending_tap_actions().lock() {
                map.remove(&id);
            }
            return;
        }
        if duration_ms > 0 {
            log::debug!(
                "[HOST-EVENTS] notification duration_ms={} requested (OS-managed on desktop)",
                duration_ms
            );
        }
    });
}

pub(crate) fn show_main_window(app: &AppHandle) {
    let app = app.clone();
    #[allow(clippy::let_underscore_future)] // intentional fire-and-forget
    let _ = tauri::async_runtime::spawn_blocking(move || match app.webview_windows().get("main") {
        Some(window) => raise_main_window(&window),
        None => {
            log::info!("[HOST-EVENTS] main window not found: recreating it");
            crate::window_bootstrap::bootstrap_main_window(&app);
            match app.webview_windows().get("main") {
                Some(window) => raise_main_window(&window),
                None => log::warn!("[HOST-EVENTS] main window recreation failed"),
            }
        }
    });
}

fn raise_main_window(window: &tauri::WebviewWindow) {
    if let Err(e) = window.set_skip_taskbar(false) {
        log::warn!(
            "[HOST-EVENTS] main window set_skip_taskbar(false) failed: {}",
            e
        );
    }
    if let Err(e) = window.unminimize() {
        log::warn!("[HOST-EVENTS] main window unminimize failed: {}", e);
    }
    if let Err(e) = window.show() {
        log::warn!("[HOST-EVENTS] main window show failed: {}", e);
    }
    if let Err(e) = window.set_always_on_top(true) {
        log::warn!(
            "[HOST-EVENTS] main window set_always_on_top(true) failed: {}",
            e
        );
    }
    if let Err(e) = window.set_focus() {
        log::warn!("[HOST-EVENTS] main window set_focus failed: {}", e);
    }
    if let Err(e) = window.set_always_on_top(false) {
        log::warn!(
            "[HOST-EVENTS] main window set_always_on_top(false) failed: {}",
            e
        );
    }
    log::info!("[HOST-EVENTS] main window shown + raised to front");
}

/// Register the host-side event listeners. Called once from `main.rs`
/// during app setup.
pub(crate) fn setup(app: &AppHandle) {
    let notify_handle = app.clone();
    app.listen("notification", move |event| {
        if let Some(payload) = parse_notification(event.payload()) {
            show_notification(&notify_handle, &payload);
        }
    });

    // OS-toast tap -> pending intent (`Notification::on_action`, 2.5.x;
    // `action_id == "tap"`; see `handle_notification_tap`). The plugin
    // reports taps only while a handler exists, hence registered here
    // at startup rather than per-toast.
    {
        use tauri_plugin_notification::NotificationExt;
        let tap_handle = app.clone();
        let registration = app.notification().on_action(move |performed| {
            if performed.action_id() != "tap" {
                return;
            }
            match performed.notification().map(|n| n.id()) {
                Some(id) => handle_notification_tap(&tap_handle, id),
                None => log::debug!("[HOST-EVENTS] tap without notification id ignored"),
            }
        });
        if let Err(e) = registration {
            log::warn!("[HOST-EVENTS] notification tap handler registration failed: {e}");
        }
    }

    let show_handle = app.clone();
    app.listen("show_window", move |_event| {
        show_main_window(&show_handle);
    });
}

// Sibling test module: tests live in `host_events_tests.rs` (per
// C-TEST-5: no inline `#[cfg(test)] mod tests` blocks in production
// source).
#[cfg(test)]
#[path = "host_events_tests.rs"]
mod host_events_tests;
