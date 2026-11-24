import {
	type RefObject,
	useCallback,
	useEffect,
	useRef,
	useState,
} from "react";
import { useLatestRef } from "@/hooks/useLatestRef";
import { useNavigation } from "@/hooks/useNavigation";
import { usePython, usePythonEvent } from "@/hooks/usePython";
import { useSnackbar } from "@/hooks/useSnackbar";
import { t } from "@/i18n/i18n";
import { consentBodyKey, openConsentGate } from "@/lib/consentGate";
import {
	CLOUD_PROVIDERS,
	type CloudProviderKey,
	cloudDefaultModel,
} from "@/lib/utils/cloudCatalog";
import type { LausuConfig } from "@/types/config";
import { HOTKEY_DEFAULT, MODEL_DEFAULT } from "../lib/constants";
import type { ModelOption, StepInfo } from "../lib/types";

// The seven consent flags surfaced on the consolidated Consent step
// (voice biometric, HuggingFace, configured cloud ASR,
// LLM polish). Module-level so useCallbacks/effects can list it as a
// stable dep without re-creating the array every render.
const CONSENT_FIELDS = [
	"voice_biometric_consent",
	"huggingface_consent",
	"cloud_openai_consent",
	"cloud_groq_consent",
	"cloud_deepgram_consent",
	"cloud_gemini_consent",
	"llm_polish_consent",
] as const;

export type BackendChoice = "local" | "cloud";

// Map a cloud provider to its allowlisted config fields (mirrors
// `useCloudProviders.ts`, the Models page cloud tab uses the same
// mapping, so the onboarding Cloud panel persists to the SAME config
// keys the user would set there).
function cloudConsentField(provider: string): string {
	if (provider === "openai") return "cloud_openai_consent";
	if (provider === "groq") return "cloud_groq_consent";
	if (provider === "gemini") return "cloud_gemini_consent";
	return "cloud_deepgram_consent";
}

/** The provider's API-key config field. Typed as the exact union rather
 *  than `string` so the activation `updates` object can be a
 *  `Partial<LausuConfig>` and stay type-checked at the write site. */
function cloudApiKeyField(
	provider: string,
): "openai_api_key" | "groq_api_key" | "gemini_api_key" | "deepgram_api_key" {
	if (provider === "openai") return "openai_api_key";
	if (provider === "groq") return "groq_api_key";
	if (provider === "gemini") return "gemini_api_key";
	return "deepgram_api_key";
}

function isCloudProvider(provider: string): provider is CloudProviderKey {
	return CLOUD_PROVIDERS.some((entry) => entry.key === provider);
}

/** The ``asr_backend`` a local model selection activates: the entry's own
 *  registry ``backend``, narrowed to the values ``asr_backend`` accepts
 *  (the Whisper family, distil variants included, is all ``"whisper"``).
 *  Falls back to ``"whisper"`` when the entry carries no backend, which is
 *  the curated-only path of an older backend. Mirrors the Models page's
 *  ``selectModel``, which derives the same value from ``ModelInfo.backend``
 *  — the wizard cannot use that field directly because its model list comes
 *  from the onboarding catalog, not from the disk-status IPC. */
function backendForModelName(
	options: ModelOption[],
	name: string,
): LausuConfig["asr_backend"] {
	const backend = options.find((m) => m.name === name)?.backend;
	if (backend === "whisper" || backend === "qwen" || backend === "parakeet") {
		return backend;
	}
	return "whisper";
}

/** Extract the fulfilled value of a settled content-fetch result,
 *  re-throwing the rejection reason. The three content fetches
 *  (hotkey presets / model options / model catalog) are fatal, a
 *  rejection surfaces as ``initError`` via the init effect's outer
 *  catch, exactly like the pre-parallel sequential code. Only the
 *  ``get_config`` probe is non-fatal by design (its own inline
 *  ``.catch`` resolves to ``null``), so it never travels through
 *  here. */
function unwrapContent<T>(outcome: PromiseSettledResult<T>): T {
	if (outcome.status === "rejected") throw outcome.reason;
	return outcome.value;
}

