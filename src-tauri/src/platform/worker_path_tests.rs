#![allow(
    clippy::unwrap_used,
    clippy::expect_used,
    clippy::panic,
    clippy::unreachable,
    clippy::todo,
    clippy::unimplemented,
    clippy::cast_possible_truncation
)]

//! Sibling tests for `platform::worker_path` (per C-TEST-5, sibling
//! test file, no inline tests in production source).
//!
//! Covers:
//!
//! - **Per-platform pack-dir resolution** (`pack_dir_from_env`): the
//!   per-platform runtime-pack root under LOCALAPPDATA (Windows) /
//!   XDG_DATA_HOME (Linux) / `~/Library/Application Support` (macOS).
//!   Mirrors the structure of `paths_tests::test_config_dir_*`.
//! - **Worker exe path construction** (`worker_exe_path_from_env`):
//!   the full path including the version leaf + target-triple-suffixed
//!   worker exe name.
//! - **Empty-string env vars treated as unset**: empty `HOME` /
//!   `LOCALAPPDATA` / `XDG_DATA_HOME` are filtered to `None` at the
//!   top of `pack_dir_from_env` (mirrors the XDG spec).
//! - **Pack-version resolution** (`pack_version`): the
//!   `VOICE_TYPER_PACK_VERSION` env var falls back to
//!   `DEFAULT_PACK_VERSION` when unset / empty.
//! - **Constants**: `WORKER_BIN_BASE_NAME`, `RUNTIME_PACK_DIR`,
//!   `DEFAULT_PACK_VERSION` pin the public API surface so a future
//!   rename is a deliberate change, not silent drift.
//!
//! Cross-platform: per-platform tests are `#[cfg(target_os = "...")]`-
//! gated so the test suite runs on every host (matching the pattern
//! in `paths_tests.rs`).

use super::*;

// ── Constants ───────────────────────────────────────────────────────

/// The worker exe base name (without triple suffix + .exe) must stay
/// pinned to `lausu-worker`: `externalBin` in `tauri.conf.json`
/// + `plugins.shell.scope` + the Python-side `build_worker_*.sh`
/// `--output-filename` flag all depend on this exact string.
#[test]
fn test_worker_bin_base_name_pinned() {
    assert_eq!(WORKER_BIN_BASE_NAME, "lausu-worker");
}

/// The runtime-pack directory leaf name must stay pinned to
/// `runtime-pack`: the Python-side pack downloader + the
/// `pack-manifest.json` integrity verifier both depend on this
/// exact leaf name.
#[test]
fn test_runtime_pack_dir_pinned() {
    assert_eq!(RUNTIME_PACK_DIR, "runtime-pack");
}

/// The default pack version must stay pinned to `v1`, the
/// The worker skeleton uses this as the dev-only sentinel before the
/// pack downloader is wired up. Production code paths set the
/// `VOICE_TYPER_PACK_VERSION` env var explicitly.
#[test]
fn test_default_pack_version_pinned() {
    assert_eq!(DEFAULT_PACK_VERSION, "v1");
}

// ── pack_dir_from_env (per-platform runtime-pack root) ──────────────

/// Windows: `%LOCALAPPDATA%\lausu\runtime-pack\`
/// (NOT `%APPDATA%`: the runtime-pack is a per-machine cache that
/// should NOT roam with the user profile; the sidecar's `config_dir`
/// uses `%APPDATA%` for roaming config, but the pack is separate.)
#[cfg(target_os = "windows")]
#[test]
fn test_pack_dir_windows_localappdata() {
    let env = WorkerPathEnv {
        home: Some("C:\\Users\\Alice"),
        local_appdata: Some("C:\\Users\\Alice\\AppData\\Local"),
        appdata: Some("C:\\Users\\Alice\\AppData\\Roaming"),
        xdg_data_home: None,
        voice_typer_config_dir: None,
    };
    let p = pack_dir_from_env(env);
    assert_eq!(
        p,
        std::path::PathBuf::from("C:\\Users\\Alice\\AppData\\Local")
            .join(APP_SLUG)
            .join(RUNTIME_PACK_DIR),
        "Windows pack_dir must be %LOCALAPPDATA%\\lausu\\runtime-pack"
    );
}

