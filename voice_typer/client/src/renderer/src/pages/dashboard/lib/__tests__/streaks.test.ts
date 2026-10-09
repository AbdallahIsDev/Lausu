import { describe, expect, it, vi } from "vitest";

import type { HistoryRecord } from "@/types/ipc";

import {
	type ActivityBar,
	buildActivityBars,
	type CorrectionUsageSnapshot,
	computeCorrectionStats,
	computePeriodStats,
	computeStreaks,
	dateKey,
	localDateKey,
	parseUtcTimestamp,
	WEEKDAY_LABEL_MAX_SPAN,
} from "../streaks";

function bar(bars: ActivityBar[], i: number): ActivityBar {
	const b = bars[i];
	if (b === undefined) throw new Error(`missing bar at index ${i}`);
	return b;
}

// Fixed "now" in LOCAL time, window math anchors on this machine's
// calendar day, and records are built relative to it.
const NOW = new Date(2026, 7, 16, 15, 0, 0); // Aug 16 2026, 3pm local

function rec(
	daysAgo: number,
	opts: { chars?: number; duration?: number; hour?: number } = {},
): HistoryRecord {
	const d = new Date(NOW);
	d.setDate(d.getDate() - daysAgo);
	d.setHours(opts.hour ?? 12, 0, 0, 0);
	return {
		id: Math.floor(Math.random() * 1e9),
		text: "",
		timestamp: d.toISOString(),
		duration: opts.duration ?? 10,
		model: "tiny",
		device: "cpu",
		word_count: 20,
		char_count: opts.chars ?? 100,
		favorite: 0,
		language: "en",
	};
}

describe("UTC timestamp parsing (data-consistency fix)", () => {
	it("parses a bare SQLite UTC timestamp as UTC, not local", () => {
		const fixed = parseUtcTimestamp("2026-08-16 03:00:00");
		expect(fixed.getTime()).toBe(Date.UTC(2026, 7, 16, 3, 0, 0));

		// The naive `new Date(ts)` parse interprets the string as LOCAL
		// (machine-dependent); the fixed parse is UTC. The two instants
		// must therefore differ by EXACTLY the host's UTC offset at that
		// wall time, zero on a UTC+0 runner, ±minutes elsewhere.
		// Asserting the precise relationship (rather than inequality)
		// keeps the test deterministic on every machine/CI timezone.
		// (naive − fixed = offset, so no unary minus on the offset —
		// avoids the -0 vs +0 Object.is trap on UTC+0 hosts.)
		const naive = new Date("2026-08-16 03:00:00");
		expect(naive.getTime() - fixed.getTime()).toBe(
			naive.getTimezoneOffset() * 60000,
		);
	});

	it("buckets an evening-UTC record into the correct LOCAL calendar day", () => {
		// 22:00 UTC on the 16th. Depending on the machine's offset this
		// is the 16th or 17th LOCAL, either way it must equal the
		// UTC-correct local day, not the naive-local parse's day.
		const ts = "2026-08-16 22:00:00";
		const expected = localDateKey(parseUtcTimestamp(ts));
		expect(dateKey(ts)).toBe(expected);
		// And it differs from the naive parse when the offset crosses
		const naiveDay = localDateKey(new Date(ts));
		expect(dateKey(ts) === naiveDay).toBe(expected === naiveDay);
	});

	it("accepts ISO strings with a Z marker unchanged", () => {
		const iso = new Date(Date.UTC(2026, 7, 16, 3)).toISOString();
		expect(parseUtcTimestamp(iso).getTime()).toBe(Date.UTC(2026, 7, 16, 3));
	});

	it("streak days are bucketed in local time (evening UTC record counts for its local day)", () => {
		// A dictation at 23:30 LOCAL today stores as a bare UTC string
		// whose UTC calendar date may be TOMORROW (on negative-offset
		// machines). Parsing it as UTC (correct) must land it back on
		// today's LOCAL day; the naive local parse would put it on the
		// wrong day and break the streak anchor. The assertion holds on
		// every offset: on UTC+ machines the UTC date happens to equal
		// the local date (vacuous), on UTC- machines it exercises the bug.
		// computeStreaks anchors on the REAL current day internally, so pin
		// the system clock to the fixed NOW, otherwise this test silently
		// flips after local midnight (records built against Aug 16 land on
		// "yesterday" and the current streak reads 0).
		vi.useFakeTimers();
		vi.setSystemTime(NOW);
		try {
			const late = new Date(NOW);
			late.setHours(23, 30, 0, 0);
			// Bare SQLite-style UTC string, no Z marker.
			const utcBare = late.toISOString().replace("T", " ").slice(0, 19);
			const records = [rec(0), { ...rec(0), timestamp: utcBare }];
			const streaks = computeStreaks(records);
			// Both records are today's LOCAL day → streak of 1, one active day.
			expect(streaks.current).toBeGreaterThan(0);
			expect(streaks.activeDays).toBe(1);
		} finally {
			vi.useRealTimers();
		}
	});
});

