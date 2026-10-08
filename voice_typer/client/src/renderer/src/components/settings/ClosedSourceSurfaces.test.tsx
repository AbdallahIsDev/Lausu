/**
 * Closed-source professionalization: the in-app replacement surfaces.
 *
 * Pins the three behaviours the refactor introduced, each of which replaced a
 * browser hand-off to the public repository:
 *   1. `parseLatestRelease` reads exactly the newest Keep-a-Changelog block,
 *      the only input the "What's New" modal has.
 *   2. "What's New" renders those notes inside the app (the old button opened
 *      the GitHub releases page).
 *   3. "Report a Bug" composes the report in-app and hands it to the host
 *      (the old button opened the GitHub issue tracker).
 */
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "@/__tests__/helpers/render";
import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
	pythonMock,
	resetStableMocks,
	snackbarMock,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";

const { showSnack } = stableMocks;

vi.mock("@/hooks/usePython", () => pythonMock());
vi.mock("@/hooks/useSnackbar", () => snackbarMock());
vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());

import changelogRaw from "virtual:release-notes";
import { BugReportModal } from "@/components/settings/BugReportModal";
import { TroubleshootingSettingsSection } from "@/components/settings/TroubleshootingSettingsSection";
import {
	parseLatestRelease,
	WhatsNewModal,
} from "@/components/settings/WhatsNewModal";

describe("parseLatestRelease", () => {
	it("keeps only the newest release block, grouped by its topic headings", () => {
		const raw = [
			"# Changelog",
			"",
			"## [Unreleased]",
			"",
			"### Added",
			"",
			"- first thing",
			"- second thing",
			"",
			"### Fixed",
			"",
			"- a fix",
			"",
			"## [1.0.0] - 2026-01-01",
			"",
			"### Added",
			"",
			"- an older thing",
		].join("\n");

		expect(parseLatestRelease(raw)).toEqual([
			{ title: "Added", items: ["first thing", "second thing"] },
			{ title: "Fixed", items: ["a fix"] },
		]);
	});

	it("joins hard-wrapped continuation lines into the item above", () => {
		const raw = [
			"## [Unreleased]",
			"### Changed",
			"- a change that was wrapped",
			"  across two source lines",
		].join("\n");

		expect(parseLatestRelease(raw)).toEqual([
			{
				title: "Changed",
				items: ["a change that was wrapped across two source lines"],
			},
		]);
	});

	it("drops item-less topic headings and returns [] without a release heading", () => {
		expect(parseLatestRelease("## [Unreleased]\n### Added\n")).toEqual([]);
		expect(parseLatestRelease("# Changelog\n\nNothing yet.")).toEqual([]);
	});
});

describe("WhatsNewModal", () => {
	beforeEach(() => {
		resetStableMocks();
	});

	afterEach(() => {
		cleanup();
	});

	it("renders the newest release notes from the bundled changelog, in-app", () => {
		// The real changelog is inlined through the `virtual:release-notes`
		// plugin module; importing it here proves the plugin resolves under
		// vitest, and that the modal shows a topic heading from that file.
		const sections = parseLatestRelease(changelogRaw);
		expect(sections.length).toBeGreaterThan(0);
		const first = sections[0];
		if (!first) return;

		renderWithProviders(<WhatsNewModal open onClose={() => {}} />);

		expect(screen.getByText("What's New")).toBeTruthy();
		expect(screen.getByText(first.title)).toBeTruthy();
	});
});

describe("BugReportModal", () => {
	const onClose = vi.fn();

	beforeEach(() => {
		resetStableMocks();
		onClose.mockClear();
	});

	afterEach(() => {
		cleanup();
		delete (window as unknown as { window_?: unknown }).window_;
		Object.defineProperty(window.navigator, "clipboard", {
			value: undefined,
			configurable: true,
		});
	});

	it("keeps Send disabled until the description has text", async () => {
		renderWithProviders(<BugReportModal open onClose={onClose} />);

		const send = screen.getByRole("button", {
			name: /send report/i,
		}) as HTMLButtonElement;
		expect(send.disabled).toBe(true);

		fireEvent.change(screen.getByLabelText("What happened?"), {
			target: { value: "The app froze on launch." },
		});

		await waitFor(() => {
			expect(send.disabled).toBe(false);
		});
	});

	it("hands the composed report to the host command when Send is pressed", async () => {
		const sendBugReport = vi.fn((_payload: unknown) =>
			Promise.resolve({ success: true, attachments: 0 }),
		);
		(window as unknown as { window_?: unknown }).window_ = { sendBugReport };

		renderWithProviders(<BugReportModal open onClose={onClose} />);

		fireEvent.change(screen.getByLabelText("What happened?"), {
			target: { value: "The app froze on launch." },
		});
		fireEvent.click(screen.getByRole("button", { name: /send report/i }));

		await waitFor(() => {
			expect(sendBugReport).toHaveBeenCalledTimes(1);
		});

		const payload = sendBugReport.mock.calls[0]?.[0] as {
			to: string;
			subject: string;
			body: string;
			attachments: unknown[];
		};
		// The summary is derived from the description when left blank.
		expect(payload.subject).toBe("[Bug] The app froze on launch.");
		expect(payload.body).toContain("The app froze on launch.");
		// The auto-collected context is appended below the separator.
		expect(payload.body).toContain("---");
		expect(payload.attachments).toEqual([]);
		expect(showSnack).toHaveBeenCalled();
		await waitFor(() => {
			expect(onClose).toHaveBeenCalled();
		});
	});

	it("falls back to the clipboard when the host bridge is absent", async () => {
		// A sandboxed runtime (the bubble window) omits `window.window_`.
		delete (window as unknown as { window_?: unknown }).window_;
		const writeText = vi.fn((_text: string) => Promise.resolve());
		Object.defineProperty(window.navigator, "clipboard", {
			value: { writeText },
			configurable: true,
		});

		renderWithProviders(<BugReportModal open onClose={onClose} />);

		fireEvent.change(screen.getByLabelText("What happened?"), {
			target: { value: "Nothing happened when I pressed the hotkey." },
		});
		fireEvent.click(screen.getByRole("button", { name: /send report/i }));

		await waitFor(() => {
			expect(writeText).toHaveBeenCalled();
		});
		expect(String(writeText.mock.calls[0]?.[0])).toContain(
			"Nothing happened when I pressed the hotkey.",
		);
		expect(showSnack).toHaveBeenCalled();
	});
});

describe("dev-only affordances", () => {
	beforeEach(() => {
		resetStableMocks();
	});

	afterEach(() => {
		cleanup();
		vi.unstubAllEnvs();
	});

	function renderTroubleshooting() {
		return renderWithProviders(
			<TroubleshootingSettingsSection
				isVisible={() => true}
				updateConfig={() => {}}
				onOpenHelp={() => {}}
				onOpenBugReport={() => {}}
			/>,
		);
	}

	it("shows Re-run Setup Wizard while developing", () => {
		renderTroubleshooting();
		expect(screen.getByText("Re-run Setup Wizard")).toBeTruthy();
	});

	it("hides Re-run Setup Wizard from a production build", () => {
		// The wizard exists so the first-run flow can be replayed while
		// developing; shipping it invites users to re-run onboarding and
		// lose their configuration.
		vi.stubEnv("DEV", false);
		renderTroubleshooting();

		expect(screen.queryByText("Re-run Setup Wizard")).toBeNull();
		// The rest of the section is unaffected.
		expect(screen.getByTestId("keyboard-shortcuts-button")).toBeTruthy();
		expect(screen.getByTestId("report-bug-button")).toBeTruthy();
	});
});
