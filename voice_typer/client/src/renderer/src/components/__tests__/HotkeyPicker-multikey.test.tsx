import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { sonnerMock, stableMocks } from "@/__tests__/helpers/stableMocks";
import { HotkeyPicker } from "../hotkey/HotkeyPicker";

// Capture errors are in-app notifications, not inline text.
vi.mock("sonner", () => sonnerMock());

interface DispatchOpts {
	code: string;
	key: string;
	ctrlKey?: boolean;
	shiftKey?: boolean;
	altKey?: boolean;
	metaKey?: boolean;
	type: "keydown" | "keyup";
}

function dispatchKey(opts: DispatchOpts) {
	const ev = new KeyboardEvent(opts.type, {
		code: opts.code,
		key: opts.key,
		ctrlKey: opts.ctrlKey ?? false,
		shiftKey: opts.shiftKey ?? false,
		altKey: opts.altKey ?? false,
		metaKey: opts.metaKey ?? false,
		bubbles: true,
		cancelable: true,
	});
	// Wrap in act() so React flushes any state updates triggered by the
	// event handler synchronously, before the test continues.
	act(() => {
		window.dispatchEvent(ev);
	});
}

function dispatchMouse(type: "mousedown" | "mouseup", button = 1) {
	const ev = new MouseEvent(type, {
		button,
		bubbles: true,
		cancelable: true,
	});
	act(() => {
		window.dispatchEvent(ev);
	});
}

async function enterCaptureMode() {
	const btn = screen.getByRole("button", { name: /record new hotkey/i });
	await act(async () => {
		btn.click();
	});
	// Wait for the button's aria-label to flip to "Cancel recording" —
	// that's the most reliable signal that recording state is now true.
	await screen.findByRole("button", { name: /cancel recording/i });
}

// The toast title is a React node (the copy plus the keycap chips), so read
// its message prop: the copy stays the contract under test.
function toastMessage(node: unknown): string {
	if (typeof node === "string") return node;
	return (
		(node as { props?: { message?: string } } | undefined)?.props?.message ?? ""
	);
}

async function waitForError(): Promise<string> {
	await waitFor(() => expect(stableMocks.toastError).toHaveBeenCalled());
	const calls = stableMocks.toastError.mock.calls;
	return toastMessage(calls[calls.length - 1]?.[0]);
}

