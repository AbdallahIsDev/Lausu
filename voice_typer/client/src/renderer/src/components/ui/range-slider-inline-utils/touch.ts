/** Pointer capture, best effort. WebKit throws when the pointer is already
 * gone; touch pointers carry implicit capture, so losing it is never fatal. */
export function capturePointer(element: Element, pointerId: number) {
	try {
		element.setPointerCapture(pointerId);
	} catch {
		// Pointer is no longer active.
	}
}

/** Release a capture taken with `capturePointer`, ignoring a stale pointer. */
export function releasePointer(element: Element, pointerId: number) {
	try {
		if (element.hasPointerCapture(pointerId)) {
			element.releasePointerCapture(pointerId);
		}
	} catch {
		// Capture was already dropped by the browser.
	}
}

/** Opt a control surface out of iOS's long-press callout and selection, so a
 * drag never turns into text selection. */
export const TOUCH_GESTURE_CLASS = "select-none [-webkit-touch-callout:none]";
