//! Unit tests for `system_cmds::dialogs` (C-TEST-5 sibling file).
//!
//! Pins the `open_logs` target-directory contract: the command must
//! open `<config_dir>/logs/`: the exact directory
//! `platform::logging::init::init_file_logger` creates and rotates
//! `lausu-rust.log` in: NOT the config-dir root. The command
//! wrapper itself needs a live `tauri::Window` (which cannot be
//! constructed in unit tests) and an OS file-manager spawn, so the
//! assertable seam is the pure [`logs_dir_path`] helper, the same
//! pure-seam approach `platform::open_path` tests use with
//! `preflight_path_exists`.

use super::{logs_dir_path, media_dialog_filters};
use std::collections::HashSet;
use std::path::{Path, PathBuf};

#[test]
fn test_logs_dir_path_appends_logs_leaf_to_config_dir() {
    // The three platform-canonical config-dir shapes from
    // `platform::paths::config_dir_from_env` (Windows / macOS / Linux)
    // plus the legacy `~/.lausu` and the
    // VOICE_TYPER_CONFIG_DIR override: the helper must append the
    // `logs` leaf to whatever root it is given, unconditionally.
    let roots: [PathBuf; 5] = [
        // Windows: %APPDATA%/lausu
        PathBuf::from(r"C:\Users\alice\AppData\Roaming\lausu"),
        // macOS: ~/Library/Application Support/lausu
        PathBuf::from("/Users/alice/Library/Application Support/lausu"),
        // Linux: $XDG_DATA_HOME/lausu (default ~/.local/share/lausu)
        PathBuf::from("/home/alice/.local/share/lausu"),
        // Legacy predecessor dir (still resolved when it exists)
        PathBuf::from("/home/alice/.lausu"),
        // VOICE_TYPER_CONFIG_DIR override
        PathBuf::from("/home/alice/custom-config"),
    ];
    for root in roots {
        let target = logs_dir_path(&root);
        assert_eq!(
            target,
            root.join("logs"),
            "open_logs target must be <config_dir>/logs"
        );
    }
}

#[test]
fn test_logs_dir_path_ends_with_logs_directory() {
    // The path handed to the OS file-manager opener must END with the
    // logs directory: this is the regression pin for the bug where
    // the command opened the config-dir ROOT instead of the logs
    // subdir (while the logger itself wrote into <config_dir>/logs,
    // so the user landed in a folder whose log files were one level
    // deeper).
    let target = logs_dir_path(Path::new("/home/alice/.local/share/lausu"));
    assert!(
        target.ends_with("logs"),
        "open_logs target must end with the logs directory, got {}",
        target.display()
    );
    // And it must NOT be the config-dir root itself.
    assert_ne!(
        target,
        PathBuf::from("/home/alice/.local/share/lausu"),
        "open_logs must not open the config-dir root"
    );
}

#[test]
fn test_logs_dir_path_matches_logging_init_layout() {
    // Byte-parity with `platform::logging::init::init_file_logger`,
    // which computes its own logs dir as
    // `config_dir.join("logs")` (init.rs) and writes
    // `lausu-rust.log` inside it. If either side changes the
    // leaf name, Open Logs would stop landing on the directory the
    // host actually writes logs into.
    let config_dir = Path::new("/home/alice/.local/share/lausu");
    let logging_init_dir = config_dir.join("logs");
    assert_eq!(
        logs_dir_path(config_dir),
        logging_init_dir,
        "open_logs target must match the logging init layout (<config_dir>/logs)"
    );
}

// ---------------------------------------------------------------------------
// Media picker filters (C-UI-13): the combined filter must come FIRST, it
// must cover both per-type lists, and an all-files escape hatch must exist.
//
// The regression these pin: the picker registered "Audio" first, so the
// native dialog pre-selected it and every video file in the folder was
// invisible until the user switched filters by hand.
// ---------------------------------------------------------------------------

#[test]
fn test_media_dialog_filters_combined_filter_comes_first() {
    let filters = media_dialog_filters();
    assert!(
        !filters.is_empty(),
        "the media picker must register at least one filter"
    );
    assert_eq!(
        filters[0].0, "Audio and video",
        "the FIRST filter is the one the native dialog pre-selects; it must be \
         the combined one or the picker opens hiding half the supported files"
    );
}

#[test]
fn test_media_dialog_filters_combined_covers_both_per_type_lists() {
    let filters = media_dialog_filters();
    let audio: HashSet<&str> = filters
        .iter()
        .find(|(label, _)| *label == "Audio")
        .expect("an Audio filter must exist")
        .1
        .iter()
        .copied()
        .collect();
    let video: HashSet<&str> = filters
        .iter()
        .find(|(label, _)| *label == "Video")
        .expect("a Video filter must exist")
        .1
        .iter()
        .copied()
        .collect();
    let combined: HashSet<&str> = filters[0].1.iter().copied().collect();

    assert!(
        combined.is_superset(&audio),
        "combined filter is missing audio extensions: {:?}",
        audio.difference(&combined).collect::<Vec<_>>()
    );
    assert!(
        combined.is_superset(&video),
        "combined filter is missing video extensions: {:?}",
        video.difference(&combined).collect::<Vec<_>>()
    );
}

#[test]
fn test_media_dialog_filters_every_per_type_extension_is_selectable_by_default() {
    let filters = media_dialog_filters();
    let combined: HashSet<&str> = filters[0].1.iter().copied().collect();
    for (label, extensions) in filters.iter().filter(|(l, _)| *l != "All files") {
        for ext in extensions {
            assert!(
                combined.contains(ext),
                "{ext} is offered under {label} but missing from the default \
                 (first) filter, so it is unreachable without switching filters"
            );
        }
    }
}

#[test]
fn test_media_dialog_filters_ends_with_all_files() {
    let filters = media_dialog_filters();
    let (label, extensions) = filters.last().expect("at least one filter");
    assert_eq!(
        *label, "All files",
        "the last filter must be the all-files one"
    );
    assert_eq!(extensions, &vec!["*"], "the all-files filter must be `*`");
}

#[test]
fn test_media_dialog_filters_has_no_duplicate_extensions_in_combined() {
    let filters = media_dialog_filters();
    let combined = &filters[0].1;
    let unique: HashSet<&str> = combined.iter().copied().collect();
    assert_eq!(
        unique.len(),
        combined.len(),
        "the combined filter repeats an extension: {combined:?}"
    );
}

#[test]
fn test_media_dialog_filters_cover_the_common_formats() {
    let filters = media_dialog_filters();
    let combined: HashSet<&str> = filters[0].1.iter().copied().collect();
    // The pair the owner actually uses for testing, plus the formats the
    // old lists forgot (aif/ac3/caf/mka/oga/spx, m2ts/mts/wmv/flv/ogv).
    for ext in [
        "mp3", "mp4", "wav", "m4a", "mkv", "webm", "mov", "aif", "m2ts",
    ] {
        assert!(
            combined.contains(ext),
            "{ext} must be selectable by default"
        );
    }
}
