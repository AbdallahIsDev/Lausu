import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Bubble } from "@/Bubble";

// ── Mock window.bubble API ──────────────────────────────────────────
// Bubble.tsx uses window.bubble.onLevel, onShow, onHide, onSetState etc.
// We provide stubs so the component mounts without crashing.

function makeMockBubble() {
	const listeners: {
		show: Array<() => void>;
		hide: Array<() => void>;
		setState: Array<(state: string) => void>;
		config?: (cfg: Record<string, unknown>) => void;
	} = { show: [], hide: [], setState: [] };
	return {
		onLevel: vi.fn(() => vi.fn()),
		onShow: vi.fn((cb: () => void) => {
			listeners.show.push(cb);
			return () => {
				listeners.show = listeners.show.filter((l) => l !== cb);
			};
		}),
		onHide: vi.fn((cb: () => void) => {
			listeners.hide.push(cb);
			return () => {
				listeners.hide = listeners.hide.filter((l) => l !== cb);
			};
		}),
		onSetState: vi.fn((cb: (state: string) => void) => {
			listeners.setState.push(cb);
			return () => {
				listeners.setState = listeners.setState.filter((l) => l !== cb);
			};
		}),
		onDraggable: vi.fn(() => vi.fn()),
		signalReady: vi.fn(),
		hideComplete: vi.fn(),
		resizeTo: vi.fn(),
		moveBy: vi.fn(),
		//bubble config + mic-button toggle (sandboxed renderer).
		onConfig: vi.fn((cb: (cfg: Record<string, unknown>) => void) => {
			listeners.config = cb;
			return () => {
				listeners.config = undefined;
			};
		}),
		toggleDictation: vi.fn(),
		//dismiss IPC send (sandboxed renderer).
		dismiss: vi.fn(),
		_listeners: listeners,
	};
}

//helper to push bubble config (simulates the backend's
// bubble:config event). The Bubble subscribes via onConfig and shows
// the mic button only when always_visible + both toggles are on.
function pushBubbleConfig(cfg: Record<string, unknown>) {
	const cb = (
		mockBubble as unknown as {
			_listeners: { config?: (c: Record<string, unknown>) => void };
		}
	)._listeners.config;
	if (cb)
		act(() => {
			cb(cfg);
		});
}

let mockBubble: ReturnType<typeof makeMockBubble>;

beforeEach(() => {
	mockBubble = makeMockBubble();
	(window as unknown as Record<string, unknown>).bubble = mockBubble;

	// Stub window.matchMedia for jsdom (used by useThemeSync in Bubble.tsx)
	Object.defineProperty(window, "matchMedia", {
		value: vi.fn().mockImplementation((query: string) => ({
			matches: false,
			media: query,
			onchange: null,
			addListener: vi.fn(),
			removeListener: vi.fn(),
			addEventListener: vi.fn(),
			removeEventListener: vi.fn(),
			dispatchEvent: vi.fn(),
		})),
		writable: true,
	});
});

afterEach(() => {
	cleanup();
	delete (window as unknown as Record<string, unknown>).bubble;
});

// ── Helpers ─────────────────────────────────────────────────────────

/** Trigger an onSetState callback with the given state, wrapped in act(). */
function setBubbleState(state: string) {
	const cbs = mockBubble._listeners.setState ?? [];
	act(() => {
		for (const cb of cbs) {
			(cb as (s: string) => void)(state);
		}
	});
}

/** Trigger an onShow/onHide callback, wrapped in act(). */
function triggerCallback(type: "show" | "hide") {
	const cbs = mockBubble._listeners[type] ?? [];
	act(() => {
		for (const cb of cbs) {
			(cb as () => void)();
		}
	});
}

