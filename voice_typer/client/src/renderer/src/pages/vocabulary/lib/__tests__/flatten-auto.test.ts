import { describe, expect, it } from "vitest";

import { flattenEntries } from "../transform";

describe("flattenEntries, auto-apply origin marks", () => {
	it("flags entries whose correction matches the recorded auto value", () => {
		const rows = flattenEntries({
			misspellings: { jonathon: "jonathan", teh: "the" },
			_auto_applied: { misspellings: { jonathon: "jonathan" } },
		});
		const auto = rows.find((r) => r.original === "jonathon");
		const manual = rows.find((r) => r.original === "teh");
		expect(auto?.autoApplied).toBe(true);
		expect(manual?.autoApplied).toBe(false);
	});

	it("does not flag when the live correction differs from the recorded one", () => {
		const rows = flattenEntries({
			misspellings: { jonathon: "jonothan" },
			_auto_applied: { misspellings: { jonathon: "jonathan" } },
		});
		expect(rows[0]?.autoApplied).toBe(false);
	});

	it("defaults to unflagged without marks", () => {
		const rows = flattenEntries({ misspellings: { teh: "the" } });
		expect(rows[0]?.autoApplied).toBe(false);
	});
});
