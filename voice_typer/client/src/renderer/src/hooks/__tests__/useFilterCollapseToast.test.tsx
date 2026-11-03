import { renderHook } from "@testing-library/react";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
	FILTER_COLLAPSE_TOAST_ID,
	useFilterCollapseToast,
} from "@/hooks/useFilterCollapseToast";
import { SNACKBAR_DEFAULT_DURATION_MS } from "@/hooks/useSnackbar";
import type { TranslateFn } from "@/i18n/translate-types";

// Capture the handler usePythonEvent registers so we can fire the backend push.
const registered = new Map<string, (data?: unknown) => unknown>();
const mockT: TranslateFn = (key) => key;
const onOpenMicrophone = vi.fn();

vi.mock("@/hooks/usePython", () => ({
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

function fire(data?: unknown) {
	const handler = registered.get("filter_collapse");
	expect(handler, "no handler registered for filter_collapse").toBeTruthy();
	handler?.(data);
}

interface ToastOpts {
	id?: string;
	description?: string;
	duration?: number;
	action?: { label: string; onClick: () => void };
}

function lastWarning(): { message: unknown; opts: ToastOpts } {
	const calls = (toast.warning as ReturnType<typeof vi.fn>).mock.calls;
	const entry = calls[calls.length - 1] ?? [];
	return { message: entry[0], opts: (entry[1] ?? {}) as ToastOpts };
}

beforeEach(() => {
	registered.clear();
	vi.clearAllMocks();
});

describe("useFilterCollapseToast", () => {
	it("subscribes to the filter-divergence push event", () => {
		renderHook(() => useFilterCollapseToast(mockT, onOpenMicrophone));
		expect(registered.has("filter_collapse")).toBe(true);
	});

	it("shows one warning that names the degradation", () => {
		renderHook(() => useFilterCollapseToast(mockT, onOpenMicrophone));
		fire({
			reason: "collapse",
			raw_db: -20.5,
			filtered_db: -70.2,
			delta_db: 49.7,
			preset: "auto",
			method: "dpdfnet",
		});

		const { message, opts } = lastWarning();
		expect(message).toBe("degradation.filterCollapse");
		expect(opts.description).toBe("degradation.filterCollapseHint");
		expect(opts.id).toBe(FILTER_COLLAPSE_TOAST_ID);
		expect(opts.duration).toBe(SNACKBAR_DEFAULT_DURATION_MS.error);
	});

	it("keeps the method and dB detail out of the user copy", () => {
		renderHook(() => useFilterCollapseToast(mockT, onOpenMicrophone));
		fire({ reason: "collapse", method: "dpdfnet", delta_db: 49.7 });

		const { message, opts } = lastWarning();
		const copy = `${String(message)} ${String(opts.description)}`;
		expect(copy).not.toContain("dpdfnet");
		expect(copy).not.toMatch(/\bdB\b/);
	});

	it("offers the Microphone page so the filter can be changed", () => {
		renderHook(() => useFilterCollapseToast(mockT, onOpenMicrophone));
		fire({ reason: "silent_take", method: "gtcrn" });

		const { opts } = lastWarning();
		expect(opts.action?.label).toBe("nav.microphone");
		opts.action?.onClick();
		expect(onOpenMicrophone).toHaveBeenCalledTimes(1);
	});

	it("reports the meter's raw fallback with its own copy", () => {
		renderHook(() => useFilterCollapseToast(mockT, onOpenMicrophone));
		fire({
			reason: "monitor_collapse",
			raw_db: -20.1,
			filtered_db: -71.4,
			delta_db: 51.3,
			preset: "auto",
			method: "gtcrn",
		});

		const { message, opts } = lastWarning();
		expect(message).toBe("degradation.filterCollapseMonitor");
		// Same remedy on the same page, so the hint is shared, not duplicated.
		expect(opts.description).toBe("degradation.filterCollapseHint");
		expect(opts.action?.label).toBe("nav.microphone");
	});

	it("keeps the dictation copy for the dictation reasons", () => {
		renderHook(() => useFilterCollapseToast(mockT, onOpenMicrophone));
		fire({ reason: "collapse" });
		expect(lastWarning().message).toBe("degradation.filterCollapse");

		fire({ reason: "silent_take" });
		expect(lastWarning().message).toBe("degradation.filterCollapse");
	});

	it("still warns when the payload is malformed", () => {
		renderHook(() => useFilterCollapseToast(mockT, onOpenMicrophone));
		fire(undefined);

		expect(lastWarning().message).toBe("degradation.filterCollapse");
	});
});
