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
import {
	CLOUD_PROVIDERS,
	type CloudModel,
	type CloudProvider,
	cloudModelLabel,
	formatCloudWer,
	formatModelSpeed,
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

// Stub Input to keep the markup lean.
vi.mock("@/components/ui/input", () => ({
	Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => (
		<input data-testid="api-key-input" {...props} />
	),
}));

/** Wrap in the shared TooltipProvider so the icon-only metadata chips
 *  (language / speed) mount their Radix tooltip. */
function renderPanel(ui: React.ReactElement) {
	return render(<TooltipProvider delayDuration={200}>{ui}</TooltipProvider>);
}

const noop = vi.fn();

/** Look the real provider up instead of hand-building a fixture: the
 *  panel renders the model rows straight off the entry, so a fixture
 *  copy would let the shipped catalogue drift out from under the
 *  assertions. */
function provider(key: CloudProvider["key"]): CloudProvider {
	const found = CLOUD_PROVIDERS.find((p) => p.key === key);
	if (!found) throw new Error(`no CLOUD_PROVIDERS entry for ${key}`);
	return found;
}

const openaiProvider = provider("openai");
const openaiModels = openaiProvider.models;

/** The catalogue entry at `index`, with the undefined branch made
 *  explicit so `noUncheckedIndexedAccess` is satisfied without a
 *  non-null assertion. */
function modelAt(index: number): CloudModel {
	const model = openaiModels[index];
	if (!model) throw new Error(`openai serves no model at index ${index}`);
	return model;
}

const baseConfig = {
	asr_backend: "whisper",
	cloud_provider: "",
	cloud_model: "",
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
	testingProviders: {},
	selectingCloudModel: null,
	onApiKeyChange: noop,
	onSaveApiKey: noop,
	onTestConnection: noop,
	onActivateModel: noop,
};

// ── Helpers ───────────────────────────────────────────────────────────
// The API-key form lives behind the provider-level "Configure" action.
// Configure is on the group's HEADER row (always visible), so it does
// not need the group expanded; the model rows do.

function expandProviderGroup(providerLabel: string) {
	fireEvent.click(screen.getByRole("button", { name: providerLabel }));
}

function openApiKeyForm(providerLabel = "OpenAI") {
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

	it("labels each group with the provider BRAND only — no model name, no 'API' suffix", () => {
		// The bug report: the triggers read "OpenAI Whisper API",
		// "Groq Whisper API", … — provider + model + the word "API"
		// welded into one label. The group header is the provider's
		// identity; the model names belong to the rows inside it.
		renderPanel(
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

		for (const label of ["OpenAI", "Groq", "Deepgram", "Google"]) {
			expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
		}
		for (const stale of [
			"OpenAI Whisper API",
			"Groq Whisper API",
			"Deepgram Nova API",
			"Google Gemini API",
		]) {
			expect(screen.queryByRole("button", { name: stale })).toBeNull();
		}
		expect(screen.queryByText(/Whisper API/)).toBeNull();
	});
});

// The Configure action is a PROVIDER-level control, not a per-model one:
// every model a provider serves shares the provider's single API key, so
// a provider with ten models must not ask for the key ten times.
describe("CloudProvidersPanel, Configure is a provider-level action", () => {
	afterEach(() => cleanup());

	it("renders exactly ONE Configure button per provider, not one per model", () => {
		renderPanel(
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

		// 4 providers × 1 Configure. The model count is deliberately
		// irrelevant here: openai alone serves 3 models, so a per-model
		// button would already push this to 9.
		const configureButtons = screen.getAllByRole("button", {
			name: /^Configure /,
		});
		expect(configureButtons).toHaveLength(4);
		for (const label of ["OpenAI", "Groq", "Deepgram", "Google"]) {
			expect(
				screen.getByRole("button", { name: `Configure ${label}` }),
			).toBeInTheDocument();
		}
	});

	it("puts Configure on the provider's header row — provider name left, action right — OUTSIDE the trigger button", () => {
		// A Configure button nested inside the accordion trigger would be
		// a <button> inside a <button>: invalid HTML, flagged by axe as
		// `nested-interactive`, and its click would toggle the group.
		renderPanel(<CloudProvidersPanel {...baseProps} />);

		const trigger = screen.getByRole("button", { name: "OpenAI" });
		const configure = screen.getByRole("button", {
			name: "Configure OpenAI",
		});

		// Sibling, not descendant.
		expect(trigger.contains(configure)).toBe(false);
		expect(configure.closest('[data-slot="accordion-trigger"]')).toBeNull();
		// …but on the SAME row: both live inside the accordion header
		// (Radix's `Header`, an <h3> the ui wrapper does not tag).
		const header = trigger.parentElement;
		expect(header?.tagName).toBe("H3");
		expect(header?.contains(configure)).toBe(true);
	});

	it("keeps Configure visible while the group is COLLAPSED (it is not a row action)", () => {
		renderPanel(<CloudProvidersPanel {...baseProps} />);

		// The rows are hidden until the group expands…
		expect(screen.queryByRole("heading", { name: "Whisper 1" })).toBeNull();
		// …but the provider-level action is already there.
		expect(
			screen.getByRole("button", { name: "Configure OpenAI" }),
		).toBeInTheDocument();
	});

	it("renders one row per model the provider serves (the catalogue grows)", () => {
		renderPanel(<CloudProvidersPanel {...baseProps} />);
		expandProviderGroup("OpenAI");

		// Driven off the catalogue, not a hardcoded count: adding a model
		// to `CLOUD_PROVIDERS` must not require touching this test.
		for (const model of openaiModels) {
			expect(
				screen.getByRole("heading", {
					name: cloudModelLabel(openaiProvider.key, model.id),
				}),
			).toBeInTheDocument();
		}
	});

	it("opens the setup dialog from Configure, titled with the provider", () => {
		renderPanel(<CloudProvidersPanel {...baseProps} />);

		// No dialog in the tree before the click.
		expect(screen.queryByTestId("api-key-input")).toBeNull();
		expect(screen.queryByRole("dialog")).toBeNull();

		openApiKeyForm();
		const dialog = screen.getByRole("dialog");
		expect(dialog).toHaveAccessibleName("OpenAI");
		expect(screen.getByTestId("api-key-input")).toBeInTheDocument();
		// Exactly ONE key field for the whole provider — the point of
		// moving Configure up a level.
		expect(screen.getAllByTestId("api-key-input")).toHaveLength(1);
	});

	it("closes the setup dialog on Escape and unmounts the form", async () => {
		renderPanel(<CloudProvidersPanel {...baseProps} />);
		openApiKeyForm();
		expect(screen.getByTestId("api-key-input")).toBeInTheDocument();

		fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
		await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
		expect(screen.queryByTestId("api-key-input")).toBeNull();
	});
});

describe("CloudProvidersPanel, model rows + activation", () => {
	afterEach(() => cleanup());

	it("renders each model row's metadata as a WER pair + icon-only chips (no text pills)", () => {
		renderPanel(<CloudProvidersPanel {...baseProps} />);
		expandProviderGroup("OpenAI");

		// WER renders as a label+value pair, exactly like the Local rows,
		// so accuracy is comparable across both tabs.
		expect(screen.getAllByText("WER")).toHaveLength(openaiModels.length);
		expect(
			screen.getByText(`: ${formatCloudWer(modelAt(0).wer)}`),
		).toBeInTheDocument();

		// Speed + multilingual are icon-only buttons; their meaning
		// lives in the accessible name + tooltip, never as visible text.
		// The SPEED chip replaced the old cloud chip: on the Cloud tab
		// every row is a cloud model, so "Cloud" restated the tab.
		expect(
			screen.getByRole("button", {
				name: `${formatModelSpeed(modelAt(0).speed_rating)} Speed`,
			}),
		).toBeInTheDocument();
		expect(screen.queryByRole("button", { name: "Cloud" })).toBeNull();
		expect(
			screen.getAllByRole("button", { name: "Multilingual" }),
		).toHaveLength(openaiModels.length);
		expect(screen.queryByText("Cloud")).toBeNull();
		expect(screen.queryByText("Multilingual")).toBeNull();
	});

	it("renders an em dash — never a guessed number — for a model with no pooled WER", () => {
		renderPanel(<CloudProvidersPanel {...baseProps} />);
		expandProviderGroup("OpenAI");

		const unmeasured = openaiModels.filter((m) => m.wer === null);
		const measured = openaiModels.filter((m) => m.wer !== null);
		expect(unmeasured.length).toBeGreaterThan(0);
		expect(measured.length).toBeGreaterThan(0);
		expect(screen.getAllByText(": —")).toHaveLength(unmeasured.length);
		// The measured ones still render a real percentage, so the em
		// dash is a per-model decision, not a whole-column fallback.
		for (const model of measured) {
			expect(
				screen.getAllByText(`: ${formatCloudWer(model.wer)}`).length,
			).toBeGreaterThan(0);
		}
	});

	it("offers Select on a non-active row and calls onActivateModel with (provider, model id)", () => {
		const onActivateModel = vi.fn();
		renderPanel(
			<CloudProvidersPanel {...baseProps} onActivateModel={onActivateModel} />,
		);
		expandProviderGroup("OpenAI");

		const target = modelAt(1);
		const select = screen.getByRole("button", {
			name: `Select ${cloudModelLabel(openaiProvider.key, target.id)}`,
		});
		expect(select).not.toBeDisabled();
		fireEvent.click(select);
		expect(onActivateModel).toHaveBeenCalledWith("openai", target.id);
	});

	it("shows a disabled Active marker (no Select) on the model the config says is in use", () => {
		const activeModel = modelAt(0);
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				config={
					{
						...baseConfig,
						asr_backend: "cloud",
						cloud_provider: "openai",
						cloud_model: activeModel.id,
					} as LausuConfig
				}
			/>,
		);
		expandProviderGroup("OpenAI");

		const label = cloudModelLabel(openaiProvider.key, activeModel.id);
		const active = screen.getByRole("button", { name: `Active: ${label}` });
		expect(active).toBeDisabled();
		expect(active).toHaveTextContent("Active");
		// The same row offers no Select action.
		expect(
			screen.queryByRole("button", { name: `Select ${label}` }),
		).toBeNull();
	});

	it("treats an EMPTY cloud_model as the provider's default model being active", () => {
		// Onboarding selects a provider without choosing a model; the
		// backend then serves `_PROVIDER_DEFAULTS[provider]["model"]`, so
		// that is the row that must read as active.
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				config={
					{
						...baseConfig,
						asr_backend: "cloud",
						cloud_provider: "openai",
						cloud_model: "",
					} as LausuConfig
				}
			/>,
		);
		expandProviderGroup("OpenAI");

		const label = cloudModelLabel(
			openaiProvider.key,
			openaiProvider.defaultModel,
		);
		expect(
			screen.getByRole("button", { name: `Active: ${label}` }),
		).toBeDisabled();
	});

	it("marks only the in-flight model's row as Selecting…", () => {
		const target = modelAt(1);
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				selectingCloudModel={{ provider: "openai", model: target.id }}
			/>,
		);
		expandProviderGroup("OpenAI");

		const busy = screen.getByRole("button", { name: "Selecting…" });
		expect(busy).toBeDisabled();
		expect(busy).toHaveAttribute("aria-busy", "true");
		// Every OTHER row is still selectable.
		expect(screen.getAllByRole("button", { name: /^Select / })).toHaveLength(
			openaiModels.length - 1,
		);
	});

	it("does not mark a row in flight for a DIFFERENT provider", () => {
		const target = modelAt(1);
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				selectingCloudModel={{ provider: "groq", model: target.id }}
			/>,
		);
		expandProviderGroup("OpenAI");

		expect(screen.queryByRole("button", { name: "Selecting…" })).toBeNull();
	});
});

