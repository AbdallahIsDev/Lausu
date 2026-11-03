import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
	denoiserLabel,
	useDenoiserFallbackNote,
} from "@/pages/microphone/hooks/useDenoiserFallbackNote";

const call = vi.fn();

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call }),
}));

// The copy itself lives in the locale files (pinned by the i18n parity test);
// this suite asserts WHICH key is used and with which names.
vi.mock("@/i18n/i18n", () => ({
	t: (key: string, params?: Record<string, string>) =>
		params ? `${key}|${params.requested}|${params.effective}` : key,
}));

beforeEach(() => {
	call.mockReset();
});

describe("denoiserLabel", () => {
	it("uses the selector's own visible names", () => {
		expect(denoiserLabel("dpdfnet")).toBe("DPDFNet");
		expect(denoiserLabel("gtcrn")).toBe("GTCRN");
	});

	it("falls back to the raw id for an unknown method", () => {
		expect(denoiserLabel("speex")).toBe("SPEEX");
	});
});

describe("useDenoiserFallbackNote", () => {
	it("names the fallback backend in plain language", async () => {
		call.mockResolvedValue({
			noise_suppression: {
				requested: "dpdfnet",
				effective: "gtcrn",
				degraded: true,
				reason_code: "backend_unavailable",
			},
		});

		const { result } = renderHook(() => useDenoiserFallbackNote("dpdfnet"));

		await waitFor(() =>
			expect(result.current).toBe(
				"settings.audioEnhancement.denoiserFallback|DPDFNet|GTCRN",
			),
		);
		expect(call).toHaveBeenCalledWith("get_status");
	});

	it("stays silent when the selected backend is the serving one", async () => {
		call.mockResolvedValue({
			noise_suppression: {
				requested: "dpdfnet",
				effective: "dpdfnet",
				degraded: false,
				reason_code: "",
			},
		});

		const { result } = renderHook(() => useDenoiserFallbackNote("dpdfnet"));

		await waitFor(() => expect(call).toHaveBeenCalled());
		expect(result.current).toBeNull();
	});

	it("stays silent when the payload has no audio status", async () => {
		call.mockResolvedValue({ status: "idle" });

		const { result } = renderHook(() => useDenoiserFallbackNote("dpdfnet"));

		await waitFor(() => expect(call).toHaveBeenCalled());
		expect(result.current).toBeNull();
	});

	it("never breaks the page when the status call fails", async () => {
		call.mockRejectedValue(new Error("sidecar not connected"));

		const { result } = renderHook(() => useDenoiserFallbackNote("dpdfnet"));

		await waitFor(() => expect(call).toHaveBeenCalled());
		expect(result.current).toBeNull();
	});

	it("reads the meter chain's block, not the dictation one", async () => {
		call.mockResolvedValue({
			noise_suppression: {
				requested: "dpdfnet",
				effective: "dpdfnet",
				degraded: false,
				reason_code: "",
			},
			level_monitor_noise_suppression: {
				requested: "dpdfnet",
				effective: "gtcrn",
				degraded: true,
				reason_code: "backend_unavailable",
			},
		});

		const { result } = renderHook(() => useDenoiserFallbackNote("dpdfnet"));

		await waitFor(() =>
			expect(result.current).toBe(
				"settings.audioEnhancement.denoiserFallback|DPDFNet|GTCRN",
			),
		);
	});

	it("falls back to the dictation block when the meter has no chain", async () => {
		call.mockResolvedValue({
			noise_suppression: {
				requested: "dpdfnet",
				effective: "gtcrn",
				degraded: true,
				reason_code: "backend_unavailable",
			},
			level_monitor_noise_suppression: null,
		});

		const { result } = renderHook(() => useDenoiserFallbackNote("dpdfnet"));

		await waitFor(() =>
			expect(result.current).toBe(
				"settings.audioEnhancement.denoiserFallback|DPDFNet|GTCRN",
			),
		);
	});

	it("re-reads the status when the selected method changes", async () => {
		call.mockResolvedValue({
			noise_suppression: {
				requested: "dpdfnet",
				effective: "gtcrn",
				degraded: true,
				reason_code: "backend_unavailable",
			},
		});

		const { rerender } = renderHook(
			({ method }: { method: string }) => useDenoiserFallbackNote(method),
			{ initialProps: { method: "dpdfnet" } },
		);
		await waitFor(() => expect(call).toHaveBeenCalledTimes(1));

		rerender({ method: "gtcrn" });

		await waitFor(() => expect(call).toHaveBeenCalledTimes(2));
	});
});
