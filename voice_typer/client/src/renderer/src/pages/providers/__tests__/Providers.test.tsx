import {
	act,
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
	hugeiconsCoreMock,
	hugeiconsReactMock,
} from "@/__tests__/helpers/stableMocks";

const mocks = vi.hoisted(() => ({
	handlers: {} as Record<string, ((data?: unknown) => void) | undefined>,
	call: vi.fn(),
	toast: {
		error: vi.fn(),
		success: vi.fn(),
		warning: vi.fn(),
		info: vi.fn(),
		dismiss: vi.fn(),
	},
}));

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: mocks.call }),
	usePythonEvent: (type: string, handler: (data?: unknown) => void) => {
		mocks.handlers[type] = handler;
	},
}));
vi.mock("sonner", () => ({ toast: mocks.toast, Toaster: () => null }));
vi.mock("@hugeicons/react", () => hugeiconsReactMock());
vi.mock("@hugeicons/core-free-icons", () => hugeiconsCoreMock());

import Providers from "../Providers";

function domain(overrides: Record<string, unknown> = {}) {
	return {
		provider: "",
		model_id: "",
		consent: false,
		fallback: "off",
		enabled: false,
		...overrides,
	};
}

const EMPTY_LIST = {
	data: {
		providers: [],
		domains: { asr: domain(), tts: domain(), llm: domain() },
	},
};

/** One remote (OpenRouter) and one on-device provider, both enabled. */
const POPULATED_LIST = {
	data: {
		providers: [
			{
				id: "openrouter",
				label: "OpenRouter",
				domains: ["asr", "llm", "tts"],
				local: false,
				auth: "api_key",
				models: [
					{
						id: "deepseek/chat",
						label: "DeepSeek Chat",
						context_length: 128000,
						free: true,
					},
				],
				unsupported_reason: {},
				key: { configured: true, masked: "sk-o…4f2a" },
				consent_required: true,
			},
			{
				id: "local",
				label: "On this device",
				domains: ["asr", "tts"],
				local: true,
				auth: "none",
				models: [],
				unsupported_reason: {},
				key: { configured: false, masked: "" },
				consent_required: false,
			},
		],
		domains: {
			asr: domain({ provider: "local", enabled: true }),
			tts: domain({ provider: "local", enabled: true }),
			llm: domain({
				provider: "openrouter",
				enabled: true,
				model_id: "deepseek/chat",
			}),
		},
	},
};

/** The same list with the remote key removed and a duplicated ASR/TTS reason. */
const UNKEYED_LIST = {
	data: {
		...POPULATED_LIST.data,
		providers: [
			{
				...POPULATED_LIST.data.providers[0],
				key: { configured: false, masked: "" },
				unsupported_reason: {
					asr: "OpenRouter serves text models only.",
					tts: "OpenRouter serves text models only.",
				},
			},
			POPULATED_LIST.data.providers[1],
		],
	},
};

/** The card button opens the key dialog (no inline editor lives in the card). */
async function openKeyEditor() {
	const trigger = await screen.findByRole("button", {
		name: /^(Edit key|Add key)$/,
	});
	fireEvent.click(trigger);
	return trigger;
}

