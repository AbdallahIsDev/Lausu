// ErrorBoundary, catches render errors so a single bad config or
// component crash doesn't white-screen the entire app (wired around
// <App /> in main.tsx).
//
// Recovery actions: "Try Again" re-mounts the children (staying
// enabled, and reporting when the retry crashed too), "Reload App"
// reloads the window, "Copy error" puts the error + React component
// stack on the clipboard for a bug report.
//
// ``componentDidCatch`` also forwards the error to the host so it lands
// in the file log (React's ``componentStack`` would be lost if only the
// console path existed).

import { Component, createRef, type ErrorInfo, type ReactNode } from "react";
import { ErrorState } from "@/components/feedback/ErrorState";
import { t } from "@/i18n/i18n";

interface ErrorBoundaryProps {
	children: ReactNode;
	fallback?: ReactNode;
}

interface ErrorBoundaryState {
	hasError: boolean;
	error: Error | null;
	errorInfo: ErrorInfo | null;
	copied: boolean;
	// Failed retries so far. Drives the "retry didn't help" hint; it
	// never disables Try Again, re-clicking is the user's call.
	retryCount: number;
}

export class ErrorBoundary extends Component<
	ErrorBoundaryProps,
	ErrorBoundaryState
> {
	// Primary recovery button ("Try Again"), focused when the fallback
	// appears so keyboard / SR users land on the actionable control.
	primaryButtonRef = createRef<HTMLButtonElement>();

	constructor(props: ErrorBoundaryProps) {
		super(props);
		this.state = {
			hasError: false,
			error: null,
			errorInfo: null,
			copied: false,
			retryCount: 0,
		};
	}

	static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
		return { hasError: true, error };
	}

	componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
		// DevTools-only: the host does not capture the webview console,
		// the `logError` forward below is what reaches the file log.
		console.error(
			"[renderer:ErrorBoundary] Caught render error:",
			error,
			errorInfo,
		);

		try {
			window.window_
				?.logError?.({
					kind: "react-render",
					message: error.message,
					stack: error.stack,
					componentStack: errorInfo.componentStack ?? undefined,
				})
				.catch((err: unknown) => {
					console.warn("[renderer:ErrorBoundary] logError IPC failed:", err);
				});
		} catch (err) {
			console.warn("[renderer:ErrorBoundary] logError call failed:", err);
		}

		// Kept in state so "Copy error" can include the component stack.
		this.setState({ errorInfo });
	}

	componentDidMount(): void {
		// ``componentDidUpdate`` does not run for a crash on first paint,
		// which is the common case.
		this.focusPrimaryButton();
	}

	componentDidUpdate(
		_prevProps: ErrorBoundaryProps,
		prevState: ErrorBoundaryState,
	): void {
		if (!prevState.hasError && this.state.hasError) {
			this.focusPrimaryButton();
		} else if (prevState.hasError && !this.state.hasError) {
			// The retry committed cleanly: forget the failed attempts so
			// their hint cannot leak onto a later, unrelated crash.
			this.setState({ retryCount: 0 });
		}
	}

	private focusPrimaryButton(): void {
		if (!this.state.hasError) return;
		this.primaryButtonRef.current?.focus();
	}

	handleReset = (): void => {
		this.setState((prev) => ({
			hasError: false,
			error: null,
			errorInfo: null,
			copied: false,
			retryCount: prev.retryCount + 1,
		}));
	};

	handleReload = (): void => {
		window.location.reload();
	};

	handleCopyError = (): void => {
		const { error, errorInfo } = this.state;
		const lines: string[] = [];
		if (error) {
			lines.push(`${error.name}: ${error.message}`);
			if (error.stack) lines.push(error.stack);
		} else {
			lines.push(t("errorBoundary.unknownError"));
		}
		if (errorInfo?.componentStack) {
			// Leading newline keeps the pasted blob's separation between
			// the JS stack and the React component tree.
			lines.push(`\n${t("errorBoundary.componentStackLabel")}`);
			lines.push(String(errorInfo.componentStack));
		}
		const payload = lines.join("\n");
		try {
			if (navigator?.clipboard?.writeText) {
				navigator.clipboard
					.writeText(payload)
					.then(() => this.flashCopied())
					.catch(() => this.copyViaTextarea(payload));
			} else {
				this.copyViaTextarea(payload);
			}
		} catch {
			this.copyViaTextarea(payload);
		}
	};

	copyViaTextarea = (payload: string): void => {
		try {
			const ta = document.createElement("textarea");
			ta.value = payload;
			ta.setAttribute("readonly", "");
			ta.style.position = "absolute";
			ta.style.left = "-9999px";
			document.body.appendChild(ta);
			ta.select();
			document.execCommand("copy");
			document.body.removeChild(ta);
			this.flashCopied();
		} catch (e) {
			// Last resort: the error text stays on screen for manual copy.
			console.warn(
				"[renderer:ErrorBoundary] clipboard fallback copy failed:",
				e,
			);
		}
	};

	// "Copied!" flash timer, cancelled on unmount.
	copiedTimer: number | null = null;

	flashCopied = (): void => {
		this.setState({ copied: true });
		if (this.copiedTimer !== null) {
			window.clearTimeout(this.copiedTimer);
		}
		this.copiedTimer = window.setTimeout(() => {
			this.copiedTimer = null;
			this.setState({ copied: false });
		}, 2000);
	};

	componentWillUnmount(): void {
		if (this.copiedTimer !== null) {
			window.clearTimeout(this.copiedTimer);
			this.copiedTimer = null;
		}
	}

	render(): ReactNode {
		if (this.state.hasError) {
			if (this.props.fallback) {
				return this.props.fallback;
			}

			return (
				<ErrorState
					message={this.state.error?.message ?? t("errorBoundary.unknownError")}
					retryCount={this.state.retryCount}
					copied={this.state.copied}
					onTryAgain={this.handleReset}
					onReload={this.handleReload}
					onCopyError={this.handleCopyError}
					primaryButtonRef={this.primaryButtonRef}
				/>
			);
		}

		return this.props.children;
	}
}
