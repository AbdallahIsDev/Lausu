// src/renderer/src/components/consent/ConsentGateDialog.tsx
// Unified point-of-use consent dialog ("This sends your audio to Groq.
// Allow?"). Mounted ONCE in App.tsx; any consent-gated flow opens it via
// `openConsentGate()` (see lib/consentGate.ts).
// Behaviour:
//   - Allow → persists the consent field via the allowlisted
//     `set_config` IPC (SEC-002), then invokes the request's `onAllow`
//     retry (e.g. re-start dictation, re-run the download), then
//     closes. If persistence fails, the dialog stays open with an
//     error toast, the UI never claims consent was granted when the
//     backend rejected it.
//   - X / overlay click / Escape → dismiss. No consent is granted and
//     `onAllow` never fires.
//   - "View all" → deep-links to the Privacy & Consent section page,
//     focused on the requested row (Settings consumes the
//     `consentField` navigate option there), closes. Grants nothing.
//
// Dialog semantics (NOT AlertDialog): refusing is non-destructive, so
// the surface must be dismissable by backdrop/Escape, which
// AlertDialog suppresses by design.
//
// Deliberately NO "Allow all" here (legal): bundled, contextual consent
// is uninformed — this dialog describes ONE data flow, so it can only
// grant that one. Accept-all lives solely in the Settings consent
// center, where every consent item is listed visibly before the user
// acts.
// The OS-level equivalent (clickable native toast → Settings) is the
// backend's `notification` event with `click_consent_field`; both
// paths land on the same Settings consent center.

import { useCallback } from "react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { useNavigation } from "@/hooks/useNavigation";
import { usePython } from "@/hooks/usePython";
import { useSnackbar } from "@/hooks/useSnackbar";
import { useT } from "@/i18n/i18n";
import { useConsentGateStore } from "@/lib/consentGate";

export default function ConsentGateDialog() {
	const { call } = usePython();
	const { navigate } = useNavigation();
	const { showSnack } = useSnackbar();
	const t = useT();
	const request = useConsentGateStore((s) => s.request);
	const close = useConsentGateStore((s) => s.close);

	const open = request !== null;

	const handleAllow = useCallback(async () => {
		if (!request) return;
		try {
			await call("set_config", { [request.consentField]: true });
		} catch (err) {
			console.error(
				"[renderer:ConsentGateDialog] set_config consent failed:",
				err,
			);
			showSnack(t("consentDialog.persistFailed"), "error");
			// Keep the dialog open, the grant did not persist, so the
			// UI must not claim it did (mirrors the onboarding Done-step
			// consent checkbox revert-on-failure contract).
			return;
		}
		close();
		if (request.onAllow) {
			try {
				await request.onAllow();
			} catch (err) {
				console.error(
					"[renderer:ConsentGateDialog] consent retry failed:",
					err,
				);
				// Non-fatal: the consent is granted; the user can simply
				// try the action again. Surface a hint so the failure
				// isn't silent.
				showSnack(t("consentDialog.retryFailed"), "warning");
			}
		}
	}, [request, call, close, showSnack, t]);

	// Dismissal is a REFUSAL: it closes the gate and never grants.
	// `Dialog` routes its X (DialogContent's built-in close button),
	// overlay click, and Escape all through this one handler.
	const handleOpenChange = useCallback(
		(isOpen: boolean) => {
			if (!isOpen) close();
		},
		[close],
	);

	// "View all" targets the Privacy & Consent SECTION page directly, not
	// the Settings hub: the consent deep-link consumer
	// (`useSettingsDeepLinks`) only arms its scroll+highlight on
	// `page === "settingsPrivacy"`, so landing on the hub would drop the
	// user on the section list with no row highlighted. The backend
	// `navigate` event applies the same remap
	// (`useNavigateEvent`: `"settings"` + consent_field -> the Privacy
	// page), so both entry points behave identically.
	const handleViewAll = useCallback(() => {
		if (!request) return;
		close();
		navigate("settingsPrivacy", { consentField: request.consentField });
	}, [request, close, navigate]);

	if (!request) return null;

	return (
		<Dialog open={open} onOpenChange={handleOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>{t("consentDialog.title")}</DialogTitle>
					<DialogDescription>
						{t(request.bodyKey, request.bodyParams)}{" "}
						{t("consentDialog.revokeHint")}
					</DialogDescription>
				</DialogHeader>
				{/* Left link + right actions: `justify-between` pushes them to
				    the row's two ends, `gap-2` spaces them (C-UI-10 — no
				    margin utilities for inter-child spacing). */}
				<DialogFooter className="sm:justify-between">
					<Button type="button" variant="ghost" onClick={handleViewAll}>
						{t("consentDialog.viewAll")}
					</Button>
					{/* Plain Button, not a Dialog close primitive: Radix's Close
					    auto-closes on click, which would defeat the
					    keep-open-on-persist-failure contract. The dialog closes
					    only via the explicit `close()` in handleAllow, or a
					    dismissal gesture (X / overlay / Escape). */}
					<Button type="button" onClick={handleAllow}>
						{t("consentDialog.allow")}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
