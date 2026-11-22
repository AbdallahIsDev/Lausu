// Owns the plugin list, plugin activation and the TWO shared plugin settings
// for the Plugins page. All three are plain fields in the main config:
// `active_plugin`, `plugin_visible`, `plugin_notify`. One write path
// (`set_config`), one refresh path (`config_changed`), one authority.
//
// The catalog itself (the `get_plugins` round-trip and the developer
// availability gate) belongs to `@/hooks/usePluginCatalog`, which the shell
// also reads; this hook is the page-side view of that shared cache.

import { useCallback, useEffect, useRef, useState } from "react";
import { useLatestRef } from "@/hooks/useLatestRef";
import { loadPluginCatalog } from "@/hooks/usePluginCatalog";
import { usePython, usePythonEvent } from "@/hooks/usePython";
import { t } from "@/i18n/i18n";
import { type PrefetchCall, runPrefetchFlight } from "@/lib/snapshotCache";
import { useAppStore } from "@/stores/appStore";
import type { LausuConfig } from "@/types/config";
import type { PluginInfo } from "@/types/plugins";

// Module-level cache, mirrors the microphone page's `_cachedMicrophones`:
// the list survives unmount so re-visiting does not flash a skeleton.
let _cachedPlugins: PluginInfo[] | null = null;

// Sidebar-hover prefetch bookkeeping (C-CACHE-4). `_prefetchedAt` is set
// ONLY by `prefetchPluginsData`, so repeated hovers stay free while an
// ordinary navigation keeps the mount reload it always had.
let _prefetchedAt = 0;
const PLUGINS_PREFETCH_KEY = "plugins.list";
export const PLUGINS_CACHE_TTL_MS = 30_000;

/** Test-only reset for the module-level list cache + prefetch stamp
 *  (module state outlives a test file's `beforeEach` otherwise). */
export function __resetPluginsPrefetchForTests(): void {
	_cachedPlugins = null;
	_prefetchedAt = 0;
}

/**
 * Warm the Plugins page's list on sidebar hover/focus (C-CACHE-4):
 * short-circuits on a fresh cache, shares one in-flight request across
 * repeated hovers, and stays best-effort — a failure leaves the cache
 * untouched and the mount load stays authoritative.
 */
export function prefetchPluginsData(call: PrefetchCall): Promise<void> {
	if (
		_cachedPlugins !== null &&
		_prefetchedAt > 0 &&
		Date.now() - _prefetchedAt < PLUGINS_CACHE_TTL_MS
	) {
		return Promise.resolve();
	}
	return runPrefetchFlight(PLUGINS_PREFETCH_KEY, async () => {
		const catalog = await loadPluginCatalog(call);
		if (!Array.isArray(catalog.plugins)) return;
		_cachedPlugins = catalog.plugins;
		_prefetchedAt = Date.now();
	});
}

export type SharedPluginSettingKey = "visible" | "notify";

export interface SharedPluginSettings {
	visible: boolean;
	notify: boolean;
}

const CONFIG_FIELD: Record<
	SharedPluginSettingKey,
	"plugin_visible" | "plugin_notify"
> = {
	visible: "plugin_visible",
	notify: "plugin_notify",
};

function sharedFromConfig(config: LausuConfig): SharedPluginSettings {
	return {
		visible: config.plugin_visible !== false,
		notify: config.plugin_notify !== false,
	};
}

export interface UsePluginsResult {
	plugins: PluginInfo[];
	/** Id of the plugin that owns dictation ("" = built-in local model). */
	activePluginId: string;
	shared: SharedPluginSettings;
	loading: boolean;
	loadError: string | null;
	loadPlugins: (isCancelled?: () => boolean) => Promise<void>;
	setActivePlugin: (pluginId: string) => void;
	/** Persist one shared setting through `set_config`; false on refusal. */
	setSharedSetting: (
		key: SharedPluginSettingKey,
		value: boolean,
	) => Promise<boolean>;
}

