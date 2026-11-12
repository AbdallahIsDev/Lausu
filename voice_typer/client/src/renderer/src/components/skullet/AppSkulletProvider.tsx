import type { ReactNode } from "react";
import { SkulletProvider } from "skullet/react";
import { useThemeStore } from "@/hooks/theme/themeStore";

// Measured skeletons for every async page. The provider fans out one
// shimmer (document clock) and one reveal to every `<Skeleton>` below
// it, so mounting the provider once at the app root keeps every page
// in step. Mode follows the app theme store (light/dark/system);
// presets only remap tokens, Skullet only needs the colour scheme.
// Reveal stays the default `smart` (fast loads show instantly, the
// rest crossfade per piece). Text spans ascender → descender, the
// full line box, matching the detail level the old page-mirroring
// blocks reserved by hand.
export function AppSkulletProvider({ children }: { children: ReactNode }) {
	const themeMode = useThemeStore((s) => s.themeMode);
	return (
		<SkulletProvider
			mode={themeMode}
			reveal="smart"
			theme={{
				animation: "shimmer",
				speed: "slow",
				text: { top: "ascender", bottom: "descender" },
			}}
		>
			{children}
		</SkulletProvider>
	);
}
