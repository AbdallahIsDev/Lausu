// All provider state, IPC and actions in one hook. The page only composes
// chrome; each layout variant receives the derived view model and the same
// action set, so switching layouts never changes behaviour. Failures surface
// as in-app notifications (C-UXERR-2/4), never as inline verdict text.

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useLatestRef } from "@/hooks/useLatestRef";
import { usePython, usePythonEvent } from "@/hooks/usePython";
import { useT } from "@/i18n/i18n";
import type {
	Domain,
	OnnxState,
	ProviderListData,
	ProviderModel,
} from "./types";
import {
	buildViewModel,
	type ProviderActions,
	type ProviderViewModel,
} from "./viewModel";

/** IPC envelopes are `{ type, data }`; tolerate a bare payload too. */
function unwrap<T>(response: unknown): T {
	const envelope = response as { data?: T } | undefined;
	return (envelope?.data ?? (response as T)) as T;
}

export interface ProviderData {
	data: ProviderListData | null;
	model: ProviderViewModel | null;
	loadError: boolean;
	domainLabels: Record<string, string>;
	actions: ProviderActions;
	reload: () => Promise<void>;
}

export function useProviderData(): ProviderData {
	const t = useT();
	const { call } = usePython();
	// Mirror the bridge call: `call` identity can change per render, and a
	// `[call]` effect dep is the documented render-loop class.
	const callRef = useLatestRef(call);
	const [data, setData] = useState<ProviderListData | null>(null);
	const [catalogues, setCatalogues] = useState<Record<string, ProviderModel[]>>(
		{},
	);
	const [drafts, setDrafts] = useState<Record<string, string>>({});
	const [busy, setBusy] = useState<string | null>(null);
	const [onnx, setOnnx] = useState<OnnxState | null>(null);
	const [loadError, setLoadError] = useState(false);
	const requestIdRef = useRef(0);

	const domainLabels: Record<string, string> = {
		asr: t("providers.domainAsr"),
		tts: t("providers.domainTts"),
		llm: t("providers.domainLlm"),
	};

	const domainDescriptions: Record<Domain, string> = {
		asr: t("providers.domainAsrDesc"),
		tts: t("providers.domainTtsDesc"),
		llm: t("providers.domainLlmDesc"),
	};

	/** Plain-language copy for a provider failure (C-UXERR-1/3). */
	const errorCopy = (err: unknown): string => {
		const code = (err as { code?: unknown } | null)?.code;
		switch (code) {
			case "server.provider_auth_required":
				return t("providers.errorAuth");
			case "server.provider_unavailable":
				return t("providers.errorUnavailable");
			case "server.provider_consent_required":
				return t("providers.errorConsent");
			case "server.provider_runtime_error":
				return t("providers.errorRuntime");
			default:
				return t("providers.errorGeneric");
		}
	};

	// One request id: a reload or an unmount invalidates an older reply, so a
	// late failure can never overwrite a newer snapshot.
	const load = useCallback(async () => {
		requestIdRef.current += 1;
		const requestId = requestIdRef.current;
		setLoadError(false);
		try {
			const response = await callRef.current("provider_list");
			if (requestId !== requestIdRef.current) return;
			setData(unwrap<ProviderListData>(response));
		} catch {
			if (requestId !== requestIdRef.current) return;
			setLoadError(true);
		}
	}, [callRef]);

	useEffect(() => {
		void load();
		return () => {
			requestIdRef.current += 1;
		};
	}, [load]);

	usePythonEvent("provider_local_onnx_state", (payload) => {
		const state = payload as OnnxState | undefined;
		if (state) setOnnx(state);
	});

	const loadModels = useCallback(
		async (provider: string) => {
			const response = await callRef.current("provider_models", { provider });
			const payload = unwrap<{ models?: ProviderModel[] }>(response);
			setCatalogues((prev) => ({ ...prev, [provider]: payload.models ?? [] }));
		},
		[callRef],
	);

	const run = async (key: string, action: () => Promise<void>) => {
		setBusy(key);
		try {
			await action();
		} catch (err) {
			toast.error(errorCopy(err));
		} finally {
			setBusy(null);
		}
	};

	// A failed save keeps the draft so the user can fix it (C-UI-14); the
	// toast carries the reason, never text under the field.
	const saveKey = (provider: string) =>
		run(`key:${provider}`, async () => {
			await callRef.current("provider_set_key", {
				provider,
				key: drafts[provider] ?? "",
			});
			setDrafts((prev) => ({ ...prev, [provider]: "" }));
			await load();
			await loadModels(provider);
		});

	const clearKey = (provider: string) =>
		run(`key:${provider}`, async () => {
			await callRef.current("provider_clear_key", { provider });
			await load();
			setCatalogues((prev) => ({ ...prev, [provider]: [] }));
		});

	// Success needs no notification: the key status and catalogue refresh are
	// the visible result (C-UXERR-2).
	const testProvider = (provider: string) =>
		run(`test:${provider}`, async () => {
			await callRef.current("provider_test", { provider });
			await loadModels(provider);
		});

	const setDomain = (domain: Domain, patch: Record<string, unknown>) =>
		run(`domain:${domain}`, async () => {
			await callRef.current("provider_set_domain", { domain, ...patch });
			await load();
		});

	const onProviderChange = (domain: Domain, provider: string) =>
		run(`domain:${domain}`, async () => {
			await callRef.current("provider_set_domain", {
				domain,
				provider,
				model_id: "",
			});
			await load();
			await loadModels(provider);
		});

	/** Turning a domain on picks its first capable provider when none is set. */
	const onEnabledChange = (domain: Domain, enabled: boolean) => {
		const options = data?.providers.filter((provider) =>
			provider.domains.includes(domain),
		);
		const provider = enabled
			? data?.domains?.[domain]?.provider || options?.[0]?.id || ""
			: "";
		return run(`domain:${domain}`, async () => {
			await callRef.current("provider_set_domain", {
				domain,
				provider,
				enabled,
			});
			await load();
		});
	};

	const onnxNote = onnx?.model
		? onnx.state === "loading"
			? t("providers.onnxLoading", { model: onnx.model })
			: onnx.state === "failed"
				? t("providers.onnxFailed", { model: onnx.model })
				: onnx.state === "ready"
					? t("providers.onnxReady", { model: onnx.model })
					: null
		: null;

	const model: ProviderViewModel | null = data
		? buildViewModel({
				data,
				drafts,
				busy,
				catalogues,
				onnx,
				domainLabels,
				domainDescriptions,
				onnxNote,
			})
		: null;

	const actions: ProviderActions = {
		onDraftChange: (provider, value) =>
			setDrafts((prev) => ({ ...prev, [provider]: value })),
		onSave: (provider) => void saveKey(provider),
		onTest: (provider) => void testProvider(provider),
		onClear: (provider) => void clearKey(provider),
		onEnabledChange: (domain, enabled) => void onEnabledChange(domain, enabled),
		onProviderChange: (domain, provider) =>
			void onProviderChange(domain, provider),
		onModelChange: (domain, modelId) =>
			void setDomain(domain, {
				provider: data?.domains?.[domain]?.provider ?? "",
				model_id: modelId,
			}),
		onConsentChange: (domain, consent) => void setDomain(domain, { consent }),
	};

	return {
		data,
		model,
		loadError,
		domainLabels,
		actions,
		reload: load,
	};
}
