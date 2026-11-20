// main page file stays a thin composition root. Pure values, no
// behaviour, no React, no IPC.

/**
 * localStorage key for the recent-activity cache (last 5 transcriptions).
 * Used by `loadCachedRecent` / `persistRecent` in `./cache.ts`.
 */
export const RECENT_CACHE_KEY = "vt_home_recent_cache";

export const STATS_CACHE_KEY = "vt_home_stats_cache";

export const FIRST_RECORD_CELEBRATED_KEY = "vt_first_recording_celebrated";

export const FORCE_CANCEL_DELAY_MS = 5_000;

// Status colours live in the shared module (the sidebar dot renders the same
// palette); re-exported so Home keeps one import surface for its constants.
export { DEFAULT_STATUS_COLOR, STATUS_COLORS } from "@/lib/dictationStatus";