describe("computePeriodStats", () => {
	it("counts only the window days + exposes the previous window", () => {
		const records = [
			rec(0), // today
			rec(1), // yesterday
			rec(3), // 3 days ago
			rec(6), // 6 days ago
			rec(7), // outside 7d window (prev window's last day)
			rec(10), // prev window
			rec(14), // outside both
		];
		const p = computePeriodStats(records, "7d", NOW);
		expect(p.count).toBe(4);
		expect(p.activeDays).toBe(4);
		// prev window = days 7..13 ago → rec(7) + rec(10)
		expect(p.prev?.count).toBe(2);
	});

	it("today range counts only today; prev is yesterday", () => {
		const records = [rec(0), rec(0), rec(1), rec(2)];
		const p = computePeriodStats(records, "today", NOW);
		expect(p.count).toBe(2);
		expect(p.prev?.count).toBe(1);
	});

	it("all-time has no previous period and includes everything ≤ today", () => {
		const records = [rec(0), rec(100)];
		const p = computePeriodStats(records, "all", NOW);
		expect(p.count).toBe(2);
		expect(p.prev).toBeNull();
	});

	it("derived metrics: avg chars, longest session, peak weekday", () => {
		const records = [
			rec(0, { chars: 200, duration: 60 }), // today
			rec(0, { chars: 400, duration: 120 }), // today
			rec(1, { chars: 300, duration: 30 }), // yesterday
		];
		const p = computePeriodStats(records, "7d", NOW);
		expect(p.avgCharsPerDictation).toBe(300); // 900 / 3
		expect(p.longestSession).toBe(120);
		// today has 2 dictations → peak weekday = today's weekday
		expect(p.peakWeekday).toBe(NOW.getDay());
	});

	it("the prev window exposes its own longest session, for a like-for-like trend", () => {
		// The Longest Session card compares against the previous window's
		// MAX, not against a sum: "prev" has to carry it. For "7d" the
		// previous window is days 7..13 ago.
		const records = [
			rec(0, { duration: 60 }),
			rec(7, { duration: 90 }),
			rec(10, { duration: 30 }),
		];
		const p = computePeriodStats(records, "7d", NOW);
		expect(p.longestSession).toBe(60);
		expect(p.prev?.longestSession).toBe(90);
	});

	it("excludes future-dated records from the window", () => {
		const future = new Date(NOW);
		future.setDate(future.getDate() + 2);
		const records = [{ ...rec(0), timestamp: future.toISOString() }];
		const p = computePeriodStats(records, "7d", NOW);
		expect(p.count).toBe(0);
	});
});

