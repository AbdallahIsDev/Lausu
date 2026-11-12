// Pure derivation of what the page renders: each connection with its key-editor
// state, and the three domain rows with their provider options, model list,
// consent gate and notes. The measured skeleton sample flows through the same
// code path as real data.

import {
	DOMAINS,
	type Domain,
	type DomainSelection,
	type OnnxState,
	type ProviderEntry,
	type ProviderListData,
	type ProviderModel,
} from "./types";

export interface DomainView {
	domain: Domain;
	label: string;
	description: string;
	selection?: DomainSelection;
	providers: ProviderEntry[];
	models: ProviderModel[];
	/** Empty when nothing is configured — selects show their placeholder. */
	activeProvider: string;
	busy: boolean;
	usesCredits: boolean;
	showConsent: boolean;
	onnxNote: string | null;
}

export interface ConnectionView {
	provider: ProviderEntry;
	draft: string;
	busy: boolean;
}

export interface ProviderViewModel {
	connections: ConnectionView[];
	domains: DomainView[];
}

export interface ProviderActions {
	onDraftChange: (provider: string, value: string) => void;
	onSave: (provider: string) => void;
	onTest: (provider: string) => void;
	onClear: (provider: string) => void;
	onEnabledChange: (domain: Domain, enabled: boolean) => void;
	onProviderChange: (domain: Domain, provider: string) => void;
	onModelChange: (domain: Domain, modelId: string) => void;
	onConsentChange: (domain: Domain, consent: boolean) => void;
}

export interface ViewModelInput {
	data: ProviderListData;
	drafts: Record<string, string>;
	busy: string | null;
	catalogues: Record<string, ProviderModel[]>;
	onnx: OnnxState | null;
	domainLabels: Record<string, string>;
	domainDescriptions: Record<Domain, string>;
	/** Localized ONNX line for the LLM domain (null when idle). */
	onnxNote: string | null;
}

export function buildViewModel({
	data,
	drafts,
	busy,
	catalogues,
	onnx,
	domainLabels,
	domainDescriptions,
	onnxNote,
}: ViewModelInput): ProviderViewModel {
	// Key management is the card's only action, so keyless providers (local
	// models, ONNX) get no connection card.
	const connections: ConnectionView[] = data.providers
		.filter((provider) => provider.auth === "api_key")
		.map((provider) => ({
			provider,
			draft: drafts[provider.id] ?? "",
			busy: busy === `key:${provider.id}` || busy === `test:${provider.id}`,
		}));

	const domains: DomainView[] = DOMAINS.map((domain) => {
		const selection = data.domains?.[domain];
		const providers = data.providers.filter((provider) =>
			provider.domains.includes(domain),
		);
		// Never present the first option as selected when none is set
		// (C-UI-15).
		const activeProvider = selection?.provider || "";
		const activeEntry = providers.find(
			(provider) => provider.id === activeProvider,
		);
		const isLlm = domain === "llm";
		return {
			domain,
			label: domainLabels[domain] ?? domain,
			description: domainDescriptions[domain],
			selection,
			providers,
			models: catalogues[activeProvider] ?? activeEntry?.models ?? [],
			activeProvider,
			busy: busy === `domain:${domain}`,
			// Only a KNOWN remote provider spends credits/needs consent.
			usesCredits: Boolean(
				selection?.enabled && activeEntry && !activeEntry.local,
			),
			showConsent: Boolean(
				activeEntry && (activeEntry.consent_required || !activeEntry.local),
			),
			onnxNote: isLlm && onnx?.model ? onnxNote : null,
		};
	});

	return { connections, domains };
}
