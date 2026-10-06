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
// Accessibility: the chart's <svg> is `aria-hidden`, so the whole card
// body is exposed as ONE `role="img"` with a summary label (same
// contract as the activity chart) — 180+ hover-only cells must not
// become 180 tab stops, and there is no keyboard path to a cell's
// tooltip, so the summary carries the totals instead.
//
// i18n: the vendored chart hardcodes English weekday/date formatting in
// `HeatmapYAxis` and `HeatmapTooltip`. Both now take override props, and
// this card feeds them locale-derived values, so every string the chart
// renders here is translated (C-I18N-1) — including the y-axis day names
// and the tooltip's date/weekday lines.

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

/**
 * Cell sizing is computed as if the grid had at least this many columns.
 *
 * `layout="fluid"` sizes each cell as `innerWidth / columnCount`, so a
 * short history (a user two weeks in → 3 columns) would render three
 * ~230px squares and blow the card height past 1600px. The chart only
 * consults `sizingColumnCount` when `xDomain` is set, so the card passes
 * both. Longer histories are unaffected: the actual column count wins
 * above this floor and the cells shrink to fit the card exactly.
 */
const MIN_SIZING_COLUMNS = 26;

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
							sizingColumnCount={Math.max(columns.length, MIN_SIZING_COLUMNS)}
							weekStartDay={0}
							xDomain={[startDate, endDate]}
						>
							<HeatmapCells />
							<HeatmapXAxis />
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
