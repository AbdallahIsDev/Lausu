// Owner of the installed-plugin catalog: one module-level cache and one
// IPC round-trip, shared by the Plugins page and by the Shell (which needs
// only `available` to decide whether to show the Plugins nav item).
//
// Why it lives here rather than under `pages/plugins/`: layout code must
// never import from a page, so the shell's consumer sits on the neutral
// side of that boundary and the page reads the same cache.

import type { PythonCall } from "@/hooks/usePython";
import { useAppStore } from "@/stores/appStore";
import { type PluginCatalog, toPluginCatalog } from "@/types/plugins";

/** Resolved once per process; `null` until the first answer lands. */
let _catalog: PluginCatalog | null = null;
/** In-flight promise, so N consumers produce one IPC call, not N. */
let _inflight: Promise<PluginCatalog> | null = null;

/** Test seam: forget the cached answer. */
export function resetPluginCatalogCache(): void {
	_catalog = null;
	_inflight = null;
}

async function fetchCatalog(call: PythonCall): Promise<PluginCatalog> {
	try {
		const catalog = toPluginCatalog(await call("get_plugins"));
		_catalog = catalog;
		return catalog;
	} catch (err) {
		console.warn("[renderer:usePluginCatalog] get_plugins failed:", err);
		// A failed probe must not unlock a developer-only surface. The
		// denial is returned to THIS caller only and never cached: caching
		// it would poison every later consumer (the Plugins page Retry
		// would resolve the stale denial without a fresh IPC round-trip,
		// and the nav item would stay hidden until process restart).
		return { available: false, plugins: [] };
	} finally {
		_inflight = null;
	}
}

/** Load the catalog once; concurrent callers share the same request. */
export function loadPluginCatalog(call: PythonCall): Promise<PluginCatalog> {
	if (_catalog) return Promise.resolve(_catalog);
	_inflight ??= fetchCatalog(call);
	return _inflight;
}

/**
 * Whether this install may show the Plugins UI.
 *
 * The persisted developer-mode flag is the ONLY renderer gate. The backend
 * still refuses `get_plugins` unless the same flag is set, so hiding the nav
 * here is a presentation guarantee, not the security boundary.
 */
export function usePluginsAvailable(): boolean {
	return useAppStore((s) => s.config?.developer_mode === true);
}
