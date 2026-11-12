import { ChevronDownIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { type Ref, useState } from "react";
import { FamilyLogo } from "@/components/models/FamilyLogo";
import {
	DOWNLOAD_CONTENT_ALIGNMENT,
	DOWNLOAD_SIZE_BUTTON_WIDTH,
} from "@/components/models/ModelCardActions";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
	ToggleGroup,
	type ToggleGroupOption,
} from "@/components/ui/toggle-group";
import { t } from "@/i18n/i18n";
import { formatVram } from "@/lib/format";
import { formatModelSpeed } from "@/lib/utils/models";
import type { BackendChoice } from "../hooks/useOnboardingWizard";
import { HEADING_CLASS } from "../lib/constants";
import type { ModelOption } from "../lib/types";

// Family grouping for the onboarding accordion, mirrors the Models
// page family headers: whisper → OpenAI, parakeet → NVIDIA, qwen →
// Qwen. Backend-driven (``ModelOption.backend``) so the two Qwen sizes
// need no per-name entry; the wizard already falls back to "whisper"
// for older backends that omit the field.
function familyForModel(option: ModelOption): string {
	if (option.backend === "qwen") return "qwen";
	if (option.backend === "parakeet") return "parakeet";
	return "whisper";
}

// Family display labels — brand names (proper nouns, kept literal like
// the Models page family headers). No "Powered by …" strip: the
// wizard is multi-provider and the family headers already carry the
// brand logos (2026-09-14 Model-step rebuild).
const FAMILY_LABELS: Record<string, string> = {
	whisper: "OpenAI",
	qwen: "Qwen",
	parakeet: "NVIDIA",
};

export interface ModelStepProps {
	headingRef: Ref<HTMLHeadingElement>;
	modelOptions: ModelOption[];
	selectedModel: string;
	setSelectedModel: (v: string) => void;
	// Local-vs-cloud choice (Model step). The app NEVER auto-downloads a
	// model, the user either picks a local model and downloads it
	// explicitly per item, or connects a cloud transcription API.
	selectedBackend: BackendChoice;
	setSelectedBackend: (v: BackendChoice) => void;
	// Explicit per-model download state + handler. HuggingFace consent
	// is requested at the point of use through the shared consent gate
	// (openConsentGate), NOT a checkbox on this step (the consent is
	// granted on the Privacy step / gate dialog; the wizard never
	// duplicates it).
	downloadingModel: string | null;
	downloadProgress: number;
	downloadFailed: boolean;
	onDownload: (model: string) => void;
	// Cloud branch: provider + API key (persisted on Continue). The
	// provider's audio-transmission CONSENT is deliberately not a checkbox
	// here — leaving the step opens the shared consent gate for the chosen
	// provider, the same dialog the Models page shows on activation, so the
	// user reads what the choice authorises at the moment it takes effect.
	cloudProvider: string;
	setCloudProvider: (v: string) => void;
	cloudApiKey: string;
	setCloudApiKey: (v: string) => void;
}

const CLOUD_PROVIDERS = ["openai", "groq", "deepgram", "gemini"] as const;

function providerLabel(provider: string): string {
	if (provider === "openai") return t("models.providers.openai.label");
	if (provider === "groq") return t("models.providers.groq.label");
	if (provider === "gemini") return t("models.providers.gemini.label");
	return t("models.providers.deepgram.label");
}

function languageBadgeKey(
	languages: string[] | null | undefined,
): string | null {
	if (languages === undefined) return null;
	if (languages === null) return "onboarding.multilingualBadge";
	if (languages.length === 0) return "onboarding.multilingualBadge";
	const onlyEnglish = languages.every((l) => l.toLowerCase() === "en");
	return onlyEnglish
		? "onboarding.englishOnlyBadge"
		: "onboarding.multilingualBadge";
}

function displayNameFor(model: ModelOption): string {
	return model.display_name && model.display_name.length > 0
		? model.display_name
		: model.name;
}

