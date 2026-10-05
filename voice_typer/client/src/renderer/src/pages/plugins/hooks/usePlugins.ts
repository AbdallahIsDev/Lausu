// Owns the plugin list + active-plugin config for the Plugins pages: the
// cache that survives page navigations (so returning from a detail page
// renders the list instantly), the mount load, and the `config_changed`
// subscription that keeps the active-plugin flag fresh after a toggle.
//
// The catalog itself (the `get_plugins` round-trip and the developer
// availability gate) belongs to `@/hooks/usePluginCatalog`, which the shell
// also reads; this hook is the page-side view of that shared cache.

import { useCallback, useEffect, useState } from "react";
import { useLatestRef } from "@/hooks/useLatestRef";
import { loadPluginCatalog } from "@/hooks/usePluginCatalog";
import { usePython, usePythonEvent } from "@/hooks/usePython";
import { t } from "@/i18n/i18n";
import type { LausuConfig } from "@/types/config";
import type { PluginInfo } from "@/types/plugins";

// Module-level cache, mirrors the microphone page's `_cachedMicrophones`:
// the list survives unmount so re-visiting does not flash a skeleton.
let _cachedPlugins: PluginInfo[] | null = null;

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