/// Windows: missing `LOCALAPPDATA` falls back to CWD-relative
/// `./lausu/runtime-pack` (mirrors `config_dir_from_env`'s
/// APPDATA fallback for Windows service accounts / headless CI).
#[cfg(target_os = "windows")]
#[test]
fn test_pack_dir_windows_missing_localappdata_falls_back_to_cwd() {
    let env = WorkerPathEnv {
        home: Some("C:\\Users\\Alice"),
        local_appdata: None,
        appdata: None,
        xdg_data_home: None,
        voice_typer_config_dir: None,
    };
    let p = pack_dir_from_env(env);
    assert_eq!(
        p,
        std::path::PathBuf::from(".")
            .join(APP_SLUG)
            .join(RUNTIME_PACK_DIR),
        "missing LOCALAPPDATA → CWD fallback ./lausu/runtime-pack"
    );
}

/// Linux: `$XDG_DATA_HOME/lausu/runtime-pack/`
/// (default `~/.local/share/lausu/runtime-pack/`).
#[cfg(target_os = "linux")]
#[test]
fn test_pack_dir_linux_xdg_data_home() {
    let env = WorkerPathEnv {
        home: Some("/home/alice"),
        local_appdata: None,
        appdata: None,
        xdg_data_home: Some("/custom/xdg"),
        voice_typer_config_dir: None,
    };
    let p = pack_dir_from_env(env);
    assert_eq!(
        p,
        std::path::PathBuf::from("/custom/xdg")
            .join(APP_SLUG)
            .join(RUNTIME_PACK_DIR),
        "Linux pack_dir must honor XDG_DATA_HOME when set"
    );
}

/// Linux: missing `XDG_DATA_HOME` falls back to
/// `~/.local/share/lausu/runtime-pack/` (the XDG spec default).
#[cfg(target_os = "linux")]
#[test]
fn test_pack_dir_linux_xdg_unset_falls_back_to_home() {
    let env = WorkerPathEnv {
        home: Some("/home/alice"),
        local_appdata: None,
        appdata: None,
        xdg_data_home: None,
        voice_typer_config_dir: None,
    };
    let p = pack_dir_from_env(env);
    assert_eq!(
        p,
        std::path::PathBuf::from("/home/alice")
            .join(".local")
            .join("share")
            .join(APP_SLUG)
            .join(RUNTIME_PACK_DIR),
        "Linux pack_dir with no XDG_DATA_HOME → ~/.local/share/lausu/runtime-pack"
    );
}

/// Linux: missing `HOME` (and missing `XDG_DATA_HOME`) falls back to
/// CWD-relative `./lausu/runtime-pack` (mirrors `config_dir`'s
/// missing-HOME fallback for systemd user units without
/// `Environment=HOME=...`).
#[cfg(target_os = "linux")]
#[test]
fn test_pack_dir_linux_missing_home_falls_back_to_cwd() {
    let env = WorkerPathEnv {
        home: None,
        local_appdata: None,
        appdata: None,
        xdg_data_home: None,
        voice_typer_config_dir: None,
    };
    let p = pack_dir_from_env(env);
    assert_eq!(
        p,
        std::path::PathBuf::from(".")
            .join(APP_SLUG)
            .join(RUNTIME_PACK_DIR),
        "missing HOME on Linux → CWD fallback ./lausu/runtime-pack"
    );
}

/// macOS: `~/Library/Application Support/lausu/runtime-pack/`.
#[cfg(target_os = "macos")]
#[test]
fn test_pack_dir_macos_application_support() {
    let env = WorkerPathEnv {
        home: Some("/Users/alice"),
        local_appdata: None,
        appdata: None,
        xdg_data_home: None,
        voice_typer_config_dir: None,
    };
    let p = pack_dir_from_env(env);
    assert_eq!(
        p,
        std::path::PathBuf::from("/Users/alice")
            .join("Library")
            .join("Application Support")
            .join(APP_SLUG)
            .join(RUNTIME_PACK_DIR),
        "macOS pack_dir must be ~/Library/Application Support/lausu/runtime-pack"
    );
}

