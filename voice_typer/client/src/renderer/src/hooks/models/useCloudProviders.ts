/**
 * useCloudProviders, cloud-provider API keys + connection-test slice.
 * Owns the actions that persist API keys and probe a provider's
 * reachability:
 *     API key never leaves the Python process (C-DATA-1 offline-app
 *     compliance) — the probe is an IPC call, not a renderer fetch.
 *
 * Every outcome is reported as a TOAST (`showSnack`). Nothing in this
 * hook feeds an inline status region any more: the old `testResults`
 * map rendered "Connection failed: 400 http_error" next to the Test
 * button, which was both unreadable (the backend token is not a
 * sentence) and in the wrong place (a transient outcome is not a
 * property of the form).
 */

import { useCallback, useState } from "react";
import type { PythonCall } from "@/hooks/usePython";
import { t } from "@/i18n/i18n";
import { consentBodyKey, openConsentGate } from "@/lib/consentGate";
import {
	type CloudModelRef,
	type CloudProviderKey,
	cloudModelLabel,
	connectionFailureKey,
	formatErrorMessage,
	getProviderLabel,
	isValidApiKeyFormat,
} from "@/lib/utils/models";
import type { LausuConfig } from "@/types/config";

// Type alias for the IPC `call` function (matches the pattern used by
// useModelConfig, useModelFolder, useModelDownload, etc.).

interface UseCloudProvidersArgs {
	showSnack: (
		message: string,
		kind: "success" | "error" | "warning" | "info",
	) => void;
	config: LausuConfig | null;
	apiKeys: Record<string, string>;
	updateConfig: (updates: Partial<LausuConfig>) => Promise<void>;
	/** Optimistic config-state merge after a successful activation, so
	 * the Active marker moves on the committed user action instead of
	 * waiting for the `config_changed` echo. Same pattern as
	 * `useModelSelection.selectModel`. */
	setConfig: React.Dispatch<React.SetStateAction<LausuConfig | null>>;
	call: PythonCall;
}

export interface UseCloudProvidersResult {
	/** Providers with a Test Connection probe in flight. Keyed by
	 * provider key; an absent entry means idle. Drives the Test button's
	 * spinner + disabled state. */
	testingProviders: Record<string, boolean>;
	/** The cloud model whose activation is being persisted (null = idle).
	 * Drives ONE row's Select-button spinner. */
	selectingCloudModel: CloudModelRef | null;
	saveApiKey: (provider: string) => Promise<void>;
	testConnection: (provider: string) => Promise<void>;
	/** Make one of a provider's models the active speech backend.
	 *  `provider` is narrowed to the catalogue's keys (unlike Save / Test,
	 *  which accept any string) because the activation ALSO lands in
	 *  `CloudModelRef`, and an unknown key there would render as a row
	 *  that cannot exist. */
	activateCloudModel: (
		provider: CloudProviderKey,
		modelId: string,
	) => Promise<void>;
}

// ── Helpers (module-level, `safeApiKey` is re-exported) ──────────────

/**
 *  helper: translate the cloud-provider key into the
 * matching `cloud_*_consent` config field. Returns the config key
 * (typed as a keyof LausuConfig so callers can index safely).
 * Exported so any presentational consumer reuses the SAME mapping
 * instead of re-declaring a drifting duplicate.
 */
export function consentKeyFor(provider: string): keyof LausuConfig {
	if (provider === "openai") return "cloud_openai_consent";
	if (provider === "groq") return "cloud_groq_consent";
	if (provider === "gemini") return "cloud_gemini_consent";
	return "cloud_deepgram_consent";
}

function apiKeyConfigField(provider: string): keyof LausuConfig {
	if (provider === "openai") return "openai_api_key";
	if (provider === "groq") return "groq_api_key";
	if (provider === "gemini") return "gemini_api_key";
	return "deepgram_api_key";
}

export function safeApiKey(value: string | undefined | null): string {
	return value && value !== "<redacted>" ? value : "";
}

/** The "that is not a key" copy, shared by Save Key and Test
 *  Connection so both reject the same input with the same wording. */
function invalidKeyMessage(provider: string): string {
	return t("models.snack.apiKeyInvalid", {
		provider: getProviderLabel(provider),
	});
}

/** What `persistKey` did, so each caller can word its own toast. */
type PersistOutcome = "empty" | "invalid" | "unchanged" | "saved";

// ── Hook ──────────────────────────────────────────────────────────────

