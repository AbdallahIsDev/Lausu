/**
 * Hotkey validation shared with the Python validators.
 *
 * Everything vocabulary-shaped comes from ``hotkey_reserved.json``; the
 * copy under ``data/`` is byte-identical to the server file and pinned by
 * ``test_hotkey_reserved_sync.py``. Validation order mirrors
 * ``config_validators/hotkey.py`` so the picker and the backend classify
 * the same spec the same way.
 */

import { t } from "@/i18n/i18n";
import hotkeyReserved from "../../data/hotkey_reserved.json";

export const UNIVERSAL_RESERVED_SHORTCUTS: readonly string[] =
	hotkeyReserved.universal_reserved;
export const RESERVED_SHORTCUTS: Record<string, string[]> =
	hotkeyReserved.per_platform_reserved as Record<string, string[]>;
export const BLOCKED_CTRL_LETTERS: readonly string[] =
	hotkeyReserved.blocked_ctrl_letters;
export const MODIFIER_KEYS_SHARED: readonly string[] = hotkeyReserved.modifiers;

export const KEY_ALIASES: Readonly<Record<string, string>> =
	hotkeyReserved.key_aliases;
export const KEY_VOCABULARY: Readonly<
	Record<string, { wire: string; platforms: readonly string[] }>
> = hotkeyReserved.keys;

export type ValidationCode =
	| "empty"
	| "no_keys"
	| "unknown_key"
	| "not_string"
	| "too_long"
	| "reserved_universal"
	| "reserved_platform"
	| "single_alnum"
	| "multiple_keys"
	| "modifier_order"
	| "shell_combo"
	| "alt_shift"
	| "ctrl_letter"
	| "shift_letter"
	| "altgr"
	| "fn_platform"
	| "key_not_delivered"
	| "ptt_modifier_only"
	| "ptt_caps_lock";

export interface ValidationResult {
	valid: boolean;
	/** Human-readable reason when valid is false. */
	reason?: string;
	/** Stable classifier shared with the Python validators. */
	code?: ValidationCode;
	partial?: never;
}

export interface ValidationOptions {
	/** Push-to-talk needs a key that reports a release after its press. */
	pushToTalk?: boolean;
}

const _MODIFIER_KEYS_SET = new Set(MODIFIER_KEYS_SHARED);

// ``right_alt``/``ralt`` arrive as genuine modifiers from pynput but the
// listeners report them as Alt/AltGr interchangeably, so they can never match.
const _ALTGR_ALIASES = new Set(["altgr", "alt_gr", "right_alt", "ralt"]);

function _canonicalModifier(token: string): string | null {
	if (!_MODIFIER_KEYS_SET.has(token)) return null;
	const base = token.replace(/_[lr]$/, "");
	if (_ALTGR_ALIASES.has(base)) return "alt_gr";
	switch (base) {
		case "control":
			return "ctrl";
		case "option":
			return "alt";
		case "globe":
			return "fn";
		case "win":
		case "super":
		case "cmd":
			return "cmd";
		default:
			return base;
	}
}

function _isModifierToken(token: string): boolean {
	return _canonicalModifier(token) !== null;
}

function _parseParts(hotkey: string): string[] {
	const seen = new Set<string>();
	const parts: string[] = [];
	for (const raw of hotkey.split("+")) {
		const token = raw.replace(/[<>]/g, "").trim().toLowerCase();
		if (!token) continue;
		const canonical = _canonicalModifier(token) ?? KEY_ALIASES[token] ?? token;
		if (!seen.has(canonical)) {
			seen.add(canonical);
			parts.push(canonical);
		}
	}
	return parts;
}

function _specString(parts: readonly string[]): string {
	const modifiers = parts.filter((part) => _isModifierToken(part)).sort();
	const keys = parts.filter((part) => !_isModifierToken(part));
	return [...modifiers, ...keys].map((part) => `<${part}>`).join("+");
}

const _UNIVERSAL_RESERVED_SET = new Set(
	UNIVERSAL_RESERVED_SHORTCUTS.map((entry) => _specString(_parseParts(entry))),
);

