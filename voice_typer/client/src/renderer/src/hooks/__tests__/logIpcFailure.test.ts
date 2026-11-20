import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { logIpcFailure } from "../connectionStatus";

describe("logIpcFailure", () => {
	beforeEach(() => {
		vi.spyOn(console, "debug").mockImplementation(() => {});
		vi.spyOn(console, "warn").mockImplementation(() => {});
	});

	afterEach(() => {
		vi.restoreAllMocks();
	});

	it("keeps an expected pre-bind failure out of the warning channel", () => {
		logIpcFailure("probe", "failed:", new Error("sidecar not connected"), true);
		expect(console.debug).toHaveBeenCalledWith(
			"[renderer:probe] failed:",
			expect.any(Error),
		);
		expect(console.warn).not.toHaveBeenCalled();
	});

	it("still warns about a verdict error", () => {
		logIpcFailure("probe", "failed:", new Error("auth failed"), true);
		expect(console.warn).toHaveBeenCalledWith(
			"[renderer:probe] failed:",
			expect.any(Error),
		);
		expect(console.debug).not.toHaveBeenCalled();
	});

	it("warns when a transient failure is no longer expected", () => {
		logIpcFailure(
			"probe",
			"failed:",
			new Error("sidecar not connected"),
			false,
		);
		expect(console.warn).toHaveBeenCalledWith(
			"[renderer:probe] failed:",
			expect.any(Error),
		);
		expect(console.debug).not.toHaveBeenCalled();
	});
});
