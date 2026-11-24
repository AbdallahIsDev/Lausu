mod protocol;
mod state;
mod view;

use std::io::{BufRead, stdin};
use std::sync::{Arc, Mutex};

use gpui::{App, AppContext, Bounds, WindowBounds, WindowOptions, px, size};

use crate::protocol::{
    EventEnvelope, hide_complete_command, ready_command, resize_command,
    toggle_dictation_command,
};
use crate::state::{OverlayState, apply_event};
use crate::view::BubbleView;

fn demo_events(state: &Arc<Mutex<OverlayState>>) {
    let lines = [
        r#"{"type":"bubble_config","data":{"bubble_behavior":"show_on_record","bubble_position":"bottom","bubble_mic_button":true}}"#,
        r#"{"type":"bubble_show","data":{}}"#,
        r#"{"type":"bubble_set_state","data":{"state":"recording"}}"#,
        r#"{"type":"bubble_level","data":{"rms":0.4,"peak":0.8}}"#,
        r#"{"type":"bubble_set_state","data":{"state":"transcribing"}}"#,
    ];
    for line in lines {
        if let Ok(event) = serde_json::from_str::<EventEnvelope>(line) {
            let mut guard = state.lock().unwrap();
            apply_event(&mut guard, &event);
        }
    }
}

fn main() {
    let state = Arc::new(Mutex::new(OverlayState::default()));

    let demo = std::env::args().any(|arg| arg == "--demo");
    if demo {
        demo_events(&state);
    } else {
        for line in stdin().lock().lines() {
            let Ok(line) = line else { break };
            if line.trim().is_empty() {
                continue;
            }
            match serde_json::from_str::<EventEnvelope>(&line) {
                Ok(event) => {
                    let mut guard = state.lock().unwrap();
                    apply_event(&mut guard, &event);
                }
                Err(err) => eprintln!("[overlay-gpui] bad JSON line: {err}"),
            }
        }
    }

    println!("{}", serde_json::to_string(&ready_command()).unwrap());
    if demo {
        for command in [
            resize_command(240, 80),
            hide_complete_command(),
            toggle_dictation_command(),
        ] {
            println!("{}", serde_json::to_string(&command).unwrap());
        }
    }

    gpui_platform::application().run(move |cx: &mut App| {
        let bounds = Bounds::centered(None, size(px(240.0), px(80.0)), cx);
        cx.open_window(
            WindowOptions::new()
                .window_bounds(WindowBounds::Windowed(bounds))
                .focus(false),
            |_window, cx| cx.new(|_| BubbleView::new(Arc::clone(&state))),
        )
        .unwrap();
    });
}
