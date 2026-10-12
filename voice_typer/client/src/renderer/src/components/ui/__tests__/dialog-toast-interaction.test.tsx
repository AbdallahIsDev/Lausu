import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
	act,
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: ({ icon }: { icon?: { name?: string } }) => (
		<span data-testid="hugeicon" data-name={icon?.name} />
	),
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogTitle,
} from "@/components/ui/dialog";

// ─────────────────────────────────────────────────────────────────────────────
// A toast must stay interactive while a modal Dialog is open, and interacting
// with it must NOT be read as a backdrop dismissal ("the first click is
// effectively wasted on closing the modal").
//
// The bug has TWO independent halves, so a naive test can only see one:
//
//   1. `document.body.style.pointerEvents = "none"` is set for the whole
//      lifetime of a modal by Radix's DismissableLayer. Sonner's stylesheet
//      only declares pointer-events on `[data-visible='false']` toasts, so a
//      visible toast inherited `none` and the click was hit-tested against the
//      dialog overlay — the toast never received it. jsdom does no
//      hit-testing, so this half is only observable as a source-shape
//      assertion (describe block 1).
//   2. Even once the click reaches the toast, Radix still dispatches
//      POINTER_DOWN_OUTSIDE and dismisses the dialog. That is what
//      `DialogContent`'s composed `onPointerDownOutside` fixes, and it IS
//      observable here (describe block 2).
//
// Neither half alone fixes the bug; both tests below fail if only one ships.
// ─────────────────────────────────────────────────────────────────────────────

const css = readFileSync(
	resolve(__dirname, "..", "..", "..", "index.css"),
	"utf8",
);

/** Sonner marks the toaster container with this attribute AND (via our
 *  `components/ui/sonner.tsx` wrapper) the `toaster group` classes that
 *  index.css scopes its toaster rules to. Same element, two handles. */
const TOASTER_ATTR = "data-sonner-toaster";

let stub: { toaster: HTMLElement; toast: HTMLElement };

function mountToasterStub(): { toaster: HTMLElement; toast: HTMLElement } {
	const toaster = document.createElement("section");
	toaster.setAttribute(TOASTER_ATTR, "");
	toaster.className = "toaster group";
	const toast = document.createElement("li");
	toast.setAttribute("data-sonner-toast", "");
	const action = document.createElement("button");
	action.type = "button";
	action.textContent = "Open Models";
	toast.appendChild(action);
	toaster.appendChild(toast);
	document.body.appendChild(toaster);
	return { toaster, toast };
}

function actionButton(): HTMLButtonElement {
	const el = stub.toast.querySelector("button");
	if (!el) throw new Error("toast action button missing");
	return el;
}

function renderDialog(open: boolean, onOpenChange: (open: boolean) => void) {
	return render(
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogTitle>Configure OpenAI</DialogTitle>
				<DialogDescription>Enter your API key.</DialogDescription>
			</DialogContent>
		</Dialog>,
	);
}

/** Radix attaches its document-level outside-pointerdown listener on a 0ms
 *  timer, so the event has to be fired after one macrotask has elapsed or the
 *  listener is not registered yet and every assertion below passes vacuously. */
async function flushRadixListener(): Promise<void> {
	await act(async () => {
		await new Promise((done) => {
			setTimeout(done, 0);
		});
	});
}

/**
 * A faithful mouse press. This matters: Radix's `Dialog` passes
 * `deferPointerDownOutside: true`, so POINTER_DOWN_OUTSIDE is NOT dispatched
 * on the pointerdown itself — it is parked on the document's next `click`
 * (and only then, if nothing called `stopPropagation` in between). Firing
 * `pointerdown` alone therefore dismisses nothing, and a test that asserts
 * "the dialog is still open" after a bare pointerdown passes vacuously.
 */
function pressPointer(el: Element): void {
	fireEvent.pointerDown(el);
	fireEvent.mouseDown(el);
	fireEvent.pointerUp(el);
	fireEvent.mouseUp(el);
	fireEvent.click(el);
}