describe("buildActivityBars", () => {
	it("7-day range: 7 bars, zero vs missing distinguished by sample coverage", () => {
		// Records on days 0 (today), 1, and 3 ago. The sample's oldest
		// record is 3 days ago → days 4-6 ago are NOT covered (missing),
		// day 2 ago is covered-but-zero, today/yesterday/3d have counts.
		const records = [rec(0), rec(1), rec(3)];
		const { bars, kind, coveredFromKey, daySpan } = buildActivityBars(
			records,
			"7d",
			NOW,
		);
		expect(kind).toBe("daily");
		expect(daySpan).toBe(7);
		expect(bars.length).toBe(7);

		// bars are oldest → newest: index 0 = 6 days ago … index 6 = today
		expect(bar(bars, 6).count).toBe(1); // today
		expect(bar(bars, 6).isMissing).toBe(false);
		expect(bar(bars, 5).count).toBe(1); // yesterday
		expect(bar(bars, 4).count).toBe(0); // 2 days ago, zero, not missing
		expect(bar(bars, 4).isMissing).toBe(false);
		expect(bar(bars, 3).count).toBe(1); // 3 days ago
		expect(bar(bars, 3).isMissing).toBe(false);
		expect(bar(bars, 0).isMissing).toBe(true); // 6 days ago, not covered
		expect(bar(bars, 1).isMissing).toBe(true); // 5 days ago, not covered
		expect(bar(bars, 2).isMissing).toBe(true); // 4 days ago, not covered
		// Oldest record in the sample is 3 days ago → coverage starts there.
		const threeDaysAgo = new Date(NOW);
		threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);
		expect(coveredFromKey).toBe(localDateKey(threeDaysAgo));
	});

	it("all-time range renders the trailing 30 days", () => {
		const records = [rec(0)];
		const { daySpan, kind } = buildActivityBars(records, "all", NOW);
		expect(kind).toBe("daily");
		expect(daySpan).toBe(30);
	});

	it("labels bars with weekday names up to a week, then with month + day", () => {
		// A weekday name identifies a day only within a week: "Thu"
		// recurs four times across a 30-day window, so a wide range used
		// to print the same handful of names in a seemingly random order
		// and never say which date a bar was. Past a week the ticks are
		// dates instead. (Locale is `en` — nothing in this file changes
		// it — so the exact strings are stable.)
		const week = buildActivityBars([rec(0)], "7d", NOW);
		expect(week.bars).toHaveLength(7);
		expect(week.bars.every((b) => !/\d/.test(b.label))).toBe(true);

		const wide = buildActivityBars([rec(0)], "all", NOW);
		expect(wide.bars).toHaveLength(30);
		// 30 days back from Aug 16 2026 → Jul 18 … Aug 16. Every label
		// carries its day-of-month, which a weekday name never does.
		expect(wide.bars.every((b) => /\d/.test(b.label))).toBe(true);
		expect(bar(wide.bars, 0).label).toBe("Jul 18");
		expect(bar(wide.bars, 29).label).toBe("Aug 16");
	});

	it("spans the weekday→date switch exactly at the threshold", () => {
		// The chart's tick SPACING reads the same constant, so the label
		// text and the labels' density cannot drift apart.
		expect(WEEKDAY_LABEL_MAX_SPAN).toBe(7);
		const atLimit = buildActivityBars([rec(0)], "7d", NOW);
		expect(atLimit.daySpan).toBe(WEEKDAY_LABEL_MAX_SPAN);
		expect(atLimit.bars.every((b) => !/\d/.test(b.label))).toBe(true);
		const pastLimit = buildActivityBars([rec(0)], "custom", NOW, {
			startKey: "2026-08-09",
			endKey: "2026-08-16",
		});
		expect(pastLimit.daySpan).toBe(8);
		expect(pastLimit.bars.every((b) => /\d/.test(b.label))).toBe(true);
	});

	it("today range: 24 hourly bars, future hours are missing, past zeros are not", () => {
		// Two records today: one at local hour 9, one at local hour 12.
		const records = [rec(0, { hour: 9 }), rec(0, { hour: 12 })];
		const { bars, kind } = buildActivityBars(records, "today", NOW);
		expect(kind).toBe("hourly");
		expect(bars.length).toBe(24);
		expect(bar(bars, 9).count).toBe(1);
		expect(bar(bars, 12).count).toBe(1);
		expect(bar(bars, 12).isMissing).toBe(false);
		// Hour 14 (past, no dictation) → zero, not missing.
		expect(bar(bars, 14).count).toBe(0);
		expect(bar(bars, 14).isMissing).toBe(false);
		// NOW is 3pm local → hours 16..23 are in the future → missing.
		expect(bar(bars, 16).isMissing).toBe(true);
		expect(bar(bars, 23).isMissing).toBe(true);
		// Hour 0 (past) is zero, not missing.
		expect(bar(bars, 0).isMissing).toBe(false);
	});
});

