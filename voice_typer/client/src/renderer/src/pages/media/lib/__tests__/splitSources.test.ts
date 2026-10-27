// splitSources turns the Media page's one input field into the sources it
// names: several pasted links become several jobs, while a local path that
// contains spaces stays ONE source (it is a path, not a list).

import { describe, expect, it } from "vitest";

import { splitSources } from "../splitSources";

describe("splitSources", () => {
	it("keeps a single URL as one source", () => {
		expect(splitSources("https://www.youtube.com/watch?v=abc123")).toEqual([
			"https://www.youtube.com/watch?v=abc123",
		]);
	});

	it("splits two URLs separated by a newline", () => {
		expect(
			splitSources(
				"https://www.youtube.com/watch?v=aaa\nhttps://vimeo.com/222",
			),
		).toEqual(["https://www.youtube.com/watch?v=aaa", "https://vimeo.com/222"]);
	});

	it("splits two URLs separated by spaces", () => {
		expect(
			splitSources("https://a.example/one   https://b.example/two"),
		).toEqual(["https://a.example/one", "https://b.example/two"]);
	});

	it("strips trailing commas and semicolons from pasted URLs", () => {
		expect(
			splitSources(
				"https://a.example/one, https://b.example/two; https://c.example/three",
			),
		).toEqual([
			"https://a.example/one",
			"https://b.example/two",
			"https://c.example/three",
		]);
	});

	it("keeps a Windows path containing spaces as ONE source", () => {
		const path = "C:\\Users\\me\\My Videos\\How To Build a Setup.mp4";
		expect(splitSources(path)).toEqual([path]);
	});

	it("keeps a POSIX path containing spaces as ONE source", () => {
		const path = "/home/me/Videos/How To Build a Setup.mp4";
		expect(splitSources(path)).toEqual([path]);
	});

	it("collapses a duplicated URL into one source", () => {
		expect(
			splitSources("https://a.example/one\nhttps://a.example/one"),
		).toEqual(["https://a.example/one"]);
	});

	it("strips a wrapping closing paren but keeps a balanced one", () => {
		expect(
			sort(splitSources("(see https://a.example/one) https://b.example/two")),
		).toEqual(["https://a.example/one", "https://b.example/two"]);
		expect(
			sort(
				splitSources(
					"https://en.wikipedia.org/wiki/Foo_(bar) https://b.example/two",
				),
			),
		).toEqual([
			"https://b.example/two",
			"https://en.wikipedia.org/wiki/Foo_(bar)",
		]);
	});

	it("returns nothing for blank input", () => {
		expect(splitSources("")).toEqual([]);
		expect(splitSources("   \n\t ")).toEqual([]);
	});
});

function sort(items: string[]): string[] {
	return [...items].sort();
}
