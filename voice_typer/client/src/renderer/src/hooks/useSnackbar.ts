// src/renderer/src/hooks/useSnackbar.ts
//   1. The bespoke ``useSnackbar`` hook (this file), used by Settings,
//      Models, Microphone, Vocabulary, Templates, and Onboarding pages.
//   2. The ``sonner`` library, used by History.tsx, ActivityList.tsx,
// Both rendered toasts to the user but looked different, had different
// lifetimes, and stacked badly when both fired at once.  This file now
// delegates ALL toast rendering to ``sonner``, there is exactly ONE
// toast system in the renderer.  The UI comes from the single global
// ``<Toaster />`` mounted in App.tsx.  Toasts are raised via ``showSnack``
// (or directly via ``toast.success(...)`` from ``sonner``); both go
// through the same renderer.
// The bespoke ``Snackbar`` component that this hook used to
// ``<Snackbar />`` JSX and, once the component stopped being exported,
// crashed those pages at render time.  There is no longer a ``Snackbar``
// member on the returned object; call sites must not destructure or
// render it.  All toast UI is the global sonner ``<Toaster />``.
// ``useSnackbar.tsx`` but contains no JSX.  The stale duplicate
// ``.tsx`` (left on disk after the rename) was deleted by sessions 1,
// 3, and 5, only this ``.ts`` file now exists under
// ``@/hooks/useSnackbar``.  Vite/TypeScript resolves imports without
// an extension, so all ``import { useSnackbar } from "@/hooks/useSnackbar"``
// statements continue to work without modification.
//toast durations are now standardised per type so that
// transient confirmations disappear quickly while errors stay on
// screen long enough to be read.  Per-call overrides take precedence
// over the per-type defaults, callers that need a custom lifetime
// (e.g. undo toasts) pass ``{ duration: ms }`` as the third argument.
//   success → 3000ms  (fleeting "saved" / "copied" pings)
//   info    → 4000ms  (neutral context, e.g. "model loaded")
//   warning → 6000ms  (recoverable issues, undo affordances)
//   error   → 8000ms  (failures the user must act on)
// Pass `{ persistent: true }` for a sticky toast that never
// auto-dismisses (update downloads, long operations); the user
// closes it with the close button or the caller clears it by id.

import { useCallback } from "react";
import { toast } from "sonner";
import { t } from "@/i18n/i18n";

export type SnackbarType = "success" | "error" | "warning" | "info";

export interface SnackbarState {
	message: string;
	type: SnackbarType;
}

export const SNACKBAR_DEFAULT_DURATION_MS: Record<SnackbarType, number> = {
	success: 3000,
	info: 4000,
	warning: 6000,
	error: 8000,
};

export interface ShowSnackOptions {
	/** Override the per-type default duration (ms). */
	duration?: number;
	/** Never auto-dismiss: the toast stays until the user closes it
	 *  with the close button or the caller clears it by id. Takes
	 *  precedence over `duration` (an explicit duration with
	 *  `persistent` is contradictory; staying wins). */
	persistent?: boolean;
	/** Optional id, passing the same id replaces the existing toast. */
	id?: string | number;
	/** Optional secondary line rendered under the toast message. */
	description?: string;
	action?: {
		label: string;
		onClick: () => void;
	};
	/** Optional SECOND button, rendered next to `action` (sonner's
	 *  "cancel" slot). Needed when a decision offers two real choices
	 *  and neither is a dismissal — e.g. the Listen-Live speaker offer's
	 *  [Lower to 75%] / [Keep as is] pair, where closing the toast by
	 *  its X would be a third, undocumented answer. */
	cancel?: {
		label: string;
		onClick: () => void;
	};
}

function resolveDuration(
	type: SnackbarType,
	options?: ShowSnackOptions,
): number {
	// Sticky toasts never auto-dismiss (sonner's Infinity duration);
	// the global close button and clearSnack(id) still dismiss them.
	if (options?.persistent) return Number.POSITIVE_INFINITY;
	if (options?.duration !== undefined) return options.duration;
	return SNACKBAR_DEFAULT_DURATION_MS[type];
}

function dispatchToast(
	type: SnackbarType,
	message: string,
	opts: {
		duration: number;
		id?: string | number;
		description?: string;
		action?: { label: string; onClick: () => void };
		cancel?: { label: string; onClick: () => void };
	},
): void {
	switch (type) {
		case "success":
			toast.success(message, opts);
			break;
		case "error":
			toast.error(message, opts);
			break;
		case "warning":
			toast.warning(message, opts);
			break;
		case "info":
			toast.info(message, opts);
			break;
	}
}

export function useSnackbar() {
	const showSnack = useCallback(
		(
			message: string,
			type: SnackbarType = "success",
			options?: ShowSnackOptions,
		) => {
			//delegate to sonner so there is exactly ONE toast
			// system in the renderer.  Each ``type`` maps to the matching
			// sonner method so the icon and color come from the global
			// Toaster configuration in ``components/ui/sonner.tsx``.
			//per-type default durations with per-call override.
			const opts: {
				duration: number;
				id?: string | number;
				description?: string;
				action?: { label: string; onClick: () => void };
				cancel?: { label: string; onClick: () => void };
			} = {
				duration: resolveDuration(type, options),
			};
			if (options?.id !== undefined) {
				opts.id = options.id;
			}
			if (options?.description !== undefined) {
				opts.description = options.description;
			}
			if (options?.action) {
				opts.action = options.action;
			}
			if (options?.cancel) {
				opts.cancel = options.cancel;
			}
			dispatchToast(type, message, opts);
		},
		[],
	);

	const clearSnack = useCallback((id?: string | number) => {
		// Dismiss a specific toast when an id is given; otherwise
		// dismiss all active toasts. The optional id maps 1:1 to
		// ``toast.dismiss(id)`` so callers that have shown a
		// context-specific toast can dismiss just that one without
		// killing unrelated toasts. Omitting id preserves the
		// legacy "clear all" semantics for existing call sites.
		if (id !== undefined) {
			toast.dismiss(id);
		} else {
			toast.dismiss();
		}
	}, []);

	return { showSnack, clearSnack };
}

export function showUndoableToast(
	message: string,
	onUndo: () => void,
	options: {
		undoLabel?: string;
		type?: SnackbarType;
		timeoutMs?: number;
	} = {},
): void {
	const { undoLabel = t("common.undo"), type = "warning", timeoutMs } = options;
	const duration = timeoutMs ?? SNACKBAR_DEFAULT_DURATION_MS[type];
	const opts = {
		duration,
		action: {
			label: undoLabel,
			onClick: onUndo,
		},
	};
	dispatchToast(type, message, opts);
}

export function showRetryableToast(
	message: string,
	onRetry: () => void,
	options: {
		retryLabel?: string;
		type?: SnackbarType;
		timeoutMs?: number;
	} = {},
): void {
	const { retryLabel = t("common.retry"), type = "error", timeoutMs } = options;
	const duration = timeoutMs ?? SNACKBAR_DEFAULT_DURATION_MS[type];
	const opts = {
		duration,
		action: {
			label: retryLabel,
			onClick: onRetry,
		},
	};
	dispatchToast(type, message, opts);
}
