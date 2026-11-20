//! Generation-based single-flight gate shared by the bubble's geometry
//! workers: drag/resize events arrive at pointer rate, so a burst must produce
//! one worker while a late event still gets a fresh pass.
//!
//! `release()` is deliberately separate from `arrive()`: the owner clears the
//! slot BEFORE its final geometry read so an event landing during that read
//! claims a new worker instead of being swallowed.

use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};

pub(super) struct SingleFlight {
    generation: AtomicU64,
    waiting: AtomicBool,
}

impl SingleFlight {
    pub(super) const fn new() -> Self {
        Self {
            generation: AtomicU64::new(0),
            waiting: AtomicBool::new(false),
        }
    }

    /// Register an arrival. `true` means this caller owns the worker slot.
    pub(super) fn arrive(&self) -> bool {
        self.generation.fetch_add(1, Ordering::SeqCst);
        !self.waiting.swap(true, Ordering::SeqCst)
    }

    pub(super) fn generation(&self) -> u64 {
        self.generation.load(Ordering::SeqCst)
    }

    /// Free the slot before the final work; a later arrival can then spawn a
    /// replacement worker instead of being dropped by this one.
    pub(super) fn release(&self) {
        self.waiting.store(false, Ordering::SeqCst);
    }
}

/// Whether the generation advanced while the coalesced work was applying.
pub(super) fn needs_follow_up(settled_generation: u64, current_generation: u64) -> bool {
    settled_generation != current_generation
}

// C-TEST-5: sibling test file.
#[cfg(test)]
#[path = "coalesce_tests.rs"]
mod coalesce_tests;
