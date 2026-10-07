import type { ScreenshotRect } from "@/bubble/ScreenshotOverlay";

// Bridge-agnostic screenshot-beta IPC helpers (Windows-only beta).
// Wire shapes mirror `ScreenshotHandlersMixin`
// (`voice_typer/server/handlers/screenshot_handlers.py`).
// The bubble window is sandboxed (SEC-026): under Tauri it gets ONLY
// `window.bubble`, never `window.python`, so every helper resolves
// `undefined` when the bridge is absent instead of throwing. Callers
// treat that as "backend unreachable", the recording keeps running.

function pythonCall(
	type: string,
	data?: Record<string, unknown>,
): Promise<unknown> {
	const api = window.python;
	if (!api) return Promise.resolve(undefined);
	return api.call({ type, data });
}

// Cycle ids are minted by the renderer, one per recording
// (`YYYY-MM-DD_<epoch-ms>`). The backend treats the id opaquely
// (sanitized into `<profile>/screenshots/<date>/<cycle>/`), so a
// fresh id is inherently a clean one-shot cycle.
export function mintScreenshotCycleId(now: number = Date.now()): string {
	const d = new Date(now);
	const day = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
	return `${day}_${now}`;
}

/** Send the device-pixel capture rect for this recording's cycle. */
export function captureScreenshot(
	cycleId: string,
	rect: ScreenshotRect,
): Promise<unknown> {
	return pythonCall("screenshot_capture", { cycle_id: cycleId, rect });
}

/** Delete one cycle's screenshot dir (history-entry deletion path). */
export function clearScreenshotCycle(cycleId: string): Promise<unknown> {
	return pythonCall("screenshot_clear_cycle", { cycle_id: cycleId });
}

/** Read the backend status (optionally with store status for a cycle). */
export function getScreenshotStatus(cycleId?: string): Promise<unknown> {
	return pythonCall(
		"screenshot_get_status",
		cycleId === undefined ? undefined : { cycle_id: cycleId },
	);
}

/** Persist the screenshot consent flag (also grantable via the gate). */
export function setScreenshotConsent(consented: boolean): Promise<unknown> {
	return pythonCall("screenshot_set_consent", { consented });
}
