import { useCallback } from "react";
import { useCloudProviders } from "@/hooks/models/useCloudProviders";
import { useModelConfig } from "@/hooks/models/useModelConfig";
import { useModelDownload } from "@/hooks/models/useModelDownload";
import { useModelFolder } from "@/hooks/models/useModelFolder";
import { useModelSelection } from "@/hooks/models/useModelSelection";
import { useLastUpdated } from "@/hooks/useLastUpdated";
import { usePython } from "@/hooks/usePython";
import { useSnackbar } from "@/hooks/useSnackbar";
import { consentBodyKey, openConsentGate } from "@/lib/consentGate";
import {
	CLOUD_PROVIDERS,
	type CloudProvider,
	type ModelInfo,
	requiresHuggingFaceConsent,
} from "@/lib/utils/models";

// ── Facade ────────────────────────────────────────────────────────────

export function useModelLifecycle() {
	const { call } = usePython();
	const { showSnack } = useSnackbar();
	const { markUpdated } = useLastUpdated();

	// 1. Core config + models + apiKeys state + load / refresh / update
	//    actions + the `config_changed` subscription.
	const configHook = useModelConfig({ call, markUpdated });
	// Destructure the internal helpers out so they don't leak into the
	// public return shape (they're not part of the pre-split return).
	const {
		refreshModelStatus,
		updateConfig,
		setConfig,
		setModels,
		...configRest
	} = configHook;

	// 2. Model-selection + deletion state + actions. Needs `setModels`
	//    (optimistic active-model flip + post-delete state clear),
	//    `refreshModelStatus` (post-select reconciliation), and
	//    `updateConfig` (persist the new active model). `setConfig`
	//    mirrors the committed selection into config state immediately
	//    so the no-model banner flips without waiting for the
	//    `config_changed` echo. Created BEFORE the download sub-hook:
	//    the download's auto-select needs `selectModel`.
	const selection = useModelSelection({
		call,
		showSnack,
		setModels,
		refreshModelStatus,
		updateConfig,
		setConfig,
	});

	// Auto-select the just-downloaded model (stable reference so the
	// download sub-hook's `downloadModel` keeps a stable identity for
	// the memo'd row components).
	const handleDownloaded = useCallback(
		(model: ModelInfo) => void selection.selectModel(model),
		[selection.selectModel],
	);

	// 3. Download-progress state machine + the `download_progress`
	//    subscription + the download / pause / cancel actions. Needs
	//    `setModels` (to mark the just-downloaded model as
	//    `downloaded: true`) and `loadConfig`
	//    (post-download reconcile, the backend does not auto-activate,
	//    so config/status truth is re-fetched instead of guessed).
	//    `onDownloaded` auto-selects the model on success (the hook
	//    passes it with `downloaded: true` applied).
	const download = useModelDownload({
		call,
		showSnack,
		setModels,
		reconcileAfterDownload: configRest.loadConfig,
		onDownloaded: handleDownloaded,
	});

	// 4. Cloud-provider API keys + connection-test + model-activation
	//    actions. Needs `apiKeys` (read by saveApiKey + testConnection),
	//    `updateConfig` (persist the key, and the
	//    asr_backend/cloud_provider/cloud_model triple an activation
	//    writes) and `setConfig` (optimistic merge so the Active marker
	//    moves on the click, not on the `config_changed` echo). Consent
	//    is granted through the shared consent dialog, not through this
	//    hook.
	const cloud = useCloudProviders({
		showSnack,
		config: configRest.config,
		apiKeys: configRest.apiKeys,
		updateConfig,
		setConfig,
		call,
	});

	// 5. Disk-info probe + import / open-folder actions. Needs
	//    `loadConfig` so a successful import re-syncs the local model
	//    list with the freshly-imported entries.
	const folder = useModelFolder({
		call,
		showSnack,
		loadConfig: configRest.loadConfig,
	});

	// 6. (UI/UX overhaul 2026-08-20, point 4), just-in-time
	//    HuggingFace-consent gate for downloads. The persistent
	//    the moment the user clicks a model's Download button:
	//      • consent already granted (or the model doesn't download
	//        from HuggingFace, e.g. qwen) → proceed immediately;
	//      • consent missing → block the download and open the shared
	//        point-of-use consent dialog (`openConsentGate`, the SAME
	//        modal every other consent-gated flow uses). Allow persists
	//        `huggingface_consent=true` and re-invokes the blocked
	//        download; Cancel leaves it blocked. The backend's own
	//        `_require_huggingface_consent` gate remains the GDPR
	//        enforcement, this only changes when/how the requirement
	//        is surfaced to the user.
	const handleDownloadModel = useCallback(
		(model: ModelInfo) => {
			if (
				!requiresHuggingFaceConsent(model) ||
				configRest.config?.huggingface_consent
			) {
				void download.downloadModel(model);
				return;
			}
			openConsentGate({
				consentField: "huggingface_consent",
				bodyKey: consentBodyKey("huggingface_consent"),
				onAllow: () => void download.downloadModel(model),
			});
		},
		[configRest.config, download.downloadModel],
	);

	return {
		...configRest,
		...download,
		...selection,
		...cloud,
		...folder,
		// Just-in-time consent-gated download entry point (point 4).
		handleDownloadModel,
		// Static data (re-exported for the panels' convenience).
		cloudProviders: CLOUD_PROVIDERS as readonly CloudProvider[],
	};
}
