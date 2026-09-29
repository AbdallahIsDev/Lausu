"use client";

import {
	Alert02Icon,
	CheckmarkCircle02Icon,
	InformationCircleIcon,
	Loading03Icon,
	MultiplicationSignCircleIcon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useEffect, useState, useSyncExternalStore } from "react";
import { Toaster as Sonner, type ToasterProps } from "sonner";
import { getLocale, isRtlLocale, subscribeLocale, t } from "@/i18n/i18n";

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
			position={rtl ? "bottom-left" : "bottom-right"}
			containerAriaLabel={t("a11y.notifications")}
			toastOptions={{
				closeButtonAriaLabel: t("a11y.close"),
			}}
			duration={4000}
			visibleToasts={6}
			expand={false}
			className="toaster group"
			icons={{
				success: (
					<HugeiconsIcon
						icon={CheckmarkCircle02Icon}
						strokeWidth={1.625}
						className="size-4"
					/>
				),
				info: (
					<HugeiconsIcon
						icon={InformationCircleIcon}
						strokeWidth={1.625}
						className="size-4"
					/>
				),
				warning: (
					<HugeiconsIcon
						icon={Alert02Icon}
						strokeWidth={1.625}
						className="size-4"
					/>
				),
				error: (
					<HugeiconsIcon
						icon={MultiplicationSignCircleIcon}
						strokeWidth={1.625}
						className="size-4"
					/>
				),
				loading: (
					<HugeiconsIcon
						icon={Loading03Icon}
						strokeWidth={1.625}
						className="size-4 animate-spin"
					/>
				),
			}}
			style={
				{
					"--normal-bg": "var(--surface)",
					"--normal-text": "var(--foreground)",
					// Match settings/cards: 1px border at the same faded
					// opacity as `border-border/10` (full --border is too loud).
					"--normal-border":
						"color-mix(in srgb, var(--border) 10%, transparent)",
					"--border-radius": "var(--radius)",
				} as React.CSSProperties
			}
			{...props}
		/>
	);
};

export { Toaster };
