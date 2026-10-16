import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
	LIVE_LISTEN_DEFAULT_LEVEL,
	LIVE_LISTEN_MAX,
	previewGain,
	useLiveListen,
} from "../useLiveListen";

// ── Mocks ─────────────────────────────────────────────────────────
// Minimal AudioContext double: only the surface useLiveListen touches.

interface MockTrack {
	stop: ReturnType<typeof vi.fn>;
}

interface MockStream {
	getTracks: () => MockTrack[];
}

function makeMocks() {
	const tracks: MockTrack[] = [{ stop: vi.fn() }, { stop: vi.fn() }];
	const stream: MockStream = { getTracks: () => tracks };
	const gainNode = {
		gain: { value: 0 },
		connect: vi.fn(),
		disconnect: vi.fn(),
	};
	const limiterNode = {
		threshold: { value: 0 },
		knee: { value: 0 },
		ratio: { value: 0 },
		attack: { value: 0 },
		release: { value: 0 },
		connect: vi.fn(),
		disconnect: vi.fn(),
	};
	const sourceNode = { connect: vi.fn(), disconnect: vi.fn() };
	const ctx = {
		state: "running",
		resume: vi.fn().mockResolvedValue(undefined),
		close: vi.fn().mockResolvedValue(undefined),
		createMediaStreamSource: vi.fn().mockReturnValue(sourceNode),
		createGain: vi.fn().mockReturnValue(gainNode),
		createDynamicsCompressor: vi.fn().mockReturnValue(limiterNode),
		destination: {},
	};
	const getUserMedia = vi.fn().mockResolvedValue(stream);
	const enumerateDevices = vi.fn().mockResolvedValue([]);
	return {
		tracks,
		stream,
		gainNode,
		limiterNode,
		sourceNode,
		ctx,
		getUserMedia,
		enumerateDevices,
	};
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
	// Real class (not vi.fn): `new` on a bare vi.fn trips the
	// "mock did not use function or class" warning, and stubGlobal does
	// not reach `window.AudioContext` in jsdom (repo precedent in
	// renderer-perf-regressions.test.tsx assigns window directly).
	class MockAudioContext {
		state = "running";
		destination = {};
		resume = m.ctx.resume;
		close = m.ctx.close;
		createMediaStreamSource = m.ctx.createMediaStreamSource;
		createGain = m.ctx.createGain;
		createDynamicsCompressor = m.ctx.createDynamicsCompressor;
	}
	Object.defineProperty(window, "AudioContext", {
		value: MockAudioContext,
		configurable: true,
		writable: true,
	});
}

function flush() {
	return act(async () => {
		await new Promise<void>((resolve) => setTimeout(resolve, 0));
	});
}

