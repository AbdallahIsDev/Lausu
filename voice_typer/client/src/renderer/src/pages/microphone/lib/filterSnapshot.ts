// Filter-value snapshots for preset dirty tracking + save.
// Single source: the registry-derived key list; one snapshot shape
// shared by the selector (baseline) and the page (save payload).

import { audioFilterConfigKeys } from "@/components/audio/audioFilterRowDescriptors";
import type { LausuConfig } from "@/types/config";

export type FilterSnapshot = Record<
	string,
	boolean | number | string | null | undefined
>;

/** Pick the 24 filter values out of a config (null-safe). */
export function snapshotFilterValues(
	config: LausuConfig | null | undefined,
): FilterSnapshot {
	const out: FilterSnapshot = {};
	if (!config) return out;
	for (const key of audioFilterConfigKeys()) {
		out[key] = (config as unknown as Record<string, unknown>)[key] as
			| boolean
			| number
			| string
			| null
			| undefined;
	}
	return out;
}

/** True when two snapshots hold identical values. */
export function filterSnapshotsEqual(
	a: FilterSnapshot,
	b: FilterSnapshot,
): boolean {
	// Compare over the BASELINE's keys: saved snapshots may legitimately
	// hold a subset (older saves, hand-built entries), and keys outside
	// the baseline can never make the selection dirty.
	for (const key of Object.keys(a)) {
		if (a[key] !== b[key]) return false;
	}
	return true;
}
