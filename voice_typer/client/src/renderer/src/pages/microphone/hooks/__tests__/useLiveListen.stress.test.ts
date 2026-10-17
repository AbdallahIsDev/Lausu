import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useLiveListen } from "../useLiveListen";

// ── Mocks ─────────────────────────────────────────────────────────
// Same shape as useLiveListen.test.ts: real class so `new` works, and a
// `window.python` bridge that records every `live_preview` toggle.

const ENABLED_REPLY = {
	active: true,
	monitoring: true,
	sample_rate: 48000,
	filtered: true,
};

interface CreatedContext {
	close: ReturnType<typeof vi.fn>;
}

interface BridgeMock {
	call: ReturnType<typeof vi.fn>;
	onEvent: ReturnType<typeof vi.fn>;
	enables: () => number;
	disables: () => number;
}

function makeMocks() {
	const created: CreatedContext[] = [];

	class MockAudioContext {
		state = "running";
		currentTime = 0;
		destination = { id: "destination" };
		resume = vi.fn().mockResolvedValue(undefined);
		close: ReturnType<typeof vi.fn>;
		createGain = vi.fn(() => ({
			gain: { value: 0 },
			connect: vi.fn(),
			disconnect: vi.fn(),
		}));
		createDynamicsCompressor = vi.fn(() => ({
			threshold: { value: 0 },
			knee: { value: 0 },
			ratio: { value: 0 },
			attack: { value: 0 },
			release: { value: 0 },
			connect: vi.fn(),
			disconnect: vi.fn(),
		}));
		createBuffer = vi.fn((_channels: number, length: number, rate: number) => ({
			duration: length / rate,
			length,
			sampleRate: rate,
			copyToChannel: vi.fn(),
		}));
		createBufferSource = vi.fn(() => ({
			buffer: null,
			onended: null,
			connect: vi.fn(),
			disconnect: vi.fn(),
			start: vi.fn(),
			stop: vi.fn(),
		}));
		constructor() {
			this.close = vi.fn().mockResolvedValue(undefined);
			created.push({ close: this.close });
		}
	}

	return { created, MockAudioContext };
}

type Mocks = ReturnType<typeof makeMocks>;
let mocks: Mocks;
let bridge: BridgeMock;

function installAudio(m: Mocks) {
	Object.defineProperty(window, "AudioContext", {
		value: m.MockAudioContext,
		configurable: true,
		writable: true,
	});
}

function installBridge(
	handler: (req: {
		type: string;
		data?: Record<string, unknown>;
	}) => unknown = (req) =>
		req.data?.enabled ? ENABLED_REPLY : { active: false, monitoring: true },
): BridgeMock {
	const call = vi.fn(
		async (req: { type: string; data?: Record<string, unknown> }) =>
			handler(req),
	);
	const onEvent = vi.fn(() => () => {});
	(window as unknown as { python?: unknown }).python = { call, onEvent };
	const toggles = () =>
		call.mock.calls.filter(
			(c) => (c[0] as { type: string }).type === "live_preview",
		);
	return {
		call,
		onEvent,
		enables: () =>
			toggles().filter(
				(c) =>
					(c[0] as { data?: { enabled?: boolean } }).data?.enabled === true,
			).length,
		disables: () =>
			toggles().filter(
				(c) =>
					(c[0] as { data?: { enabled?: boolean } }).data?.enabled === false,
			).length,
	};
}

function flush() {
	return act(async () => {
		await new Promise<void>((resolve) => setTimeout(resolve, 0));
	});
}

describe("useLiveListen stress (backend-streamed)", () => {
	beforeEach(() => {
		mocks = makeMocks();
		installAudio(mocks);
		bridge = installBridge();
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
		delete (window as unknown as { python?: unknown }).python;
		Object.defineProperty(window, "AudioContext", {
			value: undefined,
			configurable: true,
			writable: true,
		});
	});

	it("toggle storm ends stopped, with every context closed and the stream off", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		// 10 rapid toggles with no awaits between them.
		for (let i = 0; i < 10; i++) {
			act(() => {
				result.current.toggle();
			});
		}
		await flush();
		await flush();

		expect(result.current.listening).toBe(false);
		expect(result.current.starting).toBe(false);
		for (const ctx of mocks.created) expect(ctx.close).toHaveBeenCalled();
		// The stream is never left enabled: the last word is always "off".
		expect(bridge.disables()).toBeGreaterThanOrEqual(1);
		expect(bridge.enables()).toBe(bridge.disables());
	});

	it("stop during a pending enable releases the late reply", async () => {
		let release!: (value: unknown) => void;
		bridge = installBridge(
			() =>
				new Promise((resolve) => {
					release = resolve;
				}),
		);
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		act(() => {
			result.current.toggle();
		});
		expect(result.current.starting).toBe(true);
		act(() => {
			result.current.toggle();
		});

		await act(async () => {
			release(ENABLED_REPLY);
			await new Promise<void>((resolve) => setTimeout(resolve, 0));
		});

		expect(result.current.listening).toBe(false);
		expect(result.current.starting).toBe(false);
		// The enable that landed after the stop is undone.
		expect(bridge.disables()).toBe(1);
		for (const ctx of mocks.created) expect(ctx.close).toHaveBeenCalled();
	});

	it("unmount during a pending enable warns nothing and leaves the stream off", async () => {
		let release!: (value: unknown) => void;
		bridge = installBridge(
			() =>
				new Promise((resolve) => {
					release = resolve;
				}),
		);
		const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
		const { result, unmount } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		act(() => {
			result.current.toggle();
		});
		unmount();
		await act(async () => {
			release(ENABLED_REPLY);
			await new Promise<void>((resolve) => setTimeout(resolve, 0));
		});

		expect(bridge.disables()).toBe(1);
		const reactWarnings = errSpy.mock.calls.filter(
			(args) =>
				typeof args[0] === "string" && args[0].includes("unmounted component"),
		);
		expect(reactWarnings.length).toBe(0);
		errSpy.mockRestore();
	});

	it("five sequential cycles each enable, build and release exactly one graph", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		for (let i = 0; i < 5; i++) {
			act(() => {
				result.current.toggle();
			});
			await flush();
			expect(result.current.listening).toBe(true);
			act(() => {
				result.current.toggle();
			});
			expect(result.current.listening).toBe(false);
		}

		expect(bridge.enables()).toBe(5);
		expect(bridge.disables()).toBe(5);
		expect(mocks.created.length).toBe(5);
		for (const ctx of mocks.created) expect(ctx.close).toHaveBeenCalledTimes(1);
		expect(result.current.error).toBeNull();
	});
});
