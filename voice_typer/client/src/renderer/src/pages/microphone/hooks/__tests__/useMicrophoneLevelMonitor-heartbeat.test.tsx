/**
 * Keep-alive heartbeat: the backend auto-stops the level monitor after
 * 60s without polls, so the mic page (the stream's owner while open)
 * must re-poll periodically or its own level bar freezes. The heartbeat
 * is visibility-gated like everything else in this hook (C-BG-1).
 */
import { act, cleanup, render } from "@testing-library/react";
import type { ReactNode, RefObject } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const callMock = vi.fn();
const usePythonEventMock = vi.fn();

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({
		call: callMock,
		status: "connected",
		connectionStatus: "connected",
	}),
	usePythonEvent: usePythonEventMock,
}));

vi.mock("@/types/config", () => ({}));

function makeRefs(): {
	playingRef: RefObject<boolean>;
	testRunningRef: RefObject<boolean>;
	meterRef: RefObject<HTMLElement | null>;
} {
	const playingRef: RefObject<boolean> = { current: false };
	const testRunningRef: RefObject<boolean> = { current: false };
	const meterDiv = document.createElement("div");
	const progress = document.createElement("div");
	progress.setAttribute("role", "progressbar");
	const fill = document.createElement("div");
	progress.appendChild(fill);
	meterDiv.appendChild(progress);
	const meterRef: RefObject<HTMLElement | null> = { current: meterDiv };
	return { playingRef, testRunningRef, meterRef };
}

async function renderProbe(refs: ReturnType<typeof makeRefs>) {
	const { useMicrophoneLevelMonitor } = await import(
		"../useMicrophoneLevelMonitor"
	);
	function Probe() {
		useMicrophoneLevelMonitor({
			config: {
				microphone: null,
				voice_biometric_consent: true,
			} as unknown as Parameters<typeof useMicrophoneLevelMonitor>[0]["config"],
			playingRef: refs.playingRef,
			testRunningRef: refs.testRunningRef,
			meterRef: refs.meterRef,
		});
		return null as unknown as ReactNode;
	}
	const utils = render(<Probe />);
	return utils;
}

function setVisibility(state: string) {
	Object.defineProperty(document, "visibilityState", {
		value: state,
		configurable: true,
		writable: true,
	});
}

function levelCalls() {
	return callMock.mock.calls.filter((c) => c[0] === "microphone_test_get_level")
		.length;
}

describe("useMicrophoneLevelMonitor keep-alive heartbeat", () => {
	beforeEach(() => {
		callMock.mockResolvedValue({ level: 0, peak: 0, active: true });
		setVisibility("visible");
		vi.useFakeTimers();
	});

	afterEach(() => {
		cleanup();
		vi.useRealTimers();
		callMock.mockReset();
		usePythonEventMock.mockReset();
		setVisibility("visible");
	});

	it("re-polls about every 30s while visible", async () => {
		const refs = makeRefs();
		await renderProbe(refs);
		await act(async () => {
			await vi.advanceTimersByTimeAsync(1000);
		});
		const before = levelCalls();

		await act(async () => {
			await vi.advanceTimersByTimeAsync(31000);
		});
		expect(levelCalls()).toBeGreaterThan(before);
	});

	it("stays silent while hidden (no heartbeat, no mount poll)", async () => {
		setVisibility("hidden");
		const refs = makeRefs();
		await renderProbe(refs);
		await act(async () => {
			await vi.advanceTimersByTimeAsync(95000);
		});
		expect(levelCalls()).toBe(0);
	});

	it("stops the heartbeat on unmount", async () => {
		const refs = makeRefs();
		const utils = await renderProbe(refs);
		await act(async () => {
			await vi.advanceTimersByTimeAsync(1000);
		});
		const before = levelCalls();
		utils.unmount();
		await act(async () => {
			await vi.advanceTimersByTimeAsync(65000);
		});
		expect(levelCalls()).toBe(before);
	});
});
