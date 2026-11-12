// GpuRequestDialog, the "you asked for GPU, here is what that needs" modal.
//
// Opened by `DeviceToggle` when the user picks GPU for a backend whose
// `active_backend_gpu_ready` is false. It branches on the capability state
// so it never offers a button that cannot work:
//
//   gpu_present_cuda_missing  → explain the CUDA runtime, offer
//                               [Download] (starts the real install job)
//                               and [Stay on CPU] (writes nothing).
//   driver_missing            → explain that only the NVIDIA installer can
//                               add a driver (admin elevation + reboot),
//                               link out to the vendor page, offer only
//                               [Stay on CPU]. No Download button: the app
//                               cannot install a kernel driver.
//   download unsupported      → same shape as driver_missing but without
//                               the link (wrong OS / unsupported Python).
//   gpu_ready                 → the modal is meaningless; renders nothing.
//
// "Stay on CPU" is a dismissal, not a write: no `set_config`, no job. The
// dialog is a plain `Dialog` (not AlertDialog) so backdrop/Escape dismiss
// exactly like the button — refusing must never trap the user.

import { useCallback, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { usePython } from "@/hooks/usePython";
import { useSnackbar } from "@/hooks/useSnackbar";
import { useT } from "@/i18n/i18n";
import { openExternalUrl } from "@/lib/external-links";
import { formatBytes } from "@/lib/format";
import { useAppStore } from "@/stores/appStore";

export interface GpuRequestDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
}

export function GpuRequestDialog({
	open,
	onOpenChange,
}: GpuRequestDialogProps) {
	const t = useT();
	const { call } = usePython();
	const { showSnack } = useSnackbar();
	const capability = useAppStore((s) => s.config?.gpu_capability);
	const [starting, setStarting] = useState(false);

	const state = capability?.state;
	const driverUrl = capability?.driver_url;
	// Readiness is per BACKEND. `state === "gpu_ready"` only means SOME
	// backend works (e.g. CTranslate2), so gating on it left a Parakeet user
	// with no route to the CUDA download.
	const activeEntry = capability?.backends?.find(
		(entry) => entry.name === capability?.active_backend,
	);
	const activeCapable = activeEntry ? activeEntry.gpu_capable !== false : true;
	const activeReady = activeEntry
		? activeEntry.gpu_ready === true
		: capability?.active_backend_gpu_ready === true;
	const needsCuda = activeCapable && !activeReady;
	const isDriverBranch = state === "driver_missing";
	const canDownload =
		needsCuda && !isDriverBranch && capability?.download?.supported === true;
	const totalBytes = capability?.download?.total_bytes ?? 0;

	const handleDownload = useCallback(async () => {
		if (starting) return;
		setStarting(true);
		try {
			await call("start_cuda_download");
			// The sticky `cuda_progress` toast takes over from here; the
			// dialog's job is done.
			onOpenChange(false);
		} catch (err) {
			console.warn(
				"[renderer:GpuRequestDialog] start_cuda_download failed:",
				err,
			);
			showSnack(t("gpuSwitch.errorInternal"), "error");
		} finally {
			setStarting(false);
		}
	}, [starting, call, onOpenChange, showSnack, t]);

	const handleDriverPage = useCallback(() => {
		if (!driverUrl) return;
		void openExternalUrl(driverUrl);
	}, [driverUrl]);

	const handleStayOnCpu = useCallback(() => {
		// Deliberately writes nothing and starts nothing.
		onOpenChange(false);
	}, [onOpenChange]);

	// Only "no NVIDIA hardware at all" (or no capability report) suppresses
	// the dialog, plus the defensive case where the active backend turned out
	// to be ready after all — the modal exists to explain a gap that is not
	// there. Every hook above runs unconditionally, so this return is safe.
	if (!capability || state === "no_nvidia_gpu" || !needsCuda) {
		return null;
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>
						{isDriverBranch
							? t("gpuSwitch.driverMissingTitle")
							: t("gpuSwitch.dialogTitle")}
					</DialogTitle>
					<DialogDescription>
						{isDriverBranch
							? t("gpuSwitch.driverMissingBody")
							: canDownload
								? t("gpuSwitch.cudaMissingBody", {
										size: formatBytes(totalBytes),
									})
								: t("gpuSwitch.errorUnsupported")}
					</DialogDescription>
				</DialogHeader>
				{/* Two ends: the explanatory action on the left, the decision on
				    the right (C-UI-10 — no margin utilities for spacing). */}
				<DialogFooter className="sm:justify-between">
					{isDriverBranch && driverUrl ? (
						<Button type="button" variant="ghost" onClick={handleDriverPage}>
							{t("gpuSwitch.driverMissingAction")}
						</Button>
					) : (
						<span />
					)}
					<div className="flex items-center gap-2">
						{/* Plain Buttons, not Radix Close primitives: the dialog must
						    stay open when the download call fails. */}
						<Button type="button" variant="ghost" onClick={handleStayOnCpu}>
							{t("gpuSwitch.stayOnCpu")}
						</Button>
						{canDownload ? (
							<Button
								type="button"
								onClick={handleDownload}
								disabled={starting}
							>
								{t("gpuSwitch.download")}
							</Button>
						) : null}
					</div>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
