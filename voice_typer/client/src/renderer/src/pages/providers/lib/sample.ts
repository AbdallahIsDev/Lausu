import type { ProviderListData } from "./types";

// Measured-skeleton sample for Providers. It mirrors
// `model_providers/builtin.register_all()` (same ids, order, labels,
// domains and unsupported reasons) and the default config (every domain
// off), so the skeleton measures the page a first load actually renders
// instead of a shorter invented list.
const keyless = { configured: false, masked: "" };

export const SAMPLE_PROVIDER_LIST: ProviderListData = {
	providers: [
		{
			id: "local",
			label: "Local models",
			domains: ["asr", "tts"],
			local: true,
			auth: "none",
			models: [],
			unsupported_reason: {
				llm: "Local text generation uses the local_onnx provider.",
			},
			key: keyless,
			consent_required: false,
		},
		{
			id: "cloud_direct",
			label: "Direct cloud API",
			domains: ["asr", "llm"],
			local: false,
			auth: "api_key",
			models: [{ id: "", label: "Configured cloud model" }],
			unsupported_reason: {
				tts: "Hosted TTS uses the openai or custom provider.",
			},
			key: keyless,
			consent_required: false,
		},
		{
			id: "openrouter",
			label: "OpenRouter",
			domains: ["asr", "tts", "llm"],
			local: false,
			auth: "api_key",
			models: [],
			unsupported_reason: {},
			key: keyless,
			consent_required: true,
		},
		{
			id: "ollama",
			label: "Ollama",
			domains: ["llm"],
			local: true,
			auth: "local_endpoint",
			models: [],
			unsupported_reason: {
				asr: "Ollama serves text models only.",
				tts: "Ollama serves text models only.",
			},
			key: keyless,
			consent_required: false,
		},
		{
			id: "lmstudio",
			label: "LM Studio",
			domains: ["llm"],
			local: true,
			auth: "local_endpoint",
			models: [],
			unsupported_reason: {
				asr: "LM Studio serves text models only.",
				tts: "LM Studio serves text models only.",
			},
			key: keyless,
			consent_required: false,
		},
		{
			id: "local_onnx",
			label: "Local ONNX",
			domains: ["llm"],
			local: true,
			auth: "none",
			models: [],
			unsupported_reason: {
				asr: "Local ONNX is a text-generation runtime.",
				tts: "Local ONNX is a text-generation runtime.",
			},
			key: keyless,
			consent_required: false,
		},
		{
			id: "custom",
			label: "OpenAI-compatible",
			domains: ["asr", "tts", "llm"],
			local: false,
			auth: "api_key",
			models: [],
			unsupported_reason: {},
			key: keyless,
			consent_required: true,
		},
	],
	domains: {
		asr: {
			provider: "",
			model_id: "",
			consent: false,
			fallback: "local",
			enabled: false,
		},
		tts: {
			provider: "",
			model_id: "",
			consent: false,
			fallback: "off",
			enabled: false,
		},
		llm: {
			provider: "",
			model_id: "",
			consent: false,
			fallback: "off",
			enabled: false,
		},
	},
};
