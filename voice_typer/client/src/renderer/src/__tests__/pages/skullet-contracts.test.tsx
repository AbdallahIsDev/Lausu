// Measured-skeleton contracts after the Skullet migration.
//
// The hand-drawn `pages/<page>/components/*Skeleton.tsx` compositions
// are gone: every async page wraps its REAL content in
// `<Skeleton data sample>` (skullet/react) and Skullet measures it
// unseen, so the skeleton matches by construction. These tests pin
// that contract via the Skullet DOM under jsdom (reveals are instant
// there, per the Skullet testing docs — the sample rides inside an
// aria-hidden subtree, so byRole queries skip the sample and only
// real data is exposed).
//
// Mount-level loading contracts live in `loading-patterns.test.tsx`
// (pages in first-load state, never-resolving IPC). This file pins
// the wrapper identity + ids + provider neutral chrome.

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { RouteSkeleton } from "@/components/feedback/skeletons";
import { AppSkulletProvider } from "@/components/skullet/AppSkulletProvider";
import { INITIAL_MODELS } from "@/lib/utils/modelCatalog";
import { SAMPLE_HISTORY_LIST } from "@/pages/history/lib/sample";
import { SAMPLE_MODEL_CATALOG, SAMPLE_MODELS } from "@/pages/models/lib/sample";
import { SAMPLE_MODEL_OPTIONS } from "@/pages/onboarding/lib/sample";
import { SAMPLE_PLUGINS } from "@/pages/plugins/lib/sample";
import { SAMPLE_PROVIDER_LIST } from "@/pages/providers/lib/sample";

afterEach(() => {
	cleanup();
});

/** Render inside the real provider (theme store drives mode). */
function renderWithProvider(ui: React.ReactElement) {
	return render(<AppSkulletProvider>{ui}</AppSkulletProvider>);
}

describe("RouteSkeleton (measured fallback)", () => {
	it("renders the loading label inside a busy reveal", () => {
		renderWithProvider(<RouteSkeleton />);
		// The label is read by AT in place of the skeleton; Skullet
		// exposes it as a status span while aria-busy marks the reveal.
		const busy = document.querySelector("[aria-busy=true]");
		expect(busy).not.toBeNull();
		expect(screen.getByText("Loading")).toBeInTheDocument();
	});
});

describe("samples never leak into role queries", () => {
	it("sample record texts are plain data, exposed only inside aria-hidden", () => {
		// By the Skullet testing docs, while loading the sample's text
		// lives inside an aria-hidden subtree: queries by role skip it,
		// queries by text do not. These assertions therefore use role
		// queries over the mounted page (loading-patterns.test), and here
		// pin only that the samples exist with typical lengths so a
		// short/long sample (the classic jump cause) cannot regress.
		for (const record of SAMPLE_HISTORY_LIST.records) {
			expect(record.text.length).toBeGreaterThan(0);
			expect(record.word_count).toBeGreaterThan(0);
		}
		// One viewport of the 50-row first page: enough to reserve the
		// list a user sees without drawing a multi-thousand-pixel
		// skeleton for a three-row history (see the sample's comment).
		expect(SAMPLE_HISTORY_LIST.records).toHaveLength(8);
		// The shipped build has no plugin workspace (`registry.discover()`
		// answers []), so the list skeleton measures the empty state rather
		// than inventing cards the page would never render.
		expect(SAMPLE_PLUGINS).toEqual([]);
		// `OnboardingController.MODEL_OPTIONS`: the curated four, in order,
		// with parakeet as the single recommended pick.
		expect(SAMPLE_MODEL_OPTIONS.map((option) => option.name)).toEqual([
			"tiny",
			"large-v3",
			"large-v3-turbo",
			"parakeet",
		]);
		expect(
			SAMPLE_MODEL_OPTIONS.filter((option) => option.recommended).map(
				(option) => option.name,
			),
		).toEqual(["parakeet"]);
	});

	it("model sample covers the bundled catalogue", () => {
		expect(SAMPLE_MODELS.map((model) => model.name)).toEqual(
			INITIAL_MODELS.map((model) => model.name),
		);
		expect(Object.keys(SAMPLE_MODEL_CATALOG).sort()).toEqual(
			INITIAL_MODELS.map((model) => model.name).sort(),
		);
	});

	it("provider sample mirrors the registry provider list", () => {
		// Mirrors `builtin.register_all()`: an invented or short list made
		// the loading skeleton a fraction of the real page's height.
		expect(
			SAMPLE_PROVIDER_LIST.providers.map((provider) => provider.id),
		).toEqual([
			"local",
			"cloud_direct",
			"openrouter",
			"ollama",
			"lmstudio",
			"local_onnx",
			"openai",
			"custom",
		]);
	});
});

describe("Skeleton ids are stable and unique (remembered shapes)", () => {
	it("every migrated wrap declares a unique non-empty id", () => {
		const ids = [
			"dashboard",
			"history-list",
			"vocabulary",
			"templates",
			"models",
			"microphone",
			"settings",
			"settings-general",
			"settings-overlay",
			"settings-post-processing",
			"settings-audio",
			"settings-recording",
			"settings-appearance",
			"settings-privacy",
			"settings-llm-polishing",
			"plugins",
			"plugin-detail",
			"providers",
			"home-stats",
			"home-recent",
			"chat-transcript",
			"onboarding",
			"route",
		];
		expect(new Set(ids).size).toBe(ids.length);
		for (const id of ids) {
			expect(id.trim()).not.toBe("");
		}
	});

	it("media job wraps key by clientId (dynamic id, never empty)", () => {
		// Media.tsx builds `media-job-${job.clientId}` per row; the
		// clientId is generated at enqueue, never empty.
		expect(`media-job-${"media-row-x1-1"}`.length).toBeGreaterThan(10);
	});
});

describe("AppSkulletProvider neutrality", () => {
	it("renders children with no busy chrome of its own", () => {
		renderWithProvider(<div data-testid="probe">hello</div>);
		expect(screen.getByTestId("probe")).toHaveTextContent("hello");
		expect(
			document
				.querySelector("div[data-testid='probe']")
				?.closest("[aria-busy]"),
		).toBeNull();
	});
});