describe("Providers page", () => {
	beforeEach(() => {
		mocks.handlers = {};
		mocks.call.mockReset();
		mocks.call.mockResolvedValue(EMPTY_LIST);
		mocks.toast.error.mockClear();
		mocks.toast.success.mockClear();
	});

	it("uses the page shell and the plugin-style two-per-row card grid", async () => {
		mocks.call.mockResolvedValue(POPULATED_LIST);
		const { container } = render(<Providers />);
		await screen.findByText("Dictation");

		expect(container.firstElementChild?.className).toContain("max-w-4xl");
		expect(container.firstElementChild?.className).toContain("gap-4");

		const connections = screen.getByRole("region", { name: "Connections" });
		const grid = connections.querySelector(".grid-cols-2");
		expect(grid).not.toBeNull();
		expect(grid?.className).toContain("gap-4");
		// Local models / ONNX need no key, so they get no connection card.
		expect(within(connections).getByText("OpenRouter")).toBeTruthy();
		expect(within(connections).queryByText("On this device")).toBeNull();

		const routing = screen.getByRole("region", { name: "Model routing" });
		const card = routing.querySelector(".divide-y");
		expect(card?.className).toContain("border-border/8");
		expect(card?.className).toContain("bg-surface-subtle");
	});

	it("leaves Dictation without a switch to disable it", async () => {
		render(<Providers />);
		await screen.findByText("Dictation");

		expect(screen.queryByRole("switch", { name: "Dictation" })).toBeNull();
		expect(screen.getByRole("switch", { name: "Speech" })).toBeTruthy();
		expect(screen.getByRole("switch", { name: "Polish" })).toBeTruthy();
	});

	it("renders the local ONNX load state published by the backend", async () => {
		render(<Providers />);
		expect(await screen.findByText("Dictation")).toBeTruthy();

		await act(async () => {
			mocks.handlers.provider_local_onnx_state?.({
				model: "MiniCPM5-2B",
				state: "loading",
				error: null,
			});
		});

		expect(screen.getByText("MiniCPM5-2B: loading model…")).toBeTruthy();
	});

	it("keeps key status and device labels off the provider cards", async () => {
		mocks.call.mockResolvedValue(POPULATED_LIST);
		render(<Providers />);

		await screen.findAllByText("OpenRouter");
		expect(screen.queryByText("Runs on your device")).toBeNull();
		expect(screen.queryByText("No key saved")).toBeNull();
		expect(screen.queryByText(/^Key: /)).toBeNull();
	});

	it("keeps capability and unsupported-reason labels off the cards", async () => {
		mocks.call.mockResolvedValue(UNKEYED_LIST);
		render(<Providers />);

		await screen.findAllByText("OpenRouter");
		expect(screen.queryByText(/serves text models only/)).toBeNull();
		expect(screen.queryByText(/^Dictation · Speech$/)).toBeNull();
	});

	it("names each domain and labels both of its selects", async () => {
		mocks.call.mockResolvedValue(EMPTY_LIST);
		render(<Providers />);
		await screen.findByText("Dictation");

		expect(screen.getByText("Turn your voice into text.")).toBeTruthy();
		expect(screen.getByText("Read text aloud.")).toBeTruthy();
		expect(
			screen.getByText("Polish and rewrite what you dictate."),
		).toBeTruthy();

		expect(screen.getAllByRole("combobox", { name: "Provider" })).toHaveLength(
			3,
		);
		expect(screen.getAllByRole("combobox", { name: "Model" })).toHaveLength(3);
	});

	it("offers key controls only on providers that take a key", async () => {
		mocks.call.mockResolvedValue(POPULATED_LIST);
		render(<Providers />);

		await openKeyEditor();
		await screen.findByPlaceholderText("Paste API key");

		// The on-device provider has auth "none": no key control at all.
		expect(screen.getAllByPlaceholderText("Paste API key")).toHaveLength(1);
		expect(screen.queryByText("No key saved")).toBeNull();
	});

	it("opens the credential editor in a modal, never inline in the card", async () => {
		mocks.call.mockResolvedValue(POPULATED_LIST);
		render(<Providers />);

		const trigger = await screen.findByRole("button", { name: "Edit key" });
		expect(screen.queryByPlaceholderText("Paste API key")).toBeNull();
		expect(screen.queryByRole("dialog")).toBeNull();

		fireEvent.click(trigger);

		const dialog = await screen.findByRole("dialog");
		expect(dialog).toBeTruthy();
		expect(within(dialog).getByPlaceholderText("Paste API key")).toBeTruthy();
		// The trigger is a plain button: no accordion state, no chevron.
		expect(trigger.getAttribute("aria-expanded")).toBeNull();
	});

	it("shows the credits note only for an enabled remote domain", async () => {
		mocks.call.mockResolvedValue(POPULATED_LIST);
		render(<Providers />);

		await screen.findAllByText("OpenRouter");
		// Dictation and Speech point at the local provider; only Polish is remote.
		expect(screen.getAllByText("Uses your provider credits")).toHaveLength(1);
	});

	it("shows consent only where the selected provider sends data off-device", async () => {
		mocks.call.mockResolvedValue(POPULATED_LIST);
		render(<Providers />);

		await screen.findAllByText("OpenRouter");
		expect(screen.getAllByRole("checkbox")).toHaveLength(1);
	});

	it("does not present the first provider as selected for an unset domain", async () => {
		mocks.call.mockResolvedValue({
			data: {
				...POPULATED_LIST.data,
				domains: {
					asr: domain(),
					tts: domain(),
					llm: domain(),
				},
			},
		});
		render(<Providers />);

		await screen.findByText("Turn your voice into text.");
		const routing = screen.getByRole("region", { name: "Model routing" });
		expect(within(routing).queryByText("OpenRouter")).toBeNull();
		const triggers = within(routing).getAllByRole("combobox", {
			name: "Provider",
		});
		expect(triggers).toHaveLength(3);
		for (const trigger of triggers) {
			expect(trigger.getAttribute("data-placeholder")).not.toBeNull();
		}
	});

	it("stores a pasted key and clears the field on success", async () => {
		mocks.call.mockResolvedValue(POPULATED_LIST);
		render(<Providers />);

		await openKeyEditor();
		const input = (await screen.findByPlaceholderText(
			"Paste API key",
		)) as HTMLInputElement;
		fireEvent.change(input, { target: { value: "sk-or-v1-new" } });
		fireEvent.click(screen.getByText("Save key"));

		await waitFor(() => expect(input.value).toBe(""));
		expect(mocks.call).toHaveBeenCalledWith("provider_set_key", {
			provider: "openrouter",
			key: "sk-or-v1-new",
		});
	});

	it("disables the keyed actions while no key is stored", async () => {
		mocks.call.mockResolvedValue(UNKEYED_LIST);
		render(<Providers />);

		await openKeyEditor();
		const test = await screen.findByText("Test connection");
		const remove = screen.getByText("Remove key");

		// The backend refuses a keyed test without a key; the UI must not offer it.
		expect(test).toBeDisabled();
		expect(remove).toBeDisabled();
	});

	it("adds no success readout or toast after a successful connection test", async () => {
		mocks.call.mockImplementation((command: string) => {
			if (command === "provider_test") return Promise.resolve({ ok: true });
			return Promise.resolve(POPULATED_LIST);
		});
		render(<Providers />);

		await openKeyEditor();
		fireEvent.click(await screen.findByText("Test connection"));

		await waitFor(() =>
			expect(mocks.call).toHaveBeenCalledWith("provider_test", {
				provider: "openrouter",
			}),
		);
		expect(screen.queryByText("Connection works.")).toBeNull();
		expect(mocks.toast.success).not.toHaveBeenCalled();
	});

	it("reports a failed connection test as an in-app notification", async () => {
		mocks.call.mockImplementation((command: string) => {
			if (command === "provider_test") {
				return Promise.reject(
					Object.assign(new Error("nope"), {
						code: "server.provider_auth_required",
					}),
				);
			}
			return Promise.resolve(POPULATED_LIST);
		});
		render(<Providers />);

		await openKeyEditor();
		fireEvent.click(await screen.findByText("Test connection"));

		await waitFor(() =>
			expect(mocks.toast.error).toHaveBeenCalledWith(
				"This provider rejected the API key. Save a new key, then test again.",
			),
		);
		// No inline verdict under the field, and no raw code (C-UXERR-1).
		expect(
			screen.queryByText(
				"This provider rejected the API key. Save a new key, then test again.",
			),
		).toBeNull();
		expect(screen.queryByText(/server\.provider_auth_required/)).toBeNull();
	});

	it("offers a retry when the provider list cannot be loaded", async () => {
		mocks.call.mockRejectedValueOnce(new Error("boom"));
		mocks.call.mockResolvedValue(EMPTY_LIST);
		render(<Providers />);

		expect(
			await screen.findByText("The provider list could not be loaded."),
		).toBeTruthy();
		// The raw exception text never reaches the UI.
		expect(screen.queryByText("boom")).toBeNull();

		fireEvent.click(screen.getByText("Retry"));

		expect(await screen.findByText("Dictation")).toBeTruthy();
	});

	it("turning a domain off clears its provider through the IPC write", async () => {
		mocks.call.mockResolvedValue(POPULATED_LIST);
		render(<Providers />);

		const sw = await screen.findByRole("switch", { name: "Polish" });
		fireEvent.click(sw);

		await waitFor(() =>
			expect(mocks.call).toHaveBeenCalledWith("provider_set_domain", {
				domain: "llm",
				provider: "",
				enabled: false,
			}),
		);
	});

	it("keeps the dialog open with Save disabled while a key is being stored", async () => {
		mocks.call.mockImplementation((command: string) => {
			if (command === "provider_set_key") return new Promise(() => {});
			return Promise.resolve(POPULATED_LIST);
		});
		render(<Providers />);

		await openKeyEditor();
		const input = screen.getByPlaceholderText("Paste API key");
		fireEvent.change(input, { target: { value: "sk-new" } });
		fireEvent.click(screen.getByText("Save key"));

		await waitFor(() => expect(screen.getByText("Save key")).toBeDisabled());
		expect(screen.getByRole("dialog")).toBeTruthy();
	});
});
