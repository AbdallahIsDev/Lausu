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

	return createPortal(
		labels.map((tick) => (
			<div
				className="pointer-events-none absolute"
				key={tick.key}
				style={{
					top: 0,
					left: tick.x,
					width: 0,
					display: "flex",
					justifyContent: "flex-start",
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
		)),
		container,
	);
});

HeatmapXAxis.displayName = "HeatmapXAxis";

export default HeatmapXAxis;