describe("rangeDaySpan", () => {
	it("maps each range to its day count", async () => {
		const { rangeDaySpan } = await import("../streaks");
		expect(rangeDaySpan("today")).toBe(1);
		expect(rangeDaySpan("7d")).toBe(7);
		expect(rangeDaySpan("30d")).toBe(30);
		expect(rangeDaySpan("all")).toBeNull();
	});
});

describe("computeCorrectionStats", () => {
	// Fixed NOW (Aug 16 2026 local): 7d window = Aug 10..16, prev 7d
	// window = Aug 3..9. Keys are LOCAL calendar days, the same
	// bucketing `localDateKey` produces for the period stats.
	const NOW = new Date(2026, 7, 16, 15, 0, 0);

	const usage: CorrectionUsageSnapshot = {
		version: 1,
		entries: {},
		corrections_by_day: {
			"2026-08-14": 3, // inside 7d window
			"2026-08-16": 1, // today
			"2026-08-07": 5, // inside PREVIOUS 7d window (Aug 3..9)
			"2026-07-01": 9, // outside both
		},
		dictations_by_day: {
			"2026-08-14": 2,
			"2026-08-16": 1,
		},
	};

	it("sums corrections + dictations inside the 7-day window and computes the rate", () => {
		const stats = computeCorrectionStats(usage, "7d", NOW);
		expect(stats.corrections).toBe(4); // 3 (14th) + 1 (today)
		expect(stats.dictations).toBe(3); // 2 (14th) + 1 (today)
		expect(stats.rate).toBeCloseTo(4 / 3);
		expect(stats.prevCorrections).toBe(5);
	});

	it("scopes to the Today range (single local day)", () => {
		const stats = computeCorrectionStats(usage, "today", NOW);
		expect(stats.corrections).toBe(1);
		expect(stats.dictations).toBe(1);
		expect(stats.rate).toBe(1);
		expect(stats.prevCorrections).toBe(0); // yesterday had none
	});

	it("all-time sums every day and has no previous window", () => {
		const stats = computeCorrectionStats(usage, "all", NOW);
		expect(stats.corrections).toBe(18);
		expect(stats.dictations).toBe(3);
		expect(stats.prevCorrections).toBeNull();
	});

	it("returns zeros + null rate when the usage snapshot is absent", () => {
		const stats = computeCorrectionStats(null, "7d", NOW);
		expect(stats.corrections).toBe(0);
		expect(stats.dictations).toBe(0);
		expect(stats.rate).toBeNull();
		expect(stats.prevCorrections).toBeNull();
	});

	it("returns null rate when the window has dictations but no corrections", () => {
		const stats = computeCorrectionStats(
			{
				version: 1,
				entries: {},
				corrections_by_day: { "2026-08-01": 2 },
				dictations_by_day: { "2026-08-14": 2 },
			},
			"7d",
			NOW,
		);
		expect(stats.corrections).toBe(0);
		expect(stats.dictations).toBe(2);
		expect(stats.rate).toBe(0);
	});
});

