import {
	AiBrain03Icon,
	Analytics01Icon,
	BookOpen02Icon,
	Film01Icon,
	HistoryIcon,
	Home04Icon,
	Mic02Icon,
	Settings01Icon,
} from "@hugeicons/core-free-icons";
import type { IconSvgElement } from "@hugeicons/react";
import { HugeiconsIcon } from "@hugeicons/react";
import { memo, useRef } from "react";
import { ErrorBoundary } from "@/components/feedback/ErrorBoundary";
import { HotkeyTooltip } from "@/components/hotkey/HotkeyTooltip";
import { formatHotkey } from "@/components/hotkey/hotkey-utils";
import { SHORTCUTS } from "@/components/hotkey/shortcuts";
import { DeviceToggle } from "@/components/layout/DeviceToggle";
import { SidebarActiveModel } from "@/components/layout/SidebarActiveModel";
import { isSettingsSurface } from "@/components/settings/settingsSections";
import { Button } from "@/components/ui/button";
import { getLocale, isRtlLocale, t, useT } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import { prefetchPage } from "@/router/prefetch";
import type { Page } from "@/types/ipc";

// Only actual sidebar destinations are in this union. Keeping it narrow
// makes `t(`nav.${item.id}`)` type-checked against the locale catalogs:
// adding a nav item without its translation fails typecheck.
type NavLeafId = Extract<
	Page,
	| "home"
	| "history"
	| "analytics"
	| "models"
	| "dictionarySnippets"
	| "media"
	| "microphone"
	| "settings"
>;

interface NavItem {
	id: NavLeafId;
	icon: IconSvgElement;
}

// The everyday group is the whole navigation except Settings. Settings
// lives in the bottom cluster so the future profile/settings-entry
// options (title bar, profile row, dropdown) only have to replace that
// one leaf — nothing in this group changes.
const MAIN_NAV_ITEMS: NavItem[] = [
	{ id: "home", icon: Home04Icon },
	{ id: "history", icon: HistoryIcon },
	{ id: "analytics", icon: Analytics01Icon },
	{ id: "models", icon: AiBrain03Icon },
	{ id: "dictionarySnippets", icon: BookOpen02Icon },
	{ id: "media", icon: Film01Icon },
	{ id: "microphone", icon: Mic02Icon },
];

// Bottom cluster: active model/plugin indicator + CPU/GPU switch, then
// the single Settings leaf. Product identity lives in Settings → Privacy.
const SYSTEM_NAV_ITEMS: NavItem[] = [{ id: "settings", icon: Settings01Icon }];

interface NavGroup {
	labelKey: string;
	fallback: string;
	items: NavItem[];
	pinnedToBottom?: boolean;
}

const NAV_GROUPS: NavGroup[] = [
	{ labelKey: "nav.group.main", fallback: "Main", items: MAIN_NAV_ITEMS },
	{
		labelKey: "nav.group.system",
		fallback: "System",
		items: SYSTEM_NAV_ITEMS,
		pinnedToBottom: true,
	},
];

const ALL_NAV_ITEMS: NavItem[] = [...MAIN_NAV_ITEMS, ...SYSTEM_NAV_ITEMS];

const NAV_KEYSHORTCUTS: Partial<Record<Page, string>> = {
	home: SHORTCUTS.goHome.ariaKeyshortcuts,
	settings: SHORTCUTS.openSettings.ariaKeyshortcuts,
};

function navShortcut(page: Page): string | undefined {
	switch (page) {
		case "home":
			return formatHotkey(SHORTCUTS.goHome.pynput ?? SHORTCUTS.goHome.keys);
		case "settings":
			return formatHotkey(
				SHORTCUTS.openSettings.pynput ?? SHORTCUTS.openSettings.keys,
			);
	}
	return undefined;
}

// ONE label motion model for the whole rail (opacity + inline-start
// translate + explicit blur endpoints). X-axis only, never Y. The
// element owns its transition-property list; here we only supply state
// classes so a persistent node animates when `collapsed` flips.
function navLabelMotion(collapsed: boolean): string {
	return collapsed
		? "-translate-x-3 opacity-0 blur-[4px] pointer-events-none rtl:translate-x-3"
		: "translate-x-0 opacity-100 blur-[0px]";
}

function navTextClasses(collapsed: boolean): string {
	return cn(
		"overflow-hidden whitespace-nowrap text-sm font-medium dark:font-normal",
		"transition-[max-width,opacity,translate,filter] duration-200 ease-out",
		collapsed ? "max-w-0" : "max-w-40",
		navLabelMotion(collapsed),
	);
}

function navGroupLabel(labelKey: string, fallback: string): string {
	const translated = t(labelKey);
	return translated === labelKey ? fallback : translated;
}

interface SidebarProps {
	currentPage: Page;
	onNavigate: (page: Page) => void;
	collapsed?: boolean;
}

