// These functions are React-agnostic and have no side effects beyond
// reading their arguments, so they can be unit-tested in isolation and
// at module scope in `Dashboard.tsx` (lines ~80-235 of the pre-split
// file); behaviour is unchanged.
// Cross-module dependency note:
//   - `buildActivityBars` calls `dayAbbr` from `./format`; `./format`
//     imports only from `@/i18n/i18n`, no module cycle exists between
//     `./format` and this file.

import { dateKey, localDateKey, parseUtcTimestamp } from "@/lib/format";
import type { HistoryRecord } from "@/types/ipc";
import { dayAbbr, dayMonthAbbr } from "./format";

// ── Types ────────────────────────────────────────────────────────────

/**
 * Aggregate dashboard metrics derived from the backend's
 * `get_config` / `get_history` / `get_history_count` IPCs.
 * Kept in this module (rather than `lib/format.ts`) because the
 * period/activity helpers' return shapes are the `period` /
 * `activity` fields, co-locating the type with the producer keeps the
 * contract obvious.
 * NOTE: every metric here derives from ONE history sample (the last
 * 500 dictations) so the cards, chart, and streaks can never disagree
 * with each other. The only exception is `totalCount`, which comes
 * from the dedicated `get_history_count` IPC (the true all-time row
 * count). When `totalCount > sampleSize` the word/duration totals are
 * sampled, not complete, the page surfaces that with a footnote.
 */
export interface DashboardData {
	todayCount: number;
	todayChars: number;
	todayWordCount: number;
	todayDuration: number;
	totalCount: number;
	totalWords: number;
	totalDuration: number;
	favoritesCount: number;
	/** Active ASR model name, or null when no model is installed/selected. */
	model: string | null;
	/** Active compute device, or null when no model is installed/selected. */
	device: string | null;
	language: string;
	currentStreak: number;
	maxStreak: number;
	activeDays: number;
	/** Size of the history sample the derived stats are computed from. */
	sampleSize: number;
}

// ── Date helpers ─────────────────────────────────────────────────────
// ``localDateKey`` / ``parseUtcTimestamp`` / ``dateKey`` moved to
// ``@/lib/format`` (the shared locale/formatting utilities module) so
// the History page's date-grouped list can bucket rows by the same
// local calendar day WITHOUT importing from the dashboard feature
// folder. They are re-exported here so the existing dashboard imports
// (and the streaks unit tests) keep resolving unchanged. Note this
// imports these helpers from `@/lib/format` directly.

export {
	dateKey,
	localDateKey,
	parseUtcTimestamp,
} from "@/lib/format";

/** Date `now` shifted by `days` days (local calendar arithmetic). */
function addDays(now: Date, days: number): Date {
	const d = new Date(now);
	d.setDate(d.getDate() + days);
	return d;
}

// ── Daily-activity / streak computations ─────────────────────────────

/** Compute consecutive-day streak from history records. */
export function computeStreaks(records: HistoryRecord[]): {
	current: number;
	max: number;
	activeDays: number;
} {
	const days = new Set<string>();
	for (const r of records) {
		days.add(dateKey(r.timestamp));
	}
	const sorted = Array.from(days).sort().reverse();
	if (sorted.length === 0) return { current: 0, max: 0, activeDays: 0 };

	//use localDateKey (not toISOString().slice) so streak
	// calculations anchor on the user's local calendar day.
	const today = localDateKey(new Date());
	const yesterday = localDateKey(addDays(new Date(), -1));

	// Current streak (must include today or yesterday)
	let current = 0;
	if (sorted[0] === today || sorted[0] === yesterday) {
		for (let i = 0; i < sorted.length; i++) {
			const expected = localDateKey(addDays(new Date(), -i));
			if (sorted[i] === expected) current++;
			else break;
		}
	}

	// Max streak (scan all)
	let max = 1;
	let run = 1;
	for (let i = 1; i < sorted.length; i++) {
		// noUncheckedIndexedAccess: `sorted[i]` is `string | undefined`;
		// skip undefined entries, the diff computation is meaningless
		// for missing data and the rest of the loop would yield NaN.
		const prevStr = sorted[i - 1];
		const currStr = sorted[i];
		if (prevStr === undefined || currStr === undefined) continue;
		const prev = new Date(prevStr);
		const curr = new Date(currStr);
		const diffMs = prev.getTime() - curr.getTime();
		if (diffMs <= 86400000 * 1.5) {
			run++;
			if (run > max) max = run;
		} else {
			run = 1;
		}
	}
	if (sorted.length === 1) max = 1;

	return { current, max, activeDays: sorted.length };
}

