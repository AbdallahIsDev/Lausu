/**
 * The four states the GPU affordance branches on. Mirrors
 * `voice_typer/server/gpu_capability.py` constants.
 *
 * * `no_nvidia_gpu` — nothing to offer; the sidebar control stays hidden.
 * * `driver_missing` — an NVIDIA adapter is enumerated but the OS driver
 *   is not installed; only the vendor installer can fix that, so the
 *   dialog explains and links out instead of offering a download.
 * * `gpu_present_cuda_missing` — driver works, the user-level CUDA
 *   runtime is absent; this is the state the download modal exists for.
 * * `gpu_ready` — at least one local backend can serve GPU right now.
 */
export type GpuCapabilityState =
	| "no_nvidia_gpu"
	| "driver_missing"
	| "gpu_present_cuda_missing"
	| "gpu_ready";

/** One local backend's GPU readiness ("GPU works" is not global). */
export interface GpuBackendCapability {
	name: string;
	local: boolean;
	gpu_capable: boolean;
	gpu_ready: boolean;
	/** `ready` / `cuda_missing` / `no_gpu` / `cpu_only_backend` / `not_local`. */
	detail: string;
}

/** The install job's lifecycle, as published on `cuda_progress`. */
export type CudaInstallStatus =
	| "idle"
	| "downloading"
	| "verifying"
	| "installing"
	| "completed"
	| "failed"
	| "cancelled";

/** One `cuda_progress` payload (also returned by the install commands). */
export interface CudaInstallProgress {
	status: CudaInstallStatus;
	artifact: string | null;
	artifact_index: number;
	artifact_count: number;
	bytes_done: number;
	bytes_total: number;
	percent: number;
	speed_bps: number;
	eta_seconds: number | null;
	error: string | null;
}

/**
 * READ-ONLY computed capability report attached to `get_config` (and
 * returned verbatim by `get_gpu_capability`). Absent on older sidecars,
 * in which case the renderer keeps the GPU affordance hidden.
 */
export interface GpuCapability {
	state: GpuCapabilityState;
	hardware_present: boolean;
	driver_present: boolean;
	gpu_names: string[];
	/**
	 * Historical "ANY gpu-capable local backend is ready". Kept for the
	 * coarse four-state verdict only — NEVER gate on it: on a machine where
	 * CTranslate2 sees the GPU but the installed `onnxruntime` is the
	 * CPU-only wheel it is true while Parakeet/Qwen cannot serve at all.
	 */
	cuda_ready: boolean;
	/**
	 * EVERY gpu-capable LOCAL backend is ready (both the CTranslate2 path
	 * and the ORT path). The signal an install must satisfy before the app
	 * may persist `device: "cuda"`.
	 */
	stack_complete: boolean;
	backends: GpuBackendCapability[];
	download: {
		/** True only on Windows with a pinned wheel set for this Python. */
		supported: boolean;
		/** `unsupported_platform` / `unsupported_python` / `no_gpu` / null. */
		reason: string | null;
		total_bytes: number;
		python: string;
		installed: boolean;
		progress: CudaInstallProgress;
	};
	/** Pending/failed activation record, or null when nothing is staged. */
	activation: { state: "pending" | "failed"; reason?: string | null } | null;
	/** Vendor driver download page (the `driver_missing` branch). */
	driver_url: string;
	active_backend?: string;
	/** True when the ACTIVE backend can serve GPU right now. */
	active_backend_gpu_ready?: boolean;
}

// Must mirror Python `ALLOWED_USER_MODELS` (derived from
export type ModelSize =
	| ""
	| "tiny"
	| "large-v3"
	| "large-v3-turbo"
	| "qwen3-1.7b"
	| "qwen3-0.6b"
	| "parakeet";

/**
 * Linux title-bar window-button customization (persisted config field
 * `linux_window_buttons`; Settings → Appearance, Linux only). Mirrors
 */
export interface LinuxWindowButtonsConfig {
	mode: "system" | "custom";
	side: "left" | "right";
	show_minimize: boolean;
	show_maximize: boolean;
	show_close: boolean;
}

/**
 * READ-ONLY computed snapshot the sidecar attaches to every `get_config`
 * response (NOT a persisted field): the desktop's own button-layout
 */
export interface LinuxWindowButtonsSystemInfo {
	desktop_environment: "gnome" | "kde" | "xfce" | "mate" | "other" | "unknown";
	layout: { side: "left" | "right"; buttons: string[] } | null;
}

