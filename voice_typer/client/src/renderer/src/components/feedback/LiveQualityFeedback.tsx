interface LiveQualityFeedbackProps {
	isRecording: boolean;
	elapsedSeconds: number;
	totalSeconds: number;
}

// Live test readout: a pulsing red recording dot + the MM:SS / MM:SS
// countdown, right-aligned in the ActiveMicrophoneCard test-controls row.
// The dot alone carries the "capturing now" signal — the same dot the
// bubble's recording indicator uses — so no text label is needed. Renders
// null while no test is running, so the row never grows a second line and
// the buttons stay put.
export function LiveQualityFeedback({
	isRecording,
	elapsedSeconds,
	totalSeconds,
}: LiveQualityFeedbackProps) {
	if (!isRecording) return null;

	const formatTime = (s: number) => {
		const m = Math.floor(s / 60);
		const sec = Math.floor(s % 60);
		return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
	};

	return (
		// `ms-auto` (not `ml-auto`): this readout is always the trailing
		// element of its row, and the logical margin mirrors under RTL.
		<div className="flex items-center gap-2 ms-auto">
			{/* Decorative, the timer text carries the meaning. */}
			<span
				data-slot="microphone-recording-dot"
				className="w-1.5 h-1.5 rounded-full bg-destructive animate-pulse"
				aria-hidden
			/>
			{/* Timer, visual-only; rapid updates would spam SR if live */}
			<span className="text-xs font-mono tabular-nums text-muted-foreground">
				{formatTime(elapsedSeconds)} / {formatTime(totalSeconds)}
			</span>
		</div>
	);
}
