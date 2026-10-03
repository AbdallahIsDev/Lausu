import { t } from "@/i18n/i18n";
import { BUBBLE_BUTTON_CLASS, type BubbleMode } from "./constants";

export function BubbleMicButton({
	mode,
	onClick,
}: {
	mode: BubbleMode;
	onClick: () => void;
}) {
	const isRecording = mode === "recording";
	const label = isRecording
		? t("bubble.micButtonStopAria")
		: t("bubble.micButtonStartAria");
	return (
		<button
			type="button"
			onClick={onClick}
			aria-label={label}
			title={label}
			className={BUBBLE_BUTTON_CLASS}
		>
			{/* Always the mic glyph: this button only renders outside
			    recording mode (recording uses the stop button), so the
			    pill never shows two competing actions at once. */}
			<svg
				width="16"
				height="16"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				strokeWidth="2"
				strokeLinecap="round"
				strokeLinejoin="round"
				aria-hidden="true"
			>
				<rect x="9" y="2" width="6" height="12" rx="3" />
				<path d="M5 11a7 7 0 0 0 14 0" />
				<line x1="12" y1="18" x2="12" y2="22" />
			</svg>
		</button>
	);
}
