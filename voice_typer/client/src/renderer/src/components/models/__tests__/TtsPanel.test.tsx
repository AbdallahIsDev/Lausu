import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	pythonMock,
	resetStableMocks,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";
import { TtsPanel } from "@/components/models/TtsPanel";

vi.mock("@/hooks/usePython", () => pythonMock());

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: ({
		children,
		icon,
		className,
	}: {
		children?: React.ReactNode;
		icon?: { name?: string };
		className?: string;
	}) => (
		<span data-testid="hugeicon" data-name={icon?.name} className={className}>
			{children}
		</span>
	),
}));

vi.mock("@hugeicons/core-free-icons", async () => {
	const { createHugeiconsMock } = await import(
		"@/__tests__/helpers/hugeicons-mock"
	);
	return createHugeiconsMock();
});

const { mockCall } = stableMocks;

function engineInfo(available: boolean, label: string, downloadBytes: number) {
	return {
		available,
		label,
		download_bytes: downloadBytes,
		models_dir: "C:/cache/tts/models",
	};
}

function statusPayload(active: string, audio8Available: boolean) {
	return {
		data: {
			engine: active,
			voice: "default",
			language: "en",
			engines: {
				audio8: engineInfo(
					audio8Available,
					"Audio8 TTS Realistic 0.6B",
					1_890_480_128,
				),
				magpie: engineInfo(false, "MagpieTTS Multilingual 357M", 647_000_000),
			},
		},
	};
}

function mockStatus(active: string, audio8Available: boolean) {
	mockCall.mockImplementation((command: string) => {
		if (command === "tts_status") {
			return Promise.resolve(statusPayload(active, audio8Available));
		}
		return Promise.resolve({ success: true });
	});
}

async function renderPanel(active: string, audio8Available: boolean) {
	mockStatus(active, audio8Available);
	render(<TtsPanel />);
	// The first render is the empty status; wait for the engine label that
	// only the real `tts_status` payload carries.
	await waitFor(() => {
		expect(screen.getByText("Audio8 TTS Realistic 0.6B")).toBeTruthy();
	});
}

/** Accessible names carry the model name ("Select <name>"). */
const SELECT_NAME = /^Select /;
const ACTIVE_NAME = /^Active: /;

beforeEach(() => {
	resetStableMocks();
});

afterEach(() => {
	cleanup();
});

describe("TtsPanel row actions", () => {
	it("offers Download, and no Select/Test, while the pack is missing", async () => {
		await renderPanel("off", false);

		expect(
			screen.getAllByRole("button", { name: /^Download \(/ }),
		).toHaveLength(2);
		expect(screen.queryByRole("button", { name: SELECT_NAME })).toBeNull();
		expect(screen.queryByRole("button", { name: ACTIVE_NAME })).toBeNull();
		// Test is never rendered disabled for a pack that cannot run.
		expect(screen.queryByRole("button", { name: "Test voice" })).toBeNull();
	});

	it("offers Select plus Test on a downloaded, inactive engine", async () => {
		await renderPanel("off", true);

		expect(screen.getByRole("button", { name: SELECT_NAME })).toBeTruthy();
		expect(screen.getByRole("button", { name: "Test voice" })).toBeTruthy();
		expect(screen.queryByRole("button", { name: ACTIVE_NAME })).toBeNull();
		// Only the READY engine has actions; the missing one keeps Download.
		expect(
			screen.getAllByRole("button", { name: /^Download \(/ }),
		).toHaveLength(1);
	});

	it("shows Active, not Select, on the selected engine and keeps Test", async () => {
		await renderPanel("audio8", true);

		expect(screen.getByRole("button", { name: ACTIVE_NAME })).toBeTruthy();
		expect(screen.queryByRole("button", { name: SELECT_NAME })).toBeNull();
		expect(screen.getByRole("button", { name: "Test voice" })).toBeTruthy();
	});

	it("has no engine toggle and no Compare control", async () => {
		await renderPanel("audio8", true);

		expect(screen.queryByRole("radiogroup")).toBeNull();
		expect(screen.queryByRole("tablist")).toBeNull();
		expect(screen.queryByText(/compare/i)).toBeNull();
	});

	it("persists the selection through set_config when Select is pressed", async () => {
		await renderPanel("off", true);

		await userEvent.click(screen.getByRole("button", { name: SELECT_NAME }));

		expect(mockCall).toHaveBeenCalledWith("set_config", {
			tts_engine: "audio8",
		});
	});
});
