import { describe, expect, it } from "vitest";

import type { HistoryRecord } from "@/types/ipc";
import { buildDictationHeatmap, HEATMAP_MAX_WEEKS } from "../heatmap";

/** Fixed "now": Tue 6 Oct 2026, 15:00 local. */
const NOW = new Date(2026, 9, 6, 15, 0, 0);

/**
 * A record at the exact instant `date`.
 *
 * The DB stores UTC `"YYYY-MM-DD HH:MM:SS"` and `dateKey` maps it back to
 * the user's LOCAL calendar day, so fixtures must pin the instant, not a
 * wall-clock string: a midnight-adjacent fixture would assert differently
 * depending on the machine's UTC offset.
 */
function recordAt(date: Date, id: number): HistoryRecord {
	return {
		id,
		text: "",
		timestamp: date.toISOString().slice(0, 19).replace("T", " "),
		duration: 1,
		model: "",
		device: "",
		word_count: 1,
		char_count: 1,
		favorite: 0,
		language: "en",
	};
}

/** A record at LOCAL NOON on `date`'s calendar day (TZ-offset proof). */
function recordAtNoon(date: Date, id: number): HistoryRecord {
	return recordAt(
		new Date(date.getFullYear(), date.getMonth(), date.getDate(), 12, 0, 0),
		id,
	);
}

/** Local `yyyy-mm-dd` key for a Date, without importing the helper under test. */
function keyOf(date: Date): string {
	const y = date.getFullYear();
	const m = String(date.getMonth() + 1).padStart(2, "0");
	const d = String(date.getDate()).padStart(2, "0");
	return `${y}-${m}-${d}`;
}

/** The bin whose calendar day matches `key`, or undefined. */
function binFor(
	heatmap: ReturnType<typeof buildDictationHeatmap>,
	key: string,
) {
	for (const column of heatmap.columns) {
		for (const bin of column.bins) {
			if (keyOf(bin.date) === key) return bin;
		}
	}
	return undefined;
}

