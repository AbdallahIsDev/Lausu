// One-way "you have seen the Plugins surface" marker for the sidebar's New
// badge. The badge is a pointer, not a setting: once the user has been there it
// never comes back (owner decision 2026-11-18), so it lives in localStorage next
// to the other UI-only preferences rather than in config.json.

import { useEffect, useState } from "react";

/** localStorage key holding the marker. */
export const PLUGINS_BADGE_SEEN_KEY = "lausu-ui-plugins-badge-seen";

function readSeen(): boolean {
	try {
		return localStorage.getItem(PLUGINS_BADGE_SEEN_KEY) === "1";
	} catch {
		// Private mode / storage disabled: treat "unknown" as unseen so the
		// badge still shows, it simply cannot be remembered.
		return false;
	}
}

function writeSeen(): void {
	try {
		localStorage.setItem(PLUGINS_BADGE_SEEN_KEY, "1");
	} catch {
		// Best effort marker only.
	}
}

/**
 * Whether the sidebar's Plugins New badge is still due, and dismisses it for
 * good the first time the Plugins page becomes the current page.
 */
export function usePluginsNewBadge(currentPage: string): boolean {
	const [visible, setVisible] = useState(() => !readSeen());

	useEffect(() => {
		if (!visible || currentPage !== "plugins") return;
		writeSeen();
		setVisible(false);
	}, [currentPage, visible]);

	return visible;
}