/**
 * A user-saved microphone preset (persisted `custom_presets` entry).
 * Mirrors the backend validator shape: stable id, display name,
 * and a bag of noise-filter values.
 */
export interface CustomMicPreset {
	id: string;
	name: string;
	values: Record<string, boolean | number | string>;
}

export interface LausuConfig {
	schema_version: number;

	hotkey: string;

	sample_rate: number;
	microphone: string | null;
	//optional because older sidecars (pre-) don't
	// IPC allowlist; absence on the wire is treated as 1 (mono) by
	recording_channels?: number;
	//optional because older sidecars (pre-) don't
	pre_roll_buffer_seconds?: number;
	// Python `Config` dataclass and IPC allowlist. OPTIONAL so older
	vad_auto_calibrate?: boolean;

	model_size: ModelSize;
	/** Installed plugin that currently owns dictation ("" = local model). */
	active_plugin: string;
	/** Owner-only unlock for the internal Plugins surface. Optional for
	 *  wire tolerance; absent means hidden. */
	developer_mode?: boolean;
	language: string;
	device: "cuda" | "cpu";
	/**
	 * READ-ONLY computed device the LOADED engine actually runs on,
	 * attached to every `get_config` response and pushed with
	 * `config_changed` when a load or a fallback changes it. `device` is
	 * the persisted REQUEST and can differ (CPU-only onnxruntime build,
	 * forced-CPU load, worker fallback); surfaces display this one so
	 * they never claim a GPU that is not serving. Optional: absent on
	 * older sidecars and `null` while no engine is loaded.
	 */
	active_device?: "cpu" | "cuda" | null;
	/**
	 * Minutes of dictation inactivity before the ASR model is dropped from
	 * memory. `0` means "never unload" (keep it loaded while the app is
	 * open). Only ever changed by the user through the Settings → General
	 * dropdown; the app never writes it based on system memory pressure.
	 * Optional for wire tolerance with older sidecars (absent = 60).
	 */
	model_idle_unload_minutes?: number;
	/**
	 * READ-ONLY computed flag attached to every `get_config` response
	 * (NOT persisted): true when the backend probe found a
	 * CUDA-capable GPU. Absent on older sidecars; the sidebar toggle
	 * treats absence as GPU-less and stays hidden.
	 */
	gpu_available?: boolean;
	/**
	 * READ-ONLY computed GPU capability report attached to every
	 * `get_config` response (NOT persisted): the four-state verdict,
	 * per-backend readiness, install progress and the activation record.
	 * Absent on older sidecars; `null` when the probe itself failed, which
	 * the UI treats the same as absent (no GPU affordance).
	 */
	gpu_capability?: GpuCapability | null;
	/**
	 * READ-ONLY computed flag (NOT persisted): an NVIDIA display adapter is
	 * enumerated. Unlike `gpu_available` this is true on a driver-less
	 * machine, which is exactly the `driver_missing` branch.
	 */
	gpu_hardware_present?: boolean;
	/**
	 * READ-ONLY computed label (NOT persisted): the manifest name of the
	 * plugin that owns dictation (`""` when the local model does). The
	 * sidebar caption and the tray show this instead of the model name,
	 * because the model is not what is transcribing.
	 */
	active_plugin_name?: string;
	beam_size: number;
	best_of: number;
	/**
	 * Whisper-specific beam width; 1 = automatic device/model-aware default. Optional for wire tolerance with older sidecars.
	 */
	whisper_beam_size?: number;
	condition_on_previous_text: boolean;
	/**
	 * Master switch for voice-activity (silence) filtering before transcription.
	 */
	vad_filter_enabled: boolean;
	/**
	 * How aggressively low-audio hallucinations are discarded.
	 * "balanced" keeps catalog phrases that double as real dictation
	 * ("so", "you", "bye") unless the decoder confirms silence.
	 */
	hallucination_filter_mode: "strict" | "balanced" | "off";

	streaming_transcription: boolean;
	streaming_chunk_seconds: number;
	streaming_step_seconds: number;
	streaming_left_overlap_seconds: number;
	streaming_right_guard_seconds: number;
	streaming_min_first_chunk_seconds: number;
	streaming_silence_threshold: number;

	autostart: boolean;
	paste_on_stop: boolean;
	show_notifications: boolean;
	fast_startup: boolean;
	offline_pack_consent: boolean; // always-on; forced true on backend load

