// Hidden owner toggle for the developer-only Plugins surface: three presses of
// Ctrl+Shift+Alt+D within a short window flip developer_mode (hidden -> visible
// -> hidden). Not a security boundary — the backend gate alone decides whether
// a plugin runs.

import { useCallback, useEffect, useRef } from "react";
import { useLatestRef } from "@/hooks/useLatestRef";
import type { PythonCall } from "@/hooks/usePython";
import { useSnackbar } from "@/hooks/useSnackbar";
import { useT } from "@/i18n/i18n";
import { useAppStore } from "@/stores/appStore";
import type { LausuConfig } from "@/types/config";

/** The toggle's letter. Ctrl+Shift+Alt is required; Meta must be absent. */
export const DEVELOPER_TOGGLE_KEY = "d";
export const DEVELOPER_UNLOCK_PRESS_COUNT = 3;
export const DEVELOPER_UNLOCK_WINDOW_MS = 1500;

/**
 * Toggle the Plugins surface and persist the flag after three presses.
 *
 * The counter resets after firing, so the next three presses toggle back.
 * Auto-repeat and Meta-modified presses are ignored.
 */
export function useDeveloperModeUnlock(call: PythonCall): void {
	const t = useT();
	const { showSnack } = useSnackbar();
	const enabled = useAppStore((s) => s.config?.developer_mode === true);
	const callRef = useLatestRef(call);
	const enabledRef = useLatestRef(enabled);
	const inFlightRef = useRef(false);
	const pressesRef = useRef<number[]>([]);

	const toggle = useCallback(async () => {
		// The backend push may already have flipped the flag while the key
		// press was in flight; a second write would be a needless round-trip.
		if (inFlightRef.current) return;
		const next = !enabledRef.current;
		inFlightRef.current = true;
		try {
			await callRef.current("set_config", { developer_mode: next });
			const fresh = await callRef.current<LausuConfig>("get_config");
			if (fresh) {
				const setConfig = useAppStore.getState().setConfig;
				setConfig(fresh);
			}
			showSnack(
				t(next ? "plugins.unlocked" : "plugins.hidden"),
				next ? "success" : "info",
			);
		} catch (err) {
			console.error(
				"[renderer:useDeveloperModeUnlock] set_config failed:",
				err,
			);
			showSnack(t("plugins.unlockFailed"), "error");
		} finally {
			inFlightRef.current = false;
		}
	}, [callRef, showSnack, t, enabledRef]);

	useEffect(() => {
		const handler = (e: KeyboardEvent) => {
			if (e.repeat) return;
			if (e.metaKey || !e.ctrlKey || !e.shiftKey || !e.altKey) return;
			if (e.key.toLowerCase() !== DEVELOPER_TOGGLE_KEY) return;
			e.preventDefault();
			const now = Date.now();
			const recent = pressesRef.current.filter(
				(at) => now - at <= DEVELOPER_UNLOCK_WINDOW_MS,
			);
			recent.push(now);
			pressesRef.current = recent;
			if (recent.length < DEVELOPER_UNLOCK_PRESS_COUNT) return;
			pressesRef.current = [];
			void toggle();
		};
		window.addEventListener("keydown", handler);
		return () => window.removeEventListener("keydown", handler);
	}, [toggle]);
}
