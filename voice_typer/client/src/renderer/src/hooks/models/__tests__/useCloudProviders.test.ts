import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ── Mocks ───────────────────────────────────────────────────────────
vi.mock("@/i18n/i18n", () => ({
	t: (key: string, params?: Record<string, string>) => {
		if (!params) return key;
		let result = key;
		const leftover: string[] = [];
		for (const [k, v] of Object.entries(params)) {
			const placeholder = `{${k}}`;
			if (result.includes(placeholder)) {
				result = result.replace(placeholder, String(v));
			} else {
				leftover.push(`${k}=${String(v)}`);
			}
		}
		if (leftover.length > 0) {
			result = `${result}: ${leftover.join(", ")}`;
		}
		return result;
	},
}));

// The point-of-use consent gate is a zustand store module. It is
// mocked so the hook's DECISION to open the dialog is observable
// without mounting `ConsentGateDialog` (which has its own suite in
// `__tests__/behavior-rewrite/consent-privacy-behavior.test.tsx`).
const { openConsentGateMock } = vi.hoisted(() => ({
	openConsentGateMock: vi.fn(),
}));

vi.mock("@/lib/consentGate", () => ({
	openConsentGate: openConsentGateMock,
	consentBodyKey: (field: string) => `consentDialog.field.${field}`,
}));

// ── Helpers ──────────────────────────────────────────────────────────
import {
	safeApiKey,
	useCloudProviders,
} from "@/hooks/models/useCloudProviders";
import type { LausuConfig } from "@/types/config";

const callMock = vi.fn();
const showSnackMock = vi.fn();
const updateConfigMock = vi.fn().mockResolvedValue(undefined);
const setConfigMock = vi.fn();

// Realistically-shaped keys (the hook now rejects anything that is not
// a published shape for the provider). See `API_KEY_PATTERNS` in
// `lib/utils/models.ts` for the detectors these are drawn from.
const OPENAI_KEY = `sk-${"A".repeat(24)}`;
const GROQ_KEY = `gsk_${"a".repeat(52)}`;
const DEEPGRAM_KEY = "a".repeat(40);
const GEMINI_KEY = `AIza${"A".repeat(35)}`;
/** The user's "I just typed something" case from the bug report. */
const GARBAGE = "GFHFGHHFGH";

function makeConfig(overrides: Partial<LausuConfig> = {}): LausuConfig {
	return {
		schema_version: 1,
		hotkey: "<f2>",
		sample_rate: 16000,
		microphone: null,
		model_size: "tiny",
		language: "en",
		device: "cpu",
		beam_size: 5,
		best_of: 5,
		condition_on_previous_text: false,
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
		clipboard_save_restore: true,
		clipboard_restore_delay_ms: 0,
		asr_backend: "whisper",
		qwen_model_path: null,
		parakeet_model_path: null,
		openai_api_key: "",
		groq_api_key: "",
		deepgram_api_key: "",
		gemini_api_key: "",
		huggingface_consent: false,
		cloud_openai_consent: false,
		cloud_groq_consent: false,
		cloud_deepgram_consent: false,
		cloud_gemini_consent: false,
		...overrides,
	} as LausuConfig;
}

function makeHookArgs(
	apiKeys: Record<string, string>,
	config: LausuConfig | null,
) {
	return {
		showSnack: showSnackMock,
		config,
		apiKeys,
		updateConfig: updateConfigMock,
		// Consumed by `activateCloudModel`'s optimistic merge (the Active
		// marker must move on the click, not on the `config_changed`
		// echo). Save / Test never touch it.
		setConfig: setConfigMock,
		call: callMock as unknown as <T = unknown>(
			cmd: string,
			data?: Record<string, unknown>,
		) => Promise<T>,
	};
}

beforeEach(() => {
	callMock.mockReset();
	showSnackMock.mockReset();
	updateConfigMock.mockReset().mockResolvedValue(undefined);
	setConfigMock.mockReset();
	openConsentGateMock.mockReset();
});

afterEach(() => {
	vi.clearAllMocks();
});

