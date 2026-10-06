/**
 * getHeatmapDayLabels — the heatmap y-axis row labels.
 *
 * The vendored default is an English Sunday-first array. The Analytics
 * card passes locale-derived labels instead (C-I18N-1), so the rotation
 * has to apply to whatever array it is handed, not only to the built-in
 * one — that override is the contract pinned here.
 */

import { describe, expect, it } from "vitest";
import { getHeatmapDayLabels, HEATMAP_DAY_LABELS } from "../heatmap-utils";

const CUSTOM = ["D0", "D1", "D2", "D3", "D4", "D5", "D6"];

describe("getHeatmapDayLabels", () => {
	it("returns the English defaults Sunday-first", () => {
		expect(getHeatmapDayLabels()).toEqual(HEATMAP_DAY_LABELS);
		expect(getHeatmapDayLabels(0)).toEqual(HEATMAP_DAY_LABELS);
	});

	it("rotates the defaults so row 0 is the requested week start", () => {
		expect(getHeatmapDayLabels(1)).toEqual([
			"Mon",
			"Tue",
			"Wed",
			"Thu",
			"Fri",
			"Sat",
			"Sun",
		]);
	});

	it("rotates a custom label set the same way", () => {
		expect(getHeatmapDayLabels(0, CUSTOM)).toEqual(CUSTOM);
		expect(getHeatmapDayLabels(3, CUSTOM)).toEqual([
			"D3",
			"D4",
			"D5",
			"D6",
			"D0",
			"D1",
			"D2",
		]);
	});
});
