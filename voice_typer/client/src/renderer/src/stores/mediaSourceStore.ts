// The Media page's link/file field, held outside the component: the value has
// to survive navigation, a page refresh and an app restart, and only the user
// may empty it (the in-field X, or a successful submit).

import { create } from "zustand";

/** Storage key. One writer (this store), so no other surface can clobber it. */
export const MEDIA_SOURCE_STORAGE_KEY = "lausu.media.source";

/** Read the persisted value; disabled storage yields `""`, never a throw. */
export function readStoredMediaSource(): string {
	try {
		return window.localStorage.getItem(MEDIA_SOURCE_STORAGE_KEY) ?? "";
	} catch {
		return "";
	}
}

function writeStoredMediaSource(value: string): void {
	try {
		if (value) window.localStorage.setItem(MEDIA_SOURCE_STORAGE_KEY, value);
		else window.localStorage.removeItem(MEDIA_SOURCE_STORAGE_KEY);
	} catch {
		// Best-effort persistence: a read-only or full storage keeps the page
		// usable, it just forgets the value on the next launch.
	}
}

interface MediaSourceState {
	source: string;
	setSource: (value: string) => void;
	clear: () => void;
}

export const useMediaSourceStore = create<MediaSourceState>((set) => ({
	// Read once at module load: this store is imported by the Media page only,
	// so "first use" is the page being reached, and a remount must not reset
	// the field to what was typed in a previous session.
	source: readStoredMediaSource(),
	setSource: (value) => {
		writeStoredMediaSource(value);
		set({ source: value });
	},
	clear: () => {
		writeStoredMediaSource("");
		set({ source: "" });
	},
}));
