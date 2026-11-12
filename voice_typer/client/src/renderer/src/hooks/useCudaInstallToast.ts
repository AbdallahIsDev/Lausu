// useCudaInstallToast, the persistent GPU-install notification plus the
// automatic switch that follows a finished install.
//
// The install job is long (>1 GB across five wheels) and survives page
// navigation, so its progress cannot live in a page. This hook is mounted
// ONCE in App.tsx next to `usePackUpdateToast` and owns the whole
// `cuda_progress` lifecycle:
//
//   downloading / verifying / installing
//       ONE sticky toast (fixed sonner id, replaced in place, never
//       auto-dismissed) showing status, artifact name + index/count,
//       bytes done/total, percent, speed and ETA.
//   completed
//       The job is done but the GPU is NOT serving yet. The sticky toast
//       switches to "Restarting the speech engine…", the sidecar is
//       respawned through the host's `restart_sidecar` command, and the
//       hook polls `get_gpu_capability` until the respawned sidecar has
//       proven the stack (its `apply_pending_activation` persists
//       `device=cuda` only after a real backend reports GPU readiness).
//       `config.device` therefore stays "cpu" the whole time.
//   failed / cancelled
//       Terminal: the sticky toast is cleared and replaced by a normal
//       error / info toast. CPU stays selected.
//
// The toast is cleared ONLY on those three terminal outcomes, which is the
// contract the owner asked for: a notification that never disappears while
// work is in flight, and a device pill that only moves once the GPU is
// actually usable (C-UI-15).

import { useCallback, useEffect, useRef } from "react";
import { usePython, usePythonEvent } from "@/hooks/usePython";
import type { TranslateFn } from "@/i18n/translate-types";
import { formatBytes, formatSpeed } from "@/lib/format";
import { useAppStore } from "@/stores/appStore";
import type { CudaInstallProgress, GpuCapability } from "@/types/config";
import { useSnackbar } from "./useSnackbar";

/** Sonner id: every install state replaces this one toast. */
export const CUDA_INSTALL_TOAST_ID = "cuda-install";

/** Job statuses that mean "work is in flight, keep the sticky toast". */
const RUNNING_STATUSES: readonly string[] = [
	"downloading",
	"verifying",
	"installing",
];

/** Poll budget after the respawn (40 × 500 ms = 20 s of boot). */
const CONFIRM_ATTEMPTS = 40;
const CONFIRM_INTERVAL_MS = 500;

export function isRunningStatus(status: string | null | undefined): boolean {
	return typeof status === "string" && RUNNING_STATUSES.includes(status);
}

/**
 * Map an install error code to its user-facing message key. Unknown codes
 * fall back to the generic failure line rather than leaking a raw code.
 */
export function installErrorKey(code: string | null | undefined): string {
	switch (code) {
		case "checksum_mismatch":
		case "corrupt_wheel":
			return "gpuSwitch.errorChecksum";
		case "size_mismatch":
			return "gpuSwitch.errorSize";
		case "network":
			return "gpuSwitch.errorNetwork";
		case "insufficient_disk":
		case "disk_unavailable":
			return "gpuSwitch.errorDisk";
		case "unsupported_python":
		case "unsupported_platform":
		case "unsupported_runtime":
			return "gpuSwitch.errorUnsupported";
		default:
			return "gpuSwitch.errorInternal";
	}
}

/** Compact ETA: `42s`, `3m 20s`, `1h 05m`. Empty when unknown. */
export function formatEta(seconds: number | null | undefined): string {
	if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return "";
	const total = Math.round(seconds);
	if (total < 60) return `${total}s`;
	const minutes = Math.floor(total / 60);
	const rest = total % 60;
	if (minutes < 60) return `${minutes}m ${String(rest).padStart(2, "0")}s`;
	const hours = Math.floor(minutes / 60);
	return `${hours}h ${String(minutes % 60).padStart(2, "0")}m`;
}

/**
 * One-line description for the sticky toast. Every field the owner asked
 * for is present; unknown pieces are omitted instead of rendering "NaN".
 */
