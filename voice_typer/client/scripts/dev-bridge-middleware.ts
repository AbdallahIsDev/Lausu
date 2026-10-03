// Dev-only middleware bridge: browser renderer <-> Python sidecar (WS).
//
// The renderer normally reaches the backend through the Tauri WebView
// global (`window.__TAURI__`), installed by `lib/tauri-bridge`. In a plain
// browser that global does not exist, so `dev-browser-bridge.mjs` installs
// a shim which calls THIS middleware over same-origin HTTP; the middleware
// speaks the real sidecar WebSocket protocol on the renderer's behalf.
//
// Why this shape:
//   - Same-origin HTTP satisfies the dev CSP (`connect-src 'self'` in
//     csp-plugin.ts, which is pinned by tests) with no CSP change.
//   - The sidecar's `--ws` transport is the REAL transport, so the browser
//     sees genuine production behaviour (same dispatch registry, same rate
//     limiter, same event stream), not a simulation.
//   - The bearer token is generated and consumed here, inside the Node dev
//     process. It is never sent to the browser, so a stray tab cannot reach
//     the backend directly.
//
// DEV ONLY. Imported exclusively by `vite-browser-bridge.ts` under
// `apply: "serve"`, so it never reaches a production build.

import { spawn } from "node:child_process";
import type { ChildProcessWithoutNullStreams } from "node:child_process";
import type { IncomingMessage, ServerResponse } from "node:http";
import path from "node:path";
import { randomBytes } from "node:crypto";
import { fileURLToPath } from "node:url";

const LOG = "[dev-bridge]";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../../..");
const EVENTS_PATH = "/__dev_bridge/events";
const RPC_PATH = "/__dev_bridge";

// Matches EXPECTED_PROTOCOL_VERSION in src-tauri/src/sidecar/ws.rs.
const PROTOCOL_VERSION = 1;

// How long to wait for the sidecar to report its port before giving up.
// Real startup is ~15-20s (the model warms in the background, but the app
// and IPC server construct first).
const READY_TIMEOUT_MS = 90_000;

/**
 * Runs one `python -m voice_typer.server.ipc_server --ws` child and
 * exposes it as an HTTP endpoint for the browser shim.
 */
class DevSidecar {
	// Declared explicitly (not just assigned in the constructor) so the
	// class has a real shape for `strict` field access.
	private child: ChildProcessWithoutNullStreams | null = null;
	private ws: WebSocket | null = null;
	private readonly token: string = randomBytes(32).toString("hex");
	private pending = new Map<
		number,
		{ resolve: (v: unknown) => void; reject: (e: Error) => void; timer: NodeJS.Timeout }
	>();
	private nextId = 1;
	private events: Record<string, unknown>[] = [];
	private waiters = new Set<(m: Record<string, unknown> | null) => void>();
	private stdoutBuf = "";
	private onPort: ((port: number) => void) | null = null;
	private ready: Promise<void> | null = null;

	/** Spawn (once) and complete the auth handshake. Idempotent. */
	ensureStarted() {
		if (!this.ready) this.ready = this.#start();
		return this.ready;
	}

	async #start() {
		// Resolve the repo's own interpreter: the sidecar needs numpy and
		// friends, which the bare `python` on PATH may not have.
		const python =
			process.env.VOICE_TYPER_PYTHON ??
			path.join(REPO_ROOT, ".venv", "Scripts", "python.exe");

		this.child = spawn(
			python,
			["-m", "voice_typer.server.ipc_server", "--ws"],
			{
				cwd: REPO_ROOT,
				env: {
					...process.env,
					// The sidecar refuses to accept connections without this.
					VOICE_TYPER_IPC_TOKEN: this.token,
					// The Tauri host owns the single-instance mutex on the
					// real sidecar path; a dev child must not fight for it
					// while the real app is running.
					TAURI_SIDECAR: "1",
					PYTHONUNBUFFERED: "1",
				},
				stdio: ["pipe", "pipe", "pipe"],
			},
		);
		console.log(`${LOG} sidecar pid=${this.child.pid}`);

