import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CloudProvidersPanel } from "@/components/models/CloudProvidersPanel";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { ApiTestResult } from "@/hooks/useModelLifecycle";
import {
	CLOUD_PROVIDERS,
	type CloudProvider,
	formatModelSpeed,
	formatWer,
} from "@/lib/utils/models";
import type { LausuConfig } from "@/types/config";

// Mock the HugeiconsIcon wrapper so the test doesn't depend on the SVG
// renderer.
vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: ({
		children,
		icon,
	}: {
		children?: React.ReactNode;
		icon?: { name?: string };
	}) => (
		<span data-testid="hugeicon" data-name={icon?.name}>
			{children}
		</span>
	),
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

// Stub KeyringStatusBadge so we don't have to construct the keyring state.
vi.mock("@/components/common/KeyringStatusBadge", () => ({
	KeyringStatusBadge: () => <span data-testid="keyring-badge" />,
}));

// Stub Input + Switch to keep the markup lean.
vi.mock("@/components/ui/input", () => ({
	Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => (
		<input data-testid="api-key-input" {...props} />
	),
}));

vi.mock("@/components/ui/switch", () => ({
	Switch: (props: {
		checked: boolean;
		onCheckedChange: (granted: boolean) => void;
		"aria-label"?: string;
	}) => (
		<button
			type="button"
			data-testid="consent-switch"
			role="switch"
			aria-checked={props.checked}
			aria-label={props["aria-label"]}
			onClick={() => props.onCheckedChange(!props.checked)}
		/>
	),
}));

/** Wrap in the shared TooltipProvider so the icon-only metadata chips
 *  (cloud / language) mount their Radix tooltip. */
function renderPanel(ui: React.ReactElement) {
	return render(<TooltipProvider delayDuration={200}>{ui}</TooltipProvider>);
}

const noop = vi.fn();

/** Look the real provider up instead of hand-building a fixture: the
 *  panel renders `wer` / `speed_rating` straight off the entry, so a
 *  fixture copy would let the shipped figures drift out from under the
 *  assertions. */
function provider(key: CloudProvider["key"]): CloudProvider {
	const found = CLOUD_PROVIDERS.find((p) => p.key === key);
	if (!found) throw new Error(`no CLOUD_PROVIDERS entry for ${key}`);
	return found;
}

const openaiProvider = provider("openai");

const baseConfig = {
	cloud_openai_consent: false,
	cloud_groq_consent: false,
	cloud_deepgram_consent: false,
	cloud_gemini_consent: false,
	keyring_status: undefined,
} as unknown as LausuConfig;

const baseProps = {
	config: baseConfig,
	cloudProviders: [openaiProvider],
	apiKeys: {},
	testResults: {},
	onApiKeyChange: noop,
	onSaveApiKey: noop,
	onTestConnection: noop,
	onConsentChange: noop,
};

// ── Helpers ───────────────────────────────────────────────────────────
// The API-key form lives behind the provider group (accordion trigger)
// + the "Configure" action (overhaul point 11). These helpers expand
// the group and reveal the form before the test interacts with it.

function expandProviderGroup(providerLabel: string) {
	fireEvent.click(screen.getByRole("button", { name: providerLabel }));
}

function openApiKeyForm(providerLabel = "OpenAI Whisper API") {
	expandProviderGroup(providerLabel);
	fireEvent.click(
		screen.getByRole("button", {
			name: new RegExp(`Configure ${providerLabel}`, "i"),
		}),
	);
}