	clipboard_save_restore: boolean;
	clipboard_restore_delay_ms: number;

	asr_backend: "whisper" | "qwen" | "parakeet" | "cloud";
	qwen_model_path: string | null;
	parakeet_model_path: string | null;

	text_cleanup_enabled: boolean;
	corrections_path: string | null;
	log_transcriptions: boolean;

	// Password-field confirmation gate. OPTIONAL on the TS side for
	// backward compat with older sidecars (absence means `true`).
	warn_password_paste?: boolean;

	recording_mode: "toggle" | "push_to_talk";
	esc_cancel_enabled: boolean;
	repaste_hotkey: string;
	auto_punctuation: boolean;

	templates_enabled: boolean;
	vocabulary_enabled: boolean;

	cloud_api_key: string;
	cloud_api_url: string;
	cloud_model: string;
	// Which provider the "cloud" backend talks to. "" = none selected, which
	// leaves cloud inactive (the backend then reports itself not-loaded and
	// the registry degrades to whisper). The API key is NOT here: it lives in
	// the provider's own `<provider>_api_key` field below.
	cloud_provider: string;
	openai_api_key: string;
	groq_api_key: string;
	deepgram_api_key: string;
	gemini_api_key: string;

	llm_polish: boolean;
	llm_api_key: string;
	llm_api_url: string;
	llm_model: string;
	llm_preset: string;

	crash_recovery_enabled: boolean;

	audio_quality_warnings: boolean;

	waveform_bubble: boolean;

	bubble_position: "top" | "bottom";

	bubble_behavior: "show_on_record" | "always_visible" | "hidden";

	bubble_draggable: boolean;

	bubble_show_on_startup: boolean;

	bubble_click_to_toggle: boolean;

	//explicit mic-button visibility toggle. Default ON. When OFF
	bubble_mic_button: boolean;

	//show the recording duration (mm:ss) next to the red dot. Default OFF.
	bubble_show_recording_timer: boolean;

	// One-shot screenshot beta (Windows-only): master switch for the
	// bubble annotate button + region overlay. Default OFF (zero
	// behavior change while off).
	screenshot_beta_enabled: boolean;

	bubble_x: number | null;
	bubble_y: number | null;

	// this as `float = 1.0` and it's in the IPC allowlist. OPTIONAL on
	bubble_scale?: number;

	test_duration_seconds?: number;

	history_retention_days: number;
	history_retention_count: number;
	history_max_entries: number;

	onboarding_completed: boolean;
	// during guided setup). OPTIONAL because older sidecars
	onboarding_failed?: boolean;

	tray_left_click_action: "open_app" | "toggle_dictation";

	theme_mode: "system" | "light" | "dark";
	theme_preset:
		| "default"
		| "amoled"
		| "nord"
		| "dracula"
		| "sepia"
		| "solarized"
		| "monokai"
		| "ayu"
		| "github"
		| "catppuccin"
		| "tokyo-night"
		| "custom";
	custom_theme: {
		light: Record<string, string>;
		dark: Record<string, string>;
	} | null;

	// only). OPTIONAL for backward compat with older sidecars that
	linux_window_buttons?: LinuxWindowButtonsConfig;
	// (desktop button-layout + DE). OPTIONAL + nullable: absent on older
	linux_window_buttons_system?: LinuxWindowButtonsSystemInfo | null;

	text_size: number;

	wayland_warned: boolean;

	silence_warning_seconds: number;
	stop_on_silence_seconds: number;
	max_recording_time_seconds: number;

	volume_duck_enabled: boolean;
	volume_duck_level: number;
	/**
	 * dataclass (`voice_typer/server/config.py:775-781`), ducking now
	 * always applies to the master volume cross-platform. Existing
	 */
	volume_duck_per_session?: boolean;
	volume_duck_fade_ms: number;
	/**
	 * dataclass (`voice_typer/server/config.py:784-786`), smart duck
	 * is now ALWAYS ON when `volume_duck_enabled` is True. Existing
	 */
	volume_duck_smart?: boolean;
	volume_duck_smart_poll_interval_ms: number;

	/** Listen Live preview-tap level (0–1). Optional for back-compat with
	 *  sidecars predating the key; the renderer defaults to 0.5 and clamps
	 *  the resulting gain to LIVE_LISTEN_MAX. */
	live_listen_level?: number;
	/** Mic guard master toggle (default ON). Optional for back-compat. */
	mic_guard_enabled?: boolean;

