import { useCallback, useEffect } from "react";
import { A11yLiveRegions } from "@/components/common/A11yLiveRegions";
import ConsentGateDialog from "@/components/consent/ConsentGateDialog";
import { HelpOverlay } from "@/components/help/HelpOverlay";
import { configHotkeyLabels } from "@/components/hotkey/hotkey-utils";
import { ConnectionStatusScreen } from "@/components/layout/ConnectionStatusScreen";
import { Sidebar } from "@/components/layout/Sidebar";
import { TitleBar } from "@/components/layout/TitleBar";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useAsrBackendDisabledToast } from "@/hooks/useAsrBackendDisabledToast";
import { useAsrBackendLoadToast } from "@/hooks/useAsrBackendLoadToast";
import { useCloudFallbackToast } from "@/hooks/useCloudFallbackToast";
import { useConnectingProgress } from "@/hooks/useConnectingProgress";
import { useConnection } from "@/hooks/useConnection";
import { useConnectionToasts } from "@/hooks/useConnectionToasts";
import { useConsentRequiredEvent } from "@/hooks/useConsentRequiredEvent";
import { useDeviceLostToast } from "@/hooks/useDeviceLostToast";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useGlobalKeyboardShortcuts } from "@/hooks/useGlobalKeyboardShortcuts";
import { useHelpOverlayShortcut } from "@/hooks/useHelpOverlayShortcut";
import { useHistoryIntegrityToast } from "@/hooks/useHistoryIntegrityToast";
import { useLastResortUnloadedToast } from "@/hooks/useLastResortUnloadedToast";
import { useLinuxWindowButtons } from "@/hooks/useLinuxWindowButtons";
import { useLlmPolishFailedToast } from "@/hooks/useLlmPolishFailedToast";
import { useMicPermissionRevokedToast } from "@/hooks/useMicPermissionRevokedToast";
import { useMicrophoneDisconnectedToast } from "@/hooks/useMicrophoneDisconnectedToast";
import { useNavigateEvent } from "@/hooks/useNavigateEvent";
import { useNavigation } from "@/hooks/useNavigation";
import { useNetworkOnline } from "@/hooks/useNetworkOnline";
import { useOnboardingComplete } from "@/hooks/useOnboardingComplete";
import { useOnboardingRouteGuard } from "@/hooks/useOnboardingRouteGuard";
import { usePasteDeferredToast } from "@/hooks/usePasteDeferredToast";
import { usePasteFailedToast } from "@/hooks/usePasteFailedToast";
import { usePython } from "@/hooks/usePython";
import { useRendererHeartbeat } from "@/hooks/useRendererHeartbeat";
import { useRouteChangeFocus } from "@/hooks/useRouteChangeFocus";
import { useSidebarAutoCollapse } from "@/hooks/useSidebarAutoCollapse";
import { useSoundFeedback } from "@/hooks/useSoundFeedback";
import { useTheme } from "@/hooks/useTheme";
import { useTrayFallbackToast } from "@/hooks/useTrayFallbackToast";
import { useWindowMaximized } from "@/hooks/useWindowMaximized";
import { getLocale, setLocale, useT } from "@/i18n/i18n";
import { cn } from "@/lib/utils";
import { PageSwitch } from "@/router/PageSwitch";
import { prefetchRouteChunks } from "@/router/prefetch";
import { useAppStore } from "@/stores/appStore";
import type { WindowBridge } from "@/types/ipc";

