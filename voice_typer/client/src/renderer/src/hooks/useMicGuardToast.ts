// useMicGuardToast, surfaces the mic guard's "we could not put it back"
// push event (``microphone_volume_lowered``).
//
// Windows/driver auto-gain follows a loud close-range event and slides the
// OS capture knob down (100 → 92 → 88 …). The backend's MicVolumeGuard
// polls the capture endpoint and writes 100% back, so the common case is
// silent: the knob IS at 100% and there is nothing for the user to do.
//
// This toast is therefore the FALLBACK, not the normal path. It fires only
// when the guard reported ``restored: false`` — the anti-flap budget is
// exhausted (a driver that keeps re-clamping) or the device exposes no
// settable input gain at all (most built-in macOS mics). In both cases the
// knob really is below 100% right now, so the message is true and the
// button is actionable. Reporting a successful auto-restore here would
// print "lowered to 92%" about a knob sitting at 100% (C-UI-1), and the
// [Back to 100%] button would do nothing.
//
// The button writes the REAL device value, fixed at 100% — deliberately
// not restore-previous (the previous value is the broken one) and
// deliberately not a slider (a slider becomes a tug toy while a driver
// keeps pulling). It never consumes the guard's anti-flap budget, so the
// user's own press always writes.
//
// ``can_set`` rides the event so the no-settable-gain case shows the
// message WITHOUT a button — the plan is explicit that we never render a
// control that cannot work.

import { usePython, usePythonEvent } from "@/hooks/usePython";
import type { TranslateFn } from "@/i18n/translate-types";
import { type ShowSnackOptions, useSnackbar } from "./useSnackbar";

/** Sonner id: the sticky message replaces itself in place. */
export const MIC_GUARD_TOAST_ID = "mic-guard";

/** The knob the user requires, and what the button writes. */
const MIC_GUARD_RESTORE_LEVEL = 1;

export function useMicGuardToast(t: TranslateFn): void {
	const { showSnack, clearSnack } = useSnackbar();
	const { call } = usePython();

	usePythonEvent(
		"microphone_volume_lowered",
		(data): (() => void) | undefined => {
			// Only the notify-only outcome is surfaced (see the header).
			if (data?.restored === true) {
				// A successful auto-restore puts the knob back at 100%: a
				// sticky "could not be restored" message is now false.
				clearSnack(MIC_GUARD_TOAST_ID);
				return undefined;
			}
			const level = data?.level;
			if (typeof level !== "number" || !Number.isFinite(level)) {
				return undefined;
			}
			const percent = String(Math.round(level * 100));
			const canSet = data?.can_set === true;

			const options: ShowSnackOptions = {
				id: MIC_GUARD_TOAST_ID,
				description: t("micGuard.loweredMessage"),
				// Sticky: the knob stays wrong until the user acts, so the
				// message must not scroll away on a timer (pack-toast pattern).
				persistent: true,
			};
			if (canSet) {
				options.action = {
					label: t("micGuard.backTo100"),
					onClick: () => {
						clearSnack(MIC_GUARD_TOAST_ID);
						void call("set_microphone_volume", {
							level: MIC_GUARD_RESTORE_LEVEL,
						}).catch(() => undefined);
					},
				};
			}
			showSnack(t("micGuard.loweredTitle", { percent }), "warning", options);
			return undefined;
		},
	);
}
