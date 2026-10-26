/**
 * CONFIG-HYDRATE: "connected" must always come with a config snapshot.
 *
 * The sidebar's active-model caption and CPU/GPU switch are both driven
 * by the cached config: `formatActiveModel(null) === ""` hides the
 * caption, and `DeviceToggle` bails unless `config.device` is
 * cpu|cuda AND `config.gpu_available === true`. So a connection that
 * reaches "connected" without installing the `get_config` payload leaves
 * the sidebar visibly half-built — model name gone, device switch gone —
 * while the app otherwise looks healthy. A cold autostart produces
 * exactly that: the startup probe spends its retry budget, the user
 * clicks Retry, and the retry only proved the transport was alive.
 *
 * `model_size` is the completeness marker: a persisted speech-model field,
 * always present in a full `get_config` and never carried by a
 * `config_changed` push, so its absence means the store never saw a full
 * snapshot (including a partial object seeded by an early push through
 * mergeConfig's null-base branch). Deliberately NOT `gpu_available` — the
 * model caption must not have a GPU term in its data path, or a machine
 * whose GPU probe is slow/absent would look permanently incomplete and
 * refetch on every status push.
 */
import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Shared stable-mocks preamble (see helpers/stableMocks.tsx): must be
// imported above any static import of a page module.
import {
	pythonMock,
	resetStableMocks,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";

const { mockCall, mockPythonEvent } = stableMocks;

vi.mock("@/hooks/usePython", () => pythonMock());

import { useConnection } from "@/hooks/useConnection";
import { _resetNavigationForTest, useNavigation } from "@/hooks/useNavigation";
import { useAppStore } from "@/stores/appStore";
import type { LausuConfig } from "@/types/config";

/** What an early `config_changed` push can seed: truthy, but incomplete. */
const PARTIAL_CONFIG = {
	device: "cuda",
	onboarding_completed: true,
} satisfies Partial<LausuConfig>;

/** A full `get_config` snapshot. */
const FULL_CONFIG = {
	...PARTIAL_CONFIG,
	model_size: "large-v3-turbo",
	asr_backend: "whisper",
	gpu_available: true,
} satisfies Partial<LausuConfig>;

function Harness() {
	const { navigate } = useNavigation();
	const { handleRetryConnection } = useConnection({
		call: (async (type: string) => mockCall(type)) as unknown as <T = unknown>(
			type: string,
			data?: Record<string, unknown>,
		) => Promise<T>,
		navigate,
	});
	const connectionStatus = useAppStore((s) => s.connectionStatus);

	return (
		<>
			<span data-testid="status">{connectionStatus}</span>
			<button type="button" onClick={() => void handleRetryConnection()}>
				Retry
			</button>
		</>
	);
}

function findHandler(event: "state_changed"): (data: unknown) => void {
	const call = mockPythonEvent.mock.calls.find((c) => c[0] === event);
	if (!call) throw new Error(`expected a ${event} subscription`);
	return call[1] as (data: unknown) => void;
}

describe("useConnection config hydration", () => {
	beforeEach(() => {
		resetStableMocks();
		_resetNavigationForTest();
		useAppStore.getState().setConfig(null);
		useAppStore.getState().setConnectionStatus("connecting");
		useAppStore.getState().setLastError(null);
		mockCall.mockImplementation((type: string) => {
			switch (type) {
				case "get_config":
					return Promise.resolve(PARTIAL_CONFIG);
				case "get_status":
					return Promise.resolve({ status: "idle" });
				case "onboarding_is_first_run":
					return Promise.resolve({ is_first_run: false });
				default:
					return Promise.resolve({});
			}
		});
	});

	afterEach(() => {
		cleanup();
		delete (window as unknown as Record<string, unknown>).window_;
	});

	it("manual retry installs the get_config payload, not just the connection", async () => {
		render(<Harness />);
		await waitFor(() => {
			expect(screen.getByTestId("status").textContent).toBe("connected");
		});

		// Cold-boot shape: connected, but no full snapshot ever landed.
		useAppStore.getState().setConfig(null);
		useAppStore.getState().setConnectionStatus("disconnected");

		mockCall.mockImplementation((type: string) =>
			type === "get_config"
				? Promise.resolve(FULL_CONFIG)
				: Promise.resolve({ status: "idle" }),
		);

		fireEvent.click(screen.getByText("Retry"));

		await waitFor(() => {
			expect(screen.getByTestId("status").textContent).toBe("connected");
		});
		// Pre-fix: the retry awaited get_config and discarded it, leaving
		// config null, so both sidebar widgets stayed hidden.
		expect(useAppStore.getState().config?.model_size).toBe("large-v3-turbo");
		expect(useAppStore.getState().config?.gpu_available).toBe(true);
	});

	it("state_changed promotes to connected AND hydrates a missing config", async () => {
		render(<Harness />);
		await waitFor(() => {
			expect(screen.getByTestId("status").textContent).toBe("connected");
		});
		// Never received a full snapshot (only the partial push above).
		useAppStore.getState().setConfig(PARTIAL_CONFIG);
		expect(useAppStore.getState().config?.gpu_available).toBeUndefined();

		mockCall.mockImplementation((type: string) =>
			type === "get_config"
				? Promise.resolve(FULL_CONFIG)
				: Promise.resolve({ status: "idle" }),
		);

		findHandler("state_changed")({ status: "idle" });

		await waitFor(() => {
			expect(useAppStore.getState().config?.gpu_available).toBe(true);
		});
		expect(useAppStore.getState().config?.model_size).toBe("large-v3-turbo");
	});

	it("a complete config is left alone (no IPC on every state push)", async () => {
		render(<Harness />);
		await waitFor(() => {
			expect(screen.getByTestId("status").textContent).toBe("connected");
		});
		useAppStore.getState().setConfig(FULL_CONFIG);
		mockCall.mockClear();

		findHandler("state_changed")({ status: "idle" });

		await waitFor(() => {
			expect(useAppStore.getState().connectionStatus).toBe("connected");
		});
		expect(
			mockCall.mock.calls.filter((c) => c[0] === "get_config"),
		).toHaveLength(0);
	});

	it("a snapshot with the model fields but NO gpu_available is complete (no GPU refetch loop)", async () => {
		// The model caption's data path must have no GPU term. If
		// completeness were keyed on `gpu_available`, a machine whose GPU
		// probe is absent or slow would look permanently incomplete and
		// refetch get_config on every status push — a laggy UI blamed on
		// the CPU/GPU switch.
		render(<Harness />);
		await waitFor(() => {
			expect(screen.getByTestId("status").textContent).toBe("connected");
		});
		useAppStore.getState().setConfig({
			asr_backend: "whisper",
			model_size: "large-v3",
			onboarding_completed: true,
		} satisfies Partial<LausuConfig>);
		mockCall.mockClear();

		findHandler("state_changed")({ status: "idle" });

		await waitFor(() => {
			expect(useAppStore.getState().connectionStatus).toBe("connected");
		});
		expect(
			mockCall.mock.calls.filter((c) => c[0] === "get_config"),
		).toHaveLength(0);
	});
});