describe("CloudProvidersPanel, provider brand logos + collapsible groups", () => {
	afterEach(() => cleanup());

	it("renders the brand logo for openai and deepgram; groq keeps the shield fallback", () => {
		const { container } = renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				cloudProviders={[
					openaiProvider,
					provider("groq"),
					provider("deepgram"),
					provider("gemini"),
				]}
			/>,
		);

		// openai + deepgram + gemini render an <img> brand logo in their
		// group headers; groq has none.
		const imgs = container.querySelectorAll("img");
		expect(imgs).toHaveLength(3);
		const srcs = Array.from(imgs).map((i) => i.getAttribute("src") ?? "");
		expect(srcs.some((s) => s.includes("OpenAI%20icon"))).toBe(true);
		expect(srcs.some((s) => s.includes("Deepgram%20icon"))).toBe(true);
		expect(srcs.some((s) => s.includes("/plugin-icons/google.svg"))).toBe(true);

		// groq keeps the generic shield glyph in its group header.
		const shields = screen
			.getAllByTestId("hugeicon")
			.filter((el) => el.getAttribute("data-name") === "Shield01Icon");
		expect(shields).toHaveLength(1);
	});

	it("renders each provider as a collapsible group whose Configure action opens a setup dialog", () => {
		renderPanel(<CloudProvidersPanel {...baseProps} />);

		// Group header exists for the provider.
		expect(
			screen.getByRole("button", { name: "OpenAI Whisper API" }),
		).toBeInTheDocument();

		// The API-key form is NOT visible until Configure is clicked
		// (point 11, no permanently-visible API-key card), and there is
		// no dialog in the tree yet either.
		expect(screen.queryByTestId("api-key-input")).toBeNull();
		expect(screen.queryByRole("dialog")).toBeNull();
		expect(
			screen.queryByRole("button", {
				name: /Save OpenAI Whisper API API key/i,
			}),
		).toBeNull();

		// Expanding the group reveals the model row + Configure action.
		expandProviderGroup("OpenAI Whisper API");
		const configure = screen.getByRole("button", {
			name: /Configure OpenAI Whisper API/i,
		});
		// A MODAL trigger, not a disclosure: `aria-haspopup="dialog"` and
		// no `aria-expanded` (nothing expands in place) and no label flip.
		expect(configure).toHaveAttribute("aria-haspopup", "dialog");
		expect(configure).not.toHaveAttribute("aria-expanded");
		// The API model name renders as a display-formatted heading.
		expect(
			screen.getByRole("heading", { name: "Whisper 1" }),
		).toBeInTheDocument();

		// Configure opens the setup dialog, titled with the provider.
		fireEvent.click(configure);
		const dialog = screen.getByRole("dialog");
		expect(dialog).toHaveAccessibleName("OpenAI Whisper API");
		expect(screen.getByTestId("api-key-input")).toBeInTheDocument();
		// The Configure button keeps its label — the dialog owns the
		// close affordances (X / Escape / overlay).
		expect(configure).toHaveTextContent("Configure");
	});

	it("closes the setup dialog on Escape and unmounts the form", async () => {
		renderPanel(<CloudProvidersPanel {...baseProps} />);
		openApiKeyForm();
		expect(screen.getByTestId("api-key-input")).toBeInTheDocument();

		fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
		await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
		expect(screen.queryByTestId("api-key-input")).toBeNull();
	});

	it("renders the model row metadata as a WER pair + icon-only chips (no text pills)", () => {
		renderPanel(<CloudProvidersPanel {...baseProps} />);
		expandProviderGroup("OpenAI Whisper API");
		// WER renders as a label+value pair, exactly like the Local rows,
		// so accuracy is comparable across both tabs.
		expect(screen.getByText("WER")).toBeInTheDocument();
		expect(
			screen.getByText(`: ${formatWer(openaiProvider.wer)}`),
		).toBeInTheDocument();
		// Speed + multilingual are icon-only buttons; their meaning
		// lives in the accessible name + tooltip, never as visible text.
		// The SPEED chip replaced the old cloud chip: on the Cloud tab
		// every row is a cloud model, so "Cloud" restated the tab.
		expect(
			screen.getByRole("button", {
				name: `${formatModelSpeed(openaiProvider.speed_rating)} Speed`,
			}),
		).toBeInTheDocument();
		expect(screen.queryByRole("button", { name: "Cloud" })).toBeNull();
		expect(
			screen.getByRole("button", { name: "Multilingual" }),
		).toBeInTheDocument();
		expect(screen.queryByText("Cloud")).toBeNull();
		expect(screen.queryByText("Multilingual")).toBeNull();
	});
});

describe("CloudProvidersPanel, test-result span is a live region", () => {
	afterEach(() => cleanup());

	it("test-result span exposes role=status + aria-live=polite (so SR users hear the outcome)", () => {
		const testResult: ApiTestResult = {
			message: "Connection successful: API key is valid.",
			status: "success",
		};
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				testResults={{ openai: testResult }}
			/>,
		);
		openApiKeyForm();
		const resultSpan = screen.getByText(
			"Connection successful: API key is valid.",
		);
		// The result renders as an <output> element, whose IMPLICIT ARIA
		// role is status (so SR users hear the outcome). Assert the
		// computed role via toHaveRole rather than the literal role
		// attribute, which <output> doesn't carry.
		expect(resultSpan).toHaveRole("status");
		expect(resultSpan).toHaveAttribute("aria-live", "polite");
	});

	it("test-result span is absent when there is no testResult for the provider", () => {
		renderPanel(<CloudProvidersPanel {...baseProps} testResults={{}} />);
		openApiKeyForm();
		expect(screen.queryByRole("status")).toBeNull();
	});
});

