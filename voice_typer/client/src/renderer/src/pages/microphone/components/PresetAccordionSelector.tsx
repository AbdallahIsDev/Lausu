// Microphone Quality section, Microphone page only.
// One header row ([label + ?] ... Switch) then, while filtering is
// enabled, a flat preset list: Auto, Studio, Noisy Room, saved user
// presets, Advanced last. Selecting Advanced reveals the full filter
// chain inline (no disclosure step). "off" lives ONLY behind the Switch:
// flipping it off stashes the current preset, flipping it on restores it.
// Preset VALUES and label/description keys come from the shared registry
// `lib/utils/audioPresets.ts`; the canonical preset → filter mapping lives
// in `voice_typer/server/audio_presets.py` and is applied by the backend.

import { useEffect, useMemo, useRef, useState } from "react";
import { AudioFilterChain } from "@/components/audio/AudioFilterChain";
import {
	filterFactoryDefaults,
	MIC_ADVANCED_ROW_KEYS,
} from "@/components/audio/audioFilterRowDescriptors";
import { SelectableRow } from "@/components/common/SelectableRow";
import { InfoTooltip } from "@/components/feedback/InfoTooltip";
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
	/** Called when the user picks a stock preset (or Advanced). */
	onPresetChange: (preset: AudioPreset) => void;
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
}

// Resolve the shared registry's label/description keys through `t` (one
// lookup per key per mount, memoized per mount). Order is the row order:
// stock presets (minus "off" and Advanced), saved customs, Advanced last.
function getPresetOptions(customPresets: CustomMicPreset[]): PresetOption[] {
	const options: PresetOption[] = [];
	let advanced: PresetOption | null = null;
	for (const option of AUDIO_PRESET_OPTIONS) {
		if (option.value === "off") continue;
		const resolved: PresetOption = {
			value: option.value,
			label: t(option.labelKey),
			description: t(option.descriptionKey),
		};
		if (option.value === "custom") {
			advanced = resolved;
		} else {
			options.push(resolved);
		}
	}
	for (const custom of customPresets) {
		options.push({
			value: `custom:${custom.id}`,
			label: custom.name,
			description: "",
		});
	}
	if (advanced) options.push(advanced);
	return options;
}

// Stable identity for the "no saved presets" case: an inline `[]` default
// would be a fresh array on every render, invalidating the presetOptions
// memo each time (two t() lookups per key per mount instead of one).
const EMPTY_CUSTOM_PRESETS: CustomMicPreset[] = [];

export function PresetAccordionSelector({
	preset,
	config,
	onPresetChange,
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
	// Radio value: a selected saved preset addresses its own option,
	// everything else uses the preset name (incl. ad-hoc "custom").
	const radioValue =
		preset === "custom" && activeCustomPresetId
			? `custom:${activeCustomPresetId}`
			: preset;
	const activeCustom = activeCustomPresetId
		? (customPresets.find((c) => c.id === activeCustomPresetId) ?? null)
		: null;
	const enabled = preset !== "off";
	// Advanced is the ad-hoc custom row; only it opens the filter chain.
	// A saved user preset applies its recorded values, nothing to edit.
	const chainOpen = preset === "custom" && !activeCustomPresetId;

	// Remembers the last non-"off" option value so flipping the Switch back
	// on restores the user's choice instead of resetting to "auto".
	const lastNonOffRef = useRef<string>(preset === "off" ? "auto" : "");
	useEffect(() => {
		if (preset !== "off") {
			lastNonOffRef.current = radioValue;
		}
	}, [preset, radioValue]);

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
			if (radioValue === value) return;
			onSelectCustomPreset(id);
			return;
		}
		if (radioValue === value) return;
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
		<section className="flex flex-col gap-3 border-t border-border/8 bg-surface-subtle p-4">
			<div className="flex items-center gap-3">
				<div className="flex items-center gap-2 min-w-0">
					<span className="text-sm font-medium text-foreground">
						{t("settings.audioEnhancement.microphoneQuality")}
					</span>
					<InfoTooltip
						text={t("settings.audioEnhancement.microphoneQualityInfo")}
						contextLabel={t("settings.audioEnhancement.microphoneQuality")}
					/>
				</div>
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
				<RadioGroup
					value={radioValue}
					onValueChange={(v) => selectOption(v)}
					aria-label={t("settings.audioEnhancement.microphoneQualityAria")}
					className="gap-1"
					data-testid="mic-preset-radio-group"
				>
					{presetOptions.map((option) => (
						// The a11y pair (nested RadioGroupItem is the accessible
						// control; row click is pointer-only convenience) + the
						// skip-nested-button click gating (the radio AND the row's
						// InfoTooltip trigger are <button>s, clicking either must
						// never change the preset as a side effect) live in the
						// shared SelectableRow wrapper.
						<SelectableRow
							key={option.value}
							className={cn(
								"flex items-center gap-3 rounded-lg p-2 min-h-9 cursor-pointer transition-colors hover:bg-border/10",
								option.value === radioValue && "bg-foreground/5",
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
							{/* Title + its own info trigger form the left content
                                    group; the info icon sits immediately after the
                                    title (Settings pattern), never at the far end and
                                    never inside the radio's hit area. The inline span's
                                    stopPropagation (owned by InfoTooltip) keeps
                                    clicks/keys off the row handler. */}
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
			)}

			{chainOpen && (
				<div className="flex flex-col rounded-lg border border-border/8">
					<AudioFilterChain
						config={config}
						onConfigChange={onConfigChange}
						rowKeys={MIC_ADVANCED_ROW_KEYS}
					/>
					{/* Custom-preset actions: restore is always available
					    (idempotent); save enables the moment any value drifts
					    from the selection. */}
					<div className="flex flex-wrap items-center gap-2 px-4 pb-4 pt-2.5">
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
		</section>
	);
}