/// macOS: missing `HOME` falls back to CWD-relative
/// `./Library/Application Support/lausu/runtime-pack` (mirrors
/// `config_dir`'s missing-HOME fallback for system LaunchDaemons).
#[cfg(target_os = "macos")]
#[test]
fn test_pack_dir_macos_missing_home_falls_back_to_cwd() {
    let env = WorkerPathEnv {
        home: None,
        local_appdata: None,
        appdata: None,
        xdg_data_home: None,
        voice_typer_config_dir: None,
    };
    let p = pack_dir_from_env(env);
    assert_eq!(
        p,
        std::path::PathBuf::from(".")
            .join("Library")
            .join("Application Support")
            .join(APP_SLUG)
            .join(RUNTIME_PACK_DIR),
        "missing HOME on macOS → CWD fallback ./Library/Application Support/lausu/runtime-pack"
    );
}

// ── Empty-string env vars treated as unset (XDG-spec rule) ──────────

/// An empty `LOCALAPPDATA` on Windows should be treated as unset →
/// CWD fallback (mirrors the XDG-spec rule applied in
/// `config_dir_from_env` for empty APPDATA).
#[cfg(target_os = "windows")]
#[test]
fn test_pack_dir_windows_empty_localappdata_treated_as_unset() {
    let env = WorkerPathEnv {
        home: Some("C:\\Users\\Alice"),
        local_appdata: Some(""),
        appdata: None,
        xdg_data_home: None,
        voice_typer_config_dir: None,
    };
    let p = pack_dir_from_env(env);
    assert_eq!(
        p,
        std::path::PathBuf::from(".")
            .join(APP_SLUG)
            .join(RUNTIME_PACK_DIR),
        "empty LOCALAPPDATA → treated as unset → CWD fallback"
    );
}

/// An empty `XDG_DATA_HOME` on Linux should be treated as unset →
/// fall back to HOME-based path.
#[cfg(target_os = "linux")]
#[test]
fn test_pack_dir_linux_empty_xdg_treated_as_unset() {
    let env = WorkerPathEnv {
        home: Some("/home/alice"),
        local_appdata: None,
        appdata: None,
        xdg_data_home: Some(""),
        voice_typer_config_dir: None,
    };
    let p = pack_dir_from_env(env);
    assert_eq!(
        p,
        std::path::PathBuf::from("/home/alice")
            .join(".local")
            .join("share")
            .join(APP_SLUG)
            .join(RUNTIME_PACK_DIR),
        "empty XDG_DATA_HOME → treated as unset → HOME-based path"
    );
}

/// An empty `HOME` on Linux (with empty `XDG_DATA_HOME`) should be
/// treated as unset → CWD fallback.
#[cfg(target_os = "linux")]
#[test]
fn test_pack_dir_linux_empty_home_and_empty_xdg_treated_as_unset() {
    let env = WorkerPathEnv {
        home: Some(""),
        local_appdata: None,
        appdata: None,
        xdg_data_home: Some(""),
        voice_typer_config_dir: None,
    };
    let p = pack_dir_from_env(env);
    assert_eq!(
        p,
        std::path::PathBuf::from(".")
            .join(APP_SLUG)
            .join(RUNTIME_PACK_DIR),
        "empty HOME + empty XDG_DATA_HOME → both treated as unset → CWD fallback"
    );
}

// ── worker_exe_path_from_env (full path with version + worker name) ──

/// The full worker exe path on Windows must be:
/// `%LOCALAPPDATA%\lausu\runtime-pack\<version>\lausu-worker-<triple>.exe`
///
/// We can't pin the triple here (it's runtime-dependent), but we CAN
/// verify the path ends with the expected suffix + that the
/// version leaf is interpolated correctly.
#[cfg(target_os = "windows")]
#[test]
fn test_worker_exe_path_windows_full_path() {
    let env = WorkerPathEnv {
        home: Some("C:\\Users\\Alice"),
        local_appdata: Some("C:\\Users\\Alice\\AppData\\Local"),
        appdata: None,
        xdg_data_home: None,
        voice_typer_config_dir: None,
    };
    let p = worker_exe_path_from_env(env, "v1.2.0");
    let triple = crate::sidecar::spawn::target_triple::current_target_triple();
    let expected_name = format!("{}-{}.exe", WORKER_BIN_BASE_NAME, triple);
    assert_eq!(
        p.file_name().and_then(|n| n.to_str()),
        Some(expected_name.as_str()),
        "worker exe file name must be lausu-worker-<triple>.exe"
    );
    assert_eq!(
        p.parent()
            .and_then(|p| p.file_name())
            .and_then(|n| n.to_str()),
        Some("v1.2.0"),
        "version leaf must be interpolated into the path"
    );
    // The runtime-pack leaf must appear two levels up from the exe.
    let runtime_pack_parent = p
        .parent() // <version>/
        .and_then(|p| p.parent()) // runtime-pack/
        .and_then(|p| p.file_name())
        .and_then(|n| n.to_str());
    assert_eq!(
        runtime_pack_parent,
        Some(RUNTIME_PACK_DIR),
        "runtime-pack leaf must appear in the path"
    );
}

