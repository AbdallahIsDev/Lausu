#![allow(clippy::unreachable)] // tauri command macro expansion emits `unreachable!()` fallbacks

//! Bubble window Tauri commands (ADR-0020 §9).
//! Pure helpers live in sibling `parse` / `math` / `rate_limit` / `window`.
//! NOTE: see docs/code-notes/tauri-host.md#bubble-window-commands

use serde_json::{json, Value};
use std::sync::Arc;
use tauri::{Emitter, Manager, PhysicalPosition};

use crate::error::LausuError;
use crate::state::SidecarState;

use super::math::{
    bubble_position_in_work_area, clamp_resize_height, clamp_resize_width, compute_move_by_new_pos,
    edge_margin_physical, rect_contains_point, round_f64_to_i32_saturating,
    round_f64_to_u32_saturating, RectPx,
};
use super::placement::{
    bubble_edge_for_reanchor, note_bubble_configured_edge, note_bubble_edge_position,
    note_bubble_user_moved,
};
use super::rate_limit::toggle_rate_limiter_allows;
use super::window::{hide_bubble_window, show_bubble_window};

// Tauri commands: bubble window (ADR-0020 §9)
//
// Window-origin policy: most bubble commands are intentionally NOT
// require_main_window-gated — the bubble may self-manage visibility,
// position, drag, resize. SEC-016 gates apply only where spoofing
// readiness/hide from another window would break UX.

/// Show the bubble window. Not main-window-gated (hover UX + WS reader path).
#[tauri::command]
pub async fn bubble_show(app: tauri::AppHandle) -> Result<(), LausuError> {
    show_bubble_window(&app).map_err(LausuError::Host)
}

/// Signal bubble page mounted + ready for `bubble_level`.
/// SEC-016: only the bubble window may signal readiness.
#[tauri::command]
pub async fn bubble_signal_ready(
    app: tauri::AppHandle,
    window: tauri::Window,
) -> Result<(), LausuError> {
    crate::commands::require_bubble_window(&window)?;
    app.emit_to("bubble", "bubble:ready", ())
        .map_err(|e| LausuError::Host(e.to_string()))
}

/// Place bubble on the cursor's monitor from a `"top"|"bottom"` keyword.
/// Not main-window-gated (sandboxed bubble may only move itself).
/// NOTE: see docs/code-notes/tauri-host.md#bubble-window-commands
#[tauri::command]
pub async fn bubble_set_position(
    position: String,
    app: tauri::AppHandle,
) -> Result<(), LausuError> {
    let window = app
        .get_webview_window("bubble")
        .ok_or(LausuError::Host("bubble window not found".into()))?;
    place_bubble_on_edge(&app, &window, &position, "")
        .map(|_| ())
        .map_err(LausuError::Host)
}

/// Place the bubble on a configured edge on behalf of the sidecar.
///
/// The sidecar pushes `bubble_config` (carrying `bubble_position`) on
/// every authenticated connection, which reaches this BEFORE the first
/// show. That ordering is the contract: a host-side show (backend-ready
/// or recording start) no longer paints the pill at the OS default
/// position while the main window's hydration is still pending.
/// Returns `false` when the user moved the pill this session.
pub(crate) fn apply_bubble_config_edge(app: &tauri::AppHandle, edge: &str) -> Result<bool, String> {
    if !note_bubble_configured_edge(edge) {
        log::debug!("[BUBBLE] config edge {edge} ignored (user-moved session or unknown keyword)");
        return Ok(false);
    }
    let window = app
        .get_webview_window("bubble")
        .ok_or("bubble window not found")?;
    place_bubble_on_edge(app, &window, edge, " (config)")?;
    Ok(true)
}