export interface UseOnboardingWizardResult {
	loading: boolean;
	initError: string | null;
	step: StepInfo | null;
	submitting: boolean;
	applyError: boolean;
	selectedHotkey: string;
	setSelectedHotkey: (v: string) => void;
	selectedModel: string;
	setSelectedModel: (v: string) => void;
	hotkeyPresets: string[];
	modelOptions: ModelOption[];
	headingRef: RefObject<HTMLHeadingElement | null>;
	retryInit: () => void;
	handleNext: () => Promise<void>;
	handleApply: () => Promise<void>;
	handlePrev: () => Promise<void>;
	// Consent step: consolidated grant of every consent flag.
	consents: Record<string, boolean>;
	setConsentField: (field: string, value: boolean) => void;
	handleAgreeToAll: () => void;
	// Model step: local-vs-cloud choice + explicit download.
	selectedBackend: BackendChoice;
	setSelectedBackend: (v: BackendChoice) => void;
	downloadingModel: string | null;
	downloadProgress: number;
	downloadFailed: boolean;
	/** Per-model disk truth from `get_model_status` (shared is-installed logic). */
	modelStatus: Record<string, { downloaded: boolean }>;
	/** Input devices from `onboarding_get_microphones` (0 = show recovery). */
	microphoneCount: number;
	checkMicrophones: () => Promise<void>;
	/** Finish with backend defaults through the existing skip completion path. */
	handleSkip: () => Promise<void>;
	/** Request a per-model download. Opens the point-of-use
	 * HuggingFace consent gate when the consent isn't granted yet; the
	 * gate's Allow continues the download. Returns immediately (the
	 * transfer's lifecycle is observable via downloadingModel /
	 * downloadProgress). */
	handleDownload: (model: string) => void;
	// Model step: cloud provider configuration (API key). The consent for
	// the provider is NOT a checkbox on the step: it is requested at the
	// point of use through the shared gate when the user leaves the step
	// (see `guardCloudConsent`), exactly like the Models page's activation.
	cloudProvider: string;
	setCloudProvider: (v: string) => void;
	cloudApiKey: string;
	setCloudApiKey: (v: string) => void;
}

