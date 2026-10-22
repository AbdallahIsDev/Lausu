import { t } from "@/i18n/i18n";
import { checkHotkeyConflict } from "./checkHotkeyConflict";
import { formatHotkeyLabel } from "./hotkey-format";
import {
	detectPlatform,
	validateHotkey as validateHotkeyShared,
} from "./hotkey-validation";

/**
 * Validate a hotkey for the UI.
 *
 * The shared validator owns every cross-layer rule; this wrapper adds only
 * the picker's single-key mode constraint (dictation key = one key, no combo).
 * Returns null on success, or a localized message on failure.
 */
export function validateHotkey(
	hotkey: string,
	mode: "single" | "combo",
): string | null {
	const sharedResult = validateHotkeyShared(hotkey, detectPlatform());
	if (!sharedResult.valid) {
		return sharedResult.reason ?? t("hotkeyValidation.invalidHotkey");
	}

	if (mode !== "single") return null;

	const parts = hotkey.split("+").filter((p) => p.replace(/[<>]/g, "").trim());
	if (parts.length > 1) {
		return t("hotkeyValidation.dictationKeySingle");
	}
	return null;
}

// Hotkey capture state machine (reducer + types)
// unit-testable function. The hook calls ``useReducer(hotkeyCaptureReducer,
// initialHotkeyCaptureState)`` and dispatches actions; side-effects
// (calling ``onChange``, ``onCaptureStart``/``onCaptureEnd``, clearing
// timers) live in the hook, NOT in the reducer.
// The reducer tracks ONLY the visible UI state:
//   - status: idle → capturing → committed | cancelled (→ error is unused
//     in practice because validation failures keep the user in capture
//     mode; kept in the union for future use)
//   - error: the localized error string shown under the picker
//   - secondsRemaining: the 30s capture countdown
//   - heldModifiersLabel: the live "Holding: …" label
// The hook retains refs for genuine mutable state NOT in the reducer
// (held/session key sets, ESC-pressed flag, timer IDs, container DOM
// ref, unsupported-combo label).

/** How long the picker stays in capture mode before auto-exiting. */
export const CAPTURE_TIMEOUT_SECONDS = 30;

export const CANONICAL_MOD_ORDER = [
	"ctrl",
	"shift",
	"alt",
	"cmd",
	"win",
	"super",
	"fn",
] as const;

export type HotkeyCaptureStatus =
	| "idle"
	| "capturing"
	| "committed"
	| "cancelled"
	| "error";

export type HotkeyCaptureState = {
	status: HotkeyCaptureStatus;
	error: string | null;
	secondsRemaining: number;
	heldModifiersLabel: string;
};

export type HotkeyCaptureAction =
	| { type: "Start" }
	| { type: "KeyDown"; modifiers: string; nonModifiers: string }
	| { type: "KeyUp"; modifiers: string; nonModifiers: string }
	| { type: "EscPressed" }
	| { type: "EscReleased" }
	| { type: "Timeout" }
	| { type: "BackendCancel" }
	| { type: "OutsideClick" }
	| { type: "CommitAttempt"; hotkey: string }
	| { type: "CommitSuccess" }
	| { type: "CommitFailure"; error: string }
	| { type: "Tick"; secondsRemaining: number }
	//SetError is a slight extension to the  spec's action list:
	// the hook exposes ``setError`` for the preset-dropdown onSelect
	// (which can both set and clear the error), and that path doesn't
	// represent a commit failure. ``CommitFailure`` requires a non-null
	// error string, so we need a separate action that accepts ``null``.
	| { type: "SetError"; error: string | null };

export const initialHotkeyCaptureState: HotkeyCaptureState = {
	status: "idle",
	error: null,
	secondsRemaining: 0,
	heldModifiersLabel: "",
};

function buildHeldModifiersLabelFromAction(modifiers: string): string {
	if (!modifiers) return "";
	const mods = modifiers
		.split(",")
		.map((m) => m.trim())
		.filter(Boolean);
	if (mods.length === 0) return "";
	return formatHotkeyLabel(mods.map((m) => `<${m}>`).join("+"));
}

export function hotkeyCaptureReducer(
	state: HotkeyCaptureState,
	action: HotkeyCaptureAction,
): HotkeyCaptureState {
	switch (action.type) {
		case "Start":
			return {
				...state,
				status: "capturing",
				error: null,
				secondsRemaining: CAPTURE_TIMEOUT_SECONDS,
				heldModifiersLabel: "",
			};
		case "KeyDown":
			if (state.status !== "capturing") return state;
			return {
				...state,
				heldModifiersLabel: buildHeldModifiersLabelFromAction(action.modifiers),
			};
		case "KeyUp":
			if (state.status !== "capturing") return state;
			return {
				...state,
				heldModifiersLabel: buildHeldModifiersLabelFromAction(action.modifiers),
			};
		case "EscPressed":
			// no visible state change here, the ESC
			// press is tracked in ``escPressedRef`` (genuine mutable
			// state) and the cancel happens on ESC release via
			// ``EscReleased``.
			return state;
		case "EscReleased":
		case "Timeout":
		case "BackendCancel":
		case "OutsideClick":
			return state.status === "capturing"
				? {
						...state,
						status: "cancelled",
						error: null,
						heldModifiersLabel: "",
						secondsRemaining: 0,
					}
				: state;
		case "CommitAttempt":
			// The caller validates the hotkey (via ``tryCommitHotkey``)
			// and dispatches ``CommitSuccess`` or ``CommitFailure``.
			// No state change here.
			return state;
		case "CommitSuccess":
			return state.status === "capturing"
				? {
						...state,
						status: "committed",
						error: null,
						heldModifiersLabel: "",
						secondsRemaining: 0,
					}
				: state;
		case "CommitFailure":
			// Validation/conflict failure: keep status as-is (user
			// stays in capture mode). Only set the error.
			return { ...state, error: action.error };
		case "SetError":
			return { ...state, error: action.error };
		case "Tick":
			return { ...state, secondsRemaining: action.secondsRemaining };
		default:
			return state;
	}
}

export function tryCommitHotkey(
	newHotkey: string,
	opts: {
		mode: "single" | "combo";
		value: string;
		occupiedHotkeys: string[] | undefined;
		t: (key: string, params?: Record<string, string>) => string;
		resetSession: boolean;
	},
): { ok: true } | { ok: false; error: string } {
	const validationError = validateHotkey(newHotkey, opts.mode);
	if (validationError) return { ok: false, error: validationError };
	const conflict = checkHotkeyConflict(
		newHotkey,
		opts.value,
		opts.occupiedHotkeys,
		opts.t,
	);
	if (conflict) return { ok: false, error: conflict };
	return { ok: true };
}