/// Shared edge placement: resolve the cursor's monitor, center the pill
/// on the work area for `edge`, move only when it actually moved, and
/// arm the re-anchor edge. `source` tags the log line (config vs
/// renderer hydration) so one placement is traceable to its caller.
fn place_bubble_on_edge(
    app: &tauri::AppHandle,
    window: &tauri::WebviewWindow,
    edge: &str,
    source: &str,
) -> Result<(i32, i32), String> {
    let monitor = resolve_cursor_monitor(app)?;
    // Physical work area (bounds minus taskbar/dock).
    let wa = monitor.work_area();
    let wa_rect = RectPx::new(wa.position.x, wa.position.y, wa.size.width, wa.size.height);
    let bubble_size = window.outer_size().map_err(|e| e.to_string())?;
    // Saturating u32→i32 (project pattern; no silent wrap).
    let bubble_w = i32::try_from(bubble_size.width).unwrap_or(i32::MAX);
    let bubble_h = i32::try_from(bubble_size.height).unwrap_or(i32::MAX);
    // Edge offset is DIPs; scale to this monitor's physical pixels.
    let margin = edge_margin_physical(monitor.scale_factor());
    let (px, py) = bubble_position_in_work_area(edge, &wa_rect, bubble_w, bubble_h, margin)?;
    let already_there = window
        .outer_position()
        .is_ok_and(|p| p.x == px && p.y == py);
    if !already_there {
        window
            .set_position(PhysicalPosition::new(px, py))
            .map_err(|e| e.to_string())?;
    }
    // Remember the edge so later auto-fit resizes re-anchor instead of
    // sticking top-left (user drags clear it, see `note_bubble_user_moved`).
    note_bubble_edge_position(edge);
    // One line per real placement (config + hydration + settings
    // changes only, never drags): proves in lausu.log that the session
    // started on the configured edge instead of the OS default position.
    if already_there {
        log::debug!("[BUBBLE] already at ({px},{py}) edge={edge}{source}");
    } else {
        log::info!("[BUBBLE] positioned at ({px},{py}) edge={edge}{source}");
    }
    Ok((px, py))
}

/// Resolve the monitor containing a physical point (cursor or window
/// origin): OS hit first, manual bounds hit-test for stacked/negative
/// layouts, primary as the last resort.
fn resolve_monitor_at_point(
    app: &tauri::AppHandle,
    x: f64,
    y: f64,
) -> Result<tauri::window::Monitor, String> {
    match app.monitor_from_point(x, y) {
        Ok(Some(monitor)) => return Ok(monitor),
        Ok(None) | Err(_) => {
            // Fallback hit-test: saturating f64→i32 for NaN/±inf.
            let cx = round_f64_to_i32_saturating(x);
            let cy = round_f64_to_i32_saturating(y);
            let hit = app.available_monitors().ok().and_then(|monitors| {
                monitors.into_iter().find(|m| {
                    let rect = RectPx::new(
                        m.position().x,
                        m.position().y,
                        m.size().width,
                        m.size().height,
                    );
                    rect_contains_point(&rect, cx, cy)
                })
            });
            if let Some(monitor) = hit {
                return Ok(monitor);
            }
            log::warn!("[BUBBLE] point ({cx},{cy}) matched no monitor: falling back to primary");
        }
    }
    app.primary_monitor()
        .map_err(|e| e.to_string())?
        .ok_or_else(|| "no primary monitor available".to_string())
}

/// Resolve monitor the bubble should appear on (cursor display, then primary).
/// Full bounds hit-test is belt-and-suspenders for stacked/negative layouts.
fn resolve_cursor_monitor(app: &tauri::AppHandle) -> Result<tauri::window::Monitor, String> {
    if let Ok(cursor) = app.cursor_position() {
        return resolve_monitor_at_point(app, cursor.x, cursor.y);
    }
    app.primary_monitor()
        .map_err(|e| e.to_string())?
        .ok_or_else(|| "no primary monitor available".to_string())
}

/// Toggle bubble draggable via `bubble:draggable` event (Tauri v2 has no set_draggable).
/// Not main-window-gated (bubble may self-toggle drag while interacting).
#[tauri::command]
pub async fn bubble_set_draggable(
    draggable: bool,
    app: tauri::AppHandle,
) -> Result<(), LausuError> {
    app.emit_to("bubble", "bubble:draggable", draggable)
        .map_err(|e| LausuError::Host(e.to_string()))
}

/// Move bubble by (dx, dy) physical pixels; returns new {x,y}.
/// Not main-window-gated (drag path lives in Bubble.tsx).
/// spawn_blocking: OS-IPC outer_position+set_position at ~60 Hz mousemove
/// must not pin an async worker (C-TOKIO-1 adjacent).
#[tauri::command]
pub async fn bubble_move_by(dx: f64, dy: f64, app: tauri::AppHandle) -> Result<Value, LausuError> {
    let join_result = tauri::async_runtime::spawn_blocking(move || -> Result<Value, String> {
        let window = app
            .get_webview_window("bubble")
            .ok_or("bubble window not found")?;
        let pos = window.outer_position().map_err(|e| e.to_string())?;
        // Saturating f64→i32 at the FFI boundary (NaN/±inf defined).
        let dx_i32 = round_f64_to_i32_saturating(dx);
        let dy_i32 = round_f64_to_i32_saturating(dy);
        // checked_add: huge dx/dy must error, not wrap the bubble off-screen.
        let (new_x, new_y) = compute_move_by_new_pos(pos.x, dx_i32, pos.y, dy_i32)?;
        window
            .set_position(PhysicalPosition::new(new_x, new_y))
            .map_err(|e| e.to_string())?;
        // A keyboard nudge is a user move: later resizes must not snap back.
        note_bubble_user_moved();
        Ok(json!({"x": new_x, "y": new_y}))
    })
    .await;
    match join_result {
        Ok(inner) => Ok(inner?),
        Err(join_err) => Err(LausuError::Host(format!(
            "bubble_move_by blocking task failed: {join_err}"
        ))),
    }
}

