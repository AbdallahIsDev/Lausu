// Split the Media page's single input into the sources it actually names.
//
// Pasting a playlist-worth of links into one field used to submit the whole
// blob as ONE source, so the resolver saw "url1\nurl2\nurl3" and failed with
// `resolve_failed`. Several links now become several jobs.
//
// The hard rule is the opposite case: a LOCAL PATH may contain spaces, and a
// path is never a list. Splitting on whitespace would turn
// `C:\Users\me\My Videos\clip.mp4` into three broken sources, so a path is
// returned verbatim unless at least two real URLs are present.

const URL_PATTERN = /https?:\/\/[^\s,]+/gi;

/** Drop trailing sentence punctuation that a paste drags along.
 *
 * `,` and `;` are never part of a URL. A `)` is only stripped when the URL
 * has no `(` of its own, so a Wikipedia-style `.../Foo_(bar)` survives while
 * a link wrapped in prose parens does not.
 */
function trimTrailingPunctuation(token: string): string {
	let url = token;
	for (;;) {
		const last = url.charAt(url.length - 1);
		if (last === "," || last === ";") {
			url = url.slice(0, -1);
			continue;
		}
		if (last === ")" && !url.includes("(")) {
			url = url.slice(0, -1);
			continue;
		}
		return url;
	}
}

/**
 * The sources named by `raw`.
 *
 * - empty / whitespace → `[]`
 * - two or more URLs → those URLs (de-duplicated, input order)
 * - anything else → `[raw.trim()]`, i.e. one URL or one local path, kept
 *   whole so a path containing spaces stays a single source.
 */
export function splitSources(raw: string): string[] {
	const trimmed = raw.trim();
	if (!trimmed) return [];

	const matches = trimmed.match(URL_PATTERN) ?? [];
	// The threshold is the number of URLs actually present, BEFORE
	// de-duplication: pasting the same link twice must still collapse to one
	// job rather than fall through to "one blob" and fail to resolve.
	if (matches.length < 2) return [trimmed];

	const urls: string[] = [];
	const seen = new Set<string>();
	for (const match of matches) {
		const url = trimTrailingPunctuation(match);
		if (!url || seen.has(url)) continue;
		seen.add(url);
		urls.push(url);
	}
	return urls.length > 0 ? urls : [trimmed];
}
