import {
	act,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
	handlers: {} as Record<string, ((data?: unknown) => void) | undefined>,
	call: vi.fn(),
}));

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: mocks.call }),
	usePythonEvent: (type: string, handler: (data?: unknown) => void) => {
		mocks.handlers[type] = handler;
	},
}));

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

describe("Providers page", () => {
	beforeEach(() => {
		mocks.handlers = {};
		mocks.call.mockReset();
		mocks.call.mockResolvedValue(EMPTY_LIST);
	});

	it("renders the local ONNX load state published by the backend", async () => {
		render(<Providers />);
		expect(screen.getByText("Dictation")).toBeTruthy();

		await act(async () => {
			mocks.handlers.provider_local_onnx_state?.({
				model: "MiniCPM5-2B",
				state: "loading",
				error: null,
			});
		});

		expect(screen.getByText("MiniCPM5-2B: loading model…")).toBeTruthy();
	});

	it("renders capability badges and the masked key only", async () => {
		mocks.call.mockResolvedValue(POPULATED_LIST);
		render(<Providers />);

		// The label appears once in the provider row and once per domain picker.
		expect((await screen.findAllByText("OpenRouter")).length).toBeGreaterThan(
			1,
		);
		// Three domain badges on the provider that serves all three domains.
		expect(screen.getAllByText("asr").length).toBeGreaterThan(0);
		expect(screen.getAllByText("tts").length).toBeGreaterThan(0);
		expect(screen.getAllByText("llm").length).toBeGreaterThan(0);
		expect(screen.getByText("Key: sk-o…4f2a")).toBeTruthy();
	});

	it("shows the credits note only for an enabled remote domain", async () => {
		mocks.call.mockResolvedValue(POPULATED_LIST);
		render(<Providers />);

		await screen.findAllByText("OpenRouter");
		// Dictation and Speech point at the local provider; only Polish is remote.
		expect(screen.getAllByText("Uses your provider credits")).toHaveLength(1);
	});

	it("stores a pasted key and clears the field on success", async () => {
		mocks.call.mockResolvedValue(POPULATED_LIST);
		render(<Providers />);

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

	it("surfaces a failed connection test as a status message", async () => {
		mocks.call.mockImplementation((command: string) => {
			if (command === "provider_test") {
				return Promise.reject(new Error("server.provider_auth_required"));
			}
			return Promise.resolve(POPULATED_LIST);
		});
		render(<Providers />);

		fireEvent.click(await screen.findByText("Test connection"));

		expect(
			await screen.findByText("server.provider_auth_required"),
		).toBeTruthy();
	});
});
