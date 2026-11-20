import { act, cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	DEVELOPER_TOGGLE_KEY,
	useDeveloperModeUnlock,
} from "@/hooks/useDeveloperModeUnlock";
import { useAppStore } from "@/stores/appStore";

const { toastSpies } = vi.hoisted(() => ({
	toastSpies: {
		success: vi.fn(),
		error: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
	},
}));

vi.mock("sonner", () => ({
	toast: {
		success: toastSpies.success,
		error: toastSpies.error,
		warning: toastSpies.warning,
		info: toastSpies.info,
	},
}));

vi.mock("@/i18n/i18n", () => ({
	t: (key: string) => `[t]${key}`,
	useT: () => (key: string) => `[t]${key}`,
}));

const mockCall = vi.fn();

function renderToggle() {
	function Probe() {
		useDeveloperModeUnlock(mockCall);
		return null;
	}
	render(<Probe />);
}

function press(
	opts: {
		key?: string;
		ctrl?: boolean;
		shift?: boolean;
		alt?: boolean;
		meta?: boolean;
		repeat?: boolean;
	} = {},
) {
	const event = {
		key: opts.key ?? DEVELOPER_TOGGLE_KEY,
		ctrlKey: opts.ctrl ?? true,
		shiftKey: opts.shift ?? true,
		altKey: opts.alt ?? true,
		metaKey: opts.meta ?? false,
		repeat: opts.repeat ?? false,
	};
	act(() => {
		window.dispatchEvent(new KeyboardEvent("keydown", event));
	});
}

function triplePress() {
	press();
	press();
	press();
}

beforeEach(() => {
	mockCall.mockReset();
	mockCall.mockImplementation((command: string, args?: unknown) => {
		if (command === "set_config") return Promise.resolve({ type: "ack", args });
		if (command === "get_config") {
			return Promise.resolve({ developer_mode: true, model_size: "small" });
		}
		return Promise.resolve(undefined);
	});
	toastSpies.success.mockClear();
	toastSpies.info.mockClear();
	toastSpies.error.mockClear();
	useAppStore.setState({ config: null });
});

afterEach(() => {
	cleanup();
	vi.useRealTimers();
});

describe("useDeveloperModeUnlock — three-press toggle", () => {
	it("requires three presses; two do nothing", async () => {
		renderToggle();
		press();
		press();
		expect(mockCall).not.toHaveBeenCalled();
		press();
		await waitFor(() => {
			expect(mockCall).toHaveBeenCalledWith("set_config", {
				developer_mode: true,
			});
		});
		expect(mockCall).toHaveBeenCalledWith("get_config");
		expect(useAppStore.getState().config?.developer_mode).toBe(true);
		expect(toastSpies.success.mock.calls[0]?.[0]).toBe("[t]plugins.unlocked");
	});

	it("does not accumulate presses outside the 1500 ms window", () => {
		vi.useFakeTimers();
		vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
		renderToggle();
		press();
		press();
		vi.setSystemTime(new Date("2026-01-01T00:00:03Z"));
		press();
		expect(mockCall).not.toHaveBeenCalled();
		vi.useRealTimers();
	});

	it("toggles back on the next three presses while visible", async () => {
		useAppStore.setState({ config: { developer_mode: true } as never });
		renderToggle();
		triplePress();
		await waitFor(() => {
			expect(mockCall).toHaveBeenCalledWith("set_config", {
				developer_mode: false,
			});
		});
		expect(toastSpies.info.mock.calls[0]?.[0]).toBe("[t]plugins.hidden");
	});

	it("ignores presses outside the modifier combination", () => {
		renderToggle();
		press({ alt: false });
		press({ shift: false });
		press({ ctrl: false });
		press({ meta: true });
		expect(mockCall).not.toHaveBeenCalled();
	});

	it("ignores auto-repeat from a held key", () => {
		renderToggle();
		press({ repeat: true });
		press({ repeat: true });
		press({ repeat: true });
		expect(mockCall).not.toHaveBeenCalled();
	});

	it("ignores other keys", () => {
		renderToggle();
		press({ key: "k" });
		press({ key: "k" });
		press({ key: "k" });
		expect(mockCall).not.toHaveBeenCalled();
	});

	it("surfaces a failed write without leaving the flag set", async () => {
		mockCall.mockRejectedValueOnce(new Error("boom"));
		renderToggle();
		triplePress();
		await waitFor(() => {
			expect(toastSpies.error.mock.calls[0]?.[0]).toBe(
				"[t]plugins.unlockFailed",
			);
		});
		expect(useAppStore.getState().config?.developer_mode).toBeUndefined();
	});
});