export function useOnboardingWizard(
	onComplete?: () => void,
): UseOnboardingWizardResult {
	const { call } = usePython();
	const { showSnack } = useSnackbar();
	const { replace } = useNavigation();

	// Ref mirror of `call` so the init effect depends only on
	// `retryCounter`. Test mocks may return a FRESH call per render, an
	// effect dep on it re-fires init() (onboarding_start/get_config/… →
	// setState → re-render → new call → loop → worker OOM). Same
	// pattern as useVocabulary.ts.
	const callRef = useLatestRef(call);

	const [loading, setLoading] = useState(true);
	const [initError, setInitError] = useState<string | null>(null);
	const [step, setStep] = useState<StepInfo | null>(null);
	const [retryCounter, setRetryCounter] = useState(0);
	const [submitting, setSubmitting] = useState(false);
	const [applyError, setApplyError] = useState(false);

	const [selectedHotkey, setSelectedHotkey] = useState(HOTKEY_DEFAULT);
	const [selectedModel, setSelectedModel] = useState(MODEL_DEFAULT);
	const [hotkeyPresets, setHotkeyPresets] = useState<string[]>([]);
	const [modelOptions, setModelOptions] = useState<ModelOption[]>([]);

	// Model step: the user chooses a local model (downloaded explicitly
	// per model, the app NEVER auto-downloads) or a cloud transcription
	// API.
	const [selectedBackend, setSelectedBackend] =
		useState<BackendChoice>("local");
	// Explicit in-wizard download progress (per-model).
	const [downloadingModel, setDownloadingModel] = useState<string | null>(null);
	const [downloadProgress, setDownloadProgress] = useState(0);
	const [downloadFailed, setDownloadFailed] = useState(false);
	const [modelStatus, setModelStatus] = useState<
		Record<string, { downloaded: boolean }>
	>({});
	const [microphoneCount, setMicrophoneCount] = useState(0);
	// Cloud panel: the provider + its API key. Consent is not stored here,
	// it lives in `consents` under the provider's own field (see
	// `guardCloudConsent`), so the wizard has exactly ONE source for every
	// consent flag.
	const [cloudProvider, setCloudProvider] = useState("openai");
	// This step doesn't offer cloud-model selection, so retain an existing
	// model for the same provider rather than resetting it on resume.
	const [savedCloudConfig, setSavedCloudConfig] = useState<{
		provider: CloudProviderKey;
		model: string;
	} | null>(null);
	// Keep secrets out of renderer state: get_config replaces configured API
	// keys with <redacted>. An empty field is omitted from set_config below,
	// preserving any key already stored in the backend.
	const [cloudApiKey, setCloudApiKey] = useState("");

	// Consent step: the six consent flags shown on the consolidated
	// Consent step (see module-level CONSENT_FIELDS). Keyed by config
	// field; initial state loaded from get_config (so a re-run or a
	// user who already granted via Settings → Privacy sees the real
	// state).
	const [consents, setConsents] = useState<Record<string, boolean>>({});

	// Persist a single consent toggle immediately (mirrors the
	// Settings Privacy page's rows: optimistic set + revert on
	// persistence failure so the UI never claims a grant that wasn't
	// saved).
	const setConsentField = useCallback(
		(field: string, value: boolean) => {
			setConsents((prev) => ({ ...prev, [field]: value }));
			call("set_config", { [field]: value }).catch((e) => {
				console.error(
					"[renderer:useOnboardingWizard] set_config consent failed:",
					e,
				);
				// Revert on failure so the UI doesn't claim a grant
				// that wasn't persisted.
				setConsents((prev) => ({ ...prev, [field]: !value }));
			});
		},
		[call],
	);

	// Grant every consent at once (single batched set_config, same
	// six fields as the Settings Privacy page's "Agree to All").
	// CONSENT_FIELDS is a module-level const, a stable dep.
	const handleAgreeToAll = useCallback(() => {
		const all = Object.fromEntries(CONSENT_FIELDS.map((f) => [f, true]));
		setConsents((prev) => ({ ...prev, ...all }));
		call("set_config", all).catch((e) => {
			console.error(
				"[renderer:useOnboardingWizard] set_config agree-to-all failed:",
				e,
			);
		});
		// CONSENT_FIELDS is a module-level const, biome treats it
		// as stable and flags listing it as a dep as unnecessary.
	}, [call]);

	const headingRef = useRef<HTMLHeadingElement | null>(null);

	/** Re-probe input devices from the existing onboarding IPC. Read-only;
	 *  a failure means "unknown", never a claim that a mic is missing. */
	const checkMicrophones = useCallback(async () => {
		try {
			const reply = await call<{ microphones?: unknown[] }>(
				"onboarding_get_microphones",
			);
			setMicrophoneCount(
				Array.isArray(reply?.microphones) ? reply.microphones.length : 0,
			);
		} catch (err) {
			console.warn("[renderer:useOnboardingWizard] mic probe failed:", err);
		}
	}, [call]);

	const retryInit = useCallback(() => {
		setInitError(null);
		setLoading(true);
		setStep(null);
		setRetryCounter((c) => c + 1);
	}, []);

	// biome-ignore lint/correctness/useExhaustiveDependencies: callRef is a useLatestRef mirror: reading .current in a stale closure is the hook's documented contract, .current must NOT become a dep
	useEffect(() => {
		void retryCounter;
		let cancelled = false;
		async function init() {
			try {
				const started = await callRef.current<StepInfo>("onboarding_start");
				if (cancelled) return;
				setStep(started);
				// Pre-fill the selections from the saved config on
				// EVERY start, first-run AND resume. A previous
				// version skipped the get_config override when
				// ``step > 0`` (the "resume" heuristic), so a wizard
				// opened mid-way (e.g. after "Re-run setup wizard",
				// or a quit mid-onboarding) showed the renderer
				// defaults instead of the user's saved hotkey/model,
				// and hitting Continue then pushed those defaults back
				// to the backend, clobbering the restored selections.
				// The saved config is the best available source of the
				// user's intent.
				// The four payloads are fetched in PARALLEL (the
				// Dashboard pattern, same as
				// pages/dashboard/hooks/useDashboardData.ts):
				// so the wizard's first-run content waited for the
				// SUM of all five latencies. `onboarding_start`
				// stays sequential (it creates the backend
				// onboarding session the other commands read
				// from). `get_config` keeps its non-fatal
				// semantics: a failed probe resolves to `null`
				// and the wizard continues without prefill
				// (the original inner try/catch, preserved).
				// The batch settles via `Promise.allSettled`
				// (not `Promise.all`) so the CONFIG PREFILL is
				// applied on its own success even when a
				// content fetch rejects. The first
				// content-fetch rejection still surfaces as
				// `initError` exactly as before: each result
				// is unwrapped in the original apply order
				// below, re-throwing its reason into the outer
				// catch.
				const [
					cfgOutcome,
					presetsOutcome,
					modelsOutcome,
					catalogOutcome,
					statusOutcome,
					micOutcome,
				] = await Promise.allSettled([
					callRef.current<LausuConfig>("get_config").catch((e) => {
						console.warn(
							"[renderer:useOnboardingWizard] get_config probe failed:",
							e,
						);
						return null;
					}),
					callRef.current<{ presets: string[] }>(
						"onboarding_get_hotkey_presets",
					),
					callRef.current<{ models: ModelOption[] }>(
						"onboarding_get_model_options",
					),
					callRef.current<{ models: ModelOption[] }>("get_model_catalog"),
					// Disk truth + input devices are advisory: a failure must
					// not block the wizard (the error surface owns outages).
					callRef
						.current<Record<string, { downloaded: boolean }>>(
							"get_model_status",
						)
						.catch(() => ({})),
					callRef
						.current<{ microphones?: unknown[] }>("onboarding_get_microphones")
						.catch(() => ({ microphones: [] })),
				]);
				if (cancelled) return;
				// `get_config` never rejects (its inline .catch
				// resolves to `null`), the ternary only
				// narrows the allSettled result type.
				const cfg = cfgOutcome.status === "fulfilled" ? cfgOutcome.value : null;
				// Apply the config prefill BEFORE the catalog merge so
				// the merge can no-op when the saved selection is
				// already present.
				if (cfg) {
					const cfgHotkey = cfg.hotkey ?? HOTKEY_DEFAULT;
					if (cfgHotkey) setSelectedHotkey(cfgHotkey);
					const cfgModel = cfg.model_size ?? MODEL_DEFAULT;
					if (cfgModel) setSelectedModel(cfgModel);
					// Resume the saved backend/provider instead of silently
					// switching a cloud setup back to local/OpenAI when the
					// user continues the wizard. API keys remain blank because
					// get_config redacts their values; blank keys are omitted
					// from the later set_config payload.
					const savedCloudProvider = isCloudProvider(cfg.cloud_provider)
						? cfg.cloud_provider
						: null;
					setCloudProvider(savedCloudProvider ?? "openai");
					setSavedCloudConfig(
						savedCloudProvider === null
							? null
							: {
									provider: savedCloudProvider,
									model:
										typeof cfg.cloud_model === "string" ? cfg.cloud_model : "",
								},
					);
					setSelectedBackend(
						cfg.asr_backend === "cloud" && savedCloudProvider !== null
							? "cloud"
							: "local",
					);
					// Pre-fill the consolidated consent step from the
					// saved config (re-run / already-granted users).
					const savedConsents: Record<string, boolean> = {};
					for (const f of CONSENT_FIELDS) {
						// `CONSENT_FIELDS` is `as const`, every literal is a
						// real LausuConfig boolean field, so index it
						// directly (no unsafe Record cast).
						savedConsents[f] = cfg[f] === true;
					}
					setConsents(savedConsents);
				}
				// Unwrap each content result in the original
				// apply order, re-throwing the first rejection
				// reason so it surfaces as initError via the
				// outer catch — a failure AFTER the prefill
				// block no longer discards the prefill (state
				// applied before the throw stays applied,
				const presets = unwrapContent(presetsOutcome);
				setHotkeyPresets(presets.presets || []);
				const models = unwrapContent(modelsOutcome);
				// Merge the full rich-metadata catalog
				// (``get_model_catalog`` →
				// ``ModelHandlers._handle_get_model_catalog``) into the
				// curated options list so the Model step's accordion can
				// group by family like the Models page does. The
				// curated list stays the fallback (older backends /
				// a failed catalog fetch), no duplicate names.
				const catalog = unwrapContent(catalogOutcome);
				setModelOptions(
					mergeModelOptions(models.models || [], catalog.models || []),
				);
				const modelState =
					statusOutcome.status === "fulfilled" ? statusOutcome.value : {};
				setModelStatus(modelState ?? {});
				const micReply =
					micOutcome.status === "fulfilled" ? micOutcome.value : null;
				setMicrophoneCount(
					Array.isArray(micReply?.microphones)
						? micReply.microphones.length
						: 0,
				);
			} catch (err) {
				if (cancelled) return;
				// Already finished: go Home silently, no card and no toast.
				if (
					(err as { code?: unknown } | null)?.code ===
					"client.onboarding_already_complete"
				) {
					replace("home");
					return;
				}
				console.error(
					"[renderer:useOnboardingWizard] Failed to start onboarding:",
					err,
				);
				setInitError(
					err instanceof Error ? err.message : t("errorBoundary.unknownError"),
				);
			} finally {
				if (!cancelled) setLoading(false);
			}
		}
		init();
		return () => {
			cancelled = true;
		};
	}, [retryCounter]);

	useEffect(() => {
		if (!step) return;
		queueMicrotask(() => {
			headingRef.current?.focus();
		});
	}, [step]);

	// Explicit in-wizard model download, PER MODEL. The app NEVER
	// downloads automatically; the user clicks Download on a specific
	// model item. HuggingFace consent is requested at the point of use
	// via the shared consent gate (openConsentGate, C-MIC-3): the gate
	// dialog's Allow persists ``huggingface_consent`` on the backend and
	// continues the action. ``handleDownload`` guards the gate, mirrors
	// the grant into the wizard's consent state (so the Privacy step
	// shows the persisted grant), and re-enters ``startDownload`` —
	// the split avoids the stale-closure re-gate loop a naive retry
	// would hit (the callback's ``consents`` snapshot is still false).
	const startDownload = useCallback(
		async (model: string) => {
			setDownloadFailed(false);
			setDownloadingModel(model);
			setDownloadProgress(0);
			try {
				await call("download_model", { model });
			} catch (err) {
				console.error(
					"[renderer:useOnboardingWizard] model download failed:",
					err,
				);
				setDownloadFailed(true);
			} finally {
				setDownloadingModel(null);
			}
		},
		[call],
	);

	const handleDownload = useCallback(
		(model: string) => {
			if (!model || downloadingModel) return;
			if (consents.huggingface_consent !== true) {
				openConsentGate({
					consentField: "huggingface_consent",
					bodyKey: "consentDialog.field.huggingface_consent",
					onAllow: () => {
						// Mirror the gate's persisted grant into the wizard
						// state (idempotent with the dialog's own set_config;
						// keeps the Privacy step + this step in agreement),
						// then continue the download the user asked for.
						setConsents((prev) => ({
							...prev,
							huggingface_consent: true,
						}));
						void startDownload(model);
					},
				});
				return;
			}
			void startDownload(model);
		},
		[consents.huggingface_consent, downloadingModel, startDownload],
	);

	usePythonEvent(
		"download_progress",
		useCallback((data: Record<string, unknown> | undefined) => {
			if (!data) return undefined;
			if (typeof data.progress === "number") {
				setDownloadProgress(data.progress);
			}
			return undefined;
		}, []),
	);

	// Persist the CURRENT step's selection to the backend controller
	// before navigating or applying. Shared by handleNext (advance) and
	// handleApply (finish on the final step) so the final step's
	// apply can't save the controller's stale/restored selections.
	const persistStepSelections = useCallback(async () => {
		if (step?.step_name === "Hotkey") {
			// The final step stores the hotkey in the backend controller
			// BEFORE the apply: ``apply_settings`` writes
			// ``ctrl.selected_hotkey`` into the config, so skipping
			// this call would let the apply overwrite the user's
			// saved hotkey with the controller default.
			await call("onboarding_set_hotkey", { hotkey: selectedHotkey });
		} else if (step?.step_name === "Consent") {
			// The consent toggles persist IMMEDIATELY on toggle
			// (setConsentField), so leaving the step has nothing new
			// to save — re-persist anyway so a mid-wizard quit after
			// toggling but before Continue still leaves the grants
			// durable (idempotent; mirrors the Model-step pattern).
			const toPersist: Record<string, unknown> = {};
			for (const f of CONSENT_FIELDS) {
				toPersist[f] = consents[f] ?? false;
			}
			await call("set_config", toPersist);
		} else if (step?.step_name === "Model") {
			await call("onboarding_set_model", { model: selectedModel });
			// Persist the local-vs-cloud choice (Model step).
			await call("onboarding_set_backend", { backend: selectedBackend });
			// ACTIVATE the choice through the allowlisted set_config
			// fields, writing the SAME pair/triple the Models page writes
			// on selection. `onboarding_set_model` / `onboarding_set_backend`
			// only feed the wizard's own controller: `apply_settings` saves
			// hotkey + microphone + `model_size` and nothing else, so
			// without this the wizard's Model step was decorative — a cloud
			// choice left `asr_backend` at its "whisper" default (dictation
			// still ran locally, with no API key), and a parakeet/qwen
			// choice left `asr_backend` pointing at Whisper.
			if (selectedBackend === "cloud") {
				const savedModel =
					savedCloudConfig?.provider === cloudProvider
						? savedCloudConfig.model.trim()
						: "";
				const updates: Partial<LausuConfig> = {
					asr_backend: "cloud",
					cloud_provider: cloudProvider,
					// This step selects a provider, not a cloud model. Keep a
					// configured model for that same provider; use the
					// catalogue default for a newly selected provider. Both
					// defaults stay pinned to the backend's
					// `_PROVIDER_DEFAULTS` by
					// `tests/test_cloud_provider_catalogue_parity.py`.
					cloud_model: savedModel || cloudDefaultModel(cloudProvider),
				};
				if (cloudApiKey.trim()) {
					updates[cloudApiKeyField(cloudProvider)] = cloudApiKey.trim();
				}
				await call("set_config", updates);
			} else {
				await call("set_config", {
					asr_backend: backendForModelName(modelOptions, selectedModel),
					model_size: selectedModel,
				});
			}
		}
	}, [
		call,
		step?.step_name,
		selectedHotkey,
		selectedModel,
		selectedBackend,
		modelOptions,
		cloudProvider,
		savedCloudConfig,
		cloudApiKey,
		consents,
	]);

	// ── Leaving the Model step: the cloud consent gate ───────────────
	// Choosing a cloud provider activates it (see the Model branch above),
	// so the provider's consent is requested AT THE POINT OF USE through
	// the shared gate — the same dialog the Models page opens on
	// activation — rather than through a checkbox on the step that a user
	// could tick without ever seeing what it authorises.
	//
	// The gate's Allow persists the consent itself and then re-enters the
	// RAW action, so the retry can never re-gate: the callback's `consents`
	// snapshot is still stale at that point. Same split as `handleDownload`
	// / `startDownload`.
	const guardCloudConsent = useCallback(
		(run: () => void): boolean => {
			if (step?.step_name !== "Model" || selectedBackend !== "cloud") {
				return false;
			}
			const field = cloudConsentField(cloudProvider);
			if (consents[field] === true) return false;
			openConsentGate({
				consentField: field,
				bodyKey: consentBodyKey(field),
				onAllow: () => {
					// Mirror the gate's persisted grant so the Consent step
					// and this step agree for the rest of the session
					// (idempotent with the dialog's own set_config).
					setConsents((prev) => ({ ...prev, [field]: true }));
					run();
				},
			});
			return true;
		},
		[step?.step_name, selectedBackend, cloudProvider, consents],
	);

	const advanceStep = useCallback(async () => {
		setSubmitting(true);
		try {
			await persistStepSelections();
			const newStep = await call<StepInfo>("onboarding_next_step");
			setStep(newStep);
		} catch (err) {
			console.error(
				"[renderer:useOnboardingWizard] Failed to advance step:",
				err,
			);
			showSnack(t("onboarding.saveFailedSnack"), "error");
		} finally {
			setSubmitting(false);
		}
	}, [call, persistStepSelections, showSnack]);

	const applyOnboarding = useCallback(async () => {
		setApplyError(false);
		setSubmitting(true);
		try {
			// Persist the final step's selection (the hotkey) BEFORE the
			// apply: ``apply_settings`` writes ``ctrl.selected_hotkey``
			// into the config, so a user who changed the hotkey on the
			// last step and clicked "Get started" would otherwise get
			// the controller's restored/default value saved instead.
			await persistStepSelections();
			// Await the backend apply so success is only claimed when the
			// settings actually persisted. The previous fire-and-forget
			// form (`void call(...).catch(...)`) showed the success snack
			// and navigated away even when `onboarding_apply` rejected,
			// silently skipping setup.
			await call("onboarding_apply");
			// Surface a success toast so the user gets explicit
			// feedback that setup completed (the inline spinner
			// disappears as soon as `onComplete()` navigates away).
			// The `setupCompleteSnack` key is localised across all 8
			// locales; the toast persists briefly after navigation
			// so the user sees it on the Home page.
			showSnack(t("onboarding.setupCompleteSnack"), "success");
			if (onComplete) onComplete();
		} catch (err) {
			console.error(
				"[renderer:useOnboardingWizard] Failed to apply onboarding:",
				err,
			);
			setApplyError(true);
			showSnack(t("onboarding.saveFailedSnack"), "error");
		} finally {
			setSubmitting(false);
		}
	}, [call, onComplete, persistStepSelections, showSnack]);

	const handleNext = useCallback(async () => {
		if (guardCloudConsent(() => void advanceStep())) return;
		await advanceStep();
	}, [guardCloudConsent, advanceStep]);

	const handleApply = useCallback(async () => {
		if (guardCloudConsent(() => void applyOnboarding())) return;
		await applyOnboarding();
	}, [guardCloudConsent, applyOnboarding]);

	const handlePrev = useCallback(async () => {
		setSubmitting(true);
		try {
			const newStep = await call<StepInfo>("onboarding_prev_step");
			setStep(newStep);
		} catch (err) {
			console.error("[renderer:useOnboardingWizard] Failed to go back:", err);
			showSnack(t("onboarding.saveFailedSnack"), "error");
		} finally {
			setSubmitting(false);
		}
	}, [call, showSnack]);

	// Skip is a SECOND VALID COMPLETION PATH on the backend (onboarding.skip
	// marks the status document complete). We deliberately do NOT persist the
	// current step's half-finished selections first: skipping means "use the
	// defaults", and first-run state must stay exactly what the backend wrote.
	const handleSkip = useCallback(async () => {
		setSubmitting(true);
		try {
			await call("onboarding_skip");
			showSnack(t("onboarding.setupCompleteSnack"), "success");
			if (onComplete) onComplete();
		} catch (err) {
			console.error("[renderer:useOnboardingWizard] Skip failed:", err);
			showSnack(t("onboarding.saveFailedSnack"), "error");
		} finally {
			setSubmitting(false);
		}
	}, [call, onComplete, showSnack]);

	return {
		loading,
		initError,
		step,
		submitting,
		applyError,
		selectedHotkey,
		setSelectedHotkey,
		selectedModel,
		setSelectedModel,
		hotkeyPresets,
		modelOptions,
		headingRef,
		retryInit,
		handleNext,
		handleApply,
		handlePrev,
		consents,
		setConsentField,
		handleAgreeToAll,
		selectedBackend,
		setSelectedBackend,
		downloadingModel,
		downloadProgress,
		downloadFailed,
		handleDownload,
		modelStatus,
		microphoneCount,
		checkMicrophones,
		handleSkip,
		cloudProvider,
		setCloudProvider,
		cloudApiKey,
		setCloudApiKey,
	};
}