describe("CloudProvidersPanel, API-key form is only the key field + two buttons", () => {
	afterEach(() => cleanup());

	it("renders no format-hint copy under the input", () => {
		// The bug report: "…and it said typically 40 to 60 characters. So
		// all this information is not helpful at all, should be removed."
		// The actionable version of that message is the rejection toast
		// `useCloudProviders` raises when the shape is actually wrong.
		renderPanel(<CloudProvidersPanel {...baseProps} />);
		openApiKeyForm();

		const dialog = screen.getByRole("dialog");
		expect(dialog.textContent).not.toMatch(/typically/i);
		expect(dialog.textContent).not.toMatch(/\d+\s*-\s*\d+\s*characters/i);
		expect(dialog.textContent).not.toMatch(/no spaces or prefixes/i);
	});

	it("renders no consent control inside the form (the gate is a dialog raised after save)", () => {
		// The consent card used to appear the moment the user started
		// typing in the key field. It now lives in the shared
		// point-of-use consent dialog, opened by Save Key / Test
		// Connection / Select — see `useCloudProviders`.
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "sk-test" }}
				config={{ ...baseConfig, cloud_openai_consent: false } as LausuConfig}
			/>,
		);
		openApiKeyForm();

		const dialog = screen.getByRole("dialog");
		expect(dialog.textContent).not.toMatch(/consent/i);
		expect(screen.queryByRole("switch")).toBeNull();
		// The old consent copy must be gone entirely.
		expect(screen.queryByText(/Audio transmission consent/i)).toBeNull();
		expect(screen.queryByText(/audio recordings will be sent/i)).toBeNull();
	});

	it("gives the API-key input the dialog's full width (no max-w cap)", () => {
		// The wrapper was `w-full max-w-md`, which capped the field at
		// 28rem inside a 36rem dialog and left a strip of dead space to
		// its right that read as a layout bug.
		renderPanel(<CloudProvidersPanel {...baseProps} />);
		openApiKeyForm();

		const wrapper = screen.getByTestId("api-key-input").parentElement;
		expect(wrapper).not.toBeNull();
		expect(wrapper?.className).toContain("w-full");
		expect(wrapper?.className).not.toContain("max-w-md");
	});
});

