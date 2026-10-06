//! Sibling tests for `sidecar::worker_supervisor` (per C-TEST-5):
//! pure policy surface only (backoff pin, C-WS-3 predicate, §7.3
//! hook). The async engine needs a live child, so the host run covers
//! it, not here.

use super::worker_supervisor::{
    respawn_worker, should_keep_worker_running, spawn_worker_exit_watcher, worker_backoff_delay_ms,
    worker_generation_is_stale,
};
use crate::util::SUPERVISOR_BACKOFF_MS;

#[test]
fn test_worker_backoff_pins_shared_doubling_schedule() {
    assert_eq!(
        SUPERVISOR_BACKOFF_MS,
        &[500, 1000, 2000, 4000, 8000],
        "worker respawn shares the sidecar supervisor backoff schedule"
    );
}

#[test]
fn test_worker_backoff_first_attempt_is_500ms() {
    assert_eq!(worker_backoff_delay_ms(0), Some(500));
}

#[test]
fn test_worker_backoff_doubles_each_attempt() {
    for i in 1..SUPERVISOR_BACKOFF_MS.len() {
        assert_eq!(
            worker_backoff_delay_ms(i),
            Some(worker_backoff_delay_ms(i - 1).unwrap_or(0) * 2),
            "backoff must double at attempt {}",
            i
        );
    }
}

#[test]
fn test_worker_backoff_past_end_is_none() {
    assert_eq!(worker_backoff_delay_ms(SUPERVISOR_BACKOFF_MS.len()), None);
    assert_eq!(worker_backoff_delay_ms(usize::MAX), None);
}

#[test]
fn test_respawn_path_relays_the_new_bind() {
    /// Regression guard (ADR-0024 Step 6 row b, found by the host run).
    ///
    /// The initial spawn relays `worker_started` from
    /// `spawn.rs::initialize_worker`, but the RESPAWN path used to return
    /// without relaying. A live host run proved the consequence: after
    /// killing the worker, the supervisor respawned it on a NEW port
    /// (65289 -> 63792) while the sidecar still held the dead port, so
    /// the worker hop was unreachable until the app restarted.
    ///
    /// Pins the source so the relay cannot be dropped again.
    let src = include_str!("worker_supervisor.rs");
    let inner = src
        .split("async fn respawn_worker_inner")
        .nth(1)
        .expect("respawn_worker_inner must exist");
    let success_arm = inner
        .split("respawn succeeded on attempt")
        .nth(1)
        .expect("the respawn success arm must exist");
    assert!(
        success_arm.contains("relay_worker_started_to_sidecar"),
        "the respawn success path MUST relay worker_started to the sidecar; \
         otherwise the sidecar keeps the dead worker's port after a crash"
    );
    assert!(
        success_arm.contains("relay_worker_started_to_sidecar(app, fresh_pid, port)"),
        "the respawn relay must pass the freshly-spawned worker pid + the new port"
    );
}

#[test]
fn test_worker_generation_stale_on_mismatch() {
    assert!(worker_generation_is_stale(Some(2), 3));
    assert!(worker_generation_is_stale(Some(0), 1));
}

#[test]
fn test_worker_generation_fresh_on_match() {
    assert!(!worker_generation_is_stale(Some(3), 3));
}

#[test]
fn test_worker_generation_none_never_stale() {
    assert!(!worker_generation_is_stale(None, 0));
    assert!(!worker_generation_is_stale(None, 99));
}

#[test]
fn test_should_keep_worker_running_is_passthrough() {
    assert!(should_keep_worker_running(true));
    assert!(!should_keep_worker_running(false));
}

/// Compile-time contract: the supervisor entry points exist under
/// their documented names (mirrors `test_worker_spawn_stubs_exist`).
#[test]
fn test_worker_supervisor_entry_points_exist() {
    let _respawn_fn = respawn_worker;
    let _watch_fn = spawn_worker_exit_watcher;
}
