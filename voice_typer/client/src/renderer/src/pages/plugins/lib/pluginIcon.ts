// This file exists so that a plugin manifest's `icon` IDENTIFIER resolves to a
// bundled asset URL. Manifests are plugin-authored files, so an identifier is
// never trusted as a path — only the ids listed here resolve; anything else
// falls back to the card's initial tile.

/** Declared icon id → asset served from `src/renderer/public`. */
const PLUGIN_ICON_SRC: Record<string, string> = {
	google: "/plugin-icons/google.svg",
};

/**
 * URL of the bundled icon for a plugin's declared identifier, or `null` when
 * no asset ships for it (the caller then renders the name's initial).
 */
export function pluginIconSrc(icon: string): string | null {
	if (!icon) return null;
	return PLUGIN_ICON_SRC[icon] ?? null;
}
