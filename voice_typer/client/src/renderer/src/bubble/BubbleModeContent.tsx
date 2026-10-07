import type { RefObject } from "react";
import { t } from "@/i18n/i18n";
import { BubbleAnnotateButton } from "./BubbleAnnotateButton";
import { BubbleVisualizer } from "./BubbleVisualizer";
import type { BubbleMode } from "./constants";
import { FADEOUT_DURATION_MS } from "./constants";
import { tf } from "./helpers";
import { TranscribingLabel } from "./TranscribingLabel";

const TRANSCRIPT_PREVIEW_MAX_CHARS = 60;

function truncateTranscript(text: string): string {
	if (text.length <= TRANSCRIPT_PREVIEW_MAX_CHARS) return text;
	// Reserve 1 character for the ellipsis.
	return `${text.slice(0, TRANSCRIPT_PREVIEW_MAX_CHARS - 1)}…`;
}

export interface BubbleModeContentProps {
	mode: BubbleMode;
	transcript?: string | null;
	showTimer: boolean;
	dotRefs: RefObject<(HTMLSpanElement | null)[]>;
	// One-shot screenshot beta: the annotate button renders ONLY in
	// the recording case while the beta flag is on. Absent by
	// default, so the beta-off pill is unchanged.
	annotateEnabled?: boolean;
	annotateCaptured?: boolean;
	onAnnotate?: () => void;
}

export function BubbleModeContent({
	mode,
	transcript,
	showTimer,
	dotRefs,
	annotateEnabled,
	annotateCaptured,
	onAnnotate,
}: BubbleModeContentProps) {
	switch (mode) {
		case "transcribing": {
			const preview =
				typeof transcript === "string" && transcript.length > 0
					? truncateTranscript(transcript)
					: null;
			return (
				<div className="flex items-center gap-2 text-xs font-medium text-(--text-secondary)">
					<TranscribingLabel />
					{preview && (
						<output
							// `<output>` is the semantic element for
							// role="status" (implicit). It supports
							// `aria-label` and is a polite live region so
							// screen-reader users hear each partial update;
							// the parent `<output aria-live="polite">`
							// re-announces the whole pill content on mode
							// change, so this inner region is the one that
							// fires on every partial-transcript tick without
							// re-announcing the "Transcribing" label.
							aria-label={tf(
								"bubble.transcriptPreviewAria",
								"Live transcript preview",
							)}
							className="max-w-45 truncate text-muted-foreground"
						>
							{preview}
						</output>
					)}
				</div>
			);
		}
		case "fading": {
			const preview =
				typeof transcript === "string" && transcript.length > 0
					? truncateTranscript(transcript)
					: null;
			return (
				<div
					className="flex items-center gap-2 text-xs font-medium text-(--text-secondary)"
					style={{
						opacity: 0,
						transform: "translateY(-4px)",
						transition: `opacity ${FADEOUT_DURATION_MS}ms ease-out, transform ${FADEOUT_DURATION_MS}ms ease-out`,
					}}
				>
					<span>{t("bubble.transcribingLabel")}</span>
					{preview && (
						<output
							aria-label={tf(
								"bubble.transcriptPreviewAria",
								"Live transcript preview",
							)}
							className="max-w-45 truncate text-muted-foreground"
						>
							{preview}
						</output>
					)}
				</div>
			);
		}
		case "idle":
			return (
				<>
					<div className="flex h-6 items-center" aria-hidden>
						<span className="text-xs font-medium text-muted-foreground">
							{tf("bubble.idleLabel", "Ready")}
						</span>
					</div>
					<span className="sr-only">{t("a11y.transcriptionComplete")}</span>
				</>
			);
		case "error":
			// Surface a red "⚠ Error" label so the user can see
			// something went wrong (e.g. backend crash, mic
			// permission revoked). Uses the destructive token so
			// it inherits theme-preset colors. The pill stays a
			// fixed short label, the backend reason is not shown.
			return (
				<div className="flex h-6 items-center gap-2 px-2">
					<span
						className="w-1.5 h-1.5 rounded-full bg-destructive animate-pulse"
						aria-hidden
					/>
					<span className="text-[0.625rem] font-medium text-destructive">
						{tf("bubble.errorLabel", "⚠ Error")}
					</span>
				</div>
			);
		case "blocked":
			return (
				<div className="flex h-6 items-center gap-2 px-2">
					<span
						className="text-[0.6875rem] leading-none text-muted-foreground"
						aria-hidden
					>
						⊘
					</span>
					<span className="text-[0.625rem] font-medium text-muted-foreground">
						{tf("bubble.blockedLabel", "Blocked")}
					</span>
				</div>
			);
		case "cancelling":
			return (
				<div className="flex h-6 items-center gap-2 px-2">
					<span className="text-[0.625rem] font-medium text-muted-foreground">
						{tf("bubble.cancellingLabel", "Cancelling…")}
					</span>
				</div>
			);
		case "permission_revoked":
			return (
				<div className="flex h-6 items-center gap-2 px-2">
					<span
						className="w-1.5 h-1.5 rounded-full bg-destructive animate-pulse"
						aria-hidden
					/>
					<span className="text-[0.625rem] font-medium text-destructive">
						{tf("bubble.permissionRevokedLabel", "Mic permission revoked")}
					</span>
				</div>
			);
		case "paste_failed":
			return (
				<div className="flex h-6 items-center gap-2 px-2">
					<span
						className="w-1.5 h-1.5 rounded-full bg-destructive animate-pulse"
						aria-hidden
					/>
					<span className="text-[0.625rem] font-medium text-destructive">
						{tf("bubble.pasteFailedLabel", "Paste failed")}
					</span>
				</div>
			);
		case "recording":
			// Recording shows the pulsing dot + level bars only. A
			// "no live preview" notice used to sit here for engines
			// without word streaming; it widened the always-on-top
			// pill and wrapped to two lines. The bars already say
			// "listening".
			return (
				<div className="flex items-center gap-2">
					<BubbleVisualizer dotRefs={dotRefs} showTimer={showTimer} />
					{annotateEnabled && onAnnotate && (
						<BubbleAnnotateButton
							onClick={onAnnotate}
							captured={annotateCaptured === true}
						/>
					)}
				</div>
			);
		default: {
			// Exhaustiveness guard: every BubbleMode has its own branch
			// above, so this is unreachable today. If a mode is ever added
			// without a branch the compiler fails HERE, instead of the pill
			// falling through and showing the recording indicator while
			// nothing is recording.
			const unhandled: never = mode;
			void unhandled;
			return null;
		}
	}
}
