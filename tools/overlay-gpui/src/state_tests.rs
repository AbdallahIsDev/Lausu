use super::*;

fn event(event_type: &str, data: serde_json::Value) -> EventEnvelope {
    EventEnvelope {
        event_type: event_type.into(),
        data,
    }
}

#[test]
fn hint_states_keep_transcribing_mode() {
    assert_eq!(
        mode_from_push("still_transcribing"),
        Some(BubbleMode::Transcribing)
    );
    assert_eq!(
        mode_from_push("cloud_cancel_requested"),
        Some(BubbleMode::Transcribing)
    );
}

#[test]
fn event_stream_drives_visible_state() {
    let mut state = OverlayState::default();
    apply_event(&mut state, &event("bubble_show", serde_json::json!({})));
    apply_event(
        &mut state,
        &event(
            "bubble_set_state",
            serde_json::json!({"state": "recording"}),
        ),
    );
    apply_event(
        &mut state,
        &event(
            "bubble_level",
            serde_json::json!({"rms": 0.3, "peak": 0.9}),
        ),
    );
    assert!(state.visible);
    assert_eq!(state.mode, BubbleMode::Recording);
    assert_eq!(label(&state), "Recording");
    assert_eq!(state.rms, 0.3);
}