export function useCloudProviders({
	showSnack,
	config,
	apiKeys,
	updateConfig,
	setConfig,
	call,
}: UseCloudProvidersArgs): UseCloudProvidersResult {
	const [testingProviders, setTestingProviders] = useState<
		Record<string, boolean>
	>({});
	const [selectingCloudModel, setSelectingCloudModel] =
		useState<CloudModelRef | null>(null);

	const markTesting = useCallback((provider: string, testing: boolean) => {
		setTestingProviders((prev) => {
			if (testing) return { ...prev, [provider]: true };
			if (!prev[provider]) return prev;
			const next = { ...prev };
			delete next[provider];
			return next;
		});
	}, []);

	// ── persistKey ───────────────────────────────────────────────────
	// The single validated write path for a provider's API key, shared
	// by Save Key and Test Connection (the probe reads the key from the
	// backend's live Config, so the key must be persisted before the
	// probe runs). Guards, in order:
	//   • empty, the input is empty (the user clicked Save without
	//     typing). The most dangerous case: `safeApiKey` substitutes
	//     `""` for the `<redacted>` sentinel on every config fetch, so
	//     the input is empty after navigating away and back even when a
	//     key IS stored, and an unguarded save would overwrite the
	//     stored secret with `""`.
	//   • invalid, the value cannot be a key for this provider
	//     (`isValidApiKeyFormat`). Rejected BEFORE the IPC round-trip:
	//     the credential store must never receive a value that no
	//     provider would ever mint.
	//   • unchanged, the user re-typed the exact persisted key. No-op
	//     (avoids a redundant IPC round-trip). The persisted key is read
	//     from `config` so we compare against the value the backend
	//     last acknowledged.
	const persistKey = useCallback(
		async (provider: string): Promise<PersistOutcome> => {
			const key = apiKeys[provider] ?? "";
			if (!key.trim()) return "empty";
			if (!isValidApiKeyFormat(provider, key)) return "invalid";
			const configKey = apiKeyConfigField(provider);
			const persisted = safeApiKey(config?.[configKey] as string | undefined);
			if (persisted && key === persisted) return "unchanged";
			await updateConfig({ [configKey]: key } as Partial<LausuConfig>);
			return "saved";
		},
		[apiKeys, config, updateConfig],
	);

	// ── maybeRequestConsent ──────────────────────────────────────────
	// The cloud audio-transmission consent is asked for at the point of
	// use, through the SAME shared consent dialog every other
	// consent-gated flow uses (`openConsentGate` → ConsentGateDialog),
	// not as a checkbox living inside the setup form. It fires once the
	// key is actually stored, and never again once granted.
	const maybeRequestConsent = useCallback(
		(provider: string) => {
			const field = consentKeyFor(provider);
			if (config?.[field]) return;
			openConsentGate({
				consentField: field,
				bodyKey: consentBodyKey(field),
			});
		},
		[config],
	);

	// ── Action: saveApiKey ───────────────────────────────────────────
	const saveApiKey = useCallback(
		async (provider: string) => {
			const outcome = await persistKey(provider);
			if (outcome === "empty") {
				showSnack(t("models.snack.apiKeyEmpty"), "info");
				return;
			}
			if (outcome === "invalid") {
				showSnack(invalidKeyMessage(provider), "error");
				return;
			}
			if (outcome === "unchanged") {
				showSnack(t("models.snack.apiKeyUnchanged"), "info");
				return;
			}
			showSnack(
				t("models.snack.apiKeySaved", {
					provider: getProviderLabel(provider),
				}),
				"success",
			);
			maybeRequestConsent(provider);
		},
		[persistKey, showSnack, maybeRequestConsent],
	);

	// ── Action: testConnection ──────────────────────────────────────
	// Persists first (the backend probe reads the key from the live
	// Config), then runs the probe and reports the outcome as a toast.
	// The failure branch maps the backend's stable token to readable
	// copy via `connectionFailureKey` — the token itself
	// ("http_error" / "auth_failed" / …) is not a sentence.
	//
	// The probe is routed through the Python backend IPC
	// (`test_cloud_connection`) so the API key never leaves the Python
	// process and the renderer stays network-free (C-DATA-1
	// offline-app compliance). The backend handler reads the key from
	// the live Config, makes the HTTP probe using urllib, and returns
	// { ok, status, message }.
	const testConnection = useCallback(
		async (provider: string) => {
			const outcome = await persistKey(provider);
			if (outcome === "empty") {
				showSnack(t("models.test.needApiKey"), "info");
				return;
			}
			if (outcome === "invalid") {
				showSnack(invalidKeyMessage(provider), "error");
				return;
			}
			if (outcome === "saved") maybeRequestConsent(provider);
			markTesting(provider, true);
			try {
				const result = await call<{
					ok: boolean;
					status: number;
					message: string;
				}>("test_cloud_connection", { provider });
				if (result.ok) {
					showSnack(t("models.test.connectionSuccessful"), "success");
				} else {
					showSnack(
						t(connectionFailureKey(result.message), {
							provider: getProviderLabel(provider),
							status: String(result.status),
						}),
						"error",
					);
				}
			} catch (err) {
				// `formatErrorMessage` only extracts the error's `message`
				// field, so the `Authorization` header value never reaches
				// the toast.
				showSnack(
					t("models.test.connectionTestFailed", {
						error: formatErrorMessage(err),
					}),
					"error",
				);
			} finally {
				markTesting(provider, false);
			}
		},
		[persistKey, showSnack, maybeRequestConsent, markTesting, call],
	);

	// ── Action: activateCloudModel ───────────────────────────────────
	// Make ONE of a provider's models the active speech backend.
	//
	// The three config fields are written TOGETHER, and that is the
	// whole point: `asr_backend` is a single value ("whisper" | "qwen" |
	// "parakeet" | "cloud"), so writing "cloud" is itself what
	// deactivates whichever LOCAL model was active — and picking a local
	// model later writes "whisper"/"qwen"/"parakeet", which deactivates
	// the cloud one. There is no second "active" flag anywhere, so
	// "exactly one active model across local and cloud" holds by
	// construction rather than by a rule that has to be enforced.
	//
	// `cloud_model` is always written explicitly (never left empty for
	// the backend to default): the Cloud row shows the provider's
	// DEFAULT model as active when `cloud_model` is empty, and an
	// explicit write keeps the row and the backend's resolved model in
	// lockstep.
	//
	// Guards, in order — both mirror the download flow's consent gate:
	//   • no stored key, the backend's CloudAsrBackend resolves to
	//     "not loaded" and `get_active()` silently falls back to
	//     whisper, so the user would "activate" a model that never
	//     runs. Refuse up front with the same "enter a key first" copy
	//     Test Connection uses.
	//   • no consent, open the SAME shared point-of-use consent dialog
	//     and retry the activation from its Allow button. The backend's
	//     own consent check remains the enforcement; this only changes
	//     when the requirement is surfaced.
	const commitActivation = useCallback(
		async (provider: CloudProviderKey, modelId: string) => {
			setSelectingCloudModel({ provider, model: modelId });
			const updates: Partial<LausuConfig> = {
				asr_backend: "cloud",
				cloud_provider: provider,
				cloud_model: modelId,
			};
			const label = cloudModelLabel(provider, modelId);
			try {
				await updateConfig(updates);
				// Optimistic merge, same pattern as
				// `useModelSelection.selectModel`: the Active marker must
				// move on the committed action, not on the transport echo.
				setConfig((prev) => (prev ? { ...prev, ...updates } : prev));
				showSnack(t("models.snack.usingModel", { name: label }), "success");
			} catch (err) {
				// Surface the failure instead of a success toast. Config
				// state is NOT merged (the `setConfig` call is above the
				// throw point only when the write succeeded), so the UI
				// stays in sync with what the backend actually persisted.
				showSnack(
					t("models.snack.selectFailed", {
						name: label,
						error: formatErrorMessage(err),
					}),
					"error",
				);
			} finally {
				setSelectingCloudModel(null);
			}
		},
		[updateConfig, setConfig, showSnack],
	);

	const activateCloudModel = useCallback(
		async (provider: CloudProviderKey, modelId: string) => {
			const configKey = apiKeyConfigField(provider);
			if (!safeApiKey(config?.[configKey] as string | undefined)) {
				showSnack(t("models.test.needApiKey"), "info");
				return;
			}
			const field = consentKeyFor(provider);
			if (!config?.[field]) {
				openConsentGate({
					consentField: field,
					bodyKey: consentBodyKey(field),
					onAllow: () => void commitActivation(provider, modelId),
				});
				return;
			}
			await commitActivation(provider, modelId);
		},
		[config, showSnack, commitActivation],
	);

	return {
		testingProviders,
		selectingCloudModel,
		saveApiKey,
		testConnection,
		activateCloudModel,
	};
}
