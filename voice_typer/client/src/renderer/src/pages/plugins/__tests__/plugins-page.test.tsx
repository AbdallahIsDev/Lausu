// Plugins page + detail behaviour.
//
// Covers the user-visible contract only: the empty state names the actual
// state (no plugins installed), cards open the detail view, the detail
// page shows the activation toggle FIRST and writes `active_plugin`
// (plugin id on, "" off), and the generic settings controls render per
// declared type. Persistence of individual settings is deliberately not
// asserted: no `set_plugin_setting` command exists yet.
//
// Strings are asserted against the real English catalogue (no `t()` mock,
// so the assertions also prove the keys resolve), read from en.json so a
// copy edit does not silently break the suite.

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
	pythonMock,
	resetStableMocks,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";
import { TooltipProvider } from "@/components/ui/tooltip";
import en from "@/i18n/translations/en.json";

vi.mock("@/hooks/usePython", () => pythonMock({ noopEvent: true }));
vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());

const COPY = en.plugins;

/**
 * SettingRow renders an InfoTooltip, so the page needs the same
 * TooltipProvider ancestor App.tsx supplies (same props as App.tsx, so
 * tooltip timing in tests mirrors production).
 */
function renderPage(Page: React.ComponentType) {
	return render(
		<TooltipProvider delayDuration={200} skipDelayDuration={500}>
			<Page />
		</TooltipProvider>,
	);
}

type WirePlugin = Record<string, unknown>;

const SAMPLE: WirePlugin = {
	id: "gemini",
	name: "Gemini",
	description: "Cloud speech plugin",
	vendor: "Example",
	icon: "",
	active: false,
	settings: [
		{
			key: "verbose",
			type: "bool",
			label: "Verbose",
			description: "",
			default: false,
		},
	],
	values: {},
};

/** Route the shared `call` mock by command name. */
function stubCalls(plugins: WirePlugin[] = [], activePlugin = ""): void {
	stableMocks.mockCall.mockImplementation((type: string) => {
		if (type === "get_plugins")
			return Promise.resolve({ available: true, plugins });
		if (type === "get_config") {
			return Promise.resolve({ active_plugin: activePlugin });
		}
		return Promise.resolve(undefined);
	});
}

beforeEach(() => {
	resetStableMocks();
	// The page's data hook keeps a MODULE-level plugin cache so returning
	// from the detail view does not refetch. Each test needs a cold cache,
	// so the module registry is reset and the page is re-imported per test.
	vi.resetModules();
});

afterEach(() => {
	cleanup();
});

/** Fresh page + selection store for one test (cold module cache). */
async function mountPage() {
	const page = await import("@/pages/plugins/Plugins");
	const selection = await import("@/pages/plugins/lib/usePluginSelection");
	return { Page: page.default, selection };
}

describe("Plugins page", () => {
	it("shows the empty state naming the real state when nothing is installed", async () => {
		stubCalls([]);
		const { Page } = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByText(COPY.emptyTitle)).toBeTruthy();
		});
		// C-UI-2: the copy states that no plugins are installed, it does
		// not say "no data available". Matched on the fragment because the
		// `{appName}` placeholder is substituted at i18n load time, so the
		// rendered text differs from the raw catalogue value.
		expect(screen.getByText(/ships with no plugins installed/)).toBeTruthy();
		expect(screen.queryByTestId("plugin-card-gemini")).toBeNull();
	});

	it("renders a card per plugin with its active/inactive status", async () => {
		stubCalls([SAMPLE]);
		const { Page } = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByTestId("plugin-card-gemini")).toBeTruthy();
		});
		expect(screen.getByText("Gemini")).toBeTruthy();
		expect(screen.getByText(COPY.statusInactive)).toBeTruthy();
	});

	it("keeps the card to name + status only (the description lives on the detail view)", async () => {
		stubCalls([SAMPLE]);
		const { Page } = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByTestId("plugin-card-gemini")).toBeTruthy();
		});
		expect(screen.getByText("Gemini")).toBeTruthy();
		// The card is a compact two-line row; the description is owned by
		// PluginDetail's PageHeading and must not be repeated on the card.
		expect(screen.queryByText("Cloud speech plugin")).toBeNull();
	});

	it("tints the status dot with the success token when the plugin is active", async () => {
		// Owner decision 2026-10-05: the dot reads green (the app's
		// semantic --success token) exactly when this plugin owns dictation.
		// `plugin.active` is the catalog's own flag, not config.active_plugin.
		stubCalls([{ ...SAMPLE, active: true }]);
		const { Page } = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByTestId("plugin-card-gemini")).toBeTruthy();
		});
		expect(
			screen
				.getByTestId("plugin-card-gemini")
				.querySelector('[data-slot="plugin-status-dot"]')?.className,
		).toContain("bg-success");
	});

	it("leaves the status dot muted grey when the plugin is not active", async () => {
		stubCalls([SAMPLE]);
		const { Page } = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByTestId("plugin-card-gemini")).toBeTruthy();
		});
		// The app's neutral status-dot tone (PrewarmAndUpdates' "off" dot),
		// never a bare --border dot which reads as plain white in dark.
		expect(
			screen
				.getByTestId("plugin-card-gemini")
				.querySelector('[data-slot="plugin-status-dot"]')?.className,
		).toContain("bg-muted-foreground/40");
	});

	it("renders the bundled asset for a plugin whose icon id has one", async () => {
		stubCalls([{ ...SAMPLE, icon: "google" }]);
		const { Page } = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByTestId("plugin-card-gemini")).toBeTruthy();
		});
		const img = screen.getByTestId("plugin-card-gemini").querySelector("img");
		expect(img?.getAttribute("src")).toBe("/plugin-icons/google.svg");
		// Decorative: the tile is aria-hidden and the name sits beside it.
		expect(img?.getAttribute("alt")).toBe("");
		// A real logo sits bare — no chip fill or border behind it.
		const tile = screen.getByTestId("plugin-card-gemini").querySelector("span");
		expect(tile?.className).not.toContain("bg-surface");
		expect(tile?.className).not.toContain("border");
	});

	it("falls back to the initial tile when no asset ships for the icon id", async () => {
		// SAMPLE declares `icon: ""`. An id with no bundled asset must never
		// resolve to a path — a plugin cannot point the renderer at a file.
		stubCalls([{ ...SAMPLE, icon: "some-other-provider" }]);
		const { Page } = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByTestId("plugin-card-gemini")).toBeTruthy();
		});
		const card = screen.getByTestId("plugin-card-gemini");
		expect(card.querySelector("img")).toBeNull();
		// The icon tile (the card's first span) holds the initial instead,
		// framed by the chip fill + border.
		const tile = card.querySelector("span");
		expect(tile?.textContent).toBe("G");
		expect(tile?.className).toContain("bg-surface");
		expect(tile?.className).toContain("border-border/8");
	});

	it("opens the detail view when a card is activated", async () => {
		const user = userEvent.setup();
		stubCalls([SAMPLE]);
		const { Page } = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByTestId("plugin-card-gemini")).toBeTruthy();
		});
		await user.click(screen.getByTestId("plugin-card-gemini"));

		await waitFor(() => {
			expect(screen.getByTestId("plugin-activate-switch")).toBeTruthy();
		});
	});

	it("shows the load-failure state when the backend call rejects", async () => {
		stableMocks.mockCall.mockImplementation(() =>
			Promise.reject(new Error("backend gone")),
		);
		const { Page } = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByText(COPY.loadFailedTitle)).toBeTruthy();
		});
	});
});

