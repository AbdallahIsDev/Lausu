/**
 * One-command Tauri dev environment, the Tauri equivalent of
 * `npm run dev`.
 *
 * Usage (from voice_typer/client):
 *
 *     npm run tauri:dev
 *
 * What it does, in order:
 *   1. Spawns the Vite dev server (vite.tauri.config.ts, port 1420,
 *      strictPort, HMR, renderer plugins/aliases/CSP) as a child.
 *   2. Waits until http://localhost:1420 answers.
 *   2b. Ensures the Tauri externalBin/resource STUB binaries exist
 *      (`gen_tauri_icons_stub.py --check || generate`). The repo's test
 *      suite deliberately deletes stubs (`--clean`, they are
 *      gitignored build scratch), so without this step every full
 *      pytest run breaks the next `tauri dev` with
 *      "resource path ... doesn't exist". Stubs are regenerated on
 *      demand; real built binaries are never touched.
 *   3. Spawns `tauri dev --config src-tauri/tauri.dev.conf.json` from
 *      the REPO ROOT. The committed override blanks
 *      `build.beforeDevCommand` (the CLI spawns it with a CWD where
 *      the stock `cd voice_typer/client && ...` cannot resolve —
 *      reproduced 2026-08-30; the stock command stays pinned in
 *      tauri.conf.json for CI builds, which DO resolve it). The
 *      Rust host is a debug build, so `dev_mode::is_dev_mode()`
 *      defaults it to the SOURCE Python sidecar, no env vars needed.
 *   4. Forwards everything; Ctrl+C (or either child exiting) tears the
 *      whole tree down (taskkill /T, Node's child.kill does not kill
 *      Windows process trees).
 *
 * Rust file changes: the tauri CLI rebuilds + relaunches the app
 * automatically. Renderer file changes: Vite HMR pushes instantly.
 */
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const clientDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(clientDir, "..", "..");
const devOverride = path.join(repoRoot, "src-tauri", "tauri.dev.conf.json");

// rustup installs cargo under ~/.cargo/bin but GUI-launched cmd.exe often
// has a PATH without it (`cargo metadata` → "program not found"). The GNU
// Windows toolchain (tauri-winres / windres, x86_64-w64-mingw32-gcc-ar)
// lives in MSYS2 mingw64\bin and is likewise often missing from GUI PATH.
function withBuildToolsOnPath(env) {
	const extraDirs = [
		path.join(os.homedir(), ".cargo", "bin"),
		"C:\\msys64\\mingw64\\bin",
		"C:\\msys64\\ucrt64\\bin",
		"C:\\msys64\\usr\\bin",
		// Dev sidecar/worker: `python.exe` for `python -m voice_typer...`
		path.join(repoRoot, ".venv", "Scripts"),
		path.join(repoRoot, ".venv", "bin"),
	];
	const next = { ...env };
	const key = process.platform === "win32" ? "Path" : "PATH";
	let cur = next[key] ?? next.PATH ?? "";
	const parts = cur ? cur.split(path.delimiter) : [];
	const lower = new Set(parts.map((p) => p.toLowerCase()));
	for (const dir of extraDirs) {
		if (!existsSync(dir)) continue;
		if (lower.has(dir.toLowerCase())) continue;
		parts.unshift(dir);
		lower.add(dir.toLowerCase());
	}
	next[key] = parts.join(path.delimiter);
	return next;
}
const childEnv = withBuildToolsOnPath(process.env);

// NOTE: `localhost`, not 127.0.0.1, Vite binds whichever stack
// `localhost` resolves to (::1 on this machine) and the tauri CLI's
// own devUrl wait also uses `localhost`; polling 127.0.0.1 hangs.
const VITE_URL = "http://localhost:1420/";
const VITE_WAIT_TIMEOUT_MS = 60_000;

/** Kill a process tree on Windows (child.kill() does not traverse). */
function killTree(pid) {
	if (!pid) return;
	spawn("taskkill", ["/T", "/F", "/PID", String(pid)], {
		stdio: "ignore",
		windowsHide: true,
	});
}

let viteChild = null;
let cliChild = null;
let shuttingDown = false;

function teardown(exitCode) {
	if (shuttingDown) return;
	shuttingDown = true;
	killTree(viteChild?.pid);
	killTree(cliChild?.pid);
	process.exitCode = exitCode ?? 0;
	// give taskkill a beat to land before the process exits
	setTimeout(() => process.exit(process.exitCode ?? 0), 300);
}

process.on("SIGINT", () => teardown(0));
process.on("SIGTERM", () => teardown(0));
process.on("exit", () => {
	// last-resort (SIGKILL on us): still try to reap children
	killTree(viteChild?.pid);
	killTree(cliChild?.pid);
});

