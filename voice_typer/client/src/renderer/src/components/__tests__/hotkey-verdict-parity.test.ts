import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { validateHotkey } from "../hotkey/hotkey-validation";

interface VerdictCase {
	hotkey: string;
	platform: string;
	pushToTalk: boolean;
	code: string | null;
}

const FIXTURE = path.resolve(
	__dirname,
	"../../../../../../../tests/fixtures/hotkey_verdicts.json",
);
const cases = (
	JSON.parse(fs.readFileSync(FIXTURE, "utf8")) as { cases: VerdictCase[] }
).cases;

describe("shared hotkey verdict fixture", () => {
	it.each(cases.map((entry, index) => ({ ...entry, index })))(
		"case $index: $platform $hotkey (ptt=$pushToTalk)",
		({ hotkey, platform, pushToTalk, code }) => {
			const result = validateHotkey(hotkey, platform, { pushToTalk });
			expect(result.valid ? null : result.code).toBe(code);
		},
	);
});