export function usePlugins(): UsePluginsResult {
	const { call } = usePython();
	// The shared store is updated by `config_changed` even while this page is
	// unmounted. The module list cache is only an instant-render hint: never
	// seed identity from it, or a switch that happened during navigation
	// reappears as the old plugin on remount.
	const storeActivePlugin = useAppStore((s) => s.config?.active_plugin);
	const storeVisible = useAppStore((s) => s.config?.plugin_visible);
	const storeNotify = useAppStore((s) => s.config?.plugin_notify);
	const [plugins, setPlugins] = useState<PluginInfo[]>(_cachedPlugins ?? []);
	const [activePluginId, setActivePluginId] = useState<string>(
		typeof storeActivePlugin === "string"
			? storeActivePlugin
			: (_cachedPlugins?.find((p) => p.active)?.id ?? ""),
	);
	const [shared, setShared] = useState<SharedPluginSettings>({
		visible: storeVisible ?? true,
		notify: storeNotify ?? true,
	});
	const [loading, setLoading] = useState(_cachedPlugins === null);
	const [loadError, setLoadError] = useState<string | null>(null);

	// Follow the shared snapshot on every change, including pushes that
	// landed while the page was away. Identity stays canonical: one config.
	useEffect(() => {
		if (typeof storeActivePlugin === "string")
			setActivePluginId(storeActivePlugin);
	}, [storeActivePlugin]);
	useEffect(() => {
		setShared({ visible: storeVisible ?? true, notify: storeNotify ?? true });
	}, [storeVisible, storeNotify]);

	// callRef mirror: `loadPlugins` must keep a STABLE identity so the mount
	// effect below does not re-fire every time `call` is recreated.
	const callRef = useLatestRef(call);

	// biome-ignore lint/correctness/useExhaustiveDependencies: callRef is a useLatestRef mirror; reading .current in a stale closure is the hook's documented contract, .current must NOT become a dep
	const loadPlugins = useCallback(async (isCancelled?: () => boolean) => {
		try {
			const [catalog, config] = await Promise.all([
				loadPluginCatalog(callRef.current),
				callRef.current<LausuConfig>("get_config"),
			]);
			if (isCancelled?.()) return;
			const list = catalog.plugins;
			_cachedPlugins = list;
			// The backend already marks the active plugin in each entry,
			// but config is the canonical store, so it wins when they
			// disagree.
			setPlugins(list);
			setActivePluginId(
				typeof config.active_plugin === "string" ? config.active_plugin : "",
			);
			setShared(sharedFromConfig(config));
			setLoadError(null);
		} catch (err) {
			if (isCancelled?.()) return;
			console.error("[renderer:usePlugins] Failed to load plugins:", err);
			setLoadError(
				err instanceof Error ? err.message : t("plugins.loadFailedDescription"),
			);
		} finally {
			if (!isCancelled?.()) setLoading(false);
		}
	}, []);

	// Mount load, skipped when the module cache already holds a list (page
	// re-entry). `isCancelled` keeps the in-flight `setX` calls off an
	// unmounted tree.
	useEffect(() => {
		if (_cachedPlugins !== null) return;
		let cancelled = false;
		void loadPlugins(() => cancelled);
		return () => {
			cancelled = true;
		};
	}, [loadPlugins]);

	// Reconnect refetch: a mount during a backend outage (or a slow
	// startup model load that trips the 5s `get_config` budget) leaves
	// this page on its error state with an empty module cache. Every
	// reconnect path in `useConnection` lands `connectionStatus` on
	// "connected" without touching this hook, so refetch exactly on the
	// disconnected/transient → connected transition while the cache is empty.
	const connectionStatus = useAppStore((s) => s.connectionStatus);
	const prevStatusRef = useRef(connectionStatus);
	useEffect(() => {
		const prev = prevStatusRef.current;
		prevStatusRef.current = connectionStatus;
		if (
			connectionStatus === "connected" &&
			prev !== "connected" &&
			_cachedPlugins === null
		) {
			let cancelled = false;
			void loadPlugins(() => cancelled);
			return () => {
				cancelled = true;
			};
		}
		return undefined;
	}, [connectionStatus, loadPlugins]);

	// Every plugin field is canonical config, so one subscription keeps the
	// list, the activation switches and the shared controls in sync no matter
	// which surface changed them (Settings, tray, another client).
	usePythonEvent(
		"config_changed",
		useCallback((): (() => void) | undefined => {
			void (async () => {
				try {
					const config = await call<LausuConfig>("get_config");
					const id =
						typeof config.active_plugin === "string"
							? config.active_plugin
							: "";
					setActivePluginId(id);
					setPlugins((prev) =>
						prev.map((p) => ({ ...p, active: p.id === id })),
					);
					setShared(sharedFromConfig(config));
				} catch (err) {
					console.warn(
						"[renderer:usePlugins] Failed to refresh config on config_changed:",
						err,
					);
				}
			})();
			return undefined;
		}, [call]),
	);

	// Optimistic flip with rollback: the card toggle is now the primary
	// activation control, so a rejected `set_config` must not leave the UI
	// claiming a plugin owns dictation when it does not.
	const setActivePlugin = useCallback(
		(pluginId: string) => {
			const previous = activePluginId;
			setActivePluginId(pluginId);
			setPlugins((prev) =>
				prev.map((p) => ({ ...p, active: p.id === pluginId })),
			);
			call("set_config", { active_plugin: pluginId }).catch((err: unknown) => {
				console.warn(
					"[renderer:usePlugins] set_config active_plugin failed:",
					err,
				);
				setActivePluginId(previous);
				setPlugins((prev) =>
					prev.map((p) => ({ ...p, active: p.id === previous })),
				);
			});
		},
		[activePluginId, call],
	);

	const setSharedSetting = useCallback(
		(key: SharedPluginSettingKey, value: boolean): Promise<boolean> => {
			const previous = shared[key];
			setShared((prev) => ({ ...prev, [key]: value }));
			return call("set_config", { [CONFIG_FIELD[key]]: value })
				.then(() => true)
				.catch((err: unknown) => {
					console.warn(
						"[renderer:usePlugins] set_config shared plugin setting failed:",
						err,
					);
					setShared((prev) => ({ ...prev, [key]: previous }));
					return false;
				});
		},
		[call, shared],
	);

	return {
		// Card status is derived from the canonical id, never from a flag
		// frozen into the module cache at first load.
		plugins: plugins.map((p) => ({ ...p, active: p.id === activePluginId })),
		activePluginId,
		shared,
		loading,
		loadError,
		loadPlugins,
		setActivePlugin,
		setSharedSetting,
	};
}
