// Shared microphone-quality audio preset options.
// Single source of truth for the five `audio_preset` values the backend
// accepts (defined in `voice_typer/server/audio_presets.py`, the
// preset → filter-chain mapping lives server-side per ADR 0007) and
// their i18n label/description keys. Used by BOTH live preset
// presentations:
//   - the Settings → Audio "Microphone Quality" Select
//     (components/settings/AudioSettingsSection.tsx)
//   - the Microphone page's accordion + RadioGroup selector
//     (pages/microphone/components/PresetAccordionSelector.tsx)
// This module holds DATA only (values + translation keys, typed against
// the `TranslationKey` union so a typo'd or missing key is a compile
// error). Each presentation resolves the keys through its own `t`
// binding (the Settings section uses the reactive `useT()` hook; the
// Microphone-page accordion uses the plain `t` import inside a
// mount-once `useMemo`), so locale reactivity stays exactly as each
// surface had it before the consolidation.
// The label/description keys live under `settings.audioEnhancement.preset*`
// in the locale catalogues, ONE key family shared by every surface.
import type { TranslationKey } from "@/i18n";

/** Value stored in `config.hallucination_filter_mode`. */
export type HallucinationFilterMode = "strict" | "balanced" | "off";

/**
 * Single source of truth for the low-audio hallucination filter modes.
 * The backend enum lives in `voice_typer/server/hallucination.py`
 * (`HALLUCINATION_FILTER_MODES`) and is mirrored by the SEC-002 IPC
 * allowlist entry; a round-trip test keeps this list in lockstep with it.
 *
 * "balanced" is the shipped default: it keeps the catalog phrases that are
 * also real dictation ("so", "you", "bye") unless the decoder confirms
 * silence, which removes the false positives of the previous strict-only
 * behaviour without giving up the obvious artifacts ("thanks for watching").
 * "off" disables the gate entirely.
 */
export interface HallucinationFilterModeOption {
	value: HallucinationFilterMode;
	labelKey: TranslationKey;
	descriptionKey: TranslationKey;
}

export const HALLUCINATION_FILTER_MODE_OPTIONS: readonly HallucinationFilterModeOption[] =
	[
		{
			value: "balanced",
			labelKey: "settings.audioEnhancement.hallucinationBalanced",
			descriptionKey:
				"settings.audioEnhancement.hallucinationBalancedDescription",
		},
		{
			value: "strict",
			labelKey: "settings.audioEnhancement.hallucinationStrict",
			descriptionKey:
				"settings.audioEnhancement.hallucinationStrictDescription",
		},
		{
			value: "off",
			labelKey: "settings.audioEnhancement.hallucinationOff",
			descriptionKey: "settings.audioEnhancement.hallucinationOffDescription",
		},
	];

/** Microphone-quality preset value stored in `config.audio_preset`. */
export type AudioPreset = "auto" | "studio" | "noisy_room" | "off" | "custom";

/** One preset option: value + the i18n keys for its label and description. */
export interface AudioPresetOption {
	value: AudioPreset;
	labelKey: TranslationKey;
	descriptionKey: TranslationKey;
}

export const AUDIO_PRESET_OPTIONS: readonly AudioPresetOption[] = [
	{
		value: "auto",
		labelKey: "settings.audioEnhancement.presetAuto",
		descriptionKey: "settings.audioEnhancement.presetAutoDescription",
	},
	{
		value: "studio",
		labelKey: "settings.audioEnhancement.presetStudio",
		descriptionKey: "settings.audioEnhancement.presetStudioDescription",
	},
	{
		value: "noisy_room",
		labelKey: "settings.audioEnhancement.presetNoisyRoom",
		descriptionKey: "settings.audioEnhancement.presetNoisyRoomDescription",
	},
	{
		value: "off",
		labelKey: "settings.audioEnhancement.presetOff",
		descriptionKey: "settings.audioEnhancement.presetOffDescription",
	},
	{
		value: "custom",
		labelKey: "settings.audioEnhancement.presetCustom",
		descriptionKey: "settings.audioEnhancement.presetCustomDescription",
	},
] as const;