beforeEach(() => {
	stub = mountToasterStub();
});

afterEach(() => {
	cleanup();
	stub.toaster.remove();
});

describe("toaster escapes the modal body lock (index.css)", () => {
	const toasterRegionCss = css
		.slice(css.indexOf("/* ── Sonner toaster"))
		.replace(/\/\*[\s\S]*?\*\//g, "");

	it("re-enables pointer events on the toaster container", () => {
		// Without this the click never reaches the toast in a real browser:
		// `pointer-events` is inherited, and the modal body lock sets it to
		// `none` on <body>, which the portaled toaster inherits.
		expect(toasterRegionCss).toMatch(
			/\.toaster\s*\{\s*pointer-events:\s*auto;\s*\}/,
		);
	});

	it("declares it on the container only, never per-toast", () => {
		// Sonner declares `pointer-events: none` on
		// `[data-sonner-toast][data-visible='false']`; a per-toast `auto`
		// here would override it and make hidden toasts clickable, so the
		// escape hatch has to sit on the container and be inherited.
		expect(toasterRegionCss.match(/pointer-events\s*:/g) ?? []).toHaveLength(1);
	});
});

describe("a toast interaction is not a modal dismissal", () => {
	it("keeps the dialog open when the press lands on a toast", async () => {
		const onOpenChange = vi.fn();
		renderDialog(true, onOpenChange);
		await screen.findByRole("dialog");
		await flushRadixListener();

		pressPointer(actionButton());
		await flushRadixListener();

		expect(onOpenChange).not.toHaveBeenCalled();
		expect(screen.getByRole("dialog")).toBeTruthy();
	});

	it("lets the toast's own controls receive the interaction", async () => {
		const onOpenChange = vi.fn();
		const onAction = vi.fn();
		const action = actionButton();
		action.addEventListener("click", onAction);
		renderDialog(true, onOpenChange);
		await screen.findByRole("dialog");
		await flushRadixListener();

		pressPointer(action);
		await flushRadixListener();

		expect(onAction).toHaveBeenCalledTimes(1);
		expect(onOpenChange).not.toHaveBeenCalled();
	});

	it("still dismisses on a genuine backdrop interaction", async () => {
		// The negative control. If the guard over-matched (e.g. swallowed
		// every outside press) the dialog would become undismissable.
		const onOpenChange = vi.fn();
		renderDialog(true, onOpenChange);
		await screen.findByRole("dialog");
		await flushRadixListener();

		pressPointer(document.body);

		await waitFor(() => {
			expect(onOpenChange).toHaveBeenCalledWith(false);
		});
	});

	it("still dismisses when the press lands on the overlay", async () => {
		const onOpenChange = vi.fn();
		renderDialog(true, onOpenChange);
		await screen.findByRole("dialog");
		await flushRadixListener();
		const overlay = document.querySelector("[data-slot='dialog-overlay']");
		if (!overlay) throw new Error("dialog overlay missing");

		pressPointer(overlay);

		await waitFor(() => {
			expect(onOpenChange).toHaveBeenCalledWith(false);
		});
	});

	it("still composes with a caller-supplied onPointerDownOutside", async () => {
		// Guards the spread order in DialogContent: the guard is declared
		// AFTER `{...props}` and must invoke, not replace, the caller's
		// handler (mirroring the existing onOpenAutoFocus contract).
		const onOpenChange = vi.fn();
		const callerHandler = vi.fn();
		render(
			<Dialog open onOpenChange={onOpenChange}>
				<DialogContent onPointerDownOutside={callerHandler}>
					<DialogTitle>Configure OpenAI</DialogTitle>
					<DialogDescription>Enter your API key.</DialogDescription>
				</DialogContent>
			</Dialog>,
		);
		await screen.findByRole("dialog");
		await flushRadixListener();

		pressPointer(document.body);

		await waitFor(() => {
			expect(callerHandler).toHaveBeenCalledTimes(1);
		});
		expect(onOpenChange).toHaveBeenCalledWith(false);
	});
});
