// One model domain as a labeled settings row. Provider and model are separate,
// visibly named fields; the switch and the consent gate keep their own state.

import { Mic01Icon, SparklesIcon, TextIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { Switch } from "@/components/ui/switch";
import { useT } from "@/i18n/i18n";
import type {
	Domain,
	DomainSelection,
	ProviderEntry,
	ProviderModel,
} from "../lib/types";
import { DomainConsent, DomainNotes, DomainSelects } from "./DomainControls";

const DOMAIN_ICONS = {
	asr: Mic01Icon,
	tts: TextIcon,
	llm: SparklesIcon,
} as const;

const DOMAIN_DESCRIPTIONS = {
	asr: "providers.domainAsrDesc",
	tts: "providers.domainTtsDesc",
	llm: "providers.domainLlmDesc",
} as const;

interface DomainCardProps {
	domain: Domain;
	label: string;
	selection?: DomainSelection;
	providers: ProviderEntry[];
	models: ProviderModel[];
	/** Empty when nothing is configured — the select shows its placeholder. */
	activeProvider: string;
	busy: boolean;
	usesCredits: boolean;
	showConsent: boolean;
	onnxNote: string | null;
	onEnabledChange: (enabled: boolean) => void;
	onProviderChange: (provider: string) => void;
	onModelChange: (model: string) => void;
	onConsentChange: (consent: boolean) => void;
}

export function DomainCard({
	domain,
	label,
	selection,
	providers,
	models,
	activeProvider,
	busy,
	usesCredits,
	showConsent,
	onnxNote,
	onEnabledChange,
	onProviderChange,
	onModelChange,
	onConsentChange,
}: DomainCardProps) {
	const t = useT();

	return (
		<div className="flex flex-col gap-4 px-4 py-4">
			<div className="flex items-center gap-3">
				<span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-border/5 text-muted-foreground">
					<HugeiconsIcon
						icon={DOMAIN_ICONS[domain]}
						strokeWidth={1.6}
						aria-hidden="true"
						className="size-4"
					/>
				</span>
				<div className="flex min-w-0 flex-1 flex-col gap-0.5">
					<h3 className="text-sm font-semibold text-foreground">{label}</h3>
					<p className="text-xs text-muted-foreground">
						{t(DOMAIN_DESCRIPTIONS[domain])}
					</p>
				</div>
				{/* Dictation is the core path; never offer a switch that turns it off. */}
				{domain === "asr" ? null : (
					<Switch
						checked={Boolean(selection?.enabled)}
						aria-label={label}
						onCheckedChange={onEnabledChange}
					/>
				)}
			</div>

			<DomainSelects
				className="sm:ps-12"
				providers={providers}
				models={models}
				activeProvider={activeProvider}
				modelId={selection?.model_id ?? ""}
				busy={busy}
				onProviderChange={onProviderChange}
				onModelChange={onModelChange}
			/>

			{showConsent ? (
				<DomainConsent
					className="sm:ps-12"
					consent={Boolean(selection?.consent)}
					onConsentChange={onConsentChange}
				/>
			) : null}

			<DomainNotes
				className="sm:ps-12"
				usesCredits={usesCredits}
				onnxNote={onnxNote}
			/>
		</div>
	);
}
