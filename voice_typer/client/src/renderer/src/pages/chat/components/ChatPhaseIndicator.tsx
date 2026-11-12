import { cn } from "@/lib/utils";
import type { ChatPhase } from "../hooks/useChatConversation";

interface ChatPhaseIndicatorProps {
	phase: ChatPhase;
	label: string;
}

/**
 * The turn's phase, always rendered (idle included) so starting a turn never
 * displaces the button below it (C-UI-5).
 *
 * A quiet status pill: the dot carries the state, the label carries the words.
 * No pulsing — a remote model can take several seconds, but a looping animation
 * would make the whole control area compete with the transcript.
 */
export function ChatPhaseIndicator({ phase, label }: ChatPhaseIndicatorProps) {
	const active =
		phase === "listening" ||
		phase === "transcribing" ||
		phase === "thinking" ||
		phase === "speaking";

	return (
		<div
			className="inline-flex items-center gap-2 rounded-full border border-border/8 bg-border/5 px-3 py-1.5"
			role="status"
			aria-live="polite"
			data-phase={phase}
		>
			<span
				aria-hidden="true"
				className={cn(
					"size-1.5 shrink-0 rounded-full",
					phase === "error" || phase === "listening"
						? "bg-destructive"
						: active
							? "bg-primary"
							: "bg-muted-foreground/40",
				)}
			/>
			<span className="text-xs text-muted-foreground">{label}</span>
		</div>
	);
}