/// Hide bubble after renderer cleanup. SEC-016: only the bubble may finalize hide.
#[tauri::command]
pub async fn bubble_hide_complete(
    app: tauri::AppHandle,
    window: tauri::Window,
) -> Result<(), LausuError> {
    crate::commands::require_bubble_window(&window)?;
    hide_bubble_window(&app).map_err(LausuError::from)
}

/// Dismiss bubble from its own '×' button. Same hide path as hide_complete.
/// SEC-016: only the bubble may dismiss itself.
#[tauri::command]
pub async fn bubble_dismiss(
    app: tauri::AppHandle,
    window: tauri::Window,
) -> Result<(), LausuError> {
    crate::commands::require_bubble_window(&window)?;
    hide_bubble_window(&app).map_err(LausuError::from)
}

/// Resize bubble to (width, height) physical pixels; clamped to pill MIN/MAX.
/// Not main-window-gated (ResizeObserver auto-fit). f64 at FFI → saturating u32.
#[tauri::command]
pub async fn bubble_resize(
    width: f64,
    height: f64,
    app: tauri::AppHandle,
) -> Result<(), LausuError> {
    let window = app
        .get_webview_window("bubble")
        .ok_or(LausuError::Host("bubble window not found".into()))?;
    // Saturating f64→u32, then clamp to predecessor pill bounds.
    let w = round_f64_to_u32_saturating(width);
    let h = round_f64_to_u32_saturating(height);
    let capped_w = clamp_resize_width(w);
    let capped_h = clamp_resize_height(h);
    use tauri::PhysicalSize;
    window
        .set_size(PhysicalSize::new(capped_w, capped_h))
        .map_err(|e| LausuError::Host(e.to_string()))?;
    // Mode changes resize constantly; keep the chrome stripped no
    // matter which tao path last touched the window. Idempotent.
    super::window::harden_bubble_chrome(&window, true);
    // Edge-anchored pills must stay centered: the initial placement was
    // measured on the pre-content size, and every mode/button change
    // resizes around a stale top-left. Re-anchor on the remembered edge
    // with the NEW size; user-dragged pills keep their position.
    if let Some(edge) = bubble_edge_for_reanchor() {
        match reanchor_bubble_after_resize(&app, &window, &edge) {
            Ok((px, py)) => log::info!(
                "[BUBBLE] re-anchored at ({px},{py}) edge={edge} after resize {capped_w}x{capped_h}"
            ),
            Err(e) => log::warn!("[BUBBLE] re-anchor after resize failed: {}", e),
        }
    }
    Ok(())
}

/// Re-center an edge-anchored bubble after an auto-fit resize, on the
/// monitor holding its current top-left (never the cursor's monitor:
/// the cursor may have moved away since placement).
fn reanchor_bubble_after_resize(
    app: &tauri::AppHandle,
    window: &tauri::WebviewWindow,
    edge: &str,
) -> Result<(i32, i32), String> {
    let pos = window.outer_position().map_err(|e| e.to_string())?;
    let monitor = resolve_monitor_at_point(app, pos.x as f64, pos.y as f64)?;
    let wa = monitor.work_area();
    let wa_rect = RectPx::new(wa.position.x, wa.position.y, wa.size.width, wa.size.height);
    let size = window.outer_size().map_err(|e| e.to_string())?;
    let bubble_w = i32::try_from(size.width).unwrap_or(i32::MAX);
    let bubble_h = i32::try_from(size.height).unwrap_or(i32::MAX);
    let margin = edge_margin_physical(monitor.scale_factor());
    let (px, py) = bubble_position_in_work_area(edge, &wa_rect, bubble_w, bubble_h, margin)?;
    window
        .set_position(PhysicalPosition::new(px, py))
        .map_err(|e| e.to_string())?;
    Ok((px, py))
}

