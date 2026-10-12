import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Controllable hook state + backend snapshot (hoisted so the vi.mock
// factories can reference them). Follows the OfflinePackPreparingBanner
// test pattern: mock the bridge, drive the component, assert copy +
// the IPC call.
const { callMock, hookState, backend } = vi.hoisted(() => ({
	callMock: vi.fn(),
	hookState: {
		status: "idle",
		error: null,
		isReady: false,
		progress: null,
		outdatedInfo: null,
	} as {
		status: string;
		error: string | null;
		isReady: boolean;
		progress: number | null;
		outdatedInfo: { version: string; min_proto_version: number } | null;
	},
	backend: {
		pack: null as null | Record<string, unknown>,
	},
}));

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: callMock }),
}));

vi.mock("@/hooks/useOfflinePackDownload", () => ({
	useOfflinePackDownload: () => hookState,
}));

vi.mock("@hugeicons/react", () => ({
	HugeiconsIcon: () => null,
}));

vi.mock("@hugeicons/core-free-icons", () => ({
	CircleQuestionMarkIcon: {},
}));

import OfflinePackSection from "@/components/settings/OfflinePackSection";

function setHook(partial: Partial<typeof hookState>) {
	Object.assign(hookState, {
		status: "idle",
		error: null,
		isReady: false,
		progress: null,
		outdatedInfo: null,
		...partial,
	});
}

beforeEach(() => {
	callMock.mockReset();
	setHook({});
	backend.pack = null;
	callMock.mockImplementation(async (type: string) => {
		if (type === "get_status") return { offline_pack: backend.pack };
		return {};
	});
});

afterEach(() => {
	cleanup();
});

describe("OfflinePackSection, mount catch-up", () => {
	it("renders the section with status + installed version from get_status", async () => {
		backend.pack = {
			state: "ready",
			installed_version: "v9",
			download_progress: null,
		};
		render(<OfflinePackSection />);
		expect(screen.getByTestId("offline-pack-section")).toBeInTheDocument();
		expect(await screen.findByText("Offline engine pack")).toBeInTheDocument();
		expect(await screen.findByText("Ready")).toBeInTheDocument();
		expect(await screen.findByText("v9")).toBeInTheDocument();
	});

	it("shows Checking while the status query is in flight", () => {
		callMock.mockImplementation(() => new Promise(() => {}));
		render(<OfflinePackSection />);
		expect(screen.getAllByText("Checking…").length).toBeGreaterThan(0);
	});

	it("falls back to the backend state while the hook is still idle", async () => {
		backend.pack = {
			state: "downloading",
			installed_version: null,
			download_progress: 64,
		};
		render(<OfflinePackSection />);
		expect(
			await screen.findByText("Downloading voice pack 64%"),
		).toBeInTheDocument();
	});

	it("shows Not installed when no version is installed", async () => {
		backend.pack = {
			state: "missing",
			installed_version: null,
			download_progress: null,
		};
		render(<OfflinePackSection />);
		expect(await screen.findByText("Not installed")).toBeInTheDocument();
		expect(await screen.findByText("Not downloaded")).toBeInTheDocument();
	});
});

