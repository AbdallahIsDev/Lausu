import {
	cleanup,
	fireEvent,
	render,
	screen,
	waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OfflinePackPreparingBanner } from "@/components/feedback/OfflinePackPreparingBanner";
import type { OfflinePackStatus } from "@/hooks/useOfflinePackDownload";

const callMock = vi.fn();
vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: callMock }),
}));

// Mock i18n so we don't load the real locale chunks in unit tests.
// The mock returns the key as the translated string (with `: key=value`
// suffixes for placeholder substitutions that don't match a `{placeholder}`
// in the key, so we can assert on both the bare key and the param
// propagation).
vi.mock("@/i18n/i18n", () => ({
	t: (key: string, params?: Record<string, string>) => {
		if (!params) return key;
		let result = key;
		const leftover: string[] = [];
		for (const [k, v] of Object.entries(params)) {
			const placeholder = `{${k}}`;
			if (result.includes(placeholder)) {
				result = result.replace(placeholder, String(v));
			} else {
				leftover.push(`${k}=${String(v)}`);
			}
		}
		if (leftover.length > 0) {
			result = `${result}: ${leftover.join(", ")}`;
		}
		return result;
	},
}));

afterEach(() => {
	cleanup();
	callMock.mockReset();
});

describe("OfflinePackPreparingBanner, recovery action", () => {
	const recoveryStatuses: OfflinePackStatus[] = [
		"missing",
		"failed",
		"corrupt",
	];
	const passiveStatuses: OfflinePackStatus[] = [
		"idle",
		"downloading",
		"verifying",
		"ready",
		"worker-starting",
		"worker-crashed",
		"worker-unloaded",
	];

	for (const status of recoveryStatuses) {
		it(`shows Download offline engine when status=${status}`, () => {
			render(<OfflinePackPreparingBanner visible={true} status={status} />);
			expect(
				screen.getByRole("button", { name: "pack.downloadOfflineEngineAria" }),
			).toBeInTheDocument();
		});
	}

	for (const status of passiveStatuses) {
		it(`hides recovery button when status=${status}`, () => {
			render(<OfflinePackPreparingBanner visible={true} status={status} />);
			expect(screen.queryByRole("button")).toBeNull();
		});
	}

	it("clicking Download calls check_offline_pack_update", async () => {
		callMock.mockResolvedValue({});
		render(<OfflinePackPreparingBanner visible={true} status="missing" />);
		fireEvent.click(
			screen.getByRole("button", { name: "pack.downloadOfflineEngineAria" }),
		);
		await waitFor(() => {
			expect(callMock).toHaveBeenCalledWith("check_offline_pack_update", {});
		});
	});

	it("ignores double-click while a download call is in flight", async () => {
		let resolveCall: (() => void) | undefined;
		callMock.mockImplementation(
			() =>
				new Promise((resolve) => {
					resolveCall = () => resolve({});
				}),
		);
		render(<OfflinePackPreparingBanner visible={true} status="failed" />);
		const btn = screen.getByRole("button", {
			name: "pack.downloadOfflineEngineAria",
		});
		fireEvent.click(btn);
		fireEvent.click(btn);
		expect(callMock).toHaveBeenCalledTimes(1);
		expect(btn).toBeDisabled();
		expect(btn).toHaveTextContent("pack.downloadOfflineEngineBusy");
		resolveCall?.();
		await waitFor(() => {
			expect(btn).not.toBeDisabled();
		});
	});

	it("recovers after a rejected IPC call (button re-enabled)", async () => {
		callMock.mockRejectedValueOnce(new Error("bridge down"));
		render(<OfflinePackPreparingBanner visible={true} status="corrupt" />);
		const btn = screen.getByRole("button", {
			name: "pack.downloadOfflineEngineAria",
		});
		fireEvent.click(btn);
		await waitFor(() => {
			expect(btn).not.toBeDisabled();
		});
	});
});

describe("OfflinePackPreparingBanner, visibility", () => {
	it("renders nothing when visible is false", () => {
		const { container } = render(
			<OfflinePackPreparingBanner visible={false} status="downloading" />,
		);
		expect(container.firstElementChild).toBeNull();
	});

	it("renders the banner when visible is true", () => {
		render(<OfflinePackPreparingBanner visible={true} status="downloading" />);
		expect(screen.getByText("pack.preparingOfflineEngine")).toBeInTheDocument();
	});
});

describe("OfflinePackPreparingBanner, a11y", () => {
	it("uses role=status so screen readers treat it as a live region", () => {
		render(<OfflinePackPreparingBanner visible={true} status="downloading" />);
		const region = screen.getByRole("status");
		expect(region).toBeInTheDocument();
	});

	it("carries aria-live=polite (NOT assertive, informational, not an error)", () => {
		render(<OfflinePackPreparingBanner visible={true} status="verifying" />);
		const region = screen.getByRole("status");
		expect(region.getAttribute("aria-live")).toBe("polite");
	});

	it("aria-label includes the status via the i18n placeholder", () => {
		render(<OfflinePackPreparingBanner visible={true} status="corrupt" />);
		const region = screen.getByRole("status");
		// The mock t() returns the key with `{status}` substituted, so
		// the label is the i18n key with `corrupt` interpolated.
		expect(region.getAttribute("aria-label")).toContain(
			"pack.preparingOfflineEngineAria",
		);
		expect(region.getAttribute("aria-label")).toContain("corrupt");
	});
});

describe("OfflinePackPreparingBanner, data-pack-status", () => {
	const statuses: OfflinePackStatus[] = [
		"idle",
		"downloading",
		"verifying",
		"ready",
		"failed",
		"missing",
		"corrupt",
		"worker-starting",
		"worker-crashed",
		"worker-unloaded",
	];

	for (const status of statuses) {
		it(`exposes data-pack-status="${status}"`, () => {
			render(<OfflinePackPreparingBanner visible={true} status={status} />);
			const region = screen.getByRole("status");
			expect(region.getAttribute("data-pack-status")).toBe(status);
		});
	}

	it("does NOT render the data-pack-status attribute when invisible", () => {
		render(<OfflinePackPreparingBanner visible={false} status="downloading" />);
		expect(document.querySelector("[data-pack-status]")).toBeNull();
	});
});
