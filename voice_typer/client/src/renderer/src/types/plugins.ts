// Plugin payload types, mirroring the `get_plugins` response envelope
// (`{ type: "plugins", data: [...] }`, see the backend plugin handlers).
// One canonical definition shared by the page and its hook, so the wire
// shape is declared exactly once.

/** One discovered plugin. Settings are NOT plugin-owned: the two shared
 *  settings live in the main config and are written with `set_config`. */
export interface PluginInfo {
	id: string;
	name: string;
	description: string;
	vendor: string;
	/** Plugin-declared icon identifier (e.g. `google`); may be empty.
	    Resolved to a bundled asset when one ships for that id (see
	    `pages/plugins/lib/pluginIcon`), otherwise rendered as an initial
	    tile. Never used as a filesystem path. */
	icon: string;
	/** True when this plugin currently owns dictation. */
	active: boolean;
}

/** Normalize one wire entry into a {@link PluginInfo}. Manifests are
 *  plugin-authored (external files), so every field is validated here
 *  rather than trusted: one malformed plugin must not break the list.
 */
export function toPluginInfo(value: unknown): PluginInfo | null {
	if (typeof value !== "object" || value === null) return null;
	const raw = value as Record<string, unknown>;
	const id = typeof raw.id === "string" ? raw.id : "";
	if (!id) return null;
	return {
		id,
		name: typeof raw.name === "string" && raw.name ? raw.name : id,
		description: typeof raw.description === "string" ? raw.description : "",
		vendor: typeof raw.vendor === "string" ? raw.vendor : "",
		icon: typeof raw.icon === "string" ? raw.icon : "",
		active: raw.active === true,
	};
}

/** Normalize the whole `get_plugins` payload, dropping unusable entries. */
export function toPluginList(value: unknown): PluginInfo[] {
	if (!Array.isArray(value)) return [];
	const plugins: PluginInfo[] = [];
	for (const entry of value) {
		const plugin = toPluginInfo(entry);
		if (plugin) plugins.push(plugin);
	}
	return plugins;
}

/**
 * The `get_plugins` response envelope: whether the Plugins surface is
 * available on this install at all, plus the installed plugins.
 *
 * `available` is the developer gate. A shipped build answers false, which
 * is what hides the Plugins nav item. It is deliberately independent of the
 * plugin array: "you may not see this" and "nothing is installed" are
 * different states and must not collapse into an empty list.
 */
export interface PluginCatalog {
	available: boolean;
	plugins: PluginInfo[];
}

/** Normalize the wire envelope. An unrecognized shape reads as unavailable. */
export function toPluginCatalog(value: unknown): PluginCatalog {
	if (typeof value !== "object" || value === null) {
		return { available: false, plugins: [] };
	}
	const raw = value as Record<string, unknown>;
	return {
		available: raw.available === true,
		plugins: toPluginList(raw.plugins),
	};
}
