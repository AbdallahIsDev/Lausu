import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Bubble } from "@/Bubble";

// ── Mock window.bubble API ──────────────────────────────────────────
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
		onConfig: vi.fn((cb: (cfg: Record<string, unknown>) => void) => {
			listeners.config = cb;
			return () => {
				listeners.config = undefined;
			};
		}),
		toggleDictation: vi.fn(),
		dismiss: vi.fn(),
		_listeners: listeners,
	};
}

let mockBubble: ReturnType<typeof makeMockBubble>;

beforeEach(() => {
	mockBubble = makeMockBubble();
	(window as unknown as Record<string, unknown>).bubble = mockBubble;

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

function setBubbleState(state: string) {
	const cbs = mockBubble._listeners.setState ?? [];
	act(() => {
		for (const cb of cbs) {
			(cb as (s: string) => void)(state);
		}
	});
}

function setBubblePayload(payload: unknown) {
	const cbs = mockBubble._listeners.setState ?? [];
	act(() => {
		for (const cb of cbs) {
			(cb as (s: unknown) => void)(payload);
		}
	});
}

describe("bubble mid-flow modes (blocked / cancelling / permission_revoked / paste_failed)", () => {
	it("renders the 'Blocked' label when state becomes 'blocked'", () => {
		render(<Bubble />);

		// Default mode is idle (Ready), no Blocked label.
		expect(screen.queryByText("Blocked")).toBeNull();

		setBubbleState("blocked");

		expect(screen.getByText("Blocked")).toBeTruthy();
	});

	it("renders the 'Cancelling…' label when state becomes 'cancelling'", () => {
		render(<Bubble />);

		expect(screen.queryByText("Cancelling…")).toBeNull();

		setBubbleState("cancelling");

		expect(screen.getByText("Cancelling…")).toBeTruthy();
	});

	it("renders the 'Mic permission revoked' label when state becomes 'permission_revoked'", () => {
		render(<Bubble />);

		expect(screen.queryByText("Mic permission revoked")).toBeNull();

		setBubbleState("permission_revoked");

		expect(screen.getByText("Mic permission revoked")).toBeTruthy();
	});

	it("renders the 'Paste failed' label when state becomes 'paste_failed'", () => {
		render(<Bubble />);

		expect(screen.queryByText("Paste failed")).toBeNull();

		setBubbleState("paste_failed");

		expect(screen.getByText("Paste failed")).toBeTruthy();
	});

	it("renders the 'Loading model' label when state becomes 'loading'", () => {
		render(<Bubble />);

		expect(screen.queryByText("Loading model")).toBeNull();

		setBubbleState("loading");

		expect(screen.getByText("Loading model")).toBeTruthy();
	});

	it("sets a distinctive aria-label for each new mode", () => {
		render(<Bubble />);

		const output = document.querySelector('output[aria-live="polite"]');
		expect(output).toBeTruthy();

		// blocked
		setBubbleState("blocked");
		expect(output?.getAttribute("aria-label")).toBe("Lausu blocked indicator");

		// cancelling
		setBubbleState("cancelling");
		expect(output?.getAttribute("aria-label")).toBe(
			"Lausu cancelling indicator",
		);

		// permission_revoked
		setBubbleState("permission_revoked");
		expect(output?.getAttribute("aria-label")).toBe(
			"Lausu microphone permission revoked indicator",
		);

		// paste_failed
		setBubbleState("paste_failed");
		expect(output?.getAttribute("aria-label")).toBe(
			"Lausu paste failed indicator",
		);

		// loading
		setBubbleState("loading");
		expect(output?.getAttribute("aria-label")).toBe("Lausu loading indicator");
	});

	it("falls back to recording mode when state becomes 'recording' after a mid-flow mode", () => {
		render(<Bubble />);

		// Enter a mid-flow mode.
		setBubbleState("blocked");
		expect(screen.getByText("Blocked")).toBeTruthy();

		// Back to recording, Blocked label should disappear.
		setBubbleState("recording");
		expect(screen.queryByText("Blocked")).toBeNull();
	});

	it("renders recording with bars and no notice text even when live preview is unsupported", () => {
		render(<Bubble />);

		// Object payload as published by the backend (not a bare string).
		const cbs = mockBubble._listeners.setState ?? [];
		act(() => {
			for (const cb of cbs) {
				(cb as unknown as (s: unknown) => void)({
					state: "recording",
					live_preview_supported: false,
				});
			}
		});

		// Visualizer bars present…
		expect(document.querySelectorAll(".gap-0\\.75 > span").length).toBe(7);
		// …and no "No live preview" notice text anywhere in the pill.
		expect(screen.queryByText(/live preview/i)).toBeNull();
	});

	it("does NOT render bars in any of the new mid-flow modes", () => {
		render(<Bubble />);

		setBubbleState("recording");
		expect(document.querySelectorAll(".gap-0\\.75 > span").length).toBe(7);

		// Each new mode should hide the bars (no visualizer in mid-flow).
		for (const state of [
			"blocked",
			"cancelling",
			"permission_revoked",
			"paste_failed",
			"loading",
		]) {
			setBubbleState(state);
			expect(document.querySelectorAll(".gap-0\\.75 > span").length).toBe(0);
		}
	});
});

describe("bubble busy-refusal hint (still_transcribing)", () => {
	it("swaps the transcribing label to 'Still transcribing' while staying in transcribing mode", () => {
		render(<Bubble />);

		setBubbleState("transcribing");
		expect(screen.getByText("Transcribing")).toBeTruthy();

		// Backend re-push on hotkey press during transcription.
		setBubbleState("still_transcribing");

		expect(screen.getByText("Still transcribing")).toBeTruthy();
		expect(screen.queryByText("Transcribing")).toBeNull();
		// Still transcribing mode: no visualizer bars.
		expect(document.querySelectorAll(".gap-0\\.75 > span").length).toBe(0);
	});

	it("clears the hint on the next real state (e.g. a fresh recording cycle)", () => {
		render(<Bubble />);

		setBubbleState("transcribing");
		setBubbleState("still_transcribing");
		expect(screen.getByText("Still transcribing")).toBeTruthy();

		// A fresh cycle's "transcribing" push restores the plain label.
		setBubbleState("idle");
		setBubbleState("transcribing");

		expect(screen.getByText("Transcribing")).toBeTruthy();
		expect(screen.queryByText("Still transcribing")).toBeNull();
	});

	it("preserves the live transcript preview across the hint", () => {
		render(<Bubble />);

		setBubblePayload({ state: "transcribing", transcript: "hello wor" });
		expect(screen.getByText("hello wor")).toBeTruthy();

		// The hint carries no transcript payload — the preview must not wipe.
		setBubbleState("still_transcribing");

		expect(screen.getByText("hello wor")).toBeTruthy();
		expect(screen.getByText("Still transcribing")).toBeTruthy();
	});

	it("does not resurrect a fading bubble (fading guard wins)", () => {
		render(<Bubble />);

		setBubbleState("transcribing");
		// hide → two-stage fade-out begins (mode = fading): the label
		// stays in-DOM but its wrapper fades out at opacity 0.
		act(() => {
			for (const cb of mockBubble._listeners.hide ?? []) {
				(cb as () => void)();
			}
		});
		const fadingLabel = screen.getByText("Transcribing");
		expect(fadingLabel.closest("div")?.style.opacity).toBe("0");

		// A late hint push must not pull the fading pill back: mode
		// stays "fading" — the wrapper is still opacity-0 (the exit
		// sequence untouched) while only the label text swaps.
		setBubbleState("still_transcribing");
		expect(
			screen.getByText("Still transcribing").closest("div")?.style.opacity,
		).toBe("0");
		expect(screen.queryByText("Transcribing")).toBeNull();
	});
});

describe("bubble cloud-cancel honesty hint (cloud_cancel_requested)", () => {
	it("swaps the transcribing label to 'Cancel requested' while staying in transcribing mode", () => {
		render(<Bubble />);

		setBubbleState("transcribing");
		expect(screen.getByText("Transcribing")).toBeTruthy();

		// ESC during a cloud cycle: the provider may still finish.
		setBubbleState("cloud_cancel_requested");

		expect(screen.getByText("Cancel requested")).toBeTruthy();
		expect(screen.queryByText("Transcribing")).toBeNull();
	});

	it("clears the hint on the next real state (e.g. a fresh recording cycle)", () => {
		render(<Bubble />);

		setBubbleState("transcribing");
		setBubbleState("cloud_cancel_requested");
		expect(screen.getByText("Cancel requested")).toBeTruthy();

		setBubbleState("idle");
		setBubbleState("transcribing");

		expect(screen.getByText("Transcribing")).toBeTruthy();
		expect(screen.queryByText("Cancel requested")).toBeNull();
	});

	it("does not resurrect a fading bubble (fading guard wins)", () => {
		render(<Bubble />);

		setBubbleState("transcribing");
		act(() => {
			for (const cb of mockBubble._listeners.hide ?? []) {
				(cb as () => void)();
			}
		});

		setBubbleState("cloud_cancel_requested");
		expect(
			screen.getByText("Cancel requested").closest("div")?.style.opacity,
		).toBe("0");
		expect(screen.queryByText("Transcribing")).toBeNull();
	});
});
