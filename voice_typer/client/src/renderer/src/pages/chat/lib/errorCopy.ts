// Plain-language copy for the Chat page's turn failures (C-UXERR-1/3).
//
// The backend publishes a namespaced IPC code on `chat_turn.phase === "error"`.
// Raw exception text never reaches the UI: an unknown code falls back to the
// generic sentence, and every code carries the recovery action that can
// actually help (C-UXERR-4).

import type { TranslationKey } from "@/i18n/translation-keys";

export type ChatErrorAction = "retry" | "models" | "providers";

const GENERIC_KEY: TranslationKey = "chat.errorGeneric";

const COPY: Record<string, { key: TranslationKey; action: ChatErrorAction }> = {
	no_speech: { key: "chat.errorNoSpeech", action: "retry" },
	no_engine_loaded: { key: "chat.errorNoEngine", action: "models" },
	transcription_failed: {
		key: "chat.errorTranscriptionFailed",
		action: "retry",
	},
	"server.internal_error": { key: GENERIC_KEY, action: "retry" },
	"server.provider_error": { key: GENERIC_KEY, action: "retry" },
	"server.provider_unavailable": {
		key: "chat.errorProviderUnavailable",
		action: "providers",
	},
	"server.provider_consent_required": {
		key: "chat.errorProviderConsent",
		action: "providers",
	},
	"server.provider_auth_required": {
		key: "chat.errorProviderAuth",
		action: "providers",
	},
	"server.provider_unknown": {
		key: "chat.errorProviderModel",
		action: "providers",
	},
	"server.provider_model_unknown": {
		key: "chat.errorProviderModel",
		action: "providers",
	},
};

export function chatErrorKey(code: string | null): TranslationKey {
	if (code === null) return GENERIC_KEY;
	return COPY[code]?.key ?? GENERIC_KEY;
}

export function chatErrorAction(code: string | null): ChatErrorAction {
	if (code === null) return "retry";
	return COPY[code]?.action ?? "retry";
}