describe("CloudProvidersPanel, Save / Test buttons", () => {
	afterEach(() => cleanup());

	it("Save Key button invokes onSaveApiKey with the provider key", () => {
		const onSaveApiKey = vi.fn();
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "sk-test" }}
				onSaveApiKey={onSaveApiKey}
			/>,
		);
		openApiKeyForm();
		screen.getByRole("button", { name: /Save OpenAI API key/i }).click();
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
		screen.getByRole("button", { name: /Test OpenAI connection/i }).click();
		expect(onTestConnection).toHaveBeenCalledWith("openai");
	});

	it("reports the typed value through onApiKeyChange", () => {
		const onApiKeyChange = vi.fn();
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "" }}
				onApiKeyChange={onApiKeyChange}
			/>,
		);
		openApiKeyForm();
		fireEvent.change(screen.getByTestId("api-key-input"), {
			target: { value: "sk-typed" },
		});
		expect(onApiKeyChange).toHaveBeenCalledWith("openai", "sk-typed");
	});
});

// The "Save Key" button is disabled when the input is empty
// (prevents silently clobbering a stored secret with the empty string
// that `safeApiKey` substitutes for the `<redacted>` sentinel on
// every config fetch). A key that is non-empty but malformed stays
// ENABLED on purpose: clicking it is what raises the explanatory toast.
describe("CloudProvidersPanel, Save Key button disabled guard", () => {
	afterEach(() => cleanup());

	it("disables the Save Key button when the API key input is empty", () => {
		renderPanel(
			<CloudProvidersPanel {...baseProps} apiKeys={{ openai: "" }} />,
		);
		openApiKeyForm();
		const saveBtn = screen.getByRole("button", {
			name: /Save OpenAI API key/i,
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
			name: /Save OpenAI API key/i,
		});
		expect(saveBtn).not.toBeDisabled();
	});

	it("keeps Save Key enabled for a non-empty value that is NOT a key shape (the toast explains why)", () => {
		renderPanel(
			<CloudProvidersPanel {...baseProps} apiKeys={{ openai: "GFHFGHHFGH" }} />,
		);
		openApiKeyForm();
		expect(
			screen.getByRole("button", { name: /Save OpenAI API key/i }),
		).not.toBeDisabled();
	});

	it("disables the Save Key button when the input is only whitespace", () => {
		renderPanel(
			<CloudProvidersPanel {...baseProps} apiKeys={{ openai: "   " }} />,
		);
		openApiKeyForm();
		const saveBtn = screen.getByRole("button", {
			name: /Save OpenAI API key/i,
		});
		expect(saveBtn).toBeDisabled();
	});
});

