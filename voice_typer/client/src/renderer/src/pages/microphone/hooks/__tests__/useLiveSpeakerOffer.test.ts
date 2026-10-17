import { act, render, renderHook, screen } from "@testing-library/react";
import { createElement, isValidElement } from "react";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SpeakerOfferActions } from "../SpeakerOfferActions";
import {
	__resetLiveSpeakerOfferForTests,
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
	action?: unknown;
	cancel?: unknown;
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

	it("offers Lower + Keep as ONE div group when the output is above 90%", async () => {
		call.mockResolvedValue({ output_level: 0.95 });
		renderHook(() => useLiveSpeakerOffer(true));
		await settle();

		expect(call).toHaveBeenCalledWith("get_volume_backend_status");
		expect(toast.info).toHaveBeenCalledTimes(1);
		const opts = offerOpts();
		expect(opts.id).toBe(SPEAKER_OFFER_TOAST_ID);
		expect(opts.duration).toBe(Number.POSITIVE_INFINITY);
		// Honest DOM: the action slot carries ONE element holding both buttons.
		expect(isValidElement(opts.action)).toBe(true);
		expect(opts.cancel).toBeUndefined();
	});

	it("the action group renders Lower + Keep side-by-side (Lower left, Keep right)", () => {
		render(
			createElement(SpeakerOfferActions, {
				lowerLabel: "Lower to 75%",
				keepLabel: "Keep as is",
				onLower: () => undefined,
				onKeep: () => undefined,
			}),
		);
		const keep = screen.getByRole("button", { name: "Keep as is" });
		const lower = screen.getByRole("button", { name: "Lower to 75%" });
		// DOM order: Lower first (the offered action, left in LTR), Keep
		// second (de-emphasized ghost, right) — matches the pre-div-group
		// action/cancel order the toast used before the honest group landed.
		expect(
			lower.compareDocumentPosition(keep) & Node.DOCUMENT_POSITION_FOLLOWING,
		).toBeTruthy();
	});

	it("the group buttons call through (Lower writes, Keep only dismisses)", () => {
		const onLower = vi.fn();
		const onKeep = vi.fn();
		render(
			createElement(SpeakerOfferActions, {
				lowerLabel: "Lower to 75%",
				keepLabel: "Keep as is",
				onLower,
				onKeep,
			}),
		);
		screen.getByRole("button", { name: "Lower to 75%" }).click();
		expect(onLower).toHaveBeenCalledTimes(1);
		screen.getByRole("button", { name: "Keep as is" }).click();
		expect(onKeep).toHaveBeenCalledTimes(1);
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

	it("dismisses the offer exactly once when listening stops", async () => {
		call.mockResolvedValue({ output_level: 0.95 });
		const { rerender } = renderHook(
			({ listening }: { listening: boolean }) => useLiveSpeakerOffer(listening),
			{ initialProps: { listening: true } },
		);
		await settle();
		expect(toast.info).toHaveBeenCalledTimes(1);

		rerender({ listening: false });

		expect(toast.dismiss).toHaveBeenCalledTimes(1);
		expect(toast.dismiss).toHaveBeenCalledWith(SPEAKER_OFFER_TOAST_ID);
		// The stop does not break the session memory: a restart re-checks
		// nothing and never re-offers.
		rerender({ listening: true });
		await settle();
		expect(toast.info).toHaveBeenCalledTimes(1);
		expect(toast.dismiss).toHaveBeenCalledTimes(1);
	});

	it("never dismisses while the preview stays stopped", () => {
		renderHook(() => useLiveSpeakerOffer(false));

		expect(toast.dismiss).not.toHaveBeenCalled();
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