async function waitForVite() {
	const deadline = Date.now() + VITE_WAIT_TIMEOUT_MS;
	while (Date.now() < deadline) {
		try {
			const res = await fetch(VITE_URL, { signal: AbortSignal.timeout(1500) });
			if (res.ok) return;
		} catch {
			/* not up yet */
		}
		await new Promise((r) => setTimeout(r, 400));
	}
	throw new Error(
		`Vite dev server did not answer on ${VITE_URL} within ${VITE_WAIT_TIMEOUT_MS / 1000}s`,
	);
}

/** Kill whatever is bound to the Vite port (leftover from a prior run). */
function freeVitePort(port) {
	if (process.platform === "win32") {
		const out = spawnSync(
			"powershell",
			[
				"-NoProfile",
				"-Command",
				`Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess`,
			],
			{ encoding: "utf8", windowsHide: true },
		);
		const pids = String(out.stdout || "")
			.split(/\s+/)
			.map((s) => Number.parseInt(s, 10))
			.filter((n) => Number.isFinite(n) && n > 0 && n !== process.pid);
		for (const pid of pids) {
			console.log(`[tauri-dev] port ${port} busy (pid=${pid}), killing leftover process`);
			spawnSync("taskkill", ["/T", "/F", "/PID", String(pid)], {
				windowsHide: true,
				stdio: "ignore",
			});
		}
		return;
	}
	const out = spawnSync("bash", ["-lc", `lsof -ti tcp:${port} || true`], {
		encoding: "utf8",
	});
	for (const pid of String(out.stdout || "")
		.split(/\s+/)
		.map((s) => Number.parseInt(s, 10))
		.filter((n) => Number.isFinite(n) && n > 0 && n !== process.pid)) {
		console.log(`[tauri-dev] port ${port} busy (pid=${pid}), killing leftover process`);
		try {
			process.kill(pid, "SIGKILL");
		} catch {
			/* already gone */
		}
	}
}

/** Resolve a Python that can run repo scripts (bare `python` is often absent). */
function resolvePython() {
	const candidates = [];
	if (process.env.MIMO_PYTHON) candidates.push(process.env.MIMO_PYTHON);
	if (process.env.VOICE_TYPER_PYTHON) candidates.push(process.env.VOICE_TYPER_PYTHON);
	candidates.push(path.join(repoRoot, ".venv", "Scripts", "python.exe"));
	candidates.push(path.join(repoRoot, ".venv", "bin", "python"));
	candidates.push("python3");
	candidates.push("python");
	candidates.push("py");
	for (const cand of candidates) {
		if (!cand) continue;
		// Absolute paths must exist; bare names are resolved by PATH.
		if (path.isAbsolute(cand) && !existsSync(cand)) continue;
		const probe = spawnSync(cand, ["--version"], {
			windowsHide: true,
			env: childEnv,
		});
		if (probe.status === 0) return cand;
	}
	return null;
}

const stubScriptPath = path.join(repoRoot, "scripts", "gen_tauri_icons_stub.py");
const linkchainScriptPath = path.join(
	repoRoot,
	"scripts",
	"build",
	"ensure_gnu_linkchain.py",
);

function runStubGen(args) {
	const py = resolvePython();
	if (!py) {
		console.error(
			"[tauri-dev] no Python found (tried .venv, python3, python, py). " +
				"Install Python or create .venv, then re-run.",
		);
		return { status: 1, error: new Error("python not found") };
	}
	const extra = py === "py" ? ["-3"] : [];
	const res = spawnSync(py, [...extra, stubScriptPath, ...args], {
		cwd: repoRoot,
		env: childEnv,
		stdio: "inherit",
		windowsHide: true,
	});
	if (res.error) {
		console.error(`[tauri-dev] failed to spawn ${py}: ${res.error.message}`);
	}
	return res;
}

function runLinkchain(args) {
	const py = resolvePython();
	if (!py) return { status: 0 }; // non-fatal: stub step reports missing Python
	const extra = py === "py" ? ["-3"] : [];
	const res = spawnSync(py, [...extra, linkchainScriptPath, ...args], {
		cwd: repoRoot,
		env: childEnv,
		stdio: "inherit",
		windowsHide: true,
	});
	if (res.error) {
		console.error(`[tauri-dev] failed to spawn ${py}: ${res.error.message}`);
	}
	return res;
}

// ── 1. Vite dev server (HMR) ─────────────────────────────────────────
// Leftover Vite from a crashed prior run often still holds 1420
// (strictPort) — clear it so this launch can bind.
freeVitePort(1420);
console.log("[tauri-dev] starting Vite (http://localhost:1420)...");
viteChild = spawn("cmd", ["/c", "npx", "vite", "--config", "vite.tauri.config.ts"], {
	cwd: clientDir,
	env: childEnv,
	stdio: ["ignore", "inherit", "inherit"],
	windowsHide: true,
});
viteChild.on("exit", (code) => {
	if (!shuttingDown) {
		console.error(`[tauri-dev] vite exited early (code=${code}), aborting`);
		teardown(1);
	}
});

