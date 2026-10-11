#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::panic,
    clippy::unreachable,
    clippy::todo,
    clippy::unimplemented,
    clippy::cast_possible_truncation
)]

//! Sibling tests for `sidecar::spawn::worker` pack-dir launch +
//! stale-pack handshake (per C-TEST-5, sibling test file, no inline
//! tests in production source).
//!
//! Covers the pure launch-target decision (`classify_worker_launch_target`)
//! and the outdated signal shape (`pack_outdated_payload` +
//! `pack_outdated_relay_frame`). Async spawn paths need a Tauri
//! `AppHandle`, so they stay covered by `cargo check` + live runs.

use super::*;

// ── classify_worker_launch_target ─────────────────────────────

/// Pack copy wins when present, even alongside a bundled binary (the
/// pack is the updatable copy; the bundle is the fallback).
#[test]
fn test_classify_pack_exe_wins_over_bundled() {
    let pack = std::path::PathBuf::from("/pack/v1/lausu-worker-triple");
    assert_eq!(
        classify_worker_launch_target(Some(pack.clone()), true),
        WorkerLaunchTarget::PackExe(pack),
        "pack copy present must win over the bundled copy"
    );
}

/// Pack copy alone launches from its absolute path.
#[test]
fn test_classify_pack_exe_alone() {
    let pack = std::path::PathBuf::from("/pack/v1/lausu-worker-triple");
    assert_eq!(
        classify_worker_launch_target(Some(pack.clone()), false),
        WorkerLaunchTarget::PackExe(pack),
        "pack copy alone must resolve to the absolute-path launch"
    );
}

/// No pack copy + bundled binary means the full-offline install path.
#[test]
fn test_classify_bundled_when_no_pack() {
    assert_eq!(
        classify_worker_launch_target(None, true),
        WorkerLaunchTarget::Bundled,
        "bundled copy must launch via externalBin when no pack copy exists"
    );
}

/// Neither copy means a slim install with no pack: the start gate
/// skips quietly (no spawn attempt, no error log).
#[test]
fn test_classify_absent_when_no_binary_anywhere() {
    assert_eq!(
        classify_worker_launch_target(None, false),
        WorkerLaunchTarget::Absent,
        "slim install with no pack must resolve Absent so the start gate skips quietly"
    );
}

// ── pack_outdated_payload ─────────────────────────────────────

/// The outdated payload carries the pack version, the pack's required
/// minimum, and the host range, all typed (E9: u32 both sides).
#[test]
fn test_pack_outdated_payload_shape() {
    let v = pack_outdated_payload("v1", 2);
    assert_eq!(v.get("version").and_then(|s| s.as_str()), Some("v1"));
    assert_eq!(
        v.get("min_proto_version").and_then(|n| n.as_u64()),
        Some(2)
    );
    assert_eq!(
        v.get("host_min_proto_version").and_then(|n| n.as_u64()),
        Some(crate::platform::worker_path::HOST_MIN_PROTO_VERSION as u64)
    );
    assert_eq!(
        v.get("host_proto_version").and_then(|n| n.as_u64()),
        Some(crate::platform::worker_path::HOST_PROTO_VERSION as u64)
    );
}

// ── pack_outdated_relay_frame ─────────────────────────────────

/// The relay frame reuses the worker_started hop shape: literal
/// `offline_pack_outdated` type + data + numeric id (C-WS-2).
#[test]
fn test_pack_outdated_relay_frame_shape() {
    let v = pack_outdated_relay_frame("v2", 3, 9);
    assert_eq!(
        v.get("type").and_then(|t| t.as_str()),
        Some("offline_pack_outdated"),
        "relay must use the pack-outdated event name"
    );
    let data = v.get("data").expect("relay frame must carry data");
    assert_eq!(data.get("version").and_then(|s| s.as_str()), Some("v2"));
    assert_eq!(
        data.get("min_proto_version").and_then(|n| n.as_u64()),
        Some(3)
    );
    assert_eq!(v.get("id").and_then(|i| i.as_u64()), Some(9));
}

/// The event-name const pins the stale-pack contract string in one
/// place (renderer + sidecar slices subscribe to this literal).
#[test]
fn test_pack_outdated_event_name_pinned() {
    assert_eq!(PACK_OUTDATED_EVENT, "offline_pack_outdated");
}

// ── pack_refusal_message ──────────────────────────────────────

/// The stale-pack refusal names the pack minimum, the host range,
/// and the exe path (the operator needs all three to act).
#[test]
fn test_pack_refusal_message_mismatch() {
    let msg = pack_refusal_message(
        std::path::Path::new("/pack/v2/lausu-worker-triple"),
        &crate::platform::worker_path::PackProtoStatus::Mismatch {
            min_proto_version: 2,
        },
    );
    assert!(
        msg.contains("min_proto_version=2"),
        "refusal must name the pack minimum: {msg}"
    );
    assert!(
        msg.contains("/pack/v2/lausu-worker-triple"),
        "refusal must name the exe path: {msg}"
    );
}

/// The missing-manifest refusal names the reason (corrupt downloads
/// read differently from absent ones in triage).
#[test]
fn test_pack_refusal_message_missing_manifest() {
    let msg = pack_refusal_message(
        std::path::Path::new("/pack/v1/lausu-worker-triple"),
        &crate::platform::worker_path::PackProtoStatus::MissingManifest {
            reason: "invalid_json",
        },
    );
    assert!(
        msg.contains("invalid_json"),
        "refusal must name the reason: {msg}"
    );
}
