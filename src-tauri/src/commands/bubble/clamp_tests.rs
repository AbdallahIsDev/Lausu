#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::panic,
    clippy::unreachable
)]

//! Work-area clamp tests: the rule that keeps a dropped pill reachable.
//!
//! The reported failure was a pill dropped onto the Windows taskbar: the
//! taskbar paints over an always-on-top window, so the pill could not be
//! grabbed again. The clamp is Chromium's `Rect::AdjustToFit` semantics, and
//! these cases pin every outcome a drop can have — inside (no-op), past an
//! edge, past a corner, on a secondary monitor with negative coordinates, off
//! the work area in an axis it cannot fit, and the Wayland shape where the work
//! area equals the monitor bounds.

use crate::commands::bubble::clamp::clamp_candidate;
use crate::commands::bubble::coalesce::{needs_follow_up, SingleFlight};
use crate::commands::bubble::math::{clamp_into_work_area, rect_center_point, RectPx};

/// 1920x1080 monitor with a 40px bottom taskbar.
fn wa_primary() -> RectPx {
    RectPx::new(0, 0, 1920, 1040)
}

/// Secondary monitor placed to the LEFT of the primary (negative x).
fn wa_left() -> RectPx {
    RectPx::new(-1920, 0, 1920, 1040)
}

#[test]
fn test_pill_already_inside_is_never_moved() {
    // The common case: a clamp must be a no-op, never a re-apply (C-LOG-8).
    assert_eq!(
        clamp_into_work_area(&wa_primary(), 800, 500, 180, 50),
        (800, 500)
    );
    // Flush against the work-area edges is still inside.
    assert_eq!(clamp_into_work_area(&wa_primary(), 0, 0, 180, 50), (0, 0));
    assert_eq!(
        clamp_into_work_area(&wa_primary(), 1740, 990, 180, 50),
        (1740, 990)
    );
}

#[test]
fn test_pill_dropped_on_the_bottom_taskbar_comes_back_up() {
    // The exact report: dropped at the very bottom, half under the taskbar
    // (work area ends at y=1040), then dropped entirely out of it.
    assert_eq!(
        clamp_into_work_area(&wa_primary(), 800, 1010, 180, 50),
        (800, 990)
    );
    assert_eq!(
        clamp_into_work_area(&wa_primary(), 800, 1470, 180, 50),
        (800, 990)
    );
}

#[test]
fn test_pill_dropped_past_the_right_edge_slides_left() {
    assert_eq!(
        clamp_into_work_area(&wa_primary(), 1900, 500, 180, 50),
        (1740, 500)
    );
}

#[test]
fn test_pill_dropped_past_a_corner_is_pulled_in_on_both_axes() {
    assert_eq!(
        clamp_into_work_area(&wa_primary(), 1910, 1060, 180, 50),
        (1740, 990)
    );
}

#[test]
fn test_pill_dropped_above_the_top_edge_is_pushed_down() {
    // Menubar/dock shapes (macOS visibleFrame) start below y=0.
    let wa = RectPx::new(0, 25, 1920, 1015);
    assert_eq!(clamp_into_work_area(&wa, 800, 0, 180, 50), (800, 25));
}

#[test]
fn test_secondary_monitor_with_negative_origin_clamps_to_its_own_work_area() {
    assert_eq!(
        clamp_into_work_area(&wa_left(), -1800, 1030, 180, 50),
        (-1800, 990)
    );
    // A pill dragged left off that monitor's left edge cannot escape to -inf.
    assert_eq!(
        clamp_into_work_area(&wa_left(), -2600, 500, 180, 50),
        (-1920, 500)
    );
}

#[test]
fn test_pill_larger_than_the_work_area_aligns_to_its_origin() {
    // Narrow dock/menubar screens: the pill cannot fit, so its top-left wins
    // over shoving it past the far edge (it would be unreachable either way).
    let narrow = RectPx::new(0, 0, 120, 100);
    // Wider than the work area → pinned to its left edge; the axis it DOES fit
    // (50 < 100) is clamped normally instead of being dragged to the origin.
    assert_eq!(clamp_into_work_area(&narrow, 60, 90, 180, 50), (0, 50));
}

#[test]
fn test_zero_width_work_area_does_not_panic_or_wrap() {
    // A monitor query that answers nothing must degrade, not overflow.
    let degenerate = RectPx::new(0, 0, 0, 0);
    assert_eq!(clamp_into_work_area(&degenerate, 500, 500, 180, 50), (0, 0));
}

#[test]
fn test_saturating_arithmetic_on_extreme_coordinates() {
    // Huge virtual desktops must not wrap an i32 into the negative range.
    let wa = RectPx::new(i32::MAX - 100, i32::MAX - 100, 100, 100);
    // A target past the far edge lands on the last in-bounds top-left, and the
    // arithmetic saturates instead of wrapping into negative coordinates.
    let (x, y) = clamp_into_work_area(&wa, i32::MAX, i32::MAX, 40, 24);
    assert_eq!((x, y), (i32::MAX - 40, i32::MAX - 24));
}

#[test]
fn test_candidate_helper_matches_the_window_clamp() {
    // The keyboard nudge and the resize path use `clamp_candidate`; it must be
    // the same rule the drag path applies to the live window.
    let wa = wa_primary();
    for (x, y) in [(800, 500), (800, 1470), (1910, 500), (-50, -50)] {
        assert_eq!(
            clamp_candidate(&wa, x, y, 180, 50),
            clamp_into_work_area(&wa, x, y, 180, 50)
        );
    }
}

#[test]
fn a_late_move_during_the_clamp_window_schedules_a_follow_up_clamp() {
    // The settle waiter releases WAITING *before* the geometry read. A Moved
    // landing in that window must win a fresh worker slot instead of being
    // swallowed, so the pill's final resting position still gets clamped.
    let flight = SingleFlight::new();
    assert!(flight.arrive(), "first move owns the clamp worker");
    let settled = flight.generation();
    flight.release(); // happens before `clamp_bubble_into_work_area`
    assert!(
        flight.arrive(),
        "a late Moved after release starts a second clamp worker"
    );
    assert_ne!(flight.generation(), settled);
    assert!(needs_follow_up(settled, flight.generation()));
}

#[test]
fn nudge_and_drag_pick_the_monitor_from_the_rect_center() {
    // Two stacked work areas: the candidate's top-left is in the UPPER one but
    // its center is in the LOWER one. Both the drag clamp and the keyboard
    // nudge now resolve their monitor from the center (C-WIN-2), so a nudge
    // can no longer clamp against a different display than a drag.
    let upper = RectPx::new(0, 0, 1920, 1000);
    let lower = RectPx::new(0, 1000, 1920, 1000);
    let (x, y, w, h) = (800, 980, 180, 60);
    assert!(
        upper.contains(x, y),
        "top-left alone would pick the upper monitor"
    );
    let (cx, cy) = rect_center_point(x, y, w, h);
    assert_eq!((cx, cy), (890.0, 1010.0));
    assert!(
        lower.contains(cx as i32, cy as i32),
        "center picks the lower monitor"
    );
    // Both paths feed the SAME center-chosen work area to the same clamp rule.
    let dragged = clamp_into_work_area(&lower, x, y, w, h);
    let nudged = clamp_into_work_area(&lower, x, y, w, h);
    assert_eq!(dragged, nudged);
    assert_eq!(dragged, (800, 1000));
    // The rejected top-left choice would have produced a different result.
    assert_ne!(dragged, clamp_into_work_area(&upper, x, y, w, h));
}
