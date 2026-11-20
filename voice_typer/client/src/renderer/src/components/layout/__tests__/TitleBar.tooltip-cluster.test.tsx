import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: ({ icon }: { icon?: { name?: string } }) => (
		<span data-testid="hugeicon" data-name={icon?.name} />
	),
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

import { TitleBar } from "@/components/layout/TitleBar";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { WindowBridge } from "@/types/ipc";

function makeBridge(): WindowBridge {
	return {
		minimize: vi.fn().mockResolvedValue(undefined),
		toggleMaximize: vi.fn().mockResolvedValue(true),
		close: vi.fn().mockResolvedValue(undefined),
		isMaximized: vi.fn().mockResolvedValue(false),
		onMaximizedChanged: vi.fn().mockReturnValue(() => {}),
		exportHistory: vi.fn().mockResolvedValue({ success: true }),
		exportVocabulary: vi.fn().mockResolvedValue({ success: true }),
	};
}

function renderBar() {
	(window as unknown as { window_?: WindowBridge }).window_ = makeBridge();
	return render(
		<TooltipProvider delayDuration={0} skipDelayDuration={0}>
			<TitleBar
				onToggleSidebar={() => {}}
				onGoBack={() => {}}
				onGoForward={() => {}}
				canGoBack
				canGoForward
				isMaximized={false}
				onOpenHelp={() => {}}
				themeMode="light"
				onThemeChange={() => {}}
			/>
		</TooltipProvider>,
	);
}

afterEach(() => {
	cleanup();
	vi.restoreAllMocks();
});

describe("TitleBar toolbar cluster", () => {
	it("orders Back, Forward, Toggle Sidebar, Help", () => {
		renderBar();
		const back = screen.getByLabelText(/go back/i);
		const forward = screen.getByLabelText(/go forward/i);
		const sidebar = screen.getByLabelText(/toggle sidebar/i);
		const help = screen.getByLabelText(/^help overlay$/i);
		// DOCUMENT_POSITION_FOLLOWING (4) means "the argument comes after".
		expect(back.compareDocumentPosition(forward) & 4).toBe(4);
		expect(forward.compareDocumentPosition(sidebar) & 4).toBe(4);
		expect(sidebar.compareDocumentPosition(help) & 4).toBe(4);
	});

	it("swaps tooltip content without closing when the pointer crosses the row", async () => {
		renderBar();
		const back = screen.getByLabelText(/go back/i);
		const sidebar = screen.getByLabelText(/toggle sidebar/i);

		fireEvent.mouseEnter(back);
		const first = await screen.findByRole("tooltip");
		expect(first.textContent).toContain("Back");

		// Cross to the sidebar toggle without leaving the row: the SAME
		// open tooltip keeps rendering, only its label changes (no closed
		// state, no remount), which is the whole point of the cluster.
		fireEvent.mouseEnter(sidebar);
		await waitFor(() => {
			expect(screen.getByRole("tooltip").textContent).toContain(
				"Toggle sidebar",
			);
		});
		expect(screen.getByRole("tooltip")).toBe(first);
	});

	it("gives the theme toggle ONE compact current→next tooltip", async () => {
		renderBar();
		const theme = screen.getByLabelText(/current theme/i);
		// No native title on the cluster member: both used to fire on hover.
		expect(theme.getAttribute("title")).toBeNull();
		fireEvent.mouseEnter(theme);
		const tip = await screen.findByRole("tooltip");
		expect(screen.getAllByRole("tooltip")).toHaveLength(1);
		expect(tip.textContent).toBe("Light → Dark");

		// Leaving the button but staying inside its wrapper keeps the SAME node.
		fireEvent.mouseLeave(theme, { relatedTarget: theme.parentElement });
		expect(screen.getByRole("tooltip")).toBe(tip);
		fireEvent.mouseLeave(theme.parentElement as Element);
		await waitFor(() => {
			expect(screen.queryByRole("tooltip")).toBeNull();
		});
	});

	it("closes once the pointer leaves the whole row", async () => {
		renderBar();
		const back = screen.getByLabelText(/go back/i);
		fireEvent.mouseEnter(back);
		await screen.findByRole("tooltip");
		fireEvent.mouseLeave(
			back.closest("[data-slot=tooltip-trigger]") as Element,
		);
		await waitFor(() => {
			expect(screen.queryByRole("tooltip")).toBeNull();
		});
	});
});