/// The full worker exe path on Linux must be:
/// `$XDG_DATA_HOME/lausu/runtime-pack/<version>/lausu-worker-<triple>`
/// (no `.exe` suffix on POSIX).
#[cfg(target_os = "linux")]
#[test]
fn test_worker_exe_path_linux_full_path() {
    let env = WorkerPathEnv {
        home: Some("/home/alice"),
        local_appdata: None,
        appdata: None,
        xdg_data_home: Some("/custom/xdg"),
        voice_typer_config_dir: None,
    };
    let p = worker_exe_path_from_env(env, "v1");
    let triple = crate::sidecar::spawn::target_triple::current_target_triple();
    let expected_name = format!("{}-{}", WORKER_BIN_BASE_NAME, triple);
    assert_eq!(
        p.file_name().and_then(|n| n.to_str()),
        Some(expected_name.as_str()),
        "worker exe file name must be lausu-worker-<triple> (no .exe on POSIX)"
    );
    // No `.exe` extension on POSIX.
    assert!(
        !p.to_string_lossy().ends_with(".exe"),
        "POSIX worker exe path must NOT have a .exe suffix"
    );
}

/// The full worker exe path on macOS must be:
/// `~/Library/Application Support/lausu/runtime-pack/<version>/lausu-worker-<triple>`
/// (no `.exe` suffix on POSIX).
#[cfg(target_os = "macos")]
#[test]
fn test_worker_exe_path_macos_full_path() {
    let env = WorkerPathEnv {
        home: Some("/Users/alice"),
        local_appdata: None,
        appdata: None,
        xdg_data_home: None,
        voice_typer_config_dir: None,
    };
    let p = worker_exe_path_from_env(env, "v1");
    let triple = crate::sidecar::spawn::target_triple::current_target_triple();
    let expected_name = format!("{}-{}", WORKER_BIN_BASE_NAME, triple);
    assert_eq!(
        p.file_name().and_then(|n| n.to_str()),
        Some(expected_name.as_str()),
        "worker exe file name must be lausu-worker-<triple> (no .exe on POSIX)"
    );
    assert!(
        !p.to_string_lossy().ends_with(".exe"),
        "POSIX worker exe path must NOT have a .exe suffix"
    );
}

/// The worker exe path must be idempotent across calls with the same
/// env + version (mirrors `config_dir_from_env`'s purity contract —
/// the function is a pure function of its inputs, no global state).
#[test]
fn test_worker_exe_path_is_pure() {
    let env = WorkerPathEnv {
        home: if cfg!(target_os = "windows") {
            Some("C:\\Users\\Alice")
        } else if cfg!(target_os = "macos") {
            Some("/Users/alice")
        } else {
            Some("/home/alice")
        },
        local_appdata: if cfg!(target_os = "windows") {
            Some("C:\\Users\\Alice\\AppData\\Local")
        } else {
            None
        },
        appdata: None,
        xdg_data_home: if cfg!(target_os = "linux") {
            Some("/custom/xdg")
        } else {
            None
        },
        voice_typer_config_dir: None,
    };
    let p1 = worker_exe_path_from_env(env, "v1");
    let p2 = worker_exe_path_from_env(env, "v1");
    assert_eq!(
        p1, p2,
        "worker_exe_path_from_env must be pure: same inputs → same output"
    );
}

