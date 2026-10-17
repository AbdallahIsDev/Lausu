// Live microphone monitor ("hear yourself"), BACKEND-STREAMED.
//
// The sidecar owns the microphone: one PortAudio InputStream serves the level
// meter, the 10 s test and this preview (C-MIC-10). It also owns the filter
// chain — the SAME `AudioProcessor` the test and the meter run (E7) — so a
// preview frame is a copy of that post-chain buffer, never a second capture
// path and never a second filter chain (E13 / C-CONF-1).
//
// What this hook does:
//   1. `live_preview {enabled:true}` asks the level monitor to publish
//      post-chain frames and answers with the REAL state. No monitor stream
//      -> `active:false` -> honest "unavailable" (never a silent dead button).
//   2. `live_preview_audio` push events are decoded (base64 PCM16 LE mono) and
//      SCHEDULED into a dedicated AudioContext through the S1 ceiling gain and
//      the limiter. Scheduling is the only DSP here: no filtering, no gating,
//      no suppression — the preset the user is tuning is applied in the
//      sidecar, so an aggressive gate makes the preview silent and
//      filtering OFF makes it raw, exactly like the 10 s test.
//   3. `live_preview {enabled:false}` on every stop path (toggle-off, test
//      start, device switch, hidden tab, unmount) so the sidecar stops
//      encoding frames the moment nobody is listening.
//
// S1/S2 (docs/plan-listen-live-feedback.md): the preview is CAPPED at
// LIVE_LISTEN_MAX and passes a fast limiter, both on the final gain, so a
// speaker->mic->speaker path keeps headroom. The renderer no longer requests
// the browser's echo canceller: it no longer captures (the sidecar does), and
// AEC is a capture-side browser feature. The cap + limiter + the chain's own
// gate remain the loop protection, see the limitations note in the report.
// Nothing here ever touches the mic knob or the meter.

import { useCallback, useEffect, useRef, useState } from "react";
import { usePython, usePythonEvent } from "@/hooks/usePython";

/**
 * `"denied"` is retained for the card's message mapping (it is the
 * permission-refusal wording); this hook no longer prompts for a device, so
 * it does not produce it. `"unavailable"` = the sidecar has no monitor stream
 * to filter, `"failed"` = the IPC call itself failed.
 */
export type LiveListenError = "denied" | "unavailable" | "failed" | null;

export interface UseLiveListenOptions {
	/**
	 * Display name of the app-selected mic. NOT used here: the preview rides
	 * the level monitor's stream, and the monitor owns device selection
	 * (`level_monitor_start {mic_id}`). Kept on the options object so call
	 * sites stay unchanged.
	 */
	activeMicName: string | null;
	/** True when the selection is System Default. Also monitor-owned; see above. */
	isSystemDefault: boolean;
	/** Increment to force-stop (test start, device switch). Change-only, initial value ignored. */
	stopSignal?: number;
	/**
	 * Preview level, 0–1: the user's fraction of {@link LIVE_LISTEN_MAX}.
	 * Ignored (default applied) when not a finite number. The Microphone page
	 * no longer exposes a slider for it, so callers omit this and the hook
	 * runs at {@link LIVE_LISTEN_DEFAULT_LEVEL}.
	 */
	level?: number;
}

export interface UseLiveListenResult {
	listening: boolean;
	starting: boolean;
	error: LiveListenError;
	toggle: () => void;
	stop: () => void;
}

/**
 * Hard ceiling on the preview gain, as an absolute linear multiplier.
 *
 * The preview used to be a fixed 0.8. Users reported that as ringing, with
 * the meter slammed to 100%, when the mic and the laptop speakers share a
 * desk. This ceiling sits ~3 dB below unity so the speaker -> mic ->
 * speaker path keeps headroom, and it is the ONLY thing the level
 * multiplies — so a hand-edited `config.json` cannot push the preview above it.
 */
export const LIVE_LISTEN_MAX = 0.7;

/** Preview level used when no `level` is supplied. */
export const LIVE_LISTEN_DEFAULT_LEVEL = 0.5;

/**
 * Scheduling headroom before the first frame of a chunk. The sidecar ships
 * one frame per processed block (~10 ms at 48 kHz), so a chunk must be
 * queued slightly ahead of `currentTime` or its first samples are already in
 * the past and Web Audio clips them.
 */
export const LIVE_PREVIEW_LEAD_S = 0.06;

/**
 * Backlog ceiling. Transport jitter (a WS burst after a GC pause) can hand us
 * several frames at once; queueing them all would grow the delay until the
 * preview is a permanent echo. Past this the queue is dropped and resynced,
 * trading a click for bounded latency.
 */
export const LIVE_PREVIEW_MAX_BACKLOG_S = 0.35;

