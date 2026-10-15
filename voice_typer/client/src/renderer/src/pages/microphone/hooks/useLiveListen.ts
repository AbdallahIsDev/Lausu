// Live microphone monitor ("hear yourself").
// Pure frontend passthrough: getUserMedia -> a DEDICATED AudioContext ->
// MediaStreamSource -> GainNode -> destination. No backend, no IPC, no
// model, nothing recorded, stored, or transmitted.
// Dedicated (not the shared cue context in sound-manager): the cue
// context is torn down by closeAudioContext, which must never kill an
// active monitor. Stops on unmount, tab-hide (C-BG-1), and the parent's
// stopSignal (test start / device switch / playback).

import { useCallback, useEffect, useRef, useState } from "react";

export type LiveListenError = "denied" | "unavailable" | "failed" | null;

export interface UseLiveListenOptions {
	/** Display name of the app-selected mic, used to pick the browser input. Null when unknown. */
	activeMicName: string | null;
	/** True when the selection is System Default: use the browser default input, no label matching. */
	isSystemDefault: boolean;
	/** Increment to force-stop (test start, device switch). Change-only, initial value ignored. */
	stopSignal?: number;
}

export interface UseLiveListenResult {
	listening: boolean;
	starting: boolean;
	error: LiveListenError;
	toggle: () => void;
	stop: () => void;
}

const MONITOR_GAIN = 0.8;

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
}: UseLiveListenOptions): UseLiveListenResult {
	const [listening, setListening] = useState(false);
	const [starting, setStarting] = useState(false);
	const [error, setError] = useState<LiveListenError>(null);

	const streamRef = useRef<MediaStream | null>(null);
	const ctxRef = useRef<AudioContext | null>(null);
	const nodesRef = useRef<{
		source: MediaStreamAudioSourceNode;
		gain: GainNode;
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
				audio: deviceId ? { deviceId: { exact: deviceId } } : true,
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
			gain.gain.value = MONITOR_GAIN;
			source.connect(gain);
			gain.connect(ctx.destination);
			streamRef.current = stream;
			ctxRef.current = ctx;
			nodesRef.current = { source, gain };
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
	}, [activeMicName, isSystemDefault, listening, starting]);

	const toggle = useCallback(() => {
		if (listening || starting) stop();
		else void start();
	}, [listening, starting, start, stop]);

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
