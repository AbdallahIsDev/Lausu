import { render, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MeasuredSkeleton } from "../MeasuredSkeleton";

describe("MeasuredSkeleton", () => {
	it("puts the stack classes on the revealed content wrapper", async () => {
		const { container } = render(
			<MeasuredSkeleton
				data={{ label: "live content" }}
				sample={{ label: "sample content" }}
				id="measured-skeleton-test"
				label="Loading"
				stackClassName="gap-4 flex-1"
			>
				{(d) => <p>{d.label}</p>}
			</MeasuredSkeleton>,
		);

		const text = await waitFor(() => {
			const node = Array.from(container.querySelectorAll("p")).find(
				(el) => el.textContent === "live content",
			);
			if (!node) throw new Error("live content not revealed yet");
			return node;
		});

		const stack = text.parentElement;
		expect(stack?.className).toContain("flex");
		expect(stack?.className).toContain("flex-col");
		expect(stack?.className).toContain("gap-4");
		expect(stack?.className).toContain("flex-1");
	});
});
