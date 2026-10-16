import { describe, expect, it } from "vitest";

import { makeConfig } from "@/__tests__/helpers/fixtures";
import {
	audioFilterConfigKeys,
	filterFactoryDefaults,
	MIC_ADVANCED_ROW_KEYS,
} from "@/components/audio/audioFilterRowDescriptors";
import { filterSnapshotsEqual, snapshotFilterValues } from "../filterSnapshot";

describe("filterSnapshot", () => {
	it("compares over baseline keys only (partial saved snapshots)", () => {
		const baseline = { noise_filter_gate: false };
		expect(
			filterSnapshotsEqual(baseline, { ...baseline, noise_filter_eq: true }),
		).toBe(true);
		expect(
			filterSnapshotsEqual(baseline, { ...baseline, noise_filter_gate: true }),
		).toBe(false);
	});

	it("snapshots every registry key", () => {
		const snap = snapshotFilterValues(makeConfig({}));
		for (const key of audioFilterConfigKeys()) {
			expect(key in snap).toBe(true);
		}
	});
});

describe("mic advanced surface", () => {
	it("simplified set is a subset of the registry", () => {
		const all = new Set(audioFilterConfigKeys());
		for (const key of MIC_ADVANCED_ROW_KEYS) {
			expect(all.has(key)).toBe(true);
		}
		expect(MIC_ADVANCED_ROW_KEYS.length).toBeLessThan(all.size);
	});

	it("factory defaults cover every registry key", () => {
		const factory = filterFactoryDefaults();
		for (const key of audioFilterConfigKeys()) {
			expect(key in factory).toBe(true);
		}
	});
});