describe("buildDictationHeatmap", () => {
	it("lays out whole Sun–Sat columns whose row index IS the weekday", () => {
		const heatmap = buildDictationHeatmap(
			[recordAtNoon(new Date(2026, 9, 6), 1)],
			NOW,
		);

		// Fixed width — one record still yields a full year of columns.
		expect(heatmap.columns).toHaveLength(HEATMAP_MAX_WEEKS);

		// The chart derives row 0 = Sunday and its y-axis labels from
		// `HEATMAP_DAY_LABELS`; `bin` must equal `date.getDay()` for the
		// grid and its labels to line up.
		heatmap.columns.forEach((column, index) => {
			expect(column.bin).toBe(index);
			expect(column.bins).toHaveLength(7);
			column.bins.forEach((bin, row) => {
				expect(bin.bin).toBe(row);
				expect(bin.date.getDay()).toBe(row);
			});
		});

		// The LAST column is the current week and starts on its Sunday
		// (4 Oct 2026); the grid runs back 52 Sundays from there.
		const last = heatmap.columns[heatmap.columns.length - 1];
		expect(keyOf(last?.bins[0]?.date ?? new Date(0))).toBe("2026-10-04");
		expect(heatmap.columns[0]?.bins[0]?.date.getDay()).toBe(0);
		expect(keyOf(heatmap.startDate)).toBe("2025-10-05");
		expect(keyOf(heatmap.endDate)).toBe("2026-10-06");
	});

	it("counts the dictation on its own day and leaves the rest of the week empty", () => {
		const heatmap = buildDictationHeatmap(
			[recordAtNoon(new Date(2026, 9, 6), 1)],
			NOW,
		);

		expect(binFor(heatmap, "2026-10-06")?.count).toBe(1);
		expect(heatmap.total).toBe(1);
		expect(heatmap.activeDays).toBe(1);

		// Days later in the same week are inside the grid (GitHub-style
		// trailing blanks) and must read as a genuine zero, not be dropped.
		for (const key of ["2026-10-07", "2026-10-08", "2026-10-10"]) {
			expect(binFor(heatmap, key)?.count).toBe(0);
		}
	});

	it("sums several dictations on the same day", () => {
		const heatmap = buildDictationHeatmap(
			[
				recordAtNoon(new Date(2026, 9, 6), 1),
				recordAtNoon(new Date(2026, 9, 6), 2),
				recordAtNoon(new Date(2026, 9, 6), 3),
			],
			NOW,
		);

		expect(binFor(heatmap, "2026-10-06")?.count).toBe(3);
		expect(heatmap.total).toBe(3);
		expect(heatmap.activeDays).toBe(1);
	});

	it("buckets on the local calendar day, never shifted by the UTC offset", () => {
		// 00:30 and 23:30 on the same LOCAL day. Both are stored as UTC and
		// one of them is always on a different UTC day; the bug this guards
		// is bucketing a record by its UTC date, which would split them.
		const heatmap = buildDictationHeatmap(
			[
				recordAt(new Date(2026, 9, 6, 0, 30, 0), 1),
				recordAt(new Date(2026, 9, 6, 23, 30, 0), 2),
			],
			NOW,
		);

		expect(binFor(heatmap, "2026-10-06")?.count).toBe(2);
		expect(heatmap.activeDays).toBe(1);
	});

	it("renders the same full year whatever the history length", () => {
		const oneWeek = buildDictationHeatmap(
			[recordAtNoon(new Date(2026, 9, 6), 1)],
			NOW,
		);
		const elevenWeeks = buildDictationHeatmap(
			[
				recordAtNoon(new Date(2026, 7, 1), 1), // 1 Aug 2026
				recordAtNoon(new Date(2026, 9, 6), 2),
			],
			NOW,
		);
		const threeYears = buildDictationHeatmap(
			[recordAtNoon(new Date(2023, 4, 2), 1), recordAtNoon(NOW, 2)],
			NOW,
		);

		// A brand-new install and a long-time user get the SAME grid shape;
		// that is the whole point of a fixed-width grid.
		for (const heatmap of [oneWeek, elevenWeeks, threeYears]) {
			expect(heatmap.columns).toHaveLength(HEATMAP_MAX_WEEKS);
			expect(heatmap.columns.every((column) => column.bins.length === 7)).toBe(
				true,
			);
		}

		// Every day from the grid start to today has a cell, so a day
		// before the first record reads as a real zero instead of being
		// absent from the grid.
		expect(binFor(oneWeek, "2025-10-05")?.count).toBe(0);
		expect(binFor(oneWeek, "2026-08-01")?.count).toBe(0);
		expect(binFor(oneWeek, "2026-10-06")?.count).toBe(1);
		expect(oneWeek.total).toBe(1);
		expect(oneWeek.activeDays).toBe(1);

		// Truncation tracks the far edge only: history older than the
		// window is what the card has to disclose.
		expect(oneWeek.truncated).toBe(false);
		expect(elevenWeeks.truncated).toBe(false);
		expect(threeYears.truncated).toBe(true);
	});

	it("keeps every column seven consecutive local days", () => {
		const heatmap = buildDictationHeatmap(
			[recordAtNoon(new Date(2025, 0, 15), 1), recordAtNoon(NOW, 2)],
			NOW,
		);

		for (const column of heatmap.columns) {
			const times = column.bins.map((bin) => bin.date.getTime());
			for (let i = 1; i < times.length; i++) {
				const prev = times[i - 1] ?? 0;
				const curr = times[i] ?? 0;
				// 23h/25h across a DST transition, 24h otherwise — but never
				// a skipped or repeated calendar day.
				const hours = (curr - prev) / 3_600_000;
				expect(hours).toBeGreaterThanOrEqual(23);
				expect(hours).toBeLessThanOrEqual(25);
			}
		}
	});

	it("caps the grid at one year and reports the truncation", () => {
		const heatmap = buildDictationHeatmap(
			[recordAtNoon(new Date(2023, 4, 2), 1), recordAtNoon(NOW, 2)],
			NOW,
		);

		expect(heatmap.columns).toHaveLength(HEATMAP_MAX_WEEKS);
		expect(heatmap.truncated).toBe(true);

		// The last column is the CURRENT week: its right edge is the coming
		// Saturday (trailing blanks), and today sits at row `getDay()`.
		const lastColumn = heatmap.columns[heatmap.columns.length - 1];
		expect(keyOf(lastColumn?.bins[NOW.getDay()]?.date ?? new Date(0))).toBe(
			keyOf(NOW),
		);
		expect(heatmap.columns[0]?.bins[0]?.date.getDay()).toBe(0);
	});

	it("still renders a full year when there is no history at all", () => {
		const heatmap = buildDictationHeatmap([], NOW);

		expect(heatmap.columns).toHaveLength(HEATMAP_MAX_WEEKS);
		expect(heatmap.total).toBe(0);
		expect(heatmap.activeDays).toBe(0);
		expect(heatmap.truncated).toBe(false);
		expect(
			heatmap.columns.every((column) =>
				column.bins.every((bin) => bin.count === 0),
			),
		).toBe(true);
	});

	it("ignores unparseable timestamps instead of poisoning the grid", () => {
		const broken = { ...recordAtNoon(NOW, 1), timestamp: "not-a-timestamp" };
		const heatmap = buildDictationHeatmap(
			[broken, recordAtNoon(new Date(2026, 9, 6), 2)],
			NOW,
		);

		// The broken row is counted nowhere, and being unparseable it also
		// cannot drag the oldest-record edge and fake a truncation.
		expect(heatmap.columns).toHaveLength(HEATMAP_MAX_WEEKS);
		expect(heatmap.total).toBe(1);
		expect(heatmap.truncated).toBe(false);
		expect(binFor(heatmap, "2026-10-06")?.count).toBe(1);
	});

	it("covers the same span the totals are computed from", () => {
		const heatmap = buildDictationHeatmap(
			[
				recordAtNoon(new Date(2026, 8, 30), 1),
				recordAtNoon(new Date(2026, 9, 1), 2),
				recordAtNoon(new Date(2026, 9, 1), 3),
			],
			NOW,
		);

		// `total` must equal the sum of the rendered cells — the card's
		// accessible summary reads from it.
		const summed = heatmap.columns
			.flatMap((column) => column.bins)
			.reduce((acc, bin) => acc + bin.count, 0);
		expect(summed).toBe(heatmap.total);
		expect(heatmap.total).toBe(3);
		expect(heatmap.activeDays).toBe(2);
	});
});