/** Raw catalog entry shape from `get_model_catalog` (ModelMetadata.to_dict):
 *  carries `speed_rating` / `download_size_mb` / `supported_languages`,
 *  NOT the ModelOption `speed` / `size` / `languages` fields. ERR-1: the
 *  qwen catalog-only entry flowed through un-normalized, so ModelStep's
 *  `formatModelSpeed(m.speed)` read `.length` of undefined and crashed
 *  the whole wizard. */
interface RawCatalogEntry {
	name?: unknown;
	display_name?: unknown;
	size?: unknown;
	speed?: unknown;
	description?: unknown;
	vram_gb?: unknown;
	languages?: unknown;
	speed_rating?: unknown;
	download_size_mb?: unknown;
	required_vram_mb?: unknown;
	supported_languages?: unknown;
	backend?: unknown;
	recommended?: unknown;
}

function formatCatalogSize(downloadSizeMb: unknown): string {
	if (typeof downloadSizeMb !== "number" || downloadSizeMb <= 0)
		return "Variable";
	if (downloadSizeMb >= 1024) {
		const gb = downloadSizeMb / 1024;
		const rounded =
			gb >= 10 ? Math.round(gb).toString() : gb.toFixed(1).replace(/\.0$/, "");
		return `~${rounded}GB`;
	}
	return `~${downloadSizeMb}MB`;
}

