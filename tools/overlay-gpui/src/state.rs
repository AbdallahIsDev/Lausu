use crate::protocol::{BubbleConfigData, BubbleLevelData, BubbleStateData, EventEnvelope};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BubbleMode {
    Recording,
    Transcribing,
    Loading,
    Idle,
    Error,
    Blocked,
    Cancelling,
    PermissionRevoked,
    PasteFailed,
}

impl Default for BubbleMode {
    fn default() -> Self {
        Self::Idle
    }
}

#[derive(Debug, Clone, Default)]
pub struct OverlayState {
    pub visible: bool,
    pub mode: BubbleMode,
    pub message: Option<String>,
    pub transcript: Option<String>,
    pub rms: f64,
    pub peak: f64,
    pub behavior: String,
    pub position: String,
    pub mic_button: bool,
    pub click_to_toggle: bool,
    pub show_timer: bool,
    pub live_preview_supported: bool,
}

pub fn mode_from_push(push: &str) -> Option<BubbleMode> {
    match push {
        "recording" => Some(BubbleMode::Recording),
        "transcribing" | "still_transcribing" | "cloud_cancel_requested" => {
            Some(BubbleMode::Transcribing)
        }
        "loading" => Some(BubbleMode::Loading),
        "idle" => Some(BubbleMode::Idle),
        "error" => Some(BubbleMode::Error),
        "blocked" => Some(BubbleMode::Blocked),
        "cancelling" => Some(BubbleMode::Cancelling),
        "permission_revoked" => Some(BubbleMode::PermissionRevoked),
        "paste_failed" => Some(BubbleMode::PasteFailed),
        _ => None,
    }
}

pub fn label(state: &OverlayState) -> &'static str {
    match state.mode {
        BubbleMode::Recording => "Recording",
        BubbleMode::Transcribing => "Transcribing…",
        BubbleMode::Loading => "Loading model…",
        BubbleMode::Idle => "Ready",
        BubbleMode::Error => "Error",
        BubbleMode::Blocked => "Blocked",
        BubbleMode::Cancelling => "Cancelling…",
        BubbleMode::PermissionRevoked => "Mic permission revoked",
        BubbleMode::PasteFailed => "Paste failed",
    }
}

pub fn apply_event(state: &mut OverlayState, event: &EventEnvelope) {
    match event.event_type.as_str() {
        "bubble_show" => state.visible = true,
        "bubble_hide" => state.visible = false,
        "bubble_config" => {
            if let Ok(cfg) = serde_json::from_value::<BubbleConfigData>(event.data.clone()) {
                if let Some(behavior) = cfg.bubble_behavior {
                    state.behavior = behavior;
                }
                if let Some(position) = cfg.bubble_position {
                    state.position = position;
                }
                if let Some(mic_button) = cfg.bubble_mic_button {
                    state.mic_button = mic_button;
                }
                if let Some(click_to_toggle) = cfg.bubble_click_to_toggle {
                    state.click_to_toggle = click_to_toggle;
                }
                state.show_timer = cfg.bubble_show_recording_timer.unwrap_or(false);
            }
        }
        "bubble_set_state" => {
            if let Ok(push) = serde_json::from_value::<BubbleStateData>(event.data.clone()) {
                if let Some(mode) = mode_from_push(&push.state) {
                    state.mode = mode;
                }
                state.message = push.message;
                state.transcript = push.transcript;
                state.live_preview_supported = push.live_preview_supported.unwrap_or(false);
            }
        }
        "bubble_level" => {
            if let Ok(level) = serde_json::from_value::<BubbleLevelData>(event.data.clone()) {
                state.rms = level.rms;
                state.peak = level.peak;
            }
        }
        _ => {}
    }
}

#[cfg(test)]
#[path = "state_tests.rs"]
mod state_tests;
