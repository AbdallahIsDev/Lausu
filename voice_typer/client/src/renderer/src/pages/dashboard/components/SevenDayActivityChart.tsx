// Range-aware activity chart for the Dashboard: one column per slot
// (a day, or an hour on the "Today" view) with tick labels + horizontal
// gridlines, bars scaled to the max value in the range, the count above
// each bar, and a hover tooltip per bar (tChoice, locale-aware plurals).
// Zero-vs-no-data: a slot with no dictations draws NOTHING, so a quiet
// day reads as an empty column instead of as a tiny bar; a NO-DATA slot
// — a future hour on the "Today" view, or a day OLDER than the oldest
// record in the history sample — keeps a dashed tick, because "outside
// the sample" is a different claim from "nothing happened".
// Accessibility (preserved contract): the whole chart is exposed to AT
// as a single role="img" with a descriptive aria-label (no dead-end tab
// stops); each bar is a non-interactive <div> with a title tooltip for
// sighted mouse users.

import { t, tChoice } from "@/i18n/i18n";
import { cn } from "@/lib/utils";

import type { ActivityChartData, RangeId } from "../lib/streaks";

export interface ActivityChartProps {
	range: RangeId;
	activity: ActivityChartData;
}

/** Show an x tick label every N bars (crowding control for wide ranges). */
function tickEvery(activity: ActivityChartData): number {
	if (activity.kind === "hourly") return 3;
	const span = activity.daySpan;
	if (span <= 7) return 1;
	if (span <= 14) return 2;
	return 5;
}

export function ActivityChart({ range, activity }: ActivityChartProps) {
	const { bars, kind } = activity;
	const maxCount = Math.max(1, ...bars.map((b) => b.count));
	// Y-axis ticks at max / mid / 0. When the max is 1, the mid tick
	// would duplicate it (the "1" printed twice at two heights bug) —
	// drop the mid tick so every label is unique. maxCount=2 →
	// [2, 1, 0], still unique.
	const midCount = maxCount > 1 ? Math.max(1, Math.round(maxCount / 2)) : 0;
	const yTicks = maxCount > 1 ? [maxCount, midCount, 0] : [1, 0];
	const every = tickEvery(activity);

	// Range label for the header's trailing line + aria-label.
	const rangeLabel = t(`analytics.range.${range}`);
	const unitLabel =
		kind === "hourly" ? t("analytics.byHour") : t("analytics.byDay");

	const ariaCounts = bars.map((b) => `${b.label}: ${b.count}`).join(", ");

	return (
		<div className="flex flex-col gap-4 rounded-lg border border-border/8 bg-surface-subtle p-4">
			{/* Title and range/unit on ONE baseline, title leading and the
			    window trailing — the same header shape as the heatmap
			    card below, so the two cards' headers read as a pair.
			    Stacking them cost a row of height that said nothing the
			    title did not already imply. */}
			<div className="flex items-baseline justify-between gap-3">
				<h2 className="min-w-0 truncate font-sans text-sm font-semibold text-foreground">
					{t("analytics.activityTitle")}
				</h2>
				<p className="shrink-0 text-xs leading-tight text-muted-foreground">
					{rangeLabel} · {unitLabel}
				</p>
			</div>

			<div
				role="img"
				aria-label={t("analytics.activityChartAria", {
					range: rangeLabel,
					counts: ariaCounts,
				})}
				className="flex flex-col gap-2"
			>
				<div className="flex gap-2">
					{/* Y axis: unique tick labels (max / mid / 0; mid is
						dropped when it would duplicate max). */}
					<div className="flex h-36 w-7 shrink-0 flex-col justify-between pb-0 text-end text-[10px] tabular-nums text-muted-foreground">
						{yTicks.map((tick) => (
							<span key={tick}>{tick}</span>
						))}
					</div>

					{/* Plot with gridlines (one per tick, same layout) */}
					<div className="relative min-w-0 flex-1">
						<div
							aria-hidden="true"
							className="pointer-events-none absolute inset-0 flex flex-col justify-between"
						>
							{yTicks.map((tick) => (
								<div key={tick} className="border-t border-border/15" />
							))}
						</div>
						<div className="relative flex h-36 items-end gap-1">
							{bars.map((bar) => {
								// Scale to 90% of the plot so the count label above the
								// tallest bar stays INSIDE the plot (below the max
								// gridline) instead of overflowing into the axis.
								const pct =
									bar.count > 0
										? Math.max(6, Math.round((bar.count / maxCount) * 90))
										: 0;
								const tooltip = bar.isMissing
									? t("analytics.noDataBar", { label: bar.label })
									: tChoice("analytics.dayCountTooltip", bar.count, {
											label: bar.label,
										});
								return (
									<div
										key={bar.key}
										className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1"
									>
										{/* count label above the bar (only when > 0) */}
										<span className="text-[10px] leading-none tabular-nums text-muted-foreground">
											{bar.count > 0 ? bar.count : ""}
										</span>
										{/* A quiet day draws NO mark at all: the plot
										    then contains only real activity plus the
										    dashed "no data" ticks, so an empty column
										    reads as absence rather than as a bar of
										    height zero. The fill is a flat `bg-accent`
										    with no alpha step and no hover — the bar
										    is a read-out, not a control. */}
										{(bar.count > 0 || bar.isMissing) && (
											<div
												title={tooltip}
												className={cn(
													"w-full max-w-8 rounded-t-lg transition-all duration-300",
													bar.count > 0 && "bg-accent",
													bar.isMissing &&
														"h-1 border-t border-dashed border-border/8 bg-transparent",
												)}
												style={{
													height: bar.count > 0 ? `${pct}%` : undefined,
												}}
											/>
										)}
									</div>
								);
							})}
						</div>
					</div>
				</div>

				{/* X axis labels (aligned under the plot, skipping for crowding) */}
				<div className="flex gap-2">
					<div className="w-7 shrink-0" aria-hidden="true" />
					<div className="flex min-w-0 flex-1 gap-1">
						{bars.map((bar, i) => (
							<div
								key={bar.key}
								className={cn(
									"min-w-0 flex-1 text-center text-[10px] text-muted-foreground",
									i % every !== 0 && "invisible",
								)}
							>
								{bar.label}
							</div>
						))}
					</div>
				</div>
			</div>
		</div>
	);
}