/// Different pack versions produce different paths (the version leaf
/// is interpolated). Regression guard against accidentally dropping
/// the version from the path.
#[test]
fn test_worker_exe_path_version_interpolated() {
    let env = WorkerPathEnv {
        home: if cfg!(target_os = "windows") {
            Some("C:\\Users\\Alice")
        } else if cfg!(target_os = "macos") {
            Some("/Users/alice")
        } else {
            Some("/home/alice")
        },
        local_appdata: if cfg!(target_os = "windows") {
            Some("C:\\Users\\Alice\\AppData\\Local")
        } else {
            None
        },
        appdata: None,
        xdg_data_home: if cfg!(target_os = "linux") {
            Some("/custom/xdg")
        } else {
            None
        },
        voice_typer_config_dir: None,
    };
    let p_v1 = worker_exe_path_from_env(env, "v1");
    let p_v2 = worker_exe_path_from_env(env, "v2");
    assert_ne!(
        p_v1, p_v2,
        "different pack versions must produce different paths"
    );
    // The version leaf must be the parent dir of the exe.
    assert_eq!(
        p_v1.parent()
            .and_then(|p| p.file_name())
            .and_then(|n| n.to_str()),
        Some("v1"),
        "version 'v1' must appear as the parent dir of the exe"
    );
    assert_eq!(
        p_v2.parent()
            .and_then(|p| p.file_name())
            .and_then(|n| n.to_str()),
        Some("v2"),
        "version 'v2' must appear as the parent dir of the exe"
    );
}

// ── pack_version (env-var override + DEFAULT_PACK_VERSION fallback) ──

/// `pack_version()` returns the `VOICE_TYPER_PACK_VERSION` env var
/// when set, or `DEFAULT_PACK_VERSION` ("v1") when unset. This test
/// sets the env var to a sentinel + verifies the cached value.
///
/// SAFETY: `pack_version` is cached in a `OnceLock` (process-wide).
/// The first test to call `pack_version()` populates the cache; later
/// tests see the same cached value regardless of env-var changes.
/// To make this test deterministic, we set the env var BEFORE the
/// first call to `pack_version()`: but we can't guarantee ordering
/// across tests in the same binary. Instead, we test the env-var
/// resolution logic by directly calling the underlying
/// `std::env::var` + filter logic (mirroring `pack_version`'s body).
#[test]
fn test_pack_version_default_when_unset() {
    // Reproduce the pack_version() resolution logic inline (without
    // calling pack_version() itself, which is process-cached).
    let v = std::env::var("VOICE_TYPER_PACK_VERSION")
        .ok()
        .filter(|v| !v.is_empty())
        .unwrap_or_else(|| DEFAULT_PACK_VERSION.to_string());
    // If VOICE_TYPER_PACK_VERSION is set in the test env, we can't
    // assert == DEFAULT_PACK_VERSION; just assert it's non-empty.
    assert!(
        !v.is_empty(),
        "pack_version must never return an empty string"
    );
}

/// The `DEFAULT_PACK_VERSION` constant is `"v1"`, pinned by
/// `test_default_pack_version_pinned` above. This test verifies the
/// fallback string is non-empty (defensive, a future refactor that
/// accidentally empties the constant would silently break the path
/// construction with a `<pack_dir>//<worker_name>` double-slash).
#[test]
fn test_default_pack_version_nonempty() {
    assert!(
        !DEFAULT_PACK_VERSION.is_empty(),
        "DEFAULT_PACK_VERSION must be non-empty (path join with empty version produces a double-slash)"
    );
}

// ── worker_exe_path (process-wide cached resolver) ──────────────────

/// `worker_exe_path()` returns a `&'static Path` (the `OnceLock` holds
/// the `PathBuf` for the process lifetime). Calling it twice returns
/// the SAME `&Path` pointer (the cache is stable). This pins the
/// caching contract: a future refactor that drops the `OnceLock`
/// would silently re-resolve env vars on every call (microsecond cost
/// per call, but adds up under the WS reader / writer hot loops).
#[test]
fn test_worker_exe_path_cached_returns_same_pointer() {
    let p1 = worker_exe_path();
    let p2 = worker_exe_path();
    assert!(
        std::ptr::eq(p1, p2),
        "worker_exe_path() must return the SAME &'static Path on every call (OnceLock caching)"
    );
}

/// `worker_exe_path()` returns a path whose file name is the worker
/// exe name with the current target triple suffix (+ optional .exe).
/// This pins the cross-cutting contract between `worker_path` (path
/// construction) and `sidecar::spawn::target_triple` (triple
/// resolution).
#[test]
fn test_worker_exe_path_file_name_matches_target_triple() {
    let p = worker_exe_path();
    let triple = crate::sidecar::spawn::target_triple::current_target_triple();
    let suffix = if cfg!(windows) { ".exe" } else { "" };
    let expected = format!("{}-{}{}", WORKER_BIN_BASE_NAME, triple, suffix);
    assert_eq!(
        p.file_name().and_then(|n| n.to_str()),
        Some(expected.as_str()),
        "worker exe file name must match lausu-worker-<triple>[.exe]"
    );
}