// ── Time-range period computation (single source of truth) ───────────

/** Selectable analytics time ranges. `"custom"` is an explicit local-day
 *  window carried alongside (see CustomWindow); it never stands alone. */
export type RangeId = "today" | "7d" | "30d" | "all" | "custom";

/** Explicit custom window: inclusive local calendar day keys. */
export interface CustomWindow {
	startKey: string;
	endKey: string;
}

/** A resolved window: current + previous same-length day-key ranges. */
export interface ResolvedWindow {
	startKey: string;
	endKey: string;
	prevStartKey: string | null;
	prevEndKey: string | null;
}

/**
 * Resolve a range to concrete day keys. Presets anchor on `now`;
 * `"custom"` uses the caller's window and puts the previous window of
 * the same length immediately before it (trends keep working). A custom
 * range without a window falls back to the trailing 30 days: the store
 * invariant (validated on write + rehydrate) makes that unreachable in
 * production, and a guess beats a crash.
 */
export function resolveRangeWindow(
	range: RangeId,
	now: Date,
	custom?: CustomWindow | null,
): ResolvedWindow {
	if (range === "custom" && custom) {
		const spanDays =
			Math.round(
				(Date.parse(`${custom.endKey}T00:00:00Z`) -
					Date.parse(`${custom.startKey}T00:00:00Z`)) /
					86400000,
			) + 1;
		return {
			startKey: custom.startKey,
			endKey: custom.endKey,
			prevStartKey: shiftDayKey(custom.startKey, -spanDays),
			prevEndKey: shiftDayKey(custom.startKey, -1),
		};
	}
	if (range === "custom") {
		return resolveRangeWindow("30d", now);
	}
	const todayKey = localDateKey(now);
	const span = rangeDaySpan(range);
	if (span === null) {
		return {
			startKey: "0000-00-00",
			endKey: todayKey,
			prevStartKey: null,
			prevEndKey: null,
		};
	}
	return {
		startKey: localDateKey(addDays(now, -(span - 1))),
		endKey: todayKey,
		prevStartKey: localDateKey(addDays(now, -(span * 2 - 1))),
		prevEndKey: localDateKey(addDays(now, -span)),
	};
}

/** Shift a `YYYY-MM-DD` day key by whole calendar days (UTC date
 *  arithmetic: immune to DST and to the viewer's UTC offset, unlike
 *  local `setDate` on a UTC-midnight instant). */
function shiftDayKey(key: string, deltaDays: number): string {
	const [y = 1970, m = 1, d = 1] = key.split("-").map(Number);
	const shifted = new Date(Date.UTC(y, m - 1, d + deltaDays));
	return `${shifted.getUTCFullYear()}-${String(shifted.getUTCMonth() + 1).padStart(2, "0")}-${String(shifted.getUTCDate()).padStart(2, "0")}`;
}

/**
 * UTC `"YYYY-MM-DD HH:MM:SS"` bounds for a local-day window, for the
 * `get_history` `start_ts`/`end_ts` filter (storage order matches).
 * Start is inclusive (local midnight of the first day), end is exclusive
 * (local midnight of the day AFTER the last). Local-midnight arithmetic
 * rides through DST transitions instead of assuming 24h days.
 */
