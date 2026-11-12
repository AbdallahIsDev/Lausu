import type { ModelOption, StepInfo } from "./types";

// Measured-skeleton sample for Onboarding. The wizard renders the
// Model step (2 of 4) from this while the init probes run, so the
// card measures at its real height before the first real step lands.
export const SAMPLE_STEP: StepInfo = {
	step: 2,
	total_steps: 4,
	step_name: "Model",
};

// Mirrors `OnboardingController.MODEL_OPTIONS`
// (`server/onboarding_selections.py`): the curated four, in that order,
// with `recommended` on parakeet only. The earlier sample carried three
// invented picks and flagged the wrong model as recommended, so the
// skeleton showed a different list than the wizard rendered.
export const SAMPLE_MODEL_OPTIONS: ModelOption[] = [
	{
		name: "tiny",
		size: "~75MB",
		speed: "Fastest",
		description: "Multilingual, best for quick notes",
		vram_gb: 0.5,
		languages: null,
		backend: "whisper",
	},
	{
		name: "large-v3",
		size: "~3GB",
		speed: "Slow",
		description: "Multilingual, highest accuracy, GPU recommended",
		vram_gb: 3.0,
		languages: null,
		backend: "whisper",
	},
	{
		name: "large-v3-turbo",
		size: "~1.6GB",
		speed: "Fast",
		description: "Multilingual, near-large-v3 accuracy at 8x speed",
		vram_gb: 2.0,
		languages: null,
		backend: "whisper",
	},
	{
		name: "parakeet",
		display_name: "Parakeet Ultra",
		size: "~670MB",
		speed: "Fast",
		description: "Parakeet Ultra, fast & accurate, 25 languages",
		vram_gb: 2.0,
		languages: null,
		backend: "parakeet",
		recommended: true,
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