describe("Bubble", () => {
	it("renders without crashing", () => {
		render(<Bubble />);
		const output = document.querySelector('output[aria-live="polite"]');
		expect(output).toBeTruthy();
	});

	it("renders idle Ready label by default, no recording bars", () => {
		render(<Bubble />);
		// Default mode is "idle": Ready label visible, no visualizer bars,
		// no red recording dot. Recording UI appears only after a real
		// show/setState recording event from the backend.
		expect(screen.getByText("Ready")).toBeTruthy();
		expect(document.querySelectorAll(".gap-0\\.75 > span").length).toBe(0);
		expect(
			document.querySelectorAll('[data-slot="bubble-recording-dot"]'),
		).toHaveLength(0);
	});

	it("renders recording visualizer bars after recording state", () => {
		render(<Bubble />);
		setBubbleState("recording");
		const bars = document.querySelectorAll(".gap-0\\.75 > span");
		expect(bars.length).toBe(7);
	});

	it("renders no stray text in recording mode (comment-corpse guard)", () => {
		render(<Bubble />);
		setBubbleState("recording");
		expect(document.body.textContent).not.toContain("*/");
		expect(document.body.textContent).not.toContain("REC");
	});

	it("renders the recording dot only while recording", () => {
		render(<Bubble />);

		// Default mode is "idle", no red pulsing dot while not recording.
		expect(
			document.querySelectorAll('[data-slot="bubble-recording-dot"]'),
		).toHaveLength(0);

		setBubbleState("recording");
		expect(
			document.querySelectorAll('[data-slot="bubble-recording-dot"]'),
		).toHaveLength(1);

		// Every other mode owns its own indicator and must NOT show the
		// recording dot: red + pulsing means "capturing audio right now".
		for (const state of [
			"transcribing",
			"idle",
			"error",
			"blocked",
			"cancelling",
			"permission_revoked",
			"paste_failed",
		]) {
			setBubbleState(state);
			expect(
				document.querySelectorAll('[data-slot="bubble-recording-dot"]'),
				`recording dot leaked into ${state} mode`,
			).toHaveLength(0);
		}
	});

	it("shows transcribing state with text and animated dots when onSetState fires", () => {
		render(<Bubble />);

		setBubbleState("transcribing");

		expect(screen.getByText("Transcribing")).toBeTruthy();

		// Shimmer label with 3 merged blinking dots (no separate text)
		expect(document.querySelectorAll(".bubble-shimmer-text")).toHaveLength(1);
		const dots = document.querySelectorAll(".bubble-blink-dot");
		expect(dots.length).toBe(3);
	});

	it("hides visualizer bars when in transcribing mode", () => {
		render(<Bubble />);

		setBubbleState("recording");
		const barsBefore = document.querySelectorAll(".gap-0\\.75 > span");
		expect(barsBefore.length).toBe(7);

		setBubbleState("transcribing");

		// Bars should no longer be rendered
		const barsAfter = document.querySelectorAll(".gap-0\\.75 > span");
		expect(barsAfter.length).toBe(0);
	});

	it("renders idle Ready label, no bars, no recording dot", () => {
		render(<Bubble />);

		setBubbleState("idle");

		expect(screen.getByText("Ready")).toBeTruthy();
		expect(
			document.querySelectorAll('[data-slot="bubble-recording-dot"]'),
		).toHaveLength(0);

		// No bars
		const bars = document.querySelectorAll(".gap-0\\.75 > span");
		expect(bars.length).toBe(0);

		// No transcribing text
		expect(screen.queryByText("Transcribing")).toBeNull();
	});

	it("transitions through all three modes in sequence", () => {
		render(<Bubble />);

		// Start: idle (Ready, no bars)
		expect(screen.getByText("Ready")).toBeTruthy();
		expect(document.querySelectorAll(".gap-0\\.75 > span").length).toBe(0);

		// Recording: bars visible
		setBubbleState("recording");
		expect(document.querySelectorAll(".gap-0\\.75 > span").length).toBe(7);

		// Transcribing: text visible, bars hidden
		setBubbleState("transcribing");
		expect(screen.getByText("Transcribing")).toBeTruthy();
		expect(document.querySelectorAll(".gap-0\\.75 > span").length).toBe(0);

		// Idle: Ready visible again
		setBubbleState("idle");
		expect(screen.getByText("Ready")).toBeTruthy();
		expect(document.querySelectorAll(".gap-0\\.75 > span").length).toBe(0);
	});

	it("has accessible aria-label", () => {
		render(<Bubble />);
		const output = document.querySelector('output[aria-live="polite"]');
		expect(output?.getAttribute("aria-label")).toBe("Lausu idle indicator");
	});

	it("transcribing dots have staggered animation delays", () => {
		render(<Bubble />);

		setBubbleState("transcribing");

		const dots = document.querySelectorAll(".bubble-blink-dot");
		expect(dots.length).toBe(3);

		// Each dot should have a different animation-delay
		const delays = Array.from(dots).map(
			(el) => (el as HTMLElement).style.animationDelay,
		);
		expect(new Set(delays).size).toBe(3); // All three delays are unique
	});

	it("switches back to transcribing from idle when called again", () => {
		render(<Bubble />);

		setBubbleState("idle");
		expect(screen.queryByText("Transcribing")).toBeNull();

		setBubbleState("transcribing");
		expect(screen.getByText("Transcribing")).toBeTruthy();
	});

	it("triggers enter animation on onShow callback", () => {
		render(<Bubble />);

		triggerCallback("show");

		const output = document.querySelector('output[aria-live="polite"]');
		expect(output?.className).toContain("animate-bubble-enter");
	});

	it("triggers exit animation on onHide callback", () => {
		render(<Bubble />);

		triggerCallback("hide");

		const output = document.querySelector('output[aria-live="polite"]');
		expect(output?.className).toContain("animate-bubble-exit");
	});

	//mic button (always_visible + enabled) ──────────────

	it("does NOT show a mic button by default (no config received)", () => {
		render(<Bubble />);
		// Without a bubble:config push, the button must stay hidden.
		expect(screen.queryByLabelText("Start dictation")).toBeNull();
		expect(screen.queryByLabelText("Stop dictation")).toBeNull();
	});

	it("shows a mic button when always_visible + both toggles are on", () => {
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
		});

		// Default mode is "idle", so the start affordance shows.
		const btn = screen.getByLabelText("Start dictation");
		expect(btn).toBeTruthy();
		// It is clickable (not a dead pill).
		expect(btn.tagName).toBe("BUTTON");
	});

	it("hides the mic button when bubble_mic_button is false", () => {
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: false,
		});

		expect(screen.queryByLabelText("Start dictation")).toBeNull();
		expect(screen.queryByLabelText("Stop dictation")).toBeNull();
	});

	it("hides the mic button when bubble_behavior is show_on_record", () => {
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "show_on_record",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
		});

		expect(screen.queryByLabelText("Start dictation")).toBeNull();
		expect(screen.queryByLabelText("Stop dictation")).toBeNull();
	});

	it("clicking the mic button calls toggleDictation (UX-10 fix)", () => {
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
		});

		const btn = screen.getByLabelText("Start dictation");
		act(() => {
			btn.click();
		});

		expect(mockBubble.toggleDictation).toHaveBeenCalledTimes(1);
	});

	it("toggles the action slot between mic and stop as recording state changes", () => {
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
		});

		// Idle → mic affordance.
		expect(screen.getByLabelText("Start dictation")).toBeTruthy();

		// Go recording → single stop affordance, mic unmounted.
		setBubbleState("recording");
		expect(screen.getByLabelText("Stop recording")).toBeTruthy();
		expect(screen.queryByLabelText("Start dictation")).toBeNull();
		expect(screen.queryByLabelText("Stop dictation")).toBeNull();
	});

	it("shows exactly one filled stop affordance while recording", () => {
		render(<Bubble />);

		setBubbleState("recording");
		pushBubbleConfig({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
			bubble_show_recording_timer: false,
		});

		// Recording renders a single action: the stop button. The mic
		// toggle is unmounted so the pill never shows two competing
		// actions. Only `BubbleStopButton` may render the filled
		// (solid) stop glyph.
		const filledIcons = document.querySelectorAll(
			'button svg[fill="currentColor"]',
		);
		expect(filledIcons).toHaveLength(1);
	});

	it("hides the dismiss button while recording, shows it when idle", () => {
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
		});

		setBubbleState("recording");
		expect(screen.queryByLabelText("Dismiss bubble")).toBeNull();

		setBubbleState("idle");
		expect(screen.getByLabelText("Dismiss bubble")).toBeTruthy();
	});

	it("hides the recording timer by default, shows it when enabled", () => {
		render(<Bubble />);

		setBubbleState("recording");
		expect(
			document.querySelector('[data-slot="bubble-recording-timer"]'),
		).toBeNull();

		pushBubbleConfig({ bubble_show_recording_timer: true });
		const timer = document.querySelector(
			'[data-slot="bubble-recording-timer"]',
		);
		expect(timer).toBeTruthy();
		expect(timer?.textContent).toBe("00:00");
	});

	it("keeps the transcribing dismiss disabled for 5s, then arms it", () => {
		vi.useFakeTimers();
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
		});
		setBubbleState("transcribing");

		const btn = screen.getByLabelText("Dismiss bubble");
		expect(btn).toBeDisabled();

		act(() => {
			vi.advanceTimersByTime(5000);
		});
		expect(screen.getByLabelText("Dismiss bubble")).not.toBeDisabled();

		vi.useRealTimers();
	});

	it("stays idle when idle set_state overtakes show (either order)", () => {
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
		});

		// set_state first, show second: the overtaking order seen when
		// switching back to always_visible (show travels the slow
		// window-show path). Must converge on idle, never recording.
		setBubbleState("idle");
		triggerCallback("show");
		expect(screen.getByText("Ready")).toBeTruthy();
		expect(
			document.querySelectorAll('[data-slot="bubble-recording-dot"]'),
		).toHaveLength(0);
		expect(screen.queryByLabelText("Stop recording")).toBeNull();

		// Reverse order converges too.
		triggerCallback("show");
		setBubbleState("idle");
		expect(screen.getByText("Ready")).toBeTruthy();
		expect(
			document.querySelectorAll('[data-slot="bubble-recording-dot"]'),
		).toHaveLength(0);
	});

	//state-aware aria-label on outer <output> ──────────

	it("BG-95: aria-label reflects idle mode by default", () => {
		render(<Bubble />);
		const output = document.querySelector('output[aria-live="polite"]');
		expect(output?.getAttribute("aria-label")).toBe("Lausu idle indicator");
	});

	it("BG-95: aria-label switches to transcribing indicator when mode changes", () => {
		render(<Bubble />);

		setBubbleState("transcribing");

		const output = document.querySelector('output[aria-live="polite"]');
		expect(output?.getAttribute("aria-label")).toBe(
			"Lausu transcribing indicator",
		);
	});

	it("BG-95: aria-label switches to error indicator in error mode", () => {
		render(<Bubble />);

		setBubbleState("error");

		const output = document.querySelector('output[aria-live="polite"]');
		expect(output?.getAttribute("aria-label")).toBe("Lausu error indicator");
	});

	it("BG-95: aria-label switches to idle indicator in idle mode", () => {
		render(<Bubble />);

		setBubbleState("idle");

		const output = document.querySelector('output[aria-live="polite"]');
		expect(output?.getAttribute("aria-label")).toBe("Lausu idle indicator");
	});

	//dismiss '×' button ─────────────────────────────────

	it("BG-96: does NOT show a dismiss button by default (no config received)", () => {
		render(<Bubble />);
		// Without a bubble:config push, the dismiss button must stay hidden.
		expect(screen.queryByLabelText("Dismiss bubble")).toBeNull();
	});

	it("BG-96: shows a dismiss button when bubble_behavior is always_visible", () => {
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
		});

		const btn = screen.getByLabelText("Dismiss bubble");
		expect(btn).toBeTruthy();
		expect(btn.tagName).toBe("BUTTON");
	});

	it("BG-96: shows a dismiss button in always_visible mode even when mic_button is off", () => {
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: false,
		});

		// Mic button should be hidden, but dismiss button still shown
		// (always_visible bubble needs a manual dismiss affordance).
		expect(screen.queryByLabelText("Start dictation")).toBeNull();
		expect(screen.queryByLabelText("Stop dictation")).toBeNull();
		expect(screen.getByLabelText("Dismiss bubble")).toBeTruthy();
	});

	it("BG-96: hides the dismiss button when bubble_behavior is show_on_record", () => {
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "show_on_record",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
		});

		// show_on_record auto-hides when recording stops, so no
		// manual dismiss affordance is needed.
		expect(screen.queryByLabelText("Dismiss bubble")).toBeNull();
	});

	it("BG-96: clicking the dismiss button calls window.bubble.dismiss", () => {
		render(<Bubble />);

		pushBubbleConfig({
			bubble_behavior: "always_visible",
			bubble_click_to_toggle: true,
			bubble_mic_button: true,
		});

		const btn = screen.getByLabelText("Dismiss bubble");
		act(() => {
			btn.click();
		});

		expect(mockBubble.dismiss).toHaveBeenCalledTimes(1);
	});
});
