// BubblePreview, the live bubble mock rendered by the Overlay settings
// page. It is NOT a setting: it lives in its own "Bubble Preview" card
// (see OverlaySettingsSection) so it can never be read as another row
// of the Overlay card's control list.
//
// Every prop mirrors one bubble config key, so what you see is what the
// real overlay renders:
//
//   timerOn    ← bubble_show_recording_timer  (timer inside the pill)
//   micOn      ← bubble_mic_button + bubble_click_to_toggle + behavior
//                (the mic button only exists on the idle pill)
//   dismissOn  ← bubble_behavior === "always_visible" (the × only ever
//                renders on the always-visible bubble)
//   position   ← bubble_position (which screen edge the pill is pinned to)
//
// Spacing note (the two-column rhythm this component is built around):
// a row is as tall as its pill, so the rows' vertical pitch sets BOTH
// the pill-to-pill gap and the label-to-label gap; they cannot be tuned
// independently (label gap = pitch − label height, pill gap = pitch −
// pill height). Numbers after this edit: pill 38px (py-1.5), label line
// box 24px (leading-6), gap-3.5 (14px) → pills 14px apart (was 8px) and
// labels 28px apart (was 34px). Both complaints are answered by moving
// the pitch DOWN (compact pill) and the gap UP, in the same edit.

import { memo, useRef } from "react";
import { BubbleDismissButton } from "@/bubble/BubbleDismissButton";
import { BubbleMicButton } from "@/bubble/BubbleMicButton";
import { BubbleModeContent } from "@/bubble/BubbleModeContent";
import { BubbleStopButton } from "@/bubble/BubbleStopButton";
import { useT } from "@/i18n/i18n";

// Same frame as the real pill (Bubble.tsx) with tighter vertical
// padding: the overlay pill is `py-2.5` because it floats alone over
// the desktop, the preview is `py-1.5` so three of them stack without
// crowding each other. Horizontal padding, radius, border and palette
// are unchanged, so it still reads as the real thing.
const PREVIEW_PILL_CLASS =
	"pointer-events-none inline-flex items-center gap-3 rounded-full border border-border/8 bg-surface px-4 py-1.5 text-foreground";

// State labels are a fixed 24px line box (`leading-6`) so the distance
// between two labels is measured from a 24px block instead of a 16px
// one, which is what pulls the label column tighter.
const PREVIEW_LABEL_CLASS =
	"w-24 shrink-0 text-sm leading-6 text-muted-foreground";

function noop() {}

/**
 * A hairline standing in for the screen edge the bubble is pinned to,
 * so `bubble_position` shows up in the preview and not only in the row
 * above it. Decorative; the sr-only text carries the meaning.
 */
function ScreenEdge({ label }: { label: string }) {
	return (
		<div className="flex items-center gap-2">
			<span className="h-px flex-1 bg-border/10" aria-hidden />
			<span className="h-1 w-20 rounded-full bg-border/15" aria-hidden />
			<span className="h-px flex-1 bg-border/10" aria-hidden />
			<span className="sr-only">{label}</span>
		</div>
	);
}

export interface BubblePreviewProps {
	/** Mirror of `bubble_show_recording_timer`. */
	timerOn: boolean;
	/** Mirror of the mic button actually reaching the idle pill. */
	micOn: boolean;
	/** Mirror of `bubble_behavior === "always_visible"`. */
	dismissOn: boolean;
	/** Mirror of `bubble_position`. */
	position: "top" | "bottom";
}

export const BubblePreview = memo(function BubblePreview({
	timerOn,
	micOn,
	dismissOn,
	position,
}: BubblePreviewProps) {
	const t = useT();
	const dotRefs = useRef<(HTMLSpanElement | null)[]>([]);
	const pills = (
		<div className="flex flex-col gap-3.5">
			<div className="flex items-center justify-between gap-3">
				<span className={PREVIEW_LABEL_CLASS}>
					{t("settings.bubblePreviewIdle")}
				</span>
				<div className={PREVIEW_PILL_CLASS} aria-hidden>
					<BubbleModeContent mode="idle" showTimer={false} dotRefs={dotRefs} />
					{micOn && <BubbleMicButton mode="idle" onClick={noop} />}
				</div>
			</div>
			<div className="flex items-center justify-between gap-3">
				<span className={PREVIEW_LABEL_CLASS}>
					{t("settings.bubblePreviewRecording")}
				</span>
				<div className={PREVIEW_PILL_CLASS} aria-hidden>
					<BubbleModeContent
						mode="recording"
						showTimer={timerOn}
						dotRefs={dotRefs}
					/>
					<BubbleStopButton onClick={noop} mode="recording" />
				</div>
			</div>
			<div className="flex items-center justify-between gap-3">
				<span className={PREVIEW_LABEL_CLASS}>
					{t("settings.bubblePreviewTranscribing")}
				</span>
				<div className={PREVIEW_PILL_CLASS} aria-hidden>
					<BubbleModeContent
						mode="transcribing"
						showTimer={false}
						dotRefs={dotRefs}
					/>
					{dismissOn && <BubbleDismissButton onClick={noop} />}
				</div>
			</div>
		</div>
	);

	return (
		<div className="flex flex-col gap-3 px-4 py-4">
			{position === "top" && (
				<ScreenEdge
					label={`${t("settings.bubblePositionLabel")}: ${t(
						"settings.bubblePositionTop",
					)}`}
				/>
			)}
			{pills}
			{position === "bottom" && (
				<ScreenEdge
					label={`${t("settings.bubblePositionLabel")}: ${t(
						"settings.bubblePositionBottom",
					)}`}
				/>
			)}
		</div>
	);
});
