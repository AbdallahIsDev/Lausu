use std::sync::{Arc, Mutex};

use gpui::{Context, IntoElement, Render, SharedString, Window, div, prelude::*, px, rgb};

use crate::state::{OverlayState, label};

pub struct BubbleView {
    state: Arc<Mutex<OverlayState>>,
}

impl BubbleView {
    pub fn new(state: Arc<Mutex<OverlayState>>) -> Self {
        Self { state }
    }
}

impl Render for BubbleView {
    fn render(&mut self, _window: &mut Window, _cx: &mut Context<Self>) -> impl IntoElement {
        let state = self.state.lock().unwrap();
        let text = SharedString::from(label(&state));
        let level = state.rms.clamp(0.0, 1.0);

        div()
            .size_full()
            .flex()
            .items_center()
            .justify_center()
            .child(
                div()
                    .flex()
                    .items_center()
                    .gap_2()
                    .rounded_full()
                    .border_1()
                    .border_color(rgb(0x303030))
                    .bg(rgb(0x1f1f1f))
                    .px_4()
                    .py_2()
                    .child(
                        div()
                            .w(px(8.0 + 6.0 * level as f32))
                            .h(px(8.0))
                            .rounded_full()
                            .bg(gpui::red()),
                    )
                    .child(div().text_color(rgb(0xf5f5f5)).text_xs().child(text)),
            )
    }
}
