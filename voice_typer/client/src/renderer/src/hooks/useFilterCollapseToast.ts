// Single consumer of the ``filter_collapse`` push event: the backend's guard
// proved the filter chain removed speech and delivered the take unfiltered.
// Copy names the state and offers the one screen that can change it; the
// method and dB detail stay in the backend log (C-UXERR-1, C-UXERR-5).
// Rationale: docs/microphone-filter-failures.md §2.3.
//
// The meter and the mic test run the same chain, so they publish the same
// event with reason ``monitor_collapse`` when they fall back to the raw
// signal. Same shape, different state to report: the copy must say the meter
// changed, not that a take was transcribed.

import { usePythonEvent } from "@/hooks/usePython";
import type { TranslateFn } from "@/i18n/translate-types";
import { SNACKBAR_DEFAULT_DURATION_MS, useSnackbar } from "./useSnackbar";

/** Sonner id: the newest collapse report replaces the in-flight one. */
export const FILTER_COLLAPSE_TOAST_ID = "filter-collapse";

/** Reason published when the level meter / mic test bypasses the chain. */
export const MONITOR_COLLAPSE_REASON = "monitor_collapse";

export function useFilterCollapseToast(
	t: TranslateFn,
	onOpenMicrophone: () => void,
): void {
	const { showSnack } = useSnackbar();
	usePythonEvent("filter_collapse", (data): (() => void) | undefined => {
		const monitor = data?.reason === MONITOR_COLLAPSE_REASON;
		showSnack(
			t(
				monitor
					? "degradation.filterCollapseMonitor"
					: "degradation.filterCollapse",
			),
			"warning",
			{
				id: FILTER_COLLAPSE_TOAST_ID,
				// The remedy is identical for both states (pick another method on
				// the Microphone page), so the hint is shared, not duplicated.
				description: t("degradation.filterCollapseHint"),
				duration: SNACKBAR_DEFAULT_DURATION_MS.error,
				action: {
					label: t("nav.microphone"),
					onClick: onOpenMicrophone,
				},
			},
		);
		return undefined;
	});
}
