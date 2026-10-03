import { useEffect, useState } from "react";
import { tf } from "./helpers";

function formatElapsed(totalSeconds: number): string {
	const mins = Math.floor(totalSeconds / 60);
	const secs = totalSeconds % 60;
	return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function RecordingTimer() {
	const [elapsed, setElapsed] = useState(0);

	useEffect(() => {
		const startedAt = Date.now();
		const tick = () => {
			setElapsed(Math.floor((Date.now() - startedAt) / 1000));
		};
		const id = setInterval(tick, 500);
		return () => clearInterval(id);
	}, []);

	return (
		<span
			role="timer"
			data-slot="bubble-recording-timer"
			aria-label={tf("bubble.recordingTimerAria", "Recording duration")}
			className="text-[0.625rem] font-medium tabular-nums text-muted-foreground"
		>
			{formatElapsed(elapsed)}
		</span>
	);
}
