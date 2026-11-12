// A pointerdown that dismisses on click-away must not count a click on a
// notification as "outside": sonner portals the toaster onto <body>, so the
// target is never inside the dismissing surface's own container.

const TOASTER_SELECTOR = "[data-sonner-toaster]";

/** True when the pointerdown landed inside the Sonner toaster. */
export function isToasterTarget(target: EventTarget | null): boolean {
	if (!(target instanceof Node)) return false;
	return document.querySelector(TOASTER_SELECTOR)?.contains(target) ?? false;
}
