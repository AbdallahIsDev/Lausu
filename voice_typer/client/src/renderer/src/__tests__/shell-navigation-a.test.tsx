import {
	act,
	cleanup,
	render,
	renderHook,
	screen,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockCall, pythonEventHandlers } = vi.hoisted(() => ({
	mockCall: vi.fn(),
	pythonEventHandlers: {} as Record<string, (data?: unknown) => void>,
}));

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: mockCall }),
	usePythonEvent: (name: string, handler: (data?: unknown) => void) => {
		pythonEventHandlers[name] = handler;
	},
}));

vi.mock("@/hooks/useSnackbar", () => ({
	useSnackbar: () => ({ showSnack: vi.fn() }),
}));

vi.mock("@/pages/Vocabulary", async () => {
	const { useState } = await import("react");
	return {
		default: ({ active }: { active?: boolean }) => {
			const [count, setCount] = useState(0);
			return (
				<div data-testid="collection-dictionary" data-active={String(active)}>
					<button
						type="button"
						data-testid="dictionary-selection-state"
						onClick={() => setCount((n) => n + 1)}
					>
						{count}
					</button>
				</div>
			);
		},
	};
});

vi.mock("@/pages/Templates", async () => {
	const { useState } = await import("react");
	return {
		default: ({ active }: { active?: boolean }) => {
			const [count, setCount] = useState(0);
			return (
				<div data-testid="collection-snippets" data-active={String(active)}>
					<button
						type="button"
						data-testid="snippets-selection-state"
						onClick={() => setCount((n) => n + 1)}
					>
						{count}
					</button>
				</div>
			);
		},
	};
});

import { GlobalSearchBar } from "@/components/layout/GlobalSearchBar";
import { Sidebar } from "@/components/layout/Sidebar";
import { SettingsHub } from "@/components/settings/SettingsHub";
import { TooltipProvider } from "@/components/ui/tooltip";
import { _resetNavigationForTest, useNavigation } from "@/hooks/useNavigation";
import DictionarySnippetsPage from "@/pages/DictionarySnippets";
import { resolvePageAlias } from "@/router/routes";
import { useGlobalSearch } from "@/stores/useGlobalSearch";

function renderSidebar() {
	return render(
		<TooltipProvider>
			<Sidebar currentPage="home" onNavigate={() => {}} />
		</TooltipProvider>,
	);
}

function renderDictionaryPage() {
	return render(
		<TooltipProvider>
			<DictionarySnippetsPage />
		</TooltipProvider>,
	);
}

beforeEach(() => {
	mockCall.mockImplementation((command: string) => {
		if (command === "get_config") {
			return Promise.resolve({ model_size: "", device: "cpu" });
		}
		return Promise.resolve({ success: true });
	});
	useGlobalSearch.getState().clearQuery();
	_resetNavigationForTest();
});

afterEach(() => {
	cleanup();
	vi.clearAllMocks();
});

describe("A1 sidebar shape", () => {
	it("renders exactly the seven top leaves plus Settings in the bottom slot, in order", () => {
		renderSidebar();
		const labels = Array.from(
			document.querySelectorAll<HTMLButtonElement>(
				'aside button[data-nav-item="true"]',
			),
		).map((button) => button.textContent?.trim());
		expect(labels).toEqual([
			"Home",
			"History",
			"Analytics",
			"Models",
			"Dictionary & Snippets",
			"Media",
			"Microphone",
			"Settings",
		]);
		const sections = document.querySelectorAll("aside section");
		expect(sections).toHaveLength(2);
		// The bottom slot keeps only the model indicator, the switch and
		// the Settings leaf (no About & Privacy).
		expect(
			sections[1]?.querySelectorAll('button[data-nav-item="true"]'),
		).toHaveLength(1);
	});
});

