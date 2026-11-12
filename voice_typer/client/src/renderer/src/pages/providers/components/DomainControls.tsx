// Field groups for one model domain: provider + model selects, the consent
// checkbox and the credits/ONNX notes. Extracted so every layout renders the
// same labelled controls (and the same accessible names) in its own frame.

import { InformationCircleIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useId } from "react";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { useT } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import type { ProviderEntry, ProviderModel } from "../lib/types";

export function DomainSelects({
	providers,
	models,
	activeProvider,
	modelId,
	busy,
	className,
	onProviderChange,
	onModelChange,
}: {
	providers: ProviderEntry[];
	models: ProviderModel[];
	activeProvider: string;
	modelId: string;
	busy: boolean;
	className?: string;
	onProviderChange: (provider: string) => void;
	onModelChange: (modelId: string) => void;
}) {
	const t = useT();
	const providerLabelId = useId();
	const modelLabelId = useId();
	return (
		<div className={cn("grid gap-4 sm:grid-cols-2", className)}>
			<div className="flex flex-col gap-1.5">
				<span
					id={providerLabelId}
					className="text-xs-plus font-medium text-muted-foreground"
				>
					{t("providers.provider")}
				</span>
				<Select
					value={activeProvider}
					disabled={busy}
					onValueChange={onProviderChange}
				>
					<SelectTrigger className="w-full" aria-labelledby={providerLabelId}>
						<SelectValue placeholder={t("providers.provider")} />
					</SelectTrigger>
					<SelectContent>
						{providers.map((provider) => (
							<SelectItem key={provider.id} value={provider.id}>
								{provider.label}
							</SelectItem>
						))}
					</SelectContent>
				</Select>
			</div>

			<div className="flex flex-col gap-1.5">
				<span
					id={modelLabelId}
					className="text-xs-plus font-medium text-muted-foreground"
				>
					{t("providers.model")}
				</span>
				<Select value={modelId} disabled={busy} onValueChange={onModelChange}>
					<SelectTrigger className="w-full" aria-labelledby={modelLabelId}>
						<SelectValue placeholder={t("providers.model")} />
					</SelectTrigger>
					<SelectContent>
						{models.length === 0 ? (
							<SelectItem value="__none" disabled>
								{t("providers.noModels")}
							</SelectItem>
						) : (
							models.map((model) => (
								<SelectItem key={model.id} value={model.id}>
									{model.label}
									{model.context_length
										? ` · ${t("providers.contextTokens", { count: String(model.context_length) })}`
										: ""}
									{" · "}
									{model.free ? t("providers.free") : t("providers.paid")}
								</SelectItem>
							))
						)}
					</SelectContent>
				</Select>
			</div>
		</div>
	);
}

export function DomainConsent({
	consent,
	className,
	onConsentChange,
}: {
	consent: boolean;
	className?: string;
	onConsentChange: (consent: boolean) => void;
}) {
	const t = useT();
	const consentId = useId();
	const consentLabelId = useId();
	return (
		<div className={cn("flex items-center gap-2.5", className)}>
			<Checkbox
				id={consentId}
				aria-labelledby={consentLabelId}
				checked={consent}
				onCheckedChange={(checked) => onConsentChange(checked === true)}
			/>
			<label
				id={consentLabelId}
				htmlFor={consentId}
				className="cursor-pointer text-xs text-muted-foreground"
			>
				{t("providers.consent")}
			</label>
		</div>
	);
}

export function DomainNotes({
	usesCredits,
	onnxNote,
	className,
}: {
	usesCredits: boolean;
	onnxNote: string | null;
	className?: string;
}) {
	const t = useT();
	if (!usesCredits && !onnxNote) return null;
	return (
		<div className={cn("flex flex-col gap-1.5", className)}>
			{usesCredits ? (
				<p className="flex items-center gap-1.5 text-xs text-muted-foreground">
					<HugeiconsIcon
						icon={InformationCircleIcon}
						strokeWidth={1.8}
						aria-hidden="true"
						className="size-3.5 shrink-0"
					/>
					{t("providers.credits")}
				</p>
			) : null}
			{onnxNote ? (
				<p
					role="status"
					className="flex items-center gap-1.5 text-xs text-muted-foreground"
				>
					<HugeiconsIcon
						icon={InformationCircleIcon}
						strokeWidth={1.8}
						aria-hidden="true"
						className="size-3.5 shrink-0"
					/>
					{onnxNote}
				</p>
			) : null}
		</div>
	);
}
