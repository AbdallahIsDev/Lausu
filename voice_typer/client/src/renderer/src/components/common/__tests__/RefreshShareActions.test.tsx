import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RefreshShareActions } from "@/components/common/RefreshShareActions";
import type { ShareStatsActions } from "@/components/dashboard/ShareStatsDialog";
import { FALLBACK_THEME_PALETTE } from "@/lib/theme-palette";

afterEach(cleanup);

const actions: ShareStatsActions = {
	downloadImage: vi.fn().mockResolvedValue(null),
	saveImageAs: vi.fn().mockResolvedValue(null),
	copyImageToClipboard: vi.fn().mockResolvedValue(true),
	revealInFolder: vi.fn().mockResolvedValue(undefined),
};

function renderPair(showRefresh?: boolean) {
	return render(
		<RefreshShareActions
			agoLabel="5s ago"
			onRefresh={vi.fn()}
			showRefresh={showRefresh}
			actions={actions}
			stats={null}
			palette={FALLBACK_THEME_PALETTE}
			shareDisabled={false}
		/>,
	);
}

describe("RefreshShareActions — one joined group on every surface", () => {
	it("renders exactly one group with both actions as its direct children", () => {
		renderPair();
		const group = screen.getByTestId("action-buttons-group");
		expect(group.children).toHaveLength(2);
		expect(
			group.querySelector('[data-testid="last-updated-indicator"]'),
		).toBeTruthy();
		expect(group.querySelectorAll("button")).toHaveLength(2);
		// The divider rule only works when both buttons are direct children.
		expect(group.parentElement?.querySelectorAll("button")).toHaveLength(2);
	});

	it("keeps one group even when the freshness action is gated off", () => {
		renderPair(false);
		const group = screen.getByTestId("action-buttons-group");
		expect(screen.getAllByTestId("action-buttons-group")).toHaveLength(1);
		expect(group.children).toHaveLength(1);
		expect(
			group.querySelector('[data-testid="last-updated-indicator"]'),
		).toBeNull();
	});

	it("is the only composition on Home and Dashboard (global-first)", () => {
		const srcRoot = resolve(import.meta.dirname, "../../..");
		for (const page of ["pages/Home.tsx", "pages/Dashboard.tsx"]) {
			const src = readFileSync(resolve(srcRoot, page), "utf-8");
			expect(src.match(/<RefreshShareActions\b/g)).toHaveLength(1);
			expect(src).not.toContain("<LastUpdatedIndicator");
			expect(src).not.toContain("<ShareStatsDialog");
			expect(src).not.toContain("<ActionButtonsGroup");
		}
	});
});
