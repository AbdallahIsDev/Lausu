import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Bubble } from "@/Bubble";

function settleFrames(): Promise<void> {
	return new Promise<void>((resolve) => {
		setTimeout(resolve, 50);
	});
}

function makeMockBubble() {
	return {
		onLevel: vi.fn(() => vi.fn()),
		onShow: vi.fn(() => vi.fn()),
		onHide: vi.fn(() => vi.fn()),
		onSetState: vi.fn(() => vi.fn()),
		onDraggable: vi.fn(() => vi.fn()),
		signalReady: vi.fn(),
		hideComplete: vi.fn(),
		resizeTo: vi.fn(),
		moveBy: vi.fn(),
		onConfig: vi.fn(() => vi.fn()),
		toggleDictation: vi.fn(),
		dismiss: vi.fn(),
	};
}

beforeEach(() => {
	(window as unknown as Record<string, unknown>).bubble = makeMockBubble();
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
		configurable: true,
	});
	vi.spyOn(window, "getComputedStyle").mockImplementation(
		() =>
			({
				getPropertyValue: () => "",
			}) as unknown as CSSStyleDeclaration,
	);
	document.documentElement.dir = "ltr";
});

afterEach(() => {
	vi.restoreAllMocks();
	cleanup();
	delete (window as unknown as Record<string, unknown>).bubble;
});

function pill(): HTMLElement {
	const el = document.querySelector("div.rounded-full");
	expect(el).toBeTruthy();
	return el as HTMLElement;
}

describe("Bubble text selection guard", () => {
	it("cancels selectstart on the pill so a drag paints no highlight", () => {
		render(<Bubble />);
		const ev = new Event("selectstart", { bubbles: true, cancelable: true });
		pill().dispatchEvent(ev);
		expect(ev.defaultPrevented).toBe(true);
	});

	it("cancels selectstart fired on a child text node (capture phase)", () => {
		render(<Bubble />);
		const text = document.querySelector("div.rounded-full span");
		expect(text).toBeTruthy();
		const ev = new Event("selectstart", { bubbles: false, cancelable: true });
		(text as HTMLElement).dispatchEvent(ev);
		expect(ev.defaultPrevented).toBe(true);
	});

	it("swallows the context menu on the pill", () => {
		render(<Bubble />);
		const notCancelled = fireEvent.contextMenu(pill());
		expect(notCancelled).toBe(false);
	});

	it("repaints once after a context menu so no stale tile survives", async () => {
		render(<Bubble />);
		const el = pill();
		fireEvent.contextMenu(el);
		expect(el.style.opacity).toBe("0.99");
		await settleFrames();
		expect(el.style.opacity).toBe("");
	});

	it("cancels right-mousedown at initiation, leaves left alone", () => {
		render(<Bubble />);
		const rightCancelled = fireEvent.mouseDown(pill(), { button: 2 });
		expect(rightCancelled).toBe(false);
		const leftCancelled = fireEvent.mouseDown(pill(), { button: 0 });
		expect(leftCancelled).toBe(true);
	});
});
