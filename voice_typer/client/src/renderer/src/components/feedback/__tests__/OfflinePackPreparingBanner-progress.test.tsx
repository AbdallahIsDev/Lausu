import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OfflinePackPreparingBanner } from "@/components/feedback/OfflinePackPreparingBanner";

vi.mock("@/hooks/usePython", () => ({
	usePython: () => ({ call: vi.fn() }),
}));

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
});

describe("OfflinePackPreparingBanner, download percent (slice C)", () => {
	it("shows the downloading key with percent while downloading", () => {
		render(
			<OfflinePackPreparingBanner
				visible={true}
				status="downloading"
				progress={42}
			/>,
		);
		expect(
			screen.getByText("pack.downloadingOfflineEngine: percent=42"),
		).toBeInTheDocument();
	});

	it("falls back to the generic key when progress is missing", () => {
		render(<OfflinePackPreparingBanner visible={true} status="downloading" />);
		expect(screen.getByText("pack.preparingOfflineEngine")).toBeInTheDocument();
	});

	it("ignores progress outside downloading (verifying shows generic)", () => {
		render(
			<OfflinePackPreparingBanner
				visible={true}
				status="verifying"
				progress={99}
			/>,
		);
		expect(screen.getByText("pack.preparingOfflineEngine")).toBeInTheDocument();
	});

	it("aria-label carries the percent while downloading", () => {
		render(
			<OfflinePackPreparingBanner
				visible={true}
				status="downloading"
				progress={7}
			/>,
		);
		const region = screen.getByRole("status");
		expect(region.getAttribute("aria-label")).toContain(
			"pack.downloadingOfflineEngineAria",
		);
		expect(region.getAttribute("aria-label")).toContain("percent=7");
	});
});
