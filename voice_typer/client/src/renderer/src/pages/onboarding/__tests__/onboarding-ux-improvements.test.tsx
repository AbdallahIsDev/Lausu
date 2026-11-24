import {
	act,
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
	pythonMock,
	snackbarMock,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";
import ar from "@/i18n/translations/ar.json";
import de from "@/i18n/translations/de.json";
import en from "@/i18n/translations/en.json";
import es from "@/i18n/translations/es.json";
import fr from "@/i18n/translations/fr.json";
import hi from "@/i18n/translations/hi.json";
import ru from "@/i18n/translations/ru.json";
import zh from "@/i18n/translations/zh.json";
import { useConsentGateStore } from "@/lib/consentGate";
import OnboardingPage from "@/pages/Onboarding";
import ModelStep from "@/pages/onboarding/components/ModelStep";

const { mockCall } = stableMocks;

vi.mock("@/hooks/usePython", () => pythonMock({ noopEvent: true }));
vi.mock("@/hooks/useSnackbar", () => snackbarMock());
vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());

import { TooltipProvider } from "@/components/ui/tooltip";

const renderWithProviders = (ui: React.ReactElement) =>
	render(<TooltipProvider delayDuration={200}>{ui}</TooltipProvider>);

const STEP_NAMES = ["Welcome", "Consent", "Model", "Hotkey"] as const;
const MODEL_OPTIONS = [
	{
		name: "large-v3-turbo",
		display_name: "Whisper large-v3-turbo",
		size: "~886MB",
		speed: "Fast",
		description: "Recommended",
		backend: "whisper",
		recommended: true,
	},
	{
		name: "parakeet",
		size: "~740MB",
		speed: "Fast",
		description: "",
		backend: "parakeet",
	},
];

function mockWizard(
	startStep: number,
	overrides: {
		config?: Record<string, unknown>;
		status?: Record<string, { downloaded: boolean }>;
		microphones?: unknown[];
	} = {},
) {
	let current = startStep;
	const config = {
		hotkey: "<caps_lock>",
		model_size: "large-v3-turbo",
		microphone: null,
		huggingface_consent: false,
		...overrides.config,
	};
	mockCall.mockImplementation((type: string) => {
		switch (type) {
			case "onboarding_start":
				return Promise.resolve({
					step: startStep,
					total_steps: 4,
					step_name: STEP_NAMES[startStep],
				});
			case "onboarding_next_step":
				current = Math.min(current + 1, 3);
				return Promise.resolve({
					step: current,
					total_steps: 4,
					step_name: STEP_NAMES[current],
				});
			case "onboarding_prev_step":
				current = Math.max(current - 1, 0);
				return Promise.resolve({
					step: current,
					total_steps: 4,
					step_name: STEP_NAMES[current],
				});
			case "get_config":
				return Promise.resolve(config);
			case "onboarding_get_microphones":
				return Promise.resolve({
					microphones: overrides.microphones ?? [{ id: "default" }],
				});
			case "onboarding_get_hotkey_presets":
				return Promise.resolve({ presets: ["<caps_lock>", "<f2>"] });
			case "onboarding_get_model_options":
				return Promise.resolve({ models: MODEL_OPTIONS });
			case "get_model_catalog":
				return Promise.resolve({ models: [] });
			case "get_model_status":
				return Promise.resolve(overrides.status ?? {});
			case "onboarding_skip":
			case "onboarding_set_model":
			case "onboarding_set_backend":
			case "onboarding_set_hotkey":
			case "onboarding_apply":
			case "set_config":
			case "download_model":
				return Promise.resolve({});
			default:
				return Promise.resolve({});
		}
	});
}

function renderModelStep(
	status: Record<string, { downloaded: boolean }>,
	selectedModel: string,
) {
	return renderWithProviders(
		<ModelStep
			headingRef={{ current: null }}
			modelOptions={MODEL_OPTIONS}
			selectedModel={selectedModel}
			setSelectedModel={() => {}}
			selectedBackend="local"
			setSelectedBackend={() => {}}
			downloadingModel={null}
			downloadProgress={0}
			downloadFailed={false}
			onDownload={() => {}}
			modelStatus={status}
			cloudProvider="openai"
			setCloudProvider={() => {}}
			cloudApiKey=""
			setCloudApiKey={() => {}}
		/>,
	);
}

beforeEach(() => {
	mockCall.mockReset();
	useConsentGateStore.setState({ request: null });
});

afterEach(cleanup);

