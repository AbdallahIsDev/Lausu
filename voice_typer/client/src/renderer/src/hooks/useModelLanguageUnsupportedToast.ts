// useModelLanguageUnsupportedToast, surfaces the
// ``model_language_unsupported`` push event as one actionable toast.
//
// The backend refuses the dictation start when the pinned spoken language
// is outside the active model's own language list (Parakeet Ultra has no
// Arabic, for example), and publishes the raw ``{model, language}`` pair.
// The language NAME comes from the renderer's own language labels, so the
// message needs no second translation table, and the action lands the user
// on the page where the fix lives (C-UXERR-4).

import { usePythonEvent } from "@/hooks/usePython";
import type { TranslateFn } from "@/i18n/translate-types";
import { LANGUAGE_LABEL_KEYS } from "@/lib/utils/languages";
import { SNACKBAR_DEFAULT_DURATION_MS, useSnackbar } from "./useSnackbar";

function languageName(t: TranslateFn, code: string): string {
	const labelKey = LANGUAGE_LABEL_KEYS[code];
	if (labelKey) {
		const label = t(labelKey);
		if (label !== labelKey) return label;
	}
	return code.toUpperCase();
}

export function useModelLanguageUnsupportedToast(
	t: TranslateFn,
	onOpenModels: () => void,
): void {
	const { showSnack } = useSnackbar();
	usePythonEvent(
		"model_language_unsupported",
		(data): (() => void) | undefined => {
			const payload = (data ?? {}) as { model?: unknown; language?: unknown };
			const model = typeof payload.model === "string" ? payload.model : "";
			const language =
				typeof payload.language === "string" ? payload.language : "";
			if (!model || !language) return undefined;

			showSnack(
				t("degradation.modelLanguageUnsupported", {
					model,
					language: languageName(t, language),
				}),
				"warning",
				{
					id: `model-language-unsupported:${model}:${language}`,
					description: t("degradation.modelLanguageUnsupportedHint"),
					duration: SNACKBAR_DEFAULT_DURATION_MS.error,
					action: {
						label: t("common.openModels"),
						onClick: onOpenModels,
					},
				},
			);
			return undefined;
		},
	);
}
