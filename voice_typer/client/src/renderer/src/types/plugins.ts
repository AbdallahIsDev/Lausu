// Plugin payload types, mirroring the `get_plugins` response envelope
// (`{ type: "plugins", data: [...] }`, see the backend plugin handlers).
// One canonical definition shared by the list page, the detail page and
// their hook, so the wire shape is declared exactly once.

/** Declared value type of a single plugin setting. */
export type PluginSettingType = "bool" | "int" | "float" | "string" | "enum";

/** One setting a plugin declares in its manifest. */
export interface PluginSettingSpec {
	key: string;
	type: PluginSettingType;
	label: string;
	description: string;
	default: unknown;
	/** Allowed values for `enum` settings. */
	choices?: string[];
	min?: number;
	max?: number;
}

/** One discovered plugin. */
export interface PluginInfo {
	id: string;
	name: string;
	description: string;
	vendor: string;
	/** Plugin-declared icon identifier; may be empty. Rendered as an
	    initial tile, never as an image asset (no bundled icon exists). */
	icon: string;
	/** True when this plugin currently owns dictation. */
	active: boolean;
	settings: PluginSettingSpec[];
	/** Current values, keyed by `settings[].key`. */
	values: Record<string, unknown>;
}

/** Settings type is a closed set; an unknown value from the wire falls
    back to `string` so a newer plugin manifest cannot break the page. */
export function toPluginSettingType(value: unknown): PluginSettingType {
	switch (value) {
		case "bool":
		case "int":
		case "float":
		case "enum":
			return value;
		default:
			return "string";
	}
}

function toPluginSettings(value: unknown): PluginSettingSpec[] {
	if (!Array.isArray(value)) return [];
	const specs: PluginSettingSpec[] = [];
	for (const entry of value) {
		if (typeof entry !== "object" || entry === null) continue;
		const raw = entry as Record<string, unknown>;
		const key = typeof raw.key === "string" ? raw.key : "";
		if (!key) continue;
		specs.push({
			key,
			type: toPluginSettingType(raw.type),
			label: typeof raw.label === "string" ? raw.label : key,
			description: typeof raw.description === "string" ? raw.description : "",
			default: raw.default,
			choices: Array.isArray(raw.choices)
				? raw.choices.filter((c): c is string => typeof c === "string")
				: undefined,
			min: typeof raw.min === "number" ? raw.min : undefined,
			max: typeof raw.max === "number" ? raw.max : undefined,
		});
	}
	return specs;
}

/**
 * Normalize one wire entry into a {@link PluginInfo}. Manifests are
 * plugin-authored (external files), so every field is validated here
 * rather than trusted: one malformed plugin must not break the list.
 */
export function toPluginInfo(value: unknown): PluginInfo | null {
	if (typeof value !== "object" || value === null) return null;
	const raw = value as Record<string, unknown>;
	const id = typeof raw.id === "string" ? raw.id : "";
	if (!id) return null;
	const values =
		typeof raw.values === "object" && raw.values !== null
			? (raw.values as Record<string, unknown>)
			: {};
	return {
		id,
		name: typeof raw.name === "string" && raw.name ? raw.name : id,
		description: typeof raw.description === "string" ? raw.description : "",
		vendor: typeof raw.vendor === "string" ? raw.vendor : "",
		icon: typeof raw.icon === "string" ? raw.icon : "",
		active: raw.active === true,
		settings: toPluginSettings(raw.settings),
		values,
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

/**
 * Effective value of one setting: the plugin's stored value when present,
 * otherwise its declared default. Keeps every control's starting state
 * consistent whether or not the plugin has persisted a value yet.
 */
export function settingValue(
	plugin: PluginInfo,
	spec: PluginSettingSpec,
): unknown {
	const stored = plugin.values[spec.key];
	return stored === undefined ? spec.default : stored;
}
