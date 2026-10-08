// Covers the Text Polish API key reveal control: an icon-only toggle
// whose accessible name is the only thing distinguishing its states.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";

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

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: vi.fn() }),
	usePythonEvent: () => {},
}));

vi.mock("@/hooks/useSnackbar", () => ({
	useSnackbar: () => ({ showSnack: vi.fn() }),
}));

vi.mock("sonner", () => ({
	toast: {
		success: vi.fn(),
		error: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
		dismiss: vi.fn(),
	},
	Toaster: () => null,
}));

vi.mock("next-themes", () => ({ useTheme: () => ({ theme: "light" }) }));

import { LlmPolishingSettingsSection } from "@/components/settings/LlmPolishingSettingsSection";
import type { SettingsSectionSharedProps } from "@/components/settings/types";
import type { LausuConfig } from "@/types/config";

function makeConfig(overrides: Partial<LausuConfig> = {}): LausuConfig {
	return {
		llm_polish: true,
		llm_polish_consent: true,
		llm_api_key: "",
		llm_api_url: undefined,
		llm_model: "",
		llm_preset: "professional",
		...overrides,
	} as LausuConfig;
}

const alwaysVisible: SettingsSectionSharedProps["isVisible"] = () => true;

function renderSection(config: LausuConfig) {
	return render(
		<TooltipProvider delayDuration={200}>
			<LlmPolishingSettingsSection
				config={config}
				updateConfig={() => {}}
				updateConfigDebounced={() => {}}
				isVisible={alwaysVisible}
			/>
		</TooltipProvider>,
	);
}

function apiKeyInput(): HTMLInputElement {
	return screen.getByLabelText("API Key") as HTMLInputElement;
}

/** The reveal control, located by the accessible name it swaps per state. */
function revealControl(name: "Show" | "Hide"): HTMLButtonElement {
	return screen.getByRole("button", { name }) as HTMLButtonElement;
}

afterEach(() => {
	cleanup();
});

describe("LlmPolishingSettingsSection, API key reveal control", () => {
	it("is icon-only, so its accessible name is what distinguishes the states", () => {
		renderSection(makeConfig());

		const button = revealControl("Show");
		expect(button.textContent).toBe("");
		expect(button.querySelector('[data-testid="hugeicon"]')).toBeTruthy();
		expect(button.getAttribute("aria-pressed")).toBe("false");
	});

	it("starts masked and reveals the key when pressed", () => {
		renderSection(makeConfig({ llm_api_key: "sk-test-123" }));

		expect(apiKeyInput().type).toBe("password");
		expect(apiKeyInput().value).toBe("sk-test-123");

		fireEvent.click(revealControl("Show"));

		expect(apiKeyInput().type).toBe("text");
		expect(apiKeyInput().value).toBe("sk-test-123");
		expect(revealControl("Hide").getAttribute("aria-pressed")).toBe("true");
	});

	it("re-masks the key when pressed again", () => {
		renderSection(makeConfig({ llm_api_key: "sk-test-123" }));

		fireEvent.click(revealControl("Show"));
		fireEvent.click(revealControl("Hide"));

		expect(apiKeyInput().type).toBe("password");
		expect(revealControl("Show")).toBeTruthy();
	});

	it("locks the key field and the reveal control while text polish is off", () => {
		renderSection(makeConfig({ llm_polish: false }));

		expect(apiKeyInput().disabled).toBe(true);
		expect(revealControl("Show").disabled).toBe(true);
	});
});
