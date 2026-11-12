import type { LausuConfig } from "@/types/config";

// Sample config for measured skeletons. This file exists so that
// `<Skeleton data sample>` can render the real page unseen while
// its data is null: the sample is a typical, fully-populated config
// (all 160 fields, mirroring the backend defaults) so no component
// reads an undefined field during measurement. Values are fake and
// never persisted; only layout matters, so any typical value works.
// Kept in prod (not `__tests__/helpers/fixtures.ts`) because page
// samples render in production loading states.
export const SAMPLE_CONFIG: LausuConfig = {
	schema_version: 3,
	hotkey: "F2",
	sample_rate: 16000,
	microphone: null,

	model_size: "tiny",
	active_plugin: "",
	language: "en",
	device: "cpu",
	beam_size: 5,
	best_of: 1,
	condition_on_previous_text: false,
	vad_filter_enabled: true,
	hallucination_filter_mode: "balanced",

	streaming_transcription: false,
	streaming_chunk_seconds: 0,
	streaming_step_seconds: 0,
	streaming_left_overlap_seconds: 0,
	streaming_right_guard_seconds: 0,
	streaming_min_first_chunk_seconds: 0,
	streaming_silence_threshold: 0,

	autostart: false,
	paste_on_stop: true,
	show_notifications: true,
	fast_startup: false,
	offline_pack_consent: true,

	clipboard_save_restore: true,
	clipboard_restore_delay_ms: 150,

	asr_backend: "whisper",
	qwen_model_path: null,
	parakeet_model_path: null,

	text_cleanup_enabled: true,
	corrections_path: null,
	log_transcriptions: false,

	recording_mode: "toggle",
	esc_cancel_enabled: true,
	repaste_hotkey: "",
	auto_punctuation: false,

	templates_enabled: true,
	vocabulary_enabled: true,

	cloud_api_key: "",
	cloud_api_url: "",
	cloud_model: "",
	cloud_provider: "",
	openai_api_key: "",
	groq_api_key: "",
	deepgram_api_key: "",
	gemini_api_key: "",

	llm_polish: false,
	llm_api_key: "",
	llm_api_url: "",
	llm_model: "",
	llm_preset: "professional",

	crash_recovery_enabled: true,
	audio_quality_warnings: false,

	waveform_bubble: true,
	bubble_position: "top",
	bubble_behavior: "show_on_record",
	bubble_draggable: true,
	bubble_show_on_startup: false,
	bubble_click_to_toggle: true,
	bubble_mic_button: true,
	bubble_show_recording_timer: false,
	screenshot_beta_enabled: false,

	bubble_x: null,
	bubble_y: null,

	history_retention_days: 30,
	history_retention_count: 100,
	history_max_entries: 1000,

	onboarding_completed: true,

	tray_left_click_action: "open_app",

	theme_mode: "system",
	theme_preset: "default",
	custom_theme: null,

	text_size: 14,

	wayland_warned: false,

	silence_warning_seconds: 0,
	stop_on_silence_seconds: 0,
	max_recording_time_seconds: 900,

	volume_duck_enabled: false,
	volume_duck_level: 0,
	volume_duck_per_session: false,
	volume_duck_fade_ms: 0,
	volume_duck_smart: false,
	volume_duck_smart_poll_interval_ms: 0,

	audio_preset: "auto",

	noise_filter_enabled: false,
	noise_filter_highpass: false,
	noise_filter_highpass_cutoff_hz: 0,
	noise_filter_gate: false,
	noise_filter_gate_threshold: 0,
	noise_filter_gate_hold_ms: 0,
	noise_filter_gate_open_threshold_db: 0,
	noise_filter_gate_close_threshold_db: 0,
	noise_filter_gate_attack_ms: 0,
	noise_filter_gate_release_ms: 0,
	noise_filter_rnnoise: false,
	noise_filter_post_capture: false,
	noise_suppression_method: "none",
	noise_filter_eq: false,
	noise_filter_eq_low_db: 0,
	noise_filter_eq_mid_db: 0,
	noise_filter_eq_high_db: 0,
	noise_filter_compressor: false,
	noise_filter_compressor_threshold_db: 0,
	noise_filter_compressor_ratio: 0,
	noise_filter_compressor_attack_ms: 0,
	noise_filter_compressor_release_ms: 0,
	noise_filter_compressor_output_gain_db: 0,
	noise_filter_limiter: false,
	noise_filter_limiter_ceiling_db: 0,
	noise_filter_limiter_release_ms: 0,
	noise_filter_notch: false,
	noise_filter_notch_frequency_hz: 0,

	huggingface_consent: false,
	cloud_openai_consent: false,
	cloud_groq_consent: false,
	cloud_deepgram_consent: false,
	cloud_gemini_consent: false,
	voice_biometric_consent: false,
	llm_polish_consent: false,
	media_url_consent: false,
	screenshot_consent: false,

	sound_feedback_enabled: false,

	ai_enhancement_enabled: false,
	auto_capitalize: true,
	auto_punctuate: true,
	fix_grammar_basics: true,

	vocabulary_automation_enabled: false,
	vocabulary_auto_confidence_threshold: 0.7,
	vocabulary_auto_apply_threshold: 0.95,
};
