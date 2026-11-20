//! Keep the pill inside the monitor's WORK AREA (bounds minus taskbar/dock).
//!
//! Dragging runs through the OS caption region, so the pill can be dropped on
//! top of the taskbar — and once the taskbar is activated it paints over an
//! always-on-top pill, leaving it unreachable. The fix is the one browsers use
//! (Chromium `WindowSizer`): allow the drag, then constrain the window to the
//! work area of the monitor it landed on as soon as the drag settles. Never
//! clamp mid-drag — that fights the OS move loop.
//!
//! `Monitor::work_area()` is cross-platform: Windows `GetMonitorInfo` `rcWork`,
//! macOS `NSScreen.visibleFrame`, Linux `gdk_monitor.workarea()` (`_NET_WORKAREA`
//! under X11; the full monitor on Wayland, where panels publish no work area).
//!
//! NOTE: see docs/code-notes/tauri-host.md#bubble-work-area-clamp

use std::time::Duration;

use tauri::{Manager, PhysicalPosition};

use super::coalesce::{needs_follow_up, SingleFlight};
use super::commands::resolve_monitor_at_point;
use super::math::{clamp_into_work_area, rect_center_point, RectPx};

/// A drag emits `Moved` at pointer rate; wait this long for the drag to settle.
pub(super) const DRAG_SETTLE_MS: u64 = 250;

static CLAMP_FLIGHT: SingleFlight = SingleFlight::new();

/// Constrain the pill once the current drag (if any) has settled.
///
/// The window position is read at clamp time, not captured here, so the
/// final resting position of the drag is always the one constrained.
pub(crate) fn schedule_work_area_clamp(app: tauri::AppHandle) {
    if !CLAMP_FLIGHT.arrive() {
        return; // an existing waiter will observe the newer generation
    }
    let worker = std::thread::Builder::new()
        .name("bubble-work-area-clamp".into())
        .spawn(move || {
            let settle = Duration::from_millis(DRAG_SETTLE_MS);
            let settled;
            loop {
                let seen = CLAMP_FLIGHT.generation();
                std::thread::sleep(settle);
                if CLAMP_FLIGHT.generation() == seen {
                    settled = seen;
                    break;
                }
            }
            // Release BEFORE the geometry read: a `Moved` landing during the
            // clamp must start a fresh waiter, not be swallowed by this one.
            CLAMP_FLIGHT.release();
            match clamp_bubble_into_work_area(&app) {
                Ok(Some((x, y))) => {
                    log::info!("[BUBBLE] moved back into the work area at ({x},{y})")
                }
                Ok(None) => {}
                Err(e) => log::debug!("[BUBBLE] work-area clamp skipped: {e}"),
            }
            // A newer final position arrived while clamping: clamp again.
            if needs_follow_up(settled, CLAMP_FLIGHT.generation()) {
                schedule_work_area_clamp(app);
            }
        });
    if worker.is_err() {
        CLAMP_FLIGHT.release();
        log::warn!("[BUBBLE] work-area clamp worker could not start");
    }
}

/// Move the bubble so it lies fully inside its monitor's work area.
///
/// `Ok(None)` means the pill is already inside (the common case: an unchanged
/// position must never be re-applied, see C-LOG-8). Errors are non-fatal —
/// every caller is a best-effort geometry correction.
pub(crate) fn clamp_bubble_into_work_area(
    app: &tauri::AppHandle,
) -> Result<Option<(i32, i32)>, String> {
    let window = app
        .get_webview_window("bubble")
        .ok_or("bubble window not found")?;
    let pos = window.outer_position().map_err(|e| e.to_string())?;
    let size = window.outer_size().map_err(|e| e.to_string())?;
    let bubble_w = i32::try_from(size.width).unwrap_or(i32::MAX);
    let bubble_h = i32::try_from(size.height).unwrap_or(i32::MAX);
    // The CENTER picks the monitor: a pill dropped below a stacked monitor's
    // top edge belongs to that monitor, not to the one its top-left was on.
    let (center_x, center_y) = rect_center_point(pos.x, pos.y, bubble_w, bubble_h);
    let monitor = resolve_monitor_at_point(app, center_x, center_y)?;
    let wa = monitor.work_area();
    let wa_rect = RectPx::new(wa.position.x, wa.position.y, wa.size.width, wa.size.height);
    let (x, y) = clamp_into_work_area(&wa_rect, pos.x, pos.y, bubble_w, bubble_h);
    if (x, y) == (pos.x, pos.y) {
        return Ok(None);
    }
    window
        .set_position(PhysicalPosition::new(x, y))
        .map_err(|e| e.to_string())?;
    Ok(Some((x, y)))
}

/// Constrain a candidate position without touching the window.
///
/// Used by the keyboard nudge, which applies the clamped result itself, and by
/// the resize path, which already has the work area in hand.
pub(super) fn clamp_candidate(
    wa: &RectPx,
    x: i32,
    y: i32,
    bubble_w: i32,
    bubble_h: i32,
) -> (i32, i32) {
    clamp_into_work_area(wa, x, y, bubble_w, bubble_h)
}

// C-TEST-5: sibling test file.
#[cfg(test)]
#[path = "clamp_tests.rs"]
mod clamp_tests;
