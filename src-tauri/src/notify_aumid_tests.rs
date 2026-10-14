//! Read-before-write gate for the AUMID registry values: the steady-state
//! launch must skip the write (and its INFO log) when already correct.

use super::registration_current;

#[test]
fn test_matching_values_are_current() {
    assert!(registration_current(
        Some("Lausu"),
        Some("C:\\cfg\\toast-icon.ico"),
        "Lausu",
        "C:\\cfg\\toast-icon.ico"
    ));
}

#[test]
fn test_display_name_mismatch_needs_write() {
    assert!(!registration_current(
        Some("OldName"),
        Some("C:\\cfg\\toast-icon.ico"),
        "Lausu",
        "C:\\cfg\\toast-icon.ico"
    ));
}

#[test]
fn test_icon_path_mismatch_needs_write() {
    assert!(!registration_current(
        Some("Lausu"),
        Some("C:\\other\\toast-icon.ico"),
        "Lausu",
        "C:\\cfg\\toast-icon.ico"
    ));
}

#[test]
fn test_missing_values_need_write() {
    assert!(!registration_current(
        None,
        None,
        "Lausu",
        "C:\\cfg\\toast-icon.ico"
    ));
    assert!(!registration_current(
        Some("Lausu"),
        None,
        "Lausu",
        "C:\\cfg\\toast-icon.ico"
    ));
    assert!(!registration_current(
        None,
        Some("C:\\cfg\\toast-icon.ico"),
        "Lausu",
        "C:\\cfg\\toast-icon.ico"
    ));
}

#[test]
fn test_empty_strings_never_match_real_values() {
    assert!(!registration_current(
        Some(""),
        Some(""),
        "Lausu",
        "C:\\cfg\\toast-icon.ico"
    ));
}
