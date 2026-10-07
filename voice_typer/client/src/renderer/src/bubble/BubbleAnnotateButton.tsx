import { Camera01Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { BUBBLE_BUTTON_CLASS } from "./constants";
import { tf } from "./helpers";

export function BubbleAnnotateButton({
	onClick,
	captured,
}: {
	onClick: () => void;
	captured: boolean;
}) {
	const label = tf("bubble.annotateAria", "Capture a screenshot region");
	return (
		<button
			type="button"
			onClick={onClick}
			aria-label={label}
			title={label}
			disabled={captured}
			className={`${BUBBLE_BUTTON_CLASS} relative`}
		>
			<HugeiconsIcon icon={Camera01Icon} size={14} strokeWidth={2} />
			{captured && (
				<span
					aria-hidden
					className="absolute -end-0.5 -top-0.5 rounded-full bg-primary px-1 text-[9px] font-semibold leading-3 text-primary-foreground"
				>
					1/1
				</span>
			)}
		</button>
	);
}