// The picker captures ONE non-modifier key plus modifiers. A combo with two
// keys (Delete+End) can be captured but never fires: the native listeners
// match a single main key and the backend validator
// (``_check_multi_non_modifier``) rejects it, so the picker refuses it here
// with the same rule instead of committing an unsavable hotkey.
describe("HotkeyPicker, single-key capture contract", () => {
	afterEach(() => {
		cleanup();
		stableMocks.toastError.mockClear();
	});

	it("captures a single non-modifier key in single mode (Insert)", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="single"
				aria-label="Dictation key"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "Insert", key: "Insert", type: "keydown" });
		dispatchKey({ code: "Insert", key: "Insert", type: "keyup" });

		expect(onChange).toHaveBeenCalledWith("<insert>");
	});

	it("refuses Delete, which would delete text on every press", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="single"
				aria-label="Dictation key"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "Delete", key: "Delete", type: "keydown" });
		dispatchKey({ code: "Delete", key: "Delete", type: "keyup" });

		expect(onChange).not.toHaveBeenCalled();
		const err = await waitForError();
		expect(err).toMatch(/editing/i);
	});

	it("captures the middle mouse button", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="single"
				aria-label="Dictation key"
			/>,
		);
		await enterCaptureMode();

		dispatchMouse("mousedown");
		dispatchMouse("mouseup");

		expect(onChange).toHaveBeenCalledWith("<mouse_middle>");
	});

	it("captures a single modifier in single mode (Alt alone)", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="single"
				aria-label="Dictation key"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "AltLeft", key: "Alt", type: "keydown" });
		dispatchKey({ code: "AltLeft", key: "Alt", type: "keyup" });

		expect(onChange).toHaveBeenCalledWith("<alt>");
	});

	it("captures a modifier-only combo in combo mode (Ctrl+Shift)", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="combo"
				aria-label="Re-paste hotkey"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "ControlLeft", key: "Control", type: "keydown" });
		dispatchKey({ code: "ShiftLeft", key: "Shift", type: "keydown" });
		dispatchKey({ code: "ControlLeft", key: "Control", type: "keyup" });
		dispatchKey({ code: "ShiftLeft", key: "Shift", type: "keyup" });

		expect(onChange).toHaveBeenCalledWith("<ctrl>+<shift>");
	});

	it("refuses a multi-non-modifier combo in combo mode (Delete+End)", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="combo"
				aria-label="Re-paste hotkey"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "Delete", key: "Delete", type: "keydown" });
		dispatchKey({ code: "End", key: "End", type: "keydown" });
		dispatchKey({ code: "End", key: "End", type: "keyup" });
		expect(onChange).not.toHaveBeenCalled();
		dispatchKey({ code: "Delete", key: "Delete", type: "keyup" });

		expect(onChange).not.toHaveBeenCalled();
		const err = await waitForError();
		expect(err).toMatch(/Delete\+End/);
		expect(err).toMatch(/single key/i);
	});

	it("is release-order independent: Ctrl+Shift release order doesn't matter", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="combo"
				aria-label="Re-paste hotkey"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "ShiftLeft", key: "Shift", type: "keydown" });
		dispatchKey({ code: "ControlLeft", key: "Control", type: "keydown" });
		dispatchKey({ code: "ShiftLeft", key: "Shift", type: "keyup" });
		dispatchKey({ code: "ControlLeft", key: "Control", type: "keyup" });

		expect(onChange).toHaveBeenCalledWith("<ctrl>+<shift>");
	});

	it("captures Ctrl+Alt+U in combo mode", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="combo"
				aria-label="Re-paste hotkey"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "ControlLeft", key: "Control", type: "keydown" });
		dispatchKey({ code: "AltLeft", key: "Alt", type: "keydown" });
		dispatchKey({
			code: "KeyU",
			key: "u",
			ctrlKey: true,
			altKey: true,
			type: "keydown",
		});
		dispatchKey({
			code: "KeyU",
			key: "u",
			ctrlKey: true,
			altKey: true,
			type: "keyup",
		});

		expect(onChange).toHaveBeenCalledWith("<ctrl>+<alt>+<u>");
	});

	it("HOTKEY-FULLMSG-001: shows full combo in error when Shift+Z pressed in single mode", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="single"
				aria-label="Dictation key"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "ShiftLeft", key: "Shift", type: "keydown" });
		dispatchKey({
			code: "KeyZ",
			key: "z",
			shiftKey: true,
			type: "keydown",
		});
		dispatchKey({
			code: "KeyZ",
			key: "z",
			shiftKey: true,
			type: "keyup",
		});

		expect(onChange).not.toHaveBeenCalled();
		const err = await waitForError();
		expect(err).toMatch(/Shift\+Z/);
		const calls = stableMocks.toastError.mock.calls;
		const node = calls[calls.length - 1]?.[0] as {
			props?: { hotkeyLabel?: string };
		};
		expect(node.props?.hotkeyLabel).toBe("Shift+Z");
	});

	it("HOTKEY-FULLMSG-001: shows full combo in error when unsupported key pressed with modifiers", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="single"
				aria-label="Dictation key"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "ShiftLeft", key: "Shift", type: "keydown" });
		dispatchKey({
			code: "F24",
			key: "F24",
			shiftKey: true,
			type: "keydown",
		});

		expect(onChange).not.toHaveBeenCalled();
		const err = await waitForError();
		expect(err).toMatch(/Shift\+F24/);
		expect(err).toMatch(/not supported/i);
	});

	it("ESC cancels capture without committing (preserved ESC-KEYUP-FIX)", async () => {
		const onChange = vi.fn();
		const onCaptureEnd = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="single"
				aria-label="Dictation key"
				onCaptureEnd={onCaptureEnd}
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "Escape", key: "Escape", type: "keydown" });
		expect(onChange).not.toHaveBeenCalled();
		expect(onCaptureEnd).not.toHaveBeenCalled();

		dispatchKey({ code: "Escape", key: "Escape", type: "keyup" });

		expect(onChange).not.toHaveBeenCalled();
		expect(onCaptureEnd).toHaveBeenCalledTimes(1);
	});

	it("rejects single-letter hotkey in single mode (e.g. <z>)", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="single"
				aria-label="Dictation key"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "KeyZ", key: "z", type: "keydown" });
		dispatchKey({ code: "KeyZ", key: "z", type: "keyup" });

		expect(onChange).not.toHaveBeenCalled();
		await waitForError();
	});
});

