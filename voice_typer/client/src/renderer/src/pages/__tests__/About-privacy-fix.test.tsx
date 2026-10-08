import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
// Shared stable-mocks preamble (see helpers/stableMocks.tsx): the
// assertable singletons + one vi.mock line per module.
import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
	nextThemesMock,
	pythonMock,
	sonnerMock,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";

const { mockCall } = stableMocks;

vi.mock("@/hooks/usePython", () => pythonMock());
vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());
vi.mock("sonner", () => sonnerMock());
vi.mock("next-themes", () => nextThemesMock());

describe("Merged About & Privacy page, BG-59 privacy URL fix", () => {
	beforeEach(() => {
		mockCall.mockReset();
		mockCall.mockImplementation((type: string) => {
			if (type === "get_status") {
				return Promise.resolve({
					status: "idle",
					config_dir: "/tmp",
					loaded_via: "cpu/int8/tiny.en",
				});
			}
			if (type === "get_config") {
				return Promise.resolve({
					asr_backend: "whisper",
					model_size: "large-v3-turbo",
					device: "cpu",
					hotkey: "F2",
					microphone: null,
				});
			}
			return Promise.resolve({});
		});
	});

	afterEach(() => {
		cleanup();
	});

	it("does NOT render the 'Full Privacy Policy' button (removed, duplicate of Security Policy)", async () => {
		const { default: AboutAndPrivacyPage } = await import(
			"@/pages/AboutAndPrivacy"
		);
		render(<AboutAndPrivacyPage />);

		await waitFor(() => {
			expect(
				screen.getByRole("heading", { name: "About & Privacy" }),
			).toBeTruthy();
		});

		// The "Full Privacy Policy" button is gone, the i18n key
		// (unused dead key, cleaned up with the note removal), and
		// the UI renders no "Full Privacy Policy" surface at all.
		expect(screen.queryByText("Full Privacy Policy")).toBeNull();
	});

	it("does NOT render the 'See the full privacy policy below' note (removed, the full privacy content is already shown inline above it)", async () => {
		const { default: AboutAndPrivacyPage } = await import(
			"@/pages/AboutAndPrivacy"
		);
		render(<AboutAndPrivacyPage />);

		await waitFor(() => {
			expect(
				screen.getByRole("heading", { name: "About & Privacy" }),
			).toBeTruthy();
		});

		// The trailing "Privacy policy, See the full privacy policy
		// below…" line pointed at nothing (the full disclosure is
		// rendered in the rows above it). Both the label and the note
		// are gone.
		expect(screen.queryByText("Privacy policy")).toBeNull();
		expect(screen.queryByText(/See the full privacy policy below/)).toBeNull();
	});
});
