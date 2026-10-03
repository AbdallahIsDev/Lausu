// Dev-only Vite plugin: browser bridge for renderer inspection.
//
// Two jobs, both scoped to the dev server (`apply: "serve"`, so
// `npm run build` output and the shipped app are untouched):
//
//   1. Register `devBridgeMiddleware`, which relays the browser's IPC calls
//      to a Python sidecar over the sidecar's stdin/stdout transport.
//   2. Inject `dev-browser-bridge.mjs` into <head> before the app entry so
//      `window.__TAURI__` exists in a plain browser.
//
// Inside the Tauri WebView the shim no-ops (the real global is already
// there), so `npm run tauri:dev` behaves exactly as before.
//
// Why injection is unconditional in dev: the Tauri window loads the SAME
// dev server (devUrl http://localhost:1420), so this file is served there
// too. It detects the real global and skips itself, which keeps the native
// path byte-identical instead of forking on a URL parameter.

import fs from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { Plugin, ViteDevServer } from "vite";

import { devBridgeMiddleware } from "./dev-bridge-middleware";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHIM_PATH = path.resolve(__dirname, "dev-browser-bridge.mjs");

export function browserBridgePlugin(): Plugin {
	return {
		name: "dev-browser-bridge",
		apply: "serve" as const,
		configureServer(server: ViteDevServer) {
			server.middlewares.use(devBridgeMiddleware());

			// Serve the shim as a module the page can import. Vite will not
			// transform a file outside the project root, so read it once and
			// let it go through the normal JS pipeline explicitly.
			server.middlewares.use(
				"/@dev/browser-bridge.js",
				(_req: IncomingMessage, res: ServerResponse) => {
					res.setHeader("content-type", "text/javascript");
					res.end(fs.readFileSync(SHIM_PATH, "utf8"));
				},
			);

			// Inline the shim ahead of the module entry: it must define
			// `window.__TAURI__` BEFORE the renderer bundle evaluates
			// `installTauriBridge()`.
			const original = server.transformIndexHtml;
			server.transformIndexHtml = async (html: string, ctx: unknown) => {
				const out =
					typeof original === "function"
						? await original.call(server, html, ctx as never)
						: html;
				const tag = [
					'<script type="module">',
					'import "/@dev/browser-bridge.js";',
					"</script>",
				].join("");
				// Inject before any existing script so the global is defined
				// first regardless of what the HTML looks like.
				return out.includes("</head>")
					? out.replace("</head>", `${tag}</head>`)
					: tag + out;
			};
		},
	};
}
