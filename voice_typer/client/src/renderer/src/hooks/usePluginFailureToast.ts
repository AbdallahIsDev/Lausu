// Surfaces plugin dictation failures as ONE in-app snackbar. The same
// message is also sent to the OS by the backend's tray notification.
import { usePythonEvent } from "@/hooks/usePython";
import { SNACKBAR_DEFAULT_DURATION_MS, useSnackbar } from "./useSnackbar";

export function usePluginFailureToast(): void {
	const { showSnack } = useSnackbar();
	usePythonEvent("plugin_failure", (data) => {
		const message = (data as { message?: unknown } | undefined)?.message;
		if (typeof message !== "string" || !message) return;
		showSnack(message, "warning", {
			duration: SNACKBAR_DEFAULT_DURATION_MS.error,
		});
	});
}
