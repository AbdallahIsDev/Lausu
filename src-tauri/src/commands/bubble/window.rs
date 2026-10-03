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
    window.show().map_err(|e| e.to_string())
}

pub(crate) fn hide_bubble_window(app: &tauri::AppHandle) -> Result<(), String> {
    //emit FIRST so the renderer's cleanup runs while the
    // window is still visible.
    app.emit_to("bubble", "bubble:hide", ())
        .map_err(|e| e.to_string())?;
    let bubble = app
        .get_webview_window("bubble")
        .ok_or("bubble window not found")?;
    bubble.hide().map_err(|e| e.to_string())
}
