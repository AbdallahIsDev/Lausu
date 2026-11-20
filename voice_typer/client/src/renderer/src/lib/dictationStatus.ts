// One authority for "what state is dictation in" → "which colour says so".
// The Home pill and the sidebar caption both render a status dot, and two
// surfaces disagreeing about the same state is exactly the bug the shared
// `statusKeyFor` rule exists to prevent (C-HOME-1).

import type { RecordingState } from "@/types/ipc";

// Status-token palette, never literal colours: every theme preset and the
// custom-theme generator define --success/--info/--warning/--destructive.
export const STATUS_COLORS: Record<string, string> = {
	idle: "var(--muted-foreground)",
	recording: "var(--success)",
	transcribing: "var(--info)",
	loading: "var(--warning)",
	cancelling: "var(--warning)",
	error: "var(--destructive)",
};

export const DEFAULT_STATUS_COLOR = "var(--muted-foreground)";

/**
 * Status key for a live state pair.
 *
 * The `error` state only counts as an error when it carries a message: a
 * bare error state has nothing to explain, so it falls back to `idle` and
 * the UI never advertises a problem it cannot name.
 */
export function statusKeyFor(state: RecordingState, hasError: boolean): string {
	if (state === "error") {
		return hasError ? "error" : "idle";
	}
	return state;
}

/** Dot colour for a live state pair (same mapping on every surface). */
export function statusColorFor(
	state: RecordingState,
	hasError: boolean,
): string {
	return STATUS_COLORS[statusKeyFor(state, hasError)] ?? DEFAULT_STATUS_COLOR;
}
