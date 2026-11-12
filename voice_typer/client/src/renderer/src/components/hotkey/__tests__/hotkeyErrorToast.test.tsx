import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { sonnerMock, stableMocks } from "@/__tests__/helpers/stableMocks";
import {
	dismissHotkeyErrorToast,
	HOTKEY_ERROR_TOAST_ID,
	HotkeyErrorToastMessage,
	showHotkeyErrorToast,
} from "../hotkeyErrorToast";

vi.mock("sonner", () => sonnerMock());

const MESSAGE =
	'"Shift+Z" can\'t be used as a dictation key: dictation key must be a single key. Use the re-paste key picker for combos.';

afterEach(() => {
	cleanup();
	stableMocks.toastError.mockClear();
	stableMocks.toastDismiss.mockClear();
});

describe("HotkeyErrorToastMessage", () => {
	it("renders the attempted hotkey as keycap chips instead of plain text", () => {
		const { container } = render(
			<HotkeyErrorToastMessage message={MESSAGE} hotkeyLabel="Shift+Z" />,
		);
		expect(container.querySelectorAll('[data-slot="kbd"]')).toHaveLength(2);
		expect(container.textContent).toBe(
			"ShiftZ can't be used as a dictation key: dictation key must be a single key. Use the re-paste key picker for combos.",
		);
	});

	it("drops the quotes around the replaced hotkey and colours the copy as an error", () => {
		const { container } = render(
			<HotkeyErrorToastMessage message={MESSAGE} hotkeyLabel="Shift+Z" />,
		);
		expect(container.textContent).not.toContain('"');
		expect(container.firstElementChild?.className).toContain(
			"text-destructive",
		);
	});

	it("keeps the full message when the label is absent from it", () => {
		const { container } = render(
			<HotkeyErrorToastMessage
				message="AltGr can't be used as a hotkey"
				hotkeyLabel="Ctrl+Q"
			/>,
		);
		expect(container.querySelectorAll('[data-slot="kbd"]')).toHaveLength(0);
		expect(container.textContent).toBe("AltGr can't be used as a hotkey");
	});
});

describe("showHotkeyErrorToast", () => {
	it("sends the rich message through one replaceable toast id", () => {
		showHotkeyErrorToast(MESSAGE, "Shift+Z");
		expect(stableMocks.toastError).toHaveBeenCalledTimes(1);
		const [node, options] = stableMocks.toastError.mock.calls[0] as [
			{ props: { message: string; hotkeyLabel: string } },
			{ id: string },
		];
		expect(options).toEqual({ id: HOTKEY_ERROR_TOAST_ID });
		expect(node.props.message).toBe(MESSAGE);
		expect(node.props.hotkeyLabel).toBe("Shift+Z");
	});

	it("dismisses the hotkey error toast by its stable id", () => {
		dismissHotkeyErrorToast();
		expect(stableMocks.toastDismiss).toHaveBeenCalledWith(
			HOTKEY_ERROR_TOAST_ID,
		);
	});
});
