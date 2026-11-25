import { act, cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

import { APP_NAME } from "@/branding";

// The Plugins nav entry is developer-gated. These tests exercise nav
// geometry and label motion, so they opt into the gate; the gating itself
// is covered by Sidebar.plugins-gated.test.tsx.
vi.mock("@/hooks/usePluginCatalog", () => ({
	usePluginsAvailable: () => true,
	usePluginsUnlocked: () => true,
}));

import { Sidebar } from "@/components/layout/Sidebar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ensureLocaleLoaded, setLocale } from "@/i18n/i18n";
import { useAppStore } from "@/stores/appStore";

// Sidebar renders real Radix Tooltips (via HotkeyTooltip on the nav
// items), which REQUIRE a TooltipProvider ancestor, the app shell
// provides one (App.tsx:475). Same props as App.tsx so tooltip timing
// in tests mirrors production.
function renderWithProviders(ui: React.ReactElement) {
	return render(
		<TooltipProvider delayDuration={200} skipDelayDuration={500}>
			{ui}
		</TooltipProvider>,
	);
}

// Helper: find a nav-item button by its visible label. The Sidebar sets
// `title` on each nav button (either the bare label for items without a
// shortcut, or `${label} (${shortcut})` for items with one). We match by
// a regex anchored at the start of the title so both shapes are found.
// `getByText` is unreliable here because the Button component renders
// the label inside a child <span> that may be collapsed/hidden, so the
// title attribute is the stable locator.
function findNavButton(label: string) {
	return screen.getByRole("button", {
		name: new RegExp(`^${label}(\\s|$)`),
	});
}

describe("Sidebar", () => {
	beforeEach(() => {
		cleanup();
	});

	afterEach(() => {
		cleanup();
		useAppStore.setState({ config: null });
	});

	const baseProps = {
		currentPage: "home" as const,
		onNavigate: vi.fn(),
	};

	it("shows the active model directly above the CPU/GPU switch (both hidden when collapsed)", () => {
		useAppStore.setState({
			config: {
				asr_backend: "whisper",
				model_size: "large-v3",
				device: "cuda",
				gpu_available: true,
			} as never,
		});
		const { rerender } = renderWithProviders(<Sidebar {...baseProps} />);

		const model = screen.getByTestId("sidebar-active-model");
		const deviceSwitch = screen.getByRole("radiogroup", {
			name: "Compute device",
		});
		expect(
			model.compareDocumentPosition(deviceSwitch) &
				Node.DOCUMENT_POSITION_FOLLOWING,
		).toBeTruthy();

		rerender(
			<TooltipProvider delayDuration={200} skipDelayDuration={500}>
				<Sidebar {...baseProps} collapsed />
			</TooltipProvider>,
		);
		expect(screen.queryByTestId("sidebar-active-model")).toBeNull();
	});

	//active nav item visual hierarchy ───────────────────────

	it("UX-16: active leaf nav item blends with the page (card border, --background background, primary text)", () => {
		renderWithProviders(<Sidebar {...baseProps} currentPage="home" />);
		const activeButton = findNavButton("Home");
		expect(activeButton).toBeTruthy();
		const cls = activeButton?.className ?? "";
		// Active leaf = the standard card treatment: the shared border
		// token at 10% (2026-10-02: #FFFFFF/10 in dark, #000000/10 in
		// light — `border-border` carries both).
		expect(cls).toContain("border-border/10");
		// The legacy left-accent-bar borders are gone from ALL nav buttons.
		expect(cls).not.toContain("border-s-2");
		expect(cls).not.toContain("border-s-transparent");
		expect(cls).not.toContain("before:bg-accent");
		// Active background matches the page background (--background), and the
		// old soft-accent tint is gone.
		expect(cls).toContain("bg-surface");
		expect(cls).not.toContain("bg-(--accent-soft)");
		// Text color + weight bumped to primary/medium.
		expect(cls).toContain("text-foreground");
		expect(cls).toContain("font-medium");
	});

	it("UX-16: Settings leaf takes the standard card treatment when a Settings surface is active", () => {
		renderWithProviders(<Sidebar {...baseProps} currentPage="settings" />);
		const settingsButton = findNavButton("Settings");
		expect(settingsButton).toBeTruthy();
		const cls = settingsButton?.className ?? "";
		// Settings is a SINGLE leaf now, the parent/submenu concept is
		// gone (the hub page holds the section navigation). When a
		// Settings surface is active the leaf takes the SAME standard
		// card treatment as every other active page: the shared card
		// border token + the card surface + primary text at medium
		// exists.
		// NOTE: the isSettingsSurface fallback in SidebarInner carries
		// the roving tab stop (tabIndex=0) to the Settings leaf on every
		// Settings surface, but aria-current + the active card styling
		// follow `isActive` (exact page match), which only the hub
		// ("settings") satisfies, section pages (e.g. "settingsPrivacy")
		// render the leaf inactive-by-style with the tab stop only (see
		// Sidebar.settings-leaf.test.tsx).
		expect(cls).toContain("border-border/10");
		expect(cls).toContain("bg-surface");
		expect(cls).toContain("text-foreground");
		expect(cls).toContain("font-medium");
		expect(settingsButton.getAttribute("aria-current")).toBe("page");
		// The Button base's inactive weight must not leak through the
		// active treatment (font-medium replaces font-normal).
		expect(cls).not.toContain("font-normal");
	});

	it("UX-16: inactive nav items do NOT carry the card border or any active background", () => {
		renderWithProviders(<Sidebar {...baseProps} currentPage="home" />);
		const inactiveButton = findNavButton("History");
		expect(inactiveButton).toBeTruthy();
		const cls = inactiveButton?.className ?? "";
		// Inactive leaves carry the border at 0% (#FFFFFF/0 = transparent)
		// and nothing else; the legacy border-s-2 alignment bar is gone.
		expect(cls).toContain("border-transparent");
		expect(cls).not.toContain("border-s-2");
		expect(cls).not.toContain("border-s-transparent");
		expect(cls).not.toContain("border-border/10");
		expect(cls).not.toContain("border-s-(--accent)");
		expect(cls).not.toContain("bg-(--accent-soft)");
		expect(cls).not.toContain("bg-surface");
		expect(cls).not.toContain("before:bg-accent");
		expect(cls).not.toContain("font-medium");
	});

	//nav grouping ──────────────────────────────────────────

	it("renders NO visible group heading; groups are labelled for AT only", () => {
		renderWithProviders(<Sidebar {...baseProps} />);
		// No group renders a visible heading: the sidebar reads as one
		// clean list. Group context is carried by the <section aria-label>
		// only, which the next test pins.
		expect(screen.queryByText("System")).toBeNull();
		expect(screen.queryByText("Main")).toBeNull();
		expect(screen.queryByText("Power features")).toBeNull();
	});

	it("groups are rendered as <section> elements with aria-label matching the group label", () => {
		renderWithProviders(<Sidebar {...baseProps} />);
		const mainSection = findNavButton("Home").closest("section");
		const systemSection = findNavButton("Settings").closest("section");
		expect(mainSection?.getAttribute("aria-label")).toBe("Main");
		expect(systemSection?.getAttribute("aria-label")).toBe("System");
		// Only TWO groups exist.
		expect(document.querySelectorAll("aside section").length).toBe(2);
	});

	it("Home/History/Analytics/Models/Dictionary & Snippets/Media/Microphone are in Main; only Settings is in System", () => {
		renderWithProviders(<Sidebar {...baseProps} />);
		const groupOf = (label: string) =>
			findNavButton(label).closest("section")?.getAttribute("aria-label");

		expect(groupOf("Home")).toBe("Main");
		expect(groupOf("History")).toBe("Main");
		expect(groupOf("Analytics")).toBe("Main");
		expect(groupOf("Models")).toBe("Main");
		expect(groupOf("Dictionary & Snippets")).toBe("Main");
		expect(groupOf("Media")).toBe("Main");
		expect(groupOf("Microphone")).toBe("Main");

		expect(groupOf("Settings")).toBe("System");
	});

	it("PROD-7: renders NO <hr> dividers between the groups", () => {
		renderWithProviders(<Sidebar {...baseProps} />);
		const nav = screen.getByRole("navigation", { name: "Main navigation" });
		expect(nav.querySelectorAll("hr").length).toBe(0);
	});

	it("PROD-7: About & Privacy is no longer a top-level sidebar destination", () => {
		renderWithProviders(<Sidebar {...baseProps} />);
		expect(findNavButton("Settings")).toBeTruthy();
		expect(
			screen.queryByRole("button", { name: /^About & Privacy/ }),
		).toBeNull();
	});

	//aria-keyshortcuts on nav items ────────────────────────

	it("PROD-9: Home nav item exposes aria-keyshortcuts='Control+h' (App.tsx binds Ctrl+H)", () => {
		renderWithProviders(<Sidebar {...baseProps} />);
		const homeButton = findNavButton("Home");
		expect(homeButton.getAttribute("aria-keyshortcuts")).toBe("Control+h");
	});

	it("PROD-9: Settings nav item exposes aria-keyshortcuts='Control+,' (App.tsx binds Ctrl+,)", () => {
		renderWithProviders(<Sidebar {...baseProps} />);
		const settingsButton = findNavButton("Settings");
		expect(settingsButton.getAttribute("aria-keyshortcuts")).toBe("Control+,");
	});

	it("expanded: NO visible shortcut keycaps render inside the nav item (aria-keyshortcuts stays)", async () => {
		renderWithProviders(<Sidebar {...baseProps} currentPage="home" />);
		const home = findNavButton("Home");
		// No plain-text `title` tooltip attribute.
		expect(home.hasAttribute("title")).toBe(false);
		// The shortcut is NOT rendered as visible chips inside the
		// expanded nav item, the sidebar stays clean (the shortcut
		// remains functional via aria-keyshortcuts + the global
		// shortcut handler).
		const kbdTexts = Array.from(home.querySelectorAll("kbd")).map(
			(k) => k.textContent,
		);
		expect(kbdTexts).not.toContain("Ctrl");
		expect(kbdTexts).not.toContain("H");
		// aria-keyshortcuts still exposes the binding to AT.
		expect(home.getAttribute("aria-keyshortcuts")).toBe("Control+h");
		// The expanded label is visible, so NO tooltip is rendered —
		// focusing the item must not open one (there is no Tooltip
		// wrapper around the expanded nav items at all).
		home.focus();
		expect(screen.queryByRole("tooltip")).toBeNull();
	});

	it("collapsed: tooltip with label + shortcut chips still appears on hover/focus", async () => {
		renderWithProviders(
			<Sidebar {...baseProps} collapsed currentPage="home" />,
		);
		const home = findNavButton("Home");
		expect(home.hasAttribute("title")).toBe(false);
		// The label is hidden when collapsed, the right-side tooltip
		// carries the label + shortcut chips (Radix opens on focus).
		home.focus();
		const tooltip = await screen.findByRole("tooltip");
		expect(within(tooltip).getByText("Home")).toBeTruthy();
		const kbdTexts = Array.from(tooltip.querySelectorAll("kbd")).map(
			(k) => k.textContent,
		);
		expect(kbdTexts).toContain("Ctrl");
		expect(kbdTexts).toContain("H");
	});

	it("PROD-9: nav items without a keyboard shortcut omit aria-keyshortcuts entirely", () => {
		renderWithProviders(<Sidebar {...baseProps} />);
		// Only Home and Settings expose shortcuts in the nav composite.
		const noShortcutItems = [
			"History",
			"Analytics",
			"Dictionary & Snippets",
			"Media",
			"Models",
			"Microphone",
		];
		for (const label of noShortcutItems) {
			const btn = findNavButton(label);
			expect(btn?.hasAttribute("aria-keyshortcuts")).toBe(false);
		}
	});

	it("the System group is pinned to the sidebar bottom (mt-auto); the Main group is not", () => {
		renderWithProviders(<Sidebar {...baseProps} />);
		const sectionClassOf = (label: string) =>
			findNavButton(label).closest("section")?.className ?? "";
		expect(sectionClassOf("Settings")).toContain("mt-auto");
		// The top groups flow normally, no auto margin competing with
		// the System group's bottom anchor.
		expect(sectionClassOf("Home")).not.toContain("mt-auto");
		expect(sectionClassOf("Dictionary & Snippets")).not.toContain("mt-auto");
	});

	//sidebar branding removed ──────────────────────────

	it("SIDEBAR-BRANDING: no logo button (collapsed or expanded), the branding header was removed entirely", () => {
		const { rerender } = renderWithProviders(
			<Sidebar {...baseProps} collapsed />,
		);
		// The collapsed logo <button aria-label={APP_NAME}> no longer exists.
		expect(screen.queryByLabelText(APP_NAME)).toBeNull();

		rerender(
			<TooltipProvider delayDuration={200} skipDelayDuration={500}>
				<Sidebar {...baseProps} collapsed={false} />
			</TooltipProvider>,
		);
		expect(screen.queryByLabelText(APP_NAME)).toBeNull();
	});

	it("SIDEBAR-BRANDING: the nav is the sidebar's first content (nothing sits above it)", () => {
		renderWithProviders(<Sidebar {...baseProps} />);
		const nav = screen.getByRole("navigation", { name: "Main navigation" });
		// The nav's scroll container must be the first child of the
		// <aside>, no branding header precedes it, so the navigation
		const aside = nav.closest("aside");
		expect(nav.parentElement).toBe(aside?.children[0]);
	});

	it("SIDEBAR-BRANDING: no theme switch renders inside the sidebar (moved to the TitleBar)", () => {
		renderWithProviders(<Sidebar {...baseProps} />);
		expect(screen.queryByLabelText(/^Current theme:/)).toBeNull();
	});
});

describe("Sidebar inner nav direction follows the active locale", () => {
	beforeEach(async () => {
		await act(async () => {
			setLocale("en");
			await ensureLocaleLoaded("ar");
		});
	});

	afterEach(() => {
		act(() => {
			setLocale("en");
		});
		cleanup();
	});

	it("keeps the rail and nav flow physically LTR in both locales, with RTL only on labels", async () => {
		const props = { currentPage: "home" as const, onNavigate: vi.fn() };
		const { rerender } = renderWithProviders(<Sidebar {...props} />);
		const nav = screen.getByRole("navigation", { name: "Main navigation" });
		const navContainer = nav.parentElement;
		const aside = nav.closest("aside");

		// The rail is left-pinned, so the NAV FLOW must stay LTR in every
		// locale. An rtl flow would right-anchor `justify-start` and move
		// the icon column on collapse (C-SIDEBAR-12). Only the label text
		// is allowed to follow the locale.
		expect(navContainer?.getAttribute("dir")).toBe("ltr");
		expect(aside?.getAttribute("dir")).toBeNull();
		let label = screen.getByText("Home");

		// Collapse identity: same button + same icon node, still first
		// child, same physical-left anchoring classes. jsdom has no layout,
		// so these invariants stand in for the manual x-position check.
		const expandedButton = label.closest("button");
		const icon = expandedButton?.querySelector('[data-testid="hugeicon"]');
		expect(icon).toBeTruthy();
		expect(expandedButton?.firstElementChild).toBe(icon);
		expect(expandedButton?.classList.contains("justify-start")).toBe(true);
		expect(expandedButton?.classList.contains("px-2")).toBe(true);
		expect(label.getAttribute("dir")).toBe("ltr");

		rerender(
			<TooltipProvider delayDuration={200} skipDelayDuration={500}>
				<Sidebar {...props} collapsed />
			</TooltipProvider>,
		);
		label = screen.getByText("Home");
		const collapsedButton = label.closest("button");
		expect(collapsedButton).toBe(expandedButton);
		expect(collapsedButton?.firstElementChild).toBe(icon);
		expect(collapsedButton?.classList.contains("justify-start")).toBe(true);
		expect(collapsedButton?.classList.contains("px-2")).toBe(true);
		expect(navContainer?.getAttribute("dir")).toBe("ltr");

		await act(async () => {
			setLocale("ar");
		});
		rerender(
			<TooltipProvider delayDuration={200} skipDelayDuration={500}>
				<Sidebar {...props} />
			</TooltipProvider>,
		);
		expect(navContainer?.getAttribute("dir")).toBe("ltr");
		expect(aside?.getAttribute("dir")).toBeNull();

		const arLabel = screen.getByText("الرئيسية");
		expect(arLabel.getAttribute("dir")).toBe("rtl");
		const arButton = arLabel.closest("button");
		const arIcon = arButton?.querySelector('[data-testid="hugeicon"]');
		expect(arButton?.firstElementChild).toBe(arIcon);
		expect(arButton?.classList.contains("justify-start")).toBe(true);
		expect(arButton?.classList.contains("px-2")).toBe(true);

		rerender(
			<TooltipProvider delayDuration={200} skipDelayDuration={500}>
				<Sidebar {...props} collapsed />
			</TooltipProvider>,
		);
		const arCollapsedLabel = screen.getByText("الرئيسية");
		expect(screen.getByText("الرئيسية").closest("button")).toBe(arButton);
		expect(arCollapsedLabel.getAttribute("dir")).toBe("rtl");
		expect(arButton?.firstElementChild).toBe(arIcon);
		expect(navContainer?.getAttribute("dir")).toBe("ltr");
	});
});
