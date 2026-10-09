// Boot-failure fallback: a calm status card when the renderer module
// graph never boots (transform/import failure, missing assets). React,
// i18n, and Tailwind are all UNAVAILABLE on this path by definition, so
// this file is dependency-free vanilla JS with inline styles, and its
// copy is English-only (no catalog to read from). Loaded as a classic
// script BEFORE main.tsx (module scripts always defer); same-origin, so
// no CSP hash plumbing (script-src 'self'). main.tsx sets
// window.__lausu_booted after first render; a slow-but-healthy boot that
// trips the watchdog self-corrects when React replaces #root children.
(() => {
	const TIMEOUT_MS = 20000;
	let shown = false;

	const el = (tag, style, text) => {
		const node = document.createElement(tag);
		if (style) node.setAttribute("style", style);
		if (text !== undefined) node.textContent = text;
		return node;
	};

	const show = (detail) => {
		if (shown || window.__lausu_booted) return;
		const root = document.getElementById("root");
		if (!root) return;
		shown = true;
		root.innerHTML = "";
		const wrap = el(
			"div",
			"min-height:100vh;display:flex;align-items:center;justify-content:center;" +
				"background:#0e0e11;padding:24px;margin:0;" +
				"font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;",
		);
		const card = el(
			"div",
			"max-width:440px;width:100%;background:#17171c;color:#fafafa;" +
				"border:1px solid rgba(255,255,255,0.08);border-radius:12px;" +
				"padding:32px 28px;text-align:center;",
		);
		const badge = el(
			"div",
			"width:44px;height:44px;border-radius:50%;margin:0 auto;" +
				"background:rgba(239,68,68,0.12);color:#ef4444;" +
				"font-size:22px;font-weight:700;line-height:44px;",
			"!",
		);
		badge.setAttribute("aria-hidden", "true");
		card.appendChild(badge);
		card.appendChild(
			el(
				"div",
				"font-size:17px;font-weight:600;margin:16px 0 8px;",
				"Couldn't start the interface",
			),
		);
		card.appendChild(
			el(
				"div",
				"color:#a1a1aa;font-size:13px;line-height:1.5;",
				"A client file failed to load. Reload the app to try again.",
			),
		);
		const btn = el(
			"button",
			"margin-top:20px;background:#2e6bf0;color:#fff;border:0;" +
				"border-radius:8px;padding:9px 20px;font-size:13px;font-weight:600;" +
				"cursor:pointer;",
			"Reload app",
		);
		btn.onclick = () => window.location.reload();
		card.appendChild(btn);
		if (detail) {
			const det = document.createElement("details");
			det.setAttribute(
				"style",
				"margin-top:16px;color:#71717a;font-size:12px;text-align:left;",
			);
			const sum = document.createElement("summary");
			sum.textContent = "Error details";
			sum.setAttribute("style", "cursor:pointer;");
			const pre = document.createElement("pre");
			pre.setAttribute(
				"style",
				"white-space:pre-wrap;word-break:break-word;margin-top:8px;",
			);
			// textContent, never innerHTML: loader messages echo paths.
			pre.textContent = String(detail).slice(0, 500);
			det.appendChild(sum);
			det.appendChild(pre);
			card.appendChild(det);
		}
		wrap.appendChild(card);
		root.appendChild(wrap);
	};

	window.__lausu_bootFailedDismiss = () => {
		if (!shown) return;
		shown = false;
		const root = document.getElementById("root");
		if (root) root.innerHTML = "";
	};

	// Module/import failures surface here (capture: resource errors don't
	// bubble). Script-only filter: image/font 404s must not trip the card.
	window.addEventListener(
		"error",
		(event) => {
			if (window.__lausu_booted) return;
			const target = event?.target ?? null;
			const src =
				target?.src !== undefined && target?.src !== null
					? String(target.src)
					: "";
			const msg = event?.message ? String(event.message) : "";
			if (target === window || /\.js(\?|$)/.test(src)) show(msg || src || null);
		},
		true,
	);
	window.addEventListener("unhandledrejection", (event) => {
		if (window.__lausu_booted) return;
		const reason = event?.reason ?? null;
		const msg =
			reason?.message !== undefined && reason?.message !== null
				? String(reason.message)
				: String(reason ?? "");
		show(msg || null);
	});
	setTimeout(() => {
		show(null);
	}, TIMEOUT_MS);
})();
