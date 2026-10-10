//! Tests for `host_events.rs`: pure payload-parsing contracts (per
//! C-TEST-5, sibling test file; no Tauri runtime required).

use super::{navigate_payload, parse_notification, tap_action_for, TapAction};

#[test]
fn test_parses_title_and_message() {
    let raw = r#"{"title":"Model loaded","message":"Whisper small.en ready"}"#;
    let parsed = parse_notification(raw);
    let p = parsed.expect("payload should parse");
    assert_eq!(p.title, "Model loaded");
    assert_eq!(p.message, "Whisper small.en ready");
    // Click-routing fields default OFF.
    assert_eq!(p.click_path, None);
    assert_eq!(p.click_consent_field, None);
    assert_eq!(p.duration_ms, 0);
}

#[test]
fn test_click_routing_fields_are_parsed() {
    let raw =
        r#"{"title":"T","message":"M","duration_ms":5000,"critical":true,"click_path":"/models"}"#;
    let p = parse_notification(raw).expect("payload should parse");
    assert_eq!(p.click_path.as_deref(), Some("/models"));
    assert_eq!(p.click_consent_field, None);
    assert_eq!(p.duration_ms, 5000);
    assert_eq!(p.title, "T");
    assert_eq!(p.message, "M");
}

#[test]
fn test_consent_field_deep_link_is_parsed() {
    let raw = r#"{"title":"Consent","message":"Voice biometrics is off","click_consent_field":"voice_biometrics"}"#;
    let p = parse_notification(raw).expect("payload should parse");
    assert_eq!(p.click_consent_field.as_deref(), Some("voice_biometrics"));
    assert_eq!(p.click_path, None);
}

#[test]
fn test_missing_message_defaults_empty() {
    let raw = r#"{"title":"Only title"}"#;
    let p = parse_notification(raw).expect("payload should parse");
    assert_eq!(p.title, "Only title");
    assert_eq!(p.message, "");
}

#[test]
fn test_both_fields_empty_is_rejected() {
    let raw = r#"{"title":"","message":""}"#;
    assert!(parse_notification(raw).is_none());
}

#[test]
fn test_malformed_json_is_rejected() {
    assert!(parse_notification("not json").is_none());
    assert!(parse_notification("[1,2,3]").is_none());
    assert!(parse_notification("").is_none());
}

#[test]
fn test_navigate_payload_plain_path() {
    let raw = r#"{"title":"T","message":"M","click_path":"/models"}"#;
    let p = parse_notification(raw).expect("payload should parse");
    let nav = navigate_payload(&p);
    assert_eq!(nav["path"], "/models");
    assert!(nav.get("consent_field").is_none());
}

#[test]
fn test_navigate_payload_consent_field_overrides_path() {
    let raw = r#"{"title":"T","message":"M","click_path":"/settings","click_consent_field":"cloud_api_key"}"#;
    let p = parse_notification(raw).expect("payload should parse");
    let nav = navigate_payload(&p);
    assert_eq!(nav["path"], "/settings");
    assert_eq!(nav["consent_field"], "cloud_api_key");
}

#[test]
fn test_navigate_payload_no_routing_defaults_empty_path() {
    let raw = r#"{"title":"T","message":"M"}"#;
    let p = parse_notification(raw).expect("payload should parse");
    let nav = navigate_payload(&p);
    assert_eq!(nav["path"], "");
}

#[test]
fn test_tap_action_mic_settings_for_microphone_path() {
    // The mic-permission refusal toast must open the OS mic privacy page
    // on tap (parity with the in-app toast's open_mic_settings button),
    // not navigate inside the app.
    let raw = r#"{"title":"T","message":"M","click_path":"/microphone"}"#;
    let p = parse_notification(raw).expect("payload should parse");
    assert!(matches!(
        tap_action_for(&p),
        Some(TapAction::OpenMicSettings)
    ));
}

#[test]
fn test_tap_action_navigates_for_other_paths() {
    let raw = r#"{"title":"T","message":"M","click_path":"/models"}"#;
    let p = parse_notification(raw).expect("payload should parse");
    match tap_action_for(&p) {
        Some(TapAction::Navigate(nav)) => assert_eq!(nav["path"], "/models"),
        other => panic!("expected Navigate, got {other:?}"),
    }
}

#[test]
fn test_tap_action_consent_field_wins_over_microphone_path() {
    // A consent deep-link keeps the in-app navigation semantics even if
    // the path happens to be /microphone.
    let raw = r#"{"title":"T","message":"M","click_path":"/microphone","click_consent_field":"voice_biometric_consent"}"#;
    let p = parse_notification(raw).expect("payload should parse");
    match tap_action_for(&p) {
        Some(TapAction::Navigate(nav)) => {
            assert_eq!(nav["path"], "/settings");
            assert_eq!(nav["consent_field"], "voice_biometric_consent");
        }
        other => panic!("expected Navigate, got {other:?}"),
    }
}

#[test]
fn test_tap_action_none_without_click_fields() {
    let raw = r#"{"title":"T","message":"M"}"#;
    let p = parse_notification(raw).expect("payload should parse");
    assert!(tap_action_for(&p).is_none());
}