function SidebarInner({
	currentPage,
	onNavigate,
	collapsed = false,
}: SidebarProps) {
	const t = useT();
	const navRef = useRef<HTMLElement>(null);
	const activeFlatIdx = ALL_NAV_ITEMS.findIndex((i) => i.id === currentPage);
	// Settings-section pages are not nav items: hand the roving tab stop
	// to the Settings leaf so keyboard focus follows the active surface.
	const rovingFallbackIdx = isSettingsSurface(currentPage)
		? ALL_NAV_ITEMS.findIndex((i) => i.id === "settings")
		: -1;
	const rovingIdx =
		activeFlatIdx >= 0
			? activeFlatIdx
			: rovingFallbackIdx >= 0
				? rovingFallbackIdx
				: 0;

	const handleNavKeyDown = (e: React.KeyboardEvent<HTMLElement>) => {
		const nav = navRef.current;
		if (!nav) return;
		const buttons = Array.from(
			nav.querySelectorAll<HTMLButtonElement>("button[data-nav-item='true']"),
		);
		if (buttons.length === 0) return;
		const currentIdx = buttons.indexOf(
			document.activeElement as HTMLButtonElement,
		);
		let nextIdx = currentIdx;
		switch (e.key) {
			case "ArrowDown":
				e.preventDefault();
				nextIdx = currentIdx < 0 ? 0 : (currentIdx + 1) % buttons.length;
				break;
			case "ArrowUp":
				e.preventDefault();
				nextIdx =
					currentIdx < 0
						? buttons.length - 1
						: (currentIdx - 1 + buttons.length) % buttons.length;
				break;
			case "Home":
				e.preventDefault();
				nextIdx = 0;
				break;
			case "End":
				e.preventDefault();
				nextIdx = buttons.length - 1;
				break;
			default:
				return;
		}
		const target = buttons[nextIdx];
		if (target !== undefined) target.focus();
	};

	return (
		<aside
			className={cn(
				"flex shrink-0 flex-col",
				"overflow-hidden",
				"bg-sidebar",
				"transition-[width] duration-200 ease-out",
				collapsed ? "w-12" : "w-55",
			)}
		>
			{/* The rail is left-pinned in every locale: nav FLOW stays LTR
			    so the icon column never jumps on collapse. RTL applies to
			    label text only. */}
			<div className="min-h-0 flex-1 overflow-y-auto p-2" dir="ltr">
				<nav
					ref={navRef}
					aria-label={t("a11y.mainNavigation")}
					onKeyDown={handleNavKeyDown}
					className={cn(
						"flex min-h-full flex-col",
						collapsed ? "gap-2" : "gap-5",
					)}
				>
					{NAV_GROUPS.map((group) => (
						<section
							key={group.labelKey}
							aria-label={navGroupLabel(group.labelKey, group.fallback)}
							className={cn(
								"flex flex-col gap-1",
								group.pinnedToBottom && "mt-auto",
							)}
						>
							{/* Bottom slot. The model caption reads only engine
							    identity; the switch is isolated behind its own
							    error boundary so a broken toggle cannot blank the
							    caption or the whole rail (C-UI-10). */}
							{group.pinnedToBottom && (
								<SidebarActiveModel collapsed={collapsed} />
							)}
							{group.pinnedToBottom && (
								<ErrorBoundary fallback={null}>
									<DeviceToggle collapsed={collapsed} />
								</ErrorBoundary>
							)}
							{group.items.map((item) => (
								<NavLeaf
									key={item.id}
									item={item}
									currentPage={currentPage}
									collapsed={collapsed}
									onNavigate={onNavigate}
									tabIndex={
										ALL_NAV_ITEMS.findIndex((i) => i.id === item.id) ===
										rovingIdx
											? 0
											: -1
									}
								/>
							))}
						</section>
					))}
				</nav>
			</div>
		</aside>
	);
}

interface NavLeafProps {
	item: NavItem;
	currentPage: Page;
	collapsed: boolean;
	onNavigate: (page: Page) => void;
	tabIndex: number;
}

// Always wrapped in the same HotkeyTooltip element in both states:
// swapping wrappers would remount the button and skip its label
// transition. Content is suppressed while expanded.
function NavLeaf({
	item,
	currentPage,
	collapsed,
	onNavigate,
	tabIndex,
}: NavLeafProps) {
	const isActive = currentPage === item.id;
	const navLabel = t(`nav.${item.id}`);
	return (
		<HotkeyTooltip
			label={navLabel}
			keys={navShortcut(item.id)}
			side="right"
			disabled={!collapsed}
		>
			<Button
				variant="ghost"
				data-nav-item="true"
				aria-keyshortcuts={NAV_KEYSHORTCUTS[item.id]}
				tabIndex={tabIndex}
				aria-current={isActive ? "page" : undefined}
				className={cn(
					"w-full justify-start gap-3 text-sm tracking-wide normal-case font-normal rounded-lg",
					"overflow-hidden",
					"transition-[background-color,border-color,color] duration-200 ease-out",
					"px-2",
					isActive
						? cn(
								"border-border/10 bg-surface hover:bg-surface",
								"text-foreground font-medium",
							)
						: cn(
								"border-transparent dark:border-transparent text-muted-foreground",
								"hover:bg-foreground/5 hover:text-foreground",
							),
				)}
				onClick={() => onNavigate(item.id)}
				onMouseEnter={() => prefetchPage(item.id)}
				onFocus={() => prefetchPage(item.id)}
			>
				<HugeiconsIcon
					icon={item.icon}
					strokeWidth={2}
					className={cn("h-4 w-4 shrink-0 transition-colors duration-200")}
				/>
				<span
					className={navTextClasses(collapsed)}
					dir={isRtlLocale(getLocale()) ? "rtl" : "ltr"}
				>
					{navLabel}
				</span>
			</Button>
		</HotkeyTooltip>
	);
}

export const Sidebar = memo(SidebarInner);