describe("Plugin detail activation", () => {
	async function openDetail(plugins: WirePlugin[], activePlugin = "") {
		stubCalls(plugins, activePlugin);
		const { Page, selection } = await mountPage();
		selection.usePluginSelection.setState({ selectedPluginId: "gemini" });
		renderPage(Page);
		await waitFor(() => {
			expect(screen.getByTestId("plugin-activate-switch")).toBeTruthy();
		});
	}

	it("writes the plugin id when switched on", async () => {
		const user = userEvent.setup();
		await openDetail([SAMPLE]);
		await user.click(screen.getByTestId("plugin-activate-switch"));

		await waitFor(() => {
			expect(stableMocks.mockCall).toHaveBeenCalledWith("set_config", {
				active_plugin: "gemini",
			});
		});
	});

	it("writes an empty id when switched off, restoring the built-in local model", async () => {
		const user = userEvent.setup();
		await openDetail([SAMPLE], "gemini");
		await user.click(screen.getByTestId("plugin-activate-switch"));

		await waitFor(() => {
			expect(stableMocks.mockCall).toHaveBeenCalledWith("set_config", {
				active_plugin: "",
			});
		});
	});

	it("offers a Back to plugins control that returns to the list", async () => {
		const user = userEvent.setup();
		await openDetail([SAMPLE]);
		await user.click(screen.getByText(COPY.back));

		await waitFor(() => {
			expect(screen.getByTestId("plugin-card-gemini")).toBeTruthy();
		});
	});

	it("renders a control per declared setting type", async () => {
		stubCalls([
			{
				...SAMPLE,
				settings: [
					{
						key: "flag",
						type: "bool",
						label: "Flag",
						description: "",
						default: false,
					},
					{
						key: "mode",
						type: "enum",
						label: "Mode",
						description: "",
						default: "a",
						choices: ["a", "b"],
					},
					{
						key: "count",
						type: "int",
						label: "Count",
						description: "",
						default: 1,
					},
					{
						key: "name",
						type: "string",
						label: "Name",
						description: "",
						default: "",
					},
				],
			},
		]);
		const { Page, selection } = await mountPage();
		selection.usePluginSelection.setState({ selectedPluginId: "gemini" });
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByTestId("plugin-setting-flag")).toBeTruthy();
		});
		// The DECLARED type picks the control and nothing else does: `bool`
		// is the app's toggle, `enum` is the dropdown. A two-choice enum is
		// therefore still a Select — a plugin that wants a toggle declares
		// `bool`, it does not get one by narrowing its choices to two.
		expect(screen.getByTestId("plugin-setting-flag").getAttribute("role")).toBe(
			"switch",
		);
		expect(screen.getByTestId("plugin-setting-mode").getAttribute("role")).toBe(
			"combobox",
		);
		expect(screen.getByTestId("plugin-setting-count")).toBeTruthy();
		expect(screen.getByTestId("plugin-setting-name")).toBeTruthy();
	});

	it("shows the not-found state with a Back control for an unknown id", async () => {
		stubCalls([]);
		const { Page, selection } = await mountPage();
		selection.usePluginSelection.setState({ selectedPluginId: "ghost" });
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByText(COPY.notFoundTitle)).toBeTruthy();
		});
		expect(screen.getByText(COPY.back)).toBeTruthy();
	});
});