// ── safeApiKey helper (module-level, re-exported) ─────────────────────
describe("safeApiKey, secret redaction sentinel", () => {
	it("returns the value unchanged when it is a real key", () => {
		expect(safeApiKey("sk-real-key")).toBe("sk-real-key");
	});

	it("strips the <redacted> sentinel, the renderer never displays the marker", () => {
		// The backend substitutes `<redacted>` for saved API keys in
		// get_config responses. safeApiKey converts that sentinel to ""
		// so the renderer shows an empty input field instead of the
		// literal string "<redacted>".
		expect(safeApiKey("<redacted>")).toBe("");
	});

	it("normalizes null / undefined to empty string", () => {
		expect(safeApiKey(null)).toBe("");
		expect(safeApiKey(undefined)).toBe("");
	});

	it("preserves empty string (no false positive on the sentinel check)", () => {
		expect(safeApiKey("")).toBe("");
	});
});

// ── saveApiKey validation guards ──────────────────────────────────────
describe("useCloudProviders, saveApiKey validation guards", () => {
	it("bails out with an info snack when the key is empty (prevents clobbering stored key with '')", async () => {
		const args = makeHookArgs({ openai: "" }, makeConfig());
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.saveApiKey("openai");
		});

		expect(showSnackMock).toHaveBeenCalledWith(
			"models.snack.apiKeyEmpty",
			"info",
		);
		// updateConfig NOT called, no IPC round-trip.
		expect(updateConfigMock).not.toHaveBeenCalled();
		expect(openConsentGateMock).not.toHaveBeenCalled();
	});

	it("REJECTS a typed string that cannot be a key, with an error toast and no write", async () => {
		// The bug report: typing "GFHFGHHFGH" and hitting Save Key
		// produced a green "API key saved" toast. It must now be
		// refused before the credential store is touched.
		const args = makeHookArgs({ openai: GARBAGE }, makeConfig());
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.saveApiKey("openai");
		});

		expect(updateConfigMock).not.toHaveBeenCalled();
		expect(showSnackMock).toHaveBeenCalledWith(
			"models.snack.apiKeyInvalid: provider=models.providers.openai.label",
			"error",
		);
		// Nothing was stored, so there is nothing to consent to.
		expect(openConsentGateMock).not.toHaveBeenCalled();
	});

	it("rejects a key that is the right length but the wrong alphabet (gemini prefix missing)", async () => {
		const args = makeHookArgs({ gemini: "A".repeat(39) }, makeConfig());
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.saveApiKey("gemini");
		});

		expect(updateConfigMock).not.toHaveBeenCalled();
		expect(showSnackMock).toHaveBeenCalledWith(
			expect.stringContaining("models.snack.apiKeyInvalid"),
			"error",
		);
	});

	it("bails out with an info snack when the key matches the persisted value (no-op)", async () => {
		const cfg = makeConfig({ openai_api_key: OPENAI_KEY });
		const args = makeHookArgs({ openai: OPENAI_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.saveApiKey("openai");
		});

		expect(showSnackMock).toHaveBeenCalledWith(
			"models.snack.apiKeyUnchanged",
			"info",
		);
		expect(updateConfigMock).not.toHaveBeenCalled();
	});

	it("persists the key via updateConfig when the key is non-empty + differs from persisted", async () => {
		const cfg = makeConfig({ openai_api_key: `sk-${"B".repeat(24)}` });
		const args = makeHookArgs({ openai: OPENAI_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.saveApiKey("openai");
		});

		expect(updateConfigMock).toHaveBeenCalledWith({
			openai_api_key: OPENAI_KEY,
		});
		expect(showSnackMock).toHaveBeenCalledWith(
			expect.stringContaining("models.snack.apiKeySaved"),
			"success",
		);
	});

	it("treats a redacted persisted value as empty (safeApiKey strips the sentinel), so a re-typed key always saves", async () => {
		// This is the regression guard for the secret-redaction flow:
		// after navigating away and back, the persisted key shows up as
		// `<redacted>` in the config. safeApiKey converts that to "",
		// so the "unchanged" guard does NOT match a freshly-typed key
		// against the literal string `<redacted>`, the save proceeds.
		const cfg = makeConfig({ openai_api_key: "<redacted>" });
		const args = makeHookArgs({ openai: OPENAI_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.saveApiKey("openai");
		});

		expect(updateConfigMock).toHaveBeenCalledWith({
			openai_api_key: OPENAI_KEY,
		});
		expect(showSnackMock).toHaveBeenCalledWith(
			expect.stringContaining("models.snack.apiKeySaved"),
			"success",
		);
	});

	it.each([
		["groq", GROQ_KEY, "groq_api_key"],
		["deepgram", DEEPGRAM_KEY, "deepgram_api_key"],
		["gemini", GEMINI_KEY, "gemini_api_key"],
	] as const)(
		"accepts the published %s key shape and writes it to %s",
		async (provider, key, field) => {
			const args = makeHookArgs({ [provider]: key }, makeConfig());
			const { result } = renderHook(() => useCloudProviders(args));

			await act(async () => {
				await result.current.saveApiKey(provider);
			});

			expect(updateConfigMock).toHaveBeenCalledWith({ [field]: key });
			expect(showSnackMock).toHaveBeenCalledWith(
				expect.stringContaining("models.snack.apiKeySaved"),
				"success",
			);
		},
	);
});

