import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ModelsTabSwitcher } from "@/components/layout/ModelsTabSwitcher";
import { useModelsTab } from "@/stores/useModelsTab";

const gate = vi.hoisted(() => ({ unlocked: false }));

vi.mock("@/hooks/usePluginCatalog", () => ({
	usePluginsUnlocked: () => gate.unlocked,
}));

vi.mock("@/i18n/i18n", () => ({
	useT: () => (key: string) => key,
}));

beforeEach(() => {
	gate.unlocked = false;
	useModelsTab.setState({ activeTab: "local" });
});

afterEach(cleanup);

describe("ModelsTabSwitcher developer-only Plugins option", () => {
	it("never renders the option on a frozen/end-user build", () => {
		render(<ModelsTabSwitcher currentPage="models" />);

		expect(screen.getAllByRole("radio")).toHaveLength(3);
		expect(screen.queryByRole("radio", { name: "plugins.title" })).toBeNull();
	});

	it("renders and selects the option only when BOTH gates are on", async () => {
		gate.unlocked = true;
		render(<ModelsTabSwitcher currentPage="models" />);

		const option = screen.getByRole("radio", { name: "plugins.title" });
		expect(option).toBeTruthy();
		expect(screen.getAllByRole("radio")).toHaveLength(4);

		await userEvent.click(option);
		expect(useModelsTab.getState().activeTab).toBe("plugins");
	});

	it("unmounts outside the Models page", () => {
		const { container } = render(<ModelsTabSwitcher currentPage="home" />);
		expect(container.firstChild).toBeNull();
	});
});
