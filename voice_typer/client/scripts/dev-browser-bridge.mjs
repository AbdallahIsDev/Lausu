// Dev-only browser bridge shim (injected by vite-browser-bridge.ts).
//
// Lets the renderer run in a plain browser (Hermes preview pane, ordinary
// Chrome) instead of the Tauri WebView. `lib/tauri-bridge/detect.ts` probes
// for `window.__TAURI__.core.invoke`; this file provides just enough of
// that surface for `installTauriBridge()` to take its normal path, with
// `invoke("dispatch", {cmd, data})` relayed to the Python sidecar through
// the Vite dev middleware (scripts/dev-bridge-middleware.ts).
//
// The renderer bundle itself is unchanged — the same bridge code runs in
// both hosts; only the transport underneath differs.
//
// DEV ONLY: injected under `apply: "serve"`, so this never ships.

const LOG = "[dev-browser-bridge]";

const RPC_URL = "/__dev_bridge";
const EVENTS_URL = "/__dev_bridge/events";

// ─── Event plumbing ──────────────────────────────────────────────────────
// Mirrors the real global: `listen` resolves to an unlisten function and
// handlers receive `{event, payload, id}`.

const listeners = new Map();

function emit(event, payload) {
	const set = listeners.get(event);
	if (!set) return;
	for (const handler of [...set]) {
		try {
			handler({ event, payload, id: 0 });
		} catch (err) {
			console.error(LOG, "listener threw", err);
		}
	}
}

let pollStarted = false;

/** Long-poll the middleware for unsolicited server events. */
async function pumpEvents() {
	if (pollStarted) return;
	pollStarted = true;
	for (;;) {
		try {
			const res = await fetch(EVENTS_URL);
			const msg = await res.json();
			if (msg) emit(msg.type, msg.data);
		} catch (err) {
			console.warn(LOG, "event poll failed; retrying", err);
			await new Promise((r) => setTimeout(r, 1000));
		}
	}
}

const event = {
	async listen(name, handler) {
		let set = listeners.get(name);
		if (!set) {
			set = new Set();
			listeners.set(name, set);
		}
		set.add(handler);
		pumpEvents();
		return () => set.delete(handler);
	},
	async emit(name, payload) {
		emit(name, payload);
	},
};

// ─── invoke ──────────────────────────────────────────────────────────────

// Native-window commands. Each one drives the SEPARATE bubble window
// (position, drag, resize, dismiss) through the Rust host, which does not
// exist in a browser. The main renderer still calls them on its connect
// path, so they resolve as no-ops instead of throwing — otherwise every
// browser session opens with a wall of console errors that are expected
// and drown the real ones. The bubble itself is a native window; this
// bridge only ever backs the main window.
const NATIVE_ONLY_COMMANDS = new Set([
	"bubble_dismiss",
	"bubble_hide_complete",
	"bubble_move_by",
	"bubble_resize",
	"bubble_set_draggable",
	"bubble_set_position",
	"bubble_show",
	"bubble_signal_ready",
	"bubble_toggle_dictation",
]);

const core = {
	async invoke(cmd, args) {
		if (NATIVE_ONLY_COMMANDS.has(cmd)) return null;
		// The Rust host exposes many commands; the renderer only reaches the
		// backend through `dispatch`, so that is all this shim implements.
		if (cmd !== "dispatch") {
			throw new Error(
				`${LOG} unsupported command "${cmd}" (dev bridge implements "dispatch" only)`,
			);
		}
		const res = await fetch(RPC_URL, {
			method: "POST",
			headers: { "content-type": "application/json" },
			body: JSON.stringify({ type: args?.cmd, data: args?.data }),
		});
		const body = await res.json();
		if (!body.ok) {
			throw new Error(body.error ?? "dev bridge request failed");
		}
		return body.data;
	},
};

// ─── Window controls ─────────────────────────────────────────────────────
// No-ops: the browser owns its own chrome, and `isMaximized` reports false
// so the renderer renders its unmaximized layout.

function getCurrentWindow() {
	return {
		label: "main",
		minimize: async () => {},
		toggleMaximize: async () => {},
		close: async () => {},
		isMaximized: async () => false,
		resize: async () => {},
		onResized: async () => () => {},
	};
}

// ─── Install ─────────────────────────────────────────────────────────────
// Inside the real WebView, `window.__TAURI__` is already present before any
// of our code runs, so this is a no-op there and the native path is
// untouched. `label: "main"` also keeps the SEC-026 window-guard contract:
// the full bridge namespaces install, as they do for the main window.

if (typeof window.__TAURI__ === "undefined") {
	window.__TAURI__ = { core, event, window: { getCurrentWindow } };
	console.log(LOG, "installed (browser dev mode — not the Tauri WebView)");
} else {
	console.log(LOG, "real Tauri global present, shim skipped");
}