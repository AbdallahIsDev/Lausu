// Guards against dead font payload. A font shipped from `public/fonts/`
// is copied verbatim into the build output, so an unreferenced face is
// dead weight in every build (the italic face cost 379 KB). Every font
// file on disk must be referenced by an @font-face `src:` in index.css.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const HERE = dirname(fileURLToPath(import.meta.url));
const RENDERER_ROOT = join(HERE, "..", "..");
const FONTS_DIR = join(RENDERER_ROOT, "public", "fonts");
const INDEX_CSS = join(RENDERER_ROOT, "src", "index.css");

const FONT_EXTENSIONS = [".woff2", ".woff", ".ttf", ".otf"];

function listFontFiles(): string[] {
	if (!existsSync(FONTS_DIR)) return [];
	return readdirSync(FONTS_DIR).filter((name) =>
		FONT_EXTENSIONS.some((ext) => name.toLowerCase().endsWith(ext)),
	);
}

describe("webfont payload", () => {
	it("has no unreferenced font files", () => {
		const css = readFileSync(INDEX_CSS, "utf-8");
		const orphans = listFontFiles().filter((name) => !css.includes(`/${name}`));
		expect(orphans).toEqual([]);
	});

	it("keeps the variable roman face referenced", () => {
		const css = readFileSync(INDEX_CSS, "utf-8");
		expect(css).toContain("/fonts/InterVariable.woff2");
	});
});
