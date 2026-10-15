import { Suspense } from "react";
import { RouteSkeleton } from "@/components/feedback/skeletons";
import { Button } from "@/components/ui/button";
import { useT } from "@/i18n/i18n";
// Route-level code splitting. Home is the default landing page
// and stays eagerly imported so first paint is fast. The other 9 pages
// (History, Templates, Vocabulary, Models, Microphone, Analytics,
// Settings, AboutAndPrivacy, Onboarding) are loaded on demand via
// React.lazy so Vite emits per-route chunks and the initial JS payload
// only carries the Home page's transitive deps. Each lazy component
// resolves to the page module's default export. The lazy-import
// REGISTRY (the single `PAGE_LOADERS` map this switch and
// router/prefetch.ts both consume) lives in router/pageLoaders.ts.
// `<RouteChunk>` renders a WARM chunk (idle warm-up or sidebar hover)
// synchronously, so the Suspense fallback below only appears for a
// genuinely cold chunk — see router/RouteChunk.tsx.
import Home from "@/pages/Home";
import type { Page } from "@/types/ipc";

import { RouteChunk } from "./RouteChunk";

function RouteSuspenseFallback() {
	return <RouteSkeleton />;
}

interface PageSwitchProps {
	/** The active route (from useNavigation). */
	page: Page;
	/** Navigate action, used only by the page-not-found fallback. */
	navigate: (page: Page) => void;
	/** Onboarding-completion callback passed through to the wizard. */
	onOnboardingComplete: () => void;
}

export function PageSwitch({
	page,
	navigate,
	onOnboardingComplete,
}: PageSwitchProps) {
	const t = useT();

	const renderPage = () => {
		switch (page) {
			case "home":
				return <Home />;
			case "history":
				return <RouteChunk page="history" />;
			case "templates":
				return <RouteChunk page="templates" />;
			case "vocabulary":
				return <RouteChunk page="vocabulary" />;
			case "media":
				return <RouteChunk page="media" />;
			case "models":
				return <RouteChunk page="models" />;
			case "microphone":
				return <RouteChunk page="microphone" />;
			case "plugins":
				return <RouteChunk page="plugins" />;
			case "analytics":
				return <RouteChunk page="analytics" />;
			// The Settings surface is HUB + nested section pages. "settings"
			// renders the hub (one card whose rows open the section pages —
			// see SettingsHub + settingsSections.ts); each section literal
			// renders `<SettingsPage page={...} />` with exactly that
			// domain's cards. All literals resolve to the same lazy chunk
			// (`page` is forwarded to the component, see RouteChunk).
			case "settings":
				return <RouteChunk page="settings" />;
			case "settingsGeneral":
				return <RouteChunk page="settingsGeneral" />;
			case "settingsOverlay":
				return <RouteChunk page="settingsOverlay" />;
			case "settingsHotkeys":
				return <RouteChunk page="settingsHotkeys" />;
			case "settingsTranscription":
				return <RouteChunk page="settingsTranscription" />;
			case "settingsAudio":
				return <RouteChunk page="settingsAudio" />;
			case "settingsAppearance":
				return <RouteChunk page="settingsAppearance" />;
			case "settingsPrivacy":
				return <RouteChunk page="settingsPrivacy" />;
			case "settingsAdvanced":
				return <RouteChunk page="settingsAdvanced" />;
			case "aboutAndPrivacy":
				return <RouteChunk page="aboutAndPrivacy" />;
			case "onboarding":
				return (
					<RouteChunk page="onboarding" onComplete={onOnboardingComplete} />
				);
			default:
				// Page-not-found fallback now resolves via i18n
				// (`app.pageNotFoundTitle` / `app.pageNotFoundDescription`)
				// so non-English users see the fallback in their locale.
				// Both keys ship translated across all 8 locales.
				return (
					<div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
						<p className="text-sm font-medium text-foreground">
							{t("app.pageNotFoundTitle")}
						</p>
						<p className="text-xs text-muted-foreground">
							{t("app.pageNotFoundDescription", {
								page: String(page),
							})}
						</p>
						<Button variant="default" onClick={() => navigate("home")}>
							{t("app.goHome")}
						</Button>
					</div>
				);
		}
	};

	return (
		<Suspense fallback={<RouteSuspenseFallback />}>{renderPage()}</Suspense>
	);
}
