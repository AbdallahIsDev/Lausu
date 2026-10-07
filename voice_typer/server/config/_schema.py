"""Config schema: the ``_ConfigSchema`` dataclass base."""

from dataclasses import dataclass, field
from typing import ClassVar, Literal, cast

from voice_typer.server._audio_constants import (
    _DEFAULT_SMART_DUCK_POLL_MS,
    WHISPER_SAMPLE_RATE,
)
from voice_typer.server._paths import DEFAULT_LLM_API_URL, DEFAULT_LLM_MODEL
from voice_typer.server.config._defaults import (
    DEFAULT_CLIPBOARD_RESTORE_DELAY_MS,
    _default_hotkey_for_platform,
)
from voice_typer.server.config._schema_validation import (  # noqa: F401, re-exported for __init__ + _lifecycle
    _ENUM_FIELDS_TO_RESET_ON_LOAD,
    _SECRET_FIELD_NAMES_FALLBACK,
    _reset_invalid_enum_fields_impl,
    _secret_field_names_impl,
)
from voice_typer.server.config_internals.migrations import _CURRENT_SCHEMA_VERSION
from voice_typer.server.hallucination import DEFAULT_HALLUCINATION_FILTER_MODE
from voice_typer.server.model_registry import DEFAULT_MODEL_SIZE


