/**
 * AnalyticsRangeSwitcher — the Analytics time range (Today / 7 Days /
 * 30 Days / All Time) in the title-bar middle strip.
 *
 * Same PLACEMENT pattern as ModelsTabSwitcher: the control lives in the
 * bar's middle strip while `currentPage === "analytics"` and unmounts
 * elsewhere, so the range is always reachable even once the page has
 * scrolled.
 *
 * TWO controls, not one (2026-10-11):
 *
 * 1. A `ToggleGroup` of the four preset pills. Picking one swaps the data
 *    window the page shows — the "change what is displayed" job.
 * 2. A standalone calendar BUTTON beside it, one small gap away. It opens
 *    the custom-range dropdown — a disclosure job, not a selection. It
 *    used to be a fifth icon-only pill INSIDE the group, which made it
 *    read as another tab and set exactly the wrong expectation: users
 *    click a tab to change the page, but that pill opened a menu.
 *
 * The split also removes the two animation bugs that came with the pill.
 * The highlight used to slide onto the calendar while the panel was open
 * (the group was forced onto a `"custom"` value to light the icon), and
 * re-clicking could only ever re-open rather than close (a radio ignores
 * a re-click of itself, so the click had to be routed through the
 * primitive's `onOptionActivate` and still had nothing to toggle).
 * Neither is reachable now: the group's value is always a preset or
 * `null`, and the button owns its own open/close.
 *
 * Highlight rules, each a consequence of the above:
 * - Opening the dropdown changes NOTHING about the range, so the
 *   highlight stays on the tab the user was already on.
 * - Committing a custom window sets `range === "custom"`, which the group
 *   receives as `null` → no pill is lit and the indicator fades out. The
 *   custom window, not a preset, now decides what the page shows.
 * - The calendar button carries the active state for that case, so
 *   "which range is live" stays visible in the row.
 * - A picked window that coincides with a preset lands back on that
 *   preset's pill (`matchPreset`), so the indicator returns.
 *
 * The panel runs trigger-less under a plain absolutely-positioned anchor
 * div, so it hangs 8px below the row with its right edge under the
 * calendar button (the last in-flow item, so it opens inward instead of
 * off the window). It closes on Escape / outside pointer / apply;
 * `dismissGuard` tells it this row counts as INSIDE, so the pointerdown
 * half of the button's own closing click cannot pre-dismiss the panel and
 * leave the click to reopen it.
 *
 * Deliberately NOT `variant="tabs"` (which ModelsTabSwitcher uses): that
 * variant renders a WAI-ARIA tablist whose every tab must control a real
 * `role="tabpanel"`. The range picks a data window — there is no panel to
 * point at — so this keeps the radiogroup variant, the primitive's
 * documented job ("one setting with mutually exclusive values"). It
 * therefore wears the recessed-track look rather than the Models
 * switcher's transparent tab strip.
 *
 * State lives in `stores/useAnalyticsRange` (not component state) so the
 * title bar and the page, which are separate component trees, read the
 * same value.
 */