export default function App() {
	const t = useT();

	useNetworkOnline();

	const {
		currentPage,
		navigate,
		replace,
		goBack,
		goForward,
		canGoBack,
		canGoForward,
	} = useNavigation();

	useOnboardingRouteGuard({ currentPage, replace });

	const hotkeyFromConfig = useAppStore((s) => s.config?.hotkey);
	const repasteHotkeyFromConfig = useAppStore((s) => s.config?.repaste_hotkey);

	// C-BG-1: if the window is still hidden after a grace period with
	// Microphone mounted (close-to-tray / hidden autostart), leave for
	// Home so live mic monitoring never runs in the background.
	useEffect(() => {
		if (typeof document === "undefined") return;
		if (currentPage !== "microphone") return;
		if (document.visibilityState === "visible") return;
		let cancelled = false;
		const timer = setTimeout(() => {
			if (
				!cancelled &&
				typeof document !== "undefined" &&
				document.visibilityState !== "visible"
			) {
				replace("home");
			}
		}, 900);
		const onVisible = () => {
			if (document.visibilityState === "visible") {
				cancelled = true;
				clearTimeout(timer);
				document.removeEventListener("visibilitychange", onVisible);
			}
		};
		document.addEventListener("visibilitychange", onVisible);
		return () => {
			cancelled = true;
			clearTimeout(timer);
			document.removeEventListener("visibilitychange", onVisible);
		};
	}, [currentPage, replace]);

	useDocumentTitle({ currentPage, t });

	// Push the restored locale to native dialogs + the Python tray.
	useEffect(() => {
		setLocale(getLocale());
	}, []);

	useEffect(() => {
		prefetchRouteChunks();
	}, []);

	useRouteChangeFocus(currentPage);
	useSoundFeedback();

	const { showHelpOverlay, openHelp, closeHelp } = useHelpOverlayShortcut();
	const { sidebarCollapsed, setSidebarCollapsed } = useSidebarAutoCollapse();
	const { call } = usePython();

	const {
		themeMode,
		handleThemeChange,
		reloadThemeFromConfig,
		textSize,
		setTextSize,
	} = useTheme(call);
	const { recordingState, connectionStatus, lastError, handleRetryConnection } =
		useConnection({ call, currentPage, navigate });

	// Nav only when the backend is usable (and not in onboarding).
	const sidebarVisible =
		currentPage !== "onboarding" && connectionStatus === "connected";

	const prevConnectionRef = useConnectionToasts({
		connectionStatus,
		reloadThemeFromConfig,
		t,
	});

	const bridge =
		typeof window !== "undefined"
			? (window.window_ as WindowBridge)
			: undefined;
	const isMaximized = useWindowMaximized(bridge);

	useGlobalKeyboardShortcuts({
		navigate,
		textSize,
		setTextSize,
		call,
		t,
		setSidebarCollapsed,
	});

	useNavigateEvent({ navigate });
	useRendererHeartbeat();
	usePasteFailedToast(t);
	useDeviceLostToast(t, () => navigate("microphone"));
	useLlmPolishFailedToast(t);
	useAsrBackendDisabledToast(t, () => navigate("models"));
	useAsrBackendLoadToast(t, () => navigate("models"));
	useMicrophoneDisconnectedToast(t, () => navigate("microphone"));
	useMicPermissionRevokedToast(t);
	useTrayFallbackToast(t);
	useCloudFallbackToast(t);
	useHistoryIntegrityToast(t);
	usePasteDeferredToast(t);
	useLastResortUnloadedToast(t, () => navigate("models"));
	useConsentRequiredEvent({ call });

	const connectingProgress = useConnectingProgress(connectionStatus);

	const handleToggleSidebar = useCallback(
		() => setSidebarCollapsed((c) => !c),
		[setSidebarCollapsed],
	);

	const handleOnboardingComplete = useOnboardingComplete({
		navigate,
		call,
		reloadThemeFromConfig,
	});

	const { dictationLabel, repasteLabel } = configHotkeyLabels({
		hotkey: hotkeyFromConfig,
		repaste_hotkey: repasteHotkeyFromConfig,
	});

	const linuxWindowButtons = useLinuxWindowButtons();

	// Window radius lives on the native Tauri shell (html.is-maximized);
	// the React shell is a flat full-bleed column.
	return (
		<TooltipProvider delayDuration={200} skipDelayDuration={500}>
			<a
				href="#main-content"
				className="sr-only focus:not-sr-only focus:fixed focus:inset-s-4 focus:top-4 focus:z-100 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
			>
				{t("a11y.skipToMain")}
			</a>
			<div className="flex h-screen flex-col overflow-hidden bg-sidebar font-sans text-foreground">
				<TitleBar
					onToggleSidebar={handleToggleSidebar}
					onGoBack={goBack}
					onGoForward={goForward}
					canGoBack={canGoBack}
					canGoForward={canGoForward}
					isMaximized={isMaximized}
					onOpenHelp={openHelp}
					themeMode={themeMode}
					onThemeChange={handleThemeChange}
					linuxWindowButtons={linuxWindowButtons}
					currentPage={currentPage}
				/>
				<div className="flex min-h-0 flex-1">
					{sidebarVisible && (
						<Sidebar
							currentPage={currentPage}
							onNavigate={navigate}
							collapsed={sidebarCollapsed}
						/>
					)}

					{/* dir=rtl-safe: pin LTR when the sidebar is hidden so the
					    main column does not jump sides mid-onboarding/boot. */}
					<div
						className="flex min-w-0 flex-1 flex-col"
						dir={sidebarVisible ? undefined : "ltr"}
					>
						<main
							id="main-content"
							tabIndex={-1}
							// Inset frame only beside the sidebar; full-bleed when
							// chrome is hidden (boot/error cards).
							className={cn(
								"flex-1 overflow-y-auto bg-background focus:outline-none",
								sidebarVisible && "rounded-l-lg border border-border/8",
							)}
							style={{ scrollbarGutter: "stable" }}
						>
							{connectionStatus === "connected" ? (
								<PageSwitch
									page={currentPage}
									navigate={navigate}
									onOnboardingComplete={handleOnboardingComplete}
								/>
							) : (
								<ConnectionStatusScreen
									status={connectionStatus}
									lastError={lastError}
									onRetry={handleRetryConnection}
									connectingProgress={connectingProgress}
								/>
							)}
						</main>
					</div>
				</div>
				<Toaster />
				<ConsentGateDialog />
				<HelpOverlay
					open={showHelpOverlay}
					onClose={closeHelp}
					dictationLabel={dictationLabel}
					repasteLabel={repasteLabel}
				/>
				<A11yLiveRegions
					recordingState={recordingState}
					currentPage={currentPage}
					connectionStatus={connectionStatus}
					prevConnectionRef={prevConnectionRef}
				/>
			</div>
		</TooltipProvider>
	);
}
