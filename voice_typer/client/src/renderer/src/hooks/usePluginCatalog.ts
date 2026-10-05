// Owner of the installed-plugin catalog: one module-level cache and one
// IPC round-trip, shared by the Plugins page and by the Shell (which needs
// only `available` to decide whether to show the Plugins nav item).
//
// Why it lives here rather than under `pages/plugins/`: layout code must
// never import from a page, so the shell's consumer sits on the neutral
// side of that boundary and the page reads the same cache.

import { useEffect, useState } from "react";
import { useLatestRef } from "@/hooks/useLatestRef";
import { type PythonCall, usePython } from "@/hooks/usePython";
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
		// A failed probe must not unlock a developer-only surface.
		const denied: PluginCatalog = { available: false, plugins: [] };
		_catalog = denied;
		return denied;
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
 * `false` until the backend answers, so the nav item is absent on first
 * paint rather than flashing into view on a shipped build.
 */
export function usePluginsAvailable(): boolean {
	const { call } = usePython();
	const [available, setAvailable] = useState(
		() => _catalog?.available ?? false,
	);

	// callRef mirror: keeps this effect's deps free of `call`, which is
	// recreated on every bridge change and would re-probe on each one.
	const callRef = useLatestRef(call);

	// callRef is a useLatestRef mirror; reading .current in a stale closure
	// is the hook's documented contract, .current must NOT become a dep.
	useEffect(() => {
		let cancelled = false;
		void loadPluginCatalog(callRef.current).then((catalog) => {
			if (!cancelled) setAvailable(catalog.available);
		});
		return () => {
			cancelled = true;
		};
	}, [callRef]);

	return available;
}