const _RESERVED_SETS = new Map<string, Set<string>>();
function _reservedSet(platform: string): Set<string> {
	const cached = _RESERVED_SETS.get(platform);
	if (cached) return cached;
	const entries = (RESERVED_SHORTCUTS[platform] ?? []).map((entry) =>
		_specString(_parseParts(entry)),
	);
	const built = new Set(entries);
	_RESERVED_SETS.set(platform, built);
	return built;
}

export function detectPlatform(): string {
	if (typeof navigator === "undefined") return "unknown";
	const ua = navigator.userAgent.toLowerCase();
	if (ua.includes("mac")) return "darwin";
	if (ua.includes("win")) return "win32";
	if (ua.includes("linux")) return "linux";
	return "unknown";
}

export function normalizeHotkey(hotkey: string): string {
	if (!hotkey) return "";
	return hotkey
		.split("+")
		.map((p) => p.replace(/[<>]/g, "").trim().toLowerCase())
		.filter(Boolean)
		.join("+");
}

export function isReserved(hotkey: string, platform: string): boolean {
	if (!hotkey?.trim()) return false;
	const normalized = _specString(_parseParts(hotkey));
	if (!normalized) return false;
	return _reservedSet(platform).has(normalized);
}

const _MESSAGE_SPECIAL_LABELS: Readonly<Record<string, string>> = {
	ctrl: "Ctrl",
	shift: "Shift",
	alt: "Alt",
	alt_gr: "AltGr",
	cmd: "Cmd",
	fn: "Fn",
	space: "Space",
	enter: "Enter",
	tab: "Tab",
	esc: "Esc",
	caps_lock: "Caps Lock",
	num_lock: "Num Lock",
	scroll_lock: "Scroll Lock",
	print_screen: "Print Screen",
	pause: "Pause",
	insert: "Insert",
	delete: "Delete",
	home: "Home",
	end: "End",
	page_up: "Page Up",
	page_down: "Page Down",
	up: "Up",
	down: "Down",
	left: "Left",
	right: "Right",
	backspace: "Backspace",
};

function _formatForMessage(parts: readonly string[]): string {
	return parts
		.map((part) => {
			if (_MESSAGE_SPECIAL_LABELS[part]) return _MESSAGE_SPECIAL_LABELS[part];
			if (/^f\d{1,2}$/.test(part)) return part.toUpperCase();
			if (part.length === 1) return part.toUpperCase();
			return part.charAt(0).toUpperCase() + part.slice(1);
		})
		.join("+");
}

function _failure(code: ValidationCode, reason: string): ValidationResult {
	return { valid: false, code, reason };
}

