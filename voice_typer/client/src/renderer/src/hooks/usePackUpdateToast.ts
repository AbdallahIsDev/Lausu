// usePackUpdateToast, sticky voice-pack update toast with a Details action.
//
// The runtime-pack updater runs silently in the background
// (`check_offline_pack_update` on launch + on reconnect); the user
// otherwise never learns a voice-pack update is downloading. This
// hook is the ONLY transient pack surface (the Home hint line and the
// Microphone preparing banner were removed): it surfaces WORK and
// PROBLEMS as ONE sticky toast (fixed sonner id, replaced in place,
// never auto-dismissed):
//   - downloading / verifying: info toast (live percent while
//     downloading), Details action jumps to the About page.
//   - outdated (stale pack refused at launch): warning toast, same
//     Details action; a fresh download replaces it when it starts.
//   - missing: a NON-persistent info line (the download toast takes
//     over the moment a transfer starts).
// Routine startup lifecycle is deliberately silent: `offline_pack_verified`
// (background checksum pass) and `worker_started` (worker spawn) fire on
// every launch of a healthy install, and a sticky "Preparing offline
// engine…" for them made a normal start look broken.
// Terminal states clear the sticky toast and show a normal toast:
// ready → success, failed / corrupt / worker-crashed → error,
// worker-unloaded (benign RAM unload) → plain info. The close button
// always dismisses (sonner global); nothing re-fires until the next
// pack event.

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
			const raw = data?.progress ?? data?.percent;
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

	// A missing pack is the only startup state worth a line: the download
	// toast replaces this the moment a transfer starts. NOT persistent —
	// when no download is allowed it must not sit on screen forever
	// claiming to "prepare" something that is not happening.
	usePythonEvent("offline_pack_missing", (): (() => void) | undefined => {
		showSnack(t("pack.updateTitle"), "info", {
			id: PACK_UPDATE_TOAST_ID,
			description: t("pack.preparingOfflineEngine"),
			action: detailsAction,
		});
		return undefined;
	});

	// `offline_pack_verified` (background checksum pass) and `worker_started`
	// (worker spawn) fire on EVERY launch of a healthy install. They used to
	// raise a sticky "Preparing offline engine…" toast that never went away,
	// which made a normal start look like something was wrong. They are
	// background work and stay silent; a real download, a failure or an
	// outdated pack still surface below.

	usePythonEvent("worker_crashed", (): (() => void) | undefined => {
		fail(t("pack.packStateWorkerCrashed"));
		return undefined;
	});

	usePythonEvent("worker_unloaded", (): (() => void) | undefined => {
		clearSnack(PACK_UPDATE_TOAST_ID);
		showSnack(t("pack.packStateWorkerUnloaded"), "info");
		return undefined;
	});
}
