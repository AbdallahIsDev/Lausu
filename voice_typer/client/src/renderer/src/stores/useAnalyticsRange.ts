import { create } from "zustand";
import { localDateKey } from "@/lib/format";
// Type-only import: no runtime edge from `stores/` into `pages/`, and
// `RangeId` is the dashboard's own domain type (it lives next to the
// range-window math in `pages/dashboard/lib/streaks`). CustomWindow is
// the same shared shape so store and stats never drift apart.
import type { CustomWindow, RangeId } from "@/pages/dashboard/lib/streaks";

/** Preset ranges (the title-bar pill row). `"custom"` is separate. */
export type PresetRange = Exclude<RangeId, "custom">;

/** Analytics time range — shared by the Analytics page + the title-bar control. */
export interface AnalyticsRangeState {
	range: RangeId;
	customWindow: CustomWindow | null;
	setRange: (range: PresetRange) => void;
	setCustomRange: (window: CustomWindow) => void;
}

/** Every selectable preset, in display order. The title-bar control maps
 *  these to labels; the store uses them to validate what it rehydrates.
 *  Custom windows ride alongside (never in this list). */
export const ANALYTICS_RANGES: readonly PresetRange[] = [
	"today",
	"7d",
	"30d",
	"all",
];

/** Custom windows cap at ~a year: the chart draws daily bars and the
 *  backend pages 500 rows at a time, unbounded spans serve neither. */
export const CUSTOM_RANGE_MAX_DAYS = 366;

const DEFAULT_RANGE: RangeId = "7d";

// Same `vt:filters:<page>.<key>` shape `useFilterState` writes, so a
// future migration to that helper keeps the persisted value.
const STORAGE_KEY = "vt:filters:analytics.range";

const DAY_KEY_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Persisted shapes: legacy bare preset string, or an object for custom. */
type PersistedRange =
	| PresetRange
	| { range: "custom"; customStart: string; customEnd: string };

function daySpanDays(startKey: string, endKey: string): number {
	// YYYY-MM-DD parses as UTC: DST-proof span arithmetic.
	return (
		Math.round(
			(Date.parse(`${endKey}T00:00:00Z`) -
				Date.parse(`${startKey}T00:00:00Z`)) /
				86400000,
		) + 1
	);
}

export function isValidCustomWindow(
	value: unknown,
	todayKey: string,
): value is CustomWindow {
	if (typeof value !== "object" || value === null) return false;
	const { startKey, endKey } = value as Record<string, unknown>;
	if (
		typeof startKey !== "string" ||
		typeof endKey !== "string" ||
		!DAY_KEY_RE.test(startKey) ||
		!DAY_KEY_RE.test(endKey)
	)
		return false;
	if (startKey > endKey || endKey > todayKey) return false;
	const span = daySpanDays(startKey, endKey);
	return span >= 1 && span <= CUSTOM_RANGE_MAX_DAYS;
}

function isPresetRange(value: unknown): value is PresetRange {
	return (
		typeof value === "string" &&
		(ANALYTICS_RANGES as readonly string[]).includes(value)
	);
}

function readPersisted(): {
	range: RangeId;
	customWindow: CustomWindow | null;
} {
	const fallback = { range: DEFAULT_RANGE, customWindow: null } as const;
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		if (raw === null) return { ...fallback };
		const parsed: unknown = JSON.parse(raw);
		if (isPresetRange(parsed)) return { range: parsed, customWindow: null };
		if (typeof parsed === "object" && parsed !== null) {
			const { range, customStart, customEnd } = parsed as Record<
				string,
				unknown
			>;
			if (range === "custom") {
				const todayKey = localDateKey(new Date());
				const window = { startKey: customStart, endKey: customEnd };
				if (isValidCustomWindow(window, todayKey))
					return { range: "custom", customWindow: window };
			}
		}
		return { ...fallback };
	} catch {
		return { ...fallback };
	}
}

function persist(range: RangeId, customWindow: CustomWindow | null): void {
	try {
		// Presets keep the legacy bare-string shape; custom persists the
		// window it needs to rehydrate.
		const payload: PersistedRange =
			range === "custom" && customWindow !== null
				? {
						range: "custom",
						customStart: customWindow.startKey,
						customEnd: customWindow.endKey,
					}
				: (range as PresetRange);
		sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
	} catch {
		/* best-effort */
	}
}

// A zustand store, NOT `useFilterState`: the title bar and the Analytics
// page are separate component trees, and that hook is component-local
// React state (two copies would drift the moment either side changes).
// Same rationale as `useModelsTab`.
export const useAnalyticsRange = create<AnalyticsRangeState>((set, get) => ({
	...(typeof sessionStorage === "undefined"
		? { range: DEFAULT_RANGE, customWindow: null }
		: readPersisted()),
	setRange: (range: PresetRange) => {
		// The last custom window stays in state (not persisted): flipping
		// back to Custom restores it instead of opening an empty picker.
		persist(range, get().customWindow);
		set({ range });
	},
	setCustomRange: (window: CustomWindow) => {
		// Fail-closed on garbage (programmer error, never user input:
		// the picker + rehydrate paths validate first).
		if (!isValidCustomWindow(window, localDateKey(new Date()))) return;
		persist("custom", window);
		set({ range: "custom", customWindow: window });
	},
}));