export function utcBoundsForWindow(
	startKey: string,
	endKey: string,
): { startTs: string; endTs: string } {
	const toUtcStamp = (d: Date) =>
		`${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")} ${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}:${String(d.getUTCSeconds()).padStart(2, "0")}`;
	// Keys are validated (`YYYY-MM-DD`) before they reach here; the
	// defaults below only satisfy noUncheckedIndexedAccess, they never
	// fire on real input.
	const [sy = 1970, sm = 1, sd = 1] = startKey.split("-").map(Number);
	const [ey = 1970, em = 1, ed = 1] = endKey.split("-").map(Number);
	const startLocal = new Date(sy, sm - 1, sd);
	const endExclusiveLocal = new Date(ey, em - 1, ed + 1);
	return {
		startTs: toUtcStamp(startLocal),
		endTs: toUtcStamp(endExclusiveLocal),
	};
}

/** Number of calendar days a range covers (null = unbounded / all-time). */
export function rangeDaySpan(range: RangeId): number | null {
	switch (range) {
		case "today":
			return 1;
		case "7d":
			return 7;
		case "30d":
			return 30;
		case "all":
			return null;
		case "custom":
			// Custom windows carry their own span (see resolveRangeWindow):
			// a single number cannot describe them. Throw so a missed
			// call site fails loudly instead of silently mis-windowing.
			throw new Error(
				"rangeDaySpan: custom ranges resolve via resolveRangeWindow",
			);
	}
}

export interface PeriodStats {
	range: RangeId;
	count: number;
	chars: number;
	wordCount: number;
	duration: number;
	/** Distinct calendar days with ≥1 dictation inside the window. */
	activeDays: number;
	/** chars / count (0 when the window has no dictations). */
	avgCharsPerDictation: number;
	/** Longest single dictation duration in the window (seconds). */
	longestSession: number;
	/** Weekday index (0=Sunday…6=Saturday) with the most dictations, or null when empty. */
	peakWeekday: number | null;
	/** Same-length previous window, or null for "all" (no prior period). */
	prev: {
		count: number;
		chars: number;
		wordCount: number;
		duration: number;
		/**
		 * Longest single dictation in the previous window. Already
		 * computed by `aggregate`, so the Longest Session card can carry
		 * the same trend as its five neighbours instead of being the one
		 * cell with a number and nothing to compare it to.
		 */
		longestSession: number;
	} | null;
}

interface WindowAgg {
	records: HistoryRecord[];
	count: number;
	chars: number;
	wordCount: number;
	duration: number;
	days: Set<string>;
	peakWeekday: number | null;
	longestSession: number;
}

function aggregate(records: HistoryRecord[]): WindowAgg {
	let chars = 0;
	let wordCount = 0;
	let duration = 0;
	let longestSession = 0;
	const days = new Set<string>();
	const weekdayCounts = new Map<number, number>();
	for (const r of records) {
		const d = parseUtcTimestamp(r.timestamp);
		chars += r.char_count ?? 0;
		wordCount += r.word_count ?? 0;
		duration += r.duration ?? 0;
		longestSession = Math.max(longestSession, r.duration ?? 0);
		days.add(dateKey(r.timestamp));
		if (!Number.isNaN(d.getTime())) {
			weekdayCounts.set(d.getDay(), (weekdayCounts.get(d.getDay()) ?? 0) + 1);
		}
	}
	let peakWeekday: number | null = null;
	let peakCount = 0;
	for (const [day, n] of weekdayCounts) {
		if (n > peakCount) {
			peakCount = n;
			peakWeekday = day;
		}
	}
	return {
		records,
		count: records.length,
		chars,
		wordCount,
		duration,
		days,
		peakWeekday,
		longestSession,
	};
}