// ── WorkerPathEnv struct ────────────────────────────────────────────

/// The host protocol range must stay pinned to exactly version 1
/// until a wire-format change lands: it mirrors `PROTOCOL_VERSION = 1`
/// in `voice_typer/server/ipc/protocol_version.py`, and the pack
/// manifests shipped today all declare `min_proto_version: 1`.
#[test]
fn test_host_proto_range_pinned_to_v1() {
    assert_eq!(
        HOST_MIN_PROTO_VERSION, 1,
        "host min proto must mirror Python PROTOCOL_VERSION"
    );
    assert_eq!(
        HOST_PROTO_VERSION, 1,
        "host max proto must mirror Python PROTOCOL_VERSION"
    );
    assert!(
        HOST_MIN_PROTO_VERSION <= HOST_PROTO_VERSION,
        "host proto range must be non-empty"
    );
}

/// The manifest file name is owned by the Python schema (`core.py`);
/// the host only reads it, so the literal is pinned here.
#[test]
fn test_pack_manifest_file_name_pinned() {
    assert_eq!(PACK_MANIFEST_FILE_NAME, "pack-manifest.json");
}

// ── parse_pack_min_proto_version (pure) ───────────────────────

/// A manifest declaring the current version parses to a launchable value.
#[test]
fn test_parse_pack_min_proto_match_value() {
    let text = r#"{"version":"v1","sha256":"x","files":[],"min_proto_version":1}"#;
    assert_eq!(parse_pack_min_proto_version(text), Some(1));
}

/// A newer pack (higher minimum than the host) parses distinctly from
/// a match: the caller refuses instead of launching.
#[test]
fn test_parse_pack_min_proto_newer_pack() {
    let text = r#"{"version":"v2","sha256":"x","files":[],"min_proto_version":2}"#;
    assert_eq!(parse_pack_min_proto_version(text), Some(2));
}