describe("Model step installed/Select/Download states (E2)", () => {
	it("offers Select for an installed model that is not selected", () => {
		renderModelStep({ "large-v3-turbo": { downloaded: true } }, "parakeet");
		expect(
			screen.getByTestId("onboarding-select-button-large-v3-turbo"),
		).toBeTruthy();
		expect(
			screen.queryByTestId("onboarding-download-button-large-v3-turbo"),
		).toBeNull();
	});

	it("shows the shared Active control for the installed, selected model", () => {
		renderModelStep(
			{ "large-v3-turbo": { downloaded: true } },
			"large-v3-turbo",
		);
		expect(
			screen.getByTestId("onboarding-active-button-large-v3-turbo"),
		).toBeTruthy();
	});

	it("still offers Download for a missing model", () => {
		renderModelStep({}, "large-v3-turbo");
		expect(
			screen.getByTestId("onboarding-download-button-large-v3-turbo"),
		).toBeTruthy();
	});
});

describe("consent-before-download ordering (E2/E3)", () => {
	it("opens the gate first and only downloads after Allow", async () => {
		mockWizard(2);
		renderWithProviders(<OnboardingPage onComplete={() => {}} />);
		await screen.findByText("Step 3 of 4");

		fireEvent.click(
			screen.getByTestId("onboarding-download-button-large-v3-turbo"),
		);

		await waitFor(() =>
			expect(useConsentGateStore.getState().request?.consentField).toBe(
				"huggingface_consent",
			),
		);
		expect(mockCall.mock.calls.some((c) => c[0] === "download_model")).toBe(
			false,
		);

		const request = useConsentGateStore.getState().request;
		await act(async () => {
			await request?.onAllow?.();
		});
		await waitFor(() =>
			expect(mockCall.mock.calls.some((c) => c[0] === "download_model")).toBe(
				true,
			),
		);
	});
});

describe("skip / back / microphone check (E2/E3)", () => {
	it("shows a microphone count on Welcome and can re-probe", async () => {
		mockWizard(0, { microphones: [] });
		renderWithProviders(<OnboardingPage onComplete={() => {}} />);
		await screen.findByTestId("onboarding-microphone-check");

		expect(
			screen.getByTestId("onboarding-microphone-check").textContent,
		).toContain("No microphone found");
		mockCall.mockImplementation((type: string) =>
			type === "onboarding_get_microphones"
				? Promise.resolve({ microphones: [{ id: "a" }, { id: "b" }] })
				: Promise.resolve({}),
		);
		fireEvent.click(screen.getByRole("button", { name: "Check again" }));
		await waitFor(() =>
			expect(
				screen.getByTestId("onboarding-microphone-check").textContent,
			).toContain("2 microphone(s) found"),
		);
	});

	it("requires confirmation before Skip completes onboarding", async () => {
		const onComplete = vi.fn();
		mockWizard(1);
		renderWithProviders(<OnboardingPage onComplete={onComplete} />);
		await screen.findByText("Step 2 of 4");

		fireEvent.click(screen.getByTestId("onboarding-skip"));
		expect(screen.getByText("Skip setup?")).toBeTruthy();
		expect(mockCall.mock.calls.some((c) => c[0] === "onboarding_skip")).toBe(
			false,
		);

		fireEvent.click(screen.getByRole("button", { name: "Skip setup" }));
		await waitFor(() =>
			expect(mockCall.mock.calls.some((c) => c[0] === "onboarding_skip")).toBe(
				true,
			),
		);
		expect(onComplete).toHaveBeenCalled();
	});

	it("Back moves to the previous step without applying", async () => {
		mockWizard(2);
		renderWithProviders(<OnboardingPage onComplete={() => {}} />);
		await screen.findByText("Step 3 of 4");

		fireEvent.click(screen.getByRole("button", { name: "Go back" }));
		await screen.findByText("Step 2 of 4");
		expect(mockCall.mock.calls.some((c) => c[0] === "onboarding_apply")).toBe(
			false,
		);
	});
});

describe("i18n completeness for new onboarding copy (E3)", () => {
	const locales = { en, zh, hi, es, ar, fr, ru, de } as const;
	const keys = [
		"skip",
		"skipAria",
		"skipTitle",
		"skipDescription",
		"skipConfirm",
		"microphoneReady",
		"microphoneMissing",
		"microphoneCheck",
		"orientation",
	] as const;

	it.each(Object.entries(locales))(
		"%s ships every new onboarding key",
		(code, dict) => {
			for (const key of keys) {
				const value = (
					dict as unknown as { onboarding: Record<string, unknown> }
				).onboarding[key];
				expect(value, `${code}.onboarding.${key}`).toBeTruthy();
				if (code !== "en") expect(value).not.toBe(en.onboarding[key]);
			}
		},
	);
});