export function computePeriodStats(
	records: HistoryRecord[],
	range: RangeId,
	now: Date = new Date(),
	customWindow?: CustomWindow | null,
): PeriodStats {
	const {
		startKey: windowStart,
		endKey: windowEnd,
		prevStartKey: prevWindowStart,
		prevEndKey: prevWindowEnd,
	} = resolveRangeWindow(range, now, customWindow);

	const inWindow = records.filter((r) => {
		const k = dateKey(r.timestamp);
		return k >= windowStart && k <= windowEnd;
	});
	const prevRecords =
		prevWindowStart !== null && prevWindowEnd !== null
			? records.filter((r) => {
					const k = dateKey(r.timestamp);
					return k >= prevWindowStart && k <= prevWindowEnd;
				})
			: [];

	const cur = aggregate(inWindow);
	const prevAgg = aggregate(prevRecords);

	return {
		range,
		count: cur.count,
		chars: cur.chars,
		wordCount: cur.wordCount,
		duration: cur.duration,
		activeDays: cur.days.size,
		avgCharsPerDictation: cur.count > 0 ? Math.round(cur.chars / cur.count) : 0,
		longestSession: cur.longestSession,
		peakWeekday: cur.peakWeekday,
		prev:
			prevWindowStart === null || prevWindowEnd === null
				? null
				: {
						count: prevAgg.count,
						chars: prevAgg.chars,
						wordCount: prevAgg.wordCount,
						duration: prevAgg.duration,
						longestSession: prevAgg.longestSession,
					},
	};
}

// ── Correction usage (per-range, from the server usage snapshot) ────

/**
 * Shape of the server's ``get_correction_usage`` snapshot
 * (``voice_typer/server/correction_usage.py``).
 * ``corrections_by_day`` / ``dictations_by_day`` are keyed by the
 * LOCAL calendar day (``YYYY-MM-DD``), the same bucketing as
 * ``localDateKey``, so the range window math here joins cleanly.
 */
export interface CorrectionUsageSnapshot {
	version?: number;
	entries?: Record<string, Record<string, { count: number; last_ts: number }>>;
	corrections_by_day?: Record<string, number>;
	dictations_by_day?: Record<string, number>;
}

/** Range-aware corrections-applied totals from the usage snapshot. */
export interface CorrectionStats {
	/** Vocabulary corrections the engine applied inside the window. */
	corrections: number;
	/** Completed dictations inside the window (the rate's denominator). */
	dictations: number;
	/** corrections ÷ dictations (0..1), or null when the window has no dictations. */
	rate: number | null;
	/** Corrections in the PREVIOUS same-length window, or null for "all". */
	prevCorrections: number | null;
}

export function computeCorrectionStats(
	usage: CorrectionUsageSnapshot | null,
	range: RangeId,
	now: Date = new Date(),
	customWindow?: CustomWindow | null,
): CorrectionStats {
	if (!usage)
		return { corrections: 0, dictations: 0, rate: null, prevCorrections: null };

	const correctionsByDay = usage.corrections_by_day ?? {};
	const dictationsByDay = usage.dictations_by_day ?? {};
	const {
		startKey: windowStart,
		endKey: windowEnd,
		prevStartKey: prevWindowStart,
		prevEndKey: prevWindowEnd,
	} = resolveRangeWindow(range, now, customWindow);

	let corrections = 0;
	let dictations = 0;
	let prevCorrections = 0;
	for (const [day, n] of Object.entries(correctionsByDay)) {
		if (day >= windowStart && day <= windowEnd) corrections += n ?? 0;
		if (prevWindowStart !== null && prevWindowEnd !== null) {
			if (day >= prevWindowStart && day <= prevWindowEnd)
				prevCorrections += n ?? 0;
		}
	}
	for (const [day, n] of Object.entries(dictationsByDay)) {
		if (day >= windowStart && day <= windowEnd) dictations += n ?? 0;
	}

	return {
		corrections,
		dictations,
		rate: dictations > 0 ? corrections / dictations : null,
		prevCorrections: prevWindowStart === null ? null : prevCorrections,
	};
}

// ── Chart bars (per-range, with zero-vs-missing distinction) ─────────

/** One bar in the activity chart. */
export interface ActivityBar {
	key: string;
	/** Short tick label ("Mon", "9", "12"). */
	label: string;
	count: number;
	isMissing: boolean;
}

export type ChartKind = "hourly" | "daily";

