import { act, cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	DEVELOPER_UNLOCK_PRESS_COUNT,
	DEVELOPER_UNLOCK_WINDOW_MS,
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

function renderUnlock() {
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
		key: opts.key ?? "d",
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

beforeEach(() => {
	mockCall.mockReset();
	mockCall.mockImplementation((command: string) => {
		if (command === "set_config") return Promise.resolve({ type: "ack" });
		if (command === "get_config") {
			return Promise.resolve({ developer_mode: true, model_size: "small" });
		}
		return Promise.resolve(undefined);
	});
	toastSpies.success.mockClear();
	toastSpies.error.mockClear();
	useAppStore.setState({ config: null });
});

afterEach(() => {
	cleanup();
	vi.useRealTimers();
});

describe("useDeveloperModeUnlock", () => {
	it("unlocks after the configured number of presses", async () => {
		renderUnlock();
		for (let i = 0; i < DEVELOPER_UNLOCK_PRESS_COUNT; i += 1) press();
		await waitFor(() => {
			expect(mockCall).toHaveBeenCalledWith("set_config", {
				developer_mode: true,
			});
		});
		expect(mockCall).toHaveBeenCalledWith("get_config");
		expect(useAppStore.getState().config?.developer_mode).toBe(true);
		expect(toastSpies.success).toHaveBeenCalled();
	});

	it("does nothing before the last press", () => {
		renderUnlock();
		for (let i = 0; i < DEVELOPER_UNLOCK_PRESS_COUNT - 1; i += 1) press();
		expect(mockCall).not.toHaveBeenCalled();
	});

	it("ignores presses outside the modifier combination", () => {
		renderUnlock();
		for (let i = 0; i < DEVELOPER_UNLOCK_PRESS_COUNT; i += 1) {
			press({ alt: false });
			press({ shift: false });
			press({ meta: true });
		}
		expect(mockCall).not.toHaveBeenCalled();
	});

	it("ignores auto-repeat from a held key", () => {
		renderUnlock();
		for (let i = 0; i < DEVELOPER_UNLOCK_PRESS_COUNT; i += 1) {
			press({ repeat: true });
		}
		expect(mockCall).not.toHaveBeenCalled();
	});

	it("drops presses that fall outside the window", () => {
		vi.useFakeTimers();
		vi.setSystemTime(0);
		renderUnlock();
		press();
		vi.setSystemTime(DEVELOPER_UNLOCK_WINDOW_MS / 2);
		press();
		vi.setSystemTime(DEVELOPER_UNLOCK_WINDOW_MS * 3);
		press();
		expect(mockCall).not.toHaveBeenCalled();
	});

	it("surfaces a failed unlock and leaves the store locked", async () => {
		mockCall.mockImplementation((command: string) => {
			if (command === "set_config") return Promise.reject(new Error("refused"));
			return Promise.resolve({ developer_mode: false });
		});
		renderUnlock();
		for (let i = 0; i < DEVELOPER_UNLOCK_PRESS_COUNT; i += 1) press();
		await waitFor(() => {
			expect(toastSpies.error).toHaveBeenCalled();
		});
		expect(useAppStore.getState().config?.developer_mode).not.toBe(true);
	});

	it("does not listen once the flag is already on", () => {
		useAppStore.setState({ config: { developer_mode: true } as never });
		renderUnlock();
		for (let i = 0; i < DEVELOPER_UNLOCK_PRESS_COUNT; i += 1) press();
		expect(mockCall).not.toHaveBeenCalled();
	});

	it("does not write twice while an unlock is in flight", async () => {
		let resolveSet: (value: unknown) => void = () => undefined;
		mockCall.mockImplementation((command: string) => {
			if (command === "set_config") {
				return new Promise((resolve) => {
					resolveSet = resolve;
				});
			}
			return Promise.resolve({ developer_mode: false });
		});
		renderUnlock();
		for (let i = 0; i < DEVELOPER_UNLOCK_PRESS_COUNT; i += 1) press();
		for (let i = 0; i < DEVELOPER_UNLOCK_PRESS_COUNT; i += 1) press();
		await act(async () => {
			resolveSet({ type: "ack" });
		});
		expect(
			mockCall.mock.calls.filter(([command]) => command === "set_config"),
		).toHaveLength(1);
	});
});