function normalizeCatalogEntry(raw: RawCatalogEntry): ModelOption | null {
	if (typeof raw.name !== "string" || raw.name.length === 0) return null;
	const speed =
		typeof raw.speed === "string" && raw.speed.length > 0
			? raw.speed
			: typeof raw.speed_rating === "string" && raw.speed_rating.length > 0
				? raw.speed_rating.charAt(0).toUpperCase() + raw.speed_rating.slice(1)
				: "Medium";
	const size =
		typeof raw.size === "string" && raw.size.length > 0
			? raw.size
			: formatCatalogSize(raw.download_size_mb);
	const vramGb =
		typeof raw.vram_gb === "number"
			? raw.vram_gb
			: typeof raw.required_vram_mb === "number"
				? raw.required_vram_mb / 1024
				: undefined;
	const languages = Array.isArray(raw.languages)
		? (raw.languages as string[])
		: Array.isArray(raw.supported_languages)
			? (raw.supported_languages as string[])
			: raw.supported_languages === null || raw.languages === null
				? null
				: undefined;
	return {
		name: raw.name,
		size,
		...(typeof raw.download_size_mb === "number"
			? { download_size_mb: raw.download_size_mb }
			: {}),
		speed,
		description: typeof raw.description === "string" ? raw.description : "",
		...(typeof raw.display_name === "string" && raw.display_name.length > 0
			? { display_name: raw.display_name }
			: {}),
		...(typeof raw.backend === "string" && raw.backend.length > 0
			? { backend: raw.backend }
			: {}),
		...(vramGb !== undefined ? { vram_gb: vramGb } : {}),
		...(languages !== undefined ? { languages } : {}),
		...(raw.recommended === true ? { recommended: true } : {}),
	};
}

/** Merge the registry-derived option list with the rich catalog.
 *  `onboarding_get_model_options` defines the VISIBLE set (the five
 *  production models, sizes derived from the registry). The catalog only
 *  enriches those entries; catalog-only names are NOT appended, because a
 *  source build's catalog still contains the dev-only `tiny` model. For
 *  fields both sides carry (notably `size`), the catalog wins — it is
 *  generated straight from `GgufModelSpec.size_bytes`. */
function mergeModelOptions(
	curated: ModelOption[],
	catalog: RawCatalogEntry[],
): ModelOption[] {
	const byName = new Map<string, ModelOption>();
	for (const raw of catalog) {
		const m = normalizeCatalogEntry(raw);
		if (m) byName.set(m.name, m);
	}
	return curated.map((m) => {
		const fromCatalog = byName.get(m.name);
		return fromCatalog ? { ...m, ...fromCatalog } : m;
	});
}
