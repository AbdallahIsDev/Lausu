import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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

// The Plugins nav entry is developer-gated. These tests exercise nav
// geometry and label motion, so they opt into the gate; the gating itself
// is covered by Sidebar.plugins-gated.test.tsx.
vi.mock("@/hooks/usePluginCatalog", () => ({
	usePluginsAvailable: () => true,
}));

import { Sidebar } from "@/components/layout/Sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";

// Sidebar renders real Radix Tooltips (via HotkeyTooltip on the nav
// items) + a real Radix Popover (collapsed Settings flyout), both of
// which REQUIRE a TooltipProvider ancestor, the app shell provides
// one (App.tsx). Same props as App.tsx so tooltip timing mirrors
// production.
function renderWithProviders(ui: React.ReactElement) {
	return render(
		<TooltipProvider delayDuration={200} skipDelayDuration={500}>
			{ui}
		</TooltipProvider>,
	);
}

function findNavButton(label: string) {
	return screen.getByRole("button", {
		name: new RegExp(`^${label}(\\s|$)`),
	});
}

const NAV_LABELS = [
	"Home",
	"History",
	"Analytics",
	"Templates",
	"Vocabulary",
	"Media",
	"Models",
	"Microphone",
	"Settings",
	"About & Privacy",
];

describe("Sidebar, collapse rail geometry & transition model", () => {
	afterEach(() => {
		cleanup();
	});

	const baseProps = {
		currentPage: "home" as const,
		onNavigate: vi.fn(),
	};

	it("aside rail width: w-55 expanded, w-12 collapsed (anchored icon column stays centered)", () => {
		const { rerender, container } = renderWithProviders(
			<Sidebar {...baseProps} />,
		);
		const aside = () => container.querySelector("aside");
		expect(aside()?.className).toContain("w-55");
		expect(aside()?.className).not.toContain("w-12");

		rerender(
			<TooltipProvider delayDuration={200} skipDelayDuration={500}>
				<Sidebar {...baseProps} collapsed />
			</TooltipProvider>,
		);
		expect(aside()?.className).toContain("w-12");
		expect(aside()?.className).not.toContain("w-55");
	});

	it("icon anchoring: every top-level nav button uses the same px-2 icon column in BOTH states (never justify-center)", () => {
		const { rerender } = renderWithProviders(<Sidebar {...baseProps} />);
		const assertAnchored = () => {
			const buttons = Array.from(
				document.querySelectorAll<HTMLButtonElement>(
					"aside button[data-nav-item='true']",
				),
			);
			expect(buttons.length).toBe(11);
			for (const btn of buttons) {
				// The single anchored icon column: identical start padding
				// in both states (container p-2 + button px-2 = 16px from
				// the aside edge).
				expect(btn.className).toContain("px-2");
				// (justify-center), the one button whose icon jumped on
				// toggle. Forbidden: content must flow from the anchored
				// column in both states.
				expect(btn.className).not.toContain("justify-center");
			}
		};
		assertAnchored();

		rerender(
			<TooltipProvider delayDuration={200} skipDelayDuration={500}>
				<Sidebar {...baseProps} collapsed />
			</TooltipProvider>,
		);
		assertAnchored();
	});

	it("label spans use the shared animated text transition (explicit blur endpoints, no filter-none)", () => {
		const { rerender } = renderWithProviders(<Sidebar {...baseProps} />);
		const labelSpans = () =>
			Array.from(
				document.querySelectorAll<HTMLSpanElement>(
					"aside button[data-nav-item='true'] > span",
				),
			)
				.filter((s) =>
					s.className.includes(
						"transition-[max-width,opacity,translate,filter]",
					),
				)
				// The trailing "new" marker is not a nav LABEL: it rides the
				// same motion model so the rail collapses cleanly, but it is
				// excluded here so this suite keeps asserting the label
				// contract (label max-width, blur endpoints) only.
				.filter((s) => s.getAttribute("data-testid") !== "nav-new-badge");
		// 11 nav items, every leaf + the Settings parent.
		expect(labelSpans().length).toBe(11);
		for (const span of labelSpans()) {
			expect(span.className).toContain("opacity-100");
			expect(span.className).toContain("blur-[0px]");
			expect(span.className).toContain("max-w-40");
			// `filter-none` cannot interpolate against blur(), it snaps
			expect(span.className).not.toContain("filter-none");
			// STRICTLY horizontal motion: the transition property list and
			// the motion tokens must never introduce a Y component.
			expect(span.className).toContain(
				"transition-[max-width,opacity,translate,filter]",
			);
			expect(span.className).not.toContain("translate-y");
		}

		rerender(
			<TooltipProvider delayDuration={200} skipDelayDuration={500}>
				<Sidebar {...baseProps} collapsed />
			</TooltipProvider>,
		);
		for (const span of labelSpans()) {
			expect(span.className).toContain("opacity-0");
			expect(span.className).toContain("blur-[4px]");
			expect(span.className).toContain("max-w-0");
			// Text exits toward the inline-start icon column (RTL-mirrored).
			expect(span.className).toContain("-translate-x-3");
			expect(span.className).toContain("rtl:translate-x-3");
			// Invisible labels never intercept pointer events.
			expect(span.className).toContain("pointer-events-none");
			// X-axis only, no vertical/diagonal travel.
			expect(span.className).not.toContain("translate-y");
		}
	});

	it("vertical rhythm: sections gap-1; nav gap-5 expanded / gap-2 collapsed", () => {
		const { rerender, container } = renderWithProviders(
			<Sidebar {...baseProps} />,
		);
		const nav = container.querySelector("nav");
		expect(nav?.className).toContain("gap-5");
		expect(nav?.className).not.toContain("gap-2");
		for (const section of container.querySelectorAll("section")) {
			expect(section.className).toContain("flex flex-col gap-1");
		}

		rerender(
			<TooltipProvider delayDuration={200} skipDelayDuration={500}>
				<Sidebar {...baseProps} collapsed />
			</TooltipProvider>,
		);
		expect(nav?.className).toContain("gap-2");
		expect(nav?.className).not.toContain("gap-5");
	});

	it("renders NO group heading containers in either state (labels are AT-only)", () => {
		// Group names live on <section aria-label> only; there is no
		// heading element, so there is no heading collapse animation to
		// model. Pinned in BOTH states so a heading cannot reappear in
		// one rail state only.
		const headings = (container: HTMLElement) =>
			Array.from(container.querySelectorAll("section > div")).filter((d) =>
				d.className.includes("transition-[max-height]"),
			);
		const { rerender, container } = renderWithProviders(
			<Sidebar {...baseProps} />,
		);
		expect(headings(container).length).toBe(0);
		expect(screen.queryByText("System")).toBeNull();

		rerender(
			<TooltipProvider delayDuration={200} skipDelayDuration={500}>
				<Sidebar {...baseProps} collapsed />
			</TooltipProvider>,
		);
		expect(headings(container).length).toBe(0);
		expect(screen.queryByText("System")).toBeNull();
	});

	it("collapsed rail: every icon keeps a non-empty accessible name (incl. the Settings flyout trigger)", () => {
		renderWithProviders(<Sidebar {...baseProps} collapsed />);
		for (const label of NAV_LABELS) {
			const btn = findNavButton(label);
			expect(btn).toBeTruthy();
			expect(btn.getAttribute("aria-label") ?? btn.textContent?.trim()).toBe(
				label,
			);
		}
	});

	it("collapsed Settings trigger shows the same right-side hotkey tooltip on focus as the leaves", async () => {
		renderWithProviders(<Sidebar {...baseProps} collapsed />);
		const settings = findNavButton("Settings");
		settings.focus();
		const tooltip = await screen.findByRole("tooltip");
		expect(within(tooltip).getByText("Settings")).toBeTruthy();
		// Settings carries the Ctrl+, shortcut chips like the expanded
		// nav's aria-keyshortcuts contract.
		const kbdTexts = Array.from(tooltip.querySelectorAll("kbd")).map(
			(k) => k.textContent,
		);
		expect(kbdTexts).toContain("Ctrl");
		expect(kbdTexts).toContain(",");
	});

	it("rapid collapse/expand toggling keeps all 11 nav buttons mounted with classes flipping cleanly", () => {
		const { rerender } = renderWithProviders(<Sidebar {...baseProps} />);
		const countButtons = () =>
			document.querySelectorAll<HTMLButtonElement>(
				"aside button[data-nav-item='true']",
			).length;
		for (let i = 0; i < 4; i++) {
			rerender(
				<TooltipProvider delayDuration={200} skipDelayDuration={500}>
					<Sidebar {...baseProps} collapsed />
				</TooltipProvider>,
			);
			expect(countButtons()).toBe(11);
			rerender(
				<TooltipProvider delayDuration={200} skipDelayDuration={500}>
					<Sidebar {...baseProps} />
				</TooltipProvider>,
			);
			expect(countButtons()).toBe(11);
		}
		// After the toggle storm the expanded tree is intact: labels,
		// active state, and the Settings submenu contract all survive.
		expect(findNavButton("Home").getAttribute("aria-current")).toBe("page");
	});
});
