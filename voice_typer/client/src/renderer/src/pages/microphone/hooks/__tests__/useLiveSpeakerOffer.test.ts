import { act, renderHook } from "@testing-library/react";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	__resetLiveSpeakerOfferForTests,
	SPEAKER_OFFER_TARGET_LEVEL,
	SPEAKER_OFFER_TOAST_ID,
	useLiveSpeakerOffer,
} from "../useLiveSpeakerOffer";

const call = vi.fn();

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call }),
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

interface ToastOpts {
	id?: string;
	duration?: number;
	description?: string;
	action?: { label: string; onClick: () => void };
	cancel?: { label: string; onClick: () => void };
}

function offerOpts(): ToastOpts {
	const calls = (toast.info as ReturnType<typeof vi.fn>).mock.calls;
	const entry = calls[calls.length - 1] ?? [];
	return (entry[1] ?? {}) as ToastOpts;
}

/** Flush the hook's awaited status read. */
function settle() {
	return act(async () => {
		await new Promise<void>((resolve) => setTimeout(resolve, 0));
	});
}

beforeEach(() => {
	vi.clearAllMocks();
	__resetLiveSpeakerOfferForTests();
	call.mockResolvedValue({ output_level: 0.5, available: true });
});

afterEach(() => {
	__resetLiveSpeakerOfferForTests();
});

describe("useLiveSpeakerOffer", () => {
	it("does nothing while the preview is stopped", async () => {
		call.mockResolvedValue({ output_level: 0.99 });
		renderHook(() => useLiveSpeakerOffer(false));
		await settle();

		expect(call).not.toHaveBeenCalled();
		expect(toast.info).not.toHaveBeenCalled();
	});

	it("offers [Lower to 75%] and [Keep as is] when the output is above 90%", async () => {
		call.mockResolvedValue({ output_level: 0.95 });
		renderHook(() => useLiveSpeakerOffer(true));
		await settle();

		expect(call).toHaveBeenCalledWith("get_volume_backend_status");
		expect(toast.info).toHaveBeenCalledTimes(1);
		const opts = offerOpts();
		expect(opts.id).toBe(SPEAKER_OFFER_TOAST_ID);
		expect(opts.duration).toBe(Number.POSITIVE_INFINITY);
		// Real i18n copy (not a mocked t): proves the en locale keys resolve.
		expect(opts.action?.label).toContain("75%");
		expect(opts.cancel?.label.length).toBeGreaterThan(0);
	});

	it("writes 75% only when the user presses the offer's button", async () => {
		call.mockResolvedValue({ output_level: 0.95 });
		renderHook(() => useLiveSpeakerOffer(true));
		await settle();

		expect(call).toHaveBeenCalledTimes(1);
		offerOpts().action?.onClick();

		expect(call).toHaveBeenLastCalledWith("set_output_volume", {
			level: SPEAKER_OFFER_TARGET_LEVEL,
		});
		expect(toast.dismiss).toHaveBeenCalledWith(SPEAKER_OFFER_TOAST_ID);
	});

	it("dismisses without touching the speakers on [Keep as is]", async () => {
		call.mockResolvedValue({ output_level: 0.95 });
		renderHook(() => useLiveSpeakerOffer(true));
		await settle();

		offerOpts().cancel?.onClick();

		expect(toast.dismiss).toHaveBeenCalledWith(SPEAKER_OFFER_TOAST_ID);
		expect(call).toHaveBeenCalledTimes(1); // the read only
	});

	it("never offers at or below the threshold", async () => {
		call.mockResolvedValue({ output_level: 0.9 });
		renderHook(() => useLiveSpeakerOffer(true));
		await settle();

		expect(toast.info).not.toHaveBeenCalled();
	});

	it("remembers the answer for the session (one check only)", async () => {
		call.mockResolvedValue({ output_level: 0.95 });
		const { rerender } = renderHook(
			({ listening }: { listening: boolean }) => useLiveSpeakerOffer(listening),
			{ initialProps: { listening: true } },
		);
		await settle();
		expect(call).toHaveBeenCalledTimes(1);

		rerender({ listening: false });
		rerender({ listening: true });
		await settle();

		expect(call).toHaveBeenCalledTimes(1);
		expect(toast.info).toHaveBeenCalledTimes(1);
	});

	it("re-arms when the preview stops mid-check", async () => {
		let release: (value: unknown) => void = () => undefined;
		call.mockImplementationOnce(
			() =>
				new Promise((resolve) => {
					release = resolve;
				}),
		);
		const { rerender } = renderHook(
			({ listening }: { listening: boolean }) => useLiveSpeakerOffer(listening),
			{ initialProps: { listening: true } },
		);

		// Stop before the status read resolves: nothing is offered.
		rerender({ listening: false });
		await act(async () => {
			release({ output_level: 0.95 });
			await new Promise<void>((resolve) => setTimeout(resolve, 0));
		});
		expect(toast.info).not.toHaveBeenCalled();

		// The next start re-checks instead of being stuck at "checking".
		call.mockResolvedValue({ output_level: 0.95 });
		rerender({ listening: true });
		await settle();

		expect(toast.info).toHaveBeenCalledTimes(1);
	});

	it("leaves the offer armed when the status read fails", async () => {
		call.mockRejectedValueOnce(new Error("backend not connected"));
		const { rerender } = renderHook(
			({ listening }: { listening: boolean }) => useLiveSpeakerOffer(listening),
			{ initialProps: { listening: true } },
		);
		await settle();
		expect(toast.info).not.toHaveBeenCalled();

		rerender({ listening: false });
		call.mockResolvedValue({ output_level: 0.98 });
		rerender({ listening: true });
		await settle();

		expect(toast.info).toHaveBeenCalledTimes(1);
	});

	it("treats an unreadable output level as no offer, without retrying", async () => {
		call.mockResolvedValue({ output_level: null });
		const { rerender } = renderHook(
			({ listening }: { listening: boolean }) => useLiveSpeakerOffer(listening),
			{ initialProps: { listening: true } },
		);
		await settle();
		expect(toast.info).not.toHaveBeenCalled();

		rerender({ listening: false });
		rerender({ listening: true });
		await settle();

		expect(call).toHaveBeenCalledTimes(1);
	});
});
