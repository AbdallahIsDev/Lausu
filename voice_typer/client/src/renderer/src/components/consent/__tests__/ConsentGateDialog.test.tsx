/**
 * Unit tests for the unified point-of-use consent dialog
 * (`ConsentGateDialog`).
 *
 * Contract under test:
 *   - Allow → persists ONLY the requested consent field via the
 *     allowlisted `set_config` IPC (SEC-002), then runs the request's
 *     `onAllow` retry, then closes.
 *   - set_config failure → the dialog stays open, `onAllow` is NOT
 *     called (the UI never claims a grant that wasn't persisted), and
 *     an error snackbar fires.
 *   - X / overlay click / Escape → dismiss WITHOUT granting: no
 *     `set_config`, no `onAllow`.
 *   - "View all" → deep-links to the Privacy & Consent SECTION page
 *     (`settingsPrivacy`, NOT the `settings` hub) via the
 *     `consentField` navigate option, grants nothing.
 *   - There is NO "allow all" control: bundled contextual consent is
 *     uninformed, so accept-all lives only in the Settings consent
 *     center where every item is listed before the user acts.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Shared stable-mocks preamble (see helpers/stableMocks.tsx): the
// assertable singletons + one vi.mock line per module.
import {
	pythonMock,
	resetStableMocks,
	snackbarMock,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";

const { mockCall, mockNavigate, showSnack: mockShowSnack } = stableMocks;

vi.mock("@/hooks/usePython", () => pythonMock());
vi.mock("@/hooks/useNavigation", () => ({
	useNavigation: () => ({ navigate: mockNavigate }),
}));
vi.mock("@/hooks/useSnackbar", () => snackbarMock());

// `t` is the imperative translator used by shared primitives (e.g.
// DialogContent's close button `aria-label`); the dialog itself uses the
// `useT` hook.
vi.mock("@/i18n/i18n", () => ({
	t: (key: string) => key,
	useT: () => (key: string, params?: Record<string, string>) =>
		params ? `${key}:${JSON.stringify(params)}` : key,
}));

import {
	type ConsentGateRequest,
	useConsentGateStore,
} from "@/lib/consentGate";
import ConsentGateDialog from "../ConsentGateDialog";

describe("ConsentGateDialog, unified point-of-use consent", () => {
	beforeEach(() => {
		useConsentGateStore.setState({ request: null });
		resetStableMocks();
		mockCall.mockResolvedValue({});
	});

	afterEach(() => {
		useConsentGateStore.setState({ request: null });
	});

	function openDialog(overrides: Partial<ConsentGateRequest> = {}) {
		useConsentGateStore.getState().open({
			consentField: "cloud_groq_consent",
			bodyKey: "consentDialog.field.cloud_groq_consent",
			...overrides,
		});
	}

	it("renders nothing when no consent request is pending", () => {
		const { container } = render(<ConsentGateDialog />);
		expect(container).toBeEmptyDOMElement();
	});

	it("Allow persists the consent, runs the retry, and closes", async () => {
		const onAllow = vi.fn(async () => {});
		openDialog({ onAllow });
		render(<ConsentGateDialog />);

		await screen.findByRole("dialog");
		// Body leads with the exact field's plain-language description.
		// Matched as a substring because the description may carry
		// trailing hint copy alongside it (the node's full text is the
		// body + hint concatenated).
		const description = document.querySelector(
			'[data-slot="dialog-description"]',
		);
		expect(description?.textContent).toContain(
			"consentDialog.field.cloud_groq_consent",
		);

		await userEvent.click(
			screen.getByRole("button", { name: "consentDialog.allow" }),
		);

		expect(mockCall).toHaveBeenCalledWith("set_config", {
			cloud_groq_consent: true,
		});
		await waitFor(() => expect(onAllow).toHaveBeenCalledTimes(1));
		// The dialog closes only AFTER the retry ran.
		expect(useConsentGateStore.getState().request).toBeNull();
	});

	it("does NOT run the retry or close when set_config fails, error snackbar instead", async () => {
		const onAllow = vi.fn(async () => {});
		mockCall.mockRejectedValue(new Error("persist failed"));
		openDialog({ onAllow });
		render(<ConsentGateDialog />);

		await screen.findByRole("dialog");
		await userEvent.click(
			screen.getByRole("button", { name: "consentDialog.allow" }),
		);

		expect(onAllow).not.toHaveBeenCalled();
		// The dialog stays open, the grant did not persist.
		expect(useConsentGateStore.getState().request).not.toBeNull();
		expect(mockShowSnack).toHaveBeenCalledWith(
			"consentDialog.persistFailed",
			"error",
		);
	});

	it("Allow grants ONLY the requested consent field", async () => {
		const onAllow = vi.fn(async () => {});
		openDialog({ consentField: "llm_polish_consent", onAllow });
		render(<ConsentGateDialog />);

		await screen.findByRole("dialog");
		await userEvent.click(
			screen.getByRole("button", { name: "consentDialog.allow" }),
		);

		expect(mockCall).toHaveBeenCalledTimes(1);
		expect(mockCall).toHaveBeenCalledWith("set_config", {
			llm_polish_consent: true,
		});
		await waitFor(() => expect(onAllow).toHaveBeenCalledTimes(1));
	});

	describe("dismissal grants nothing", () => {
		it("the X close button closes without granting", async () => {
			const onAllow = vi.fn();
			openDialog({ onAllow });
			render(<ConsentGateDialog />);

			await screen.findByRole("dialog");
			await userEvent.click(
				screen.getByRole("button", { name: "common.close" }),
			);

			await waitFor(() =>
				expect(useConsentGateStore.getState().request).toBeNull(),
			);
			expect(mockCall).not.toHaveBeenCalled();
			expect(onAllow).not.toHaveBeenCalled();
		});

		it("an overlay click closes without granting", async () => {
			const onAllow = vi.fn();
			openDialog({ onAllow });
			render(<ConsentGateDialog />);

			const dialog = await screen.findByRole("dialog");
			// The overlay is the sibling layer Radix dismisses on when a
			// pointer interaction lands outside the content.
			const overlay = document.querySelector("[data-slot='dialog-overlay']");
			expect(overlay).toBeTruthy();
			await userEvent.pointer({
				target: overlay as Element,
				keys: "[MouseLeft]",
				// Coordinates must fall OUTSIDE the content box so Radix
				// classifies the press as an outside interaction.
				coords: {
					clientX: dialog.getBoundingClientRect().left - 40,
					clientY: dialog.getBoundingClientRect().top - 40,
				},
			});

			await waitFor(() =>
				expect(useConsentGateStore.getState().request).toBeNull(),
			);
			expect(mockCall).not.toHaveBeenCalled();
			expect(onAllow).not.toHaveBeenCalled();
		});

		it("Escape closes without granting", async () => {
			const onAllow = vi.fn();
			openDialog({ onAllow });
			render(<ConsentGateDialog />);

			await screen.findByRole("dialog");
			await userEvent.keyboard("{Escape}");

			await waitFor(() =>
				expect(useConsentGateStore.getState().request).toBeNull(),
			);
			expect(mockCall).not.toHaveBeenCalled();
			expect(onAllow).not.toHaveBeenCalled();
		});
	});

	it("View all deep-links to the Privacy consent section and grants nothing", async () => {
		const onAllow = vi.fn();
		openDialog({ onAllow });
		render(<ConsentGateDialog />);

		await screen.findByRole("dialog");
		await userEvent.click(
			screen.getByRole("button", { name: "consentDialog.viewAll" }),
		);

		// Must be the Privacy & Consent SECTION page, not the `"settings"`
		// hub: `useSettingsDeepLinks` only arms the row scroll+highlight on
		// `page === "settingsPrivacy"`, so the hub would land the user on the
		// section list with no row focused.
		expect(mockNavigate).toHaveBeenCalledWith("settingsPrivacy", {
			consentField: "cloud_groq_consent",
		});
		expect(useConsentGateStore.getState().request).toBeNull();
		expect(mockCall).not.toHaveBeenCalled();
		expect(onAllow).not.toHaveBeenCalled();
	});

	it("exposes no 'allow all' control (uninformed bundled consent)", async () => {
		openDialog();
		render(<ConsentGateDialog />);

		await screen.findByRole("dialog");
		const labels = screen
			.getAllByRole("button")
			.map((btn) =>
				(btn.getAttribute("aria-label") ?? btn.textContent ?? "").trim(),
			);
		// No single control may grant everything at once. `viewAll` is the
		// navigate-only link ("View all" = see every consent item in the
		// Settings consent center); it grants nothing, so the pattern
		// targets an accept/allow-ALL action. Compared per-label so the
		// joined list can't produce a false cross-button match.
		for (const label of labels) {
			expect(label).not.toMatch(/allow.?all|accept.?all|all.?consent/i);
		}
		// Only the three intended controls exist: X, View all, Allow.
		expect(labels).toHaveLength(3);
		expect(labels).toEqual([
			"common.close",
			"consentDialog.viewAll",
			"consentDialog.allow",
		]);
	});

	it("surfaces a warning snackbar when the retry itself fails (consent still granted)", async () => {
		const onAllow = vi.fn(async () => {
			throw new Error("toggle failed");
		});
		openDialog({ onAllow });
		render(<ConsentGateDialog />);

		await screen.findByRole("dialog");
		await userEvent.click(
			screen.getByRole("button", { name: "consentDialog.allow" }),
		);

		await waitFor(() => expect(mockShowSnack).toHaveBeenCalled());
		// The consent WAS persisted, the dialog closed regardless.
		expect(useConsentGateStore.getState().request).toBeNull();
		expect(mockShowSnack).toHaveBeenCalledWith(
			"consentDialog.retryFailed",
			"warning",
		);
	});
});