@dataclass
class _ConfigSchema:
    """Dataclass base holding ALL ``Config`` field declarations."""

    schema_version: int = _CURRENT_SCHEMA_VERSION
    # ``last_load_warnings`` was previously a

    # marks that plaintext API keys in config.json have been
    secrets_migrated: bool = False

    # Hotkey
    hotkey: str = _default_hotkey_for_platform()

    # Recording
    sample_rate: int = WHISPER_SAMPLE_RATE
    microphone: str | None = None  # None = system default

    # Transcription
    model_size: str = DEFAULT_MODEL_SIZE
    # Installed plugin that currently owns dictation ("" = local model).
    # Set from the Plugins page; a non-empty value must match an installed
    # plugin id, otherwise the local model stays in charge (fail-closed).
    active_plugin: str = ""
    language: str = "en"
    device: str = "cuda"  # cuda, cpu
    beam_size: int = 1  # 1 = fastest greedy decoding; higher values trade speed for accuracy
    best_of: int = 1
    condition_on_previous_text: bool = False
    # In the SEC-002 IPC allowlist so the Settings UI toggle persists it.
    vad_filter_enabled: bool = True
    # How aggressively low-audio hallucinations are discarded.
    # "balanced" keeps catalog phrases that are also real dictation
    # ("so", "you", "bye") unless the decoder confirms silence.
    hallucination_filter_mode: str = DEFAULT_HALLUCINATION_FILTER_MODE
    # Whisper-specific beam size override. Defaults to 1 (matching the
    whisper_beam_size: int = 1

    # Hidden streaming transcription
    streaming_transcription: bool = True
    streaming_chunk_seconds: float = 12.0
    streaming_step_seconds: float = 5.0
    streaming_left_overlap_seconds: float = 3.0
    streaming_right_guard_seconds: float = 1.5
    streaming_min_first_chunk_seconds: float = 6.0
    streaming_silence_threshold: float = 0.003

    # Behavior
    autostart: bool = True
    paste_on_stop: bool = True
    # client-side field now has a server counterpart
    unsafe_paste_on_unknown_focus: bool = False  # paste even when focus detection fails
    show_notifications: bool = True
    # warn when pasting into an elevated process from non-elevated
    warn_elevated_paste: bool = True
    # warn when pasting into a password field
    warn_password_paste: bool = True
    # Master toggle for the OS-level prewarm scheduled task.
    fast_startup: bool = True
    # Always-on pack auto-update (user product decision): no Settings
    # toggle, not in SEC-002 IPC allowlist, load path forces True.
    offline_pack_consent: bool = True

    # ASR backend selection
    asr_backend: Literal["whisper", "qwen", "parakeet"] = "whisper"
    qwen_model_path: str | None = None  # local path to Qwen3-ASR weights
    parakeet_model_path: str | None = None  # local override for Parakeet weights (None = HF cache)

    # re-enabled). NOT in ``IPC_CONFIG_ALLOWLIST`` because it is
    disabled_backends: list[str] = field(default_factory=list)

    # User-configured URL-allowlist extensions for self-hosted
    trusted_extra_hosts: list[str] = field(default_factory=list)

    # Text cleanup
    text_cleanup_enabled: bool = True  # Set False for raw (uncorrected) output

    # External corrections file
    corrections_path: str | None = None

    # Logging
    log_transcriptions: bool = False

    # Clipboard security settings.
    clipboard_save_restore: bool = True  # save/restore previous clipboard content after paste
    clipboard_restore_delay_ms: int = (
        DEFAULT_CLIPBOARD_RESTORE_DELAY_MS  # delay between paste keystroke and clipboard restore (ms)
    )

    # Push-to-talk mode (hold to record, release to stop)
    recording_mode: Literal["toggle", "push_to_talk"] = "toggle"

    # ESC to cancel at any stage
    esc_cancel_enabled: bool = True

    # Repaste last transcription
    repaste_hotkey: str = "<ctrl>+<alt>+v"  # Hotkey for repasting last

    # Auto-punctuation (runs AFTER template matching)
    auto_punctuation: bool = True

    # Templates
    templates_enabled: bool = True

    # Vocabulary
    vocabulary_enabled: bool = True

    # Cloud ASR backends
    cloud_api_key: str = ""
    cloud_api_url: str = ""
    cloud_model: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""
    deepgram_api_key: str = ""

    # LLM text polishing
    llm_polish: bool = False
    llm_api_key: str = ""
    llm_api_url: str = DEFAULT_LLM_API_URL
    llm_model: str = DEFAULT_LLM_MODEL
    llm_preset: str = "professional"  # professional/casual/email/code

    # Explicit user consent that text may leave the
    llm_polish_consent: bool = False

    # explicit consent that model weights are downloaded
    huggingface_consent: bool = False

    # explicit per-provider consent for cloud ASR.
    cloud_openai_consent: bool = False
    cloud_groq_consent: bool = False
    cloud_deepgram_consent: bool = False

    # explicit consent that voice recordings (which may
    voice_biometric_consent: bool = False

    # explicit consent that media URLs are sent to the extractor (yt-dlp)
    media_url_consent: bool = False

    # play a short audio cue when recording starts/stops.
    sound_feedback_enabled: bool = True

    # volume multiplier applied to the renderer's sound-feedback cues
    sound_volume: float = 1.0

    # Crash recovery
    crash_recovery_enabled: bool = True

    # Superseded: an earlier draft removed AudioQualityAnalyzer as
    audio_quality_warnings: bool = False

    # Waveform visualization bubble
    waveform_bubble: bool = False

    # Bubble screen position (top / bottom).  Default "bottom", the
    bubble_position: Literal["top", "bottom"] = "bottom"

    # Bubble behavior: show on record, always visible, or never
    bubble_behavior: Literal["show_on_record", "always_visible", "hidden"] = "show_on_record"

    # Whether the bubble can be dragged by the user
    bubble_draggable: bool = True

    # Whether to show the bubble at app startup (only applies when bubble_behavior is 'always_visible')
    bubble_show_on_startup: bool = True

    # when in `always_visible` mode, show a mic button next to the
    bubble_click_to_toggle: bool = True

    # explicit mic-button visibility toggle (independent of
    bubble_mic_button: bool = True

    # Show the recording duration (mm:ss) next to the red dot
    bubble_show_recording_timer: bool = False

    # Persisted bubble window position (screen-space pixel coords) and
    bubble_x: int | None = None
    bubble_y: int | None = None
    bubble_scale: float | None = None

    # Persisted microphone-test duration (seconds). The Microphone
    test_duration_seconds: int | None = None

    # History database
    history_enabled: bool = True
    history_retention_days: int = 90  # 0 = keep forever
    history_retention_count: int = 0  # 0 = unlimited
    history_max_entries: int = 1000

    # One-shot screenshot beta (Windows-only, local-only files).
    screenshot_beta_enabled: bool = False
    # JIT consent gate for screen capture.
    screenshot_consent: bool = False

    # Onboarding
    onboarding_completed: bool = False
    # marks that onboarding was force-completed after repeated
    onboarding_failed: bool = False

    # Tray icon left-click behavior
    tray_left_click_action: Literal["open_app", "toggle_dictation"] = "open_app"

    # Theme mode (system/light/dark)
    theme_mode: Literal["system", "light", "dark"] = "system"
    # Theme preset, a built-in colour scheme applied on top of the
    theme_preset: Literal[
        "default",
        "amoled",
        "nord",
        "dracula",
        "sepia",
        "solarized",
        "monokai",
        "ayu",
        "github",
        "catppuccin",
        "tokyo-night",
        "custom",
    ] = "default"
    # User-customised theme colours (only used when theme_preset == "custom").
    custom_theme: dict[str, dict[str, str]] | None = None

    # Linux title-bar window-button customization (Settings → Appearance).
    linux_window_buttons: dict[str, object] = field(
        default_factory=lambda: cast(
            "dict[str, object]",
            {
                "mode": "system",
                "side": "right",
                "show_minimize": True,
                "show_maximize": True,
                "show_close": True,
            },
        )
    )

    # Accessibility
    text_size: int = 14

    # Wayland hotkey fallback warning
    wayland_warned: bool = False

    # Silent mic disconnection
    silence_warning_seconds: float = 20.0
    stop_on_silence_seconds: float = 60.0
    # Single explicit field replaces the previous 3-field split
    max_recording_time_seconds: int = 900  # 15 minutes

    # NOTE: dead_air_timeout (float) was REMOVED in

    # silence_rms_threshold / silence_peak_threshold were REMOVED

    # Idle-unload timer for the active ASR backend. After this
    # many minutes without dictation the model is dropped from memory.
    # 60 (not 30): unloading inside a meeting is the worst possible
    # moment to cost the user a reload, and the committed memory is
    # only reclaimed when the app closes anyway (where it is
    # guaranteed). 0 disables the timer entirely. Surfaces in
    # Settings → General as a dropdown (15/30/60/90/120/Never).
    model_idle_unload_minutes: int = 60

    # VAD configuration for the recording callback.
    use_silero_vad: bool = True  # ADR 0007: was False, now True (torch available)
    vad_speech_threshold: float = 0.5  # Silero VAD prob > this → speech candidate
    vad_silence_threshold: float = 0.3  # Silero VAD prob < this → silence candidate
    # Auto-calibrate VAD thresholds from the ambient noise floor
    vad_auto_calibrate: bool = False

    # AUDIO-CH: number of channels to request from the input device.
    recording_channels: int = 1

    # AUDIO-PRE: pre-roll buffer captures audio before recording starts.
    pre_roll_buffer_seconds: float = 0.0

    # ADR 0007 §5.2: normalize_audio and normalize_target_peak REMOVED.

    # Reduces system volume during dictation to prevent speaker output
    volume_duck_enabled: bool = True
    volume_duck_level: float = 0.20  # 0.0–1.0 perceptual-linear (20% duck)
    #  ``volume_duck_per_session`` REMOVED from the Config
    volume_duck_fade_ms: int = 200  # 0–1000, 0 = instant
    #  ``volume_duck_smart`` REMOVED from the Config dataclass —
    volume_duck_smart_poll_interval_ms: int = _DEFAULT_SMART_DUCK_POLL_MS

    # Preset name that controls the entire filter chain:
    audio_preset: Literal[
        "auto",
        "studio",
        "noisy_room",
        "off",
        "custom",
        "none",
        "recommended",
    ] = "auto"

    # Each filter has an enable flag + parameters. The filter chain
    noise_filter_enabled: bool = True  # runtime switch, see ADR 0009
    noise_filter_highpass: bool = True
    noise_filter_highpass_cutoff_hz: float = 80.0  # 20–500
    noise_filter_gate: bool = True
    # ``noise_filter_gate_threshold`` REMOVED from the Config
    noise_filter_gate_hold_ms: float = 200.0  # ADR 0007: was 150, now 200 (matches OBS)
    noise_filter_rnnoise: bool = True  # ADR 0007: was False, now True (RNNoise is default dep)
    noise_filter_post_capture: bool = True  # runtime switch, see ADR 0009

    # ADR 0007 §5.1: New filter chain fields
    noise_suppression_method: Literal["rnnoise", "gtcrn", "none"] = "rnnoise"

    # NoiseGate (OBS-style, replaces single threshold)
    noise_filter_gate_open_threshold_db: float = -26.0
    noise_filter_gate_close_threshold_db: float = -32.0
    noise_filter_gate_attack_ms: float = 25.0
    noise_filter_gate_release_ms: float = 150.0
    # when True, gate samples the first ~500ms of audio to estimate
    noise_filter_gate_adaptive: bool = False

    # Equalizer (3-band)
    noise_filter_eq: bool = True
    noise_filter_eq_low_db: float = -3.0
    noise_filter_eq_mid_db: float = 3.0
    noise_filter_eq_high_db: float = 2.0

    # Compressor (replaces normalize_audio + _agc_update)
    noise_filter_compressor: bool = True
    noise_filter_compressor_threshold_db: float = -18.0
    noise_filter_compressor_ratio: float = 3.0
    noise_filter_compressor_attack_ms: float = 6.0
    noise_filter_compressor_release_ms: float = 60.0
    noise_filter_compressor_output_gain_db: float = 0.0

    # Limiter (brick-wall)
    noise_filter_limiter: bool = True
    noise_filter_limiter_ceiling_db: float = -6.0
    noise_filter_limiter_release_ms: float = 60.0

    # Notch filter (50/60Hz hum), optional, default OFF
    noise_filter_notch: bool = False
    noise_filter_notch_frequency_hz: float = 0.0  # 0 = auto-detect (60Hz Americas default)

    # Rule-based, offline enhancement applied AFTER LLM polish and
    ai_enhancement_enabled: bool = False  # master toggle (opt-in)
    auto_capitalize: bool = True  # capitalize sentence starts + proper nouns
    auto_punctuate: bool = True  # add periods at sentence boundaries
    fix_grammar_basics: bool = True  # fix bare "i", contractions, double spaces

    # Confidence-score-based auto-correction suggestions.  When the
    vocabulary_automation_enabled: bool = False  # master toggle (opt-in)
    # Below this segment-confidence, suggest corrections.  0.7 is a
    vocabulary_auto_confidence_threshold: float = 0.7
    # Above this confidence, auto-apply suggestions without asking.
    vocabulary_auto_apply_threshold: float = 0.95

    # ``ClassVar`` bindings of the module-level constants above —
    _ENUM_FIELDS_TO_RESET_ON_LOAD: ClassVar[frozenset[str]] = _ENUM_FIELDS_TO_RESET_ON_LOAD
    _SECRET_FIELD_NAMES_FALLBACK: ClassVar[frozenset[str]] = _SECRET_FIELD_NAMES_FALLBACK
