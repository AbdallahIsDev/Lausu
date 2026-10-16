// Live microphone monitor ("hear yourself").
// Pure frontend passthrough: getUserMedia -> a DEDICATED AudioContext ->
// MediaStreamSource -> GainNode -> DynamicsCompressor ceiling ->
// destination. No backend, no IPC, no model, nothing recorded, stored, or
// transmitted.
// Dedicated (not the shared cue context in sound-manager): the cue
// context is torn down by closeAudioContext, which must never kill an
// active monitor. Stops on unmount, tab-hide (C-BG-1), and the parent's
// stopSignal (test start / device switch / playback).
//
// S1/S2 (docs/plan-listen-live-feedback.md): the preview is CAPPED and the
// capture track asks the browser's own canceller to subtract what the
// speakers emit. The gain used to be a fixed 0.8 straight to destination,
// which rang and slammed the meter on laptop speakers sitting next to the
// mic; both changes exist so Listen Live on speakers can never build into
// a sustained loop. Nothing here ever touches the mic knob or the meter.

import { useCallback, useEffect, useRef, useState } from "react";

export type LiveListenError = "denied" | "unavailable" | "failed" | null;

export interface UseLiveListenOptions {
	/** Display name of the app-selected mic, used to pick the browser input. Null when unknown. */
	activeMicName: string | null;
	/** True when the selection is System Default: use the browser default input, no label matching. */
	isSystemDefault: boolean;
	/** Increment to force-stop (test start, device switch). Change-only, initial value ignored. */
	stopSignal?: number;
	/**
	 * Preview level, 0–1 (`config.live_listen_level`): the user's fraction of
	 * {@link LIVE_LISTEN_MAX}. Ignored (default applied) when not a finite
	 * number, so an unloaded config cannot mute the monitor by accident.
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
 * multiplies — so neither the slider nor a hand-edited `config.json` can
 * push the preview above it.
 */
export const LIVE_LISTEN_MAX = 0.7;

/** Preview level used when `config.live_listen_level` is absent. */
export const LIVE_LISTEN_DEFAULT_LEVEL = 0.5;

// DynamicsCompressor settings that turn the node into a fast LIMITER rather
// than an effect: hard knee, 20:1, 3 ms attack. Whatever the mic hears, no
// spike reaches the speakers at full blast.
const LIMITER_THRESHOLD_DB = -3;
const LIMITER_KNEE_DB = 0;
const LIMITER_RATIO = 20;
const LIMITER_ATTACK_S = 0.003;
const LIMITER_RELEASE_S = 0.25;

function clampLevel(level: number): number {
	if (!Number.isFinite(level)) return LIVE_LISTEN_DEFAULT_LEVEL;
	return Math.min(Math.max(level, 0), 1);
}

/** The gain-node value for a 0–1 user level. Never exceeds `LIVE_LISTEN_MAX`. */
export function previewGain(level: number): number {
	return clampLevel(level) * LIVE_LISTEN_MAX;
}

function normalizeLabel(s: string): string {
	return s.toLowerCase().trim();
}

async function pickDeviceId(
	activeMicName: string | null,
): Promise<string | undefined> {
	const devices = await navigator.mediaDevices.enumerateDevices();
	const inputs = devices.filter((d) => d.kind === "audioinput");
	if (!activeMicName || inputs.every((d) => !d.label)) return undefined;
	const want = normalizeLabel(activeMicName);
	const hit = inputs.find(
		(d) =>
			d.label &&
			(normalizeLabel(d.label).includes(want) ||
				want.includes(normalizeLabel(d.label))),
	);
	return hit?.deviceId || undefined;
}

export function useLiveListen({
	activeMicName,
	isSystemDefault,
	stopSignal = 0,
	level = LIVE_LISTEN_DEFAULT_LEVEL,
}: UseLiveListenOptions): UseLiveListenResult {
	const [listening, setListening] = useState(false);
	const [starting, setStarting] = useState(false);
	const [error, setError] = useState<LiveListenError>(null);

	const streamRef = useRef<MediaStream | null>(null);
	const ctxRef = useRef<AudioContext | null>(null);
	const nodesRef = useRef<{
		source: MediaStreamAudioSourceNode;
		gain: GainNode;
		limiter: DynamicsCompressorNode;
	} | null>(null);
	const runIdRef = useRef(0);
	const stopRef = useRef(() => {});

	const stop = useCallback(() => {
		runIdRef.current += 1;
		const nodes = nodesRef.current;
		nodesRef.current = null;
		try {
			nodes?.source.disconnect();
		} catch {
			/* already torn down */
		}
		try {
			nodes?.gain.disconnect();
		} catch {
			/* already torn down */
		}
		try {
			nodes?.limiter.disconnect();
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
		const stream = streamRef.current;
		streamRef.current = null;
		if (stream) {
			for (const track of stream.getTracks()) {
				try {
					track.stop();
				} catch {
					/* already stopped */
				}
			}
		}
		setListening(false);
		setStarting(false);
	}, []);
	stopRef.current = stop;

	const start = useCallback(async () => {
		if (listening || starting) return;
		const runId = ++runIdRef.current;
		setError(null);
		setStarting(true);
		try {
			if (!navigator.mediaDevices?.getUserMedia) {
				if (runIdRef.current === runId) {
					setError("unavailable");
					setStarting(false);
				}
				return;
			}
			const deviceId = isSystemDefault
				? undefined
				: await pickDeviceId(activeMicName);
			if (runIdRef.current !== runId) return;
			const stream = await navigator.mediaDevices.getUserMedia({
				audio: {
					...(deviceId ? { deviceId: { exact: deviceId } } : {}),
					// S2: ask the browser's own canceller to subtract what the
					// speakers are emitting — that is the loop. Noise
					// suppression and AGC stay OFF: NS would fight the user's
					// filter tuning and AGC would move gain behind their back.
					echoCancellation: true,
					noiseSuppression: false,
					autoGainControl: false,
				},
			});
			if (runIdRef.current !== runId) {
				for (const track of stream.getTracks()) {
					try {
						track.stop();
					} catch {
						/* best-effort */
					}
				}
				return;
			}
			const Ctor: typeof AudioContext | undefined =
				window.AudioContext ??
				(window as unknown as { webkitAudioContext?: typeof AudioContext })
					.webkitAudioContext;
			if (!Ctor) {
				for (const track of stream.getTracks()) {
					try {
						track.stop();
					} catch {
						/* best-effort */
					}
				}
				setError("unavailable");
				setStarting(false);
				return;
			}
			const ctx = new Ctor();
			if (ctx.state === "suspended") {
				await ctx.resume();
			}
			if (runIdRef.current !== runId) {
				void ctx.close().catch(() => {});
				for (const track of stream.getTracks()) {
					try {
						track.stop();
					} catch {
						/* best-effort */
					}
				}
				return;
			}
			const source = ctx.createMediaStreamSource(stream);
			const gain = ctx.createGain();
			gain.gain.value = previewGain(level);
			const limiter = ctx.createDynamicsCompressor();
			limiter.threshold.value = LIMITER_THRESHOLD_DB;
			limiter.knee.value = LIMITER_KNEE_DB;
			limiter.ratio.value = LIMITER_RATIO;
			limiter.attack.value = LIMITER_ATTACK_S;
			limiter.release.value = LIMITER_RELEASE_S;
			source.connect(gain);
			gain.connect(limiter);
			limiter.connect(ctx.destination);
			streamRef.current = stream;
			ctxRef.current = ctx;
			nodesRef.current = { source, gain, limiter };
			setListening(true);
		} catch (err) {
			if (runIdRef.current !== runId) return;
			const name = (err as DOMException | null)?.name ?? "";
			setError(
				name === "NotAllowedError" || name === "SecurityError"
					? "denied"
					: "failed",
			);
		} finally {
			if (runIdRef.current === runId) setStarting(false);
		}
	}, [activeMicName, isSystemDefault, listening, starting, level]);

	const toggle = useCallback(() => {
		if (listening || starting) stop();
		else void start();
	}, [listening, starting, start, stop]);

	// Level changes must take effect WHILE listening, not only on the next
	// start: the preview tap is what the user is tuning. A no-op when the
	// graph is not built (nothing to write).
	useEffect(() => {
		const nodes = nodesRef.current;
		if (!nodes) return;
		nodes.gain.gain.value = previewGain(level);
	}, [level]);

	// External stop signals (test start / device switch): change-only.
	const firstSignal = useRef(stopSignal);
	useEffect(() => {
		if (firstSignal.current === stopSignal) return;
		firstSignal.current = stopSignal;
		stopRef.current();
	}, [stopSignal]);

	// Hidden tabs must never capture audio (C-BG-1).
	useEffect(() => {
		const onVisibility = () => {
			if (document.visibilityState === "hidden") stopRef.current();
		};
		document.addEventListener("visibilitychange", onVisibility);
		return () => document.removeEventListener("visibilitychange", onVisibility);
	}, []);

	// Unmount tears everything down.
	useEffect(() => () => stopRef.current(), []);

	return { listening, starting, error, toggle, stop };
}