		this.child.stdout.setEncoding("utf8");
		this.child.stdout.on("data", (c) => this.#onStdout(c));
		this.child.stderr.setEncoding("utf8");
		this.child.stderr.on("data", (c) =>
			console.log(`${LOG} stderr: ${c.trim()}`),
		);
		this.child.on("exit", (code) => {
			console.log(`${LOG} sidecar exited code=${code}`);
			this.#failAll(`sidecar exited (code ${code})`);
			this.child = null;
			this.ws = null;
			this.ready = null; // allow a later request to respawn
			this.#pushEvent({
				type: "error",
				data: { message: "dev sidecar exited" },
			});
		});

		const port = await this.#awaitPort();
		await this.#connect(port);
	}

	/** The sidecar prints {"event":"server_started","port":N} on stdout. */
	#awaitPort(): Promise<number> {
		return new Promise<number>((resolve, reject) => {
			const timer = setTimeout(
				() => reject(new Error("sidecar did not report a port in time")),
				READY_TIMEOUT_MS,
			);
			this.onPort = (port) => {
				clearTimeout(timer);
				resolve(port);
			};
		});
	}

	#onStdout(chunk: string) {
		this.stdoutBuf += chunk;
		let idx;
		while ((idx = this.stdoutBuf.indexOf("\n")) !== -1) {
			const line = this.stdoutBuf.slice(0, idx).trim();
			this.stdoutBuf = this.stdoutBuf.slice(idx + 1);
			if (!line || !line.startsWith("{")) continue; // plain logging
			let msg;
			try {
				msg = JSON.parse(line);
			} catch {
				continue;
			}
			if (msg.event === "server_started") this.onPort?.(msg.port);
		}
	}

	/** Connect + handshake, mirroring the Rust host's client sequence. */
	#connect(port: number): Promise<void> {
		return new Promise((resolve, reject) => {
			const ws = new WebSocket(`ws://127.0.0.1:${port}`);
			this.ws = ws;
			const failTimer = setTimeout(
				() => reject(new Error("sidecar auth timed out")),
				30_000,
			);

			ws.addEventListener("open", () => {
				ws.send(
					JSON.stringify({
						type: "auth",
						token: this.token,
						protocol_version: PROTOCOL_VERSION,
					}),
				);
			});

			ws.addEventListener("message", (ev) => {
				let msg;
				try {
					msg = JSON.parse(ev.data);
				} catch {
					return;
				}
				// C-WS-1: the first post-auth frame is `ready`.
				if (msg.type === "ready" || msg.type === "auth_ok") {
					clearTimeout(failTimer);
					console.log(`${LOG} authenticated, sidecar ready`);
					resolve(undefined);
					return;
				}
				this.#route(msg);
			});

			ws.addEventListener("error", () => {
				clearTimeout(failTimer);
				reject(new Error("sidecar socket error"));
			});
			ws.addEventListener("close", () => {
				clearTimeout(failTimer);
				this.#failAll("sidecar socket closed");
				this.ws = null;
			});
		});
	}

	#route(msg: Record<string, unknown>) {
		// No `id` => unsolicited server-initiated event.
		if (typeof msg.id !== "number") {
			this.#pushEvent(msg);
			return;
		}
		const id = msg.id;
		const entry = this.pending.get(id);
		if (!entry) return;
		clearTimeout(entry.timer);
		this.pending.delete(id);
		if (msg.type === "error") {
			const data = msg.data as { message?: string } | undefined;
			entry.reject(new Error(data?.message ?? "sidecar error"));
		} else {
			entry.resolve(msg.data);
		}
	}

	#pushEvent(msg: Record<string, unknown>) {
		this.events.push(msg);
		// Bound the buffer so a chatty event source cannot grow it forever.
		if (this.events.length > 200) this.events.splice(0, 100);
		for (const resolve of this.waiters) resolve(msg);
		this.waiters.clear();
	}

	#failAll(reason: string) {
		for (const [, p] of this.pending) {
			clearTimeout(p.timer);
			p.reject(new Error(reason));
		}
		this.pending.clear();
	}

	/** Send one IPC dispatch; resolves with the response `data` field. */
	async request(
		type: string,
		data: unknown,
		{ timeoutMs = 60_000 }: { timeoutMs?: number } = {},
	): Promise<unknown> {
		await this.ensureStarted();
		const ws = this.ws;
		if (!ws || ws.readyState !== 1 /* OPEN */) {
			throw new Error("dev sidecar not connected");
		}
		const id = this.nextId++;
		return new Promise((resolve, reject) => {
			const timer = setTimeout(() => {
				this.pending.delete(id);
				reject(new Error(`bridge timeout for ${type}`));
			}, timeoutMs);
			this.pending.set(id, { resolve, reject, timer });
			// Frame shape matches the Rust host (dispatch.rs:195).
			ws.send(JSON.stringify({ type, data: data ?? {}, id }));
		});
	}

	/** Long-poll for the next unsolicited server event. */
	async nextEvent(
		{ timeoutMs = 25_000 }: { timeoutMs?: number } = {},
	): Promise<Record<string, unknown> | null> {
		if (this.events.length) return this.events.shift() ?? null;
		return new Promise((resolve) => {
			const done = (msg: Record<string, unknown> | null) => {
				clearTimeout(timer);
				this.waiters.delete(done);
				resolve(msg);
			};
			const timer = setTimeout(() => done(null), timeoutMs);
			this.waiters.add(done);
		});
	}

	stop() {
		try {
			this.ws?.close();
		} catch {
			// already closing
		}
		if (this.child && this.child.exitCode === null) this.child.kill();
		this.child = null;
		this.ws = null;
		this.ready = null;
	}
}

export function devBridgeMiddleware() {
	const sidecar = new DevSidecar();

	const handler = async (
		req: IncomingMessage,
		res: ServerResponse,
		next: () => void,
	) => {
		const url = req.url ?? "";

		if (url.startsWith(RPC_PATH) && req.method === "POST") {
			let raw = "";
			req.on("data", (c: Buffer | string) => {
				raw += c;
				// IPC frames are small JSON objects; cap runaway bodies.
				if (raw.length > 4 * 1024 * 1024) req.destroy();
			});
			req.on("end", async () => {
				let msg: { type?: string; data?: unknown };
				try {
					msg = JSON.parse(raw);
				} catch {
					res.statusCode = 400;
					res.end('{"ok":false,"error":"invalid JSON"}');
					return;
				}
				try {
					const data = await sidecar.request(
						String(msg.type),
						msg.data,
					);
					res.setHeader("content-type", "application/json");
					res.end(JSON.stringify({ ok: true, data }));
				} catch (err) {
					res.statusCode = 502;
					res.end(
						JSON.stringify({
							ok: false,
							error: String(
								err instanceof Error ? err.message : err,
							),
						}),
					);
				}
			});
			return;
		}

		if (url.startsWith(EVENTS_PATH)) {
			// Start eagerly so the first long-poll wait also covers sidecar
			// startup.
			sidecar.ensureStarted().catch(() => {});
			const msg = await sidecar.nextEvent();
			res.setHeader("content-type", "application/json");
			// `null` = no event within the window; the client re-polls, so
			// this is a keepalive rather than an error.
			res.end(JSON.stringify(msg ?? null));
			return;
		}

		next();
	};

	handler.close = () => sidecar.stop();
	return handler;
}