// DynamicsCompressor settings that turn the node into a fast LIMITER rather
// than an effect: hard knee, 20:1, 3 ms attack. Whatever the mic hears, no
// spike reaches the speakers at full blast.
const LIMITER_THRESHOLD_DB = -3;
const LIMITER_KNEE_DB = 0;
const LIMITER_RATIO = 20;
const LIMITER_ATTACK_S = 0.003;
const LIMITER_RELEASE_S = 0.25;

// The sidecar scales float samples by 32767 before casting to int16, so the
// inverse uses the same constant and a full-scale frame round-trips to ±1.
const PCM16_FULL_SCALE = 32767;

/** Reply of the `live_preview` command (`live_preview_status`). */
interface LivePreviewStatus {
	active?: boolean;
	monitoring?: boolean;
	sample_rate?: number;
	filtered?: boolean;
}

function clampLevel(level: number): number {
	if (!Number.isFinite(level)) return LIVE_LISTEN_DEFAULT_LEVEL;
	return Math.min(Math.max(level, 0), 1);
}

/** The gain-node value for a 0–1 user level. Never exceeds `LIVE_LISTEN_MAX`. */
export function previewGain(level: number): number {
	return clampLevel(level) * LIVE_LISTEN_MAX;
}

/**
 * Decode one `live_preview_audio` frame (base64 PCM16 little-endian mono)
 * into float samples in [-1, 1].
 */
export function decodePreviewFrame(pcm: string): Float32Array<ArrayBuffer> {
	const binary = atob(pcm);
	const count = binary.length >> 1;
	const out = new Float32Array(count);
	for (let i = 0; i < count; i++) {
		const lo = binary.charCodeAt(i * 2);
		const hi = binary.charCodeAt(i * 2 + 1);
		let value = (hi << 8) | lo;
		if (value >= 0x8000) value -= 0x10000;
		out[i] = value / PCM16_FULL_SCALE;
	}
	return out;
}

