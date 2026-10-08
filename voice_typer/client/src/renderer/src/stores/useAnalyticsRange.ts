import { create } from "zustand";

// Type-only import: no runtime edge from `stores/` into `pages/`, and
// `RangeId` is the dashboard's own domain type (it lives next to the
// range-window math in `pages/dashboard/lib/streaks`).
import type { RangeId } from "@/pages/dashboard/lib/streaks";

/** Analytics time range — shared by the Analytics page + the title-bar control. */
export interface AnalyticsRangeState {
	range: RangeId;
	setRange: (range: RangeId) => void;
}

/** Every selectable range, in display order. The title-bar control maps
 *  these to labels; the store uses them to validate what it rehydrates. */
export const ANALYTICS_RANGES: readonly RangeId[] = [
	"today",
	"7d",
	"30d",
	"all",
];

const DEFAULT_RANGE: RangeId = "7d";

// Same `vt:filters:<page>.<key>` shape `useFilterState` writes, so a
// future migration to that helper keeps the persisted value.
const STORAGE_KEY = "vt:filters:analytics.range";

function isRangeId(value: unknown): value is RangeId {
	return (
		typeof value === "string" &&
		(ANALYTICS_RANGES as readonly string[]).includes(value)
	);
}

function readPersisted(): RangeId {
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		const parsed: unknown = raw ? JSON.parse(raw) : null;
		return isRangeId(parsed) ? parsed : DEFAULT_RANGE;
	} catch {
		return DEFAULT_RANGE;
	}
}

// A zustand store, NOT `useFilterState`: the title bar and the Analytics
// page are separate component trees, and that hook is component-local
// React state (two copies would drift the moment either side changes).
// Same rationale as `useModelsTab`.
export const useAnalyticsRange = create<AnalyticsRangeState>((set) => ({
	range:
		typeof sessionStorage === "undefined" ? DEFAULT_RANGE : readPersisted(),
	setRange: (range: RangeId) => {
		try {
			sessionStorage.setItem(STORAGE_KEY, JSON.stringify(range));
		} catch {
			/* best-effort */
		}
		set({ range });
	},
}));
