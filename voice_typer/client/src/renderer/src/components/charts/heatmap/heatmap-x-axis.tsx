"use client";

import { memo, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { useHeatmap } from "./heatmap-context";
import { buildHeatmapMonthTicks } from "./heatmap-utils";

export interface HeatmapXAxisProps {
	/** Additional class name for labels */
	className?: string;
	/**
	 * Month labels indexed by `Date.getMonth()` (0 = January). The default
	 * is English; pass a localised array so a full-year grid does not
	 * render ~13 English month names inside a translated card.
	 */
	monthLabels?: readonly string[];
}

export const HeatmapXAxis = memo(function HeatmapXAxis({
	className,
	monthLabels,
}: HeatmapXAxisProps) {
	const { containerRef, data, margin, xScale } = useHeatmap();
	const [mounted, setMounted] = useState(false);

	useEffect(() => {
		setMounted(true);
	}, []);

	const labels = useMemo(
		() =>
			buildHeatmapMonthTicks(data, monthLabels).map((tick) => ({
				...tick,
				x: margin.left + xScale(tick.columnIndex),
			})),
		[data, margin.left, monthLabels, xScale],
	);

	const container = containerRef.current;
	if (!(mounted && container)) {
		return null;
	}

	const lastIndex = labels.length - 1;

	return createPortal(
		labels.map((tick, index) => {
			// The LAST label is anchored to the container's right edge
			// rather than to its column's left edge. A month label is wider
			// than the column it names, so the final one hangs past the
			// plot, and how far depends on the calendar: the last month
			// tick sits on whichever column that month began, which can be
			// the very last column or four columns earlier. Anchoring it
			// right keeps it inside the card in every case, and since it
			// can only ever move right, it cannot collide with the label
			// four columns before it. Every other label keeps its column
			// anchor, so the axis still reads as month boundaries.
			const isLast = index === lastIndex;

			return (
				<div
					className="pointer-events-none absolute"
					key={tick.key}
					style={{
						top: 0,
						...(isLast ? { right: 0 } : { left: tick.x, width: 0 }),
						display: "flex",
						justifyContent: isLast ? "flex-end" : "flex-start",
					}}
				>
					<span
						className={cn(
							"whitespace-nowrap text-chart-label text-xs",
							className,
						)}
					>
						{tick.label}
					</span>
				</div>
			);
		}),
		container,
	);
});

HeatmapXAxis.displayName = "HeatmapXAxis";

export default HeatmapXAxis;
