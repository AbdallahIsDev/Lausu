import { memo } from "react";
import { cn } from "@/lib/utils";

export interface RecordingStatusPillProps {
	statusColor: string;
	statusLabel: string;
	isRecording: boolean;
}

export function RecordingStatusPill({
	statusColor,
	statusLabel,
	isRecording,
}: RecordingStatusPillProps) {
	return (
		<div className="flex items-center gap-2 animate-fade-in">
			<span
				className={cn(
					"h-2 w-2 rounded-full transition-colors duration-300",
					isRecording && "animate-pulse",
				)}
				style={{ backgroundColor: statusColor }}
				aria-hidden
			/>
			{/* The label carries the DOT's colour, so the word and the dot
			    always read as one status instead of a coloured dot next to a
			    neutral caption. `style` (not a class) because the colour comes
			    from the status token map, not the theme's text scale. */}
			<span
				key={statusLabel}
				style={{ color: statusColor }}
				className="text-[0.6875rem] font-medium uppercase tracking-wide transition-opacity duration-200 animate-fade-in"
			>
				{statusLabel}
			</span>
		</div>
	);
}

export default memo(RecordingStatusPill);
