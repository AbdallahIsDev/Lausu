// Hidden owner unlock for the developer-only Plugins surface: Ctrl+Shift+Alt+D
// three times persists `developer_mode: true` (Android developer-options model).
// Not a security boundary — the backend gate alone decides whether a plugin runs.

import { useCallback, useEffect, useRef } from "react";
import { useLatestRef } from "@/hooks/useLatestRef";
import type { PythonCall } from "@/hooks/usePython";
import { useSnackbar } from "@/hooks/useSnackbar";
import { useT } from "@/i18n/i18n";
import { useAppStore } from "@/stores/appStore";
import type { LausuConfig } from "@/types/config";

/** The sequence's letter. Ctrl+Shift+Alt is required; Meta must be absent. */
export const DEVELOPER_UNLOCK_KEY = "d";
/** Consecutive presses that unlock the surface. */
export const DEVELOPER_UNLOCK_PRESS_COUNT = 3;
/** Longest gap between two presses that still counts as the sequence. */
export const DEVELOPER_UNLOCK_WINDOW_MS = 1_500;

/**
 * Detect the unlock sequence and persist the flag.
 *
 * Only target presses are timestamped; other keystrokes are ignored. The
 * modifiers themselves fire keydown events on the way in, so resetting on
 * any unrelated key would make the sequence impossible to type.
 */
export function useDeveloperModeUnlock(call: PythonCall): void {
	const t = useT();
	const { showSnack } = useSnackbar();
	const unlocked = useAppStore((s) => s.config?.developer_mode === true);
	const callRef = useLatestRef(call);
	const unlockedRef = useLatestRef(unlocked);
	const inFlightRef = useRef(false);

	const unlock = useCallback(async () => {
		// The backend push may already have flipped the flag while the third
		// press was in flight; a second write would be a needless round-trip.
		if (unlockedRef.current || inFlightRef.current) return;
		inFlightRef.current = true;
		try {
			await callRef.current("set_config", { developer_mode: true });
			const fresh = await callRef.current<LausuConfig>("get_config");
			if (fresh) {
				const setConfig = useAppStore.getState().setConfig;
				setConfig(fresh);
			}
			showSnack(t("plugins.unlocked"), "success");
		} catch (err) {
			console.error(
				"[renderer:useDeveloperModeUnlock] set_config failed:",
				err,
			);
			showSnack(t("plugins.unlockFailed"), "error");
		} finally {
			inFlightRef.current = false;
		}
	}, [callRef, showSnack, t, unlockedRef]);

	useEffect(() => {
		// Already unlocked: the surface is visible, so the sequence has no
		// job left and the listener comes off entirely.
		if (unlocked) return;
		let presses: number[] = [];
		const handler = (e: KeyboardEvent) => {
			if (e.repeat) return;
			if (e.metaKey || !e.ctrlKey || !e.shiftKey || !e.altKey) return;
			if (e.key.toLowerCase() !== DEVELOPER_UNLOCK_KEY) return;
			e.preventDefault();
			const now = Date.now();
			presses = presses.filter((at) => now - at <= DEVELOPER_UNLOCK_WINDOW_MS);
			presses.push(now);
			if (presses.length < DEVELOPER_UNLOCK_PRESS_COUNT) return;
			presses = [];
			void unlock();
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [unlock, unlocked]);
}
