// S1 step 4, the one-time "your speakers are loud" offer for Listen Live.
//
// Live monitoring on speakers is the one path where the output level feeds
// back into what the mic hears, so when the preview starts with the system
// output above SPEAKER_OFFER_THRESHOLD we offer to lower it — once.
//
// Deliberately an OFFER, never an automatic duck (plan verdict): Live must
// not move the speakers on its own. Users tune the preview by ear and a
// quieter system output hides the very noise they are hunting, and a second
// volume mechanism on this path would fight the preview level.
//
// The decision is remembered per session in module state, so answering or
// dismissing it never brings it back until the next app launch. Only a
// completed check marks it; a failed read leaves the offer armed.

import { createElement, useEffect, useRef } from "react";
import { usePython } from "@/hooks/usePython";
import { useSnackbar } from "@/hooks/useSnackbar";
import { t } from "@/i18n/i18n";
import { SpeakerOfferActions } from "./SpeakerOfferActions";

/** Sonner id: the offer replaces itself in place. */
export const SPEAKER_OFFER_TOAST_ID = "live-speaker-offer";

/** Offer only above this system-output level (plan: ">90%"). */
export const SPEAKER_OFFER_THRESHOLD = 0.9;

/** What the offer's button writes. Fixed: it is a suggestion, not a slider. */
export const SPEAKER_OFFER_TARGET_LEVEL = 0.75;

type CheckState = "idle" | "checking" | "done";

// Session memory (module scope outlives navigation, resets on app restart).
let _checkState: CheckState = "idle";

/** Test-only reset for the session memory. */
export function __resetLiveSpeakerOfferForTests(): void {
	_checkState = "idle";
}

function readOutputLevel(status: unknown): number | null {
	const raw = (status as { output_level?: unknown } | null)?.output_level;
	if (typeof raw !== "number" || !Number.isFinite(raw)) return null;
	return Math.min(1, Math.max(0, raw));
}

/**
 * Offer to lower the speakers once per session when Live starts loud.
 *
 * @param listening true while the Live preview is running.
 */
export function useLiveSpeakerOffer(listening: boolean): void {
	const { showSnack, clearSnack } = useSnackbar();
	const { call } = usePython();
	const wasListening = useRef(listening);

	// Auto-dismiss on stop: the offer only makes sense while the preview
	// runs. Gated on the actual listening true→false flip so a stopped
	// mount never touches an unrelated toast; dismissing an absent sonner
	// id is a silent no-op.
	useEffect(() => {
		if (wasListening.current && !listening) {
			clearSnack(SPEAKER_OFFER_TOAST_ID);
		}
		wasListening.current = listening;
	}, [listening, clearSnack]);

	useEffect(() => {
		if (!listening || _checkState !== "idle") return;
		_checkState = "checking";
		let cancelled = false;
		void (async () => {
			let level: number | null = null;
			try {
				level = readOutputLevel(
					await call<{ output_level?: number | null }>(
						"get_volume_backend_status",
					),
				);
			} catch {
				// Unreadable backend: leave the offer armed for a later start.
				if (!cancelled) _checkState = "idle";
				return;
			}
			if (cancelled) {
				// The preview stopped mid-check. Re-arm rather than leaving
				// the session stuck at "checking" — a completed check is the
				// only thing that counts as "offered this session".
				_checkState = "idle";
				return;
			}
			// A completed check is final for this session, loud or not.
			_checkState = "done";
			if (level === null || level <= SPEAKER_OFFER_THRESHOLD) return;

			const lowerLabel = t("microphoneTest.speakerOfferLower");
			const keepLabel = t("microphoneTest.speakerOfferKeep");
			showSnack(t("microphoneTest.speakerOfferTitle"), "info", {
				id: SPEAKER_OFFER_TOAST_ID,
				description: t("microphoneTest.speakerOfferMessage"),
				persistent: true,
				// Real div group (honest DOM): sonner's action slot takes raw
				// JSX, so both buttons share ONE container — no sibling hacks.
				// createElement (not JSX syntax) so this file stays .ts.
				action: createElement(SpeakerOfferActions, {
					lowerLabel,
					keepLabel,
					onLower: () => {
						clearSnack(SPEAKER_OFFER_TOAST_ID);
						void call("set_output_volume", {
							level: SPEAKER_OFFER_TARGET_LEVEL,
						}).catch(() => undefined);
					},
					onKeep: () => clearSnack(SPEAKER_OFFER_TOAST_ID),
				}),
			});
		})();
		return () => {
			cancelled = true;
		};
	}, [listening, call, showSnack, clearSnack]);
}
