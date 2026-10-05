/**
 * Tests for useConnection, initial-probe startup grace.
 *
 * Scenario: the backend answers from a cold disk + first-import storm
 * for ~20s after launch. A lone 15s-timeout get_config mid-storm is
 * transient, not death: timeout-shaped errors within the mount grace
 * earn extra attempts and the UI stays on "connecting", never flashing
 * the "Lost connection" screen. Fast failures (pre-handshake refusal)
 * keep the plain 5-attempt budget so a truly dead backend still
 * surfaces in seconds (covered by useConnection-background-reconnect).
 */

import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
	pythonMock,
	resetStableMocks,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";

const { mockCall } = stableMocks;

vi.mock("@/hooks/usePython", () => pythonMock());

import { useConnection } from "@/hooks/useConnection";
import { _resetNavigationForTest, useNavigation } from "@/hooks/useNavigation";
import { useAppStore } from "@/stores/appStore";

const lsStub: Record<string, string> = {};
Object.defineProperty(window, "localStorage", {
	value: {
		getItem: (k: string) => lsStub[k] ?? null,
		setItem: (k: string, v: string) => {
			lsStub[k] = v;
		},
		removeItem: (k: string) => {
			delete lsStub[k];
		},
		clear: () => {
			for (const k of Object.keys(lsStub)) delete lsStub[k];
		},
	},
	configurable: true,
});

function Harness() {
	const { currentPage, navigate } = useNavigation();
	useConnection({
		call: (async (type: string, _data?: Record<string, unknown>) =>
			mockCall(type)) as unknown as <T = unknown>(
			type: string,
			data?: Record<string, unknown>,
		) => Promise<T>,
		currentPage,
		navigate,
	});
	return null;
}

function readStatus(): string {
	return useAppStore.getState().connectionStatus;
}

function rejectAllTimeouts(): void {
	mockCall.mockImplementation((type: string) => {
		if (type === "get_config")
			return Promise.reject(new Error("dispatch timeout (15s)"));
		return Promise.resolve({});
	});
}

describe("useConnection, initial-probe startup grace", () => {
	beforeEach(() => {
		resetStableMocks();
		localStorage.clear();
		_resetNavigationForTest();
		vi.resetModules();
		useAppStore.getState().setConnectionStatus("connecting");
		useAppStore.getState().setLastError(null);
	});

	afterEach(() => {
		cleanup();
		if (vi.isFakeTimers()) {
			vi.useRealTimers();
		}
	});

	it("withholds disconnected across 9 timeouts inside the grace", async () => {
		vi.useFakeTimers();
		rejectAllTimeouts();
		render(<Harness />);

		// 8 consecutive timeout failures ≈ 14s of fake time, inside the
		// 60s grace: the plain budget (5) is long exhausted, yet the
		// status must stay off "disconnected" (the 9th failure at ~16s
		// is the first one allowed to flip it).
		await act(async () => {
			await vi.advanceTimersByTimeAsync(15_000);
		});
		expect(readStatus()).not.toBe("disconnected");
	});

	it("declares disconnected once timeouts outlast the budget", async () => {
		vi.useFakeTimers();
		rejectAllTimeouts();
		render(<Harness />);

		// 10th timeout failure exhausts even the graced budget (5 + 4).
		await act(async () => {
			await vi.advanceTimersByTimeAsync(25_000);
		});
		expect(readStatus()).toBe("disconnected");
	});

	it("recovers without the death screen when a retry lands", async () => {
		vi.useFakeTimers({ shouldAdvanceTime: true });
		let calls = 0;
		mockCall.mockImplementation((type: string) => {
			if (type === "get_config") {
				calls++;
				if (calls < 3)
					return Promise.reject(new Error("dispatch timeout (15s)"));
				return Promise.resolve({ onboarding_completed: true });
			}
			if (type === "get_status") return Promise.resolve({ status: "idle" });
			if (type === "onboarding_is_first_run")
				return Promise.resolve({ is_first_run: false });
			return Promise.resolve({});
		});
		render(<Harness />);

		await act(async () => {
			await vi.advanceTimersByTimeAsync(10_000);
		});
		expect(readStatus()).toBe("connected");
	});
});
