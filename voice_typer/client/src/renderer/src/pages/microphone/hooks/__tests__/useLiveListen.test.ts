import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
	decodePreviewFrame,
	LIVE_LISTEN_DEFAULT_LEVEL,
	LIVE_LISTEN_MAX,
	LIVE_PREVIEW_MAX_BACKLOG_S,
	previewGain,
	useLiveListen,
} from "../useLiveListen";

// ── Mocks ─────────────────────────────────────────────────────────
// Minimal AudioContext double: only the surface useLiveListen touches. The
// hook no longer calls getUserMedia at all (the sidecar owns the mic), so the
// only browser surface left is playback.

interface MockGainNode {
	gain: { value: number };
	connect: ReturnType<typeof vi.fn>;
	disconnect: ReturnType<typeof vi.fn>;
}

interface MockLimiterNode {
	threshold: { value: number };
	knee: { value: number };
	ratio: { value: number };
	attack: { value: number };
	release: { value: number };
	connect: ReturnType<typeof vi.fn>;
	disconnect: ReturnType<typeof vi.fn>;
}

interface MockBuffer {
	duration: number;
	length: number;
	sampleRate: number;
	copyToChannel: ReturnType<typeof vi.fn>;
}

interface MockSourceNode {
	buffer: MockBuffer | null;
	onended: (() => void) | null;
	connect: ReturnType<typeof vi.fn>;
	disconnect: ReturnType<typeof vi.fn>;
	start: ReturnType<typeof vi.fn>;
	stop: ReturnType<typeof vi.fn>;
}

function makeMocks() {
	const gains: MockGainNode[] = [];
	const limiters: MockLimiterNode[] = [];
	const buffers: MockBuffer[] = [];
	const sources: MockSourceNode[] = [];
	const closes: ReturnType<typeof vi.fn>[] = [];
	let currentTime = 0;

	class MockAudioContext {
		state = "running";
		destination = { id: "destination" };
		resume = vi.fn().mockResolvedValue(undefined);
		close: ReturnType<typeof vi.fn>;
		createGain = vi.fn(() => {
			const node: MockGainNode = {
				gain: { value: 0 },
				connect: vi.fn(),
				disconnect: vi.fn(),
			};
			gains.push(node);
			return node;
		});
		createDynamicsCompressor = vi.fn(() => {
			const node: MockLimiterNode = {
				threshold: { value: 0 },
				knee: { value: 0 },
				ratio: { value: 0 },
				attack: { value: 0 },
				release: { value: 0 },
				connect: vi.fn(),
				disconnect: vi.fn(),
			};
			limiters.push(node);
			return node;
		});
		createBuffer = vi.fn((_channels: number, length: number, rate: number) => {
			const buffer: MockBuffer = {
				duration: length / rate,
				length,
				sampleRate: rate,
				copyToChannel: vi.fn(),
			};
			buffers.push(buffer);
			return buffer;
		});
		createBufferSource = vi.fn(() => {
			const node: MockSourceNode = {
				buffer: null,
				onended: null,
				connect: vi.fn(),
				disconnect: vi.fn(),
				start: vi.fn(),
				stop: vi.fn(),
			};
			sources.push(node);
			return node;
		});
		get currentTime() {
			return currentTime;
		}
		set currentTime(value: number) {
			currentTime = value;
		}
		constructor() {
			this.close = vi.fn().mockResolvedValue(undefined);
			closes.push(this.close);
		}
	}

	return {
		gains,
		limiters,
		buffers,
		sources,
		closes,
		MockAudioContext,
		setCurrentTime: (value: number) => {
			currentTime = value;
		},
	};
}

interface BridgeMock {
	call: ReturnType<typeof vi.fn>;
	onEvent: ReturnType<typeof vi.fn>;
	emit: (type: string, data: Record<string, unknown>) => void;
}

/** Default `live_preview` reply: a live monitor stream is available. */
const ENABLED_REPLY = {
	active: true,
	monitoring: true,
	sample_rate: 48000,
	filtered: true,
};

