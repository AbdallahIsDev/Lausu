import { renderHook } from "@testing-library/react";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
	PACK_UPDATE_TOAST_ID,
	usePackUpdateToast,
} from "@/hooks/usePackUpdateToast";

// Capture the handlers usePythonEvent registers so we can fire them.
const registered = new Map<string, (data?: unknown) => unknown>();
const mockT = vi.fn((key: string) => key);
const onViewDetails = vi.fn();

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: vi.fn() }),
	usePythonEvent: (type: string, handler: (data?: unknown) => unknown) => {
		registered.set(type, handler);
	},
}));

vi.mock("sonner", () => ({
	toast: {
		error: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
		success: vi.fn(),
		dismiss: vi.fn(),
	},
}));

function fire(type: string, data?: unknown) {
	const handler = registered.get(type);
	expect(handler, `no handler registered for ${type}`).toBeTruthy();
	handler?.(data);
}

beforeEach(() => {
	registered.clear();
	vi.clearAllMocks();
});

describe("usePackUpdateToast", () => {
	it("registers handlers for the pack download lifecycle events", () => {
		renderHook(() => usePackUpdateToast(mockT, onViewDetails));
		for (const type of [
			"offline_pack_download_started",
			"offline_pack_download_progress",
			"offline_pack_download_completed",
			"offline_pack_ready",
			"offline_pack_download_failed",
			"offline_pack_corrupt",
			"offline_pack_outdated",
			"offline_pack_missing",
			"offline_pack_verified",
			"worker_started",
			"worker_crashed",
			"worker_unloaded",
		]) {
			expect(registered.has(type), `missing handler for ${type}`).toBe(true);
		}
	});

	it("shows a sticky info toast with the fixed id when a download starts", () => {
		renderHook(() => usePackUpdateToast(mockT, onViewDetails));
		fire("offline_pack_download_started");

		expect(toast.info).toHaveBeenCalledTimes(1);
		expect(toast.info).toHaveBeenCalledWith(
			"pack.updateTitle",
			expect.objectContaining({
				id: PACK_UPDATE_TOAST_ID,
				duration: Number.POSITIVE_INFINITY,
			}),
		);
	});

	it("replaces the sticky toast with live percent on progress", () => {
		renderHook(() => usePackUpdateToast(mockT, onViewDetails));
		fire("offline_pack_download_started");
		fire("offline_pack_download_progress", { progress: 42 });

		expect(toast.info).toHaveBeenCalledTimes(2);
		const [, opts] =
			(toast.info as ReturnType<typeof vi.fn>).mock.calls[1] ?? [];
		expect(opts).toMatchObject({
			id: PACK_UPDATE_TOAST_ID,
			duration: Number.POSITIVE_INFINITY,
		});
	});

	it("clears the sticky toast and shows success when ready", () => {
		renderHook(() => usePackUpdateToast(mockT, onViewDetails));
		fire("offline_pack_download_started");
		fire("offline_pack_ready");

		expect(toast.dismiss).toHaveBeenCalledWith(PACK_UPDATE_TOAST_ID);
		expect(toast.success).toHaveBeenCalledTimes(1);
		expect(toast.success).toHaveBeenCalledWith(
			"pack.updateReady",
			expect.objectContaining({ duration: 3000 }),
		);
	});

	it("clears the sticky toast and shows an error on failure", () => {
		renderHook(() => usePackUpdateToast(mockT, onViewDetails));
		fire("offline_pack_download_started");
		fire("offline_pack_download_failed");

		expect(toast.dismiss).toHaveBeenCalledWith(PACK_UPDATE_TOAST_ID);
		expect(toast.error).toHaveBeenCalledTimes(1);
	});

	it("shows the sticky preparing toast with Details when the pack is missing", () => {
		renderHook(() => usePackUpdateToast(mockT, onViewDetails));
		fire("offline_pack_missing");

		expect(toast.info).toHaveBeenCalledTimes(1);
		const [, opts] =
			(toast.info as ReturnType<typeof vi.fn>).mock.calls[0] ?? [];
		expect(opts).toMatchObject({
			id: PACK_UPDATE_TOAST_ID,
			duration: Number.POSITIVE_INFINITY,
		});
		const action = (opts as { action?: { label: string; onClick: () => void } })
			.action;
		expect(action?.label).toBe("pack.viewDetails");
		action?.onClick();
		expect(onViewDetails).toHaveBeenCalledTimes(1);
	});

	it("shows the sticky preparing toast on verified and worker-started", () => {
		renderHook(() => usePackUpdateToast(mockT, onViewDetails));
		fire("offline_pack_verified");
		fire("worker_started");

		expect(toast.info).toHaveBeenCalledTimes(2);
		for (const call of (toast.info as ReturnType<typeof vi.fn>).mock.calls) {
			expect(call[1]).toMatchObject({
				id: PACK_UPDATE_TOAST_ID,
				duration: Number.POSITIVE_INFINITY,
			});
		}
	});

	it("clears the sticky toast and shows an error when the worker crashes", () => {
		renderHook(() => usePackUpdateToast(mockT, onViewDetails));
		fire("offline_pack_download_started");
		fire("worker_crashed");

		expect(toast.dismiss).toHaveBeenCalledWith(PACK_UPDATE_TOAST_ID);
		expect(toast.error).toHaveBeenCalledTimes(1);
		expect(toast.error).toHaveBeenCalledWith(
			"pack.packStateWorkerCrashed",
			expect.objectContaining({ duration: 8000 }),
		);
	});

	it("clears the sticky toast and shows info when the worker unloads", () => {
		renderHook(() => usePackUpdateToast(mockT, onViewDetails));
		fire("offline_pack_download_started");
		fire("worker_unloaded");

		expect(toast.dismiss).toHaveBeenCalledWith(PACK_UPDATE_TOAST_ID);
		expect(toast.info).toHaveBeenCalledTimes(2);
		expect(toast.info).toHaveBeenLastCalledWith(
			"pack.packStateWorkerUnloaded",
			expect.objectContaining({ duration: 4000 }),
		);
	});

	it("shows a sticky warning with the Details action when outdated", () => {
		renderHook(() => usePackUpdateToast(mockT, onViewDetails));
		fire("offline_pack_outdated", { version: "1.0.0", min_proto_version: 2 });

		expect(toast.warning).toHaveBeenCalledTimes(1);
		const [, opts] =
			(toast.warning as ReturnType<typeof vi.fn>).mock.calls[0] ?? [];
		expect(opts).toMatchObject({
			id: PACK_UPDATE_TOAST_ID,
			duration: Number.POSITIVE_INFINITY,
		});
		const action = (opts as { action?: { label: string; onClick: () => void } })
			.action;
		expect(action?.label).toBe("pack.viewDetails");
		action?.onClick();
		expect(onViewDetails).toHaveBeenCalledTimes(1);
	});
});