describe("OfflinePackSection, per-state render (hook wins over snapshot)", () => {
	it("downloading shows the live percent", async () => {
		setHook({ status: "downloading", progress: 42 });
		render(<OfflinePackSection />);
		expect(
			await screen.findByText("Downloading voice pack 42%"),
		).toBeInTheDocument();
	});

	it("verifying shows the preparing copy", async () => {
		setHook({ status: "verifying" });
		render(<OfflinePackSection />);
		expect(
			await screen.findByText("Preparing offline engine…"),
		).toBeInTheDocument();
	});

	it("outdated renders Update available + a Download action", async () => {
		setHook({
			status: "outdated",
			outdatedInfo: { version: "v10", min_proto_version: 7 },
		});
		render(<OfflinePackSection />);
		expect(await screen.findByText("Update available")).toBeInTheDocument();
		expect(
			screen.getByRole("button", {
				name: "Download the offline speech engine pack",
			}),
		).toBeInTheDocument();
	});

	it("failed renders Download failed + Retry", async () => {
		setHook({ status: "failed", error: "disk full" });
		render(<OfflinePackSection />);
		expect(await screen.findByText("Download failed")).toBeInTheDocument();
		expect(
			screen.getByRole("button", {
				name: "Download the offline speech engine pack",
			}),
		).toHaveTextContent("Retry download");
	});

	it("corrupt renders Pack corrupt + Repair", async () => {
		setHook({ status: "corrupt", error: "sha256 mismatch" });
		render(<OfflinePackSection />);
		expect(await screen.findByText("Pack corrupt")).toBeInTheDocument();
		expect(
			screen.getByRole("button", {
				name: "Download the offline speech engine pack",
			}),
		).toHaveTextContent("Repair pack");
	});

	it("worker-crashed and worker-unloaded render their states", async () => {
		setHook({ status: "worker-crashed", error: "SIGSEGV" });
		const { unmount } = render(<OfflinePackSection />);
		expect(await screen.findByText("Engine crashed")).toBeInTheDocument();
		unmount();
		cleanup();

		setHook({ status: "worker-unloaded" });
		render(<OfflinePackSection />);
		expect(await screen.findByText("Engine unloaded")).toBeInTheDocument();
	});

	it("ready shows no action button", async () => {
		setHook({ status: "ready", isReady: true });
		backend.pack = {
			state: "ready",
			installed_version: "v9",
			download_progress: null,
		};
		render(<OfflinePackSection />);
		expect(await screen.findByText("Ready")).toBeInTheDocument();
		expect(
			screen.queryByRole("button", {
				name: "Download the offline speech engine pack",
			}),
		).toBeNull();
	});

	it("has no Remove button in any state (no remove IPC exists)", async () => {
		setHook({ status: "missing" });
		render(<OfflinePackSection />);
		await screen.findByText("Not downloaded");
		expect(screen.queryByRole("button", { name: /remove/i })).toBeNull();
	});
});

describe("OfflinePackSection, actions", () => {
	it("Download calls check_offline_pack_update", async () => {
		callMock.mockResolvedValue({ offline_pack: backend.pack });
		setHook({ status: "missing" });
		render(<OfflinePackSection />);
		const btn = await screen.findByRole("button", {
			name: "Download the offline speech engine pack",
		});
		fireEvent.click(btn);
		await waitFor(() => {
			expect(callMock).toHaveBeenCalledWith("check_offline_pack_update", {});
		});
	});

	it("Retry and Repair hit the same command", async () => {
		setHook({ status: "failed", error: "x" });
		const { unmount } = render(<OfflinePackSection />);
		fireEvent.click(
			await screen.findByRole("button", {
				name: "Download the offline speech engine pack",
			}),
		);
		await waitFor(() => {
			expect(callMock).toHaveBeenCalledWith("check_offline_pack_update", {});
		});
		unmount();
		cleanup();
		callMock.mockClear();

		setHook({ status: "corrupt", error: "y" });
		render(<OfflinePackSection />);
		fireEvent.click(
			await screen.findByRole("button", {
				name: "Download the offline speech engine pack",
			}),
		);
		await waitFor(() => {
			expect(callMock).toHaveBeenCalledWith("check_offline_pack_update", {});
		});
	});

	it("disables the button while the call is in flight", async () => {
		let resolveCall: (() => void) | undefined;
		callMock.mockImplementation(
			(type: string) =>
				new Promise((resolve) => {
					if (type === "check_offline_pack_update") {
						resolveCall = () => resolve({});
					} else {
						resolve({ offline_pack: backend.pack });
					}
				}),
		);
		setHook({ status: "missing" });
		render(<OfflinePackSection />);
		const btn = await screen.findByRole("button", {
			name: "Download the offline speech engine pack",
		});
		fireEvent.click(btn);
		expect(btn).toBeDisabled();
		expect(btn).toHaveTextContent("Downloading…");
		resolveCall?.();
		await waitFor(() => {
			expect(btn).not.toBeDisabled();
		});
	});
});

describe("OfflinePackSection, a11y", () => {
	it("announces status changes via a polite live region", async () => {
		setHook({ status: "ready", isReady: true });
		backend.pack = {
			state: "ready",
			installed_version: "v9",
			download_progress: null,
		};
		render(<OfflinePackSection />);
		const value = await screen.findByText("Ready");
		expect(value.closest("[aria-live='polite']")).not.toBeNull();
	});
});
