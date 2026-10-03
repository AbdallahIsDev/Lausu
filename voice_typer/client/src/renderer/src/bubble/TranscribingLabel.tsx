import { t } from "@/i18n/i18n";
import { TRANSCRIBING_DOT_COUNT } from "./constants";

const DOT_INDICES: readonly number[] = Array.from(
	{ length: TRANSCRIBING_DOT_COUNT },
	(_, i) => i,
);

export function TranscribingLabel() {
	const label = t("bubble.transcribingLabel");
	return (
		<span className="inline-flex items-center gap-1">
			<span
				className="bubble-shimmer-text text-xs font-medium"
				data-text={label}
			>
				{label}
			</span>
			<span className="inline-flex items-center gap-0.5" aria-hidden>
				{DOT_INDICES.map((i) => (
					<span
						key={i}
						className="bubble-blink-dot inline-block h-1 w-1 rounded-full bg-muted-foreground"
						style={{ animationDelay: `${i * 0.25}s` }}
					/>
				))}
			</span>
		</span>
	);
}
