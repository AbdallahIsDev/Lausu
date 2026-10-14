/**
 * Locale-aware formatting for the Models surface: model sizes and speeds,
 * VRAM/WER cells, id-derived display names, caught-error text, and the
 * backend's cloud-test failure tokens.
 *
 * Split out of `lib/utils/models.ts`; the barrel (`./models`) re-exports
 * every symbol below, so existing import paths keep resolving.
 */

import { t } from "@/i18n/i18n";
import {
	formatVram as _formatVram,
	formatWer as _formatWer,
} from "@/lib/format";

/**
 * Map the backend's `test_cloud_connection` failure token to the i18n
 * key that explains it in words. The backend deliberately returns a
 * short stable token (`_http_error_message` in
 * `server/handlers/cloud_test_handlers.py`) so the wording stays a
 * renderer concern; rendering the token raw is what produced the
 * meaningless "Connection failed: 400 http_error".
 *
 * `no_api_key` maps to the existing "enter a key first" copy: it means
 * the same thing to the user as the pre-flight guard's message.
 */
export function connectionFailureKey(token: string): string {
	switch (token) {
		case "auth_failed":
			return "models.test.failure.auth";
		case "rate_limited":
			return "models.test.failure.rateLimited";
		case "server_error":
			return "models.test.failure.server";
		case "network_error":
			return "models.test.failure.network";
		case "no_api_key":
			return "models.test.needApiKey";
		default:
			return "models.test.failure.http";
	}
}

const MODEL_SIZE_NORMALIZER = /^(?:~|≈)?\s*(\d+(?:[.,]\d+)?)\s*([A-Za-z]+)$/;
export function formatModelSize(size: string): string {
	const trimmed = size.trim();
	if (trimmed === "Variable") return t("models.variable");
	const match = MODEL_SIZE_NORMALIZER.exec(trimmed);
	if (!match) return trimmed;
	// optional, hence the explicit guard before formatting).
	const [, number, unit] = match;
	if (number === undefined || unit === undefined) return trimmed;
	return `${number} ${unit.toUpperCase()}`;
}

const SPEED_I18N_MAP: Record<string, string> = {
	Fastest: "models.speed.fastest",
	Fast: "models.speed.fast",
	Medium: "models.speed.medium",
	Slow: "models.speed.slow",
	Variable: "models.speed.variable",
};

/**
 * Capitalize the first letter of a word ("fast" → "Fast"). Defensive:
 * backend catalog entries may omit the field (ERR-1: qwen catalog-only
 */
function capitalizeFirst(value: string | null | undefined): string {
	if (typeof value !== "string") return "";
	return value.length > 0
		? value.charAt(0).toUpperCase() + value.slice(1)
		: value;
}

/**
 * Format a speed rating for display. Accepts both the legacy
 * capitalized source values ("Fast", "Fastest") and the backend
 */
export function formatModelSpeed(speed: string | null | undefined): string {
	if (typeof speed !== "string" || speed.length === 0) return "";
	const key = SPEED_I18N_MAP[speed] ?? SPEED_I18N_MAP[capitalizeFirst(speed)];
	return key ? t(key) : capitalizeFirst(speed);
}

// `voice_typer/client/src`, so there is nothing to wire, the helper
export function formatVram(mb: number): string {
	return _formatVram(mb);
}

/**
 * Re-export of the locale-aware WER percent formatter (see lib/format.ts).
 */
export function formatWer(wer: number): string {
	return _formatWer(wer);
}

/**
 * : format an unknown caught value as a user-friendly string.
 *
 */
export function formatErrorMessage(
	err: unknown,
	fallback: string = t("models.errors.unknown"),
): string {
	if (err instanceof Error) {
		return err.message || fallback;
	}
	if (typeof err === "string") {
		return err || fallback;
	}
	if (err && typeof err === "object") {
		const obj = err as { _error?: unknown; message?: unknown; error?: unknown };
		if (typeof obj._error === "string" && obj._error) return obj._error;
		if (typeof obj.message === "string" && obj.message) return obj.message;
		if (typeof obj.error === "string" && obj.error) return obj.error;
	}
	return fallback;
}

export function formatModelDisplayName(rawId: string): string {
	return rawId
		.split("-")
		.filter((part) => part.length > 0)
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");
}
