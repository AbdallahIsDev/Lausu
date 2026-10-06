// Contribution-style dictation heatmap card for the Analytics (Dashboard)
// page. Wraps the vendored Bklit UI chart
// (`@bklit/heatmap-chart`, see `components.json` → `registries.@bklit`,
// source under `components/charts/heatmap/`).
//
// Why this card is NOT range-aware: the page's TimeRangeSelector answers
// "what happened in this window"; the heatmap answers "how consistent
// have I been", which only reads at a scale of months. Driving it from
// the selector would collapse "Today" to a single cell. The card prints
// its own covered range in the subtitle so the two windows can never be
// mistaken for each other.
//
// The grid is FIXED-WIDTH — always 53 weeks ending with the current week
// (see `../lib/heatmap`). A two-week history therefore renders a full
// year of cells that are mostly empty, rather than a two-column sliver;
// the empty cells left of the first record mean "no data yet".
//
// Accessibility: the chart's <svg> is `aria-hidden`, so the whole card
// body is exposed as ONE `role="img"` with a summary label (same
// contract as the activity chart) — 180+ hover-only cells must not
// become 180 tab stops, and there is no keyboard path to a cell's
// tooltip, so the summary carries the totals instead.
//
// i18n: the vendored chart hardcodes English formatting in
// `HeatmapXAxis` (month names), `HeatmapYAxis` (weekday names) and
// `HeatmapTooltip` (date/weekday). All three take override props, and this
// card feeds them locale-derived values, so every string the chart renders
// here is translated (C-I18N-1). The month labels matter most: a
// full-year grid shows ~13 of them.

import { LayoutGridIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useMemo } from "react";
import {
	HeatmapCells,
	HeatmapChart,
	HeatmapInteractionBoundary,
	HeatmapInteractionProvider,
	HeatmapLegend,
	HeatmapTooltip,
	HeatmapXAxis,
	HeatmapYAxis,
} from "@/components/charts/heatmap";
import { getLocale, t, tChoice } from "@/i18n/i18n";
import type { DictationHeatmap } from "../lib/heatmap";

const RANGE_FORMAT: Intl.DateTimeFormatOptions = {
	month: "short",
	day: "numeric",
};

/** Localised "Jan 5 – Oct 6" (year added only when the range spans two). */
function formatRange(start: Date, end: Date, locale: string): string {
	const short = new Intl.DateTimeFormat(locale, RANGE_FORMAT);
	const startLabel =
		start.getFullYear() === end.getFullYear()
			? short.format(start)
			: new Intl.DateTimeFormat(locale, {
					...RANGE_FORMAT,
					year: "numeric",
				}).format(start);
	return `${startLabel} – ${short.format(end)}`;
}

export interface ActivityHeatmapProps {
	heatmap: DictationHeatmap;
}

export function ActivityHeatmap({ heatmap }: ActivityHeatmapProps) {
	const { columns, total, activeDays, startDate, endDate, truncated } = heatmap;

	const locale = getLocale();
	const rangeLabel = useMemo(
		() => formatRange(startDate, endDate, locale),
		[startDate, endDate, locale],
	);

	// The vendored chart defaults to English-only weekday/date formatting;
	// this card is translated, so it derives every label the chart renders
	// from the active locale (C-I18N-1) via the chart's override props.
	// Sunday-first, matching `weekStartDay={0}` below.
	const dayLabels = useMemo(() => {
		const fmt = new Intl.DateTimeFormat(locale, { weekday: "short" });
		// 2023-01-01 is a Sunday, so index 0 stays Sunday-first.
		return Array.from({ length: 7 }, (_, i) =>
			fmt.format(new Date(2023, 0, 1 + i)),
		);
	}, [locale]);

	// January-first, because `buildHeatmapMonthTicks` indexes it by
	// `Date.getMonth()`. A full-year grid renders ~13 month labels, so
	// leaving them English would be the loudest untranslated string on the
	// card (C-I18N-1).
	const monthLabels = useMemo(() => {
		const fmt = new Intl.DateTimeFormat(locale, { month: "short" });
		return Array.from({ length: 12 }, (_, i) =>
			fmt.format(new Date(2023, i, 1)),
		);
	}, [locale]);

	const formatDate = useMemo(() => {
		const fmt = new Intl.DateTimeFormat(locale, {
			day: "numeric",
			month: "long",
			year: "numeric",
		});
		return (date: Date) => fmt.format(date);
	}, [locale]);

	const formatWeekday = useMemo(() => {
		const fmt = new Intl.DateTimeFormat(locale, { weekday: "long" });
		return (date: Date) => fmt.format(date);
	}, [locale]);

	const title = t("analytics.heatmap.title");

	return (
		<section
			aria-label={title}
			className="flex flex-col gap-4 rounded-lg border border-border/8 bg-surface-subtle p-4"
		>
			<div className="flex items-center gap-2.5">
				{/* Grid glyph: the heatmap IS a grid of squares, so it reads as
				    "this card is the grid" rather than a second analytics
				    glyph next to the page's own Analytics nav icon. */}
				<HugeiconsIcon
					className="h-8 w-8 shrink-0 text-muted-foreground"
					icon={LayoutGridIcon}
					strokeWidth={1}
				/>
				<div className="flex flex-col gap-0.5">
					<h2 className="font-sans text-sm font-semibold text-foreground">
						{title}
					</h2>
					<p className="text-xs text-muted-foreground">
						{rangeLabel} · {t("analytics.byDay")}
						{truncated ? ` · ${t("analytics.heatmap.truncated")}` : ""}
					</p>
				</div>
			</div>

			<div
				role="img"
				aria-label={t("analytics.heatmap.aria", {
					total: String(total),
					days: String(activeDays),
				})}
			>
				{/* The provider sits ABOVE both chart and legend so hovering a
				    legend swatch dims the matching cells (the chart's own
				    internal provider is skipped when one already exists). */}
				<HeatmapInteractionProvider>
					<HeatmapInteractionBoundary className="w-full">
						<HeatmapChart
							data={columns}
							layout="fluid"
							// Cell size comes from the full grid width, not from
							// the columns the x-domain filter happens to keep:
							// `fluid` divides innerWidth by this, so using the
							// filtered count would resize all 53 cells whenever
							// one boundary column drops.
							sizingColumnCount={columns.length}
							weekStartDay={0}
							xDomain={[startDate, endDate]}
						>
							{/* Ghost cells stay ON screen. The chart's ghost logic
							    infers a GitHub-style calendar range from the grid
							    shape and hides the bins outside it — which, on
							    the days that inference matches, would shave the
							    leading days of column 0 and the trailing days of
							    the current week, leaving a ragged edge that
							    changes shape by date. The card's whole point is a
							    complete rectangle, so opt out. */}
							<HeatmapCells hideGhostCells={false} />
							<HeatmapXAxis monthLabels={monthLabels} />
							<HeatmapYAxis dayLabels={dayLabels} />
							<HeatmapTooltip
								formatDate={formatDate}
								formatLabel={(count) =>
									tChoice("analytics.heatmap.tooltip", count)
								}
								formatWeekday={formatWeekday}
							/>
						</HeatmapChart>
						<HeatmapLegend
							className="mt-3"
							lessLabel={t("analytics.heatmap.less")}
							moreLabel={t("analytics.heatmap.more")}
						/>
					</HeatmapInteractionBoundary>
				</HeatmapInteractionProvider>
			</div>
		</section>
	);
}
