/**
 * Inlines the repo's `CHANGELOG.md` as the `virtual:release-notes` module.
 *
 * Settings → Updates "What's New" renders the newest release block, and the
 * notes must work offline and can never disagree with the file that ships in
 * the release. A plain `?raw` import of the repo-root changelog is NOT an
 * option: it resolves outside the renderer root, which Vite's dev-server fs
 * guard denies (`Denied ID .../CHANGELOG.md?raw`) and which previously
 * crashed HMR on an out-of-root alias — see the `@server` note in
 * `vite.config.ts` and the in-root JSON copy rationale in
 * `components/hotkey/hotkey-validation.ts`. Reading the file here, in Node at
 * config/build time, keeps the module graph inside the renderer root.
 *
 * Registered by `vite.tauri.config.ts` (dev server + production build) and
 * `vitest.config.ts` (tests). The module type is declared in
 * `src/renderer/src/globals.d.ts`.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import type { Plugin } from "vite";

const VIRTUAL_ID = "virtual:release-notes";
/** Rollup convention: a `\0` prefix marks a module with no file on disk. */
const RESOLVED_ID = `\0${VIRTUAL_ID}`;

/**
 * @param repoRoot Absolute path to the repository root (the directory that
 *   holds `CHANGELOG.md`), one level above `voice_typer/`.
 */
export function releaseNotesPlugin(repoRoot: string): Plugin {
	return {
		name: "lausu:release-notes",
		resolveId(id) {
			return id === VIRTUAL_ID ? RESOLVED_ID : null;
		},
		load(id) {
			if (id !== RESOLVED_ID) return null;
			const changelog = path.join(repoRoot, "CHANGELOG.md");
			// The changelog sits outside the Vite root, so the watcher does
			// not pick it up on its own; without this a dev-server edit to
			// CHANGELOG.md would not refresh the modal.
			this.addWatchFile(changelog);
			const raw = readFileSync(changelog, "utf8");
			return `export default ${JSON.stringify(raw)};`;
		},
	};
}
