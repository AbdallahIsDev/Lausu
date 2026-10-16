import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useLiveListen } from "../useLiveListen";

// ── Mocks ─────────────────────────────────────────────────────────
// Same shape as useLiveListen.test.ts: real class so `new` works.

interface MockTrack {
	stop: ReturnType<typeof vi.fn>;
}

function makeMocks() {
	const created: {
		tracks: MockTrack[];
		close: ReturnType<typeof vi.fn>;
		ctxBuilt: boolean;
	}[] = [];
	const getUserMedia = vi.fn().mockImplementation(async () => {
		const tracks: MockTrack[] = [{ stop: vi.fn() }, { stop: vi.fn() }];
		const stream = { getTracks: () => tracks };
		created.push({
			tracks,
			close: vi.fn().mockResolvedValue(undefined),
			ctxBuilt: false,
		});
		return stream;
	});
	const enumerateDevices = vi.fn().mockResolvedValue([]);
	const gainNode = () => ({
		gain: { value: 0 },
		connect: vi.fn(),
		disconnect: vi.fn(),
	});
	const sourceNode = () => ({ connect: vi.fn(), disconnect: vi.fn() });
	const limiterNode = () => ({
		threshold: { value: 0 },
		knee: { value: 0 },
		ratio: { value: 0 },
		attack: { value: 0 },
		release: { value: 0 },
		connect: vi.fn(),
		disconnect: vi.fn(),
	});
	class MockAudioContext {
		state = "running";
		destination = {};
		resume = vi.fn().mockResolvedValue(undefined);
		close: ReturnType<typeof vi.fn>;
		createMediaStreamSource = vi.fn().mockImplementation(() => sourceNode());
		createGain = vi.fn().mockImplementation(() => gainNode());
		createDynamicsCompressor = vi.fn().mockImplementation(() => limiterNode());
		constructor() {
			const entry = created[created.length - 1];
			if (entry) entry.ctxBuilt = true;
			this.close = entry?.close ?? vi.fn().mockResolvedValue(undefined);
		}
	}
	return { created, getUserMedia, enumerateDevices, MockAudioContext };
}

type Mocks = ReturnType<typeof makeMocks>;
let mocks: Mocks;

function installMocks(m: Mocks) {
	Object.defineProperty(navigator, "mediaDevices", {
		value: {
			getUserMedia: m.getUserMedia,
			enumerateDevices: m.enumerateDevices,
		},
		configurable: true,
		writable: true,
	});
	Object.defineProperty(window, "AudioContext", {
		value: m.MockAudioContext,
		configurable: true,
		writable: true,
	});
}

function flush() {
	return act(async () => {
		await new Promise<void>((resolve) => setTimeout(resolve, 0));
	});
}

describe("useLiveListen stress", () => {
	beforeEach(() => {
		mocks = makeMocks();
		installMocks(mocks);
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
		Object.defineProperty(window, "AudioContext", {
			value: undefined,
			configurable: true,
			writable: true,
		});
	});

	it("toggle storm ends in a consistent stopped state with no leaks", async () => {
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
		// Every created stream was stopped; every BUILT context closed.
		// (Late streams from superseded starts never reach the context
		// step by design: nothing built, nothing to close.)
		for (const c of mocks.created) {
			for (const track of c.tracks) expect(track.stop).toHaveBeenCalled();
			if (c.ctxBuilt) expect(c.close).toHaveBeenCalled();
		}
	});

	it("stop during a pending permission prompt releases the late stream", async () => {
		let release!: (s: unknown) => void;
		mocks.getUserMedia.mockImplementationOnce(
			() =>
				new Promise((resolve) => {
					release = resolve as (s: unknown) => void;
				}),
		);
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		act(() => {
			result.current.toggle();
		});
		expect(result.current.starting).toBe(true);
		// Stop BEFORE the permission resolves.
		act(() => {
			result.current.toggle();
		});
		// Permission granted late.
		const stopMock = vi.fn();
		const tracks = [{ stop: stopMock }];
		await act(async () => {
			release({ getTracks: () => tracks });
			await new Promise<void>((resolve) => setTimeout(resolve, 0));
		});

		expect(result.current.listening).toBe(false);
		expect(result.current.starting).toBe(false);
		expect(stopMock).toHaveBeenCalled();
	});

	it("unmount during a pending start warns nothing and leaks nothing", async () => {
		let release!: (s: unknown) => void;
		mocks.getUserMedia.mockImplementationOnce(
			() =>
				new Promise((resolve) => {
					release = resolve as (s: unknown) => void;
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
		const stopMock = vi.fn();
		const tracks = [{ stop: stopMock }];
		await act(async () => {
			release({ getTracks: () => tracks });
			await new Promise<void>((resolve) => setTimeout(resolve, 0));
		});

		expect(stopMock).toHaveBeenCalled();
		const reactWarnings = errSpy.mock.calls.filter(
			(args) =>
				typeof args[0] === "string" && args[0].includes("unmounted component"),
		);
		expect(reactWarnings.length).toBe(0);
		errSpy.mockRestore();
	});

	it("five sequential cycles each build and release exactly one graph", async () => {
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

		expect(mocks.getUserMedia).toHaveBeenCalledTimes(5);
		expect(mocks.created.length).toBe(5);
		for (const c of mocks.created) {
			for (const track of c.tracks) expect(track.stop).toHaveBeenCalledTimes(1);
			expect(c.close).toHaveBeenCalledTimes(1);
		}
		expect(result.current.error).toBeNull();
	});
});
