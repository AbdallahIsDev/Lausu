// Guards the i18n bundling contract. A runtime-templated dynamic import
// (`import(`./translations/${locale}.json`)`) cannot be analysed by Vite, so
// it never reaches the bundle and every non-English user silently falls back
// to English at runtime. These tests fail if that shape ever returns.
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { SUPPORTED_LOCALES } from "../locale";

const HERE = dirname(fileURLToPath(import.meta.url));
const I18N_DIR = join(HERE, "..");
const STORE_PATH = join(I18N_DIR, "store.ts");
const TRANSLATIONS_DIR = join(I18N_DIR, "translations");

const storeSource = readFileSync(STORE_PATH, "utf-8");

// Comment text may legitimately name the annotation it forbids, so strip
// line comments before asserting on the code itself.
const storeCode = storeSource
	.split("\n")
	.filter((line) => !line.trimStart().startsWith("//"))
	.join("\n");

const NON_EN_LOCALES = SUPPORTED_LOCALES.filter((locale) => locale !== "en");

describe("i18n locale bundling contract", () => {
	it("never opts out of bundler analysis for a locale import", () => {
		expect(storeCode).not.toContain("@vite-ignore");
	});

	it("never builds a locale specifier from a template literal", () => {
		expect(storeCode).not.toMatch(/import\(\s*`[^`]*\$\{/);
	});

	it.each(NON_EN_LOCALES)(
		"statically imports the %s locale so the bundler can emit it",
		(locale) => {
			expect(storeSource).toContain(
				`${locale}: () => import("./translations/${locale}.json")`,
			);
			expect(existsSync(join(TRANSLATIONS_DIR, `${locale}.json`))).toBe(true);
		},
	);

	it("covers every supported non-English locale exactly once", () => {
		const loaders = [
			...storeSource.matchAll(
				/^\t(\w+): \(\) => import\("\.\/translations\//gm,
			),
		]
			.map((match) => match[1])
			.sort();
		expect(loaders).toEqual([...NON_EN_LOCALES].sort());
	});
});
