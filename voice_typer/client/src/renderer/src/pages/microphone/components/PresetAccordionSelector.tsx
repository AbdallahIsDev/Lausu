// Accordion-style "Microphone Quality" preset selector, Microphone
// page only.
// Collapsed, the header shows the section label + a general help
// InfoTooltip + the CURRENT selection; expanding reveals a master
// enable-Switch first, then (while enabled) a RadioGroup of the four
// real presets (the preset VALUES and their label/description keys come
// from the shared registry `lib/utils/audioPresets.ts` — single source
// of truth for the preset set, shared with the Settings → Audio rows;
// the canonical preset → filter mapping lives in
// `voice_typer/server/audio_presets.py`). "off" lives ONLY behind the
// Switch (same mechanism as the Settings surface): flipping it off
// stashes the current preset, flipping it on restores it. Each
// option's description lives in a per-row InfoTooltip instead of being
// permanently visible, keeps the accordion compact and kills the
// duplicated header paragraph.
// Selecting a radio applies the preset immediately (ADR 0007: backend
// maps preset → filter chain). When the Custom preset is active, the
// progressive-disclosure Custom-filters toggle + AudioFilterChain render
// inside the expanded region.
// The expand/collapse affordance is the shared ui/accordion trigger.
// That trigger's own glyph is switched off here (see `disclosure={false}`
// below) and replaced by a dedicated rotating chevron.

import { ArrowDown01Icon, FilterIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { AudioFilterChain } from "@/components/audio/AudioFilterChain";
import {
	filterFactoryDefaults,
	MIC_ADVANCED_ROW_KEYS,
} from "@/components/audio/audioFilterRowDescriptors";
import { SelectableRow } from "@/components/common/SelectableRow";
import { InfoTooltip } from "@/components/feedback/InfoTooltip";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Switch } from "@/components/ui/switch";
import { t } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import {
	AUDIO_PRESET_OPTIONS,
	type AudioPreset,
} from "@/lib/utils/audioPresets";
import type { CustomMicPreset, LausuConfig } from "@/types/config";
import {
	type FilterSnapshot,
	filterSnapshotsEqual,
	snapshotFilterValues,
} from "../lib/filterSnapshot";
import { SavePresetDialog } from "./SavePresetDialog";

interface PresetAccordionSelectorProps {
	preset: AudioPreset;
	config: LausuConfig;
	/** Whether the Custom-filters panel is expanded. */
	showAdvanced: boolean;
	/** Called when the user picks a new preset. */
	onPresetChange: (preset: AudioPreset) => void;
	/** Called when the user toggles the Custom-filters disclosure. */
	onToggleAdvanced: () => void;
	/** Called when any individual filter field changes. */
	onConfigChange: (updates: Partial<LausuConfig>) => void;
	/** Saved custom presets (from config). */
	customPresets?: CustomMicPreset[];
	/** Selected saved preset id while preset === "custom". */
	activeCustomPresetId?: string | null;
	/** Called with a saved preset id (values applied by the caller). */
	onSelectCustomPreset?: (id: string) => void;
	/** Called with a new preset name (current values snapshotted by the caller). */
	onSaveCustomPreset?: (name: string) => void;
	/** Called to restore factory filter values. */
	onRestoreMicDefaults?: () => void;
}

interface PresetOption {
	value: string;
	label: string;
	description: string;
	isCustom: boolean;
}

// Resolve the shared registry's label/description keys through `t`
// (one lookup per key per mount, memoized per mount). The DATA
// (values + keys) lives in `lib/utils/audioPresets.ts`; only the
// locale resolution happens here. Saved customs append after the
// stock options (no description → no tooltip).
function getPresetOptions(customPresets: CustomMicPreset[]): PresetOption[] {
	const stock: PresetOption[] = AUDIO_PRESET_OPTIONS.map((option) => ({
		value: option.value,
		label: t(option.labelKey),
		description: t(option.descriptionKey),
		isCustom: false,
	}));
	for (const custom of customPresets) {
		stock.push({
			value: `custom:${custom.id}`,
			label: custom.name,
			description: "",
			isCustom: true,
		});
	}
	return stock;
}

const ACCORDION_ITEM_VALUE = "microphone-quality";

// Stable identity for the "no saved presets" case: an inline `[]` default
// would be a fresh array on every render, invalidating the presetOptions
// memo each time (two t() lookups per key per mount instead of one).
const EMPTY_CUSTOM_PRESETS: CustomMicPreset[] = [];

