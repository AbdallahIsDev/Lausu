// The Microphone page shows the denoiser that is actually running, not the
// one the config asks for (C-UI-15). A fallback backend (a missing runtime, a
// preload that never landed) is invisible in `config.noise_suppression_method`,
// which is how "DPDFNet is on" could coexist with a meter a third its size for
// a whole session (docs/microphone-filter-failures.md §3.2).
//
// The backend reports the truth on the existing `get_status` payload. The page
// configures the METER chain, whose block is `level_monitor_noise_suppression`
// (`noise_suppression` is the dictation chain, used only as a fallback when the
// meter has no chain at all). The block is re-read while mounted, because the
// preload lands mid-session and promotes the chain under a live page; the note
// then has to disappear on its own. Informational only: every failure resolves
// to "no note".

import { useEffect, useState } from "react";
import { audioFilterDescriptorByConfigKey } from "@/components/audio/audioFilterRowDescriptors";
import { useLatestRef } from "@/hooks/useLatestRef";
import { usePython } from "@/hooks/usePython";
import { t } from "@/i18n/i18n";

export interface NoiseSuppressionStatus {
	requested: string;
	effective: string;
	degraded: boolean;
	reason_code: string;
}

const METHOD_SELECT_KEY = "noise_suppression_method";

/** User-facing name for a method id, from the selector's own option labels. */
export function denoiserLabel(method: string): string {
	const options =
		audioFilterDescriptorByConfigKey.get(METHOD_SELECT_KEY)?.options ?? [];
	const option = options.find((candidate) => candidate.value === method);
	if (!option) return method.toUpperCase();
	return option.labelKey ? t(option.labelKey) : (option.label ?? method);
}

/**
 * Plain-language note when the chain serves a different denoiser than the one
 * selected, else `null`. `requestedMethod` re-reads the status when the user
 * picks another method.
 */
export function useDenoiserFallbackNote(
	requestedMethod: string | null | undefined,
): string | null {
	const { call } = usePython();
	// Latest-ref mirror: `call` must never be an effect dep (OOM-loop class).
	const callRef = useLatestRef(call);
	const [note, setNote] = useState<string | null>(null);

	// biome-ignore lint/correctness/useExhaustiveDependencies: callRef is a useLatestRef mirror (reading .current in a stale closure is its documented contract, .current must NOT become a dep); requestedMethod is the deliberate re-read trigger, not a body value
	useEffect(() => {
		let cancelled = false;
		let timer: ReturnType<typeof setInterval> | undefined;

		const read = async () => {
			try {
				const status = await callRef.current<{
					noise_suppression?: NoiseSuppressionStatus | null;
					level_monitor_noise_suppression?: NoiseSuppressionStatus | null;
				}>("get_status");
				if (cancelled) return;
				const reported =
					status?.level_monitor_noise_suppression ?? status?.noise_suppression;
				if (!reported?.degraded) {
					setNote(null);
					// A chain cannot un-promote: once the truth is reported there is
					// nothing left to wait for.
					if (timer !== undefined) clearInterval(timer);
					return;
				}
				setNote(
					t("settings.audioEnhancement.denoiserFallback", {
						requested: denoiserLabel(reported.requested),
						effective: denoiserLabel(reported.effective),
					}),
				);
			} catch {
				/* informational only: a failed read must never break the page */
			}
		};

		setNote(null);
		void read();
		timer = setInterval(() => void read(), 3000);
		return () => {
			cancelled = true;
			if (timer !== undefined) clearInterval(timer);
		};
	}, [requestedMethod]);

	return note;
}
