import { renderHook } from "@testing-library/react";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { buttonVariants } from "@/components/ui/button";
import { MIC_GUARD_TOAST_ID, useMicGuardToast } from "@/hooks/useMicGuardToast";
import type { TranslateFn } from "@/i18n/translate-types";

// Capture the handler usePythonEvent registers so we can fire the backend push.
const registered = new Map<string, (data?: unknown) => unknown>();
const call = vi.fn().mockResolvedValue({});
// Interpolating mock so the {percent} parameter is visible in assertions.
const mockT: TranslateFn = (key, params) =>
	params ? `${key}:${JSON.stringify(params)}` : key;

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call }),
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
	const handler = registered.get("microphone_volume_lowered");
	expect(
		handler,
		"no handler registered for microphone_volume_lowered",
	).toBeTruthy();
	handler?.(data);
}

interface ToastOpts {
	id?: string;
	duration?: number;
	description?: string;
	action?: { label: string; onClick: () => void };
	cancel?: { label: string; onClick: () => void };
	classNames?: { actionButton?: string };
}

function lastWarningOpts(): ToastOpts {
	const calls = (toast.warning as ReturnType<typeof vi.fn>).mock.calls;
	const entry = calls[calls.length - 1] ?? [];
	return (entry[1] ?? {}) as ToastOpts;
}

beforeEach(() => {
	registered.clear();
	vi.clearAllMocks();
});

describe("useMicGuardToast", () => {
	it("subscribes to the mic-guard push event", () => {
		renderHook(() => useMicGuardToast(mockT));
		expect(registered.has("microphone_volume_lowered")).toBe(true);
	});

	it("stays silent when the guard already restored the knob", () => {
		renderHook(() => useMicGuardToast(mockT));
		fire({ level: 0.92, restored: true, can_set: true });

		expect(toast.warning).not.toHaveBeenCalled();
	});

	it("retires the sticky message once the guard restores on its own", () => {
		renderHook(() => useMicGuardToast(mockT));
		fire({ level: 0.92, restored: false, can_set: true });
		expect(toast.warning).toHaveBeenCalledTimes(1);

		// Anti-flap budget refilled: the guard puts the knob back itself.
		fire({ level: 1, restored: true, can_set: true });

		expect(toast.dismiss).toHaveBeenCalledWith(MIC_GUARD_TOAST_ID);
		expect(toast.warning).toHaveBeenCalledTimes(1);
	});

	it("shows a sticky message with the percent and a [Back to 100%] button", () => {
		renderHook(() => useMicGuardToast(mockT));
		fire({ level: 0.92, restored: false, can_set: true });

		expect(toast.warning).toHaveBeenCalledTimes(1);
		const [message] =
			(toast.warning as ReturnType<typeof vi.fn>).mock.calls[0] ?? [];
		expect(message).toContain("92");
		const opts = lastWarningOpts();
		expect(opts.id).toBe(MIC_GUARD_TOAST_ID);
		expect(opts.duration).toBe(Number.POSITIVE_INFINITY);
		expect(opts.action?.label).toBe("micGuard.backTo100");
	});

	it("writes the real device value to 100% and clears the toast on press", () => {
		renderHook(() => useMicGuardToast(mockT));
		fire({ level: 0.88, restored: false, can_set: true });

		lastWarningOpts().action?.onClick();

		expect(toast.dismiss).toHaveBeenCalledWith(MIC_GUARD_TOAST_ID);
		expect(call).toHaveBeenCalledWith("set_microphone_volume", { level: 1 });
	});

	it("pins the [Back to 100%] action to the outline xs Button (per-toast)", () => {
		// The button carries its OWN classes on the toast, so sonner's
		// per-toast merge (after the global default) renders it as the
		// outline xs Button regardless of how the global default evolves.
		renderHook(() => useMicGuardToast(mockT));
		fire({ level: 0.92, restored: false, can_set: true });

		expect(lastWarningOpts().classNames?.actionButton).toBe(
			buttonVariants({ variant: "outline", size: "xs" }),
		);
	});

	it("lone action button carries outline geometry classes (left edge owned by CSS)", () => {
		// The class string owns geometry (xs padding/font); the CSS
		// kind-scoped rule owns fill + left edge (see index.css: sonner's
		// cn() is a plain join, so per-toast classes land beside globals
		// and the cascade decides — the rule pins the lone-button look).
		renderHook(() => useMicGuardToast(mockT));
		fire({ level: 0.92, restored: false, can_set: true });

		const cls = lastWarningOpts().classNames?.actionButton ?? "";
		expect(cls).toContain("px-2.5");
		expect(cls).toContain("text-xs");
		expect(cls).not.toContain("bg-primary");
	});

	it("drops the button on a device without settable gain (message only)", () => {
		renderHook(() => useMicGuardToast(mockT));
		fire({ level: 0.5, restored: false, can_set: false });

		expect(toast.warning).toHaveBeenCalledTimes(1);
		expect(lastWarningOpts().action).toBeUndefined();
		// No button → no per-toast button classes either.
		expect(lastWarningOpts().classNames).toBeUndefined();
	});

	it("ignores a payload with no usable level", () => {
		renderHook(() => useMicGuardToast(mockT));
		fire({ restored: false, can_set: true });
		fire({ level: "loud", restored: false, can_set: true });
		fire(undefined);

		expect(toast.warning).not.toHaveBeenCalled();
	});

	it("replaces itself in place on a second detection (fixed id)", () => {
		renderHook(() => useMicGuardToast(mockT));
		fire({ level: 0.9, restored: false, can_set: true });
		fire({ level: 0.8, restored: false, can_set: true });

		expect(toast.warning).toHaveBeenCalledTimes(2);
		for (const [, opts] of (toast.warning as ReturnType<typeof vi.fn>).mock
			.calls) {
			expect((opts as { id?: string }).id).toBe(MIC_GUARD_TOAST_ID);
		}
	});
});