export interface ActivityChartData {
	bars: ActivityBar[];
	kind: ChartKind;
	/** Oldest date key covered by the sample (null when empty). */
	coveredFromKey: string | null;
	/** Number of calendar days the bars span. */
	daySpan: number;
}

/**
 * Widest daily span whose bars are still identified by weekday name.
 * Past a week the name stops being an identifier — "Thu" recurs four
 * times in a 30-day window — so the ticks switch to month + day. The
 * chart's tick SPACING reads the same threshold, so the label text and
 * the labels' density can never drift apart.
 */
export const WEEKDAY_LABEL_MAX_SPAN = 7;

/** Build the chart bars for the selected range from the history sample. */
export function buildActivityBars(
	records: HistoryRecord[],
	range: RangeId,
	now: Date = new Date(),
	customWindow?: CustomWindow | null,
): ActivityChartData {
	const { startKey, endKey } = resolveRangeWindow(range, now, customWindow);
	const spanDays =
		Math.round(
			(Date.parse(`${endKey}T00:00:00Z`) -
				Date.parse(`${startKey}T00:00:00Z`)) /
				86400000,
		) + 1;
	if (range === "today" || (range === "custom" && spanDays <= 1)) {
		return buildHourlyBars(
			records,
			range === "today" ? localDateKey(now) : startKey,
			// Past days have no future hours; today caps at the current one.
			range === "today" ? now.getHours() : null,
		);
	}
	// "all" renders the trailing 30 days (per-day bars are unbounded
	// otherwise); the subtitle communicates the window.
	const span = range === "all" ? 30 : spanDays;
	const anchoredEnd = range === "all" ? localDateKey(now) : endKey;
	const anchoredStart =
		range === "all" ? localDateKey(addDays(now, -(span - 1))) : startKey;

	const counts = new Map<string, number>();
	let coveredFromKey: string | null = null;
	for (const r of records) {
		const k = dateKey(r.timestamp);
		if (coveredFromKey === null || k < coveredFromKey) coveredFromKey = k;
		if (k >= anchoredStart && k <= anchoredEnd) {
			counts.set(k, (counts.get(k) ?? 0) + 1);
		}
	}

	const bars: ActivityBar[] = [];
	// Weekday names identify a day only within a week; the wider ranges
	// label the ticks with month + day instead.
	const weekdayLabels = span <= WEEKDAY_LABEL_MAX_SPAN;
	for (let i = 0; i < span; i++) {
		const key = shiftDayKey(anchoredStart, i);
		const missing = coveredFromKey !== null && key < coveredFromKey;
		bars.push({
			key,
			label: weekdayLabels ? dayAbbr(key) : dayMonthAbbr(key),
			count: counts.get(key) ?? 0,
			isMissing: missing,
		});
	}
	return { bars, kind: "daily", coveredFromKey, daySpan: span };
}

/** Per-hour bars for a single day. `hourCap` hides future hours (today);
 *  null marks every hour eligible (a fully-past custom day). */
function buildHourlyBars(
	records: HistoryRecord[],
	dayKey: string,
	hourCap: number | null,
): ActivityChartData {
	const counts = new Map<number, number>();
	let coveredFromKey: string | null = null;
	for (const r of records) {
		const d = parseUtcTimestamp(r.timestamp);
		const k = dateKey(r.timestamp);
		if (coveredFromKey === null || k < coveredFromKey) coveredFromKey = k;
		if (k === dayKey && !Number.isNaN(d.getTime())) {
			counts.set(d.getHours(), (counts.get(d.getHours()) ?? 0) + 1);
		}
	}
	const bars: ActivityBar[] = [];
	for (let h = 0; h < 24; h++) {
		bars.push({
			key: `${dayKey}-${h}`,
			label: String(h),
			count: counts.get(h) ?? 0,
			// Future hours can't have data yet, a "no data" slot, not
			// a zero-activity one.
			isMissing: hourCap !== null && h > hourCap,
		});
	}
	return { bars, kind: "hourly", coveredFromKey, daySpan: 1 };
}
