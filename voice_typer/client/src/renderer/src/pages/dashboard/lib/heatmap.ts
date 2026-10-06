// Contribution-style heatmap data for the Analytics (Dashboard) page.
// Pure + React-agnostic (same contract as `./streaks`): takes the ONE
// history sample the hook already fetches and returns the
// `HeatmapColumn[]` shape `@bklit/heatmap-chart` renders, plus the
// aggregate numbers the card's accessible summary needs.
//
// Fixed-width grid: ALWAYS `HEATMAP_MAX_WEEKS` whole Sun–Sat columns
// ending with the current week, whatever the history length. A two-week
// history therefore renders a full year of cells that are mostly empty,
// instead of a two-column sliver that reads as a broken chart. The
// trade-off is deliberate: cells left of the first record are empty
// because there was no data yet, not because nothing was dictated.
// `truncated` guards the OTHER edge — history older than the window is
// not in the grid, and the card says so.
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
 * Grid width, in whole weeks. 53 ≈ one year, the span a contribution
 * graph is conventionally read at. This is the grid's ACTUAL width, not
 * a cap: every render produces exactly this many columns, so the cells
 * stay a readable size and the card keeps the same shape as the history
 * grows.
 */
export const HEATMAP_MAX_WEEKS = 53;

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
		// dropping it keeps it from counting as a day AND from dragging the
		// `oldestKey` edge (which is what decides `truncated`).
		if (!DATE_KEY_RE.test(key)) continue;
		counts.set(key, (counts.get(key) ?? 0) + 1);
		if (oldestKey === null || key < oldestKey) oldestKey = key;
	}

	const endDate = startOfDay(now);
	const endWeekStart = startOfWeek(endDate);

	// Fixed width: walk back a whole year of Sundays from the current
	// week's anchor. Calendar arithmetic (setDate), not milliseconds, so a
	// DST transition inside the window cannot shift the anchor by an hour
	// and land the grid on the wrong weekday.
	const weeks = HEATMAP_MAX_WEEKS;
	const startWeekStart = new Date(endWeekStart);
	startWeekStart.setDate(startWeekStart.getDate() - (weeks - 1) * 7);
	startWeekStart.setHours(0, 0, 0, 0);

	// Truncation is judged against the window actually rendered: history
	// whose first week sits left of the grid start is the only case the
	// card has to disclose, because that data is genuinely not on screen.
	const truncated =
		oldestKey !== null &&
		startOfWeek(fromDateKey(oldestKey)).getTime() < startWeekStart.getTime();

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

	// `startWeekStart` is already the first Sunday of the window; returning
	// it directly keeps the card's range subtitle in step with the grid.
	return {
		columns,
		total,
		activeDays,
		startDate: startWeekStart,
		endDate,
		truncated,
	};
}