export function useLiveListen({
	stopSignal = 0,
	level = LIVE_LISTEN_DEFAULT_LEVEL,
}: UseLiveListenOptions): UseLiveListenResult {
	const { call } = usePython();
	const [listening, setListening] = useState(false);
	const [starting, setStarting] = useState(false);
	const [error, setError] = useState<LiveListenError>(null);

	const ctxRef = useRef<AudioContext | null>(null);
	const gainRef = useRef<GainNode | null>(null);
	const limiterRef = useRef<DynamicsCompressorNode | null>(null);
	const pendingRef = useRef<Set<AudioBufferSourceNode>>(new Set());
	const nextStartRef = useRef(0);
	// True only between a confirmed enable and the matching disable: it gates
	// both frame scheduling and the teardown IPC, so a stop that never started
	// anything does not talk to the backend.
	const playingRef = useRef(false);
	const runIdRef = useRef(0);
	const stopRef = useRef(() => {});
	const callRef = useRef(call);
	callRef.current = call;

	const stop = useCallback(() => {
		runIdRef.current += 1;
		const wasPlaying = playingRef.current;
		playingRef.current = false;
		nextStartRef.current = 0;

		for (const source of pendingRef.current) {
			try {
				source.stop();
			} catch {
				/* never started, or already ended */
			}
			try {
				source.disconnect();
			} catch {
				/* already torn down */
			}
		}
		pendingRef.current.clear();

		const gain = gainRef.current;
		gainRef.current = null;
		try {
			gain?.disconnect();
		} catch {
			/* already torn down */
		}
		const limiter = limiterRef.current;
		limiterRef.current = null;
		try {
			limiter?.disconnect();
		} catch {
			/* already torn down */
		}
		const ctx = ctxRef.current;
		ctxRef.current = null;
		if (ctx) {
			try {
				void ctx.close();
			} catch {
				/* already closed */
			}
		}

		if (wasPlaying) {
			// Fire-and-forget: a stop must never block teardown (unmount,
			// hidden tab), and a failed disable only wastes frames until the
			// monitor stops or the next enable overwrites the flag.
			void callRef.current("live_preview", { enabled: false }).catch(() => {});
		}

		setListening(false);
		setStarting(false);
	}, []);
	stopRef.current = stop;

	// One chunk -> one buffer, queued end-to-end after the previous one.
	const scheduleFrame = useCallback((pcm: string, sampleRate: number) => {
		const ctx = ctxRef.current;
		const gain = gainRef.current;
		if (!ctx || !gain) return;
		let samples: Float32Array<ArrayBuffer>;
		try {
			samples = decodePreviewFrame(pcm);
		} catch {
			return; // malformed base64: drop the frame, keep the stream
		}
		if (samples.length === 0) return;

		const buffer = ctx.createBuffer(1, samples.length, sampleRate);
		buffer.copyToChannel(samples, 0);
		const source = ctx.createBufferSource();
		source.buffer = buffer;
		source.connect(gain);

		const now = ctx.currentTime;
		let startAt = nextStartRef.current;
		if (startAt < now + LIVE_PREVIEW_LEAD_S) {
			startAt = now + LIVE_PREVIEW_LEAD_S;
		}
		if (startAt > now + LIVE_PREVIEW_MAX_BACKLOG_S) {
			// Queue too deep: drop what is pending and resync on the clock.
			for (const pending of pendingRef.current) {
				try {
					pending.stop();
				} catch {
					/* never started, or already ended */
				}
				try {
					pending.disconnect();
				} catch {
					/* already torn down */
				}
			}
			pendingRef.current.clear();
			startAt = now + LIVE_PREVIEW_LEAD_S;
		}

		source.onended = () => {
			pendingRef.current.delete(source);
			try {
				source.disconnect();
			} catch {
				/* already torn down */
			}
		};
		pendingRef.current.add(source);
		source.start(startAt);
		nextStartRef.current = startAt + buffer.duration;
	}, []);

	// Subscribed for the whole lifetime (hook rules); the ref decides whether
	// a frame is ours, so a burst arriving during teardown is dropped instead
	// of resurrecting the graph.
	usePythonEvent("live_preview_audio", (data) => {
		if (!playingRef.current) return;
		const pcm = data?.pcm;
		const sampleRate = data?.sample_rate;
		if (typeof pcm !== "string" || typeof sampleRate !== "number") return;
		if (!Number.isFinite(sampleRate) || sampleRate <= 0) return;
		scheduleFrame(pcm, sampleRate);
	});

	const start = useCallback(async () => {
		if (listening || starting) return;
		const runId = ++runIdRef.current;
		setError(null);
		setStarting(true);

		const Ctor: typeof AudioContext | undefined =
			window.AudioContext ??
			(window as unknown as { webkitAudioContext?: typeof AudioContext })
				.webkitAudioContext;
		if (!Ctor) {
			setError("unavailable");
			setStarting(false);
			return;
		}

		let ctx: AudioContext;
		try {
			ctx = new Ctor();
		} catch {
			setError("unavailable");
			setStarting(false);
			return;
		}
		// Resume inside the click gesture (autoplay policy): a resume issued
		// after the IPC round-trip may be rejected as not user-initiated.
		if (ctx.state === "suspended") {
			void ctx.resume().catch(() => {});
		}

		let status: LivePreviewStatus | undefined;
		try {
			status = await callRef.current<LivePreviewStatus>("live_preview", {
				enabled: true,
			});
		} catch {
			if (runIdRef.current === runId) {
				void ctx.close().catch(() => {});
				setError("failed");
				setStarting(false);
			}
			return;
		}

		if (runIdRef.current !== runId) {
			// Superseded by a stop while the enable was in flight: release
			// both halves we just acquired.
			void ctx.close().catch(() => {});
			void callRef.current("live_preview", { enabled: false }).catch(() => {});
			return;
		}

		if (!status?.active) {
			// Honest unavailable: the sidecar has no monitor stream to filter.
			void ctx.close().catch(() => {});
			setError("unavailable");
			setStarting(false);
			return;
		}

		const gain = ctx.createGain();
		gain.gain.value = previewGain(level);
		const limiter = ctx.createDynamicsCompressor();
		limiter.threshold.value = LIMITER_THRESHOLD_DB;
		limiter.knee.value = LIMITER_KNEE_DB;
		limiter.ratio.value = LIMITER_RATIO;
		limiter.attack.value = LIMITER_ATTACK_S;
		limiter.release.value = LIMITER_RELEASE_S;
		gain.connect(limiter);
		limiter.connect(ctx.destination);

		ctxRef.current = ctx;
		gainRef.current = gain;
		limiterRef.current = limiter;
		nextStartRef.current = 0;
		playingRef.current = true;
		setListening(true);
		setStarting(false);
	}, [listening, starting, level]);

	const toggle = useCallback(() => {
		if (listening || starting) stop();
		else void start();
	}, [listening, starting, start, stop]);

	// Level changes must take effect WHILE listening, not only on the next
	// start: the preview tap is what the user is tuning. A no-op when the
	// graph is not built (nothing to write).
	useEffect(() => {
		const gain = gainRef.current;
		if (!gain) return;
		gain.gain.value = previewGain(level);
	}, [level]);

	// External stop signals (test start / device switch): change-only.
	const firstSignal = useRef(stopSignal);
	useEffect(() => {
		if (firstSignal.current === stopSignal) return;
		firstSignal.current = stopSignal;
		stopRef.current();
	}, [stopSignal]);

	// Hidden tabs must never capture or play audio (C-BG-1).
	useEffect(() => {
		const onVisibility = () => {
			if (document.visibilityState === "hidden") stopRef.current();
		};
		document.addEventListener("visibilitychange", onVisibility);
		return () => document.removeEventListener("visibilitychange", onVisibility);
	}, []);

	// Unmount tears everything down (and disables the backend stream).
	useEffect(() => () => stopRef.current(), []);

	return { listening, starting, error, toggle, stop };
}