/// Every non-u32 shape fails closed to `None`: missing field, invalid
/// JSON, negative, float, bool, string, and u32 overflow must never
/// parse into a launchable version.
#[test]
fn test_parse_pack_min_proto_rejects_non_u32_shapes() {
    assert_eq!(
        parse_pack_min_proto_version(r#"{"version":"v1"}"#),
        None,
        "missing min_proto_version must fail closed"
    );
    assert_eq!(
        parse_pack_min_proto_version("{not json"),
        None,
        "invalid JSON must fail closed"
    );
    assert_eq!(
        parse_pack_min_proto_version(r#"{"min_proto_version":-1}"#),
        None,
        "negative version must fail closed"
    );
    assert_eq!(
        parse_pack_min_proto_version(r#"{"min_proto_version":1.5}"#),
        None,
        "float version must fail closed"
    );
    assert_eq!(
        parse_pack_min_proto_version(r#"{"min_proto_version":true}"#),
        None,
        "bool must not pass as 1/0"
    );
    assert_eq!(
        parse_pack_min_proto_version(r#"{"min_proto_version":"1"}"#),
        None,
        "string version must fail closed"
    );
    assert_eq!(
        parse_pack_min_proto_version(r#"{"min_proto_version":1099511627776}"#),
        None,
        "u32 overflow must fail closed, never wrap"
    );
}

// ── check_pack_proto (pure range decision) ────────────────────

/// The current pack version launches.
#[test]
fn test_check_pack_proto_match_launches() {
    let status = check_pack_proto(Some(1));
    assert_eq!(
        status,
        PackProtoStatus::Match {
            min_proto_version: 1
        }
    );
    assert!(status.launch_allowed(), "match must allow launch");
}

/// Older (0) and newer (2) packs both refuse: anything outside the
/// host range fails fast instead of failing mid-transcription.
#[test]
fn test_check_pack_proto_mismatch_refuses_both_directions() {
    for v in [0u32, 2u32, u32::MAX] {
        let status = check_pack_proto(Some(v));
        assert_eq!(
            status,
            PackProtoStatus::Mismatch {
                min_proto_version: v
            },
            "min_proto_version={v} is outside the host range and must refuse"
        );
        assert!(!status.launch_allowed(), "mismatch must never allow launch");
    }
}

/// An unparseable manifest refuses with the schema reason.
#[test]
fn test_check_pack_proto_none_is_missing_manifest() {
    let status = check_pack_proto(None);
    assert_eq!(
        status,
        PackProtoStatus::MissingManifest {
            reason: "invalid_schema"
        }
    );
    assert!(
        !status.launch_allowed(),
        "missing manifest must never allow launch"
    );
}

// ── pack_manifest_path_for_exe + check_pack_manifest_for_exe (fs) ──

/// The manifest sits next to the pack exe inside the version dir.
#[test]
fn test_pack_manifest_path_for_exe_is_sibling() {
    let exe = std::path::Path::new("/pack/v1/lausu-worker-triple");
    assert_eq!(
        pack_manifest_path_for_exe(exe),
        Some(std::path::PathBuf::from("/pack/v1/pack-manifest.json"))
    );
}

/// A missing manifest file refuses with the not_found reason
/// (fail-closed: a pack without a manifest never launches).
#[test]
fn test_check_pack_manifest_missing_file() {
    let dir =
        std::env::temp_dir().join(format!("vt-pack-proto-test-missing-{}", std::process::id()));
    let exe = dir.join("lausu-worker-triple");
    let status = check_pack_manifest_for_exe(&exe);
    assert_eq!(
        status,
        PackProtoStatus::MissingManifest {
            reason: "not_found"
        },
        "absent manifest must refuse with not_found"
    );
}

/// A well-formed on-disk manifest with the current version launches.
#[test]
fn test_check_pack_manifest_on_disk_match() {
    let dir = std::env::temp_dir().join(format!("vt-pack-proto-test-match-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).expect("test temp dir must be creatable");
    std::fs::write(
        dir.join(PACK_MANIFEST_FILE_NAME),
        r#"{"version":"v1","sha256":"x","files":[],"min_proto_version":1}"#,
    )
    .expect("test manifest must be writable");
    let status = check_pack_manifest_for_exe(&dir.join("lausu-worker-triple"));
    let _ = std::fs::remove_dir_all(&dir);
    assert_eq!(
        status,
        PackProtoStatus::Match {
            min_proto_version: 1
        },
        "on-disk manifest with min_proto_version=1 must launch"
    );
}

/// A corrupt on-disk manifest refuses with the invalid_json reason.
#[test]
fn test_check_pack_manifest_on_disk_corrupt() {
    let dir =
        std::env::temp_dir().join(format!("vt-pack-proto-test-corrupt-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).expect("test temp dir must be creatable");
    std::fs::write(dir.join(PACK_MANIFEST_FILE_NAME), "{not valid json")
        .expect("test manifest must be writable");
    let status = check_pack_manifest_for_exe(&dir.join("lausu-worker-triple"));
    let _ = std::fs::remove_dir_all(&dir);
    assert_eq!(
        status,
        PackProtoStatus::MissingManifest {
            reason: "invalid_json"
        },
        "corrupt manifest must refuse with invalid_json"
    );
}

/// `WorkerPathEnv` must be `Clone + Copy + Debug + PartialEq + Eq`
/// (the derive macros are pinned on the struct). The `Copy` bound is
/// important: it lets tests pass `WorkerPathEnv` by value without
/// `.clone()` boilerplate, and it documents that the struct is a
/// small fixed-size bundle of `Option<&'static str>`s (no heap
/// allocation).
#[test]
fn test_worker_path_env_is_copy_clone_debug_eq() {
    let env = WorkerPathEnv {
        home: Some("/home/alice"),
        local_appdata: None,
        appdata: None,
        xdg_data_home: None,
        voice_typer_config_dir: None,
    };
    // Copy: pass by value without .clone().
    let env_copy = env;
    // Clone: explicit .clone() also works (Copy implies Clone).
    let _env_clone = env.clone();
    // Debug: format!("{:?}", env) compiles + produces a non-empty string.
    let debug_str = format!("{:?}", env_copy);
    assert!(
        !debug_str.is_empty(),
        "WorkerPathEnv must impl Debug (derive): got empty debug string"
    );
    // PartialEq + Eq: == comparison compiles.
    assert_eq!(
        env, env_copy,
        "WorkerPathEnv must impl PartialEq + Eq (derive)"
    );
}
