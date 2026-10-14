#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::panic,
    clippy::unreachable
)]

//! Placement-tracker unit tests: edge memory vs user-move clearing.
//! The re-anchor math itself (`bubble_position_in_work_area`) is pinned
//! in `tests.rs`; here we pin the decision layer plus the growth case
//! that caused the off-center startup pill (position measured small,
//! pill grew when the mic/dismiss buttons arrived, top-left stuck).

use super::PlacementTracker;
use crate::commands::bubble::math::{bubble_position_in_work_area, RectPx};

fn wa_primary() -> RectPx {
    RectPx::new(0, 0, 1920, 1040)
}

#[test]
fn test_fresh_tracker_has_no_edge() {
    let tracker = PlacementTracker::fresh();
    assert_eq!(tracker.edge_for_reanchor(), None);
}

#[test]
fn test_edge_position_arms_reanchor() {
    let mut tracker = PlacementTracker::fresh();
    tracker.note_edge_position("bottom");
    assert_eq!(tracker.edge_for_reanchor().as_deref(), Some("bottom"));
    tracker.note_edge_position("top");
    assert_eq!(tracker.edge_for_reanchor().as_deref(), Some("top"));
}

#[test]
fn test_unknown_keyword_clears_edge_fail_closed() {
    let mut tracker = PlacementTracker::fresh();
    tracker.note_edge_position("bottom");
    tracker.note_edge_position("middle");
    assert_eq!(tracker.edge_for_reanchor(), None);
}

#[test]
fn test_user_move_clears_edge() {
    let mut tracker = PlacementTracker::fresh();
    tracker.note_edge_position("bottom");
    tracker.note_user_moved();
    assert_eq!(tracker.edge_for_reanchor(), None);
}

#[test]
fn test_user_move_on_fresh_tracker_is_noop() {
    let mut tracker = PlacementTracker::fresh();
    tracker.note_user_moved();
    assert_eq!(tracker.edge_for_reanchor(), None);
}

#[test]
fn test_edge_replacement_bottom_then_top() {
    let mut tracker = PlacementTracker::fresh();
    tracker.note_edge_position("bottom");
    tracker.note_edge_position("top");
    assert_eq!(tracker.edge_for_reanchor().as_deref(), Some("top"));
}

#[test]
fn test_reanchor_after_growth_stays_bottom_centered() {
    // Startup sequence: hydration measured a 72x47 pill at (924,945),
    // then the mic/dismiss buttons grew it to 180x50. Re-anchoring with
    // the NEW size keeps bottom-center instead of sticking top-left:
    // x centers on 180, y keeps the bottom edge glued to the work area.
    let (x, y) = bubble_position_in_work_area("bottom", &wa_primary(), 180, 50, 48).unwrap();
    assert_eq!(x, (1920 - 180) / 2);
    assert_eq!(y, 1040 - 50 - 48);
    // And it differs from the stale top-left (924,945): the fix moves it.
    assert_ne!((x, y), (924, 945));
}

#[test]
fn test_reanchor_after_growth_stays_top_centered() {
    let (x, y) = bubble_position_in_work_area("top", &wa_primary(), 180, 50, 48).unwrap();
    assert_eq!(x, (1920 - 180) / 2);
    assert_eq!(y, 48);
}
