// One-line label for a queued media source: the file name for a local
// path, "host/path-tail" for a link. The full source stays in the tooltip
// (`title`) so a long path never blows the row layout.

export function describeMediaSource(source: string): string {
	const text = source.trim();
	if (!text) return "";
	if (/^https?:\/\//i.test(text)) {
		try {
			const url = new URL(text);
			const tail = url.pathname.split("/").filter(Boolean).pop();
			return tail
				? `${url.hostname}/${decodeURIComponent(tail)}`
				: url.hostname;
		} catch {
			return text;
		}
	}
	const parts = text.split(/[\\/]/).filter(Boolean);
	return parts.length > 0 ? (parts[parts.length - 1] as string) : text;
}