describe("CloudProvidersPanel, three test-result color branches", () => {
	afterEach(() => cleanup());

	it("success branch uses text-primary", () => {
		const testResult: ApiTestResult = {
			message: "ok",
			status: "success",
		};
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				testResults={{ openai: testResult }}
			/>,
		);
		openApiKeyForm();
		const span = screen.getByText("ok");
		expect(span.className).toContain("text-primary");
		expect(span.className).not.toContain("text-[(--muted-foreground)]");
	});

	it("failure branch uses text-destructive", () => {
		const testResult: ApiTestResult = {
			message: "bad key",
			status: "failure",
		};
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				testResults={{ openai: testResult }}
			/>,
		);
		openApiKeyForm();
		const span = screen.getByText("bad key");
		expect(span.className).toContain("text-destructive");
	});

	it("info branch uses the canonical text-muted-foreground class (NOT the invalid text-[(--muted-foreground)] form)", () => {
		const testResult: ApiTestResult = {
			message: "testing…",
			status: "info",
		};
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				testResults={{ openai: testResult }}
			/>,
		);
		openApiKeyForm();
		const span = screen.getByText("testing…");
		//`text-[(--muted-foreground)]` is invalid Tailwind v4 syntax.
		// The canonical form is `text-muted-foreground`, matches every other
		// call site in the codebase.
		expect(span.className).toContain("text-muted-foreground");
		expect(span.className).not.toContain("text-[(--muted-foreground)]");
	});
});

describe("CloudProvidersPanel, consent progressive disclosure", () => {
	afterEach(() => cleanup());

	it("hides the consent card when no API key is set AND consent is not granted", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{}}
				config={{ ...baseConfig, cloud_openai_consent: false } as LausuConfig}
			/>,
		);
		openApiKeyForm();
		expect(screen.queryByTestId("consent-switch")).toBeNull();
	});

	it("shows the consent card when an API key is present (even if consent not granted)", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "sk-test" }}
				config={{ ...baseConfig, cloud_openai_consent: false } as LausuConfig}
			/>,
		);
		openApiKeyForm();
		expect(screen.getByTestId("consent-switch")).toBeInTheDocument();
		expect(screen.getByText(/Consent not granted/i)).toBeInTheDocument();
	});

	it("shows the consent card when consent is already granted (even without an API key)", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{}}
				config={{ ...baseConfig, cloud_openai_consent: true } as LausuConfig}
			/>,
		);
		openApiKeyForm();
		expect(screen.getByTestId("consent-switch")).toBeInTheDocument();
		expect(screen.getByText(/Consent granted/i)).toBeInTheDocument();
	});

	it("toggling the consent switch invokes onConsentChange with the new value", () => {
		const onConsentChange = vi.fn();
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "sk-test" }}
				config={{ ...baseConfig, cloud_openai_consent: false } as LausuConfig}
				onConsentChange={onConsentChange}
			/>,
		);
		openApiKeyForm();
		screen.getByTestId("consent-switch").click();
		expect(onConsentChange).toHaveBeenCalledWith("openai", true);
	});
});

describe("CloudProvidersPanel, Save / Test buttons", () => {
	afterEach(() => cleanup());

	it("Save Key button invokes onSaveApiKey with the provider key", () => {
		// Provider label for "openai" is "OpenAI Whisper API", so the aria-label
		// resolves to "Save OpenAI Whisper API API key".
		//the Save Key button is disabled when the input is empty,
		// so the test must pass a non-empty key to click it.
		const onSaveApiKey = vi.fn();
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "sk-test" }}
				onSaveApiKey={onSaveApiKey}
			/>,
		);
		openApiKeyForm();
		screen
			.getByRole("button", { name: /Save OpenAI Whisper API API key/i })
			.click();
		expect(onSaveApiKey).toHaveBeenCalledWith("openai");
	});

	it("Test Connection button invokes onTestConnection with the provider key", () => {
		const onTestConnection = vi.fn();
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				onTestConnection={onTestConnection}
			/>,
		);
		openApiKeyForm();
		screen
			.getByRole("button", { name: /Test OpenAI Whisper API connection/i })
			.click();
		expect(onTestConnection).toHaveBeenCalledWith("openai");
	});
});

