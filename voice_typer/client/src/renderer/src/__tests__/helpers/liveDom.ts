// Skullet keeps the outgoing skeleton ghost in the DOM (inside an inert,
// aria-hidden pane) while the live content reveals, so a bare getByText /
// getByTestId can match both copies. These helpers return the live tree only.
import { queryAllByTestId, queryAllByText } from "@testing-library/react";

function isLive(el: HTMLElement): boolean {
	return el.closest("[inert]") === null;
}

function onlyLive(matches: HTMLElement[], what: string): HTMLElement {
	const [only] = matches;
	if (!only || matches.length !== 1) {
		throw new Error(
			`Expected exactly one live element for ${what}, found ${matches.length}`,
		);
	}
	return only;
}

export function getLiveByTestId(
	id: string,
	container: HTMLElement = document.body,
): HTMLElement {
	return onlyLive(
		queryAllByTestId(container, id).filter(isLive),
		`[data-testid="${id}"]`,
	);
}

export function getLiveByText(
	text: string | RegExp,
	container: HTMLElement = document.body,
): HTMLElement {
	return onlyLive(
		queryAllByText(container, text).filter(isLive),
		`text "${String(text)}"`,
	);
}
