//! Read-before-write gate for the AUMID registry values: the steady-state
//! launch must skip the write (and its INFO log) when already correct.
//!
//! C-BRAND-1: the expected display name comes from `crate::branding::APP_NAME`,
//! never a literal, so a rename cannot leave these assertions pinning the old
//! product name.

use super::registration_current;
use crate::branding::APP_NAME;

#[test]
fn test_matching_values_are_current() {
    assert!(registration_current(
        Some(APP_NAME),
        Some("C:\\cfg\\toast-icon.ico"),
        APP_NAME,
        "C:\\cfg\\toast-icon.ico"
    ));
}

#[test]
fn test_display_name_mismatch_needs_write() {
    assert!(!registration_current(
        Some("OldName"),
        Some("C:\\cfg\\toast-icon.ico"),
        APP_NAME,
        "C:\\cfg\\toast-icon.ico"
    ));
}

#[test]
fn test_icon_path_mismatch_needs_write() {
    assert!(!registration_current(
        Some(APP_NAME),
        Some("C:\\other\\toast-icon.ico"),
        APP_NAME,
        "C:\\cfg\\toast-icon.ico"
    ));
}

#[test]
fn test_missing_values_need_write() {
    assert!(!registration_current(
        None,
        None,
        APP_NAME,
        "C:\\cfg\\toast-icon.ico"
    ));
    assert!(!registration_current(
        Some(APP_NAME),
        None,
        APP_NAME,
        "C:\\cfg\\toast-icon.ico"
    ));
    assert!(!registration_current(
        None,
        Some("C:\\cfg\\toast-icon.ico"),
        APP_NAME,
        "C:\\cfg\\toast-icon.ico"
    ));
}

#[test]
fn test_empty_strings_never_match_real_values() {
    assert!(!registration_current(
        Some(""),
        Some(""),
        APP_NAME,
        "C:\\cfg\\toast-icon.ico"
    ));
}
