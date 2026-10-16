import {
	CircleIcon,
	Loading03Icon,
	Settings01Icon,
	Shield01Icon,
	SparklesIcon,
	Tick02Icon,
	ViewIcon,
	ViewOffIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import type React from "react";
import { memo, useState } from "react";
import { KeyringStatusBadge } from "@/components/common/KeyringStatusBadge";
import { FamilyLogo } from "@/components/models/FamilyLogo";
import {
	MetadataPair,
	ModelGroupAccordion,
	ModelGroupContent,
	ModelGroupItem,
	ModelGroupTrigger,
	ModelVariantRow,
} from "@/components/models/ModelGroupList";
import {
	LanguageScopeTag,
	SpeedTag,
} from "@/components/models/ModelMetaIconTags";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { hasStoredCloudApiKey } from "@/hooks/models/useCloudProviders";
import { t } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import {
	type CloudModel,
	type CloudModelRef,
	type CloudProvider,
	type CloudProviderKey,
	cloudModelLabel,
	formatCloudWer,
	getProviderLabel,
	isCloudModelActive,
	isRealtimeGuardOnly,
} from "@/lib/utils/models";
import type { LausuConfig } from "@/types/config";

export interface CloudProvidersPanelProps {
	config: LausuConfig | null;
	cloudProviders: readonly CloudProvider[];
	apiKeys: Record<string, string>;
	/** Providers with a Test Connection probe in flight (absent = idle).
	 * Only the button's spinner/disabled state depends on it — the
	 * outcome itself is a toast (see `useCloudProviders`). */
	testingProviders: Record<string, boolean>;
	/** The cloud model whose activation is being persisted (absent =
	 * idle). Only that one row shows its spinner. */
	selectingCloudModel: CloudModelRef | null;
	onApiKeyChange: (provider: string, value: string) => void;
	onSaveApiKey: (provider: string) => void;
	onTestConnection: (provider: string) => void;
	/** Make ONE of a provider's models the active speech backend. */
	onActivateModel: (provider: CloudProviderKey, modelId: string) => void;
	// Controlled accordion state (page-lifted): keeps the user's
	// expanded providers alive across tab flips, Models.tsx unmounts
	// this panel when switching to Local, which would otherwise reset
	// the accordion to collapsed on return. When absent the accordion
	// falls back to internal state (uncontrolled, for direct mounts /
	// tests).
	accordionValue?: string[];
	onAccordionValueChange?: (value: string[]) => void;
}

// One shared width for every cloud row action so the Select / Selecting…
// / Active labels never reflow the row. Mirrors the local rows'
// `ModelCardActions` (w-24), so the two tabs' right-hand columns line up.
const CLOUD_ACTION_BUTTON_CLASS = "w-24 gap-2 text-xs whitespace-nowrap";

// ── The provider-level setup dialog's state ───────────────────────────
// `open` is kept SEPARATE from the provider so the dialog stays mounted
// while it animates closed: unmounting it the instant `open` flips to
// false would skip Radix's `onCloseAutoFocus`, dropping focus onto
// <body> instead of returning it to the Configure button that opened it.
interface ConfigureDialogState {
	provider: CloudProvider;
	open: boolean;
}

// Wrapped in `React.memo` (same pattern as the memo'd settings sections
// and the local-models panel): the panel's props are data + stable
// callbacks, so a Models-page re-render driven by unrelated state (e.g.
// a local-model download tick) skips the whole cloud tab tree. The page
// passes `onApiKeyChange` as a `useCallback`-stable handler and all other
// handlers come from `useCallback`-stable hook actions, so the memo
// gates effectively.
export const CloudProvidersPanel = memo(function CloudProvidersPanel({
	config,
	cloudProviders,
	apiKeys,
	testingProviders,
	selectingCloudModel,
	onApiKeyChange,
	onSaveApiKey,
	onTestConnection,
	onActivateModel,
	accordionValue,
	onAccordionValueChange,
}: CloudProvidersPanelProps) {
	// Which provider's setup dialog is open, plus the provider it belongs
	// to. A SINGLE slot, not a map: the setup form is a modal
	// (2026-10-11), and a modal is exclusive by construction — the
	// overlay blocks every other provider's Configure button, so at most
	// one form can ever be open. Purely local UI state.
	const [dialog, setDialog] = useState<ConfigureDialogState | null>(null);

	return (
		<div className="flex flex-col gap-4">
			<ModelGroupAccordion
				type="multiple"
				value={accordionValue}
				onValueChange={onAccordionValueChange}
			>
				{cloudProviders.map((provider) => {
					// Every model a provider serves shares that provider's ONE
					// key, so "is this provider configured" is a per-GROUP fact.
					// It decides whether the model rows offer Select at all:
					// a Select that can only answer "enter the API key first"
					// is a button that exists to refuse.
					const keyConfigured = hasStoredCloudApiKey(config, provider.key);
					return (
						<ModelGroupItem key={provider.key} value={provider.key}>
							{/* The trigger carries the provider's BRAND only
						    ("OpenAI", "Groq", "Deepgram", "Google") and the
						    Configure action sits at the provider level, on
						    the right of that same row — immediately LEFT of
						    the disclosure chevron, so the whole row (brand →
						    Configure → chevron) is one hover surface.
						    Both halves are deliberate:
						      • the trigger used to read "OpenAI Whisper API" —
						        provider + model + the word "API" welded into
						        one label, which pre-empted the group's own
						        content. The model name now appears once, as
						        the row heading inside the group;
						      • Configure used to hang off EACH model row, so
						        a provider with ten models asked for the same
						        API key ten times. All of a provider's models
						        share one key, so the form belongs to the
						        provider. It renders in the trigger trailing group, inside the button (see
						        `AccordionTrigger`'s `actions` slot; its click is stopped before it can toggle the panel. */}
							<ModelGroupTrigger
								actions={
									<Button
										variant="outline"
										size="sm"
										className="gap-2"
										onClick={() => setDialog({ provider, open: true })}
										// A MODAL trigger, not a disclosure: the
										// setup form opens in a dialog, so the
										// button advertises `aria-haspopup="dialog"`
										// and carries neither `aria-expanded`
										// (nothing expands in place) nor a "Hide"
										// label — the dialog owns its own close
										// affordances.
										aria-haspopup="dialog"
										aria-label={t("models.cloud.configureAria", {
											provider: getProviderLabel(provider.key),
										})}
									>
										<HugeiconsIcon
											icon={Settings01Icon}
											strokeWidth={2}
											className="h-4 w-4"
										/>
										{t("models.cloud.configure")}
									</Button>
								}
							>
								{provider.key === "groq" ? (
									<HugeiconsIcon
										icon={Shield01Icon}
										strokeWidth={2}
										className="h-4 w-4 text-accent"
									/>
								) : (
									<FamilyLogo family={provider.key} />
								)}
								{getProviderLabel(provider.key)}
							</ModelGroupTrigger>
							<ModelGroupContent>
								{/* One row per model the provider serves. The list
							    is data (`CloudProvider.models`) and grows over
							    time, so nothing here may assume a fixed count
							    or a single entry. */}
								{provider.models.map((model) => (
									<CloudModelRow
										key={model.id}
										provider={provider}
										model={model}
										config={config}
										keyConfigured={keyConfigured}
										activating={
											selectingCloudModel?.provider === provider.key &&
											selectingCloudModel.model === model.id
										}
										onActivateModel={onActivateModel}
									/>
								))}
							</ModelGroupContent>
						</ModelGroupItem>
					);
				})}
			</ModelGroupAccordion>
			{dialog && (
				<Dialog
					open={dialog.open}
					onOpenChange={(open) => {
						// Escape, an overlay click and the X all land here
						// with `false`. Only flip THIS dialog's flag, so a
						// late event from an already-closed dialog cannot
						// close a newly opened one.
						if (!open) {
							setDialog((current) =>
								current ? { ...current, open: false } : current,
							);
						}
					}}
				>
					{/* Title = the provider name. The form below carries its
					    own labelled fields, so no separate description is
					    needed. */}
					<DialogContent size="lg">
						<DialogHeader>
							<DialogTitle>{getProviderLabel(dialog.provider.key)}</DialogTitle>
						</DialogHeader>
						<ProviderConfigForm
							provider={dialog.provider}
							config={config}
							apiKeyValue={apiKeys[dialog.provider.key] ?? ""}
							isTesting={Boolean(testingProviders[dialog.provider.key])}
							onApiKeyChange={(v) => onApiKeyChange(dialog.provider.key, v)}
							onSaveApiKey={() => onSaveApiKey(dialog.provider.key)}
							onTestConnection={() => onTestConnection(dialog.provider.key)}
						/>
					</DialogContent>
				</Dialog>
			)}
		</div>
	);
});

// ── Sub-component: one model row ──────────────────────────────────────
// The row's action is the SAME Select / Active vocabulary the Local tab
// uses, on purpose: there is exactly ONE active speech model at a time
// across both tabs (`config.asr_backend` is a single value), so one
// vocabulary is the honest way to express it. Activating a cloud model
// writes `asr_backend = "cloud"`, which is what deactivates whichever
// local model was active — and vice versa.
function CloudModelRow({
	provider,
	model,
	config,
	keyConfigured,
	activating,
	onActivateModel,
}: {
	provider: CloudProvider;
	model: CloudModel;
	config: LausuConfig | null;
	/** The provider has a stored API key. Gates the Select action: without
	 *  a key the backend cannot run the model, so offering Select would
	 *  only ever answer "enter the API key first". */
	keyConfigured: boolean;
	activating: boolean;
	onActivateModel: (provider: CloudProviderKey, modelId: string) => void;
}) {
	const label = cloudModelLabel(provider.key, model.id);
	const isActive = isCloudModelActive(provider, model.id, config);
	// Guard-only rows are display-only: no app transport serves
	// them, so they get a marker instead of Select — and never Active.
	// WS-supported realtime rows activate like batch rows.
	const realtime = isRealtimeGuardOnly(provider.key, model.id);

	return (
		<ModelVariantRow
			name={label}
			meta={
				<>
					{/* WER, the same figure the Local tab shows — and, like
					    the Local rows, rendered ONLY when a pooled
					    real-world benchmark actually covers the model.
					    `null` used to render as "WER : —", which spent a
					    label on an absence and read as a broken value;
					    hiding the pair is the honest version. Never
					    guessed — see `formatCloudWer`. */}
					{model.wer !== null && (
						<MetadataPair
							label={t("models.card.werLabel")}
							value={formatCloudWer(model.wer)}
						/>
					)}
					{/* Same two-group structure as the Local rows
					    (C-MODELS-2): the information group is the WER pair
					    above (spaced `gap-x-3` by `ModelVariantRow`), and
					    this span is the chip group at the tighter
					    `gap-x-1.5`. The cloud chip that used to open this
					    group is gone: every row on THIS tab is a cloud
					    model, so a cloud glyph with a "Cloud" tooltip
					    restated the tab. The speed chip takes its place —
					    that is the fact the user cannot read off the tab. */}
					<span className="inline-flex flex-wrap items-center gap-x-1.5 gap-y-1.5">
						<LanguageScopeTag multilingual />
						<SpeedTag rating={model.speed_rating} />
					</span>
				</>
			}
			actions={
				realtime ? (
					<span
						className={cn(
							CLOUD_ACTION_BUTTON_CLASS,
							"inline-flex cursor-default items-center justify-center rounded-lg border border-border/8 text-muted-foreground",
						)}
						// Exposed to AT: a bare span drops aria-label, and
						// title is mouse-only, so keyboard users get the
						// reason through the note role instead.
						role="note"
						title={t("models.cloud.realtimeOnlyTooltip")}
						aria-label={t("models.cloud.realtimeOnlyTooltip")}
						data-testid={`realtime-only-${provider.key}-${model.id}`}
					>
						{t("models.cloud.realtimeOnly")}
					</span>
				) : isActive ? (
					<Button
						variant="secondary"
						size="sm"
						className={cn(
							CLOUD_ACTION_BUTTON_CLASS,
							"cursor-default opacity-60",
						)}
						// Disabled, not hidden: it reports state ("this is the
						// one in use") and a second click would be a no-op.
						// It also stays visible with no stored key: the config
						// naming the model is a fact about the app, not an
						// action the user can take.
						disabled
						aria-label={t("models.card.activeAria", { name: label })}
					>
						<HugeiconsIcon
							icon={Tick02Icon}
							strokeWidth={2}
							className="h-3 w-3"
						/>
						{t("models.active")}
					</Button>
				) : keyConfigured ? (
					<Button
						variant={activating ? "secondary" : "outline"}
						size="sm"
						className={CLOUD_ACTION_BUTTON_CLASS}
						onClick={() => onActivateModel(provider.key, model.id)}
						disabled={activating}
						// Announce the in-flight activation via aria-busy + a
						// label swap (same contract as the Local rows).
						aria-busy={activating}
						aria-label={
							activating
								? t("models.selecting")
								: t("models.card.selectAria", { name: label })
						}
					>
						<HugeiconsIcon
							icon={activating ? Loading03Icon : CircleIcon}
							strokeWidth={2}
							className={cn("h-3 w-3", activating && "animate-spin")}
						/>
						{activating ? t("models.selecting") : t("models.select")}
					</Button>
				) : null
			}
		/>
	);
}

// ── Sub-component: API-key entry + test ───────────────────────────────
// Rendered INSIDE the provider's setup dialog (`DialogContent`), opened
// by that provider's Configure action. It deliberately carries no card
// surface of its own: the dialog already provides the raised panel, so
// a second border + fill here would read as a card inside a card.
//
// The form is the key field and two buttons, and NOTHING else. The
// format hint that used to sit under the field ("… typically 40-60
// characters. Paste the full key: no spaces or prefixes.") was removed:
// it described a shape the user cannot act on, and the actionable
// version of that message is the rejection toast `useCloudProviders`
// raises when the shape is actually wrong. The audio-transmission
// consent moved to the shared consent dialog, raised after the key is
// saved.

interface ProviderConfigFormProps {
	provider: CloudProvider;
	config: LausuConfig | null;
	apiKeyValue: string;
	isTesting: boolean;
	onApiKeyChange: (value: string) => void;
	onSaveApiKey: () => void;
	onTestConnection: () => void;
}

function ProviderConfigForm({
	provider,
	config,
	apiKeyValue,
	isTesting,
	onApiKeyChange,
	onSaveApiKey,
	onTestConnection,
}: ProviderConfigFormProps) {
	// Show/hide toggle for the API key input. Default is
	// hidden (type="password"); clicking the eye-icon button reveals
	// the plain-text value for verification. The reveal state is purely
	// local, every ProviderConfigForm instance owns its own toggle so
	// opening one provider's key does NOT reveal another's.
	const [revealKey, setRevealKey] = useState(false);

	//disable Save Key when the input is empty (prevents
	// silently clobbering a stored secret with the empty string that
	// `safeApiKey` substitutes for the `<redacted>` sentinel on every
	// config fetch). A key that is non-empty but malformed stays
	// ENABLED on purpose: clicking it is what raises the explanatory
	// toast, and a disabled button would say "no" without saying why.
	const saveDisabled = !apiKeyValue.trim();

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-col gap-2">
				<div className="flex items-center gap-2">
					<label
						htmlFor={`api-key-input-${provider.key}`}
						className="text-sm font-medium text-foreground"
					>
						{t("models.cloud.apiKey")}
					</label>
					<KeyringStatusBadge status={config?.keyring_status} compact />
				</div>
				{/* Full width of the dialog. The wrapper used to be
				    `w-full max-w-md`, which capped the field at 28rem
				    inside a 36rem `size="lg"` dialog and left a strip of
				    dead space to its right that read as a layout bug. */}
				<div className="relative w-full">
					<Input
						id={`api-key-input-${provider.key}`}
						type={revealKey ? "text" : "password"}
						value={apiKeyValue}
						onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
							onApiKeyChange(e.target.value)
						}
						placeholder={t("models.apiKeyPlaceholder")}
						className="w-full pe-10"
						autoComplete="off"
						spellCheck={false}
					/>
					<button
						type="button"
						onClick={() => setRevealKey((v) => !v)}
						className="absolute inset-e-2 top-1/2 -translate-y-1/2 inline-flex size-6 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
						aria-label={
							revealKey
								? t("models.cloud.apiKeyHideAria", {
										provider: getProviderLabel(provider.key),
									})
								: t("models.cloud.apiKeyShowAria", {
										provider: getProviderLabel(provider.key),
									})
						}
						aria-pressed={revealKey}
					>
						<HugeiconsIcon
							icon={revealKey ? ViewOffIcon : ViewIcon}
							strokeWidth={2}
							className="h-4 w-4"
							aria-hidden="true"
						/>
					</button>
				</div>
			</div>
			<div className="flex flex-wrap items-center gap-3">
				<Button
					variant="default"
					size="sm"
					onClick={onSaveApiKey}
					disabled={saveDisabled}
					aria-label={t("models.cloud.saveKeyAria", {
						provider: getProviderLabel(provider.key),
					})}
				>
					{t("models.cloud.saveKey")}
				</Button>
				<Button
					variant="outline"
					size="sm"
					className="gap-2"
					onClick={onTestConnection}
					//disable while a test is in flight so concurrent
					// clicks don't fire overlapping fetches.
					disabled={isTesting}
					aria-busy={isTesting}
					aria-label={t("models.cloud.testConnectionAria", {
						provider: getProviderLabel(provider.key),
					})}
				>
					<HugeiconsIcon
						//swap the static SparklesIcon for a spinning
						// Loading03Icon while the test is in flight so users
						// get immediate visual feedback that the click
						// registered (the probe can take 500ms–5s).
						icon={isTesting ? Loading03Icon : SparklesIcon}
						strokeWidth={2}
						className={cn("h-4 w-4", isTesting && "animate-spin")}
					/>
					{t("models.cloud.testConnection")}
				</Button>
			</div>
		</div>
	);
}
