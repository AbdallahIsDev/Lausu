import { PanelLeftIcon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { memo, useEffect, useState } from "react";
import { HotkeyTooltip } from "@/components/hotkey/HotkeyTooltip";
import { IS_LINUX, IS_MAC, IS_WIN } from "@/components/hotkey/hotkey-utils";
import { SHORTCUTS } from "@/components/hotkey/shortcuts";
import { AnalyticsRangeSwitcher } from "@/components/layout/AnalyticsRangeSwitcher";
import { GlobalSearchBar } from "@/components/layout/GlobalSearchBar";
import { ModelsTabSwitcher } from "@/components/layout/ModelsTabSwitcher";
import { ThemeSwitch } from "@/components/layout/ThemeSwitch";
import {
	CloseIcon,
	MaximizeIcon,
	MinimizeIcon,
	RestoreIcon,
} from "@/components/layout/titlebar/captionGlyphs";
import {
	NavChevronButton,
	TitleBarButton,
	ToolbarButton,
} from "@/components/layout/titlebar/titleBarButtons";
import { t } from "@/i18n/i18n";
import { isTauri } from "@/lib/tauri-bridge/detect";
import { cn } from "@/lib/utils";
import {
	type ResolvedLinuxWindowButtons,
	resolveLinuxWindowButtons,
} from "@/lib/utils/windowButtons";
import type { LausuConfig } from "@/types/config";
import type { Page, WindowBridge } from "@/types/ipc";

// Focus-aware title bar: native OS title bars DIM their whole bar
// while the window is unfocused (the user clicked another app, e.g.
// VS Code, so the window is visible but inactive), and restore it to
// full brightness on refocus. We mirror that using the DOM
// `focus`/`blur` events on `window`, which fire in BOTH runtimes with
// zero IPC / main-process code: the predecessor's Chromium, and the Tauri
// webviews (WebView2 on Windows, WKWebView on macOS, WebKitGTK on
// Linux). The dim is CONTAINER OPACITY (see TitleBarInner), not a
// specific dim color, so it scales whatever colors the active theme
// resolves and cannot break light/dark/custom themes.
function useWindowFocused(): boolean {
	// Start FOCUSED: a window opens focused, and the blur/focus events
	// below are the source of truth from there on. Deliberately NOT
	// synced from `document.hasFocus()` at mount, that call returns
	// false in jsdom and varies across webviews, which would start the
	// glyphs dimmed in tests; the event-driven state is deterministic.
	const [focused, setFocused] = useState(true);
	useEffect(() => {
		if (typeof window === "undefined") return;
		const onFocus = () => setFocused(true);
		const onBlur = () => setFocused(false);
		window.addEventListener("focus", onFocus);
		window.addEventListener("blur", onBlur);
		return () => {
			window.removeEventListener("focus", onFocus);
			window.removeEventListener("blur", onBlur);
		};
	}, []);
	return focused;
}

interface TitleBarProps {
	onToggleSidebar?: () => void;
	onGoBack?: () => void;
	onGoForward?: () => void;
	canGoBack?: boolean;
	canGoForward?: boolean;
	// ``onMaximizedChanged`` subscription as a fallback for when the
	// prop was undefined, duplicating the subscription already living
	// in App.tsx (App.tsx:161-189) which always passes the prop. The
	// duplicate subscription is deleted; App.tsx is the single owner of
	// the maximize-state subscription.
	isMaximized: boolean;
	// overlay was only reachable via the "?" key, invisible to users
	// who never discover that shortcut. Exposing a TitleBar button
	// makes the overlay discoverable for mouse + keyboard users alike.
	onOpenHelp?: () => void;
	// THEME CONTROL LIVES IN THE TITLE BAR (moved out of the sidebar).
	// The icon-only theme button sits in the window-control cluster so
	// it is part of the bar's control language. App.tsx passes the
	// SAME state + change handler the sidebar's ThemeSwitch used, no
	// second theme implementation.
	themeMode: LausuConfig["theme_mode"];
	onThemeChange: (mode: LausuConfig["theme_mode"]) => void;
	/** Linux-only: the resolved window-button layout (side, visibility,
	 *  circle-vs-square shell). App.tsx computes it from the
	 *  `linux_window_buttons` config + the sidecar's
	 *  `linux_window_buttons_system` snapshot via
	 *  `resolveLinuxWindowButtons`. Optional, omitted (undefined)
	 *  falls back to the classic right-side trio, and the prop is
	 *  ignored entirely on Windows/macOS. */
	linuxWindowButtons?: ResolvedLinuxWindowButtons;
	/** Active route, drives the global search bar's per-page
	 *  placeholder + visibility. Optional so existing TitleBar call
	 *  sites (tests, splash) render without the search bar. */
	currentPage?: Page;
	/** Minimal chrome for the connection-status screens (boot /
	 *  restarting / lost backend): the bar stays visible (drag, theme,
	 *  window buttons) but the toolbar group and the middle strip go
	 *  away, and a card-colored bottom rule separates it from the
	 *  status card below. App.tsx sets this whenever the main column
	 *  shows ConnectionStatusScreen instead of a page. Defaults false. */
	minimalChrome?: boolean;
	/** Per-page middle-strip controls (search, models tabs, analytics
	 *  range) render only while the routed page is actually visible.
	 *  App.tsx sets this false whenever the main column shows the
	 *  connection-status screen instead of the page (boot / restarting
	 *  / lost-backend), so dead controls never linger above an error
	 *  card. Defaults true to preserve existing call sites. */
	showPageControls?: boolean;
}

function TitleBarInner({
	onToggleSidebar,
	onGoBack,
	onGoForward,
	canGoBack,
	canGoForward,
	isMaximized,
	onOpenHelp,
	themeMode,
	onThemeChange,
	linuxWindowButtons,
	currentPage,
	showPageControls = true,
	minimalChrome = false,
}: TitleBarProps) {
	// When the window is unfocused (user clicked another app), the
	// WHOLE title bar dims like native OS title bars (container
	// opacity below).
	const windowFocused = useWindowFocused();
	const bridge =
		typeof window !== "undefined"
			? (window.window_ as WindowBridge)
			: undefined;

	const handleMinimize = () =>
		bridge
			?.minimize()
			.catch((err) =>
				console.warn(
					"[renderer:TitleBar] window control failed: minimize:",
					err,
				),
			);
	const handleToggleMaximize = () =>
		bridge
			?.toggleMaximize()
			.catch((err) =>
				console.warn(
					"[renderer:TitleBar] window control failed: toggleMaximize:",
					err,
				),
			);
	const handleClose = () =>
		bridge
			?.close()
			.catch((err) =>
				console.warn("[renderer:TitleBar] window control failed: close:", err),
			);

	// ── Linux window-button layout (option: system / custom / KDE) ──
	// Resolved from the config + sidecar snapshot by App.tsx; undefined
	// falls back to the classic right-side trio. Only the IS_LINUX
	// cluster below consumes this, Windows keeps its fixed native
	// convention and macOS has no custom buttons at all.
	const linuxButtons =
		linuxWindowButtons ?? resolveLinuxWindowButtons(undefined, undefined);

	const linuxButtonDefs = [
		{
			key: "minimize",
			show: linuxButtons.showMinimize,
			label: t("titleBar.minimize"),
			onClick: handleMinimize,
			glyph: <MinimizeIcon />,
		},
		{
			key: "maximize",
			show: linuxButtons.showMaximize,
			label: isMaximized ? t("titleBar.restore") : t("titleBar.maximize"),
			onClick: handleToggleMaximize,
			glyph: isMaximized ? <RestoreIcon /> : <MaximizeIcon />,
		},
		{
			key: "close",
			show: linuxButtons.showClose,
			label: t("titleBar.close"),
			onClick: handleClose,
			glyph: <CloseIcon />,
		},
	].filter((button) => button.show);

	const renderLinuxCluster = (side: "left" | "right") => (
		<div
			className={cn(
				"flex items-center gap-2",
				// Right side: ms-1 separates from the theme switch and pe-2
				// keeps the close button off the window's right edge.
				// Left side: mirrored insets (the bar is pinned dir="ltr",
				// so these are PHYSICAL sides, see the root's LTR pin).
				side === "right" ? "ms-1 pe-2" : "me-1 ps-2",
			)}
		>
			{linuxButtonDefs.map((button) => (
				<TitleBarButton
					key={button.key}
					onClick={button.onClick}
					ariaLabel={button.label}
					shape={linuxButtons.buttonStyle}
				>
					{button.glyph}
				</TitleBarButton>
			))}
		</div>
	);

	return (
		<div
			// PHYSICAL-SIDE PINNING: the bar is forced LTR so the window
			// chrome keeps its platform-conventional geometry regardless
			// of the document direction. Under dir=rtl a plain flex row
			// would mirror the whole bar, the macOS traffic-light gutter
			// would flip to the right edge and the Windows/Linux
			// minimize/maximize/close cluster to the left, both wrong:
			// native window controls never move when the UI language is
			// RTL. With dir="ltr" the gutter stays physically left, the
			// control cluster physically right, in every locale. Content
			// inside the buttons is icon-only (no text to mirror); the
			// Back/Forward chevrons opt INTO mirroring via the
			// `nav-directional-icon` class, whose [dir="rtl"] ancestor
			// selector still matches through this container.
			dir="ltr"
			{...(isTauri() ? { "data-tauri-drag-region": "" } : {})}
			className={cn(
				"drag-region flex w-full shrink-0 items-center select-none h-9 transition-opacity duration-150",
				// Minimal chrome (status screens): a card-colored bottom
				// rule (C-DESIGN-2 8% default) separates the bar from the
				// status card, same border the cards themselves wear.
				minimalChrome && "border-b border-border/8",
				// Native OS title bars dim the WHOLE bar while the window
				// is unfocused, every element (sidebar toggle, back,
				// forward, help, and all three window controls) tones
				// down together. Opacity is THE theme-agnostic dim: it
				// scales whatever colors the active theme resolves
				// (light/dark/custom), so the pure-white glyph pins and
				// hover colors stay intact underneath and nothing can
				// "break" under a custom theme.
				!windowFocused && "opacity-60",
			)}
		>
			{/* macOS traffic-light gutter: the native red/yellow/green dots
                            are drawn by the OS at trafficLightPosition x:12 spanning
                            ~52px, reserve 72px so the bar's buttons never collide
                            with them. Windows/Linux don't need it (their window
                            controls are the custom ones on the right). */}
			{/* Linux window controls pinned to the LEFT edge, either the
                            desktop's own button-layout says so (gsettings, "follow
                            system" mode) or the user picked "Left" in Settings →
                            Appearance. Rendered BEFORE the toolbar group so the app
                            buttons start after them. The bar is pinned dir="ltr", so
                            this is the physical left edge in every locale. */}
			{IS_LINUX && linuxButtons.side === "left" && renderLinuxCluster("left")}
			{IS_MAC && <div className="h-9 w-18 shrink-0" aria-hidden="true" />}
			{/* Toolbar button group, sidebar/back/forward/help wrapped in
                            a p-1 (4px) padded flex container so no button takes the
                            full 36px bar height; the 4px padding gives breathing room
                            top/bottom/left/right, and gap-1 separates the buttons.
                            Hidden entirely in minimal chrome (status screens):
                            nothing up here is usable without a page behind it. */}
			{!minimalChrome && (
				<div className="flex items-center gap-1 p-1">
					{/* ONB-3: the onboarding wizard is a focused, mandatory flow —
				    the sidebar is hidden entirely for that page, so the toggle
				    must not render (toggling would collapse a sidebar that
				    isn't visible and desync the persisted rail state). */}
					{currentPage !== "onboarding" && (
						<HotkeyTooltip
							label={t("a11y.toggleSidebar")}
							keys={SHORTCUTS.toggleSidebar.keys}
						>
							<ToolbarButton
								onClick={onToggleSidebar}
								ariaLabel={t("a11y.toggleSidebarWithShortcut", {
									shortcut: SHORTCUTS.toggleSidebar.keys,
								})}
								ariaKeyshortcuts={SHORTCUTS.toggleSidebar.ariaKeyshortcuts}
							>
								<HugeiconsIcon
									icon={PanelLeftIcon}
									strokeWidth={2}
									className="h-4 w-4"
								/>
							</ToolbarButton>
						</HotkeyTooltip>
					)}

					{/* Back/Forward navigation */}
					<NavChevronButton
						tooltipLabel={t("titleBar.back")}
						shortcutKeys={SHORTCUTS.navBack.keys}
						ariaLabel={t("a11y.goBack")}
						onClick={onGoBack}
						disabled={!canGoBack}
						path="M10 12L6 8L10 4"
					/>
					<NavChevronButton
						tooltipLabel={t("titleBar.forward")}
						shortcutKeys={SHORTCUTS.navForward.keys}
						ariaLabel={t("a11y.goForward")}
						onClick={onGoForward}
						disabled={!canGoForward}
						path="M6 4L10 8L6 12"
					/>

					{/*discoverable "?" help button. Mirrors the "?"
                            keyboard shortcut (handled in App.tsx) so mouse users and
                            AT users can also open the keyboard-shortcut overlay. */}
					<HotkeyTooltip
						label={t("help.openHelp")}
						keys={SHORTCUTS.openHelp.keys}
					>
						<ToolbarButton
							onClick={onOpenHelp}
							ariaLabel={t("help.openHelp")}
							ariaKeyshortcuts={SHORTCUTS.openHelp.ariaKeyshortcuts}
						>
							<span
								aria-hidden
								className="text-xs-plus font-medium leading-none"
							>
								?
							</span>
						</ToolbarButton>
					</HotkeyTooltip>
				</div>
			)}

			{/* Per-page controls, centered in the middle of the title bar.
                            Global search renders on the searchable pages (history,
                            templates, vocabulary, settings*); Models swaps in the
                            Local/Cloud segmented control; Analytics swaps in the
                            time-range control (both same middle strip, so the
                            control stays put while the page scrolls). On other
                            pages the flex-1 spacer keeps the toolbar left +
                            controls right. Suppressed entirely while
                            showPageControls is false (boot/restart/error screens
                            own the main column, so route-matched controls would
                            be dead buttons above a status card). */}
			<div className="flex min-w-0 flex-1 items-center justify-center p-1 h-full">
				{currentPage && showPageControls ? (
					<>
						<GlobalSearchBar currentPage={currentPage} />
						<ModelsTabSwitcher currentPage={currentPage} />
						<AnalyticsRangeSwitcher currentPage={currentPage} />
					</>
				) : null}
			</div>

			{/* Theme control, icon-only, in its OWN p-1 (4px) padded
                            container (separate from the toolbar group). It sits on
                            the right edge of the bar, immediately LEFT of the window
                            controls. The 4px padding insets the 24px button from the
                            full bar height AND keeps its hover background from
                            touching the window-control cluster (e.g. the Linux
                            minimize circle, whose always-visible background the theme
                            hover would otherwise collide with). On macOS the native
                            traffic lights occupy the left gutter and there are no
                            window controls, the button anchors the bar's right edge
                            instead. The accessible name + hover title carry the
                            current→next theme info (no visible text). */}
			<div className="flex items-center p-1">
				<ThemeSwitch
					themeMode={themeMode}
					onThemeChange={onThemeChange}
					className={cn(
						"no-drag press-scale h-6 w-6 rounded-lg",
						"text-muted-foreground hover:text-foreground",
					)}
				/>
			</div>

			{/* Window controls, Windows/Linux only. macOS uses the native
                            traffic lights (titleBarStyle: 'hiddenInset' in the main
                            window), so rendering Windows-style buttons there would
                            duplicate the chrome with wrong-style buttons.
                            Windows: the fixed 46×36 edge-to-edge trio, the layout is
                            NOT user-configurable on Windows (native convention).
                            Linux: the resolved cluster (side/visibility/shape from
                            the linux_window_buttons setting + system snapshot); the
                            LEFT-side variant renders before the toolbar group (see
                            the mirror block at the top of the bar). */}
			{IS_WIN && (
				<div
					className={cn(
						// ms-1 separates the cluster from the theme switch —
						// 4px here + the theme wrapper's 4px padding = an
						// 8px icon-to-icon gap. Windows square buttons are
						// edge-to-edge (no gap).
						"ms-1 flex items-center",
					)}
				>
					<TitleBarButton
						onClick={handleMinimize}
						ariaLabel={t("titleBar.minimize")}
					>
						<MinimizeIcon />
					</TitleBarButton>
					<TitleBarButton
						onClick={handleToggleMaximize}
						ariaLabel={
							isMaximized ? t("titleBar.restore") : t("titleBar.maximize")
						}
					>
						{isMaximized ? <RestoreIcon /> : <MaximizeIcon />}
					</TitleBarButton>
					<TitleBarButton
						onClick={handleClose}
						ariaLabel={t("titleBar.close")}
						// Red close hover is a WINDOWS convention (the native
						// close button turns solid red); Linux never passes
						// the "close" variant.
						variant="close"
					>
						<CloseIcon />
					</TitleBarButton>
				</div>
			)}
			{IS_LINUX && linuxButtons.side === "right" && renderLinuxCluster("right")}
		</div>
	);
}

//wrap in React.memo so stable callbacks from App.tsx can
// short-circuit re-renders when no props have changed.
export const TitleBar = memo(TitleBarInner);
