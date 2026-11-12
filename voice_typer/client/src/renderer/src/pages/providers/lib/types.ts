// Wire shapes of `provider_list` / `provider_models` and the page's own view
// types. Shared by the page and its provider-row component so neither has to
// import the other.

export type Domain = "asr" | "tts" | "llm";

export const DOMAINS: Domain[] = ["asr", "tts", "llm"];

export interface ProviderModel {
	id: string;
	label: string;
	domains?: string[];
	context_length?: number | null;
	free?: boolean;
	note?: string | null;
}

export interface ProviderEntry {
	id: string;
	label: string;
	domains: string[];
	local: boolean;
	auth: string;
	models: ProviderModel[];
	unsupported_reason: Record<string, string>;
	key: { configured: boolean; masked: string };
	consent_required: boolean;
}

export interface DomainSelection {
	provider: string;
	model_id: string;
	consent: boolean;
	fallback: string;
	enabled: boolean;
}

export interface ProviderListData {
	providers: ProviderEntry[];
	domains: Record<Domain, DomainSelection>;
}

export interface OnnxState {
	model: string;
	state: string;
	error: string | null;
}