/// Bubble mic-button toggle. First sanctioned dispatch-allowlist bypass (SEC-026):
/// fixed `toggle_dictation` envelope built in Rust, fire-and-forget, rate-limited
/// 1/500ms. Bubble cannot invoke arbitrary sidecar commands.
/// NOTE: see docs/code-notes/tauri-host.md#fire-and-forget-id0
#[tauri::command]
pub async fn bubble_toggle_dictation(
    state: tauri::State<'_, Arc<SidecarState>>,
) -> Result<(), LausuError> {
    // Rate limiter: drop rapid toggles silently (UI tracks actual status_change).
    if !toggle_rate_limiter_allows() {
        log::warn!("[BUBBLE] toggle_dictation rate-limited (last toggle <500ms ago), dropping");
        return Ok(());
    }
    // id=0, no pending entry; reader DEBUG-drops the response.
    crate::commands::sidecar_cmds::dispatch_fire_and_forget(state.inner(), "toggle_dictation", None)
}

/// Pill-space capture rect (device px, from the overlay drag).
/// Translated to virtual-screen pixels by adding the bubble window's
/// outer position before forwarding (the backend grabs screen space).
#[derive(Debug, Clone, Copy)]
pub(super) struct PillCaptureRect {
    pub(super) left: f64,
    pub(super) top: f64,
    pub(super) width: f64,
    pub(super) height: f64,
}

/// Translate a pill-client rect into virtual-screen pixels. Pure
/// (unit-testable): the caller looks up the window position, this only
/// does the saturating math. Bounds mirror the backend
/// (`screenshots/capture.py::validate_rect`) so bad rects fail fast
/// here with a clear message instead of a sidecar round-trip.
pub(super) fn translate_pill_rect_to_screen(
    origin_x: i32,
    origin_y: i32,
    rect: PillCaptureRect,
) -> Result<(i32, i32, u32, u32), String> {
    if !rect.left.is_finite()
        || !rect.top.is_finite()
        || !rect.width.is_finite()
        || !rect.height.is_finite()
    {
        return Err("capture rect must be finite numbers".into());
    }
    if rect.width < 1.0 || rect.height < 1.0 {
        return Err(format!(
            "capture rect too small: {}x{}",
            rect.width, rect.height
        ));
    }
    if rect.width > 7680.0 || rect.height > 4320.0 {
        return Err(format!(
            "capture rect too large: {}x{}",
            rect.width, rect.height
        ));
    }
    let x = origin_x.saturating_add(round_f64_to_i32_saturating(rect.left));
    let y = origin_y.saturating_add(round_f64_to_i32_saturating(rect.top));
    let w = round_f64_to_u32_saturating(rect.width);
    let h = round_f64_to_u32_saturating(rect.height);
    Ok((x, y, w, h))
}

/// Bubble screenshot-annotate capture. Second sanctioned
/// dispatch-allowlist bypass (SEC-026): fixed `screenshot_capture`
/// envelope built in Rust (the sandboxed bubble has no `window.python`,
/// so the renderer cannot dispatch it directly). Request/response (not
/// fire-and-forget) so the renderer can log captured/failed.
/// SEC-016: only the bubble window may call it.
#[tauri::command]
pub async fn bubble_request_screenshot_capture(
    cycle_id: String,
    left: f64,
    top: f64,
    width: f64,
    height: f64,
    state: tauri::State<'_, Arc<SidecarState>>,
    app: tauri::AppHandle,
    window: tauri::Window,
) -> Result<Value, LausuError> {
    crate::commands::require_bubble_window(&window)?;
    if cycle_id.is_empty() || cycle_id.len() > 128 {
        return Err(LausuError::Host("cycle_id must be 1..=128 chars".into()));
    }
    let bubble_window = app
        .get_webview_window("bubble")
        .ok_or(LausuError::Host("bubble window not found".into()))?;
    let origin = bubble_window
        .outer_position()
        .map_err(|e| LausuError::Host(e.to_string()))?;
    let (x, y, w, h) = translate_pill_rect_to_screen(
        origin.x,
        origin.y,
        PillCaptureRect {
            left,
            top,
            width,
            height,
        },
    )
    .map_err(LausuError::Host)?;
    let data = json!({
        "cycle_id": cycle_id,
        "rect": {"left": x, "top": y, "width": w, "height": h},
    });
    let result = crate::commands::sidecar_cmds::dispatch_inner(
        crate::commands::sidecar_cmds::DispatchArgs {
            cmd: "screenshot_capture".to_string(),
            data: Some(data),
        },
        state.inner().clone(),
    )
    .await;
    match &result {
        Ok(value) => {
            let path = value
                .pointer("/data/path")
                .and_then(|p| p.as_str())
                .unwrap_or("?");
            log::info!("[SCREENSHOT] bubble capture ok: {}", path);
        }
        Err(e) => log::warn!("[SCREENSHOT] bubble capture failed: {}", e),
    }
    result
}