export function describeProgress(
	t: TranslateFn,
	progress: CudaInstallProgress,
): string {
	const parts: string[] = [];
	if (progress.status === "verifying") {
		parts.push(t("gpuSwitch.toastVerifying"));
	} else if (progress.status === "installing") {
		parts.push(t("gpuSwitch.toastInstalling"));
	} else {
		parts.push(t("gpuSwitch.statusDownloading"));
	}
	if (progress.artifact) {
		parts.push(
			t("gpuSwitch.toastArtifact", {
				name: progress.artifact,
				index: String(progress.artifact_index + 1),
				count: String(progress.artifact_count),
			}),
		);
	}
	if (progress.bytes_total > 0) {
		parts.push(
			t("gpuSwitch.toastProgress", {
				percent: String(Math.round(progress.percent)),
				done: formatBytes(progress.bytes_done),
				total: formatBytes(progress.bytes_total),
			}),
		);
	}
	if (progress.speed_bps > 0) {
		const eta = formatEta(progress.eta_seconds);
		parts.push(
			eta
				? t("gpuSwitch.toastSpeed", {
						speed: formatSpeed(progress.speed_bps),
						eta,
					})
				: formatSpeed(progress.speed_bps),
		);
	}
	return parts.join(" · ");
}

type RespawnResult = { ok: boolean; reason?: string };

