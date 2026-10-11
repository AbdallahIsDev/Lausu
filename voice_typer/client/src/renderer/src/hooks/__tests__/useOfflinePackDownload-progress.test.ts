import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { usePythonEventMock } = vi.hoisted(() => ({
	usePythonEventMock: vi.fn(),
}));

vi.mock("@/hooks/usePython", () => ({
	usePythonEvent: usePythonEventMock,
}));

import { useOfflinePackDownload } from "@/hooks/useOfflinePackDownload";

function getHandler(
	eventName: string,
): (data?: Record<string, unknown>) => (() => void) | undefined {
	const call = usePythonEventMock.mock.calls.find((c) => c[0] === eventName);
	if (!call) throw new Error(`no subscription for "${eventName}"`);
	return call[1] as (
		data?: Record<string, unknown>,
	) => (() => void) | undefined;
}

beforeEach(() => {
	usePythonEventMock.mockReset();
});

describe("useOfflinePackDownload, progress % (slice C)", () => {
	it("initial progress is null", () => {
		const { result } = renderHook(() => useOfflinePackDownload());
		expect(result.current.progress).toBeNull();
	});

	it("started sets progress 0", () => {
		const { result } = renderHook(() => useOfflinePackDownload());
		act(() => getHandler("offline_pack_download_started")());
		expect(result.current.status).toBe("downloading");
		expect(result.current.progress).toBe(0);
	});

	it("progress event sets percent from the live payload", () => {
		const { result } = renderHook(() => useOfflinePackDownload());
		act(() => getHandler("offline_pack_download_progress")({ progress: 37 }));
		expect(result.current.status).toBe("downloading");
		expect(result.current.progress).toBe(37);
	});

	it("progress accepts the legacy percent field and clamps", () => {
		const { result } = renderHook(() => useOfflinePackDownload());
		act(() => getHandler("offline_pack_download_progress")({ percent: 50 }));
		expect(result.current.progress).toBe(50);
		act(() => getHandler("offline_pack_download_progress")({ progress: 250 }));
		expect(result.current.progress).toBe(100);
		act(() => getHandler("offline_pack_download_progress")({ progress: -4 }));
		expect(result.current.progress).toBe(0);
	});

	it("ignores non-numeric payloads, keeps last percent", () => {
		const { result } = renderHook(() => useOfflinePackDownload());
		act(() => getHandler("offline_pack_download_progress")({ progress: 20 }));
		act(() =>
			getHandler("offline_pack_download_progress")({ progress: "half" }),
		);
		expect(result.current.progress).toBe(20);
		act(() => getHandler("offline_pack_download_progress")());
		expect(result.current.progress).toBe(20);
	});

	it("completed / verified / ready clear progress", () => {
		const { result } = renderHook(() => useOfflinePackDownload());
		act(() => getHandler("offline_pack_download_progress")({ progress: 80 }));
		act(() => getHandler("offline_pack_download_completed")());
		expect(result.current.progress).toBeNull();
		act(() => getHandler("offline_pack_download_started")());
		act(() => getHandler("offline_pack_download_progress")({ progress: 10 }));
		act(() => getHandler("offline_pack_verified")());
		expect(result.current.progress).toBeNull();
		act(() => getHandler("offline_pack_download_started")());
		act(() => getHandler("offline_pack_ready")());
		expect(result.current.progress).toBeNull();
		expect(result.current.isReady).toBe(true);
	});

	it("failed / missing / corrupt clear progress", () => {
		const { result } = renderHook(() => useOfflinePackDownload());
		act(() => getHandler("offline_pack_download_progress")({ progress: 60 }));
		act(() => getHandler("offline_pack_download_failed")({ error: "x" }));
		expect(result.current.progress).toBeNull();
		act(() => getHandler("offline_pack_download_started")());
		act(() => getHandler("offline_pack_missing")());
		expect(result.current.progress).toBeNull();
		act(() => getHandler("offline_pack_download_started")());
		act(() => getHandler("offline_pack_corrupt")({ reason: "y" }));
		expect(result.current.progress).toBeNull();
	});
});
