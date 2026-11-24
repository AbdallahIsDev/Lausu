use super::*;

#[test]
fn parses_existing_event_envelope() {
    let line = r#"{"type":"bubble_set_state","data":{"state":"recording"}}"#;
    let event: EventEnvelope = serde_json::from_str(line).unwrap();
    assert_eq!(event.event_type, "bubble_set_state");
    let state: BubbleStateData = serde_json::from_value(event.data).unwrap();
    assert_eq!(state.state, "recording");
}

#[test]
fn emits_existing_command_names() {
    assert_eq!(ready_command().cmd, "bubble_signal_ready");
    assert_eq!(resize_command(10, 20).cmd, "bubble_resize");
    assert_eq!(resize_command(10, 20).data["width"], 10);
    assert_eq!(hide_complete_command().cmd, "bubble_hide_complete");
    assert_eq!(toggle_dictation_command().cmd, "bubble_toggle_dictation");
}
