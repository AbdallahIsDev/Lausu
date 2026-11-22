// Plugins page behaviour: one card per installed plugin with the activation
// switch ON the card, and ONE shared settings block below for the active
// plugin. All three controls are canonical app config fields, so every write
// goes through `set_config` and every refresh through `config_changed`.
//
// Strings are asserted against the real English catalogue (no `t()` mock),
// read from en.json so the assertions also prove the keys resolve.

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getLiveByTestId } from "@/__tests__/helpers/liveDom";
import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
	pythonMock,
	resetStableMocks,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";
import { TooltipProvider } from "@/components/ui/tooltip";
import en from "@/i18n/translations/en.json";

vi.mock("@/hooks/usePython", () =>
	pythonMock({ captureEvents: stableMocks.pythonEventHandlers }),
);
vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());

const COPY = en.plugins;

function renderPage(Page: React.ComponentType) {
	return render(
		<TooltipProvider delayDuration={200} skipDelayDuration={500}>
			<Page />
		</TooltipProvider>,
	);
}

type WirePlugin = Record<string, unknown>;

const GEMINI: WirePlugin = {
	id: "gemini",
	name: "Gemini",
	description: "Cloud speech plugin",
	vendor: "Example",
	icon: "",
	active: false,
};
const CLAUDE: WirePlugin = {
	id: "claude",
	name: "Claude",
	description: "Browser speech plugin",
	vendor: "Example",
	icon: "",
	active: false,
};

function stubCalls(
	plugins: WirePlugin[] = [],
	config: Record<string, unknown> = {},
): void {
	stableMocks.mockCall.mockImplementation((type: string) => {
		if (type === "get_plugins")
			return Promise.resolve({ available: true, plugins });
		if (type === "get_config")
			return Promise.resolve({
				active_plugin: "",
				plugin_visible: true,
				plugin_notify: true,
				...config,
			});
		return Promise.resolve(undefined);
	});
}

beforeEach(() => {
	resetStableMocks();
	vi.resetModules();
});

afterEach(() => {
	cleanup();
});

async function mountPage() {
	const page = await import("@/pages/plugins/Plugins");
	return page.default;
}

