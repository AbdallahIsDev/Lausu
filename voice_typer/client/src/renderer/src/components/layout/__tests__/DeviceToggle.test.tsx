import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
	pythonMock,
	resetStableMocks,
	stableMocks,
} from "@/__tests__/helpers/stableMocks";
import { DeviceToggle } from "@/components/layout/DeviceToggle";
import { useAppStore } from "@/stores/appStore";

vi.mock("@/hooks/usePython", () => pythonMock());

const { mockCall } = stableMocks;

function setConfigSnapshot(config: Record<string, unknown> | null) {
	useAppStore.setState({ config: config as never });
}

beforeEach(() => {
	resetStableMocks();
	mockCall.mockResolvedValue({ success: true });
});

afterEach(() => {
	cleanup();
	useAppStore.setState({ config: null });
});

describe("DeviceToggle", () => {
	it("renders CPU/GPU with the active device checked", () => {
		setConfigSnapshot({ device: "cuda", gpu_available: true });
		render(<DeviceToggle />);
		const radios = screen.getAllByRole("radio");
		expect(radios).toHaveLength(2);
		expect(radios[1]).toBeChecked();
	});

	it("persists a GPU->CPU switch via set_config", async () => {
		const user = userEvent.setup();
		setConfigSnapshot({ device: "cuda", gpu_available: true });
		render(<DeviceToggle />);
		await user.click(screen.getByText("CPU"));
		expect(mockCall).toHaveBeenCalledWith("set_config", { device: "cpu" });
	});

	it("stays hidden when no GPU is present", () => {
		setConfigSnapshot({ device: "cpu", gpu_available: false });
		const { container } = render(<DeviceToggle />);
		expect(container).toBeEmptyDOMElement();
	});

	it("stays hidden when the capability flag is absent (legacy sidecar)", () => {
		setConfigSnapshot({ device: "cpu" });
		const { container } = render(<DeviceToggle />);
		expect(container).toBeEmptyDOMElement();
	});

	it("stays hidden in the collapsed rail", () => {
		setConfigSnapshot({ device: "cuda", gpu_available: true });
		const { container } = render(<DeviceToggle collapsed />);
		expect(container).toBeEmptyDOMElement();
	});

	it("follows a backend GPU->CPU fallback through the store", () => {
		setConfigSnapshot({ device: "cuda", gpu_available: true });
		const { rerender } = render(<DeviceToggle />);
		useAppStore.getState().mergeConfig({ device: "cpu" });
		rerender(<DeviceToggle />);
		const radios = screen.getAllByRole("radio");
		expect(radios[0]).toBeChecked();
	});
});