export function useCudaInstallToast(t: TranslateFn): void {
	const { showSnack, clearSnack } = useSnackbar();
	const { call } = usePython();

	// One flow at a time: a second `completed` (or a remount during the
	// respawn) must not start a parallel restart/poll chain.
	const switchingRef = useRef(false);
	// The sticky toast is only re-shown while a job is genuinely in flight.
	const lastStatusRef = useRef<string | null>(null);

	const showSticky = useCallback(
		(description: string, cancellable = true) => {
			showSnack(t("gpuSwitch.toastTitle"), "info", {
				id: CUDA_INSTALL_TOAST_ID,
				description,
				persistent: true,
				// Once the job has finished there is nothing left to cancel:
				// the toast is showing the respawn/confirmation phase, so a
				// Cancel button would be a control that does nothing.
				...(cancellable
					? {
							action: {
								label: t("gpuSwitch.cancelDownload"),
								onClick: () => {
									void call("cancel_cuda_download").catch((err) => {
										console.warn(
											"[renderer:useCudaInstallToast] cancel_cuda_download failed:",
											err,
										);
									});
								},
							},
						}
					: {}),
			});
		},
		[showSnack, t, call],
	);

	const finish = useCallback(
		(message: string, type: "success" | "error" | "info") => {
			clearSnack(CUDA_INSTALL_TOAST_ID);
			showSnack(message, type);
		},
		[clearSnack, showSnack],
	);

	/**
	 * Re-read config so the sidebar pill sees the backend's decision.
	 *
	 * Returns the freshly-read snapshot (or `null` when the read failed) so
	 * the confirm step can require the PERSISTED `device` — the pill moving
	 * is the backend's own statement that activation succeeded, and the
	 * toast must not run ahead of it.
	 */
	const refreshConfig = useCallback(async () => {
		try {
			const config = await call<Record<string, unknown>>("get_config");
			if (config && typeof config === "object") {
				// `mergeConfig` is a plain zustand action, not a hook: the store
				// stays the single source for `device` / `active_device`, and the
				// pill moves only after the backend has written `cuda`.
				useAppStore.getState().mergeConfig(config as never);
				return config;
			}
		} catch (err) {
			console.warn(
				"[renderer:useCudaInstallToast] get_config refresh failed:",
				err,
			);
		}
		return null;
	}, [call]);

	const acknowledgeFailure = useCallback(
		(reason: string | null | undefined) => {
			// Show the reason once, then clear the record so the failure is
			// not re-reported on every later capability read.
			finish(
				t("gpuSwitch.toastActivationFailed", {
					reason: reason || t("gpuSwitch.errorInternal"),
				}),
				"error",
			);
			void call("ack_cuda_activation").catch((err) => {
				console.warn(
					"[renderer:useCudaInstallToast] ack_cuda_activation failed:",
					err,
				);
			});
		},
		[t, finish, call],
	);

	const confirmGpu = useCallback(async () => {
		showSticky(t("gpuSwitch.toastActivating"), false);
		try {
			for (let attempt = 0; attempt < CONFIRM_ATTEMPTS; attempt += 1) {
				try {
					const capability = await call<GpuCapability>("get_gpu_capability");
					if (capability?.activation?.state === "failed") {
						acknowledgeFailure(capability.activation.reason);
						await refreshConfig();
						return;
					}
					// Success needs BOTH halves of the same decision activation
					// makes: the whole stack proven (`stack_complete`, the
					// acceptance signal in `activation.py` / the `set_config`
					// guard) AND the backend having actually persisted
					// `device: "cuda"`.
					//
					// `active_backend_gpu_ready` alone is NOT enough: with
					// Whisper active and the ORT GPU wheel broken it is true
					// while activation refuses to switch, so the toast would
					// announce a GPU the app never uses. And the poll can win a
					// race against `apply_pending_activation` itself, so a
					// complete stack without the persisted device keeps polling
					// instead of declaring victory early.
					if (capability?.stack_complete === true) {
						const config = await refreshConfig();
						if (config?.device === "cuda") {
							finish(t("gpuSwitch.toastReady"), "success");
							return;
						}
					}
				} catch (err) {
					// The sidecar is mid-respawn; the bridge answers "not
					// connected" for a moment. Retry, do not fail the flow.
					console.debug(
						"[renderer:useCudaInstallToast] capability read during respawn:",
						err,
					);
				}
				await new Promise((resolve) =>
					setTimeout(resolve, CONFIRM_INTERVAL_MS),
				);
			}
			// Never leave the sticky toast spinning after the poll budget.
			await refreshConfig();
			finish(t("gpuSwitch.toastFailed"), "error");
		} finally {
			// One flow at a time: release the guard on EVERY exit path so a
			// later install can still switch the device.
			switchingRef.current = false;
		}
	}, [showSticky, t, call, finish, acknowledgeFailure, refreshConfig]);

	const restartAndConfirm = useCallback(async () => {
		if (switchingRef.current) return;
		switchingRef.current = true;
		// The job is already complete: no Cancel control from here on.
		showSticky(t("gpuSwitch.toastRestarting"), false);
		let result: RespawnResult = { ok: false, reason: "no_bridge" };
		try {
			const restart = window.window_?.restartBackend;
			if (restart) result = await restart();
		} catch (err) {
			result = {
				ok: false,
				reason: err instanceof Error ? err.message : String(err),
			};
		}
		if (!result?.ok) {
			// The respawn command itself refused: nothing will ever prove
			// the stack in this process, so report and stay on CPU.
			switchingRef.current = false;
			console.warn(
				"[renderer:useCudaInstallToast] restart_sidecar failed:",
				result?.reason,
			);
			await refreshConfig();
			finish(t("gpuSwitch.toastFailed"), "error");
			return;
		}
		await confirmGpu();
	}, [showSticky, t, confirmGpu, refreshConfig, finish]);

	usePythonEvent(
		"cuda_progress",
		(data?: CudaInstallProgress): (() => void) | undefined => {
			if (!data || typeof data.status !== "string") return undefined;
			lastStatusRef.current = data.status;
			switch (data.status) {
				case "downloading":
				case "verifying":
				case "installing":
					showSticky(describeProgress(t, data));
					return undefined;
				case "completed":
					void restartAndConfirm();
					return undefined;
				case "cancelled":
					switchingRef.current = false;
					finish(t("gpuSwitch.toastCancelled"), "info");
					return undefined;
				case "failed":
					switchingRef.current = false;
					finish(t(installErrorKey(data.error)), "error");
					return undefined;
				default:
					return undefined;
			}
		},
	);

	// Reattach after a renderer reload: a job that is still running must
	// restore its sticky toast, and an activation failure recorded while
	// the window was closed must still be explained exactly once.
	useEffect(() => {
		let cancelled = false;
		const reattach = async () => {
			try {
				const capability = await call<GpuCapability>("get_gpu_capability");
				if (cancelled || !capability) return;
				if (capability.activation?.state === "failed") {
					acknowledgeFailure(capability.activation.reason);
					return;
				}
				const progress = capability.download?.progress;
				if (progress && isRunningStatus(progress.status)) {
					showSticky(describeProgress(t, progress));
				}
			} catch (err) {
				console.debug(
					"[renderer:useCudaInstallToast] reattach read failed:",
					err,
				);
			}
		};
		void reattach();
		return () => {
			cancelled = true;
		};
		// Every dependency is referentially stable (`t` is the module-level
		// translator, `call`/`showSnack`/`clearSnack` are empty-dep
		// useCallbacks), so this runs once per mount while still satisfying
		// the exhaustive-deps rule. Later capability reads are driven by
		// `cuda_progress`.
	}, [acknowledgeFailure, call, showSticky, t]);
}
