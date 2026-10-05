// The model-idle-unload dropdown options, in the exact order the Settings
// → General row renders them.
//
// This file exists so the option list has ONE definition shared by the
// dropdown and its test. The value written to the backend is the number of
// minutes of dictation inactivity before the ASR model is dropped from
// memory; `0` is the sentinel that disables the timer entirely, which is
// why it is modelled as an option rather than as "off".
//
// 15 is the floor on purpose: below ~15 minutes a normal pause (a sip of
// coffee, a glance at chat) would evict the model and force a reload on
// the very next dictation, which is the exact failure the setting exists
// to avoid. 120 is the ceiling because it is where the memory trade stops
// being worth it for most machines.
//
// The labels are per-option i18n keys rather than one interpolated
// "{minutes} minutes" string, so each locale can express its own numeral
// and unit form without a plural-category table (C-I18N-1/2).

export interface ModelIdleUnloadOption {
	/** Minutes written to `model_idle_unload_minutes` (0 = never unload). */
	value: number;
	/** i18n key for this option's visible label. */
	labelKey: string;
}

export const MODEL_IDLE_UNLOAD_OPTIONS: readonly ModelIdleUnloadOption[] = [
	{ value: 15, labelKey: "settings.modelIdleUnload.minutes15" },
	{ value: 30, labelKey: "settings.modelIdleUnload.minutes30" },
	{ value: 60, labelKey: "settings.modelIdleUnload.minutes60" },
	{ value: 90, labelKey: "settings.modelIdleUnload.minutes90" },
	{ value: 120, labelKey: "settings.modelIdleUnload.minutes120" },
	{ value: 0, labelKey: "settings.modelIdleUnload.never" },
] as const;

/** Fallback when an older sidecar sends no `model_idle_unload_minutes`. */
export const DEFAULT_MODEL_IDLE_UNLOAD_MINUTES = 60;

/**
 * Normalise a config value into one the dropdown can select.
 *
 * An older sidecar may omit the field, and a hand-edited config.json may
 * hold something outside the offered range. Both collapse to the default
 * rather than rendering an empty trigger (a `Select` whose value matches no
 * item displays blank, which reads as a broken control).
 */
export function normalizeModelIdleUnloadMinutes(
	raw: number | undefined,
): number {
	if (typeof raw !== "number" || !Number.isFinite(raw)) {
		return DEFAULT_MODEL_IDLE_UNLOAD_MINUTES;
	}
	const match = MODEL_IDLE_UNLOAD_OPTIONS.find(
		(option) => option.value === raw,
	);
	return match ? match.value : DEFAULT_MODEL_IDLE_UNLOAD_MINUTES;
}
