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
	isRealtimeGuardOnly,
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
	// `<redacted>` is what `get_config` returns for a STORED key, and it
	// is the state that decides whether the model rows offer Select. It
	// is the realistic default here: a provider the user has configured.
	// The "no key configured" branch is asserted explicitly below.
	openai_api_key: "<redacted>",
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
	// The trigger button now wraps the whole row: provider brand on the
	// left plus the trailing Configure + chevron group on the right, so
	// its accessible name includes the Configure text.
	fireEvent.click(
		screen.getByRole("button", { name: `${providerLabel} Configure` }),
	);
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
			// The trigger wraps the whole row, so its name carries the
			// trailing Configure text; the brand is the leading half.
			expect(
				screen.getByRole("button", { name: `${label} Configure` }),
			).toBeInTheDocument();
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
		// irrelevant here: openai alone serves 4 models, so a per-model
		// button would already push this to 10.
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

	it("puts Configure on the provider's header row — provider name left, action right — INSIDE the trigger button", () => {
		// The row is one full-width trigger button: the left div holds
		// the brand, the trailing div holds Configure + the chevron.
		renderPanel(<CloudProvidersPanel {...baseProps} />);

		const trigger = screen.getByRole("button", {
			name: "OpenAI Configure",
		});
		const configure = screen.getByRole("button", {
			name: "Configure OpenAI",
		});

		// Descendant, not sibling: both groups live inside the button.
		expect(trigger.contains(configure)).toBe(true);
		expect(
			configure.closest('[data-slot="accordion-trigger-trailing"]'),
		).not.toBeNull();
		// …and the button spans the header row (Radix `Header`, an H3).
		const header = trigger.parentElement;
		expect(header?.tagName).toBe("H3");
		expect(trigger.className).toContain("w-full");
	});

	it("places Configure immediately LEFT of the disclosure glyph", () => {
		// Order inside the trailing div is [Configure … ▸]: the action
		// comes first, then the disclosure glyph.
		renderPanel(<CloudProvidersPanel {...baseProps} />);

		const trigger = screen.getByRole("button", {
			name: "OpenAI Configure",
		});
		const trailing = trigger.querySelector(
			'[data-slot="accordion-trigger-trailing"]',
		);
		const configure = screen.getByRole("button", {
			name: "Configure OpenAI",
		});
		// The mocked HugeiconsIcon keeps `data-name` but drops `data-slot`
		// (this suite stubs the icon wrapper), so the disclosure glyph is
		// found by its icon name here. `a11y-attrs.test.tsx` pins the real
		// `data-slot="accordion-trigger-icon"` against the unmocked icon.
		const chevron = trailing?.querySelector('[data-name="ArrowRight01Icon"]');

		expect(trailing).not.toBeNull();
		expect(chevron).not.toBeNull();
		// The glyph FOLLOWS the action in document order, i.e. renders to
		// its right in this LTR row.
		expect(configure.compareDocumentPosition(chevron as Node)).toBe(
			Node.DOCUMENT_POSITION_FOLLOWING,
		);
		// Both live in the trailing div, inside the trigger <button>.
		expect(trailing?.contains(configure)).toBe(true);
		expect(trigger.contains(chevron as Element)).toBe(true);
	});

	it("makes the trigger button the single hover surface, action included", () => {
		// jsdom cannot measure a :hover paint, so the CONTRACT is pinned
		// instead: the trigger alone owns `hover:bg-foreground/5` and the
		// trailing div paints no second tint. One button, one hover.
		renderPanel(<CloudProvidersPanel {...baseProps} />);

		const trigger = screen.getByRole("button", {
			name: "OpenAI Configure",
		});
		expect(trigger.className).toContain("hover:bg-foreground/5");
		const trailing = trigger.querySelector(
			'[data-slot="accordion-trigger-trailing"]',
		);
		expect(trailing?.className).not.toContain("group-hover");
	});

	it("renders the row as two div groups inside one full-width button (no seam)", () => {
		// One button, two divs: the left content group and the trailing
		// action+chevron group. No sibling half, so no height step where
		// two tints could meet. jsdom has no layout, so the DOM contract
		// is the guard.
		renderPanel(<CloudProvidersPanel {...baseProps} />);

		const trigger = screen.getByRole("button", {
			name: "OpenAI Configure",
		});
		expect(trigger.className).toContain("w-full");
		expect(trigger.className).toContain("items-center");

		// The trailing group is a DIV child of the trigger…
		const trailing = trigger.querySelector(
			'[data-slot="accordion-trigger-trailing"]',
		) as HTMLElement;
		expect(trailing).not.toBeNull();
		expect(trailing.tagName).toBe("DIV");
		// …and the Configure action lives inside it.
		expect(
			trailing.contains(
				screen.getByRole("button", { name: "Configure OpenAI" }),
			),
		).toBe(true);
	});

	it("packs the provider name against its logo in the left div, action far right", () => {
		// The trigger spreads its two groups with `justify-between`: the
		// left content div (logo + name, packed with a small gap) against
		// the trailing div. jsdom cannot measure the rendered gap, so the
		// CONTRACT that decides it is pinned instead. Both tabs go through
		// `ModelGroupTrigger`, so this covers Local too.
		renderPanel(<CloudProvidersPanel {...baseProps} />);

		const trigger = screen.getByRole("button", {
			name: "OpenAI Configure",
		});
		expect(trigger.className).toContain("justify-between");
		expect(trigger.className).toContain("items-center");

		// The left div packs the logo and the name, in that order —
		// nothing sits between them that could push them apart.
		const left = trigger.querySelector("div.flex.min-w-0") as HTMLElement;
		expect(left).not.toBeNull();
		expect(left.querySelector("img")).not.toBeNull();
		expect(left.textContent).toContain("OpenAI");
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
		// so accuracy is comparable across both tabs — and, also like the
		// Local rows, only on the models a pooled benchmark actually
		// covers (see the "no pooled WER" test below).
		const measured = openaiModels.filter((model) => model.wer !== null);
		expect(measured.length).toBeGreaterThan(0);
		expect(screen.getAllByText("WER")).toHaveLength(measured.length);
		expect(
			screen.getByText(`: ${formatCloudWer(modelAt(0).wer)}`),
		).toBeInTheDocument();

		// Speed + multilingual are icon-only buttons; their meaning
		// lives in the accessible name + tooltip, never as visible text.
		// The SPEED chip replaced the old cloud chip: on the Cloud tab
		// every row is a cloud model, so "Cloud" restated the tab.
		//
		// Count-based, NOT `getByRole`: several OpenAI rows now share one
		// speed tier (whisper-1 and gpt-transcribe are both "Medium"), so a
		// single-element query would throw on a legitimate catalogue.
		expect(screen.getAllByRole("button", { name: / Speed$/ })).toHaveLength(
			openaiModels.length,
		);
		for (const model of openaiModels) {
			expect(
				screen.getAllByRole("button", {
					name: `${formatModelSpeed(model.speed_rating)} Speed`,
				}).length,
			).toBeGreaterThan(0);
		}
		expect(screen.queryByRole("button", { name: "Cloud" })).toBeNull();
		expect(
			screen.getAllByRole("button", { name: "Multilingual" }),
		).toHaveLength(openaiModels.length);
		expect(screen.queryByText("Cloud")).toBeNull();
		expect(screen.queryByText("Multilingual")).toBeNull();
	});

	it("hides the WER pair entirely when no pooled benchmark covers the model", () => {
		// The bug report: a row read "WER : —" — a label spent on an
		// absence, which reads as a broken value. An unknown WER is not a
		// value at all, so the pair is not rendered. The measured rows
		// still show a real percentage, so this is a per-model decision,
		// not a whole-column fallback.
		renderPanel(<CloudProvidersPanel {...baseProps} />);
		expandProviderGroup("OpenAI");

		const unmeasured = openaiModels.filter((m) => m.wer === null);
		const measured = openaiModels.filter((m) => m.wer !== null);
		expect(unmeasured.length).toBeGreaterThan(0);
		expect(measured.length).toBeGreaterThan(0);

		// No em dash anywhere, and no "WER" label beyond the measured rows.
		expect(screen.queryByText(": —")).toBeNull();
		expect(screen.getAllByText("WER")).toHaveLength(measured.length);
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
		// Every OTHER *selectable* row is still selectable (guard-only
		// rows render a marker, never Select, so they are out of the count).
		const selectable = openaiModels.filter(
			(model) => !isRealtimeGuardOnly(openaiProvider.key, model.id),
		);
		expect(screen.getAllByRole("button", { name: /^Select / })).toHaveLength(
			selectable.length - 1,
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

// A Select button whose only possible answer is "Please enter the API key
// first" is a button that exists to refuse. The action is therefore gated
// on the provider having a STORED key — one fact per provider, because all
// of a provider's models share its single key.
describe("CloudProvidersPanel, Select is gated on a stored API key", () => {
	afterEach(() => cleanup());

	/** Every non-guard-only OpenAI model, i.e. the rows that can offer Select. */
	function selectableModels(): CloudModel[] {
		return openaiModels.filter(
			(model) => !isRealtimeGuardOnly(openaiProvider.key, model.id),
		);
	}

	it("offers Select on every selectable row when the provider IS configured", () => {
		renderPanel(<CloudProvidersPanel {...baseProps} />);
		expandProviderGroup("OpenAI");

		// `<redacted>` in `baseConfig` is the stored-key state.
		expect(screen.getAllByRole("button", { name: /^Select / })).toHaveLength(
			selectableModels().length,
		);
	});

	it("renders NO Select at all when the provider has no stored key", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				config={
					{
						...baseConfig,
						openai_api_key: "",
					} as LausuConfig
				}
			/>,
		);
		expandProviderGroup("OpenAI");

		// Every row is still listed — the catalogue is not hidden, only the
		// action that could not succeed is.
		for (const model of openaiModels) {
			expect(
				screen.getByRole("heading", {
					name: cloudModelLabel(openaiProvider.key, model.id),
				}),
			).toBeInTheDocument();
		}
		expect(screen.queryByRole("button", { name: /^Select / })).toBeNull();
		expect(screen.queryByRole("button", { name: "Selecting…" })).toBeNull();
	});

	it("renders no marker on OpenAI rows without a key (both realtime rows stream over WS)", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				config={
					{
						...baseConfig,
						openai_api_key: "",
					} as LausuConfig
				}
			/>,
		);
		expandProviderGroup("OpenAI");

		expect(screen.queryByTestId(/^realtime-only-/)).toBeNull();
	});

	it("keeps the Active marker without a key (config state, not an action)", () => {
		const activeModel = modelAt(0);
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				config={
					{
						...baseConfig,
						openai_api_key: "",
						asr_backend: "cloud",
						cloud_provider: "openai",
						cloud_model: activeModel.id,
					} as LausuConfig
				}
			/>,
		);
		expandProviderGroup("OpenAI");

		const label = cloudModelLabel(openaiProvider.key, activeModel.id);
		expect(
			screen.getByRole("button", { name: `Active: ${label}` }),
		).toBeDisabled();
	});

	it("gates each provider on ITS OWN key, not on any configured provider", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				cloudProviders={[openaiProvider, provider("groq")]}
				config={
					{
						...baseConfig,
						// openai is configured, groq is not.
						groq_api_key: "",
					} as LausuConfig
				}
			/>,
		);
		// `type="multiple"`, so both groups are open at once.
		expandProviderGroup("OpenAI");
		expandProviderGroup("Groq");

		// Groq's rows ARE rendered (the catalogue is never hidden)…
		expect(
			screen.getByRole("heading", { name: "Whisper Large V3" }),
		).toBeInTheDocument();
		// …but they add no Select: the only Selects in the tree are
		// OpenAI's, whose key is stored.
		expect(screen.getAllByRole("button", { name: /^Select / })).toHaveLength(
			selectableModels().length,
		);
	});
});

