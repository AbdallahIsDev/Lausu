// Contribution-style heatmap data for the Analytics (Dashboard) page.
// Pure + React-agnostic (same contract as `./streaks`): takes the ONE
// history sample the hook already fetches and returns the
// `HeatmapColumn[]` shape `@bklit/heatmap-chart` renders, plus the
// aggregate numbers the card's accessible summary needs.
//
// Coverage honesty (this is the whole reason the grid is data-driven):
// the grid is built from the sample's OLDEST record to today, never from
// a fixed "last 12 months" window. The dashboard sample is the newest
// N rows, so every calendar day inside [oldest, today] is fully
// represented — a zero cell there means "no dictation that day", never
// "we don't know". A fixed-width grid would paint the months before the
// app was installed as empty, which reads as "you did nothing".
//
// Cell `count` is the RAW dictation count for that day, not a level:
// the chart maps count → level internally via
// `getHeatmapContributionLevel` (0 → 0, 1 → 1, 2 → 2, 3 → 3, ≥4 → 4) and
// the tooltip prints the same value as "N contributions". Pre-bucketing
// would make the tooltip lie about the count.

import { dateKey, localDateKey } from "@/lib/format";
import type { HistoryRecord } from "@/types/ipc";

/** One cell — a single calendar day. */
export interface DictationHeatmapBin {
	/** Row index inside the column (0 = Sunday, matching `HEATMAP_DAY_LABELS`). */
	bin: number;
	/** Dictations recorded that day (raw count). */
	count: number;
	date: Date;
}

/** One column — a single Sun–Sat week. */
export interface DictationHeatmapColumn {
	/** Column index (0 = oldest week shown). */
	bin: number;
	bins: DictationHeatmapBin[];
}

export interface DictationHeatmap {
	columns: DictationHeatmapColumn[];
	/** Dictations inside the covered window. */
	total: number;
	/** Days with at least one dictation inside the covered window. */
	activeDays: number;
	/** First day of the grid (local midnight, a Sunday). */
	startDate: Date;
	/** Last day of the grid (local midnight, today). */
	endDate: Date;
	/**
	 * True when the history reaches further back than {@link HEATMAP_MAX_WEEKS}
	 * allows — the left edge is a cap, not the beginning of the user's history.
	 */
	truncated: boolean;
}

/**
 * Hard cap on grid width. 53 whole weeks ≈ one year, the span a
 * contribution graph is conventionally read at; beyond that the cells
 * get too small to hover accurately at the card's width.
 */
export const HEATMAP_MAX_WEEKS = 53;

const MS_PER_WEEK = 7 * 24 * 60 * 60 * 1000;
const DATE_KEY_RE = /^\d{4}-\d{2}-\d{2}$/;

/** Local midnight of `d` (a copy — the argument is never mutated). */
function startOfDay(d: Date): Date {
	const s = new Date(d);
	s.setHours(0, 0, 0, 0);
	return s;
}

/** Local midnight of the Sunday starting `d`'s week. */
function startOfWeek(d: Date): Date {
	const s = startOfDay(d);
	s.setDate(s.getDate() - s.getDay());
	return s;
}

/** `YYYY-MM-DD` → local midnight Date. */
function fromDateKey(key: string): Date {
	const [y, m, d] = key.split("-").map(Number);
	return new Date(y ?? 0, (m ?? 1) - 1, d ?? 1);
}

/**
 * Build the heatmap grid from a history sample.
 *
 * `records` is the same DESC-ordered sample the rest of the dashboard
 * derives from, so the heatmap can never disagree with the cards or the
 * activity chart. `now` is injectable for tests.
 */
export function buildDictationHeatmap(
	records: HistoryRecord[],
	now: Date = new Date(),
): DictationHeatmap {
	// Per-day totals, bucketed on the LOCAL calendar day of each record's
	// UTC timestamp — identical to every other dashboard derivation.
	const counts = new Map<string, number>();
	let oldestKey: string | null = null;
	for (const r of records) {
		const key = dateKey(r.timestamp);
		// A malformed timestamp makes `dateKey` return the raw string;
		// ignoring it keeps it out of the grid anchor (see below).
		if (!DATE_KEY_RE.test(key)) continue;
		counts.set(key, (counts.get(key) ?? 0) + 1);
		if (oldestKey === null || key < oldestKey) oldestKey = key;
	}

	const endDate = startOfDay(now);
	const endWeekStart = startOfWeek(endDate);
	const startWeekStart =
		oldestKey === null ? endWeekStart : startOfWeek(fromDateKey(oldestKey));

	// Whole weeks between the two Sunday anchors. The difference is not an
	// exact multiple of 7 days across a DST boundary, so round the division
	// (the drift is at most ±1h).
	const weeksCovered =
		Math.round(
			(endWeekStart.getTime() - startWeekStart.getTime()) / MS_PER_WEEK,
		) + 1;
	const weeks = Math.max(1, Math.min(weeksCovered, HEATMAP_MAX_WEEKS));
	const truncated = weeksCovered > HEATMAP_MAX_WEEKS;

	const columns: DictationHeatmapColumn[] = [];
	let total = 0;
	let activeDays = 0;

	for (let column = 0; column < weeks; column++) {
		const bins: DictationHeatmapBin[] = [];
		for (let row = 0; row < 7; row++) {
			const date = new Date(endWeekStart);
			// Walk back whole weeks from the anchor, then forward by row, so
			// DST transitions stay on the correct calendar day (millisecond
			// arithmetic would drift by an hour and land on the wrong date).
			date.setDate(date.getDate() - (weeks - 1 - column) * 7 + row);
			date.setHours(0, 0, 0, 0);

			const count = counts.get(localDateKey(date)) ?? 0;
			total += count;
			if (count > 0) activeDays++;
			bins.push({ bin: row, count, date });
		}
		columns.push({ bin: column, bins });
	}

	const startDate = new Date(endWeekStart);
	startDate.setDate(startDate.getDate() - (weeks - 1) * 7);

	return { columns, total, activeDays, startDate, endDate, truncated };
}
