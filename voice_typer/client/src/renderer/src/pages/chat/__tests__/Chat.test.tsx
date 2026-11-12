// Chat page: bridge wiring, phase rendering and the push-to-talk lifecycle.
//
// The mocked bridge is the ONLY dependency: `chat_state` / `get_config` answer
// on mount, `chat_turn` is driven through the captured event handler, and the
// command names are asserted as literals so a rename in the backend surfaces
// here (C-UXERR-1: no raw exception text reaches the page).

import {
	act,
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
	navigationMock,
	pythonMock,
	resetStableMocks,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";
import { useConsentGateStore } from "@/lib/consentGate";

const { mockCall, mockNavigate, pythonEventHandlers } = stableMocks;

vi.mock("@/hooks/usePython", () =>
	pythonMock({ captureEvents: stableMocks.pythonEventHandlers }),
);
vi.mock("@/hooks/useNavigation", () => navigationMock());
vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());

const CONFIGURED = {
	llm_provider: "openrouter",
	llm_model_id: "vendor/model",
	voice_biometric_consent: true,
};

function bridge(options: {
	config?: Record<string, unknown>;
	messages?: { role: string; text: string }[];
	phase?: string;
	started?: boolean;
	/** Deferred `chat_state` reply, to drive the pre-hydration queue. */
	state?: Promise<unknown>;
}) {
	mockCall.mockImplementation((type: string) => {
		switch (type) {
			case "chat_state":
				if (options.state) return options.state;
				return Promise.resolve({
					messages: options.messages ?? [],
					busy: false,
					phase: options.phase ?? "idle",
				});
			case "get_config":
				return Promise.resolve(options.config ?? CONFIGURED);
			case "chat_listen_start":
				return Promise.resolve({
					started: options.started ?? true,
					sample_rate: 16000,
				});
			case "chat_listen_stop":
				return Promise.resolve({ accepted: true });
			case "chat_reset":
				return Promise.resolve({ ok: true });
			default:
				return Promise.resolve({});
		}
	});
}

async function renderChat() {
	const { default: ChatPage } = await import("@/pages/Chat");
	const utils = render(<ChatPage />);
	await waitFor(() =>
		expect(screen.queryByText(/Loading conversation/)).toBeNull(),
	);
	return utils;
}

function pushTurn(payload: Record<string, unknown>) {
	act(() => {
		pythonEventHandlers.chat_turn?.(payload);
	});
}

