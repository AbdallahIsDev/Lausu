// components/settings/WhatsNewModal.tsx
//
// In-app release notes. Replaces the old "View Changelog" button, which
// opened the project's GitHub releases page in a browser — a shipped
// application should show what changed without handing the user off to a
// repository.
//
// The notes are the newest block of the repo's `CHANGELOG.md`, inlined at
// build time as `virtual:release-notes` (see `release-notes-plugin.ts`) so
// the modal works offline and can never disagree with the file that ships in
// the release. A direct `?raw` import is not possible: the changelog lives
// outside the renderer root, which Vite's fs guard denies.

import changelogRaw from "virtual:release-notes";
import { memo, type ReactNode, useMemo } from "react";
import { Modal, ModalFooter } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import {
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { useT } from "@/i18n/i18n";
import pkg from "../../../../../package.json";

const APP_VERSION = pkg.version as string;

interface ReleaseSection {
	title: string;
	items: string[];
}

/**
 * Extract the newest release block from Keep-a-Changelog markdown: the
 * first `##` heading (the `[Unreleased]` section) down to the next `##`,
 * grouped by its `###` topic headings.
 *
 * Deliberately narrow. A general markdown renderer would be a large
 * dependency for a surface that only ever renders this one file's shape.
 */
export function parseLatestRelease(raw: string): ReleaseSection[] {
	const lines = raw.split(/\r?\n/);
	const start = lines.findIndex((line) => /^##\s/.test(line));
	if (start === -1) return [];

	const sections: ReleaseSection[] = [];
	let current: ReleaseSection | null = null;
	for (const line of lines.slice(start + 1)) {
		if (/^##\s/.test(line)) break;

		const heading = line.match(/^###\s+(.*)$/);
		if (heading) {
			current = { title: (heading[1] ?? "").trim(), items: [] };
			sections.push(current);
			continue;
		}
		const bullet = line.match(/^-\s+(.*)$/);
		if (bullet && current) {
			current.items.push((bullet[1] ?? "").trim());
			continue;
		}
		// Wrapped bullet text: a hard-wrapped continuation line belongs to
		// the item above it, not to a new one.
		if (current && current.items.length > 0 && /^\s+\S/.test(line)) {
			current.items[current.items.length - 1] += ` ${line.trim()}`;
		}
	}
	return sections.filter((section) => section.items.length > 0);
}

/** Render the inline subset the changelog uses: `**bold**` and `` `code` ``. */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
	const nodes: ReactNode[] = [];
	const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
	let cursor = 0;
	let match = pattern.exec(text);
	let index = 0;
	while (match !== null) {
		if (match.index > cursor) nodes.push(text.slice(cursor, match.index));
		const token = match[0];
		if (token.startsWith("**")) {
			nodes.push(
				<strong
					key={`${keyPrefix}-b${index}`}
					className="font-medium text-foreground"
				>
					{token.slice(2, -2)}
				</strong>,
			);
		} else {
			nodes.push(
				<code
					key={`${keyPrefix}-c${index}`}
					className="rounded bg-muted px-1 py-0.5 font-mono text-xs"
				>
					{token.slice(1, -1)}
				</code>,
			);
		}
		cursor = match.index + token.length;
		index += 1;
		match = pattern.exec(text);
	}
	if (cursor < text.length) nodes.push(text.slice(cursor));
	return nodes;
}

interface WhatsNewModalProps {
	open: boolean;
	onClose: () => void;
}

function WhatsNewModalInner({ open, onClose }: WhatsNewModalProps) {
	const t = useT();
	const sections = useMemo(() => parseLatestRelease(changelogRaw), []);

	return (
		<Modal
			open={open}
			onClose={onClose}
			size="lg"
			// The panel clips instead of scrolling: an internal scrollbar on
			// a rounded panel escapes the corner radius on Windows classic
			// scrollbars. Header + body scroll together in the inner wrapper.
			className="max-h-[85vh] grid-rows-[minmax(0,1fr)] overflow-hidden shadow-none"
		>
			<div className="-mx-6 -mb-6 flex min-h-0 flex-col gap-5 overflow-y-auto px-6 pb-6">
				<DialogHeader>
					<DialogTitle>{t("about.whatsNewTitle")}</DialogTitle>
					<DialogDescription>
						{t("about.versionValue", { version: APP_VERSION })}
					</DialogDescription>
				</DialogHeader>

				{sections.length === 0 ? (
					<p className="text-sm text-muted-foreground">
						{t("about.whatsNewEmpty")}
					</p>
				) : (
					sections.map((section) => (
						<div key={section.title} className="flex flex-col gap-2">
							<h3 className="text-sm font-medium text-foreground">
								{section.title}
							</h3>
							<ul className="flex list-disc flex-col gap-2 ps-5 text-sm text-muted-foreground">
								{section.items.map((item) => (
									<li key={item.slice(0, 60)}>
										{renderInline(item, item.slice(0, 24))}
									</li>
								))}
							</ul>
						</div>
					))
				)}

				<ModalFooter>
					<Button variant="outline" onClick={onClose}>
						{t("common.close")}
					</Button>
				</ModalFooter>
			</div>
		</Modal>
	);
}

export const WhatsNewModal = memo(WhatsNewModalInner);