// ── Consent gate (point-of-use, opened by Save / Test) ────────────────
describe("useCloudProviders, audio-transmission consent gate", () => {
	it("opens the shared consent dialog after a successful save, for the provider's own consent field", async () => {
		const args = makeHookArgs({ gemini: GEMINI_KEY }, makeConfig());
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.saveApiKey("gemini");
		});

		expect(openConsentGateMock).toHaveBeenCalledTimes(1);
		expect(openConsentGateMock).toHaveBeenCalledWith({
			consentField: "cloud_gemini_consent",
			bodyKey: "consentDialog.field.cloud_gemini_consent",
		});
	});

	it("does NOT open the dialog when the consent was already granted", async () => {
		const cfg = makeConfig({ cloud_openai_consent: true });
		const args = makeHookArgs({ openai: OPENAI_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.saveApiKey("openai");
		});

		expect(openConsentGateMock).not.toHaveBeenCalled();
	});

	it("opens the dialog from Test Connection too, so the probe is never run on an unconsented provider", async () => {
		callMock.mockResolvedValue({ ok: true, status: 200, message: "OK" });
		const args = makeHookArgs({ deepgram: DEEPGRAM_KEY }, makeConfig());
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.testConnection("deepgram");
		});

		expect(openConsentGateMock).toHaveBeenCalledWith({
			consentField: "cloud_deepgram_consent",
			bodyKey: "consentDialog.field.cloud_deepgram_consent",
		});
	});

	it("does not re-ask on a re-test when consent is already granted", async () => {
		callMock.mockResolvedValue({ ok: true, status: 200, message: "OK" });
		const cfg = makeConfig({
			cloud_deepgram_consent: true,
			deepgram_api_key: DEEPGRAM_KEY,
		});
		const args = makeHookArgs({ deepgram: DEEPGRAM_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.testConnection("deepgram");
		});

		expect(openConsentGateMock).not.toHaveBeenCalled();
	});
});