describe("Plugins page", () => {
	it("shows the empty state naming the real state when nothing is installed", async () => {
		stubCalls([]);
		const Page = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getAllByText(COPY.emptyTitle).length).toBeGreaterThan(0);
		});
		expect(screen.queryByTestId("plugin-card-gemini")).toBeNull();
	});

	it("renders one card per plugin with name, status and an activation switch", async () => {
		stubCalls([GEMINI, CLAUDE]);
		const Page = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(getLiveByTestId("plugin-card-gemini")).toBeTruthy();
			expect(getLiveByTestId("plugin-card-claude")).toBeTruthy();
		});
		expect(screen.getByText("Gemini")).toBeTruthy();
		expect(screen.getAllByText(COPY.statusInactive).length).toBeGreaterThan(0);
		expect(getLiveByTestId("plugin-activate-switch-gemini")).toBeTruthy();
		expect(getLiveByTestId("plugin-activate-switch-claude")).toBeTruthy();
	});

	it("marks the active plugin with the success dot", async () => {
		stubCalls([{ ...GEMINI, active: true }], { active_plugin: "gemini" });
		const Page = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(getLiveByTestId("plugin-card-gemini")).toBeTruthy();
		});
		expect(
			getLiveByTestId("plugin-card-gemini").querySelector(
				'[data-slot="plugin-status-dot"]',
			)?.className,
		).toContain("bg-success");
	});

	it("writes active_plugin via set_config when a card switch is turned on", async () => {
		stubCalls([GEMINI, CLAUDE]);
		const Page = await mountPage();
		renderPage(Page);

		const toggle = await waitFor(() =>
			getLiveByTestId("plugin-activate-switch-gemini"),
		);
		await userEvent.click(toggle);
		expect(stableMocks.mockCall).toHaveBeenCalledWith("set_config", {
			active_plugin: "gemini",
		});
	});

	it("writes an empty active_plugin when the active card switch is turned off", async () => {
		stubCalls([{ ...GEMINI, active: true }], { active_plugin: "gemini" });
		const Page = await mountPage();
		renderPage(Page);

		const toggle = await waitFor(() =>
			getLiveByTestId("plugin-activate-switch-gemini"),
		);
		await userEvent.click(toggle);
		expect(stableMocks.mockCall).toHaveBeenCalledWith("set_config", {
			active_plugin: "",
		});
	});

	it("shows the two shared settings for the active plugin", async () => {
		stubCalls([{ ...GEMINI, active: true }], { active_plugin: "gemini" });
		const Page = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByText(COPY.visibleLabel)).toBeTruthy();
		});
		expect(screen.getByText(COPY.notifyLabel)).toBeTruthy();
		expect(getLiveByTestId("plugin-setting-visible")).toBeTruthy();
		expect(getLiveByTestId("plugin-setting-notify")).toBeTruthy();
	});

	it("shows the section subtitle in a ? tooltip, never as plugin-specific body copy", async () => {
		stubCalls([{ ...GEMINI, active: true }], { active_plugin: "gemini" });
		const Page = await mountPage();
		renderPage(Page);

		const heading = await waitFor(() =>
			screen.getByRole("heading", { name: COPY.settingsSection }),
		);
		expect(heading.className).toContain("font-sans");
		expect(heading.className).toContain("text-lg");
		expect(heading.className).toContain("font-medium");
		expect(heading.className).toContain("text-foreground");
		expect(
			heading.parentElement?.parentElement?.parentElement?.parentElement
				?.className,
		).toContain("gap-2");

		// No plugin name in the copy: the settings are shared by plugins.
		expect(COPY.sharedSettingsDescription).not.toMatch(/Gemini|Claude/);
		expect(screen.queryByText(COPY.sharedSettingsDescription)).toBeNull();

		// The ? trigger carries the shared subtitle as its tooltip payload
		// (InfoTooltip's own tests pin hover/focus rendering).
		const help = screen.getByRole("button", {
			name: `More info about ${COPY.settingsSection}`,
		});
		expect(help).toBeTruthy();
	});

	it("persists shared setting changes as main config fields", async () => {
		stubCalls([{ ...GEMINI, active: true }], {
			active_plugin: "gemini",
			plugin_visible: true,
			plugin_notify: true,
		});
		const Page = await mountPage();
		renderPage(Page);

		const visible = await waitFor(() =>
			getLiveByTestId("plugin-setting-visible"),
		);
		await userEvent.click(visible);
		expect(stableMocks.mockCall).toHaveBeenCalledWith("set_config", {
			plugin_visible: false,
		});

		const notify = getLiveByTestId("plugin-setting-notify");
		await userEvent.click(notify);
		expect(stableMocks.mockCall).toHaveBeenCalledWith("set_config", {
			plugin_notify: false,
		});
	});

	it("says plainly when no plugin is active instead of showing orphan settings", async () => {
		stubCalls([GEMINI, CLAUDE]);
		const Page = await mountPage();
		renderPage(Page);

		await waitFor(() => {
			expect(screen.getByText(COPY.noActivePlugin)).toBeTruthy();
		});
		expect(screen.queryByTestId("plugin-setting-visible")).toBeNull();
	});

	it("seeds activation from the shared store on remount, not the stale list cache", async () => {
		stubCalls(
			[
				{ ...GEMINI, active: true },
				{ ...CLAUDE, active: false },
			],
			{ active_plugin: "gemini" },
		);
		const Page = await mountPage();
		const first = renderPage(Page);
		await waitFor(() => getLiveByTestId("plugin-card-gemini"));
		first.unmount();

		// A switch happened while the page was away: the shared store (fed
		// by config_changed) is fresh, the module list cache is not.
		// Dynamic import: `vi.resetModules()` gave the page a fresh store
		// instance, so the test must mutate THAT one, not a static import.
		const { useAppStore: freshStore } = await import("@/stores/appStore");
		freshStore.getState().setConfig({ active_plugin: "claude" });
		renderPage(Page);

		await waitFor(() => {
			expect(
				getLiveByTestId("plugin-card-claude").querySelector(
					'[data-slot="plugin-status-dot"]',
				)?.className,
			).toContain("bg-success");
		});
		expect(
			getLiveByTestId("plugin-card-gemini").querySelector(
				'[data-slot="plugin-status-dot"]',
			)?.className,
		).toContain("bg-muted-foreground/40");
	});

	it("keeps activation and shared values in sync on config_changed", async () => {
		stubCalls([GEMINI, CLAUDE]);
		const Page = await mountPage();
		renderPage(Page);

		await waitFor(() => getLiveByTestId("plugin-card-gemini"));

		stableMocks.mockCall.mockImplementation((type: string) => {
			if (type === "get_config")
				return Promise.resolve({
					active_plugin: "claude",
					plugin_visible: false,
					plugin_notify: false,
				});
			return Promise.resolve(undefined);
		});
		const handler = stableMocks.pythonEventHandlers.config_changed;
		if (!handler) throw new Error("config_changed handler was not registered");
		await act(async () => {
			handler(undefined);
			await Promise.resolve();
		});

		await waitFor(() => {
			expect(
				getLiveByTestId("plugin-card-claude").querySelector(
					'[data-slot="plugin-status-dot"]',
				)?.className,
			).toContain("bg-success");
		});
		const visible = await waitFor(() =>
			getLiveByTestId("plugin-setting-visible"),
		);
		expect(visible.getAttribute("data-state")).toBe("unchecked");
	});
});
