//! Bubble placement preference: configured edge vs user drag.
//!
//! `bubble_set_position` centers on the transient `outer_size`; later
//! auto-fit `bubble_resize` calls kept top-left and de-centered the pill.
//! This tracker remembers the last configured edge so resizes re-anchor;
//! any user move clears it so a resize never fights a drag.

use std::sync::{Mutex, OnceLock};

use crate::state::lock;

/// Edge preference: `Some("top"|"bottom")` re-anchors on resize,
/// `None` means the user moved the pill (leave it alone).
pub(super) struct PlacementTracker {
    edge: Option<String>,
}

impl PlacementTracker {
    fn fresh() -> Self {
        Self { edge: None }
    }

    /// Remember the configured edge after a successful edge placement.
    /// Only the two known keywords arm re-anchoring; anything else
    /// clears it (fail-closed, same as the position math's error arm).
    pub(super) fn note_edge_position(&mut self, position: &str) {
        if position == "top" || position == "bottom" {
            self.edge = Some(position.to_string());
        } else {
            self.edge = None;
        }
    }

    /// A user move (drag or keyboard nudge) wins over the edge: later
    /// resizes keep top-left instead of snapping back to center.
    pub(super) fn note_user_moved(&mut self) {
        self.edge = None;
    }

    /// Edge to re-anchor to after a resize, if the user hasn't moved.
    pub(super) fn edge_for_reanchor(&self) -> Option<String> {
        self.edge.clone()
    }
}

static PLACEMENT: OnceLock<Mutex<PlacementTracker>> = OnceLock::new();

fn placement() -> &'static Mutex<PlacementTracker> {
    PLACEMENT.get_or_init(|| Mutex::new(PlacementTracker::fresh()))
}

/// Record a successful configured-edge placement (from `bubble_set_position`).
pub(crate) fn note_bubble_edge_position(position: &str) {
    lock(placement()).note_edge_position(position);
}

/// Record a user-initiated move (drag `Moved` event, `bubble_move_by`).
pub(crate) fn note_bubble_user_moved() {
    lock(placement()).note_user_moved();
}

/// Configured edge to re-anchor to, `None` once the user has moved.
pub(crate) fn bubble_edge_for_reanchor() -> Option<String> {
    lock(placement()).edge_for_reanchor()
}

// C-TEST-5: sibling test file.
#[cfg(test)]
#[path = "placement_tests.rs"]
mod placement_tests;
