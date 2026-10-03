import { type RefObject, useMemo } from "react";
import { DOT_COUNT, DOT_INDICES, MIN_HEIGHT } from "./constants";
import { RecordingTimer } from "./RecordingTimer";

export function BubbleVisualizer({
	dotRefs,
	showTimer,
}: {
	dotRefs: RefObject<(HTMLSpanElement | null)[]>;
	showTimer: boolean;
}) {
	// Build the 7 stable ref setters once per `dotRefs` instance.
	// The array identity is stable across renders (only changes if
	// `dotRefs` changes, which it doesn't in practice), so React's
	// reconciler sees the same ref callback on every render and skips
	// the detach/attach cycle.
	const refSetters = useMemo(
		() =>
			Array.from(
				{ length: DOT_COUNT },
				(_, i) => (el: HTMLSpanElement | null) => {
					dotRefs.current[i] = el;
				},
			),
		[dotRefs],
	);
	return (
		<div className="flex h-6 items-center gap-2">
			{/* The recording indicator is the dot alone, no text label. Red +
			    pulsing means "capturing audio right now"; this component is
			    only rendered in the recording mode (see BubbleModeContent),
			    so the red pulse can never appear while nothing is recording. */}
			<span
				data-slot="bubble-recording-dot"
				className="w-1.5 h-1.5 rounded-full bg-destructive animate-pulse"
				aria-hidden
			/>
			{showTimer && <RecordingTimer />}
			{/* `ms-1` is the RTL-safe logical replacement for the old
		    physical `ml-1`. In LTR it renders as margin-left; in RTL
		    (ar locale) it flips to margin-right automatically. */}
			<div className="flex h-6 items-center gap-0.75 ms-1" aria-hidden>
				{DOT_INDICES.map((i) => (
					<span
						key={i}
						ref={refSetters[i]}
						className="inline-block w-0.75 rounded-full bg-foreground"
						style={{ height: MIN_HEIGHT, opacity: 0.3 }}
					/>
				))}
			</div>
		</div>
	);
}