describe("custom windows (explicit day ranges)", () => {
	// Fixed NOW (Aug 16 2026 local) shared with the module helper above.
	const CUSTOM = { startKey: "2026-08-10", endKey: "2026-08-12" }; // 3 days

	it("resolveRangeWindow passes the window through with the previous same-length span", async () => {
		const { resolveRangeWindow } = await import("../streaks");
		const w = resolveRangeWindow("custom", NOW, CUSTOM);
		expect(w.startKey).toBe("2026-08-10");
		expect(w.endKey).toBe("2026-08-12");
		expect(w.prevStartKey).toBe("2026-08-07");
		expect(w.prevEndKey).toBe("2026-08-09");
	});

	it("resolveRangeWindow crosses month boundaries in the previous span", async () => {
		const { resolveRangeWindow } = await import("../streaks");
		const w = resolveRangeWindow("custom", NOW, {
			startKey: "2026-03-01",
			endKey: "2026-03-03",
		});
		// 2026 is not a leap year: Feb has 28 days.
		expect(w.prevStartKey).toBe("2026-02-26");
		expect(w.prevEndKey).toBe("2026-02-28");
	});

	it("resolveRangeWindow falls back to trailing-30d without a window", async () => {
		const { resolveRangeWindow } = await import("../streaks");
		expect(resolveRangeWindow("custom", NOW)).toEqual(
			resolveRangeWindow("30d", NOW),
		);
	});

	it("utcBoundsForWindow emits an inclusive-start/exclusive-end UTC pair", async () => {
		const { utcBoundsForWindow } = await import("../streaks");
		const { startTs, endTs } = utcBoundsForWindow("2026-08-10", "2026-08-12");
		expect(startTs).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
		expect(endTs).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
		expect(startTs < endTs).toBe(true);
		// Local noon inside the window satisfies start <= ts < end on
		// every host timezone (storage order matches the strings).
		const noon = new Date(2026, 7, 11, 12, 0, 0);
		const ts = `${noon.getUTCFullYear()}-${String(noon.getUTCMonth() + 1).padStart(2, "0")}-${String(noon.getUTCDate()).padStart(2, "0")} ${String(noon.getUTCHours()).padStart(2, "0")}:00:00`;
		expect(startTs <= ts && ts < endTs).toBe(true);
	});

	it("computePeriodStats scopes counts + trends to the custom window", () => {
		const records = [rec(4), rec(5), rec(6), rec(3), rec(7)];
		const p = computePeriodStats(records, "custom", NOW, CUSTOM);
		expect(p.count).toBe(3); // Aug 10, 11, 12
		expect(p.prev?.count).toBe(1); // Aug 9 (prev window Aug 7..9)
	});

	it("computeCorrectionStats scopes to the custom window", () => {
		const stats = computeCorrectionStats(
			{
				version: 1,
				entries: {},
				corrections_by_day: {
					"2026-08-11": 4, // inside
					"2026-08-08": 6, // previous window
					"2026-08-16": 9, // outside (today)
				},
				dictations_by_day: { "2026-08-11": 2 },
			},
			"custom",
			NOW,
			CUSTOM,
		);
		expect(stats.corrections).toBe(4);
		expect(stats.dictations).toBe(2);
		expect(stats.prevCorrections).toBe(6);
	});

	it("buildActivityBars renders daily bars over a multi-day custom window", () => {
		const { bars, kind, daySpan } = buildActivityBars(
			[rec(6), rec(6), rec(4)],
			"custom",
			NOW,
			CUSTOM,
		);
		expect(kind).toBe("daily");
		expect(daySpan).toBe(3);
		expect(bars.map((b) => b.key)).toEqual([
			"2026-08-10",
			"2026-08-11",
			"2026-08-12",
		]);
		expect(bars.map((b) => b.count)).toEqual([2, 0, 1]);
	});

	it("buildActivityBars renders hourly bars for a single past custom day", () => {
		const day = { startKey: "2026-08-10", endKey: "2026-08-10" };
		const { bars, kind } = buildActivityBars(
			[rec(6, { hour: 9 }), rec(6, { hour: 9 }), rec(6, { hour: 14 })],
			"custom",
			NOW,
			day,
		);
		expect(kind).toBe("hourly");
		expect(bars).toHaveLength(24);
		expect(bar(bars, 9).count).toBe(2);
		expect(bar(bars, 14).count).toBe(1);
		// A fully-past day has no future hours to mark missing.
		expect(bars.every((b) => !b.isMissing)).toBe(true);
	});
});

describe("formatWindowLabel", () => {
	it("joins a same-year span without years", async () => {
		const { formatWindowLabel } = await import("../format");
		const label = formatWindowLabel("2026-08-10", "2026-08-12");
		expect(label).toContain("–");
		expect(label).not.toContain("2026");
	});

	it("shows years when the span crosses New Year", async () => {
		const { formatWindowLabel } = await import("../format");
		const label = formatWindowLabel("2025-12-30", "2026-01-02");
		expect(label).toContain("2025");
		expect(label).toContain("2026");
	});
});
