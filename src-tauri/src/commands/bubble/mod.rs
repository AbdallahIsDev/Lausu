//! Bubble window commands ( + ADR-0020 §9).
//!
//! The 9 `#[tauri::command]` functions exposed to the renderer live
//! in [`commands`]. Pure helpers are split by concern: position
//! parsing in [`parse`], geometry math in [`math`], the toggle
//! rate limiter in [`rate_limit`], and the shared bubble-hide helper
//! in [`window`]. Unit tests live in [`tests`]. Bubble drags are
//! session-local by product decision (no position persistence).
//!
//! [`commands`]: commands
//! [`parse`]: parse
//! [`math`]: math
//! [`rate_limit`]: rate_limit
//! [`window`]: window
//! [`tests`]: tests

mod commands;
mod math;
mod parse;
mod rate_limit;
mod window;

// The global bubble-dismiss shortcut reuses the exact hide
// body the bubble's '×' button uses, so the keyboard path can never
// drift from the click path (E7).
pub(crate) use window::{
    hide_bubble_window, is_active_bubble_state, show_bubble_window, wants_bubble_show,
};

pub(crate) use commands::{
    bubble_dismiss, bubble_hide_complete, bubble_move_by, bubble_resize, bubble_set_draggable,
    bubble_set_position, bubble_show, bubble_signal_ready, bubble_toggle_dictation,
};

#[cfg(test)]
mod tests;