// Notifications render in their own portal on <body>, outside the picker,
// so a naive click-away check aborted capture on the first toast click.
describe("HotkeyPicker, click-away handling", () => {
	afterEach(() => {
		cleanup();
	});

	it("keeps capture open when a notification is clicked, still cancels on a real outside click", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="single"
				aria-label="Dictation key"
			/>,
		);
		await enterCaptureMode();

		const toaster = document.createElement("section");
		toaster.setAttribute("data-sonner-toaster", "");
		const toast = document.createElement("li");
		toaster.appendChild(toast);
		document.body.appendChild(toaster);

		try {
			act(() => {
				toast.dispatchEvent(
					new MouseEvent("pointerdown", { bubbles: true, cancelable: true }),
				);
			});
			// Still capturing, the notification click only dismissed a toast.
			expect(
				screen.getByRole("button", { name: /cancel recording/i }),
			).toBeInTheDocument();

			act(() => {
				document.body.dispatchEvent(
					new MouseEvent("pointerdown", { bubbles: true, cancelable: true }),
				);
			});
			expect(
				await screen.findByRole("button", { name: /record new hotkey/i }),
			).toBeInTheDocument();
		} finally {
			toaster.remove();
		}
	});
});

// Chrome sizes the pill from its content: the resting state holds a keycap
// chip, the capture state a shorter text line, so without a pinned floor the
// blue button came out visibly shorter than the button it replaced.
describe("HotkeyPicker, capture button geometry", () => {
	afterEach(() => {
		cleanup();
	});

	it("keeps the capture button's box identical to the resting button", async () => {
		render(
			<HotkeyPicker
				value="<caps_lock>"
				onChange={vi.fn()}
				mode="single"
				aria-label="Dictation key"
			/>,
		);
		const resting = screen.getByRole("button", { name: /record new hotkey/i });
		expect(resting.className).toContain("min-h-9");

		await enterCaptureMode();

		const recording = screen.getByRole("button", {
			name: /cancel recording/i,
		});
		expect(recording.className).toBe(resting.className);
	});
});

// Push-to-talk is a cross-field rule (mode + key), so the picker must show
// the incompatibility at capture time instead of letting `set_config`
// reject the pair after the user has already committed it.
describe("HotkeyPicker, push-to-talk contract", () => {
	afterEach(() => {
		cleanup();
	});

	it("refuses modifier-only capture when push-to-talk is active", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="single"
				pushToTalk
				aria-label="Dictation key"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "AltLeft", key: "Alt", type: "keydown" });
		dispatchKey({ code: "AltLeft", key: "Alt", type: "keyup" });

		expect(onChange).not.toHaveBeenCalled();
		const err = await waitForError();
		expect(err).toMatch(/push-to-talk/i);
	});

	it("still captures a release-reporting key in push-to-talk mode", async () => {
		const onChange = vi.fn();
		render(
			<HotkeyPicker
				value=""
				onChange={onChange}
				mode="single"
				pushToTalk
				aria-label="Dictation key"
			/>,
		);
		await enterCaptureMode();

		dispatchKey({ code: "Insert", key: "Insert", type: "keydown" });
		dispatchKey({ code: "Insert", key: "Insert", type: "keyup" });

		expect(onChange).toHaveBeenCalledWith("<insert>");
	});
});
