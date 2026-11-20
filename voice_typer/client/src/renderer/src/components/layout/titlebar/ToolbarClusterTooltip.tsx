import type { ReactNode } from "react";
import { useState } from "react";
import { HotkeyChips } from "@/components/hotkey/HotkeyChips";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";

/** One toolbar button the cluster can label. */
export interface ToolbarClusterEntry {
	id: string;
	label: string;
	keys?: string;
}

/** Hover/focus handlers a cluster member spreads onto its button. */
export type ClusterMemberProps = {
	onMouseEnter: () => void;
	onFocus: () => void;
	onBlur: () => void;
};

interface ToolbarClusterTooltipProps {
	entries: readonly ToolbarClusterEntry[];
	/** Receives the per-entry handler factory. */
	children: (bind: (id: string) => ClusterMemberProps) => ReactNode;
	className?: string;
}

/**
 * ONE tooltip for the whole title-bar button row.
 *
 * Per-button tooltips swap by closing the old Root and opening a new one, so
 * crossing from one button to the next flashed a closed tooltip and could
 * leave the PREVIOUS label behind (owner report 2026-11-18). Here every button
 * feeds the same Root: the content stays mounted while the pointer moves
 * inside the row, only its text changes, and it disappears when the pointer
 * leaves the row.
 *
 * The content anchors to the row rather than to a single button, which also
 * keeps it off the window's leading edge (per-button centering pushed the first
 * button's tooltip past the edge, where Radix had to shift it back).
 */
export function ToolbarClusterTooltip({
	entries,
	children,
	className,
}: ToolbarClusterTooltipProps) {
	const [activeId, setActiveId] = useState<string | null>(null);
	const active = entries.find((entry) => entry.id === activeId) ?? null;

	// Only ENTER is per-button: a per-button leave fires on the way to the next
	// member and unmounts the content we are keeping alive. The row's own
	// mouseleave clears it.
	const bind = (id: string): ClusterMemberProps => ({
		onMouseEnter: () => setActiveId(id),
		onFocus: () => setActiveId(id),
		onBlur: () => setActiveId((current) => (current === id ? null : current)),
	});

	return (
		<Tooltip open={active !== null}>
			<TooltipTrigger asChild>
				<div className={className} onMouseLeave={() => setActiveId(null)}>
					{children(bind)}
				</div>
			</TooltipTrigger>
			{active && (
				<TooltipContent
					side="bottom"
					align="start"
					sideOffset={6}
					collisionPadding={8}
				>
					<span className="flex items-center gap-2 whitespace-nowrap">
						<span>{active.label}</span>
						{active.keys !== undefined && <HotkeyChips keys={active.keys} />}
					</span>
				</TooltipContent>
			)}
		</Tooltip>
	);
}
