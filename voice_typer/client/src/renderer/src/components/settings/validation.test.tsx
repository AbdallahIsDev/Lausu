import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: () => <span data-testid="hugeicon" />,
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

vi.mock("@/components/feedback/InfoTooltip", () => ({
	InfoTooltip: ({ text }: { text: string }) => (
		<span data-testid="info-tooltip" data-text={text} />
	),
}));

vi.mock("@/components/common/KeyringStatusBadge", () => ({
	KeyringStatusBadge: () => <span data-testid="keyring-badge" />,
}));

vi.mock("@/lib/consentGate", () => ({
	openConsentGate: vi.fn(),
	consentBodyKey: (field: string) => `consent.${field}`,
}));

const sliderInstances: Array<{
	ariaLabel: string;
	value: number;
	onChange: (v: number) => void;
	disabled: boolean;
}> = [];

vi.mock("@/components/common/RangeSlider", () => ({
	RangeSlider: (props: {
		ariaLabel?: string;
		value: number;
		onChange: (v: number) => void;
		disabled?: boolean;
	}) => {
		sliderInstances.push({
			ariaLabel: props.ariaLabel ?? "",
			value: props.value,
			onChange: props.onChange,
			disabled: props.disabled ?? false,
		});
		return <div data-testid="range-slider" data-value={props.value} />;
	},
}));

import { makeConfig } from "@/__tests__/helpers/fixtures";
import { LlmPolishingSettingsSection } from "@/components/settings/LlmPolishingSettingsSection";
import { PostProcessingSettingsSection } from "@/components/settings/PostProcessingSettingsSection";

const alwaysVisible = () => true;
const noopUpdate = () => {};

describe("PostProcessingSettingsSection, vocab automation row", () => {
	beforeEach(() => {
		sliderInstances.length = 0;
	});

	afterEach(() => {
		cleanup();
	});

	it("renders the Vocabulary Automation toggle with zero sliders", () => {
		render(
			<PostProcessingSettingsSection
				config={makeConfig({
					vocabulary_automation_enabled: true,
				})}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		expect(sliderInstances).toHaveLength(0);
		expect(
			screen.getByRole("switch", { name: "Vocabulary Automation" }),
		).toBeTruthy();
	});

	it("renders the Text Snippets row with toggle and Open Text Snippets button", () => {
		const navigate = vi.fn();
		render(
			<PostProcessingSettingsSection
				config={makeConfig({ templates_enabled: true })}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
				onNavigate={navigate}
			/>,
		);
		expect(screen.getByTestId("open-templates-button")).toBeTruthy();
		fireEvent.click(screen.getByTestId("open-templates-button"));
		expect(navigate).toHaveBeenCalledWith("templates");
	});
});

describe("LlmPolishingSettingsSection, LLM API URL validation", () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	afterEach(() => {
		cleanup();
	});

	it("shows no error while typing (validation does not block typing)", () => {
		const updateConfigDebounced = vi.fn();
		render(
			<LlmPolishingSettingsSection
				config={makeConfig({ llm_polish: true, llm_api_url: "" })}
				updateConfig={noopUpdate}
				updateConfigDebounced={updateConfigDebounced}
				isVisible={alwaysVisible}
			/>,
		);
		const input = screen.getByLabelText("API URL") as HTMLInputElement;
		fireEvent.change(input, { target: { value: "not a url" } });
		expect(updateConfigDebounced).toHaveBeenCalledWith(
			"llm_api_url",
			"not a url",
		);
		expect(screen.queryByTestId("llm-api-url-error")).toBeNull();
	});

	it("shows the inline error on blur for a non-http(s) value", () => {
		render(
			<LlmPolishingSettingsSection
				config={makeConfig({ llm_polish: true, llm_api_url: "" })}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		const input = screen.getByLabelText("API URL") as HTMLInputElement;
		fireEvent.change(input, { target: { value: "ftp://bad.example" } });
		fireEvent.blur(input);
		expect(screen.getByTestId("llm-api-url-error")).toBeTruthy();
		expect(input.getAttribute("aria-invalid")).toBe("true");
	});

	it("rejects scheme-less values on blur", () => {
		render(
			<LlmPolishingSettingsSection
				config={makeConfig({
					llm_polish: true,
					llm_api_url: "api.openai.com/v1",
				})}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		const input = screen.getByLabelText("API URL") as HTMLInputElement;
		fireEvent.blur(input);
		expect(screen.getByTestId("llm-api-url-error")).toBeTruthy();
	});

	it("clears the error once a valid https URL is entered and blurred", () => {
		render(
			<LlmPolishingSettingsSection
				config={makeConfig({ llm_polish: true, llm_api_url: "" })}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		const input = screen.getByLabelText("API URL") as HTMLInputElement;
		fireEvent.change(input, { target: { value: "garbage" } });
		fireEvent.blur(input);
		expect(screen.getByTestId("llm-api-url-error")).toBeTruthy();

		fireEvent.change(input, {
			target: { value: "https://api.groq.com/openai/v1" },
		});
		fireEvent.blur(input);
		expect(screen.queryByTestId("llm-api-url-error")).toBeNull();
	});

	it("accepts http and https URLs on blur without error", () => {
		render(
			<LlmPolishingSettingsSection
				config={makeConfig({
					llm_polish: true,
					llm_api_url: "http://localhost:8000/v1",
				})}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		const input = screen.getByLabelText("API URL") as HTMLInputElement;
		fireEvent.blur(input);
		expect(screen.queryByTestId("llm-api-url-error")).toBeNull();
	});

	it("accepts an empty value on blur (server falls back to the default endpoint)", () => {
		render(
			<LlmPolishingSettingsSection
				config={makeConfig({ llm_polish: true, llm_api_url: "" })}
				updateConfig={noopUpdate}
				updateConfigDebounced={noopUpdate}
				isVisible={alwaysVisible}
			/>,
		);
		const input = screen.getByLabelText("API URL") as HTMLInputElement;
		fireEvent.blur(input);
		expect(screen.queryByTestId("llm-api-url-error")).toBeNull();
	});
});