export function validateHotkey(
	hotkey: string,
	platform: string,
	options?: ValidationOptions,
): ValidationResult {
	if (!hotkey?.trim()) {
		return _failure("empty", t("hotkeyValidation.empty"));
	}
	if (hotkey.length > 256) {
		return _failure("too_long", t("hotkeyValidation.invalidHotkey"));
	}

	const rawParts = hotkey
		.split("+")
		.map((p) => p.replace(/[<>]/g, "").trim().toLowerCase())
		.filter(Boolean);
	const parts = _parseParts(hotkey);
	if (parts.length === 0) {
		return _failure("no_keys", t("hotkeyValidation.noKeys"));
	}
	const spec = _specString(parts);
	const label = _formatForMessage(parts);
	const nonMods = parts.filter((part) => !_isModifierToken(part));

	if (_UNIVERSAL_RESERVED_SET.has(spec)) {
		return _failure(
			"reserved_universal",
			t("hotkeyValidation.reservedUniversal", { label }),
		);
	}

	if (_reservedSet(platform).has(spec)) {
		return _failure(
			"reserved_platform",
			t("hotkeyValidation.reservedOs", { label }),
		);
	}

	// A combo mixing a key and modifiers must put the key last; a bare
	// modifier spelling is still a valid modifier-only trigger.
	const trailing = rawParts[rawParts.length - 1];
	if (
		rawParts.length >= 2 &&
		nonMods.length > 0 &&
		trailing !== undefined &&
		_isModifierToken(trailing)
	) {
		return _failure(
			"modifier_order",
			t("hotkeyValidation.mustEndWithNonModifier", { label }),
		);
	}

	if (parts.length === 1) {
		const sole = parts[0];
		if (sole !== undefined && /^[a-z0-9]$/.test(sole)) {
			return _failure(
				"single_alnum",
				t("hotkeyValidation.singleLetterDigit", { key: sole }),
			);
		}
	}

	if (nonMods.length > 1) {
		return _failure(
			"multiple_keys",
			t("hotkeyValidation.multipleKeys", {
				label,
				count: String(nonMods.length),
			}),
		);
	}

	if (parts.includes("alt_gr")) {
		return _failure("altgr", t("hotkeyValidation.altGrUnsupported"));
	}

	if (parts.includes("fn") && platform !== "darwin") {
		return _failure("fn_platform", t("hotkeyValidation.fnMacosOnly"));
	}

	if (parts.includes("cmd")) {
		if (platform === "win32") {
			return _failure(
				"shell_combo",
				t("hotkeyValidation.reservedWindows", { label }),
			);
		}
		if (platform === "darwin") {
			const letter = nonMods.find(
				(part) => part.length === 1 && /^[a-z]$/.test(part),
			);
			if (letter !== undefined) {
				return _failure(
					"shell_combo",
					t("hotkeyValidation.reservedMacosCmd", {
						key: letter.toUpperCase(),
					}),
				);
			}
		}
	}

	if (
		platform === "win32" &&
		parts.includes("alt") &&
		parts.includes("shift") &&
		nonMods.length === 0
	) {
		return _failure(
			"alt_shift",
			t("hotkeyValidation.reservedWindowsAltShift", { label }),
		);
	}

	if (parts.includes("ctrl")) {
		const otherModifiers = parts.filter(
			(part) => _isModifierToken(part) && part !== "ctrl",
		);
		if (otherModifiers.length === 0) {
			const blocked = nonMods.find((part) =>
				BLOCKED_CTRL_LETTERS.includes(part),
			);
			if (blocked !== undefined) {
				return _failure(
					"ctrl_letter",
					t("hotkeyValidation.reservedAppCtrl", {
						key: blocked.toUpperCase(),
					}),
				);
			}
		}
	}

	if (parts.includes("shift")) {
		const otherModifiers = parts.filter(
			(part) => _isModifierToken(part) && part !== "shift",
		);
		if (otherModifiers.length === 0) {
			const alnum = nonMods.find((part) => /^[a-z0-9]$/.test(part));
			if (alnum !== undefined) {
				return _failure(
					"shift_letter",
					t("hotkeyValidation.shiftLetterInterferes", {
						key: alnum.toUpperCase(),
					}),
				);
			}
		}
	}

	for (const key of nonMods) {
		const meta = KEY_VOCABULARY[key];
		if (meta === undefined) {
			return _failure(
				"unknown_key",
				t("hotkeyValidation.keyNotSupported", { label: key }),
			);
		}
		if (
			(platform === "win32" || platform === "darwin" || platform === "linux") &&
			!meta.platforms.includes(platform)
		) {
			return _failure(
				"key_not_delivered",
				t("hotkeyValidation.keyNotDelivered", { key }),
			);
		}
	}

	// Push-to-talk needs a delivered release. The macOS Fn/Globe key has its
	// own down/up pair, so it is the one modifier-only trigger that works.
	const pttFnExempt = platform === "darwin" && parts.includes("fn");
	if (options?.pushToTalk === true && nonMods.length === 0 && !pttFnExempt) {
		return _failure(
			"ptt_modifier_only",
			t("hotkeyValidation.modifierOnlyNotForPushToTalk"),
		);
	}

	// Caps Lock push-to-talk works on Windows and Linux (their listeners emit
	// the key-up); only macOS never reports its release.
	if (
		options?.pushToTalk === true &&
		platform === "darwin" &&
		nonMods.includes("caps_lock")
	) {
		return _failure(
			"ptt_caps_lock",
			t("hotkeyValidation.capsLockNotForPushToTalk"),
		);
	}

	return { valid: true };
}
