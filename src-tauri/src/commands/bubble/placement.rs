//! Bubble placement preference: configured edge vs user drag.
//!
//! `bubble_set_position` centers on the transient `outer_size`; later
//! auto-fit `bubble_resize` calls kept top-left and de-centered the pill.
//! This tracker remembers the last configured edge so resizes re-anchor;
//! any user move clears it so a resize never fights a drag. The edge is
//! armed from the sidecar's `bubble_config` frame, which lands before the
//! first show: placement must not depend on the renderer's hydration.

use std::sync::{Mutex, OnceLock};

use crate::state::lock;

/// Edge preference: `Some("top"|"bottom")` re-anchors on resize,
/// `None` means the user moved the pill (leave it alone).
pub(super) struct PlacementTracker {
    edge: Option<String>,
    /// Sticky: a configuration frame must never undo a user drag.
    user_moved: bool,
    /// Last edge a configuration frame carried, so an UNCHANGED edge
    /// (reconnect) is told apart from a deliberate settings change.
    configured: Option<String>,
}

impl PlacementTracker {
    fn fresh() -> Self {
        Self {
            edge: None,
            user_moved: false,
            configured: None,
        }
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

    /// Arm the edge from a configuration frame (startup / settings
    /// change). Returns whether the caller should place the window:
    /// `false` for an unchanged edge after a user drag (reconnects must
    /// not yank a dragged pill), `true` for a deliberate edge change,
    /// `false` for an unknown keyword (fail-closed, no placement).
    pub(super) fn note_configured_edge(&mut self, position: &str) -> bool {
        if position != "top" && position != "bottom" {
            return false;
        }
        let changed = self.configured.as_deref() != Some(position);
        self.configured = Some(position.to_string());
        if self.user_moved && !changed {
            return false;
        }
        // A deliberate edge change is a new instruction: it clears the
        // drag memory it overrides.
        self.user_moved = false;
        self.note_edge_position(position);
        true
    }

    /// A user move (drag or keyboard nudge) wins over the edge: later
    /// resizes keep top-left instead of snapping back to center.
    pub(super) fn note_user_moved(&mut self) {
        self.edge = None;
        self.user_moved = true;
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

/// Arm the edge from a `bubble_config` frame; `false` means the user
/// owns the position this session (or the keyword is invalid).
pub(crate) fn note_bubble_configured_edge(position: &str) -> bool {
    lock(placement()).note_configured_edge(position)
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