describe("A2 hub rows and search keywords", () => {
	it("renders only icon, title and chevron, with Chat and Providers appended", () => {
		render(<SettingsHub onNavigateSection={() => {}} />);
		const rows = screen.getAllByRole("button");
		expect(rows).toHaveLength(9);
		expect(rows.map((row) => row.getAttribute("data-testid"))).toEqual([
			"settings-hub-row-settingsGeneral",
			"settings-hub-row-settingsHotkeys",
			"settings-hub-row-settingsTranscription",
			"settings-hub-row-settingsAudio",
			"settings-hub-row-settingsAppearance",
			"settings-hub-row-settingsPrivacy",
			"settings-hub-row-settingsAdvanced",
			"settings-hub-row-chat",
			"settings-hub-row-providers",
		]);
		for (const row of rows) {
			expect(row.children).toHaveLength(3);
			expect(row.children[1]?.textContent?.length).toBeGreaterThan(0);
		}
	});

	it("still finds rows by text removed from the visible row", () => {
		act(() => useGlobalSearch.getState().setQuery("hotkey"));
		render(<SettingsHub onNavigateSection={() => {}} />);
		expect(screen.getByTestId("settings-hub-row-settingsHotkeys")).toBeTruthy();
		act(() => useGlobalSearch.getState().setQuery("bubble position"));
		expect(screen.getByTestId("settings-hub-row-settingsGeneral")).toBeTruthy();
	});
});

describe("A5 Dictionary & Snippets", () => {
	it("toggles tabs while keeping both collections mounted and their state", async () => {
		const user = userEvent.setup();
		renderDictionaryPage();
		expect(screen.getByTestId("collection-dictionary")).toBeTruthy();
		expect(screen.getByTestId("collection-snippets")).toBeTruthy();
		expect(screen.getByRole("radio", { name: "Dictionary" })).toBeChecked();
		expect(
			screen.getByTestId("collection-dictionary").getAttribute("data-active"),
		).toBe("true");

		await user.click(screen.getByTestId("dictionary-selection-state"));
		expect(screen.getByTestId("dictionary-selection-state").textContent).toBe(
			"1",
		);
		await user.click(screen.getByRole("radio", { name: "Snippets" }));
		expect(screen.getByRole("radio", { name: "Snippets" })).toBeChecked();
		expect(
			screen.getByTestId("collection-snippets").getAttribute("data-active"),
		).toBe("true");
		expect(screen.getByTestId("collection-dictionary")).toBeTruthy();
		await user.click(screen.getByRole("radio", { name: "Dictionary" }));
		expect(screen.getByTestId("dictionary-selection-state").textContent).toBe(
			"1",
		);
	});

	it("uses the active tab's live count in the search placeholder", () => {
		act(() => useGlobalSearch.getState().setVocabEntryCount(7));
		render(<GlobalSearchBar currentPage="dictionarySnippets" />);
		expect(screen.getByRole("textbox").getAttribute("placeholder")).toBe(
			"Search 7 corrections",
		);
	});

	it("selects the snippets tab for a legacy templates deep link", () => {
		const { result } = renderHook(() => useNavigation());
		act(() => result.current.navigate("templates"));
		renderDictionaryPage();
		expect(screen.getByRole("radio", { name: "Snippets" })).toBeChecked();
	});

	it("selects the dictionary tab for a legacy vocabulary deep link", () => {
		const { result } = renderHook(() => useNavigation());
		act(() => result.current.navigate("vocabulary"));
		renderDictionaryPage();
		expect(screen.getByRole("radio", { name: "Dictionary" })).toBeChecked();
	});
});

describe("A4/A1 legacy route aliases", () => {
	it.each([
		["settingsOverlay", "settingsGeneral"],
		["settingsAboutPrivacy", "settingsPrivacy"],
		["aboutAndPrivacy", "settingsPrivacy"],
		["settingsDictionarySnippets", "dictionarySnippets"],
	] as const)("maps %s to %s", (legacy, current) => {
		expect(resolvePageAlias(legacy).page).toBe(current);
	});

	it("navigates via an alias without keeping the old route in history", () => {
		const { result } = renderHook(() => useNavigation());
		act(() => result.current.navigate("aboutAndPrivacy"));
		expect(result.current.currentPage).toBe("settingsPrivacy");
		act(() => result.current.goBack());
		expect(result.current.currentPage).toBe("home");
	});

	it("keeps the dictionary tab intent on a legacy route", () => {
		expect(resolvePageAlias("templates").dictionaryTab).toBe("snippets");
		expect(resolvePageAlias("vocabulary").dictionaryTab).toBe("dictionary");
	});
});
