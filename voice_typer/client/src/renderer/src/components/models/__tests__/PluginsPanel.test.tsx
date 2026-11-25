import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PluginsPanel } from "@/components/models/PluginsPanel";
import { TooltipProvider } from "@/components/ui/tooltip";

const fake = vi.hoisted(() => ({
	activate: vi.fn(),
	sharedSetting: vi.fn(),
}));

vi.mock("@/pages/plugins/hooks/usePlugins", () => ({
	usePlugins: () => ({
		plugins: [
			{
				id: "anthropic-stt",
				name: "Anthropic STT",
				description: "Dictation in the browser",
				vendor: "Owner",
				icon: "",
				active: true,
			},
			{
				id: "google-stt",
				name: "Google STT",
				description: "Dictation in the browser",
				vendor: "Owner",
				icon: "google",
				active: false,
			},
			{
				id: "chatgpt-stt",
				name: "ChatGPT STT",
				description: "Dictation in the browser",
				vendor: "Owner",
				icon: "",
				active: false,
			},
		],
		activePluginId: "anthropic-stt",
		shared: { visible: true, notify: false },
		loadError: null,
		loadPlugins: vi.fn(),
		setActivePlugin: fake.activate,
		setSharedSetting: fake.sharedSetting,
	}),
}));

vi.mock("@/i18n/i18n", () => ({
	useT: () => (key: string) => key,
	t: (key: string) => key,
	getLocale: () => "en",
}));

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: () => <span data-testid="hugeicon" />,
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

afterEach(cleanup);

const renderPanel = () =>
	render(
		<TooltipProvider>
			<PluginsPanel />
		</TooltipProvider>,
	);

describe("PluginsPanel (Models developer tab content)", () => {
	it("shows every plugin card with Active/Inactive status", () => {
		renderPanel();

		expect(screen.getByText("Anthropic STT")).toBeTruthy();
		expect(screen.getByText("Google STT")).toBeTruthy();
		expect(screen.getByText("ChatGPT STT")).toBeTruthy();
		expect(screen.getAllByText("plugins.statusActive")).toHaveLength(1);
		expect(screen.getAllByText("plugins.statusInactive")).toHaveLength(2);
	});

	it("renders two plugins per row with no enclosing card", () => {
		renderPanel();

		const ids = ["anthropic-stt", "google-stt", "chatgpt-stt"];
		const cards = ids.map((id) => screen.getByTestId(`plugin-card-${id}`));
		const row = cards[0]!.parentElement;
		expect(row?.className).toContain("grid-cols-2");
		for (const card of cards) expect(card.parentElement).toBe(row);

		let ancestor: HTMLElement | null = row?.parentElement ?? null;
		while (ancestor) {
			expect(ancestor.className).not.toMatch(
				/bg-surface-subtle|border-border\/8/,
			);
			ancestor = ancestor.parentElement;
		}
	});

	it("activates a plugin and restores the local model on deactivate", async () => {
		renderPanel();

		await userEvent.click(
			screen.getByRole("switch", { name: "plugins.activateAria: Google STT" }),
		);
		// Single-owner model: ON writes this id, OFF writes "" (local model).
		expect(fake.activate).toHaveBeenCalledWith("google-stt");

		await userEvent.click(
			screen.getByRole("switch", {
				name: "plugins.activateAria: Anthropic STT",
			}),
		);
		expect(fake.activate).toHaveBeenCalledWith("");
	});

	it("writes the shared visibility/notification flags via set_config owner", async () => {
		renderPanel();

		await userEvent.click(
			screen.getByRole("switch", { name: "plugins.notifyLabel" }),
		);
		expect(fake.sharedSetting).toHaveBeenCalledWith("notify", true);

		await userEvent.click(
			screen.getByRole("switch", { name: "plugins.visibleLabel" }),
		);
		expect(fake.sharedSetting).toHaveBeenCalledWith("visible", false);
	});
});