describe("Chat page", () => {
	beforeEach(() => {
		resetStableMocks();
		localStorage.clear();
		useConsentGateStore.getState().close();
	});

	afterEach(() => {
		cleanup();
	});

	it("hydrates from chat_state and renders the empty state", async () => {
		bridge({});
		await renderChat();

		expect(mockCall).toHaveBeenCalledWith("chat_state");
		expect(mockCall).toHaveBeenCalledWith("get_config");
		expect(screen.getByText("No messages yet")).toBeTruthy();
		expect(screen.getByText("Hold the button and speak")).toBeTruthy();
		expect(screen.getByTestId("chat-push-to-talk")).toHaveAttribute(
			"aria-pressed",
			"false",
		);
	});

	it("renders a reattached transcript from chat_state", async () => {
		bridge({
			messages: [
				{ role: "user", text: "earlier question" },
				{ role: "assistant", text: "earlier answer" },
			],
		});
		await renderChat();

		expect(screen.getByText("earlier question")).toBeTruthy();
		expect(screen.getByText("earlier answer")).toBeTruthy();
	});

	it("does not duplicate a queued turn the snapshot already carries", async () => {
		// A turn is in flight and the user leaves Chat and comes back: the
		// `chat_turn` frame lands while `chat_state` is still in flight, and the
		// snapshot it resolves with already contains that user message.
		let releaseState!: () => void;
		const gate = new Promise<void>((resolve) => {
			releaseState = resolve;
		});
		const state = gate.then(() => ({
			messages: [{ role: "user", text: "unique-probe-sentence" }],
			busy: true,
			// Deliberately idle: only the replayed event can move the phase.
			phase: "idle",
		}));
		bridge({ state });

		const { default: ChatPage } = await import("@/pages/Chat");
		render(<ChatPage />);

		pushTurn({
			phase: "thinking",
			role: "user",
			text: "unique-probe-sentence",
		});

		await act(async () => {
			releaseState();
			await gate;
		});
		await waitFor(() =>
			expect(screen.queryByText(/Loading conversation/)).toBeNull(),
		);

		expect(screen.getAllByText("unique-probe-sentence")).toHaveLength(1);
		expect(screen.getByText("Thinking…")).toBeTruthy();
	});

	it("appends a queued turn the snapshot does not carry", async () => {
		let releaseState!: () => void;
		const gate = new Promise<void>((resolve) => {
			releaseState = resolve;
		});
		const state = gate.then(() => ({
			messages: [],
			busy: true,
			phase: "idle",
		}));
		bridge({ state });

		const { default: ChatPage } = await import("@/pages/Chat");
		render(<ChatPage />);

		pushTurn({
			phase: "thinking",
			role: "user",
			text: "fresh-queued-sentence",
		});

		await act(async () => {
			releaseState();
			await gate;
		});
		await waitFor(() =>
			expect(screen.queryByText(/Loading conversation/)).toBeNull(),
		);

		expect(screen.getAllByText("fresh-queued-sentence")).toHaveLength(1);
		expect(screen.getByText("Thinking…")).toBeTruthy();
	});

	it("renders every phase label the backend publishes", async () => {
		bridge({});
		await renderChat();

		for (const [phase, label] of [
			["listening", "Listening…"],
			["transcribing", "Transcribing…"],
			["thinking", "Thinking…"],
			["speaking", "Speaking…"],
			["idle", "Hold the button and speak"],
		] as const) {
			pushTurn({ phase });
			expect(await screen.findByText(label)).toBeTruthy();
		}
	});

	it("appends the user and assistant turns carried by chat_turn", async () => {
		bridge({});
		await renderChat();

		pushTurn({ phase: "thinking", role: "user", text: "what time is it" });
		pushTurn({ phase: "speaking", role: "assistant", text: "it is noon" });

		expect(await screen.findByText("what time is it")).toBeTruthy();
		expect(await screen.findByText("it is noon")).toBeTruthy();
		expect(screen.getByText("Assistant")).toBeTruthy();
	});

	it("starts capture on pointerdown and stops it on pointerup", async () => {
		bridge({});
		await renderChat();
		const button = screen.getByTestId("chat-push-to-talk");

		fireEvent.pointerDown(button);
		await waitFor(() =>
			expect(mockCall).toHaveBeenCalledWith("chat_listen_start"),
		);
		await waitFor(() =>
			expect(screen.getByTestId("chat-push-to-talk")).toHaveAttribute(
				"aria-pressed",
				"true",
			),
		);

		fireEvent.pointerUp(button);
		await waitFor(() =>
			expect(mockCall).toHaveBeenCalledWith("chat_listen_stop"),
		);
	});

	it("releases capture on pointercancel", async () => {
		bridge({});
		await renderChat();
		const button = screen.getByTestId("chat-push-to-talk");

		fireEvent.pointerDown(button);
		await waitFor(() =>
			expect(mockCall).toHaveBeenCalledWith("chat_listen_start"),
		);
		fireEvent.pointerCancel(button);

		await waitFor(() =>
			expect(mockCall).toHaveBeenCalledWith("chat_listen_stop"),
		);
	});

	it("releases capture when the page unmounts mid-hold", async () => {
		bridge({});
		const { unmount } = await renderChat();
		const button = screen.getByTestId("chat-push-to-talk");

		fireEvent.pointerDown(button);
		await waitFor(() =>
			expect(screen.getByTestId("chat-push-to-talk")).toHaveAttribute(
				"aria-pressed",
				"true",
			),
		);

		unmount();

		await waitFor(() =>
			expect(mockCall).toHaveBeenCalledWith("chat_listen_stop"),
		);
	});

	it("keeps the button disabled while a turn is in flight", async () => {
		bridge({});
		await renderChat();

		pushTurn({ phase: "thinking", role: "user", text: "hello" });

		expect(screen.getByTestId("chat-push-to-talk")).toHaveAttribute(
			"aria-disabled",
			"true",
		);
	});

	it("offers Providers when no language model is selected", async () => {
		bridge({ config: { llm_provider: "", llm_model_id: "" } });
		await renderChat();

		expect(screen.getByText("No language model is selected.")).toBeTruthy();
		const open = screen.getByRole("button", { name: "Open Providers" });
		fireEvent.click(open);
		expect(mockNavigate).toHaveBeenCalledWith("providers");
		expect(screen.getByTestId("chat-push-to-talk")).toHaveAttribute(
			"aria-disabled",
			"true",
		);
	});

	it("renders a provider failure in plain language with a recovery action", async () => {
		bridge({});
		await renderChat();

		pushTurn({ phase: "error", error_code: "server.provider_unavailable" });

		expect(
			await screen.findByText(
				"The language model is unavailable right now. Try again in a moment.",
			),
		).toBeTruthy();
		fireEvent.click(screen.getByRole("button", { name: "Open Providers" }));
		expect(mockNavigate).toHaveBeenCalledWith("providers");
	});

	it("never renders a raw error code for an unknown failure", async () => {
		bridge({});
		await renderChat();

		pushTurn({ phase: "error", error_code: "some.unknown.code" });

		expect(
			await screen.findByText("The reply could not be generated. Try again."),
		).toBeTruthy();
		expect(screen.queryByText(/some\.unknown\.code/)).toBeNull();
	});

	it("opens the consent gate instead of starting capture without voice consent", async () => {
		bridge({ config: { ...CONFIGURED, voice_biometric_consent: false } });
		await renderChat();

		fireEvent.pointerDown(screen.getByTestId("chat-push-to-talk"));

		expect(mockCall).not.toHaveBeenCalledWith("chat_listen_start");
		expect(useConsentGateStore.getState().request?.consentField).toBe(
			"voice_biometric_consent",
		);
	});

	it("clears the conversation through chat_reset", async () => {
		bridge({
			messages: [{ role: "user", text: "old question" }],
		});
		await renderChat();
		expect(screen.getByText("old question")).toBeTruthy();

		fireEvent.click(screen.getByRole("button", { name: "New conversation" }));

		await waitFor(() => expect(mockCall).toHaveBeenCalledWith("chat_reset"));
		await waitFor(() => expect(screen.queryByText("old question")).toBeNull());
		expect(screen.getByText("No messages yet")).toBeTruthy();
	});

	it("keeps the transcript and the control on matching themed surfaces", async () => {
		bridge({});
		await renderChat();

		const controls = screen
			.getByTestId("chat-push-to-talk")
			.closest(".rounded-lg") as HTMLElement;
		const transcript = screen
			.getByText("No messages yet")
			.closest(".rounded-lg") as HTMLElement;
		expect(controls.className).toContain("bg-surface-subtle");
		expect(transcript.className).toContain("bg-surface-subtle");
		expect(transcript).not.toBe(controls);
		expect(within(controls).getByRole("status")).toBeTruthy();
		// No bordered card is nested inside another bordered card.
		expect(
			transcript.querySelector(".rounded-lg.bg-surface-subtle"),
		).toBeNull();
	});

	it("keeps the phase readout quiet and the button free of looping motion", async () => {
		bridge({});
		await renderChat();

		const button = screen.getByTestId("chat-push-to-talk");
		expect(button.className).not.toContain("transition-all");
		expect(button.className).not.toContain("animate-glow-pulse");
		const status = screen.getByRole("status");
		expect(status.className).toContain("rounded-full");
		expect(status.querySelector(".animate-pulse")).toBeNull();
	});

	it("renders softened, app-themed message bubbles", async () => {
		bridge({
			messages: [
				{ role: "user", text: "earlier question" },
				{ role: "assistant", text: "earlier answer" },
			],
		});
		await renderChat();

		expect(screen.getByText("earlier question").className).toContain(
			"bg-primary/10",
		);
		expect(screen.getByText("earlier answer").className).toContain(
			"bg-surface",
		);
	});

	it("uses the canonical card for page-level state screens", async () => {
		bridge({ config: { llm_provider: "", llm_model_id: "" } });
		await renderChat();

		const card = screen
			.getByText("No language model is selected.")
			.closest(".rounded-lg");
		expect(card?.className).toContain("bg-surface-subtle");
		expect(card?.querySelector(".rounded-lg.bg-surface-subtle")).toBeNull();
	});
});