// The "Test Connection" button shows a spinner + is disabled while a
// probe is in flight (`testingProviders[provider] === true`). The
// outcome itself is a toast, never an inline region — that is why the
// panel takes no `testResults` prop any more.
describe("CloudProvidersPanel, Test Connection pending state", () => {
	afterEach(() => cleanup());

	it("disables the Test Connection button + sets aria-busy while the provider is in flight", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "sk-test" }}
				testingProviders={{ openai: true }}
			/>,
		);
		openApiKeyForm();
		const testBtn = screen.getByRole("button", {
			name: /Test OpenAI connection/i,
		});
		expect(testBtn).toBeDisabled();
		expect(testBtn).toHaveAttribute("aria-busy", "true");
	});

	it("renders the spinning Loading03Icon (NOT SparklesIcon) while in flight", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				apiKeys={{ openai: "sk-test" }}
				testingProviders={{ openai: true }}
			/>,
		);
		openApiKeyForm();
		const iconNames = screen
			.getAllByTestId("hugeicon")
			.map((el) => el.getAttribute("data-name"));
		expect(iconNames).toContain("Loading03Icon");
		expect(iconNames).not.toContain("SparklesIcon");
	});

	it("enables the Test Connection button + uses SparklesIcon when no test is in flight", () => {
		renderPanel(
			<CloudProvidersPanel {...baseProps} apiKeys={{ openai: "sk-test" }} />,
		);
		openApiKeyForm();
		const testBtn = screen.getByRole("button", {
			name: /Test OpenAI connection/i,
		});
		expect(testBtn).not.toBeDisabled();
		expect(testBtn).toHaveAttribute("aria-busy", "false");
		const iconNames = screen
			.getAllByTestId("hugeicon")
			.map((el) => el.getAttribute("data-name"));
		expect(iconNames).toContain("SparklesIcon");
	});

	it("keeps the in-flight state per provider (a busy groq row leaves openai idle)", async () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				cloudProviders={[openaiProvider, provider("groq")]}
				apiKeys={{ openai: "sk-test", groq: "gsk-test" }}
				testingProviders={{ groq: true }}
			/>,
		);

		// The setup form is a modal, so only one provider's dialog is in
		// the tree at a time: open, assert, close, open the next.
		openApiKeyForm("OpenAI");
		expect(
			screen.getByRole("button", { name: /Test OpenAI connection/i }),
		).not.toBeDisabled();
		fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
		await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

		openApiKeyForm("Groq");
		expect(
			screen.getByRole("button", { name: /Test Groq connection/i }),
		).toBeDisabled();
	});
});