	audio_preset: "auto" | "studio" | "noisy_room" | "off" | "custom";

	/** A user-saved microphone preset: stable id, display name, filter values. */
	custom_presets?: CustomMicPreset[];
	/** Selected saved preset while `audio_preset === "custom"`; null = ad-hoc values. */
	active_custom_preset?: string | null;

	noise_filter_enabled: boolean; // DEPRECATED
	noise_filter_highpass: boolean;
	noise_filter_highpass_cutoff_hz: number;
	noise_filter_gate: boolean;
	/**
	 * dataclass (`voice_typer/server/config.py:837-840`), replaced
	 * by the open/close threshold pair below per ADR 0007. Existing
	 */
	noise_filter_gate_threshold?: number; // DEPRECATED
	noise_filter_gate_hold_ms: number;
	noise_filter_gate_open_threshold_db: number;
	noise_filter_gate_close_threshold_db: number;
	noise_filter_gate_attack_ms: number;
	noise_filter_gate_release_ms: number;
	//ADR 0009: RUNTIME (server-controlled, not IPC-settable
	noise_filter_rnnoise: boolean; // RUNTIME (server-controlled, not IPC-settable per ADR 0009)
	//ADR 0009: RUNTIME (server-controlled, not IPC-settable
	noise_filter_post_capture: boolean; // RUNTIME (server-controlled, not IPC-settable per ADR 0009)
	noise_suppression_method: "dpdfnet" | "rnnoise" | "gtcrn" | "none";
	noise_filter_eq: boolean;
	noise_filter_eq_low_db: number;
	noise_filter_eq_mid_db: number;
	noise_filter_eq_high_db: number;
	noise_filter_compressor: boolean;
	noise_filter_compressor_threshold_db: number;
	noise_filter_compressor_ratio: number;
	noise_filter_compressor_attack_ms: number;
	noise_filter_compressor_release_ms: number;
	noise_filter_compressor_output_gain_db: number;
	noise_filter_limiter: boolean;
	noise_filter_limiter_ceiling_db: number;
	noise_filter_limiter_release_ms: number;
	noise_filter_notch: boolean;
	noise_filter_notch_frequency_hz: number;

	// false in the Python Config dataclass; the renderer must show a
	huggingface_consent: boolean;
	cloud_openai_consent: boolean;
	cloud_groq_consent: boolean;
	cloud_deepgram_consent: boolean;
	cloud_gemini_consent: boolean;
	voice_biometric_consent: boolean;
	llm_polish_consent: boolean;
	// ADR-0023: consent that media URLs are sent to the yt-dlp extractor.
	media_url_consent: boolean;
	// One-shot screenshot beta (Windows-only): consent that the
	// selected screen region is sent with the transcription.
	screenshot_consent: boolean;

	sound_feedback_enabled: boolean;

	sound_volume?: number;

	// must explicitly opt in via Settings → AI Enhancement.  The three
	ai_enhancement_enabled: boolean;
	auto_capitalize: boolean;
	auto_punctuate: boolean;
	fix_grammar_basics: boolean;

	vocabulary_automation_enabled: boolean;
	vocabulary_auto_confidence_threshold: number;
	vocabulary_auto_apply_threshold: number;

	secrets_migrated?: boolean;

	// runtime-probed state).  Optional because legacy responses
	keyring_status?: KeyringStatus;

	// defaults, missing optional files). Populated by
	// verbatim, so this attribute rides along). OPTIONAL because
	last_load_warnings?: string[] | null;
}

/**
 * : OS keychain backend status, attached to get_config responses.
 *
 */
export interface KeyringStatus {
	/**
	 * True when a real keyring backend (not the fail backend) is in use.
	 */
	available: boolean;
	/**
	 * Backend class name (e.g. "SecretServiceKeyring", "macOSKeyring",
	 * "WindowsCredentialVaultKeyring") when available, else null.
	 */
	backend: string | null;
	/**
	 * True when secrets will be stored in plaintext in config.json.
	 */
	fallback: boolean;
	/**
	 * Short reason string when available is false (tooltip-friendly).
	 */
	reason?: string | null;
}

export interface MicrophoneDevice {
	index: number;
	id?: string;
	name: string;
	host_api: string;
	default?: boolean;
	channels?: number;
	rate?: number;
}