describe("useLiveListen", () => {
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

	it("starts the capped passthrough graph on toggle (source -> gain -> limiter -> destination)", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		act(() => {
			result.current.toggle();
		});
		expect(result.current.starting).toBe(true);
		await flush();

		expect(result.current.listening).toBe(true);
		expect(result.current.error).toBeNull();
		// S2: the browser's own canceller is asked for; NS and AGC stay OFF
		// so they cannot fight the user's filter tuning or move gain.
		expect(mocks.getUserMedia).toHaveBeenCalledWith({
			audio: {
				echoCancellation: true,
				noiseSuppression: false,
				autoGainControl: false,
			},
		});
		// S1: the preview is the user level times the hard ceiling, well
		// below the old fixed 0.8 that rang on laptop speakers.
		expect(mocks.gainNode.gain.value).toBe(
			previewGain(LIVE_LISTEN_DEFAULT_LEVEL),
		);
		expect(mocks.gainNode.gain.value).toBeLessThan(0.8);
		expect(mocks.sourceNode.connect).toHaveBeenCalledWith(mocks.gainNode);
		expect(mocks.gainNode.connect).toHaveBeenCalledWith(mocks.limiterNode);
		expect(mocks.limiterNode.connect).toHaveBeenCalledWith(
			mocks.ctx.destination,
		);
		// Ceiling node configured as a fast limiter, not an effect.
		expect(mocks.limiterNode.ratio.value).toBeGreaterThanOrEqual(20);
		expect(mocks.limiterNode.attack.value).toBeLessThanOrEqual(0.005);
	});

	it("never lets a level exceed the hard ceiling", async () => {
		const { result } = renderHook(() =>
			useLiveListen({
				activeMicName: null,
				isSystemDefault: true,
				level: 1,
			}),
		);

		act(() => {
			result.current.toggle();
		});
		await flush();

		expect(mocks.gainNode.gain.value).toBe(LIVE_LISTEN_MAX);
	});

	it("applies the configured preview level", async () => {
		const { result } = renderHook(() =>
			useLiveListen({
				activeMicName: null,
				isSystemDefault: true,
				level: 0.2,
			}),
		);

		act(() => {
			result.current.toggle();
		});
		await flush();

		expect(mocks.gainNode.gain.value).toBeCloseTo(0.2 * LIVE_LISTEN_MAX);
	});

	it("follows a level change while listening (config arrives late)", async () => {
		const { result, rerender } = renderHook(
			({ level }: { level: number }) =>
				useLiveListen({ activeMicName: null, isSystemDefault: true, level }),
			{ initialProps: { level: LIVE_LISTEN_DEFAULT_LEVEL } },
		);

		act(() => {
			result.current.toggle();
		});
		await flush();
		expect(mocks.gainNode.gain.value).toBe(
			previewGain(LIVE_LISTEN_DEFAULT_LEVEL),
		);

		rerender({ level: 1 });
		expect(mocks.gainNode.gain.value).toBe(LIVE_LISTEN_MAX);
	});

	it("stops everything on second toggle (tracks, nodes, context)", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		act(() => {
			result.current.toggle();
		});
		await flush();
		act(() => {
			result.current.toggle();
		});

		expect(result.current.listening).toBe(false);
		for (const track of mocks.tracks) expect(track.stop).toHaveBeenCalled();
		expect(mocks.sourceNode.disconnect).toHaveBeenCalled();
		expect(mocks.gainNode.disconnect).toHaveBeenCalled();
		expect(mocks.limiterNode.disconnect).toHaveBeenCalled();
		expect(mocks.ctx.close).toHaveBeenCalled();
	});

	it("tears down on unmount while listening", async () => {
		const { result, unmount } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		act(() => {
			result.current.toggle();
		});
		await flush();
		expect(result.current.listening).toBe(true);

		unmount();
		for (const track of mocks.tracks) expect(track.stop).toHaveBeenCalled();
		expect(mocks.ctx.close).toHaveBeenCalled();
	});

	it("reports denied when the browser rejects the permission prompt", async () => {
		const err = new DOMException("denied", "NotAllowedError");
		mocks.getUserMedia.mockRejectedValueOnce(err);
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		act(() => {
			result.current.toggle();
		});
		await flush();

		expect(result.current.listening).toBe(false);
		expect(result.current.error).toBe("denied");
	});

	it("reports unavailable when getUserMedia does not exist", async () => {
		Object.defineProperty(navigator, "mediaDevices", {
			value: {},
			configurable: true,
			writable: true,
		});
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		act(() => {
			result.current.toggle();
		});
		await flush();

		expect(result.current.listening).toBe(false);
		expect(result.current.error).toBe("unavailable");
	});

	it("stops when the stopSignal changes (test start / device switch)", async () => {
		let signal = 0;
		const { result, rerender } = renderHook(
			({ stopSignal }: { stopSignal: number }) =>
				useLiveListen({
					activeMicName: null,
					isSystemDefault: true,
					stopSignal,
				}),
			{ initialProps: { stopSignal: signal } },
		);

		act(() => {
			result.current.toggle();
		});
		await flush();
		expect(result.current.listening).toBe(true);

		signal += 1;
		rerender({ stopSignal: signal });
		expect(result.current.listening).toBe(false);
		for (const track of mocks.tracks) expect(track.stop).toHaveBeenCalled();
	});

	it("stops when the tab hides (C-BG-1)", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		act(() => {
			result.current.toggle();
		});
		await flush();
		expect(result.current.listening).toBe(true);

		Object.defineProperty(document, "visibilityState", {
			value: "hidden",
			configurable: true,
		});
		act(() => {
			document.dispatchEvent(new Event("visibilitychange"));
		});
		Object.defineProperty(document, "visibilityState", {
			value: "visible",
			configurable: true,
		});

		expect(result.current.listening).toBe(false);
		for (const track of mocks.tracks) expect(track.stop).toHaveBeenCalled();
	});

	it("picks the browser input matching the selected mic label", async () => {
		mocks.enumerateDevices.mockResolvedValue([
			{ kind: "audioinput", label: "Default Microphone", deviceId: "def" },
			{ kind: "audioinput", label: "USB Headset Microphone", deviceId: "usb1" },
		]);
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: "USB Headset", isSystemDefault: false }),
		);

		act(() => {
			result.current.toggle();
		});
		await flush();

		expect(result.current.listening).toBe(true);
		expect(mocks.getUserMedia).toHaveBeenCalledWith({
			audio: {
				deviceId: { exact: "usb1" },
				echoCancellation: true,
				noiseSuppression: false,
				autoGainControl: false,
			},
		});
	});
});

describe("previewGain", () => {
	it("scales the user level by the ceiling and clamps out-of-range input", () => {
		expect(previewGain(LIVE_LISTEN_DEFAULT_LEVEL)).toBeCloseTo(
			LIVE_LISTEN_DEFAULT_LEVEL * LIVE_LISTEN_MAX,
		);
		expect(previewGain(1)).toBe(LIVE_LISTEN_MAX);
		expect(previewGain(4)).toBe(LIVE_LISTEN_MAX);
		expect(previewGain(-1)).toBe(0);
	});

	it("falls back to the default level for a non-finite value", () => {
		expect(previewGain(Number.NaN)).toBe(
			LIVE_LISTEN_DEFAULT_LEVEL * LIVE_LISTEN_MAX,
		);
	});
});
