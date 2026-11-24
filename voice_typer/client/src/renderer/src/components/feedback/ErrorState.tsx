import { Alert02Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import type { Ref } from "react";

import { Button } from "@/components/ui/button";
import { t } from "@/i18n/i18n";

export interface ErrorStateProps {
	message: string;
	retryCount: number;
	copied: boolean;
	onTryAgain: () => void;
	onReload: () => void;
	onCopyError: () => void;
	primaryButtonRef?: Ref<HTMLButtonElement>;
}

export function ErrorState({
	message,
	retryCount,
	copied,
	onTryAgain,
	onReload,
	onCopyError,
	primaryButtonRef,
}: ErrorStateProps) {
	const retryFailed = retryCount > 0;

	return (
		<div
			className="flex min-h-screen items-center justify-center bg-surface-subtle p-6"
			role="alert"
			aria-live="assertive"
		>
			<div className="flex w-full max-w-lg flex-col items-center gap-4 rounded-lg border border-border/8 bg-surface px-6 py-8 text-center">
				<div className="flex rounded-full bg-destructive/10 p-3">
					<HugeiconsIcon
						icon={Alert02Icon}
						strokeWidth={2}
						className="h-10 w-10 text-destructive"
						aria-hidden="true"
					/>
				</div>
				<h1 className="text-xl font-medium text-foreground">
					{t("errorBoundary.title")}
				</h1>
				<p className="text-sm text-muted-foreground">
					{t("errorBoundary.description")}
				</p>
				<pre className="w-full overflow-auto rounded-lg border border-border/8 bg-muted p-4 font-mono text-start text-xs text-muted-foreground">
					{message}
				</pre>
				<div className="flex flex-wrap items-center justify-center gap-2">
					<Button
						type="button"
						variant="default"
						onClick={onTryAgain}
						ref={primaryButtonRef}
						className="focus-visible:ring-1 focus-visible:ring-ring"
					>
						{t("errorBoundary.tryAgain")}
					</Button>
					<Button type="button" variant="outline" onClick={onReload}>
						{t("errorBoundary.reloadApp")}
					</Button>
					<Button type="button" variant="outline" onClick={onCopyError}>
						{copied ? t("errorBoundary.copied") : t("errorBoundary.copyError")}
					</Button>
				</div>
				{retryFailed && (
					<p className="text-xs text-muted-foreground">
						{t("errorBoundary.retryFailed")}
					</p>
				)}
			</div>
		</div>
	);
}