describe("CloudProvidersPanel, realtime-only rows", () => {
	afterEach(() => cleanup());

	it("offers Select — never a marker — on the WS-supported OpenAI realtime rows", () => {
		renderPanel(<CloudProvidersPanel {...baseProps} />);
		expandProviderGroup("OpenAI");

		// Both streaming ids render the normal Select action: the app
		// streams OpenAI sessions over its own WS transport.
		expect(screen.queryByTestId(/^realtime-only-/)).toBeNull();
		expect(
			screen.getByRole("button", { name: /Select GPT-Live-Transcribe/ }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("button", { name: /Select GPT-Realtime-Whisper/ }),
		).toBeInTheDocument();
	});

	it("renders the gemini realtime marker beside its batch row", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				cloudProviders={[provider("gemini")]}
				// The batch row offers Select only once Google's key is
				// stored (`baseConfig` stores OpenAI's, not Google's).
				config={
					{
						...baseConfig,
						gemini_api_key: "<redacted>",
					} as LausuConfig
				}
			/>,
		);
		expandProviderGroup("Google");

		expect(screen.getAllByTestId(/^realtime-only-/)).toHaveLength(1);
		expect(
			screen.getByRole("button", { name: /Select Gemini 3\.5 Transcribe/ }),
		).toBeInTheDocument();
	});

	it("never shows Active on a guard-only row, even when the config names it", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				cloudProviders={[provider("gemini")]}
				config={
					{
						...baseConfig,
						gemini_api_key: "<redacted>",
						asr_backend: "cloud",
						cloud_provider: "gemini",
						cloud_model: "gemini-3.5-transcribe-live",
					} as LausuConfig
				}
			/>,
		);
		expandProviderGroup("Google");

		expect(screen.queryByRole("button", { name: /^Active/ })).toBeNull();
		expect(screen.getAllByTestId(/^realtime-only-/)).toHaveLength(1);
	});

	it("shows Active on a WS-supported realtime row when the config names it", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				config={
					{
						...baseConfig,
						asr_backend: "cloud",
						cloud_provider: "openai",
						cloud_model: "gpt-realtime-whisper",
					} as LausuConfig
				}
			/>,
		);
		expandProviderGroup("OpenAI");

		const label = cloudModelLabel("openai", "gpt-realtime-whisper");
		expect(
			screen.getByRole("button", { name: `Active: ${label}` }),
		).toBeDisabled();
	});

	it("never shows Selecting… on a guard-only row, even if marked in flight", () => {
		renderPanel(
			<CloudProvidersPanel
				{...baseProps}
				cloudProviders={[provider("gemini")]}
				config={
					{
						...baseConfig,
						gemini_api_key: "<redacted>",
					} as LausuConfig
				}
				selectingCloudModel={{
					provider: "gemini",
					model: "gemini-3.5-transcribe-live",
				}}
			/>,
		);
		expandProviderGroup("Google");

		expect(screen.queryByRole("button", { name: "Selecting…" })).toBeNull();
		expect(screen.getAllByTestId(/^realtime-only-/)).toHaveLength(1);
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