//the "Save Key" button is disabled when the input is empty
// (prevents silently clobbering a stored secret with the empty string
// that `safeApiKey` substitutes for the `<redacted>` sentinel on
// every config fetch).
describe("CloudProvidersPanel, Save Key button disabled guard", () => {
	afterEach(() => cleanup());

	it("disables the Save Key button when the API key input is empty", () => {
		renderPanel(
			<CloudProvidersPanel {...baseProps} apiKeys={{ openai: "" }} />,
		);
		openApiKeyForm();
		const saveBtn = screen.getByRole("button", {
			name: /Save OpenAI Whisper API API key/i,
		});
		expect(saveBtn).toBeDisabled();
	});

	it("enables the Save Key button when the API key input has a non-whitespace value", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "sk-test-key" }}
			/>,
		);
		openApiKeyForm();
		const saveBtn = screen.getByRole("button", {
			name: /Save OpenAI Whisper API API key/i,
		});
		expect(saveBtn).not.toBeDisabled();
	});

	it("disables the Save Key button when the input is only whitespace", () => {
		renderPanel(
			<CloudProvidersPanel {...baseProps} apiKeys={{ openai: "   " }} />,
		);
		openApiKeyForm();
		const saveBtn = screen.getByRole("button", {
			name: /Save OpenAI Whisper API API key/i,
		});
		expect(saveBtn).toBeDisabled();
	});
});

//the "Test Connection" button shows a spinner + is disabled
// while a test is in flight (`testResult?.status === "pending"`).
// Stale results are cleared via `onClearTestResult` whenever the
// API-key Input changes.
describe("CloudProvidersPanel, Test Connection pending state + clear-on-key-change", () => {
	afterEach(() => cleanup());

	it("disables the Test Connection button + sets aria-busy when testResult.status is 'pending'", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "sk-test" }}
				testResults={{
					openai: { message: "Testing…", status: "pending" },
				}}
			/>,
		);
		openApiKeyForm();
		const testBtn = screen.getByRole("button", {
			name: /Test OpenAI Whisper API connection/i,
		});
		expect(testBtn).toBeDisabled();
		expect(testBtn).toHaveAttribute("aria-busy", "true");
	});

	it("renders the spinning Loading03Icon (NOT SparklesIcon) when testResult.status is 'pending'", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "sk-test" }}
				testResults={{
					openai: { message: "Testing…", status: "pending" },
				}}
			/>,
		);
		openApiKeyForm();
		const icons = screen.getAllByTestId("hugeicon");
		const iconNames = icons.map((el) => el.getAttribute("data-name"));
		expect(iconNames).toContain("Loading03Icon");
		expect(iconNames).not.toContain("SparklesIcon");
	});

	it("enables the Test Connection button + uses SparklesIcon when no test is in flight", () => {
		renderPanel(
			<CloudProvidersPanel {...baseProps} apiKeys={{ openai: "sk-test" }} />,
		);
		openApiKeyForm();
		const testBtn = screen.getByRole("button", {
			name: /Test OpenAI Whisper API connection/i,
		});
		expect(testBtn).not.toBeDisabled();
		expect(testBtn).toHaveAttribute("aria-busy", "false");
		const icons = screen.getAllByTestId("hugeicon");
		const iconNames = icons.map((el) => el.getAttribute("data-name"));
		expect(iconNames).toContain("SparklesIcon");
	});

	it("clears the stale test result via onClearTestResult when the API key Input changes", () => {
		const onApiKeyChange = vi.fn();
		const onClearTestResult = vi.fn();
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "sk-test" }}
				testResults={{
					openai: {
						message: "Connection successful: API key is valid.",
						status: "success",
					},
				}}
				onApiKeyChange={onApiKeyChange}
				onClearTestResult={onClearTestResult}
			/>,
		);
		openApiKeyForm();
		const input = screen.getByTestId("api-key-input");
		fireEvent.change(input, { target: { value: "sk-new-key" } });
		expect(onApiKeyChange).toHaveBeenCalledWith("openai", "sk-new-key");
		expect(onClearTestResult).toHaveBeenCalledWith("openai");
	});
});
