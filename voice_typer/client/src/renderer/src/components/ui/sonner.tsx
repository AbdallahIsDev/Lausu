"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { Toaster as Sonner, type ToasterProps } from "sonner";
import { getLocale, isRtlLocale, subscribeLocale, t } from "@/i18n/i18n";
import { buttonVariants } from "./button";

function useResolvedTheme(): "light" | "dark" {
	const [resolved, setResolved] = useState<"light" | "dark">(() => {
		if (typeof document === "undefined") return "light";
		return document.documentElement.classList.contains("dark")
			? "dark"
			: "light";
	});

	useEffect(() => {
		if (typeof document === "undefined") return;
		const root = document.documentElement;
		// Initial sync.
		setResolved(root.classList.contains("dark") ? "dark" : "light");
		// Watch for class changes (useTheme.ts toggles `dark` on every
		// theme change). MutationObserver is the standard pattern for
		// watching class attribute changes.
		const observer = new MutationObserver(() => {
			setResolved(root.classList.contains("dark") ? "dark" : "light");
		});
		observer.observe(root, {
			attributes: true,
			attributeFilter: ["class"],
		});
		return () => observer.disconnect();
	}, []);

	return resolved;
}

function useRtlLocale(): boolean {
	return useSyncExternalStore(
		subscribeLocale,
		() => isRtlLocale(getLocale()),
		() => false,
	);
}

const Toaster = ({ ...props }: ToasterProps) => {
	const theme = useResolvedTheme();
	// Position follows the ACTIVE locale on every change: bottom-right
	// in LTR locales, bottom-left in RTL locales (Arabic) so the toaster
	// sits in the visually-far corner from the reading start.
	const rtl = useRtlLocale();

	return (
		<Sonner
			theme={theme}
			closeButton
			// Explicit nulls kill sonner's built-in per-type glyphs: omitting the
			// prop falls back to getAsset(type) (sonner index.js ~649). Nulls are
			// the documented kill-shot (sonner issue #600->#610). The close (X)
			// stays — it is a control, not a status icon.
			icons={{
				success: null,
				info: null,
				warning: null,
				error: null,
				loading: null,
			}}
			position={rtl ? "bottom-left" : "bottom-right"}
			containerAriaLabel={t("a11y.notifications")}
			toastOptions={{
				closeButtonAriaLabel: t("a11y.close"),
				// Sonner's <li> ships class-less, so it never matched the
				// squircle family index.css shapes via :where(.rounded-lg).
				classNames: {
					toast: "rounded-lg",
					// Shared Button (xs) so toast action/cancel buttons read as
					// the same family as the card controls, denser. Hierarchy
					// via VARIANT only: Lower = outline (visible, neutral),
					// Keep = ghost (de-emphasized). No white/blue fills here.
					actionButton: buttonVariants({ variant: "outline", size: "xs" }),
					cancelButton: buttonVariants({ variant: "ghost", size: "xs" }),
				},
			}}
			duration={4000}
			visibleToasts={6}
			expand={false}
			className="toaster group"
			style={
				{
					"--normal-bg": "var(--surface)",
					"--normal-text": "var(--foreground)",
					// Match settings/cards: 1px border at the same faded
					// opacity as `border-border/10` (full --border is too loud).
					"--normal-border":
						"color-mix(in srgb, var(--border) 10%, transparent)",
					// Toasts match the app surface radius (rounded-lg), not
					// the generic --radius, so they track theme changes.
					"--border-radius": "var(--radius-lg)",
				} as React.CSSProperties
			}
			{...props}
		/>
	);
};

export { Toaster };
