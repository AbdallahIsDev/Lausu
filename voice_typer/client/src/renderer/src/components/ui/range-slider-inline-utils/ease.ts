/** Dragged handles and fills (sliders) — critically damped, so the thumb
 * follows the pointer and never rebounds off an end. */
export const SPRING_GLIDE = {
	stiffness: 700,
	damping: 50,
	mass: 0.5,
} as const;
