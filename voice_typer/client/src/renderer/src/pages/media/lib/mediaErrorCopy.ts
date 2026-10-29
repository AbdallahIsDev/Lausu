// Renderer copy map for media-transcribe failure codes (ADR-0023 E13):
// the backend's raw message is diagnostics, never shown verbatim — the
// user gets the localized, actionable line for the failure class.

import type { TranslationKey } from "@/i18n/translation-keys";

const MEDIA_ERROR_KEYS: Readonly<Record<string, TranslationKey>> = {
	drm_refused: "media.errorDrm",
	no_audio: "media.errorNoAudio",
	unsupported_live: "media.errorLive",
	login_required: "media.errorLoginRequired",
	geo_blocked: "media.errorGeoBlocked",
	playlist_rejected: "media.errorPlaylist",
	decode_failed: "media.errorDecode",
	resolve_failed: "media.errorResolve",
	// A stalled stream ends in the same recovery advice as a failed
	// download: check the connection and retry.
	stream_stalled: "media.errorDownloadFailed",
	url_expired: "media.errorUrlExpired",
	download_failed: "media.errorDownloadFailed",
	// Selected but unusable (not installed / load failed): retry is the
	// action, so this does NOT get the "Open Models" treatment.
	no_engine_loaded: "media.errorEngineUnavailable",
	job_busy: "media.errorBusy",
	media_too_short: "media.errorTooShort",
	media_truncated: "media.errorTruncated",
	multi_item_url: "media.errorMultiItem",
	no_media_url: "media.errorNoMedia",
	// The model is still loading: retryable, never "choose a model".
	model_loading: "media.errorModelLoading",
	"server.model_loading": "media.errorModelLoading",
	model_changed: "media.errorModelChanged",
	"server.model_changed": "media.errorModelChanged",
};

/** Localized copy for a backend media/error code; `null` when unknown. */
export function mediaErrorKey(
	code: string | null | undefined,
): TranslationKey | null {
	if (!code) return null;
	return MEDIA_ERROR_KEYS[code] ?? null;
}

/** True when NOTHING is selected (offers Open Models).
 *
 * Deliberately narrower than it used to be: `no_engine_loaded` means a model
 * IS selected but could not be loaded, and that failure offers retry copy
 * instead of sending the user to pick a model they already picked.
 */
export function isNoModelError(code: string | null | undefined): boolean {
	return code === "server.no_model";
}

/** True when the failure is retryable a moment later (model still loading). */
export function isRetryableLater(code: string | null | undefined): boolean {
	return code === "model_loading" || code === "server.model_loading";
}

/** True when a multi-item link needs the count interpolated into its copy. */
export function isMultiItemError(code: string | null | undefined): boolean {
	return code === "multi_item_url";
}
