// Owns the plugin list + active-plugin config for the Plugins pages: the
// cache that survives page navigations (so returning from a detail page
// renders the list instantly), the mount load, and the `config_changed`
// subscription that keeps the active-plugin flag fresh after a toggle.
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

export interface UsePluginsResult {
	plugins: PluginInfo[];
	/** Id of the plugin that owns dictation ("" = built-in local model). */
	activePluginId: string;
	loading: boolean;
	loadError: string | null;
	loadPlugins: (isCancelled?: () => boolean) => Promise<void>;
	setActivePlugin: (pluginId: string) => void;
}

export function usePlugins(): UsePluginsResult {
	const { call } = usePython();
	const [plugins, setPlugins] = useState<PluginInfo[]>(_cachedPlugins ?? []);
	const [activePluginId, setActivePluginId] = useState<string>(
		_cachedPlugins?.find((p) => p.active)?.id ?? "",
	);
	const [loading, setLoading] = useState(_cachedPlugins === null);
	const [loadError, setLoadError] = useState<string | null>(null);

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
	// reconnect path in `useConnection` (background poll, manual retry,
	// supervisor `reconnected`) lands `connectionStatus` on "connected"
	// without touching this hook, so without this effect the error
	// state sticks until the user navigates away or clicks Retry. Refetch
	// exactly on the disconnected/transient → connected transition while
	// the cache is still empty; a populated cache means the list already
	// rendered and needs no refresh.
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

	// Activation is persisted by the backend (`set_config` writes
	// `active_plugin`); the push keeps the list + this page's toggle in sync
	// no matter which surface changed it.
	usePythonEvent(
		"config_changed",
		useCallback((): (() => void) | undefined => {
			void (async () => {
				try {
					const config = await call<LausuConfig>("get_config");
					setActivePluginId(
						typeof config.active_plugin === "string"
							? config.active_plugin
							: "",
					);
					setPlugins((prev) =>
						prev.map((p) => ({ ...p, active: p.id === config.active_plugin })),
					);
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

	// Optimistic: flip locally, then persist. `""` restores the built-in
	// local model, which is why the toggle writes a value, not a boolean.
	const setActivePlugin = useCallback(
		(pluginId: string) => {
			setActivePluginId(pluginId);
			setPlugins((prev) =>
				prev.map((p) => ({ ...p, active: p.id === pluginId })),
			);
			call("set_config", { active_plugin: pluginId }).catch((err) => {
				console.warn(
					"[renderer:usePlugins] set_config active_plugin failed:",
					err,
				);
			});
		},
		[call],
	);

	return {
		plugins,
		activePluginId,
		loading,
		loadError,
		loadPlugins,
		setActivePlugin,
	};
}
