// Owner-only UI variant preferences, driven by the bottom-right Debug Panel.
// localStorage + a window event keeps every mounted consumer in sync without a
// new store (mirrors the guarded style of usePluginsNewBadge).

import { useCallback, useEffect, useState } from "react";
import type { PluginsBadgeHue } from "@/components/layout/PluginsNewBadge";

export const DEBUG_STATS_LAYOUT_KEY = "lausu-ui-debug-stats-layout";
export const DEBUG_BADGE_HUE_KEY = "lausu-ui-debug-badge-hue";
export const DEBUG_PREFS_EVENT = "lausu-debug-prefs-changed";
/** Debug Panel visibility stays off until the owner explicitly opts in. */
export const DEBUG_PANEL_VISIBLE_KEY = "lausu-ui-debug-panel-visible";

export type StatsLayout = "separated" | "joined";

export interface DebugPrefs {
	statsLayout: StatsLayout;
	badgeHue: PluginsBadgeHue;
}

const DEFAULTS: DebugPrefs = { statsLayout: "separated", badgeHue: "green" };

function readPrefs(): DebugPrefs {
	try {
		const layout = localStorage.getItem(DEBUG_STATS_LAYOUT_KEY);
		const hue = localStorage.getItem(DEBUG_BADGE_HUE_KEY);
		return {
			statsLayout: layout === "joined" ? "joined" : "separated",
			badgeHue:
				hue === "red" || hue === "green" || hue === "primary" ? hue : "green",
		};
	} catch {
		// Storage disabled: fall back to the shipped look.
		return { ...DEFAULTS };
	}
}

export function useDebugPrefs(): DebugPrefs & {
	setStatsLayout: (value: StatsLayout) => void;
	setBadgeHue: (value: PluginsBadgeHue) => void;
	reset: () => void;
} {
	const [prefs, setPrefs] = useState<DebugPrefs>(readPrefs);

	useEffect(() => {
		const sync = () => setPrefs(readPrefs());
		window.addEventListener(DEBUG_PREFS_EVENT, sync);
		return () => window.removeEventListener(DEBUG_PREFS_EVENT, sync);
	}, []);

	const write = useCallback((patch: Partial<DebugPrefs>) => {
		const next = { ...readPrefs(), ...patch };
		try {
			localStorage.setItem(DEBUG_STATS_LAYOUT_KEY, next.statsLayout);
			localStorage.setItem(DEBUG_BADGE_HUE_KEY, next.badgeHue);
		} catch {
			// Best-effort preference: still update this session.
		}
		setPrefs(next);
		window.dispatchEvent(new Event(DEBUG_PREFS_EVENT));
	}, []);

	return {
		...prefs,
		setStatsLayout: (statsLayout) => write({ statsLayout }),
		setBadgeHue: (badgeHue) => write({ badgeHue }),
		reset: () => write(DEFAULTS),
	};
}

export { DEFAULTS as DEBUG_PREFS_DEFAULTS };
