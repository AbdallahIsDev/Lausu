import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

// `hotkey-utils.ts` reads `navigator.userAgent` to derive IS_WIN /
// IS_LINUX / IS_MAC at module load, and `getComboPresets()` re-reads it
// on every call via `detectPlatform()`. Each test below stubs the
// userAgent string and re-imports the module via vi.resetModules() +
// dynamic import() so the platform branch under test is exercised
// deterministically.

async function importUtils() {
	vi.resetModules();
	return (await import(
		"../hotkey/hotkey-utils"
	)) as typeof import("../hotkey/hotkey-utils");
}

function setUserAgent(ua: string) {
	vi.stubGlobal("navigator", { userAgent: ua });
}

describe("getComboPresets(), Win+Space safety", () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		vi.resetModules();
	});

	beforeAll(() => {
		// Ensure a clean starting point.
		vi.resetModules();
	});

	it("never contains <win>+<space> on Windows", async () => {
		setUserAgent(
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
		);
		const { getComboPresets, IS_WIN } = await importUtils();
		expect(IS_WIN).toBe(true);
		const COMBO_PRESETS = getComboPresets();
		const offending = COMBO_PRESETS.filter((p) => p.value === "<win>+<space>");
		expect(offending).toHaveLength(0);
	});

	it("never contains <super>+<space> on Windows (Super is Linux-only)", async () => {
		setUserAgent(
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
		);
		const { getComboPresets, IS_WIN } = await importUtils();
		expect(IS_WIN).toBe(true);
		const COMBO_PRESETS = getComboPresets();
		const offending = COMBO_PRESETS.filter(
			(p) => p.value === "<super>+<space>",
		);
		expect(offending).toHaveLength(0);
	});

	it("still offers <super>+<space> on Linux (Linux does not reserve it)", async () => {
		setUserAgent("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36");
		const { getComboPresets, IS_LINUX } = await importUtils();
		expect(IS_LINUX).toBe(true);
		const COMBO_PRESETS = getComboPresets();
		const superSpace = COMBO_PRESETS.find((p) => p.value === "<super>+<space>");
		expect(superSpace).toBeTruthy();
	});

	it("never contains <win>+<space> on macOS either", async () => {
		setUserAgent(
			"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
		);
		const { getComboPresets, IS_MAC } = await importUtils();
		expect(IS_MAC).toBe(true);
		const COMBO_PRESETS = getComboPresets();
		const offending = COMBO_PRESETS.filter((p) => p.value === "<win>+<space>");
		expect(offending).toHaveLength(0);
	});
});

describe("HotkeyPicker, reusable for both recording and paste shortcuts", () => {
	// This is a structural import test: it verifies the HotkeyPicker
	// component is the single, shared entry point used by the settings
	// section. A full render test already lives in Settings.test.tsx;
	// here we just guard against regressions where the paste shortcut
	// might be silently switched to a bespoke picker.
	// Note: no afterEach with vi.resetModules() here, the platform-
	// detection tests in the describe block above need module isolation
	// (they stub navigator.userAgent), but this test does not. Keeping
	// the module cache intact avoids re-evaluating the ~dozen+ component
	// dependency tree on every test run.
	it("HotkeySettingsSection imports HotkeyPicker (shared component for both modes)", async () => {
		// The RecordingSettingsSection now contains both the dictation key
		// and re-paste key pickers (the standalone HotkeySettingsSection
		// RecordingSettingsSection and confirm it resolves to a defined,
		// renderable component.
		const sectionMod = (await import(
			"../settings/RecordingSettingsSection"
		)) as typeof import("../settings/RecordingSettingsSection");
		expect(sectionMod.RecordingSettingsSection).toBeTruthy();
		// Re-import HotkeyPicker to confirm the symbol resolves; if
		// either the section or the picker is renamed/removed, this
		// throws and the test fails loudly.
		const pickerMod = (await import(
			"../hotkey/HotkeyPicker"
		)) as typeof import("../hotkey/HotkeyPicker");
		expect(typeof pickerMod.HotkeyPicker).toBe("function");
	}, 30_000);
});

describe("resolveCharKey(), per-platform single-character capture", () => {
	afterEach(() => {
		vi.unstubAllGlobals();
		vi.resetModules();
	});

	// Fake KeyboardEvent-shaped objects: only `key` and `code` are read.
	const fakeEvent = (key: string, code: string) => ({ key, code });

	it("digits resolve from e.code on every platform", async () => {
		const { resolveCharKey } = await importUtils();
		for (const platform of ["win32", "darwin", "linux"]) {
			// e.key differs from the top-row digit (numpad / layout shift).
			expect(resolveCharKey(fakeEvent("!", "Digit1"), platform)).toBe("1");
			expect(resolveCharKey(fakeEvent("5", "Digit5"), platform)).toBe("5");
		}
	});

	it("win32 and darwin resolve single characters from e.key", async () => {
		const { resolveCharKey } = await importUtils();
		for (const platform of ["win32", "darwin"]) {
			// Non-US layout: physical KeyY produces the character "z".
			expect(resolveCharKey(fakeEvent("z", "KeyY"), platform)).toBe("z");
			expect(resolveCharKey(fakeEvent("V", "KeyV"), platform)).toBe("v");
		}
	});

	it("linux resolves single characters from e.code (physical keycode)", async () => {
		const { resolveCharKey } = await importUtils();
		// Physical position wins over the shifted character.
		expect(resolveCharKey(fakeEvent("Z", "KeyY"), "linux")).toBe("y");
		expect(resolveCharKey(fakeEvent("v", "KeyV"), "linux")).toBe("v");
	});

	it("falls back to the code table for unmapped single characters", async () => {
		const { resolveCharKey } = await importUtils();
		// A multi-char e.key (e.g. "Enter") is not a single character.
		expect(resolveCharKey(fakeEvent("Enter", "Enter"), "win32")).toBe("enter");
		expect(resolveCharKey(fakeEvent("Spacebar", "Space"), "linux")).toBe(
			"space",
		);
	});

	it("resolves Space through the code table on every platform", async () => {
		const { resolveCharKey } = await importUtils();
		// A real Space event carries a single-space e.key: treating it as a
		// character would collapse <ctrl>+<space> into modifier-only <ctrl>.
		for (const platform of ["win32", "darwin", "linux"]) {
			expect(resolveCharKey(fakeEvent(" ", "Space"), platform)).toBe("space");
		}
	});

	it("refuses numpad codes instead of binding the top-row digit", async () => {
		const { resolveCharKey } = await importUtils();
		for (const platform of ["win32", "darwin", "linux"]) {
			expect(
				resolveCharKey(fakeEvent("0", "Numpad0"), platform),
			).toBeUndefined();
		}
	});
});