export function PresetAccordionSelector({
	preset,
	config,
	showAdvanced,
	onPresetChange,
	onToggleAdvanced,
	onConfigChange,
	customPresets = EMPTY_CUSTOM_PRESETS,
	activeCustomPresetId = null,
	onSelectCustomPreset = () => {},
	onSaveCustomPreset = () => {},
	onRestoreMicDefaults = () => {},
}: PresetAccordionSelectorProps) {
	const presetOptions = useMemo(
		() => getPresetOptions(customPresets),
		[customPresets],
	);
	// "off" is not a radio option (disabling is the enable-Switch's
	// job); the header chip still needs a display label for it.
	const selectableOptions = presetOptions.filter((o) => o.value !== "off");
	// Radio value: a selected saved preset addresses its own option,
	// everything else uses the preset name (incl. ad-hoc "custom").
	const radioValue =
		preset === "custom" && activeCustomPresetId
			? `custom:${activeCustomPresetId}`
			: preset;
	const activeCustom = activeCustomPresetId
		? (customPresets.find((c) => c.id === activeCustomPresetId) ?? null)
		: null;
	const current =
		activeCustom != null
			? {
					value: `custom:${activeCustom.id}`,
					label: activeCustom.name,
					description: "",
				}
			: preset === "off"
				? {
						value: "off",
						label: t("settings.audioEnhancement.presetOff"),
						description: "",
					}
				: presetOptions.find((o) => o.value === preset);
	const enabled = preset !== "off";
	const isCustom = preset === "custom";
	const panelId = "mic-preset-custom-panel";

	// Remembers the last non-"off" option value so flipping the Switch back
	// on restores the user's choice instead of resetting to "auto".
	const lastNonOffRef = useRef<string>(preset === "off" ? "auto" : "");
	useEffect(() => {
		if (preset !== "off") {
			lastNonOffRef.current =
				preset === "custom" && activeCustomPresetId
					? `custom:${activeCustomPresetId}`
					: preset;
		}
	}, [preset, activeCustomPresetId]);

	const handleEnabledChange = (checked: boolean) => {
		if (checked) {
			selectOption(lastNonOffRef.current);
		} else {
			onPresetChange("off");
		}
	};

	const selectOption = (value: string) => {
		if (value.startsWith("custom:")) {
			const id = value.slice("custom:".length);
			if (preset === "custom" && activeCustomPresetId === id) return;
			onSelectCustomPreset(id);
			return;
		}
		if (preset === (value as AudioPreset)) return;
		onPresetChange(value as AudioPreset);
	};

	// ── Dirty tracking for "Save as preset" ──────────────────────
	// A preset name prop only ever changes together with its applied
	// values (one backend push carries both), so the current config
	// always owns the current selection's values. Baselines:
	// - named custom → its saved snapshot (exact, derived, no waiting);
	// - stock/ad-hoc → learned from the first config seen under that
	//   key (the renaming push already carries applied values);
	// - just-restored factory values → clean until the next edit.
	// Until any baseline exists, save stays disabled rather than guessing.
	const [learned, setLearned] = useState<Record<string, FilterSnapshot>>({});
	const [restored, setRestored] = useState<{
		key: string;
		values: FilterSnapshot;
	} | null>(null);
	const [saveDialogOpen, setSaveDialogOpen] = useState(false);
	const presetKey = `${preset}:${activeCustomPresetId ?? ""}`;
	useEffect(() => {
		if (activeCustom != null) return;
		if (learned[presetKey] !== undefined) return;
		const snap = snapshotFilterValues(config);
		setLearned((prev) =>
			prev[presetKey] !== undefined ? prev : { ...prev, [presetKey]: snap },
		);
	}, [config, presetKey, activeCustom, learned]);
	const savedValues =
		activeCustom != null
			? ((activeCustom.values as FilterSnapshot) ?? null)
			: null;
	const currentValues = snapshotFilterValues(config);
	const baselineValues = savedValues ?? learned[presetKey] ?? null;
	const matchesBaseline =
		baselineValues != null &&
		filterSnapshotsEqual(baselineValues, currentValues);
	const matchesRestored =
		restored != null &&
		restored.key === presetKey &&
		filterSnapshotsEqual(restored.values, currentValues);
	const dirty =
		(baselineValues !== null ||
			(restored != null && restored.key === presetKey)) &&
		!matchesBaseline &&
		!matchesRestored;

	return (
		<Accordion
			type="single"
			collapsible
			className="overflow-hidden border-t border-border/8 bg-surface-subtle"
		>
			<AccordionItem
				value={ACCORDION_ITEM_VALUE}
				className="border-border/8 data-open:bg-transparent"
			>
				<AccordionTrigger
					// No aria-label override: the visible trigger content (section
					// label + CURRENT selection field) IS the accessible name, so
					// screen readers announce the selected preset in the collapsed
					// state. Single compact row: label + ? on the left, the
					// active-filter field + rotating chevron grouped on the right
					// (base justify-between spreads them). px-4 keeps both insets
					// equal and matches the option rows' content boundary.
					// The primitive's own disclosure glyph is switched OFF on
					// THIS instance (user decision for this selector) and replaced
					// by the dedicated rotating chevron below, which rotates
					// down↔up rather than the shared right→down.
					disclosure={false}
					className="items-center gap-3 px-4 py-2.5 hover:bg-foreground/5 hover:no-underline focus-visible:ring-ring"
				>
					<div className="flex items-center gap-2 min-w-0">
						<span className="text-sm font-medium text-foreground">
							{t("settings.audioEnhancement.microphoneQuality")}
						</span>
						{/* Inline (span) trigger: this tooltip lives INSIDE the
                                                AccordionTrigger <button>, where a nested real <button>
                                                would be invalid DOM and would toggle the accordion.
                                                Anchored in normal flow beside the label, it can never
                                                slide into the option list during the expand animation. */}
						<InfoTooltip
							triggerAs="inline"
							text={t("settings.audioEnhancement.microphoneQualityInfo")}
							contextLabel={t("settings.audioEnhancement.microphoneQuality")}
						/>
					</div>
					{/* Active-filter field + chevron: a NON-interactive chip
                                        (plain span, the whole row is the one control) that visually
                                        communicates the current selection, grouped with the expand
                                        control it belongs to. Mirrors the SelectTrigger shell
                                        (bg-background lifts it off the bg-surface-subtle card). The
                                        chevron is decorative (the trigger owns aria-expanded) and
                                        rotates via the primitive's data-state, collapsed points
                                        down (can expand), expanded points up (can collapse). */}
					<div className="flex items-center gap-2 shrink-0">
						<span
							className="inline-flex max-w-40 items-center rounded-lg border border-border/8 bg-background px-2.5 py-1 text-xs font-medium text-foreground"
							data-testid="mic-preset-current"
						>
							<span className="truncate">{current?.label ?? preset}</span>
						</span>
						<HugeiconsIcon
							icon={ArrowDown01Icon}
							strokeWidth={1.625}
							aria-hidden="true"
							className="size-4 shrink-0 text-muted-foreground transition-transform duration-200 group-data-[state=open]/accordion-trigger:rotate-180"
						/>
					</div>
				</AccordionTrigger>
				{/* Padding contract (C-MIC-15): AccordionContent supplies NO
                                horizontal padding, so the shared 16px inset is set HERE
                                (switch row px-4; options px-2 + row p-2), never on the primitive. */}
				<AccordionContent className="flex flex-col gap-2 border-t border-border/8">
					{/* Master enable-Switch (first row): "off" lives ONLY
                                        here, never among the radios below. The radios
                                        (and the Custom panel) render only while enabled. */}
					<div className="flex items-center gap-3 px-4 py-2.5">
						{/* Distinct from the trigger's label: reusing
                                        `microphoneQuality` here echoed the section title
                                        twice on screen while the panel was expanded. */}
						<span className="text-sm font-medium text-foreground">
							{t("settings.audioEnhancement.microphoneQualityEnable")}
						</span>
						<Switch
							checked={enabled}
							onCheckedChange={handleEnabledChange}
							aria-label={t(
								"settings.audioEnhancement.microphoneQualityEnableAria",
							)}
							data-testid="mic-quality-switch"
							className="ms-auto"
						/>
					</div>
					{enabled && (
						<div className="border-t border-border/8 pt-4">
							<RadioGroup
								value={radioValue}
								onValueChange={(v) => selectOption(v)}
								className="gap-1 px-2"
								data-testid="mic-preset-radio-group"
							>
								{selectableOptions.map((option) => (
									// The a11y pair (nested RadioGroupItem is the accessible
									// control; row click is pointer-only convenience) + the
									// skip-nested-button click gating (the radio AND the row's
									// InfoTooltip trigger are <button>s, clicking either must
									// never change the preset as a side effect) live in the
									// shared SelectableRow wrapper.
									<SelectableRow
										key={option.value}
										className={cn(
											"flex items-center gap-3 rounded-lg p-2 min-h-9 cursor-pointer transition-colors hover:bg-foreground/5",
											option.value === preset && "bg-foreground/5",
										)}
										data-testid={`mic-preset-option-${option.value}`}
										ignoreClicksFrom={["button"]}
										onRowSelect={() => {
											selectOption(option.value);
										}}
									>
										{/* Explicit aria-label keeps the radio's name to the
                                                                    preset LABEL; the radio stays FIRST in DOM and is
                                                                    pushed visual-last (order-last ms-auto) onto the rail. */}
										<RadioGroupItem
											value={option.value}
											aria-label={option.label}
											className="order-last ms-auto"
										/>
										{/* Title + its own info trigger form the left
                                                                    content group; the info icon sits immediately
                                                                    after the title (Settings pattern), never at the
                                                                    far end and never inside the radio's hit area.
                                                                    The inline span's stopPropagation (owned by
                                                                    InfoTooltip) keeps clicks/keys off the row
                                                                    handler. */}
										<span className="flex items-center gap-2 min-w-0">
											<span className="text-sm font-medium text-foreground truncate">
												{option.label}
											</span>
											{option.description !== "" && (
												<InfoTooltip
													text={option.description}
													contextLabel={option.label}
												/>
											)}
										</span>
									</SelectableRow>
								))}
							</RadioGroup>
						</div>
					)}

					{isCustom && (
						<>
							{/* px-4 wrapper: the disclosure is a bordered pill, so it
                                                must sit on the same 16px rail as every other row
                                                instead of running flush into the card's borders. */}
							<div className="px-4">
								<button
									type="button"
									className="flex w-full items-center justify-between rounded-lg border border-border/8 px-3 py-2.5 text-xs font-medium text-foreground hover:bg-foreground/5 transition-colors cursor-pointer"
									onClick={onToggleAdvanced}
									aria-expanded={showAdvanced}
									aria-controls={panelId}
								>
									<span className="flex items-center gap-2 font-medium tracking-wide">
										<HugeiconsIcon
											icon={FilterIcon}
											strokeWidth={2}
											className="h-4 w-4 text-muted-foreground"
										/>
										{t("settings.audioEnhancement.customFiltersTitle")}
									</span>
									<HugeiconsIcon
										icon={ArrowDown01Icon}
										strokeWidth={1.625}
										className={cn(
											"h-3.5 w-3.5 transition-transform duration-200",
											showAdvanced && "rotate-180",
										)}
									/>
								</button>
							</div>

							{showAdvanced && (
								<div id={panelId} className="flex flex-col gap-3 px-4 pb-1">
									<AudioFilterChain
										config={config}
										onConfigChange={onConfigChange}
										rowKeys={MIC_ADVANCED_ROW_KEYS}
									/>
									{/* Custom-preset actions: restore is always
									available (idempotent); save enables the
									moment any value drifts from the selection. */}
									<div className="flex flex-wrap items-center gap-2">
										<Button
											variant="outline"
											size="sm"
											className="gap-2"
											onClick={() => {
												const factory = snapshotFilterValues({
													...config,
													...filterFactoryDefaults(),
												} as LausuConfig);
												setRestored({ key: presetKey, values: factory });
												onRestoreMicDefaults();
											}}
										>
											{t("microphoneTest.restoreMicDefaults")}
										</Button>
										<Button
											variant="default"
											size="sm"
											className="gap-2"
											disabled={!dirty}
											onClick={() => setSaveDialogOpen(true)}
										>
											{t("microphoneTest.saveAsPreset")}
										</Button>
									</div>
									<SavePresetDialog
										open={saveDialogOpen}
										takenNames={customPresets.map((c) => c.name)}
										onSave={(name) => {
											setSaveDialogOpen(false);
											onSaveCustomPreset(name);
										}}
										onClose={() => setSaveDialogOpen(false)}
									/>
								</div>
							)}
						</>
					)}
				</AccordionContent>
			</AccordionItem>
		</Accordion>
	);
}
