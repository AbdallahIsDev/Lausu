// lib/support.ts
// Single source for the in-app support surfaces (currently the bug-report
// composer). Kept in one module so the destination address and the
// generated environment block have exactly one definition.

import { APP_NAME } from "@/branding";

/**
 * Destination for in-app bug reports.
 *
 * OWNER: point this at a mailbox that is actually monitored. A wrong
 * address silently swallows every report the user sends, and there is no
 * bounce path back into the app.
 */
export const SUPPORT_EMAIL = "a.elfiky.dev@gmail.com";

/**
 * Environment lines appended to every report body.
 *
 * The user cannot be expected to know their build version or runtime, and
 * asking them to type it is the main reason bug reports arrive unusable.
 * Reads only values the renderer already holds; no IPC, no network.
 */
export function collectReportContext(appVersion: string): string[] {
	const lines = [`${APP_NAME}: ${appVersion}`];
	if (typeof navigator === "undefined") return lines;
	if (navigator.userAgent) lines.push(`Runtime: ${navigator.userAgent}`);
	if (navigator.language) lines.push(`UI language: ${navigator.language}`);
	return lines;
}
