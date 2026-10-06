/**
 * buildHeatmapMonthTicks — the heatmap x-axis month labels.
 *
 * The vendored axis formatted its own labels with an English
 * `Intl.DateTimeFormat` and had no way to override them. A full-year grid
 * renders ~13 of these, which is the loudest string on the Analytics card,
 * so the override is the contract pinned here: one tick per calendar month,
 * anchored to the first column of that month, with the caller's labels
 * indexed January-first (`Date.getMonth()`).
 */

import { describe, expect, it } from "vitest";
import type { HeatmapColumn } from "../heatmap-context";
import { buildHeatmapMonthTicks, HEATMAP_MONTH_LABELS } from "../heatmap-utils";

/** `weeks` Sun–Sat columns starting at local midnight on `startSunday`. */
function columnsFrom(startSunday: Date, weeks: number): HeatmapColumn[] {
	const columns: HeatmapColumn[] = [];

	for (let column = 0; column < weeks; column++) {
		const bins = Array.from({ length: 7 }, (_, row) => {
			const date = new Date(startSunday);
			date.setDate(date.getDate() + column * 7 + row);
			date.setHours(0, 0, 0, 0);
			return { bin: row, count: 0, date };
		});
		columns.push({ bin: column, bins });
	}

	return columns;
}

/** First column of a 53-week grid ending 4 Oct 2026. */
const START = new Date(2025, 9, 5);

/** The 13 months a rolling year spans, in order. */
const EXPECTED_MONTHS = [
	"Oct",
	"Nov",
	"Dec",
	"Jan",
	"Feb",
	"Mar",
	"Apr",
	"May",
	"Jun",
	"Jul",
	"Aug",
	"Sep",
	"Oct",
];

describe("buildHeatmapMonthTicks", () => {
	it("ships twelve January-first English labels", () => {
		expect(HEATMAP_MONTH_LABELS).toHaveLength(12);
		expect(HEATMAP_MONTH_LABELS[0]).toBe("Jan");
		expect(HEATMAP_MONTH_LABELS[11]).toBe("Dec");
	});

	it("emits one tick per month, in order, anchored to that month's first column", () => {
		const columns = columnsFrom(START, 53);
		const ticks = buildHeatmapMonthTicks(columns);

		// A rolling year crosses 13 month labels: Oct 2025 → Oct 2026.
		expect(ticks.map((tick) => tick.label)).toEqual(EXPECTED_MONTHS);

		// Anchors strictly increase, and each is the FIRST column whose
		// month differs from the previous column's — a month must not
		// produce a second tick when a later column repeats it.
		for (let i = 1; i < ticks.length; i++) {
			const previous = ticks[i - 1]?.columnIndex ?? -1;
			expect(ticks[i]?.columnIndex ?? -1).toBeGreaterThan(previous);
		}

		// The first tick belongs to column 0 (the grid's own first column).
		expect(ticks[0]?.columnIndex).toBe(0);

		// Each anchor really is the first column of its month: the column
		// before it still belongs to the previous month.
		const secondTick = ticks[1];
		expect(secondTick?.columnIndex).toBe(3); // 26 Oct – 1 Nov 2025
		expect(columns[secondTick?.columnIndex ?? 0]?.bins[6]?.date.getDate()).toBe(
			1,
		);
		expect(
			columns[(secondTick?.columnIndex ?? 0) - 1]?.bins[6]?.date.getMonth(),
		).toBe(9);
	});

	it("keys each tick by year and month, so a year boundary is not collapsed", () => {
		const ticks = buildHeatmapMonthTicks(columnsFrom(START, 53));
		const keys = ticks.map((tick) => tick.key);

		expect(new Set(keys).size).toBe(keys.length);
		expect(keys[0]).toBe("2025-9"); // Oct 2025
		expect(keys[3]).toBe("2026-0"); // Jan 2026 — same month index, new year
		expect(keys[keys.length - 1]).toBe("2026-9");
	});

	it("uses the caller's labels, indexed January-first", () => {
		const custom = Array.from({ length: 12 }, (_, i) => `M${i + 1}`);
		const ticks = buildHeatmapMonthTicks(columnsFrom(START, 53), custom);

		expect(ticks[0]?.label).toBe("M10"); // October → month index 9
		expect(ticks[1]?.label).toBe("M11");
		expect(ticks[2]?.label).toBe("M12");
		expect(ticks[3]?.label).toBe("M1"); // January → month index 0
		expect(ticks[ticks.length - 1]?.label).toBe("M10");
	});

	it("falls back per entry, so a short array cannot blank a label", () => {
		const ticks = buildHeatmapMonthTicks(columnsFrom(START, 53), ["X"]);

		// October is index 9 — past the end of the array → English default.
		expect(ticks[0]?.label).toBe("Oct");
		// January is index 0 → the caller's value.
		expect(ticks[3]?.label).toBe("X");
	});

	it("returns no ticks for an empty grid", () => {
		expect(buildHeatmapMonthTicks([])).toEqual([]);
	});
});