function installBridge(
	reply: (req: { type: string; data?: Record<string, unknown> }) => unknown = (
		req,
	) =>
		req.data?.enabled ? ENABLED_REPLY : { active: false, monitoring: true },
): BridgeMock {
	let listener:
		| ((event: { type: string; data?: Record<string, unknown> }) => void)
		| null = null;
	const call = vi.fn(
		async (req: { type: string; data?: Record<string, unknown> }) => reply(req),
	);
	const onEvent = vi.fn(
		(cb: (event: { type: string; data?: Record<string, unknown> }) => void) => {
			listener = cb;
			return () => {
				listener = null;
			};
		},
	);
	(window as unknown as { python?: unknown }).python = { call, onEvent };
	return {
		call,
		onEvent,
		emit: (type, data) => listener?.({ type, data }),
	};
}

/** Encode float samples the way the sidecar does: PCM16 little-endian mono. */
function pcm16Base64(values: number[]): string {
	const bytes = new Uint8Array(values.length * 2);
	values.forEach((value, index) => {
		const clamped = Math.max(-1, Math.min(1, value));
		const int = Math.round(clamped * 32767);
		bytes[index * 2] = int & 0xff;
		bytes[index * 2 + 1] = (int >> 8) & 0xff;
	});
	let binary = "";
	for (const byte of bytes) binary += String.fromCharCode(byte);
	return btoa(binary);
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

function flush() {
	return act(async () => {
		await new Promise<void>((resolve) => setTimeout(resolve, 0));
	});
}

/** Non-optional array read (the tsconfig enables noUncheckedIndexedAccess). */
function at<T>(items: T[], index: number): T {
	const item = items[index];
	if (item === undefined) throw new Error(`no element at index ${index}`);
	return item;
}

/** First argument of the nth recorded call, non-optional. */
function callArg<T>(
	mock: { mock: { calls: readonly unknown[][] } },
	index: number,
): T {
	const call = mock.mock.calls[index];
	if (!call) throw new Error(`no call recorded at index ${index}`);
	return call[0] as T;
}

/** Toggle on and let the enable IPC settle. */
async function startListening(result: {
	current: ReturnType<typeof useLiveListen>;
}) {
	act(() => {
		result.current.toggle();
	});
	await flush();
}

describe("useLiveListen (backend-streamed)", () => {
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

	it("asks the sidecar to stream and builds the capped playback graph", async () => {
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
		// The preview is the sidecar's job: it is enabled, never captured here.
		expect(bridge.call).toHaveBeenCalledWith({
			type: "live_preview",
			data: { enabled: true },
		});
		// S1: the preview is the user level times the hard ceiling, well
		// below the old fixed 0.8 that rang on laptop speakers.
		expect(mocks.gains).toHaveLength(1);
		expect(at(mocks.gains, 0).gain.value).toBe(
			previewGain(LIVE_LISTEN_DEFAULT_LEVEL),
		);
		expect(at(mocks.gains, 0).gain.value).toBeLessThan(0.8);
		expect(at(mocks.gains, 0).connect).toHaveBeenCalledWith(
			at(mocks.limiters, 0),
		);
		expect(at(mocks.limiters, 0).connect).toHaveBeenCalledWith(
			expect.objectContaining({ id: "destination" }),
		);
		// Ceiling node configured as a fast limiter, not an effect.
		expect(at(mocks.limiters, 0).ratio.value).toBeGreaterThanOrEqual(20);
		expect(at(mocks.limiters, 0).attack.value).toBeLessThanOrEqual(0.005);
	});

	it("plays a streamed frame through the final gain, unmodified", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);
		await startListening(result);

		const frame = [0, 0.5, -0.5, 1, -1];
		act(() => {
			bridge.emit("live_preview_audio", {
				pcm: pcm16Base64(frame),
				sample_rate: 48000,
				seq: 1,
			});
		});

		// One buffer per chunk, at the frame's own rate, sample-for-sample.
		expect(mocks.buffers).toHaveLength(1);
		expect(at(mocks.buffers, 0).length).toBe(frame.length);
		expect(at(mocks.buffers, 0).sampleRate).toBe(48000);
		const written = callArg<Float32Array>(
			at(mocks.buffers, 0).copyToChannel,
			0,
		);
		// No JS filter chain (E13 / C-CONF-1): the post-chain samples the
		// sidecar sent are exactly what reaches the gain node. The only
		// difference allowed is PCM16 quantisation (< 1/32767).
		expect(
			Array.from(written).map((value) => Math.round(value * 1e4) / 1e4),
		).toEqual(frame);

		expect(mocks.sources).toHaveLength(1);
		expect(at(mocks.sources, 0).buffer).toBe(at(mocks.buffers, 0));
		expect(at(mocks.sources, 0).connect).toHaveBeenCalledWith(
			at(mocks.gains, 0),
		);
		expect(at(mocks.sources, 0).start).toHaveBeenCalledTimes(1);
	});

	it("queues consecutive frames end-to-end instead of overlapping them", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);
		await startListening(result);

		act(() => {
			bridge.emit("live_preview_audio", {
				pcm: pcm16Base64([0.1, 0.1]),
				sample_rate: 48000,
				seq: 1,
			});
			bridge.emit("live_preview_audio", {
				pcm: pcm16Base64([0.1, 0.1]),
				sample_rate: 48000,
				seq: 2,
			});
		});

		const firstStart = callArg<number>(at(mocks.sources, 0).start, 0);
		const secondStart = callArg<number>(at(mocks.sources, 1).start, 0);
		expect(secondStart).toBeGreaterThan(firstStart);
	});

	it("resyncs instead of queueing an unbounded backlog", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);
		await startListening(result);
		mocks.setCurrentTime(0);

		// One full second of audio: the queue is now far past the ceiling.
		const longFrame = new Array(48000).fill(0.1);
		act(() => {
			bridge.emit("live_preview_audio", {
				pcm: pcm16Base64(longFrame),
				sample_rate: 48000,
				seq: 1,
			});
		});
		act(() => {
			bridge.emit("live_preview_audio", {
				pcm: pcm16Base64([0.1]),
				sample_rate: 48000,
				seq: 2,
			});
		});

		// The stale source is dropped and the new one restarts near "now".
		expect(at(mocks.sources, 0).stop).toHaveBeenCalled();
		const restarted = callArg<number>(at(mocks.sources, 1).start, 0);
		expect(restarted).toBeLessThanOrEqual(LIVE_PREVIEW_MAX_BACKLOG_S);
	});

	it("ignores frames while not listening", async () => {
		renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		act(() => {
			bridge.emit("live_preview_audio", {
				pcm: pcm16Base64([0.5]),
				sample_rate: 48000,
				seq: 1,
			});
		});

		expect(mocks.buffers).toHaveLength(0);
		expect(mocks.sources).toHaveLength(0);
	});

	it("keeps the stream alive when a frame is malformed", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);
		await startListening(result);

		act(() => {
			bridge.emit("live_preview_audio", { pcm: "!!!", sample_rate: 48000 });
			bridge.emit("live_preview_audio", { pcm: pcm16Base64([0.2]) });
			bridge.emit("live_preview_audio", {
				pcm: pcm16Base64([0.2]),
				sample_rate: 0,
			});
		});

		expect(mocks.buffers).toHaveLength(0);
		expect(result.current.listening).toBe(true);
	});

	it("reports unavailable when the sidecar has no monitor stream", async () => {
		// The preview has no capture path of its own: no monitor, no preview.
		bridge = installBridge(() => ({ active: false, monitoring: false }));
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		await startListening(result);

		expect(result.current.listening).toBe(false);
		expect(result.current.error).toBe("unavailable");
		// Nothing was built and the context we opened for the gesture is closed.
		expect(mocks.gains).toHaveLength(0);
		expect(mocks.closes).toHaveLength(1);
		expect(at(mocks.closes, 0)).toHaveBeenCalled();
	});

	it("reports failed when the IPC call rejects (backend down)", async () => {
		bridge = installBridge(() => {
			throw new Error("Python bridge not available");
		});
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		await startListening(result);

		expect(result.current.listening).toBe(false);
		expect(result.current.error).toBe("failed");
		expect(mocks.gains).toHaveLength(0);
		expect(at(mocks.closes, 0)).toHaveBeenCalled();
	});

	it("reports unavailable when the renderer has no AudioContext", async () => {
		Object.defineProperty(window, "AudioContext", {
			value: undefined,
			configurable: true,
			writable: true,
		});
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		await startListening(result);

		expect(result.current.error).toBe("unavailable");
		// No point enabling a stream we cannot play.
		expect(bridge.call).not.toHaveBeenCalled();
	});

	it("never lets a level exceed the hard ceiling", async () => {
		const { result } = renderHook(() =>
			useLiveListen({
				activeMicName: null,
				isSystemDefault: true,
				level: 1,
			}),
		);

		await startListening(result);

		expect(at(mocks.gains, 0).gain.value).toBe(LIVE_LISTEN_MAX);
	});

	it("applies the configured preview level", async () => {
		const { result } = renderHook(() =>
			useLiveListen({
				activeMicName: null,
				isSystemDefault: true,
				level: 0.2,
			}),
		);

		await startListening(result);

		expect(at(mocks.gains, 0).gain.value).toBeCloseTo(0.2 * LIVE_LISTEN_MAX);
	});

	it("follows a level change while listening (config arrives late)", async () => {
		const { result, rerender } = renderHook(
			({ level }: { level: number }) =>
				useLiveListen({ activeMicName: null, isSystemDefault: true, level }),
			{ initialProps: { level: LIVE_LISTEN_DEFAULT_LEVEL } },
		);

		await startListening(result);
		expect(at(mocks.gains, 0).gain.value).toBe(
			previewGain(LIVE_LISTEN_DEFAULT_LEVEL),
		);

		rerender({ level: 1 });
		expect(at(mocks.gains, 0).gain.value).toBe(LIVE_LISTEN_MAX);
	});

	it("disables the backend stream and releases the graph on toggle-off", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);
		await startListening(result);
		expect(result.current.listening).toBe(true);

		act(() => {
			result.current.toggle();
		});

		expect(result.current.listening).toBe(false);
		expect(bridge.call).toHaveBeenLastCalledWith({
			type: "live_preview",
			data: { enabled: false },
		});
		expect(at(mocks.gains, 0).disconnect).toHaveBeenCalled();
		expect(at(mocks.limiters, 0).disconnect).toHaveBeenCalled();
		expect(at(mocks.closes, 0)).toHaveBeenCalled();
	});

	it("stops queued frames when it stops", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);
		await startListening(result);

		act(() => {
			bridge.emit("live_preview_audio", {
				pcm: pcm16Base64([0.3, 0.3]),
				sample_rate: 48000,
				seq: 1,
			});
		});
		act(() => {
			result.current.stop();
		});

		expect(at(mocks.sources, 0).stop).toHaveBeenCalled();
		expect(at(mocks.sources, 0).disconnect).toHaveBeenCalled();
	});

	it("never talks to the backend when it never started", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);

		act(() => {
			result.current.stop();
		});

		expect(bridge.call).not.toHaveBeenCalled();
	});

	it("releases the stream when stopped while the enable is in flight", async () => {
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
		// Both halves acquired by the superseded start are released.
		expect(mocks.gains).toHaveLength(0);
		expect(at(mocks.closes, 0)).toHaveBeenCalled();
		expect(bridge.call).toHaveBeenLastCalledWith({
			type: "live_preview",
			data: { enabled: false },
		});
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
		await startListening(result);
		expect(result.current.listening).toBe(true);

		signal += 1;
		rerender({ stopSignal: signal });

		expect(result.current.listening).toBe(false);
		expect(bridge.call).toHaveBeenLastCalledWith({
			type: "live_preview",
			data: { enabled: false },
		});
	});

	it("stops when the tab hides (C-BG-1)", async () => {
		const { result } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);
		await startListening(result);
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
		expect(bridge.call).toHaveBeenLastCalledWith({
			type: "live_preview",
			data: { enabled: false },
		});
	});

	it("tears down and disables the stream on unmount", async () => {
		const { result, unmount } = renderHook(() =>
			useLiveListen({ activeMicName: null, isSystemDefault: true }),
		);
		await startListening(result);
		expect(result.current.listening).toBe(true);

		unmount();

		expect(at(mocks.closes, 0)).toHaveBeenCalled();
		expect(bridge.call).toHaveBeenLastCalledWith({
			type: "live_preview",
			data: { enabled: false },
		});
	});
});

describe("decodePreviewFrame", () => {
	it("decodes PCM16 little-endian mono to float samples", () => {
		const frame = [0, 0.5, -0.5, 1, -1];
		const decoded = decodePreviewFrame(pcm16Base64(frame));
		expect(
			Array.from(decoded).map((value) => Math.round(value * 1e4) / 1e4),
		).toEqual(frame);
	});

	it("round-trips a negative sample that would flip if the byte order were swapped", () => {
		// 0x0100 (LE: 00 01) is 256; byte-swapped it is 1. A -1/256 sample
		// distinguishes the two unambiguously.
		const decoded = decodePreviewFrame(pcm16Base64([-1 / 256]));
		expect(decoded[0]).toBeCloseTo(-1 / 256, 5);
	});

	it("returns an empty buffer for an empty frame", () => {
		expect(decodePreviewFrame("").length).toBe(0);
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
