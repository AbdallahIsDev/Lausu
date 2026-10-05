import {
	CloudIcon,
	FlaskConicalIcon,
	Globe02Icon,
	TextFontIcon,
	ZapIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react";
import {
	Tooltip,
	TooltipContent,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import { t } from "@/i18n/i18n";
import { cn, focusRing } from "@/lib/utils";
import { formatModelSpeed } from "@/lib/utils/models";

// ── Metadata icon chips ────────────────────────────────────────────────
// Language scope (globe = multilingual, "Aa" = English-only), speed
// rating (zap), distilled (flask) and cloud-hosted (cloud) render as
// compact icon-only chips: the chip carries no visible text, its meaning
// lives in the hover/focus tooltip and in the button's accessible name.
// A real <button> trigger (not a span) so keyboard users can Tab to the
// chip and read the same tooltip a mouse user gets on hover.

function MetadataIconChip({
	icon,
	label,
	testId,
}: {
	icon: IconSvgElement;
	label: string;
	testId: string;
}) {
	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<button
					type="button"
					aria-label={label}
					data-testid={testId}
					className={cn(
						"inline-flex size-5 shrink-0 cursor-help items-center justify-center rounded-full border border-border/8 bg-foreground/5 p-0 text-muted-foreground",
						focusRing,
					)}
				>
					<HugeiconsIcon
						icon={icon}
						strokeWidth={2}
						className="h-3.5 w-3.5"
						aria-hidden="true"
					/>
				</button>
			</TooltipTrigger>
			<TooltipContent side="top" align="center" className="max-w-64">
				{label}
			</TooltipContent>
		</Tooltip>
	);
}

/** Globe for multilingual models, "Aa" text glyph for English-only ones. */
export function LanguageScopeTag({ multilingual }: { multilingual: boolean }) {
	return (
		<MetadataIconChip
			icon={multilingual ? Globe02Icon : TextFontIcon}
			label={t(
				multilingual ? "models.card.multilingual" : "models.card.englishOnly",
			)}
			testId={`meta-icon-language-${multilingual ? "multilingual" : "english-only"}`}
		/>
	);
}

/** Zap: transcription speed rating ("Fast Speed" / "Slow Speed" / …). */
export function SpeedTag({ rating }: { rating: string }) {
	const text = t("models.card.speedSuffix", {
		rating: formatModelSpeed(rating),
	}).trim();
	return (
		<MetadataIconChip icon={ZapIcon} label={text} testId="meta-icon-speed" />
	);
}

/** Flask: distilled variants. */
export function DistilledTag() {
	return (
		<MetadataIconChip
			icon={FlaskConicalIcon}
			label={t("models.card.distilled")}
			testId="meta-icon-distilled"
		/>
	);
}

/** Cloud: the model is transcribed by a hosted provider, not locally. */
export function CloudTag() {
	return (
		<MetadataIconChip
			icon={CloudIcon}
			label={t("models.cloud.tagCloud")}
			testId="meta-icon-cloud"
		/>
	);
}
