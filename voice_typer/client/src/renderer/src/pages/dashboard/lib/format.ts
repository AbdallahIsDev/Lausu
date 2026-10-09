// `pages/Dashboard.tsx`.
// These helpers render human-facing strings (day-of-week abbreviations
// and month+day dates for chart tick labels). They have no React
// dependency, `t` resolves the active i18n locale at call time.
// This module imports ONLY from `@/i18n/i18n`, in particular it does
// NOT import from `./streaks`, so no import cycle can form between the
// two dashboard lib modules (`./streaks` imports `dayAbbr` from here).

import { getLocale, t } from "@/i18n/i18n";

/**
 * `YYYY-MM-DD` → a LOCAL-midnight Date. NOT `new Date(key)`: a bare
 * date string parses as UTC midnight, so reading its weekday/day
 * components back out shifts the label one day early for every viewer
 * west of UTC.
 */
function parseDayKey(key: string): Date {
	const [y = 1970, m = 1, d = 1] = key.split("-").map(Number);
	return new Date(y, m - 1, d);
}

/** Get day-of-week abbreviation for a date string. */
export function dayAbbr(dateStr: string): string {
	const label = weekdayLabel(parseDayKey(dateStr).getDay());
	// noUncheckedIndexedAccess: weekdayLabel returns "" for an
	// out-of-range index (an unparseable key yields NaN here), fall back
	// to the original input string so we never lie about the return type.
	return label || dateStr;
}

/**
 * Localized "Sep 10" label for a day key. Used as the activity chart's
 * x tick once the span is wider than a week, where a weekday name stops
 * identifying a date — "Thu" recurs four times in a 30-day window.
 */
export function dayMonthAbbr(dateStr: string): string {
	return new Intl.DateTimeFormat(getLocale(), {
		month: "short",
		day: "numeric",
	}).format(parseDayKey(dateStr));
}

/** Get the localized name for a weekday index (0=Sunday…6=Saturday). */
export function weekdayLabel(index: number): string {
	const days = [
		t("analytics.days.sun"),
		t("analytics.days.mon"),
		t("analytics.days.tue"),
		t("analytics.days.wed"),
		t("analytics.days.thu"),
		t("analytics.days.fri"),
		t("analytics.days.sat"),
	];
	return days[index] ?? "";
}

/**
 * Localized "Oct 1 – Oct 9" label for a custom window (chart subtitle,
 * Custom button). Year appears only when the window spans years.
 * Keys are validated `YYYY-MM-DD` before they reach here.
 */
export function formatWindowLabel(startKey: string, endKey: string): string {
	const start = parseDayKey(startKey);
	const end = parseDayKey(endKey);
	const locale = getLocale();
	if (start.getFullYear() === end.getFullYear()) {
		const fmt = new Intl.DateTimeFormat(locale, {
			month: "short",
			day: "numeric",
		});
		return `${fmt.format(start)} – ${fmt.format(end)}`;
	}
	const fmt = new Intl.DateTimeFormat(locale, {
		month: "short",
		day: "numeric",
		year: "numeric",
	});
	return `${fmt.format(start)} – ${fmt.format(end)}`;
}
