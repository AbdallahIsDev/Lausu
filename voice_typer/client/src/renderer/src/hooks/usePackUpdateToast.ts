// usePackUpdateToast, sticky voice-pack update toast with a Details action.
//
// The runtime-pack updater runs silently in the background
// (`check_offline_pack_update` on launch + on reconnect); the user
// otherwise never learns a voice-pack update is downloading. This
// hook surfaces the two states that deserve attention as ONE sticky
// toast (fixed sonner id, replaced in place, never auto-dismissed):
//   - downloading / verifying: info toast with live percent, Details
//     action jumps to the About page (pack status + update outcome).
//   - outdated (stale pack refused at launch): warning toast, same
//     Details action; a fresh download replaces it when it starts.
// Terminal states clear the sticky toast and show a normal toast:
// ready → success, failed / corrupt → error. The close button always
// dismisses (sonner global); nothing re-fires until the next download
// or outdated event.

import { usePythonEvent } from "@/hooks/usePython";
import type { TranslateFn } from "@/i18n/translate-types";
import { useSnackbar } from "./useSnackbar";

/** Sonner id: all pack-update states replace this one toast. */
export const PACK_UPDATE_TOAST_ID = "pack-update";

export function usePackUpdateToast(
	t: TranslateFn,
	onViewDetails: () => void,
): void {
	const { showSnack, clearSnack } = useSnackbar();

	const detailsAction = {
		label: t("pack.viewDetails"),
		onClick: onViewDetails,
	};

	usePythonEvent(
		"offline_pack_download_started",
		(): (() => void) | undefined => {
			showSnack(t("pack.updateTitle"), "info", {
				id: PACK_UPDATE_TOAST_ID,
				description: t("pack.downloadingOfflineEngine", { percent: "0" }),
				persistent: true,
				action: detailsAction,
			});
			return undefined;
		},
	);

	usePythonEvent(
		"offline_pack_download_progress",
		(data?: Record<string, unknown>): (() => void) | undefined => {
			const raw = data?.["progress"] ?? data?.["percent"];
			const pct =
				typeof raw === "number" && Number.isFinite(raw)
					? Math.max(0, Math.min(100, Math.round(raw)))
					: null;
			showSnack(t("pack.updateTitle"), "info", {
				id: PACK_UPDATE_TOAST_ID,
				description:
					pct === null
						? t("pack.downloadingOfflineEngine", { percent: "…" })
						: t("pack.downloadingOfflineEngine", {
								percent: String(pct),
							}),
				persistent: true,
				action: detailsAction,
			});
			return undefined;
		},
	);

	usePythonEvent(
		"offline_pack_download_completed",
		(): (() => void) | undefined => {
			showSnack(t("pack.updateTitle"), "info", {
				id: PACK_UPDATE_TOAST_ID,
				description: t("pack.updateVerifying"),
				persistent: true,
				action: detailsAction,
			});
			return undefined;
		},
	);

	usePythonEvent("offline_pack_ready", (): (() => void) | undefined => {
		clearSnack(PACK_UPDATE_TOAST_ID);
		showSnack(t("pack.updateReady"), "success");
		return undefined;
	});

	const fail = (message: string): void => {
		clearSnack(PACK_UPDATE_TOAST_ID);
		showSnack(message, "error");
	};

	usePythonEvent(
		"offline_pack_download_failed",
		(): (() => void) | undefined => {
			fail(t("pack.updateFailed"));
			return undefined;
		},
	);

	usePythonEvent("offline_pack_corrupt", (): (() => void) | undefined => {
		fail(t("pack.updateFailed"));
		return undefined;
	});

	usePythonEvent("offline_pack_outdated", (): (() => void) | undefined => {
		showSnack(t("pack.updateTitle"), "warning", {
			id: PACK_UPDATE_TOAST_ID,
			description: t("pack.outdatedDescription"),
			persistent: true,
			action: detailsAction,
		});
		return undefined;
	});
}
