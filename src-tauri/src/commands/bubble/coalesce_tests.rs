#![allow(clippy::unwrap_used, clippy::expect_used, clippy::panic)]

//! Single-flight coalescing tests: one worker per geometry-event burst.
//!
//! The bubble receives `Moved` at pointer rate. A fresh worker (and a fresh
//! child-window enumeration) per sample is pure churn; the generation gate
//! collapses a whole burst into one pass while still letting a late arrival
//! after `release` claim a new worker slot.

use crate::commands::bubble::coalesce::SingleFlight;

#[test]
fn a_pointer_rate_burst_coalesces_into_exactly_one_worker() {
    let gate = SingleFlight::new();
    assert!(gate.arrive(), "first arrival owns the worker slot");
    for _ in 0..120 {
        assert!(!gate.arrive(), "a burst must not spawn a worker per sample");
    }
    assert_eq!(gate.generation(), 121);
    gate.release();
    assert!(gate.arrive(), "a later burst may claim a new worker slot");
}