// ── testConnection lifecycle ──────────────────────────────────────────
describe("useCloudProviders, testConnection lifecycle", () => {
	it("reports 'enter a key first' and never calls the backend when the key is empty", async () => {
		const args = makeHookArgs({}, makeConfig());
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.testConnection("openai");
		});

		expect(showSnackMock).toHaveBeenCalledWith(
			"models.test.needApiKey",
			"info",
		);
		expect(callMock).not.toHaveBeenCalled();
	});

	it("rejects an un-shaped key before probing (no IPC, error toast)", async () => {
		const args = makeHookArgs({ openai: GARBAGE }, makeConfig());
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.testConnection("openai");
		});

		expect(callMock).not.toHaveBeenCalled();
		expect(updateConfigMock).not.toHaveBeenCalled();
		expect(showSnackMock).toHaveBeenCalledWith(
			expect.stringContaining("models.snack.apiKeyInvalid"),
			"error",
		);
	});

	it("reports success as a toast and clears the in-flight flag", async () => {
		callMock.mockResolvedValue({ ok: true, status: 200, message: "OK" });
		const args = makeHookArgs({ openai: OPENAI_KEY }, makeConfig());
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.testConnection("openai");
		});

		expect(showSnackMock).toHaveBeenCalledWith(
			"models.test.connectionSuccessful",
			"success",
		);
		expect(callMock).toHaveBeenCalledWith("test_cloud_connection", {
			provider: "openai",
		});
		expect(result.current.testingProviders.openai).toBeUndefined();
	});

	it("marks the provider in flight while the probe is pending", async () => {
		// Deferred backend response so the pending state is observable
		// before the terminal branch clears it. The panel reads this
		// map to disable the Test button and show its spinner.
		let resolveBackend: (value: {
			ok: boolean;
			status: number;
			message: string;
		}) => void = () => {};
		callMock.mockReturnValue(
			new Promise<{ ok: boolean; status: number; message: string }>(
				(resolve) => {
					resolveBackend = resolve;
				},
			),
		);
		const args = makeHookArgs({ openai: OPENAI_KEY }, makeConfig());
		const { result } = renderHook(() => useCloudProviders(args));

		let inFlight: Promise<void> | undefined;
		await act(async () => {
			inFlight = result.current.testConnection("openai");
			await Promise.resolve();
			await Promise.resolve();
			await Promise.resolve();
		});

		expect(result.current.testingProviders.openai).toBe(true);

		resolveBackend({ ok: true, status: 200, message: "OK" });
		await act(async () => {
			await inFlight;
		});
		expect(result.current.testingProviders.openai).toBeUndefined();
	});

	it.each([
		["auth_failed", "models.test.failure.auth"],
		["rate_limited", "models.test.failure.rateLimited"],
		["server_error", "models.test.failure.server"],
		["network_error", "models.test.failure.network"],
	] as const)(
		"translates the backend token %s into readable copy (%s)",
		async (token, expectedKey) => {
			callMock.mockResolvedValue({ ok: false, status: 401, message: token });
			const args = makeHookArgs({ openai: OPENAI_KEY }, makeConfig());
			const { result } = renderHook(() => useCloudProviders(args));

			await act(async () => {
				await result.current.testConnection("openai");
			});

			expect(showSnackMock).toHaveBeenCalledWith(
				expect.stringContaining(expectedKey),
				"error",
			);
		},
	);

	it("maps an unrecognised token (the raw `http_error` case) to the generic http copy with the status interpolated", async () => {
		// The bug report: "Connection failed: 400 http_error" rendered
		// inline next to the button. The token must never reach the user
		// verbatim, and the HTTP status must be carried into the
		// sentence so the message is actionable.
		callMock.mockResolvedValue({
			ok: false,
			status: 400,
			message: "http_error",
		});
		const args = makeHookArgs({ openai: OPENAI_KEY }, makeConfig());
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.testConnection("openai");
		});

		const calls = showSnackMock.mock.calls;
		const [message, kind] = calls[calls.length - 1] as [string, string];
		expect(kind).toBe("error");
		expect(message).toContain("models.test.failure.http");
		expect(message).toContain("status=400");
		expect(message).not.toContain("http_error");
	});

	it("reports an IPC throw as a toast carrying the error message", async () => {
		callMock.mockRejectedValue(new Error("network unreachable"));
		const args = makeHookArgs({ openai: OPENAI_KEY }, makeConfig());
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.testConnection("openai");
		});

		expect(showSnackMock).toHaveBeenCalledWith(
			"models.test.connectionTestFailed: error=network unreachable",
			"error",
		);
		expect(result.current.testingProviders.openai).toBeUndefined();
	});

	it("probes even when the key is unchanged (re-testing a stored key is the common case)", async () => {
		callMock.mockResolvedValue({ ok: true, status: 200, message: "OK" });
		const cfg = makeConfig({ openai_api_key: OPENAI_KEY });
		const args = makeHookArgs({ openai: OPENAI_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.testConnection("openai");
		});

		expect(updateConfigMock).not.toHaveBeenCalled();
		expect(callMock).toHaveBeenCalledWith("test_cloud_connection", {
			provider: "openai",
		});
	});

	it("keeps the two providers' in-flight flags independent", async () => {
		const resolvers: Record<
			string,
			| ((value: { ok: boolean; status: number; message: string }) => void)
			| undefined
		> = {};
		callMock.mockImplementation(
			(_cmd: string, data?: Record<string, unknown>) =>
				new Promise<{ ok: boolean; status: number; message: string }>(
					(resolve) => {
						resolvers[String(data?.provider)] = resolve;
					},
				),
		);
		const args = makeHookArgs(
			{ openai: OPENAI_KEY, groq: GROQ_KEY },
			makeConfig(),
		);
		const { result } = renderHook(() => useCloudProviders(args));

		let openaiRun: Promise<void> | undefined;
		let groqRun: Promise<void> | undefined;
		await act(async () => {
			openaiRun = result.current.testConnection("openai");
			groqRun = result.current.testConnection("groq");
			for (let i = 0; i < 4; i++) await Promise.resolve();
		});

		expect(result.current.testingProviders).toEqual({
			openai: true,
			groq: true,
		});

		resolvers.openai?.({ ok: true, status: 200, message: "OK" });
		await act(async () => {
			await openaiRun;
		});
		expect(result.current.testingProviders).toEqual({ groq: true });

		resolvers.groq?.({ ok: true, status: 200, message: "OK" });
		await act(async () => {
			await groqRun;
		});
		expect(result.current.testingProviders).toEqual({});
	});
});

