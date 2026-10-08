import type { IconSvgElement } from "@hugeicons/react";
import { HugeiconsIcon } from "@hugeicons/react";
import type { ReactNode } from "react";

import { t } from "@/i18n/i18n";
import { cn } from "@/lib/utils";

export interface StatTrend {
	/** Percentage change vs the previous period (can be 0 = flat). */
	pct: number;
	up: boolean;
}

interface StatCardProps {
	label: string;
	value: string;
	icon: IconSvgElement;
	trend?: StatTrend | null;
	/**
	 * Drops the card's own radius/border/background (padding stays) so a
	 * parent can wrap several cards in ONE bordered surface and separate
	 * them with dividers instead of gaps (C-DESIGN-2).
	 */
	inGroup?: boolean;
	/**
	 * Secondary line under the value (e.g. the corrections rate);
	 * omitted when the cell has no derived sub-metric.
	 */
	sublabel?: ReactNode;
}

function TrendIndicator({ trend }: { trend: StatTrend }) {
	const { pct, up } = trend;
	// Screen-reader copy + native tooltip for the arrow glyph (aria-hidden).
	const ariaLabel =
		pct === 0
			? t("analytics.trendFlatLabel")
			: up
				? t("analytics.trendUpLabel", { pct: String(pct) })
				: t("analytics.trendDownLabel", { pct: String(pct) });
	const glyph = pct === 0 ? "–" : up ? "▲" : "▼";
	return (
		<span
			title={ariaLabel}
			role="img"
			aria-label={ariaLabel}
			className={cn(
				"inline-flex shrink-0 items-center gap-0.5 text-[11px] font-medium tabular-nums",
				pct === 0 && "text-muted-foreground",
				pct > 0 && up && "text-emerald-500",
				pct > 0 && !up && "text-destructive",
			)}
		>
			<span aria-hidden="true" className="text-[9px] leading-none">
				{glyph}
			</span>
			{pct > 0 ? `${pct}%` : ""}
		</span>
	);
}

export function StatCard({
	label,
	value,
	icon,
	trend,
	inGroup,
	sublabel,
}: StatCardProps) {
	return (
		// Informational display card, NOT interactive: no hover
		// lift/border change. Layout: a single top row of icon +
		// label (horizontal, left-aligned, not stacked), then ONE
		// bottom row holding the value hard left and its trend hard
		// right, baseline-aligned so the percentage sits on the
		// number's own line instead of under it. `mt-auto` on that
		// row pins the icon+label row to the top of the stretched
		// cell and pushes the number down; `min-h-24` guarantees the
		// breathing room even when the group's tallest cell is
		// otherwise only as tall as its content.
		<div
			className={cn(
				"flex min-h-24 flex-col gap-2 p-3",
				!inGroup && "rounded-lg border border-border/8 bg-surface-subtle",
			)}
		>
			{/* Label row, icon on the far left, immediately followed
			    by the card's title. Truncated to a single line so a
			    long label can never wrap and break the card's
			    vertical rhythm. */}
			<div className="flex min-w-0 items-center gap-2">
				<HugeiconsIcon
					icon={icon}
					strokeWidth={1.75}
					className="h-5 w-5 shrink-0 text-muted-foreground"
				/>
				<p className="min-w-0 max-w-full truncate text-xs leading-tight text-muted-foreground">
					{label}
				</p>
			</div>
			<div className="mt-auto flex items-baseline justify-between gap-2">
				{/* `min-w-0 truncate`: a value too wide for the cell
				    ellipsises rather than colliding with the trend. */}
				<p className="min-w-0 truncate text-2xl font-semibold leading-none tracking-tight tabular-nums text-foreground">
					{value}
				</p>
				{trend && <TrendIndicator trend={trend} />}
			</div>
			{sublabel && (
				<p className="truncate text-[11px] text-muted-foreground">{sublabel}</p>
			)}
		</div>
	);
}
