import type { ModelOption, StepInfo } from "./types";

// Measured-skeleton sample for Onboarding. The wizard renders the
// Model step (2 of 4) from this while the init probes run, so the
// card measures at its real height before the first real step lands.
export const SAMPLE_STEP: StepInfo = {
	step: 2,
	total_steps: 4,
	step_name: "Model",
};

// Skeleton-only stand-ins for the five production models. Sizes are a single
// neutral placeholder: this list is never shown as data (the Skeleton hides
// it), it only measures the card, and curated per-model sizes used to drift
// from the registry. The real rows come from the backend's registry-derived
// options + catalog (see useOnboardingWizard.mergeModelOptions).
export const SAMPLE_MODEL_OPTIONS: ModelOption[] = [
	{
		name: "parakeet",
		size: "~1.0GB",
		speed: "Fast",
		description: "",
		backend: "parakeet",
	},
	{
		name: "large-v3-turbo",
		size: "~1.0GB",
		speed: "Fast",
		description: "",
		backend: "whisper",
		recommended: true,
	},
	{
		name: "large-v3",
		size: "~1.0GB",
		speed: "Slow",
		description: "",
		backend: "whisper",
	},
	{
		name: "qwen3-1.7b",
		size: "~1.0GB",
		speed: "Medium",
		description: "",
		backend: "qwen",
	},
	{
		name: "qwen3-0.6b",
		size: "~1.0GB",
		speed: "Fast",
		description: "",
		backend: "qwen",
	},
];

export const SAMPLE_CONSENTS: Record<string, boolean> = {
	voice_biometric_consent: true,
	huggingface_consent: true,
	cloud_openai_consent: false,
	cloud_groq_consent: false,
	cloud_deepgram_consent: false,
	cloud_gemini_consent: false,
	llm_polish_consent: false,
};
