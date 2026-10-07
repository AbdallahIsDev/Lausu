// FilterRow, presentational per-row renderer for `<AudioFilterChain>`.
// the same `SettingRow + (Switch | RangeSlider | Select)` pattern
// repeated 24 times (16 sliders + 7 toggles + 1 select). This
// component renders ONE descriptor, the parent does a `.map` over
// the registry.
//Behaviour preservation (vs the pre- inline JSX):
//   - `<SettingRow label={...} info={...}>`, label is the resolved
//     i18n string from the labels dictionary; info is resolved via
//`t(descriptor.infoKey)` at render time (the pre- inline
//     `t("...Info")` call happened at render time too, kept here so
//the  memo test's per-render `t()` call pattern is
//     unchanged).
//   - Slider `value={config[k] ?? defaultValue}`, identical fallback.
//   - Slider `min/max/step/suffix/deferApply`, identical.
//   - Toggle `checked={config[k] ?? defaultValue}`, identical.
//   - Select `value={config[k] ?? defaultValue}` + options, identical.
//   - `parentToggle`, when set, the row stays VISIBLE and renders
//     its control disabled while the parent toggle is off (after
//     applying the parent's own defaultValue fallback). Locking
//     instead of unmounting keeps the dependent filters discoverable,
//     and the row unlocks the moment the parent toggle is enabled.

import { RangeSlider } from "@/components/common/RangeSlider";
import { SettingRow } from "@/components/common/SettingRow";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import type { LausuConfig } from "@/types/config";
import type { AudioFilterLabels } from "./audioFilterLabels";
import {
	type AudioFilterRowDescriptor,
	audioFilterDescriptorByConfigKey,
} from "./audioFilterRowDescriptors";

export type AudioFilterSet = <K extends keyof LausuConfig>(
	k: K,
	v: LausuConfig[K],
) => void;

export interface FilterRowProps {
	descriptor: AudioFilterRowDescriptor;
	config: LausuConfig;
	set: AudioFilterSet;
	labels: AudioFilterLabels;
	/**
	 * Lock the control from outside the descriptor's `parentToggle`
	 * relation, used by the Settings page while the preset is not
	 * `custom` (the whole chain is visible but inert then).
	 */
	disabled?: boolean;
}

function readRowValue(
	config: LausuConfig,
	descriptor: AudioFilterRowDescriptor,
): number | boolean | string {
	const raw = config[descriptor.configKey];
	if (raw === undefined) return descriptor.defaultValue;
	return raw as number | boolean | string;
}

function parentToggleActive(
	config: LausuConfig,
	parentToggle: AudioFilterRowDescriptor["parentToggle"],
): boolean {
	if (!parentToggle) return true;
	const parentDescriptor = audioFilterDescriptorByConfigKey.get(
		parentToggle as string,
	);
	const parentDefault = parentDescriptor?.defaultValue ?? true;
	const parentRaw = config[parentToggle];
	return Boolean(parentRaw ?? parentDefault);
}

export function FilterRow({
	descriptor,
	config,
	set,
	labels,
	disabled = false,
}: FilterRowProps): React.ReactNode {
	// A dependent filter row is locked (not unmounted) while its parent
	// toggle is off, so the row is still discoverable and unlocks as soon
	// as the parent is enabled.
	const locked =
		disabled || !parentToggleActive(config, descriptor.parentToggle);

	const label = labels[descriptor.labelKey] ?? descriptor.labelKey;
	// Resolve info/aria strings from the memoized labels bundle
	// (built once per locale by buildAudioFilterLabels) instead of
	// calling t() at render time, zero t() calls on re-render.
	const info = labels[descriptor.infoKey] ?? descriptor.infoKey;
	const aria = labels[descriptor.ariaKey] ?? descriptor.ariaKey;
	const value = readRowValue(config, descriptor);

	// `descriptor.configKey` is `keyof LausuConfig` (widened) —
	// `set`'s generic K can't be inferred from a non-literal, so we
	// cast through `never` (assignable to any `LausuConfig[K]`).
	// Call sites that pass a literal configKey still get full type
	// safety; the registry path is the only one that needs the cast.
	const write = (v: number | boolean | string): void => {
		set(descriptor.configKey, v as never);
	};

	switch (descriptor.kind) {
		case "toggle":
			return (
				<SettingRow label={label} info={info}>
					<Switch
						checked={value as boolean}
						onCheckedChange={(v: boolean) => write(v)}
						aria-label={aria}
						disabled={locked}
					/>
				</SettingRow>
			);
		case "slider":
			return (
				<SettingRow label={label} info={info}>
					<RangeSlider
						value={value as number}
						min={descriptor.min ?? 0}
						max={descriptor.max ?? 100}
						step={descriptor.step ?? 1}
						onChange={(v: number) => write(v)}
						ariaLabel={aria}
						suffix={descriptor.suffix ?? ""}
						disabled={locked}
						deferApply
					/>
				</SettingRow>
			);
		case "select":
			return (
				<SettingRow label={label} info={info}>
					<Select
						value={value as string}
						disabled={locked}
						onValueChange={(v: string) => write(v)}
					>
						<SelectTrigger className="w-40" aria-label={aria}>
							<SelectValue />
						</SelectTrigger>
						<SelectContent>
							{(descriptor.options ?? []).map((opt) => (
								<SelectItem key={opt.value} value={opt.value}>
									{opt.labelKey
										? (labels[opt.labelKey] ?? opt.labelKey)
										: opt.label}
								</SelectItem>
							))}
						</SelectContent>
					</Select>
				</SettingRow>
			);
	}
}