import { Calendar01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { memo, useCallback, useRef, useState } from "react";
import {
	type DateRange,
	DateRangePicker,
} from "@/components/ui/date-range-picker";
import {
	ToggleGroup,
	type ToggleGroupOption,
} from "@/components/ui/toggle-group";
import { getLocale, t, tChoice } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import {
	ANALYTICS_RANGES,
	CUSTOM_RANGE_MAX_DAYS,
	type PresetRange,
	useAnalyticsRange,
} from "@/stores/useAnalyticsRange";
import type { Page } from "@/types/ipc";

interface AnalyticsRangeSwitcherProps {
	currentPage: Page;
}

/** Local `YYYY-MM-DD` key for a Date (picker hands us Dates). */
function keyOfLocal(d: Date): string {
	return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Shift a validated day key by whole local days (validated input only). */
function shiftLocalKey(key: string, delta: number): string {
	const [y = 1970, m = 1, d = 1] = key.split("-").map(Number);
	return keyOfLocal(new Date(y, m - 1, d + delta));
}

function dateFromKey(key: string): Date {
	const [y = 1970, m = 1, d = 1] = key.split("-").map(Number);
	return new Date(y, m - 1, d);
}

/**
 * Match an applied picker range back to a preset (so a hand-picked span
 * that coincides with one lands on the same state as the pill row).
 * Anchored on today: anything else — including a single past day — is a
 * genuine custom window.
 */
function matchPreset(startKey: string, endKey: string): PresetRange | null {
	const todayKey = keyOfLocal(new Date());
	if (endKey !== todayKey) return null;
	if (startKey === todayKey) return "today";
	if (startKey === shiftLocalKey(todayKey, -6)) return "7d";
	if (startKey === shiftLocalKey(todayKey, -29)) return "30d";
	return null;
}

export const AnalyticsRangeSwitcher = memo(function AnalyticsRangeSwitcher({
	currentPage,
}: AnalyticsRangeSwitcherProps) {
	const range = useAnalyticsRange((s) => s.range);
	const customWindow = useAnalyticsRange((s) => s.customWindow);
	const setRange = useAnalyticsRange((s) => s.setRange);
	const setCustomRange = useAnalyticsRange((s) => s.setCustomRange);
	const [picking, setPicking] = useState(false);
	// The row holds BOTH controls AND the panel, so a pointerdown on
	// either control must not read as "outside" the panel.
	const rowRef = useRef<HTMLDivElement>(null);
	const guardRow = useCallback(() => rowRef.current, []);

	const customActive = range === "custom";

	// Presets only now. Picking one always means "show this window", so it
	// also drops an open panel: leaving it up would strand a picker whose
	// own selection no longer matches the row.
	const handleToggleChange = (value: PresetRange) => {
		setPicking(false);
		setRange(value);
	};

	const handlePickerOpenChange = useCallback((open: boolean) => {
		if (!open) setPicking(false);
	}, []);

	// A disclosure toggle, not a radio: click opens, click again closes.
	// The panel's outside-dismiss treats this row as INSIDE
	// (`dismissGuard`), so the pointerdown half of the closing click
	// cannot dismiss the panel first and leave the click to reopen it.
	const togglePicker = useCallback(() => setPicking((open) => !open), []);

	const applyPickedRange = (picked: DateRange) => {
		const preset = matchPreset(
			keyOfLocal(picked.start),
			keyOfLocal(picked.end),
		);
		if (preset) setRange(preset);
		else
			setCustomRange({
				startKey: keyOfLocal(picked.start),
				endKey: keyOfLocal(picked.end),
			});
		setPicking(false);
	};

	if (currentPage !== "analytics") return null;

	const options: ToggleGroupOption<PresetRange>[] = ANALYTICS_RANGES.map(
		(r) => ({
			value: r,
			label: t(`analytics.range.${r}`),
		}),
	);

	const today = new Date();
	const minDate = new Date(
		today.getFullYear(),
		today.getMonth(),
		today.getDate() - (CUSTOM_RANGE_MAX_DAYS - 1),
	);
	const maxDate = new Date(
		today.getFullYear(),
		today.getMonth(),
		today.getDate(),
	);

	return (
		<div ref={rowRef} className="relative flex items-center gap-1.5">
			<ToggleGroup
				options={options}
				// `null` while a custom window is live: no preset pill is the
				// truth then, so the indicator fades out rather than staying
				// lit on the pill the user came from. Opening the picker
				// deliberately does NOT touch `range`, so the highlight stays
				// put while the panel is open.
				value={range === "custom" ? null : range}
				onChange={handleToggleChange}
				ariaLabel={t("analytics.rangeAria")}
				// `no-drag`: the strip sits inside the title bar's drag region,
				// so without it a click would start a window move instead of
				// selecting a range. `h-full` fills the 36px bar the way the
				// Models switcher does.
				className="no-drag h-full"
			/>
			{/* The custom-range disclosure. It wears the same recessed track
			    as the group (same p-0.5, same radius, same hairline ring) so
			    the two read as siblings, and the gap between them is what
			    keeps it from reading as a fifth segment. The inner span is
			    the pill that lights up when a custom window is live — the
			    same raised-surface treatment the group gives its selected
			    option, so "which range is live" reads identically on both. */}
			<button
				type="button"
				onClick={togglePicker}
				aria-haspopup="dialog"
				aria-expanded={picking}
				aria-pressed={customActive}
				aria-label={t("analytics.rangeCustomAria")}
				title={t("analytics.range.custom")}
				className={cn(
					"no-drag inline-flex h-full cursor-pointer items-center justify-center rounded-lg bg-border/6 p-0.5 shadow-[0_0_0_1px_rgba(0,0,0,0.1)] outline-hidden transition-colors duration-150 dark:bg-border/5",
					"focus-visible:ring-1 focus-visible:ring-ring",
				)}
			>
				<span
					className={cn(
						"inline-flex items-center justify-center rounded-lg px-2.5 py-1 transition-colors duration-150",
						customActive
							? "bg-surface text-foreground shadow-xs dark:bg-border/10"
							: "text-muted-foreground hover:text-foreground",
					)}
				>
					<HugeiconsIcon
						icon={Calendar01Icon}
						strokeWidth={2}
						className="h-4 w-4 shrink-0"
					/>
				</span>
			</button>
			{/* Trigger-less picker: the calendar button above opens the panel;
			    the anchor below only places it. The anchor is a plain div,
			    so the utility classes win — the picker's own root is
			    `position: relative` from its stylesheet, which would
			    silently ignore an `absolute` class and leave the panel
			    hanging off the end of the row instead of under it.
			    `right-0` + align="end" keeps the panel's right edge under
			    the calendar button (the last in-flow item), so it opens
			    into the row rather than off the right of the window. */}
			<div className="no-drag absolute top-[calc(100%+8px)] right-0">
				<DateRangePicker
					value={
						customWindow
							? {
									start: dateFromKey(customWindow.startKey),
									end: dateFromKey(customWindow.endKey),
								}
							: null
					}
					onChange={applyPickedRange}
					label={t("analytics.rangeAria")}
					placeholder={t("analytics.range.custom")}
					presets={[]}
					minDate={minDate}
					maxDate={maxDate}
					months={1}
					locale={getLocale()}
					open={picking}
					onOpenChange={handlePickerOpenChange}
					hideTrigger
					autoApply
					align="end"
					dismissGuard={guardRow}
					className="no-drag"
					strings={{
						presetsLabel: t("analytics.rangePicker.presets"),
						prevMonthLabel: t("analytics.rangePicker.prevMonth"),
						nextMonthLabel: t("analytics.rangePicker.nextMonth"),
						cancelLabel: t("analytics.rangePicker.cancel"),
						applyLabel: t("analytics.rangePicker.apply"),
						pickEndDateHint: t("analytics.rangePicker.pickEndDate"),
						noDatesText: t("analytics.rangePicker.noDates"),
						formatDayCount: (days) =>
							tChoice("analytics.rangePicker.days", days),
						formatStatusStart: (startText) =>
							t("analytics.rangePicker.statusStart", { date: startText }),
						formatStatusShown: (shownText, countText) =>
							t("analytics.rangePicker.statusShown", {
								shown: shownText,
								count: countText,
							}),
					}}
				/>
			</div>
		</div>
	);
});
