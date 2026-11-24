use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize)]
pub struct EventEnvelope {
    #[serde(rename = "type")]
    pub event_type: String,
    #[serde(default)]
    pub data: serde_json::Value,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct BubbleConfigData {
    pub bubble_position: Option<String>,
    pub bubble_behavior: Option<String>,
    pub bubble_click_to_toggle: Option<bool>,
    pub bubble_mic_button: Option<bool>,
    pub bubble_show_recording_timer: Option<bool>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct BubbleStateData {
    pub state: String,
    #[serde(default)]
    pub message: Option<String>,
    #[serde(default)]
    pub transcript: Option<String>,
    #[serde(rename = "live_preview_supported", default)]
    pub live_preview_supported: Option<bool>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct BubbleLevelData {
    pub rms: f64,
    pub peak: f64,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct HostCommand {
    pub cmd: String,
    pub data: serde_json::Value,
}

pub fn ready_command() -> HostCommand {
    HostCommand {
        cmd: "bubble_signal_ready".into(),
        data: serde_json::Value::Null,
    }
}

pub fn resize_command(width: u32, height: u32) -> HostCommand {
    HostCommand {
        cmd: "bubble_resize".into(),
        data: serde_json::json!({ "width": width, "height": height }),
    }
}

pub fn hide_complete_command() -> HostCommand {
    HostCommand {
        cmd: "bubble_hide_complete".into(),
        data: serde_json::Value::Null,
    }
}

pub fn toggle_dictation_command() -> HostCommand {
    HostCommand {
        cmd: "bubble_toggle_dictation".into(),
        data: serde_json::Value::Null,
    }
}

#[cfg(test)]
#[path = "protocol_tests.rs"]
mod protocol_tests;