try {
	await waitForVite();
} catch (e) {
	console.error(`[tauri-dev] ${e.message}`);
	teardown(1);
	// teardown schedules process.exit, never fall through to the CLI.
	await new Promise(() => {});
}

// ── 2b. Ensure the Tauri stub binaries exist ─────────────────────────
//
// The stub generator is the sanctioned flow (repo AGENTS.md dev notes):
// `--check` exits 0 iff every externalBin/resource path is present AND
// structurally valid (stub bytes or a REAL binary); the bare run
// generates what is missing and never touches real artifacts. The test
// suite's `--clean` deletes stubs by design, so this check-then-generate
// must run before EVERY `tauri dev`, otherwise pytest (often running
// concurrently in another terminal) breaks the next dev launch.
console.log("[tauri-dev] checking Tauri stub binaries...");
const stubCheck = runStubGen(["--check"]);
if (stubCheck.status !== 0) {
	console.log("[tauri-dev] stubs missing, regenerating...");
	const gen = runStubGen([]);
	if (gen.status !== 0) {
		console.error(
			"[tauri-dev] stub generation failed, aborting (see output above)",
		);
		teardown(1);
		await new Promise(() => {});
	}
}

// ── 2c. Ensure the GNU linker shim exists ────────────────────────────
//
// On Windows-without-MSVC hosts the Rust host links through a generated
// MSYS2/mingw-w64 shim (src-tauri/.toolchain/linker-wrap.exe, built from the
// tracked src-tauri/toolchain/linker_wrap.c). It is gitignored build scratch,
// so a stray delete, an AV quarantine, or a fresh clone removes it — and the
// only symptom is a misleading "error: linker ... not found" plus dozens of
// unrelated "could not compile" lines. Same check-then-regenerate shape as the
// stub step above, so the dev loop self-heals instead of failing cryptically.
console.log("[tauri-dev] checking GNU linker shim...");
if (runLinkchain(["--check"]).status !== 0) {
	console.log("[tauri-dev] linker shim missing, regenerating...");
	if (runLinkchain([]).status !== 0) {
		console.error(
			"[tauri-dev] GNU linker shim setup failed, aborting (see output above)",
		);
		teardown(1);
		await new Promise(() => {});
	}
}

// ── 3. Tauri CLI (Rust host + sidecar supervisor) ────────────────────
// Prefer the LOCAL @tauri-apps/cli from voice_typer/client/node_modules.
// Bare `npx @tauri-apps/cli` with cwd=repoRoot does not see the client
// package, re-downloads the CLI into the npx cache every run, and prompts
// "Ok to proceed? (y)" — which also vanishes when the cache is cleaned.
console.log("[tauri-dev] starting tauri dev (debug host + source sidecar)...");
const localTauriWin = path.join(clientDir, "node_modules", ".bin", "tauri.cmd");
const localTauriPosix = path.join(clientDir, "node_modules", ".bin", "tauri");
const localTauri = existsSync(localTauriWin)
	? localTauriWin
	: existsSync(localTauriPosix)
		? localTauriPosix
		: null;

let cliCmd;
let cliArgs;
if (localTauri) {
	// Windows .cmd needs cmd.exe; POSIX bin is directly executable.
	cliCmd = process.platform === "win32" ? "cmd" : localTauri;
	cliArgs =
		process.platform === "win32"
			? ["/c", localTauri, "dev", "--config", devOverride]
			: ["dev", "--config", devOverride];
} else {
	console.warn(
		"[tauri-dev] local @tauri-apps/cli missing; using npx --yes (run `npm install` in voice_typer/client to pin it)",
	);
	cliCmd = process.platform === "win32" ? "cmd" : "npx";
	cliArgs =
		process.platform === "win32"
			? ["/c", "npx", "--yes", "@tauri-apps/cli", "dev", "--config", devOverride]
			: ["--yes", "@tauri-apps/cli", "dev", "--config", devOverride];
}
cliChild = spawn(cliCmd, cliArgs, {
	cwd: repoRoot,
	env: childEnv,
	stdio: ["inherit", "inherit", "inherit"],
	windowsHide: true,
});
cliChild.on("exit", (code) => {
	// The CLI owns the Rust host; when it exits (app closed / Ctrl+C in
	// the CLI's console), the whole dev session is done.
	if (!shuttingDown) teardown(code ?? 0);
});

// Keep the orchestrator alive while the CLI runs.
await new Promise(() => {});