/** Small info chip used for the VRAM / language badges on a model row. */
function ModelBadge({ children }: { children: string }) {
	return (
		<span className="rounded-full bg-surface-subtle px-1.5 py-0.5 text-[0.625rem] font-medium uppercase tracking-wide text-muted-foreground">
			{children}
		</span>
	);
}

export function ModelStep({
	headingRef,
	modelOptions,
	selectedModel,
	setSelectedModel,
	selectedBackend,
	setSelectedBackend,
	downloadingModel,
	downloadProgress,
	downloadFailed,
	onDownload,
	cloudProvider,
	setCloudProvider,
	cloudApiKey,
	setCloudApiKey,
}: ModelStepProps) {
	const isDownloading = downloadingModel !== null;
	const progressPct = Math.round(downloadProgress);
	const [allModelsOpen, setAllModelsOpen] = useState(false);

	// Single recommended model (backend ``recommended: true``, exactly
	// one entry). The recommended card satisfies the step's
	// one-model gate on its own; the rest stays behind All Models.
	const recommended = modelOptions.find((m) => m.recommended === true) ?? null;
	const restOptions = recommended
		? modelOptions.filter((m) => m.name !== recommended.name)
		: modelOptions;

	// Group the offered local models by family for the accordion.
	// Families appear in first-seen order (whisper, qwen, parakeet).
	const families: { id: string; models: ModelOption[] }[] = [];
	for (const m of restOptions) {
		const id = familyForModel(m);
		let bucket = families.find((f) => f.id === id);
		if (!bucket) {
			bucket = { id, models: [] };
			families.push(bucket);
		}
		bucket.models.push(m);
	}

	const backendOptions: ToggleGroupOption<BackendChoice>[] = [
		{ value: "local", label: t("onboarding.backendLocalLabel") },
		{ value: "cloud", label: t("onboarding.backendCloudLabel") },
	];

	const renderModelRow = (m: ModelOption) => {
		const langKey = languageBadgeKey(m.languages);
		const isSelected = selectedModel === m.name;
		const isDownloadingThis = downloadingModel === m.name;
		const displayName = displayNameFor(m);
		return (
			<div
				key={m.name}
				className="flex flex-wrap items-center justify-between gap-2 py-2.5"
				data-testid={`onboarding-model-item-${m.name}`}
			>
				{/* Row-select button (toggle pattern): the
				    name + badges are one selectable unit;
				    the Download button is a SIBLING, never
				    nested (invalid DOM inside a button).
				    aria-pressed conveys the selection state
				    (a native <input type=radio> cannot carry
				    the badge layout inside the row). */}
				<button
					type="button"
					aria-pressed={isSelected}
					onClick={() => setSelectedModel(m.name)}
					className="flex min-w-0 flex-1 flex-col items-start gap-1 rounded-lg p-1 text-start outline-none focus-visible:ring-1 focus-visible:ring-ring"
					aria-label={t("onboarding.modelSelectAria", {
						name: displayName,
					})}
					data-testid={`onboarding-model-select-${m.name}`}
				>
					<span
						className={`text-sm font-medium ${isSelected ? "text-accent" : "text-foreground"}`}
					>
						{displayName}
						{isSelected ? " ✓" : ""}
					</span>
					<span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
						<span>
							{m.description ?? ""}
							{m.description && m.size ? ", " : ""}
							{m.size ?? ""}
							{(() => {
								const speedLabel = formatModelSpeed(m.speed);
								return speedLabel ? ` (${speedLabel})` : "";
							})()}
						</span>
						{m.vram_gb != null && (
							<ModelBadge>
								{t("onboarding.vramBadge", {
									vram: formatVram(m.vram_gb * 1024),
								})}
							</ModelBadge>
						)}
						{langKey != null && <ModelBadge>{t(langKey)}</ModelBadge>}
					</span>
				</button>
				<Button
					type="button"
					variant="outline"
					size="sm"
					// Same fixed-width, left-aligned, compact-icon
					// tokens as the Models page download buttons
					// (C-MODELS-2), imported (no duplication).
					className={`gap-2 text-xs whitespace-nowrap ${DOWNLOAD_SIZE_BUTTON_WIDTH} ${DOWNLOAD_CONTENT_ALIGNMENT}`}
					onClick={() => onDownload(m.name)}
					disabled={isDownloading}
					aria-busy={isDownloadingThis}
					aria-label={t("onboarding.modelSizeDownloadAria", {
						name: displayName,
					})}
					data-testid={`onboarding-download-button-${m.name}`}
				>
					{isDownloadingThis ? (
						<>
							<span
								className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
								role="presentation"
							/>
							{progressPct}%
						</>
					) : (
						t("onboarding.downloadModel")
					)}
				</Button>
			</div>
		);
	};

	const recommendedIsFast = (() => {
		if (!recommended) return false;
		const speed = (recommended.speed ?? "").toLowerCase();
		return speed === "fast" || speed === "fastest";
	})();
	const recommendedIsMultilingual =
		recommended != null &&
		languageBadgeKey(recommended.languages) === "onboarding.multilingualBadge";
	const recommendedIsSelected =
		recommended != null && selectedModel === recommended.name;
	const recommendedIsDownloadingThis =
		recommended != null && downloadingModel === recommended.name;
	const recommendedDisplayName = recommended ? displayNameFor(recommended) : "";

	return (
		<>
			<h2 ref={headingRef} tabIndex={-1} className={HEADING_CLASS}>
				{t("onboarding.modelTitle")}
			</h2>
			<p className="text-sm text-muted-foreground">
				{t("onboarding.modelDescription")}
			</p>

			{/* Local vs cloud choice — the SAME ToggleGroup the Models
			    page uses for its Local/Cloud tabs (identical tokens:
			    rounded-lg border border-border/10 bg-surface-subtle container
			    + bg-surface bordered active segment, C-MODELS-1). This is the
			    single place where the user decides how transcription runs;
			    the app never downloads a model on its own. */}
			<ToggleGroup
				variant="tabs"
				options={backendOptions}
				value={selectedBackend}
				onChange={setSelectedBackend}
				ariaLabel={t("onboarding.backendAria")}
				indicatorClassName="bg-surface border border-border/10"
				labelClassName="flex-1 text-center"
				className="w-full rounded-lg border border-border/10 bg-surface-subtle"
				getTabId={(v) => `onboarding-backend-tab-${v}`}
				getPanelId={(v) => `onboarding-backend-panel-${v}`}
			/>

			{selectedBackend === "local" ? (
				<div
					role="tabpanel"
					id="onboarding-backend-panel-local"
					aria-labelledby="onboarding-backend-tab-local"
					className="flex flex-col gap-3"
				>
					{recommended ? (
						<div
							className="flex flex-col gap-2 rounded-lg border border-border/8 bg-surface-subtle p-4"
							data-testid="onboarding-recommended-card"
						>
							<div className="flex flex-wrap items-center gap-x-2 gap-y-1">
								<ModelBadge>
									{t("onboarding.models.badgeRecommended")}
								</ModelBadge>
								{recommendedIsFast && (
									<ModelBadge>{t("onboarding.models.badgeFast")}</ModelBadge>
								)}
								{recommendedIsMultilingual && (
									<ModelBadge>
										{t("onboarding.models.badgeLanguages")}
									</ModelBadge>
								)}
							</div>
							<div
								className="flex flex-wrap items-center justify-between gap-2"
								data-testid={`onboarding-model-item-${recommended.name}`}
							>
								<button
									type="button"
									aria-pressed={recommendedIsSelected}
									onClick={() => setSelectedModel(recommended.name)}
									className="flex min-w-0 flex-1 flex-col items-start gap-1 rounded-lg p-1 text-start outline-none focus-visible:ring-1 focus-visible:ring-ring"
									aria-label={t("onboarding.modelSelectAria", {
										name: recommendedDisplayName,
									})}
									data-testid={`onboarding-model-select-${recommended.name}`}
								>
									<span
										className={`text-sm font-medium ${recommendedIsSelected ? "text-accent" : "text-foreground"}`}
									>
										{recommendedDisplayName}
										{recommendedIsSelected ? " ✓" : ""}
									</span>
									<span className="text-xs text-muted-foreground">
										{recommended.description ?? ""}
										{recommended.description && recommended.size ? ", " : ""}
										{recommended.size ?? ""}
										{(() => {
											const speedLabel = formatModelSpeed(recommended.speed);
											return speedLabel ? ` (${speedLabel})` : "";
										})()}
									</span>
									{recommended.vram_gb != null && (
										<span className="flex flex-wrap items-center gap-x-2 gap-y-1">
											<ModelBadge>
												{t("onboarding.vramBadge", {
													vram: formatVram(recommended.vram_gb * 1024),
												})}
											</ModelBadge>
										</span>
									)}
								</button>
								<Button
									type="button"
									variant="outline"
									size="sm"
									className={`gap-2 text-xs whitespace-nowrap ${DOWNLOAD_SIZE_BUTTON_WIDTH} ${DOWNLOAD_CONTENT_ALIGNMENT}`}
									onClick={() => onDownload(recommended.name)}
									disabled={isDownloading}
									aria-busy={recommendedIsDownloadingThis}
									aria-label={t("onboarding.modelSizeDownloadAria", {
										name: recommendedDisplayName,
									})}
									data-testid={`onboarding-download-button-${recommended.name}`}
								>
									{recommendedIsDownloadingThis ? (
										<>
											<span
												className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
												role="presentation"
											/>
											{progressPct}%
										</>
									) : (
										t("onboarding.downloadModel")
									)}
								</Button>
							</div>
						</div>
					) : null}

					{recommended ? (
						<div className="flex flex-col gap-2">
							<Button
								type="button"
								variant="ghost"
								size="sm"
								className="w-full justify-between px-4"
								aria-expanded={allModelsOpen}
								aria-controls="onboarding-all-models-panel"
								onClick={() => setAllModelsOpen((v) => !v)}
								data-testid="onboarding-all-models-toggle"
							>
								<span className="text-sm font-medium text-foreground">
									{t("onboarding.models.allModels")}
								</span>
								<HugeiconsIcon
									icon={ChevronDownIcon}
									strokeWidth={1.8}
									aria-hidden="true"
									className={`size-4 shrink-0 text-muted-foreground transition-transform duration-200 ${allModelsOpen ? "rotate-180" : ""}`}
								/>
							</Button>
							<div className="collapse-root" data-open={allModelsOpen}>
								<div
									id="onboarding-all-models-panel"
									className="flex flex-col gap-2"
								>
									{allModelsOpen ? (
										<Accordion
											type="multiple"
											defaultValue={families[0] ? [families[0].id] : []}
											className="rounded-lg border border-border/8 bg-surface-subtle"
											data-testid="onboarding-model-accordion"
										>
											{families.map((family) => (
												<AccordionItem key={family.id} value={family.id}>
													<AccordionTrigger className="px-4 hover:no-underline">
														<div className="flex items-center gap-2">
															<FamilyLogo family={family.id} />
															<span className="text-sm font-medium text-foreground">
																{FAMILY_LABELS[family.id] ?? family.id}
															</span>
														</div>
													</AccordionTrigger>
													<AccordionContent className="px-4 pb-2">
														<div className="flex flex-col divide-y divide-border/8">
															{family.models.map((m) => renderModelRow(m))}
														</div>
													</AccordionContent>
												</AccordionItem>
											))}
										</Accordion>
									) : null}
								</div>
							</div>
						</div>
					) : (
						<Accordion
							type="multiple"
							// The first family (whisper) starts expanded, matching the
							// Models page's expand-the-active-family default.
							defaultValue={families[0] ? [families[0].id] : []}
							className="rounded-lg border border-border/10 bg-surface-subtle"
							data-testid="onboarding-model-accordion"
						>
							{families.map((family) => (
								<AccordionItem key={family.id} value={family.id}>
									<AccordionTrigger className="px-4 hover:no-underline">
										<div className="flex items-center gap-2">
											<FamilyLogo family={family.id} />
											<span className="text-sm font-medium text-foreground">
												{FAMILY_LABELS[family.id] ?? family.id}
											</span>
										</div>
									</AccordionTrigger>
									<AccordionContent className="px-4 pb-2">
										<div className="flex flex-col divide-y divide-border/8">
											{family.models.map((m) => renderModelRow(m))}
										</div>
									</AccordionContent>
								</AccordionItem>
							))}
						</Accordion>
					)}

					{/* Inline download-failure hint. The per-item button is
					    the retry affordance (click Download again); the old
					    standalone blue Download button + its adjacent hint
					    text are gone (downloads are per item now). */}
					{downloadFailed && !isDownloading && (
						<p
							className="text-xs text-destructive"
							data-testid="onboarding-download-error"
						>
							{t("onboarding.downloadFailedHint")}
						</p>
					)}

					{/* In-wizard download progress (kept from the previous
					    flow, driven by download_progress push events). */}
					{isDownloading && (
						<div
							role="progressbar"
							aria-valuenow={progressPct}
							aria-valuemin={0}
							aria-valuemax={100}
							aria-label={t("onboarding.downloadProgressAria", {
								percent: String(progressPct),
							})}
							className="flex flex-col gap-2 rounded-lg border border-accent/40 bg-accent/5 p-3"
							data-testid="onboarding-download-progress"
						>
							<div className="flex items-center justify-between text-xs text-(--text-secondary)">
								<span className="flex items-center gap-2">
									<span
										className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
										role="presentation"
									/>
									{t("onboarding.downloadingModel")}
								</span>
								<span>{progressPct}%</span>
							</div>
							<div className="h-1.5 w-full rounded-full bg-surface-subtle">
								<div
									className="h-1.5 rounded-full bg-accent transition-all duration-300"
									style={{ width: `${Math.min(100, downloadProgress)}%` }}
								/>
							</div>
						</div>
					)}
				</div>
			) : (
				<div
					role="tabpanel"
					id="onboarding-backend-panel-cloud"
					aria-labelledby="onboarding-backend-tab-cloud"
					className="flex flex-col gap-4"
				>
					{/* Cloud provider selection, mirrors the Models page
					    cloud tab (same config fields). */}
					<div className="flex flex-col gap-1">
						<label
							htmlFor="onboarding-cloud-provider"
							className="text-sm font-medium text-foreground"
						>
							{t("onboarding.cloudProviderLabel")}
						</label>
						<select
							id="onboarding-cloud-provider"
							value={cloudProvider}
							onChange={(e) => setCloudProvider(e.target.value)}
							aria-label={t("onboarding.cloudProviderLabel")}
							className="w-full rounded-lg border border-border/8 bg-surface px-3 py-2 text-sm text-foreground"
							data-testid="onboarding-cloud-provider"
						>
							{CLOUD_PROVIDERS.map((p) => (
								<option key={p} value={p}>
									{providerLabel(p)}
								</option>
							))}
						</select>
					</div>

					<div className="flex flex-col gap-1">
						<label
							htmlFor="onboarding-cloud-api-key"
							className="text-sm font-medium text-foreground"
						>
							{t("models.cloud.apiKey")}
						</label>
						<Input
							id="onboarding-cloud-api-key"
							type="password"
							value={cloudApiKey}
							onChange={(e) => setCloudApiKey(e.target.value)}
							placeholder={t("models.cloud.apiKeyPlaceholder")}
							autoComplete="off"
							spellCheck={false}
							data-testid="onboarding-cloud-api-key"
						/>
					</div>

					<p className="text-xs text-muted-foreground">
						{t("onboarding.cloudNote")}
					</p>
				</div>
			)}
		</>
	);
}

export default ModelStep;
