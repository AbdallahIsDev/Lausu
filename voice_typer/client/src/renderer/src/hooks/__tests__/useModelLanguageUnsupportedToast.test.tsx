import { renderHook } from "@testing-library/react";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useModelLanguageUnsupportedToast } from "@/hooks/useModelLanguageUnsupportedToast";

// Capture the handler usePythonEvent registers so we can fire it.
const registered = new Map<string, (data?: unknown) => unknown>();
const onOpenModels = vi.fn();
const t = vi.fn((key: string, params?: Record<string, string>) => {
	// Language labels resolve through their own keys; the message gets the
	// resolved name interpolated so an assertion can see the real wording.
	if (key === "degradation.modelLanguageUnsupported") {
		return `${params?.model} does not support ${params?.language}.`;
	}
	if (key === "degradation.modelLanguageUnsupportedHint")
		return "hint.openModels";
	if (key === "common.openModels") return "Open Models";
	if (key === "settings.languageArabic") return "Arabic";
	if (key === "settings.languageEnglish") return "English";
	return key;
});

vi.mock("@/hooks/usePython", () => ({
	usePythonEvent: (type: string, handler: (data?: unknown) => unknown) => {
		registered.set(type, handler);
	},
}));

vi.mock("sonner", () => ({
	toast: { warning: vi.fn() },
}));

beforeEach(() => {
	registered.clear();
	vi.clearAllMocks();
});

describe("useModelLanguageUnsupportedToast", () => {
	it("registers a handler for model_language_unsupported", () => {
		renderHook(() => useModelLanguageUnsupportedToast(t, onOpenModels));
		expect(registered.has("model_language_unsupported")).toBe(true);
	});

	it("names the model and the localized language, with a Models-page action", () => {
		renderHook(() => useModelLanguageUnsupportedToast(t, onOpenModels));
		const handler = registered.get("model_language_unsupported");
		expect(handler).toBeDefined();
		handler?.({ model: "Parakeet Ultra", language: "ar" });

		expect(t).toHaveBeenCalledWith("settings.languageArabic");
		expect(toast.warning).toHaveBeenCalledWith(
			"Parakeet Ultra does not support Arabic.",
			{
				id: "model-language-unsupported:Parakeet Ultra:ar",
				description: "hint.openModels",
				duration: 8000,
				action: { label: "Open Models", onClick: onOpenModels },
			},
		);
	});

	it("falls back to the upper-cased code when the locale has no label", () => {
		renderHook(() => useModelLanguageUnsupportedToast(t, onOpenModels));
		const handler = registered.get("model_language_unsupported");
		handler?.({ model: "Parakeet Ultra", language: "zz" });

		expect(toast.warning).toHaveBeenCalledWith(
			"Parakeet Ultra does not support ZZ.",
			expect.objectContaining({ duration: 8000 }),
		);
	});

	it("ignores a payload without both fields", () => {
		renderHook(() => useModelLanguageUnsupportedToast(t, onOpenModels));
		const handler = registered.get("model_language_unsupported");
		handler?.({ model: "Parakeet Ultra" });
		handler?.({ language: "ar" });
		handler?.(undefined);
		expect(toast.warning).not.toHaveBeenCalled();
	});
});