// ── activateCloudModel ────────────────────────────────────────────────
// Making one of a provider's models the active speech backend. The whole
// point of the feature is that the THREE config fields move together, so
// the assertions below are written against the exact object handed to
// `updateConfig`, not against individual fields.
describe("useCloudProviders, activateCloudModel", () => {
	it("refuses with the 'enter a key first' toast when the provider has no stored key", async () => {
		// Without a key the backend's CloudAsrBackend resolves to
		// "not loaded" and `get_active()` silently falls back to whisper
		// — the user would have "activated" a model that never runs.
		const cfg = makeConfig({ cloud_openai_consent: true });
		const args = makeHookArgs({}, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.activateCloudModel("openai", "whisper-1");
		});

		expect(showSnackMock).toHaveBeenCalledWith(
			"models.test.needApiKey",
			"info",
		);
		expect(updateConfigMock).not.toHaveBeenCalled();
		expect(setConfigMock).not.toHaveBeenCalled();
		expect(openConsentGateMock).not.toHaveBeenCalled();
	});

	it("treats a <redacted> persisted key as absent (safeApiKey), so it still refuses", async () => {
		const cfg = makeConfig({
			openai_api_key: "<redacted>",
			cloud_openai_consent: true,
		});
		const args = makeHookArgs({}, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.activateCloudModel("openai", "whisper-1");
		});

		expect(updateConfigMock).not.toHaveBeenCalled();
		expect(showSnackMock).toHaveBeenCalledWith(
			"models.test.needApiKey",
			"info",
		);
	});

	it("opens the shared consent dialog (with a retry) instead of activating when consent is missing", async () => {
		const cfg = makeConfig({ openai_api_key: OPENAI_KEY });
		const args = makeHookArgs({ openai: OPENAI_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.activateCloudModel("openai", "gpt-4o-transcribe");
		});

		// Nothing is written yet — Allow is what retries.
		expect(updateConfigMock).not.toHaveBeenCalled();
		expect(openConsentGateMock).toHaveBeenCalledTimes(1);
		const gateCalls = openConsentGateMock.mock.calls;
		const request = gateCalls[gateCalls.length - 1]?.[0] as {
			consentField: string;
			bodyKey: string;
			onAllow?: () => void;
		};
		expect(request.consentField).toBe("cloud_openai_consent");
		expect(request.bodyKey).toBe("consentDialog.field.cloud_openai_consent");
		expect(typeof request.onAllow).toBe("function");

		// The Allow button re-runs the SAME activation.
		await act(async () => {
			await request.onAllow?.();
		});
		expect(updateConfigMock).toHaveBeenCalledWith({
			asr_backend: "cloud",
			cloud_provider: "openai",
			cloud_model: "gpt-4o-transcribe",
		});
	});

	it("maps gemini to its own consent field", async () => {
		const cfg = makeConfig({ gemini_api_key: GEMINI_KEY });
		const args = makeHookArgs({ gemini: GEMINI_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.activateCloudModel("gemini", "gemini-3.8-flash");
		});

		expect(openConsentGateMock).toHaveBeenCalledWith(
			expect.objectContaining({ consentField: "cloud_gemini_consent" }),
		);
	});

	it("writes asr_backend + cloud_provider + cloud_model together and reports the display name", async () => {
		const cfg = makeConfig({
			groq_api_key: GROQ_KEY,
			cloud_groq_consent: true,
		});
		const args = makeHookArgs({ groq: GROQ_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.activateCloudModel("groq", "whisper-large-v3-turbo");
		});

		// `asr_backend: "cloud"` is what deactivates the previously active
		// LOCAL model — there is no separate "active" flag.
		expect(updateConfigMock).toHaveBeenCalledWith({
			asr_backend: "cloud",
			cloud_provider: "groq",
			cloud_model: "whisper-large-v3-turbo",
		});
		// The toast uses the catalogue's display name, not the raw id.
		expect(showSnackMock).toHaveBeenCalledWith(
			"models.snack.usingModel: name=Whisper Large V3 Turbo",
			"success",
		);
		expect(openConsentGateMock).not.toHaveBeenCalled();
	});

	it("merges the three fields into config state optimistically (no waiting for the echo)", async () => {
		const cfg = makeConfig({
			openai_api_key: OPENAI_KEY,
			cloud_openai_consent: true,
		});
		const args = makeHookArgs({ openai: OPENAI_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.activateCloudModel("openai", "whisper-1");
		});

		expect(setConfigMock).toHaveBeenCalledTimes(1);
		const mergeCalls = setConfigMock.mock.calls;
		const merge = mergeCalls[mergeCalls.length - 1]?.[0] as (
			prev: LausuConfig | null,
		) => LausuConfig | null;
		const prev = makeConfig({ asr_backend: "whisper" });
		expect(merge(prev)).toEqual({
			...prev,
			asr_backend: "cloud",
			cloud_provider: "openai",
			cloud_model: "whisper-1",
		});
		// A null config (still loading) must stay null, not become an object.
		expect(merge(null)).toBeNull();
	});

	it("marks only the clicked row in flight, then clears it", async () => {
		let resolveWrite: () => void = () => {};
		updateConfigMock.mockReturnValue(
			new Promise<void>((resolve) => {
				resolveWrite = resolve;
			}),
		);
		const cfg = makeConfig({
			openai_api_key: OPENAI_KEY,
			cloud_openai_consent: true,
		});
		const args = makeHookArgs({ openai: OPENAI_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		let run: Promise<void> | undefined;
		await act(async () => {
			run = result.current.activateCloudModel("openai", "whisper-1");
			await Promise.resolve();
		});

		expect(result.current.selectingCloudModel).toEqual({
			provider: "openai",
			model: "whisper-1",
		});

		resolveWrite();
		await act(async () => {
			await run;
		});
		expect(result.current.selectingCloudModel).toBeNull();
	});

	it("reports a failed write as an error toast and does NOT merge the config", async () => {
		updateConfigMock.mockRejectedValue(new Error("validation failed"));
		const cfg = makeConfig({
			openai_api_key: OPENAI_KEY,
			cloud_openai_consent: true,
		});
		const args = makeHookArgs({ openai: OPENAI_KEY }, cfg);
		const { result } = renderHook(() => useCloudProviders(args));

		await act(async () => {
			await result.current.activateCloudModel("openai", "whisper-1");
		});

		expect(showSnackMock).toHaveBeenCalledWith(
			"models.snack.selectFailed: name=Whisper 1, error=validation failed",
			"error",
		);
		// The UI must stay in sync with what the backend actually
		// persisted — nothing was, so no optimistic merge.
		expect(setConfigMock).not.toHaveBeenCalled();
		expect(result.current.selectingCloudModel).toBeNull();
	});
});
