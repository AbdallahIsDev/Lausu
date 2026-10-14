import {
	act,
	cleanup,
	fireEvent,
	render,
	screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { makeConfig } from "@/__tests__/helpers/fixtures";
import { Bubble } from "@/Bubble";
import { ScreenshotOverlay } from "@/bubble/ScreenshotOverlay";
import { useConsentGateStore } from "@/lib/consentGate";
import { mintScreenshotCycleId } from "@/lib/screenshot";

function makeMockBubble() {
	const listeners: {
		show: Array<() => void>;
		hide: Array<() => void>;
		setState: Array<(state: unknown) => void>;
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
		onSetState: vi.fn((cb: (state: unknown) => void) => {
			listeners.setState.push(cb);
			return () => {
				listeners.setState = listeners.setState.filter((l) => l !== cb);
			};
		}),
		onDraggable: vi.fn(() => vi.fn()),
		onLocaleChanged: vi.fn(() => vi.fn()),
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
		requestScreenshotCapture: vi.fn().mockResolvedValue({
			type: "screenshot_captured",
			data: { path: "shot.png", width: 10, height: 10, bytes: 8 },
		}),
		_listeners: listeners,
	};
}

let mockBubble: ReturnType<typeof makeMockBubble>;
const mockPythonCall = vi.fn();

beforeEach(() => {
	mockBubble = makeMockBubble();
	(window as unknown as Record<string, unknown>).bubble = mockBubble;
	(window as unknown as Record<string, unknown>).python = {
		call: mockPythonCall,
		onEvent: vi.fn(() => vi.fn()),
	};
	mockPythonCall.mockReset().mockResolvedValue({ ok: true });
	useConsentGateStore.getState().close();

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
	delete (window as unknown as Record<string, unknown>).python;
	useConsentGateStore.getState().close();
});

function setBubbleState(state: unknown) {
	const cbs = mockBubble._listeners.setState ?? [];
	act(() => {
		for (const cb of cbs) cb(state);
	});
}

function pushBetaConfig(consent: boolean) {
	act(() => {
		mockBubble._listeners.config?.({
			screenshot_beta_enabled: true,
			screenshot_consent: consent,
		});
	});
}

const ANNOTATE_ARIA = "Capture a screenshot region";

describe("screenshot beta annotate button", () => {
	it("stays hidden while the beta flag is off, even in recording", () => {
		render(<Bubble />);
		setBubbleState("recording");
		expect(screen.queryByLabelText(ANNOTATE_ARIA)).toBeNull();
	});

	it("appears in recording when the beta flag is on", () => {
		render(<Bubble />);
		pushBetaConfig(true);
		setBubbleState("recording");
		expect(screen.getByLabelText(ANNOTATE_ARIA)).toBeTruthy();
	});

	it("stays hidden in idle and transcribing when the beta flag is on", () => {
		render(<Bubble />);
		pushBetaConfig(true);
		expect(screen.queryByLabelText(ANNOTATE_ARIA)).toBeNull();
		setBubbleState("transcribing");
		expect(screen.queryByLabelText(ANNOTATE_ARIA)).toBeNull();
	});

	it("opens the shared consent gate (no overlay) when consent is missing", () => {
		render(<Bubble />);
		pushBetaConfig(false);
		setBubbleState("recording");
		fireEvent.click(screen.getByLabelText(ANNOTATE_ARIA));
		const request = useConsentGateStore.getState().request;
		expect(request?.consentField).toBe("screenshot_consent");
		expect(request?.bodyKey).toBe("screenshot.consentDesc");
		expect(screen.queryByText(/Drag to select a region/)).toBeNull();
	});

	it("granting consent opens the overlay, Esc cancels without IPC", () => {
		render(<Bubble />);
		pushBetaConfig(false);
		setBubbleState("recording");
		fireEvent.click(screen.getByLabelText(ANNOTATE_ARIA));
		act(() => {
			useConsentGateStore.getState().request?.onAllow?.();
		});
		expect(screen.getByText(/Drag to select a region/)).toBeTruthy();
		fireEvent.keyDown(window, { key: "Escape" });
		expect(screen.queryByText(/Drag to select a region/)).toBeNull();
		expect(mockPythonCall).not.toHaveBeenCalled();
	});

	it("drag release captures via the bubble host bridge and burns the one shot on success", async () => {
		Object.defineProperty(window, "devicePixelRatio", {
			value: 2,
			configurable: true,
		});
		const info = vi.spyOn(console, "info").mockImplementation(() => {});
		try {
			render(<Bubble />);
			pushBetaConfig(true);
			setBubbleState("recording");
			fireEvent.click(screen.getByLabelText(ANNOTATE_ARIA));
			const dialog = screen.getByRole("dialog", {
				name: "Screenshot capture",
			});
			fireEvent.mouseDown(dialog, { clientX: 10, clientY: 10, button: 0 });
			fireEvent.mouseMove(dialog, { clientX: 110, clientY: 60 });
			fireEvent.mouseUp(dialog, { clientX: 110, clientY: 60 });
			const request = mockBubble.requestScreenshotCapture;
			expect(request).toHaveBeenCalledTimes(1);
			const [cycleId, rect] = request.mock.calls[0] as [unknown, unknown];
			expect(typeof cycleId).toBe("string");
			expect(rect).toEqual({ left: 20, top: 20, width: 200, height: 100 });
			// The sandboxed bubble has no window.python: the capture must
			// NOT go through the python bridge (that path silently no-ops).
			expect(mockPythonCall).not.toHaveBeenCalled();
			expect(screen.queryByText(/Drag to select a region/)).toBeNull();
			expect(await screen.findByText("1/1")).toBeTruthy();
			expect(screen.getByLabelText(ANNOTATE_ARIA)).toBeDisabled();
			expect(info).toHaveBeenCalledWith(
				"[renderer:bubble] screenshot captured:",
				"shot.png",
			);
		} finally {
			info.mockRestore();
			Object.defineProperty(window, "devicePixelRatio", {
				value: 1,
				configurable: true,
			});
		}
	});

	it("a rejected capture warns and stays retryable (one shot not burnt)", async () => {
		mockBubble.requestScreenshotCapture.mockRejectedValueOnce(
			new Error("sidecar down"),
		);
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		try {
			render(<Bubble />);
			pushBetaConfig(true);
			setBubbleState("recording");
			fireEvent.click(screen.getByLabelText(ANNOTATE_ARIA));
			const dialog = screen.getByRole("dialog", {
				name: "Screenshot capture",
			});
			fireEvent.mouseDown(dialog, { clientX: 10, clientY: 10, button: 0 });
			fireEvent.mouseMove(dialog, { clientX: 60, clientY: 60 });
			fireEvent.mouseUp(dialog, { clientX: 60, clientY: 60 });
			expect(mockBubble.requestScreenshotCapture).toHaveBeenCalledTimes(1);
			await act(async () => {});
			expect(screen.queryByText(/Drag to select a region/)).toBeNull();
			expect(screen.queryByText("1/1")).toBeNull();
			expect(screen.getByLabelText(ANNOTATE_ARIA)).toBeEnabled();
			expect(warn).toHaveBeenCalledWith(
				"[renderer:bubble] screenshot_capture failed:",
				expect.anything(),
			);
		} finally {
			warn.mockRestore();
		}
	});

	it("warns when the bubble bridge has no capture method", () => {
		(
			mockBubble as unknown as Record<string, unknown>
		).requestScreenshotCapture = undefined;
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
		try {
			render(<Bubble />);
			pushBetaConfig(true);
			setBubbleState("recording");
			fireEvent.click(screen.getByLabelText(ANNOTATE_ARIA));
			const dialog = screen.getByRole("dialog", {
				name: "Screenshot capture",
			});
			fireEvent.mouseDown(dialog, { clientX: 10, clientY: 10, button: 0 });
			fireEvent.mouseMove(dialog, { clientX: 60, clientY: 60 });
			fireEvent.mouseUp(dialog, { clientX: 60, clientY: 60 });
			expect(screen.queryByText(/Drag to select a region/)).toBeNull();
			expect(screen.queryByText("1/1")).toBeNull();
			expect(warn).toHaveBeenCalledWith(
				"[renderer:bubble] screenshot capture backend unreachable (no bubble bridge)",
			);
		} finally {
			warn.mockRestore();
		}
	});

	it("re-arms the button on the next recording", async () => {
		render(<Bubble />);
		pushBetaConfig(true);
		setBubbleState("recording");
		fireEvent.click(screen.getByLabelText(ANNOTATE_ARIA));
		const dialog = screen.getByRole("dialog", {
			name: "Screenshot capture",
		});
		fireEvent.mouseDown(dialog, { clientX: 0, clientY: 0, button: 0 });
		fireEvent.mouseMove(dialog, { clientX: 50, clientY: 50 });
		fireEvent.mouseUp(dialog, { clientX: 50, clientY: 50 });
		expect(await screen.findByText("1/1")).toBeTruthy();
		expect(screen.getByLabelText(ANNOTATE_ARIA)).toBeDisabled();
		setBubbleState("transcribing");
		setBubbleState("recording");
		expect(screen.getByLabelText(ANNOTATE_ARIA)).toBeEnabled();
		expect(screen.queryByText("1/1")).toBeNull();
	});
});

describe("ScreenshotOverlay in isolation", () => {
	it("cancels on Escape without capturing", () => {
		const onCapture = vi.fn();
		const onCancel = vi.fn();
		render(<ScreenshotOverlay onCapture={onCapture} onCancel={onCancel} />);
		fireEvent.keyDown(window, { key: "Escape" });
		expect(onCancel).toHaveBeenCalledTimes(1);
		expect(onCapture).not.toHaveBeenCalled();
	});

	it("treats a click without drag as a cancel", () => {
		const onCapture = vi.fn();
		const onCancel = vi.fn();
		render(<ScreenshotOverlay onCapture={onCapture} onCancel={onCancel} />);
		const dialog = screen.getByRole("dialog");
		fireEvent.mouseDown(dialog, { clientX: 40, clientY: 40, button: 0 });
		fireEvent.mouseUp(dialog, { clientX: 41, clientY: 41 });
		expect(onCapture).not.toHaveBeenCalled();
		expect(onCancel).toHaveBeenCalledTimes(1);
	});
});

describe("screenshot beta config surface", () => {
	it("defaults both flags off in the shared fixture", () => {
		const cfg = makeConfig();
		expect(cfg.screenshot_beta_enabled).toBe(false);
		expect(cfg.screenshot_consent).toBe(false);
	});

	it("mints date-prefixed cycle ids", () => {
		const now = new Date("2026-10-07T12:00:00Z").getTime();
		const id = mintScreenshotCycleId(now);
		expect(id).toMatch(/^\d{4}-\d{2}-\d{2}_\d+$/);
		expect(id.endsWith(String(now))).toBe(true);
	});
});
