import {
	act,
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
	pythonMock,
	resetStableMocks,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";
import { expireModelStatusSnapshot } from "@/hooks/models/modelStatusCache";
import { useConsentGateStore } from "@/lib/consentGate";

vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());
vi.mock("@/hooks/usePython", () =>
	pythonMock({ captureEvents: stableMocks.pythonEventHandlers }),
);
vi.mock("@/i18n/i18n", () => ({
	t: (key: string, params?: Record<string, string>) =>
		params?.percent ? `${key} ${params.percent}%` : key,
	useT: () => (key: string, params?: Record<string, string>) =>
		params?.percent ? `${key} ${params.percent}%` : key,
}));

import { TranslationModelDownloadRow } from "@/components/settings/TranslationModelDownloadRow";
import { TRANSLATION_MODEL_ID } from "@/components/settings/translationModel";

const { mockCall, pythonEventHandlers } = stableMocks;

function renderRow(overrides: Record<string, boolean> = {}) {
	const config = {
		huggingface_consent: true,
		translation_enabled: true,
		...overrides,
	} as never;
	return render(
		<TranslationModelDownloadRow
			config={config}
			downloadLabel="Download translation model"
			sizeLabel="1.31 GB"
		/>,
	);
}

beforeEach(() => {
	resetStableMocks();
	expireModelStatusSnapshot();
	useConsentGateStore.setState({ request: null });
	mockCall.mockImplementation((cmd: string) => {
		if (cmd === "get_model_status") {
			return Promise.resolve({
				[TRANSLATION_MODEL_ID]: { downloaded: false, deps_ok: true },
			});
		}
		return Promise.resolve({ success: true });
	});
});

afterEach(() => {
	cleanup();
	resetStableMocks();
});

describe("TranslationModelDownloadRow", () => {
	it("shows download required while enabled and not installed", async () => {
		renderRow();
		expect(
			await screen.findByText("settings.translationDownloadRequired"),
		).toBeTruthy();
		expect(
			screen.getByRole("button", { name: "Download translation model" }),
		).toBeTruthy();
	});

	it("opens the shared consent dialog before any download IPC", async () => {
		renderRow({ huggingface_consent: false });
		await screen.findByText("settings.translationDownloadRequired");
		fireEvent.click(
			screen.getByRole("button", { name: "Download translation model" }),
		);
		expect(useConsentGateStore.getState().request?.consentField).toBe(
			"huggingface_consent",
		);
		expect(
			mockCall.mock.calls.filter(([cmd]) => cmd === "download_model"),
		).toEqual([]);
		await act(async () => {
			await useConsentGateStore.getState().request?.onAllow?.();
		});
		expect(mockCall).toHaveBeenCalledWith("download_model", {
			model: TRANSLATION_MODEL_ID,
		});
	});

	it("renders shared progress bar + cancel, then delete after success", async () => {
		let finishDownload: (value: object) => void = () => {};
		mockCall.mockImplementation((cmd: string) => {
			if (cmd === "get_model_status") {
				return Promise.resolve({
					[TRANSLATION_MODEL_ID]: { downloaded: false, deps_ok: true },
				});
			}
			if (cmd === "download_model") {
				return new Promise((resolve) => {
					finishDownload = resolve;
				});
			}
			return Promise.resolve({ success: true });
		});
		renderRow();
		await screen.findByText("settings.translationDownloadRequired");
		fireEvent.click(
			screen.getByRole("button", { name: "Download translation model" }),
		);

		const handler = pythonEventHandlers["download_progress"];
		expect(handler).toBeTypeOf("function");
		act(() => {
			handler?.({
				model: TRANSLATION_MODEL_ID,
				progress: 50,
				status: "Downloading",
			});
		});
		expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe(
			"50",
		);
		const cancel = screen.getByRole("button", {
			name: "settings.translationCancelDownload",
		});
		fireEvent.click(cancel);
		expect(mockCall).toHaveBeenCalledWith("cancel_model_download", {
			model: TRANSLATION_MODEL_ID,
		});

		await act(async () => {
			finishDownload({ success: true });
		});
		await waitFor(() =>
			expect(
				screen.getByRole("button", { name: "settings.translationDelete" }),
			).toBeTruthy(),
		);
		fireEvent.click(
			screen.getByRole("button", { name: "settings.translationDelete" }),
		);
		await waitFor(() =>
			expect(mockCall).toHaveBeenCalledWith("delete_model", {
				model: TRANSLATION_MODEL_ID,
			}),
		);
	});

	it("shows a clear localized message when the server reports low disk space", async () => {
		mockCall.mockImplementation((cmd: string) => {
			if (cmd === "get_model_status") {
				return Promise.resolve({
					[TRANSLATION_MODEL_ID]: { downloaded: false, deps_ok: true },
				});
			}
			if (cmd === "download_model") {
				return Promise.resolve({
					success: false,
					code: "translation_disk_space_insufficient",
				});
			}
			return Promise.resolve({ success: true });
		});
		renderRow();
		await screen.findByText("settings.translationDownloadRequired");
		fireEvent.click(
			screen.getByRole("button", { name: "Download translation model" }),
		);
		expect(
			await screen.findByText("settings.translationDownloadInsufficientSpace"),
		).toBeTruthy();
	});
});
