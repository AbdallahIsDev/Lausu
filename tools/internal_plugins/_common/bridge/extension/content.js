'use strict';

// Page-side driver for the Claude tab, in the content script's isolated world.
// It only reads the page and clicks the platform's own controls. It never
// overrides navigator/document state, never fakes visibility, and never types
// into the composer.

(function () {
  const CFG = self.ANTHROPIC_STT_CONFIG || {};
  const HOST = (typeof location !== 'undefined' && location && location.host) || '';
  const PLATFORM = HOST.includes('gemini.google.com')
    ? 'gemini'
    : HOST.includes('claude.ai')
      ? 'claude'
      : HOST.includes('chatgpt.com')
        ? 'chatgpt'
        : '';
  // Unknown host: a clean no-op. Never inject a selector set by guessing.
  if (!PLATFORM) return;
  const SEL = (CFG.platforms && CFG.platforms[PLATFORM]) || {};
  const IDLE_SLOT = SEL.idleSlot || '';
  const COMPOSER = SEL.composer || '';
  // Live dictation streams into the composer on both tested platforms; the
  // selector is a per-platform anchor, never a generic page-wide search.
  const LIVE_TEXT_SELECTOR = SEL.liveTextSelector || '';
  // Claude streams live words into hidden spans; a platform can declare the
  // exact structure and extraction method instead of relying on innerText.
  const LIVE_TEXT = SEL.liveText || null;
  const MIC_SELECTOR = SEL.micSelector || '';
  const STOP_SELECTOR = SEL.stopSelector || '';
  // The COMMIT and DISCARD controls are siblings while recording: "Finish
  // dictation" keeps the transcript, "Cancel dictation" throws it away. They
  // must never share a selector -- stopping through the discard control is
  // how a whole dictation used to disappear.
  const CANCEL_SELECTOR = SEL.cancelSelector || '';
  const NEW_CHAT_NAMES = (SEL.newChatNames || []).map((name) => name.toLowerCase());
  // A discard control is OPTIONAL: Gemini exposes only the Dictate/Stop toggle,
  // so requiring CANCEL_SELECTOR made that platform permanently unusable
  // (`selectors-missing` on every start). Cancel() still prefers a real discard
  // control whenever one exists -- the commit control is never used as a
  // substitute for it (C-ASR-4).
  const SELECTORS_READY = !!(COMPOSER && MIC_SELECTOR && STOP_SELECTOR && IDLE_SLOT);

  const state = { recording: false, starting: null, enabled: true };

  // Per-profile switch from the popup. Absent means enabled, so an existing
  // install keeps working; a profile the owner does not dictate from can be
  // switched off instead of being uninstalled.
  try {
    chrome.storage.local.get('enabled', (stored) => {
      state.enabled = stored && stored.enabled !== false;
    });
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === 'local' && changes.enabled) state.enabled = changes.enabled.newValue !== false;
    });
    chrome.runtime.onMessage.addListener((msg) => {
      if (msg && msg.type === 'stt-bridge-enabled') state.enabled = msg.enabled !== false;
    });
  } catch (_) {}

  class CmdError extends Error {
    constructor(kind, message, details) {
      super(message);
      this.kind = kind;
      if (details !== undefined) this.details = details;
    }
  }

  function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  // A signed-out Claude answers with `/api/challenge_redirect?to=<encoded
  // /login>` as often as a plain `/login`; testing the raw URL misses the
  // encoded target, so decode before deciding.
  function isSignedOutUrl(url) {
    let decoded = String(url);
    try {
      decoded = decodeURIComponent(decoded);
    } catch (_) {}
    return /\/login|challenge_redirect|\/auth\/|accounts\.google\.com/i.test(decoded);
  }

  function isChallenge() {
    try {
      if (/just a moment|performing security verification/i.test(document.title || '')) return true;
      const body = (document.body && document.body.innerText) || '';
      return /performing security verification|verify you are not a bot/i.test(body);
    } catch (_) {
      return false;
    }
  }

  // ChatGPT serves the guest composer at "/" with visible Log in / Sign up
  // controls; the URL never changes, so a URL-only check misses the state and
  // the mic click silently no-ops (OpenAI requires a signed-in session).
  function isSignedOutPage() {
    if (PLATFORM !== 'chatgpt') return false;
    try {
      const labels = Array.from(document.querySelectorAll('button, a'))
        .filter(isClickable)
        .map((el) => (el.textContent || el.getAttribute('aria-label') || '').trim());
      const hasLogin = labels.some((text) => /^(log in|sign in)$/i.test(text));
      const hasSignup = labels.some((text) => /^(sign up|sign up for free)$/i.test(text));
      return hasLogin && hasSignup;
    } catch (_) {
      return false;
    }
  }

  function pageState() {
    if (isSignedOutUrl(location.href) || isSignedOutPage()) return 'signed_out';
    if (isChallenge()) return 'challenge';
    return 'ok';
  }

  // The selector list is a PRIORITY list, not one big union: a candidate that
  // does not exist on this page is skipped and the next one is tried. That
  // keeps a stale anchor (a leftover `#prompt-textarea` from an older
  // release) from shadowing the live composer. Commas inside a functional
  // pseudo-class (`:is(a, b)`) do not split the list.
  function splitSelectors(list) {
    const out = [];
    let depth = 0;
    let quote = '';
    let current = '';
    for (const ch of String(list || '')) {
      if (quote) {
        current += ch;
        if (ch === quote) quote = '';
        continue;
      }
      if (ch === '"' || ch === "'") {
        quote = ch;
        current += ch;
        continue;
      }
      if (ch === '(') depth += 1;
      if (ch === ')') depth = Math.max(0, depth - 1);
      if (ch === ',' && depth === 0) {
        if (current.trim()) out.push(current.trim());
        current = '';
        continue;
      }
      current += ch;
    }
    if (current.trim()) out.push(current.trim());
    return out;
  }

  // A control the user cannot see is not the control. Only a POSITIVE signal
  // counts: an element with no layout API (a minimal DOM) is never hidden.
  function isHiddenElement(el) {
    try {
      if (!el) return true;
      if (typeof el.getBoundingClientRect !== 'function') return false;
      const rect = el.getBoundingClientRect();
      if (rect && (rect.width > 0 || rect.height > 0)) return false;
      if (typeof getComputedStyle !== 'function') return false;
      const style = getComputedStyle(el);
      if (!style) return false;
      if (style.display === 'none' || style.visibility === 'hidden') return true;
      if (Number(style.opacity || 1) === 0) return true;
      // A zero rect with a visible style is a collapsed clone of the anchor.
      return true;
    } catch (_) {
      return false;
    }
  }

  function composerBox() {
    let fallback = null;
    try {
      for (const candidate of splitSelectors(COMPOSER)) {
        let first = null;
        try {
          first = document.querySelector(candidate);
        } catch (_) {
          // An invalid candidate must not take the whole platform down.
          continue;
        }
        if (!first) continue;
        if (!isHiddenElement(first)) return first;
        // The first match is hidden (a stale duplicate of the anchor): a
        // VISIBLE match of the same anchor is the box the user types in.
        try {
          const visible = Array.from(document.querySelectorAll(candidate)).find(
            (el) => !isHiddenElement(el),
          );
          if (visible) return visible;
        } catch (_) {}
        if (!fallback) fallback = first;
      }
      // Nothing visible matched, but the anchor EXISTS: report it as present
      // rather than pretending the platform has no composer at all.
      return fallback;
    } catch (_) {
      return null;
    }
  }

  // A value-backed composer (a textarea) keeps its text in `.value`; its DOM
  // text nodes are EMPTY, so reading innerText/textContent would report an
  // empty composer forever and the transcript would never be scraped.
  function isValueBacked(box) {
    try {
      const tag = (box && box.tagName ? box.tagName : '').toLowerCase();
      if (tag === 'textarea' || tag === 'input') return true;
      return typeof box.value === 'string';
    } catch (_) {
      return false;
    }
  }

  function composerText() {
    const box = composerBox();
    if (!box) return '';
    try {
      if (isValueBacked(box)) return String(box.value || '').trim();
      // A ProseMirror transcript can span several paragraphs: joining them
      // keeps the whole text instead of the first paragraph only.
      let rich = '';
      if (typeof box.querySelectorAll === 'function') {
        rich = Array.from(box.querySelectorAll('p'))
          .map((p) => (p.innerText || p.textContent || ''))
          .filter((t) => t.trim())
          .join('\n')
          .trim();
      } else {
        const first = box.querySelector('p');
        rich = first ? String(first.innerText || '').trim() : '';
      }
      if (rich) return rich;
      const text = (box.innerText || box.textContent || '').trim();
      const placeholder =
        box.getAttribute('data-placeholder') || box.getAttribute('aria-placeholder') || '';
      if (placeholder && text === placeholder.trim()) return '';
      return text;
    } catch (_) {
      return '';
    }
  }

  // Read-only snapshot of the text already visible on the page. The composer
  // is cumulative on ChatGPT and Claude (measured 2026-11-27); the interim
  // word chip is deliberately NOT used because it is rewritten every tick.
  function draftSnapshot() {
    if (LIVE_TEXT && LIVE_TEXT.selector) {
      const parts = [];
      for (const candidate of splitSelectors(LIVE_TEXT.selector)) {
        let nodes = [];
        try {
          nodes = Array.from(document.querySelectorAll(candidate));
        } catch (_) {
          continue;
        }
        for (const node of nodes) {
          let text = '';
          if (LIVE_TEXT.method === 'value') text = typeof node.value === 'string' ? node.value : '';
          else text = node.textContent || '';
          if (text.trim()) parts.push(text); // keep logical text (spaces, RTL order, emoji) intact
        }
        if (parts.length) break;
      }
      if (parts.length) {
        return { text: parts.join('').trim(), source: 'live-selector', kind: LIVE_TEXT.kind || 'structured' };
      }
    }
    for (const candidate of splitSelectors(LIVE_TEXT_SELECTOR)) {
      let box = null;
      try {
        box = Array.from(document.querySelectorAll(candidate)).find((el) => !isHiddenElement(el)) || null;
      } catch (_) {
        continue;
      }
      if (!box) continue;
      const text = isValueBacked(box) ? String(box.value || '').trim() : (box.innerText || box.textContent || '').trim();
      if (text) {
        return { text, source: 'live-selector', kind: isValueBacked(box) ? 'input' : 'contenteditable' };
      }
    }
    const text = composerText();
    return { text, source: text ? 'composer' : 'none', kind: 'composer' };
  }

  // Claude keeps the Dictate slot inert while the box has text. `inert` blocks
  // clicks even when the slot is visible, so the attribute that would swallow
  // the click is removed right before an intentional click; presence and
  // visibility are never forced.
  function releaseIdleSlot() {
    try {
      for (const el of document.querySelectorAll(IDLE_SLOT)) {
        el.removeAttribute('inert');
        el.style.pointerEvents = 'auto';
      }
    } catch (_) {}
  }

  function micButtons() {
    const out = [];
    try {
      for (const slot of document.querySelectorAll(IDLE_SLOT)) {
        out.push(...slot.querySelectorAll(MIC_SELECTOR));
      }
      // A redesign moved the Dictate control out of the idle slot; keep the
      // slot-first order (it is the composer's own control) and fall back to
      // the document instead of losing the button.
      if (out.length === 0) {
        out.push(...document.querySelectorAll(MIC_SELECTOR));
      }
    } catch (_) {}
    // Several idle-slot ancestors can match the same button; count it once.
    return Array.from(new Set(out));
  }

  // A control the user cannot see or click is not a control: hidden duplicates
  // of the same label exist in the page (collapsed slots, aria-hidden copies),
  // and clicking one silently does nothing.
  function isClickable(el) {
    try {
      const rect = el.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      const style = getComputedStyle(el);
      if (style.visibility === 'hidden' || style.display === 'none') return false;
      if (Number(style.opacity || 1) === 0) return false;
      // Deliberately NOT filtered on disabled/aria-disabled: the platform
      // briefly disables the commit control while it flushes the capture, and
      // a click in that window is simply retried by stop().
      return true;
    } catch (_) {
      return false;
    }
  }

  function describeControl(el) {
    if (!el) return 'none';
    try {
      const rect = el.getBoundingClientRect();
      return `${el.getAttribute('aria-label') || el.textContent.trim().slice(0, 24)}|${el.tagName.toLowerCase()}|${Math.round(
        rect.width,
      )}x${Math.round(rect.height)}`;
    } catch (_) {
      return 'unknown';
    }
  }

  // Why each stop-selector match was accepted or rejected. Read-only, used by
  // the probe: a hidden/disabled duplicate silently swallowing the commit is
  // invisible otherwise.
  function stopCandidates() {
    const out = [];
    let matches = [];
    try {
      matches = Array.from(document.querySelectorAll(STOP_SELECTOR));
    } catch (_) {
      return 'selector-error';
    }
    for (const el of matches) {
      let why = 'ok';
      try {
        const rect = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        if (rect.width <= 0 || rect.height <= 0) why = 'zero-rect';
        else if (style.visibility === 'hidden') why = 'visibility';
        else if (style.display === 'none') why = 'display';
        else if (Number(style.opacity || 1) === 0) why = 'opacity';
        else if (el.disabled === true) why = 'disabled';
        else if (el.getAttribute('aria-disabled') === 'true') why = 'aria-disabled';
        out.push(
          `${(el.getAttribute('aria-label') || '?').slice(0, 22)}:${Math.round(rect.width)}x${Math.round(
            rect.height,
          )}:op=${style.opacity}:${why}`,
        );
      } catch (e) {
        out.push('error:' + String(e).slice(0, 40));
      }
    }
    return out.join(',') || 'no-match';
  }

  function stopButtons() {
    try {
      const all = Array.from(document.querySelectorAll(STOP_SELECTOR));
      const clickable = all.filter(isClickable);
      // Prefer the platform's live stable control over older label/glyph
      // fallbacks: on a transitional page both can exist, and the legacy
      // "Submit dictation" must not steal the click from the current toggle.
      const rank = (el) => {
        if (el.getAttribute('data-dictation-button') === 'dictating') return 0;
        const label = (el.getAttribute('aria-label') || '').toLowerCase();
        if (label.includes('finish dictation') || label.includes('submit dictation')) return 1;
        return 2;
      };
      return (clickable.length ? clickable : []).sort((a, b) => rank(a) - rank(b));
    } catch (_) {
      return [];
    }
  }

  function cancelButtons() {
    try {
      // Only a control the user can actually click can discard the capture: a
      // hidden duplicate of the same label silently swallows the click.
      return Array.from(document.querySelectorAll(CANCEL_SELECTOR)).filter(isClickable);
    } catch (_) {
      return [];
    }
  }

  function clickElement(el) {
    if (!el) return false;
    try {
      el.scrollIntoView({ block: 'center', inline: 'center' });
    } catch (_) {}
    try {
      el.click();
      return true;
    } catch (_) {
      return false;
    }
  }

  // The platform's own capture signal: the composer placeholder switches to
  // "Listening..." while the mic is open. It corroborates the toggle label and
  // is never the only signal.
  function platformRecording() {
    try {
      for (const el of document.querySelectorAll(COMPOSER)) {
        const attrs = [
          el.getAttribute('data-placeholder'),
          el.getAttribute('aria-placeholder'),
          el.getAttribute('aria-label'),
        ];
        if (attrs.some((value) => value && /listening/i.test(value))) return true;
      }
      return Array.from(document.querySelectorAll('[aria-live]')).some((el) =>
        /listening/i.test(el.textContent || ''),
      );
    } catch (_) {
      return false;
    }
  }

  // Pure decision table for "is the platform still capturing?". A missing or
  // contradictory pair is reported as such and never guessed.
  function classifyRecordingState(listening, stopCount, micCount) {
    if (stopCount > 0) return 'recording';
    if (micCount > 0) return listening ? 'signal_disagreement' : 'auto_stopped';
    return 'signal_disagreement';
  }

  function recordingState() {
    // Either recording control proves capture: the commit button alone is
    // enough, and a redesign that offers only a discard control must still
    // read as "recording" instead of flipping to idle mid-dictation.
    const controls = stopButtons().length + cancelButtons().length;
    return classifyRecordingState(platformRecording(), controls, micButtons().length);
  }

  // Grace period after the platform leaves "recording" before we conclude
  // that no transcript is coming. The old loop had NO empty branch: with an
  // empty composer the stable counter never advanced, so a dictation with no
  // speech burned the entire 15s timeout before saying "Empty transcript".
  const EMPTY_AFTER_STOP_MS = 900;
  // Some page states keep the commit control visible after the platform
  // stopped, so `isDone()` stays false. Bound "no text at all" separately,
  // still far below the configured hard timeout.
  const NO_TEXT_CAP_MS = 3500;

  async function scrapeStable(opts) {
    const pollMs = opts.pollMs || 200;
    const windows = opts.stableWindows || 2;
    const timeoutMs = opts.timeoutMs || 15000;
    const stableMs = opts.stableMs || 800;
    const isDone = opts.isDone || null;
    const started = Date.now();
    const deadline = started + timeoutMs;
    const noTextDeadline = started + NO_TEXT_CAP_MS;
    let last = '';
    let stable = 0;
    let wait = pollMs;
    let doneSince = 0;
    while (Date.now() < deadline) {
      const current = (composerText() || '').trim();
      const done = isDone ? await isDone() : false;
      if (done && !doneSince) doneSince = Date.now();
      if (!done) doneSince = 0;
      if (current && current === last) {
        stable += 1;
        // Two stable reads are enough on their own; `isDone` short-circuits
        // even that once the platform has left the recording state.
        if (stable >= windows) return { text: current, reason: 'stable' };
        if (stable >= 1 && done) return { text: current, reason: 'stopped' };
      } else {
        stable = 0;
        last = current;
        // Text still moving: give it longer next time (up to stableMs).
        wait = Math.min(wait * 2, stableMs);
      }
      // No words were spoken: stop as soon as the platform is done instead
      // of polling an empty composer until the hard timeout.
      if (!current) {
        if (doneSince && Date.now() - doneSince >= EMPTY_AFTER_STOP_MS) {
          return { text: '', reason: 'empty_after_stop' };
        }
        if (Date.now() >= noTextDeadline) {
          return { text: '', reason: 'no_text' };
        }
      }
      await sleep(wait);
    }
    const finalText = (composerText() || '').trim();
    return {
      text: finalText,
      reason: finalText ? 'timeout_with_text' : 'timeout_empty',
    };
  }

  function newChatCandidates() {
    const out = [];
    try {
      for (const el of document.querySelectorAll('a, button, [role="link"], [role="button"]')) {
        const label = (el.getAttribute('aria-label') || el.textContent || '').trim().toLowerCase();
        if (!label) continue;
        if (NEW_CHAT_NAMES.some((name) => label === name || label.startsWith(name))) out.push(el);
      }
    } catch (_) {}
    return out;
  }

  // In-page navigation only: click the platform's own New chat control. A
  // reload or location change would throw away the session this bridge exists
  // to reuse.
  async function newChat() {
    const candidates = newChatCandidates();
    if (!candidates.length) return false;
    if (!clickElement(candidates[0])) return false;
    // The old blind sleep(900) wasted time on a fast page and still raced a
    // slow one. Wait for the composer to actually become clean, bounded so a
    // stuck page cannot hold the start path forever.
    const deadline = Date.now() + 2000;
    while (Date.now() < deadline) {
      if (!composerText()) return true;
      await sleep(60);
    }
    return !composerText();
  }

  async function ensureCleanComposer() {
    if (!composerText()) return true;
    // Clear IN PLACE first: a New chat click navigates, which reloads the
    // platform's view and throws away the state the user is working in.
    const cleared = await clearComposer();
    if (cleared.cleared) return true;
    await newChat();
    if (!composerText()) return true;
    const retry = await clearComposer();
    return retry.cleared;
  }

  async function doStart(opts) {
    if (!SELECTORS_READY) {
      throw new CmdError('selectors-missing', `no live-verified ${PLATFORM} selectors are installed`);
    }
    if (!state.enabled) {
      throw new CmdError('disabled', 'the plugin is switched off in this browser profile');
    }
    const page = pageState();
    if (page === 'signed_out') throw new CmdError('signed-out', 'the tab is signed out');
    if (page === 'challenge') throw new CmdError('challenge', 'the tab is showing a security check');
    // Never record into a dirty box: leftover text would be scraped as if it
    // were dictated, and Claude marks the Dictate slot inert while text is
    // present. ensureCleanComposer() cleans AND verifies.
    if (!(await ensureCleanComposer())) {
      throw new CmdError('composer-dirty', 'the prompt box still has text after New chat');
    }
    releaseIdleSlot();
    // The bridge already waits for a clickable mic, but a page can change
    // between the status read and this click. Wait again here instead of
    // clicking a stale or hidden control (P2).
    const budget = Date.now() + (opts.startTimeoutMs || 5000);
    const maxAttempts = 3;
    const attempts = [];
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      // A second click on a toggle that DID start would stop the dictation.
      // Re-probe the platform signal before every click (C-ASR-4).
      if (recordingState() === 'recording') {
        state.recording = true;
        return { ok: true, already: true, attempts: attempt - 1 };
      }
      let mic = micButtons().filter(isClickable)[0];
      const probeDeadline = Math.min(Date.now() + 600, budget);
      while (!mic && Date.now() < probeDeadline) {
        await sleep(50);
        mic = micButtons().filter(isClickable)[0];
      }
      if (!mic) {
        attempts.push({ attempt, reason: 'control.missing' });
        if (attempt < maxAttempts && Date.now() < budget) continue;
        releaseIdleSlot();
        throw new CmdError('page-not-ready', 'the dictation control is not ready');
      }
      const before = describeControl(mic);
      clickElement(mic);
      const verifyUntil = Math.min(Date.now() + 350, budget);
      let started = false;
      while (Date.now() < verifyUntil) {
        if (recordingState() === 'recording') {
          started = true;
          break;
        }
        await sleep(50);
      }
      attempts.push({ attempt, control: before, started });
      if (started) {
        state.recording = true;
        return { ok: true, attempts };
      }
      if (attempt < maxAttempts && Date.now() < budget) {
        // Give the page a moment to hydrate before the next verified click.
        await sleep(120);
      }
    }
    releaseIdleSlot();
    const remaining = micButtons().length;
    throw new CmdError(
      remaining === 0 ? 'no-recording-indicator' : 'platform-not-recording',
      `the control never changed to Stop after ${attempts.length} verified attempts`,
      { attempts },
    );
  }

  // Two start commands in a row must not double-click: the first click owns
  // the transition and the second waits for the same result.
  async function start(opts) {
    if (state.recording) return { ok: true, already: true };
    if (state.starting) return state.starting;
    state.starting = doStart(opts).finally(() => {
      state.starting = null;
    });
    return state.starting;
  }

  async function stop(opts) {
    let platform = 'not_recording';
    let autoStopped = false;
    if (state.recording) {
      platform = recordingState();
      autoStopped = platform === 'auto_stopped';
    }
    const t0 = Date.now();
    releaseIdleSlot();
    // COMMIT, never discard: "Finish dictation" is what turns the captured
    // audio into text in the composer. An absent control means the platform
    // already stopped on its own, so scraping is the correct next step.
    let stopControl = stopButtons();
    let control = 'none';
    if (stopControl.length) {
      control = describeControl(stopControl[0]);
      clickElement(stopControl[0]);
      // The commit control can be transiently disabled while the platform
      // flushes the capture; a click that lands in that window does nothing.
      // Retry against the SAME control until the page leaves recording.
      for (let attempt = 0; attempt < 6; attempt += 1) {
        await sleep(400);
        if (recordingState() !== 'recording') break;
        stopControl = stopButtons();
        if (!stopControl.length) break;
        clickElement(stopControl[0]);
      }
    }
    const tClicked = Date.now();
    state.recording = false;
    let text = '';
    let reason = 'unknown';
    try {
      const scraped = await scrapeStable({
        pollMs: opts.pollMs,
        stableMs: opts.stableMs,
        stableWindows: opts.stableWindows,
        timeoutMs: opts.timeoutMs,
        isDone: async () => recordingState() !== 'recording',
      });
      text = scraped.text;
      reason = scraped.reason;
    } catch (_) {
      reason = 'error';
    }
    const tScraped = Date.now();
    // `platform` is the state at the STOP REQUEST (it drove this cycle);
    // `state_after` is what the page reports after the commit attempt, so a
    // stopped platform no longer logs a misleading "state=recording".
    return {
      text,
      reason,
      platform: PLATFORM,
      state: platform,
      state_after: recordingState(),
      auto_stopped: autoStopped,
      committed: stopControl.length > 0,
      control,
      click_ms: tClicked - t0,
      scrape_ms: tScraped - tClicked,
    };
  }

  async function cancel() {
    state.recording = false;
    releaseIdleSlot();
    // DISCARD: the sibling control that throws the capture away. Clicking the
    // COMMIT control instead would transcribe an aborted recording, so a
    // platform that HAS a discard control is never stopped through it
    // (C-ASR-4). A platform with NO discard control (Gemini exposes only the
    // Dictate/Stop toggle) stops through that toggle and the text it commits
    // is cleared afterwards.
    const discard = cancelButtons();
    let control = 'none';
    let via = 'none';
    if (discard.length) {
      control = describeControl(discard[0]);
      via = 'discard';
      clickElement(discard[0]);
      await sleep(1200);
    } else if (!CANCEL_SELECTOR) {
      const stopControl = stopButtons();
      if (stopControl.length) {
        control = describeControl(stopControl[0]);
        via = 'stop-fallback';
        clickElement(stopControl[0]);
        await sleep(1200);
      }
    } else {
      // The platform HAS a discard control but it is not clickable now.
      // Report that instead of committing a dictation the user threw away.
      via = 'discard-unavailable';
    }
    // Discard the text the platform already committed, IN PLACE: a New chat
    // click navigates and reloads the view (owner report 2026-11-20).
    const cleared = await clearComposer();
    if (!cleared.cleared) await newChat();
    return { ok: true, control, via, cleared: cleared.cleared };
  }

  // Clear the prompt box in place after a delivered transcript. The text has
  // already been pasted into the user's app, so leaving it in the composer only
  // invites an accidental send -- but a New chat click would RELOAD the view and
  // throw away the page state the user is working in (owner report 2026-11-20),
  // so in-place clearing is the primary path and New chat is only a fallback.
  //
  // Ordering matters: `execCommand` only works when the tab owns OS focus, and
  // the normal case is the OPPOSITE (the user is typing in another app while the
  // dictation window sits in the background), where it silently does nothing.
  // The DOM strategies after it work unfocused, so they carry the background
  // case and the editing commands keep the focused case cheap.
  const CLEAR_STRATEGIES = [
    ['selection-delete', (box) => runSelectionDelete(box)],
    ['select-all-delete', (box) => runSelectAllDelete(box)],
    ['insert-text-empty', (box) => runInsertTextEmpty(box)],
    ['dom-paragraph', (box) => runDomParagraphReset(box)],
    ['dom-empty', (box) => runDomEmpty(box)],
  ];

  // A textarea keeps its text in `.value`. Emptying the DOM text leaves the
  // value intact, so the value itself has to be cleared -- and the framework
  // has to be told, or it restores the old text on its next render.
  function runValueEmpty(box) {
    setNativeValue(box, '');
    notifyInput(box);
  }

  // React (and other frameworks) install their own `value` setter on the
  // element INSTANCE and compare against it; assigning through the PROTOTYPE
  // setter is what makes the framework see the change instead of treating it
  // as a no-op.
  function setNativeValue(box, value) {
    try {
      const proto = Object.getPrototypeOf(box);
      const desc = proto && Object.getOwnPropertyDescriptor(proto, 'value');
      if (desc && typeof desc.set === 'function') {
        desc.set.call(box, value);
        return;
      }
    } catch (_) {}
    try {
      box.value = value;
    } catch (_) {}
  }

  function runSelectionDelete(box) {
    box.focus();
    selectBoxContents(box);
    document.execCommand('delete', false);
  }

  function runSelectAllDelete(box) {
    box.focus();
    document.execCommand('selectAll', false);
    document.execCommand('delete', false);
  }

  function runInsertTextEmpty(box) {
    box.focus();
    document.execCommand('selectAll', false);
    document.execCommand('insertText', false, '');
  }

  function runDomParagraphReset(box) {
    // Framework editors (Quill backs Gemini's rich-textarea) rebuild their model
    // from a mutation they own, so an empty paragraph plus the input event is
    // the shape they accept.
    box.innerHTML = '<p><br></p>';
    notifyInput(box);
  }

  function runDomEmpty(box) {
    box.textContent = '';
    notifyInput(box);
  }

  function notifyInput(box) {
    const EventCtor = typeof InputEvent === 'function' ? InputEvent : Event;
    box.dispatchEvent(new EventCtor('beforeinput', { bubbles: true, inputType: 'deleteContentBackward' }));
    box.dispatchEvent(new EventCtor('input', { bubbles: true, inputType: 'deleteContentBackward' }));
    box.dispatchEvent(new Event('change', { bubbles: true }));
  }

  async function clearComposer() {
    const box = composerBox();
    if (!box) return { cleared: false, reason: 'no-composer' };
    if (!composerText()) return { cleared: true, reason: 'already-empty' };
    // A value-backed composer is emptied FIRST: the editing commands and the
    // DOM-text strategies cannot touch a textarea's `.value`, so they would
    // burn the whole list and report the box as still dirty.
    const strategies = isValueBacked(box)
      ? [['value-empty', (b) => runValueEmpty(b)], ...CLEAR_STRATEGIES]
      : CLEAR_STRATEGIES;
    const steps = [];
    for (const [name, run] of strategies) {
      try {
        run(box);
      } catch (err) {
        steps.push(`${name}:${String(err).slice(0, 40)}`);
        continue;
      }
      await sleep(120);
      if (!composerText().length) return { cleared: true, reason: name, steps };
      steps.push(name);
    }
    return { cleared: false, reason: 'still-dirty', steps };
  }

  function selectBoxContents(box) {
    const selection = window.getSelection();
    if (!selection) return false;
    const range = document.createRange();
    range.selectNodeContents(box);
    selection.removeAllRanges();
    selection.addRange(range);
    return true;
  }

  async function clean() {
    // In-place first (no navigation), New chat only when the box resists.
    const inPlace = await clearComposer();
    if (inPlace.cleared) return { cleaned: true, via: 'clear' };
    const clicked = await newChat();
    if (!clicked) return { cleaned: !composerText(), via: 'new-chat' };
    const deadline = Date.now() + 3000;
    while (Date.now() < deadline) {
      if (!composerText()) return { cleaned: true, via: 'new-chat' };
      await sleep(100);
    }
    return { cleaned: false, via: 'new-chat' };
  }

  function status() {
    const page = pageState();
    return {
      url: location.href,
      platform: PLATFORM,
      page,
      recording: page === 'ok' && recordingState() === 'recording',
      has_text: composerText().length > 0,
      // A transport connection is not a ready page: the dictation control
      // only exists after document_idle + React hydration. The bridge gates
      // /start on these two facts (P2).
      micCount: micButtons().filter(isClickable).length,
      selectorsReady: SELECTORS_READY,
      // Truthful readiness facts for the single-call state model. The page
      // gate itself still uses micCount + selectorsReady only (P2).
      signed_in: page === 'signed_out' ? 'no' : 'unknown',
      control_disabled: /:(?:aria-)?disabled/.test(String(stopCandidates())) ? 1 : 0,
      // The mic can be in the DOM before the app attaches handlers. A gate
      // that only counts buttons can click a dead element (Item 1).
      document_ready: document.readyState === 'complete',
      control_signature: (() => {
        const live = micButtons().filter(isClickable)[0];
        if (!live) return '';
        const r = live.getBoundingClientRect();
        const label = live.getAttribute('aria-label') || live.getAttribute('data-testid') || '';
        return `${label}|${Math.round(r.x)}|${Math.round(r.y)}|${Math.round(r.width)}|${Math.round(r.height)}`;
      })(),
    };
  }

  function redact(value) {
    return String(value)
      .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '<account-email>')
      .replace(/account:[^"<]*/gi, 'account: <account-name>');
  }

  function composerDump() {
    const box = composerBox();
    if (!box) return 'NO-COMPOSER';
    try {
      // Walk up to the composer form so the trailing slots (Send / Dictate)
      // are included, then strip volatile tokens but keep the structure.
      let host = box;
      for (let i = 0; i < 4 && host.parentElement; i += 1) host = host.parentElement;
      const scrub = (el) => {
        for (const attr of [...el.attributes]) {
          const keep = attr.name === 'data-cds-part' || attr.name === 'data-placeholder';
          if (!keep && /^(data-.*|aria-describedby|id|jslog|jsname)$/.test(attr.name)) {
            el.removeAttribute(attr.name);
          }
        }
        for (const child of el.children) scrub(child);
      };
      const clone = host.cloneNode(true);
      scrub(clone);
      return redact(clone.outerHTML).slice(0, 64 * 1024);
    } catch (_) {
      return 'NO-COMPOSER';
    }
  }

  // Read-only page facts for selector work: what the live page actually
  // exposes (labels/testids/dialogs) when a control cannot be matched.
  function pageFacts() {
    const facts = { title: '', url: location.href, auth: [], dialogs: [], buttons: [] };
    try {
      facts.title = document.title || '';
    } catch (_) {}
    try {
      facts.auth = Array.from(document.querySelectorAll('a, button'))
        .map((el) => (el.textContent || el.getAttribute('aria-label') || '').trim())
        .filter((text) => /^(log in|sign up|sign in)$/i.test(text))
        .slice(0, 6);
    } catch (_) {}
    try {
      facts.dialogs = Array.from(document.querySelectorAll('[role="dialog"], dialog'))
        .filter((el) => !isHiddenElement(el))
        .map((el) => (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 160))
        .slice(0, 4);
    } catch (_) {}
    try {
      facts.buttons = Array.from(document.querySelectorAll('button, [role="button"]'))
        .map((el) => ({
          label: (el.getAttribute('aria-label') || '').slice(0, 60),
          testid: el.getAttribute('data-testid') || '',
          text: (el.textContent || '').trim().slice(0, 40),
          hidden: isHiddenElement(el),
        }))
        .filter((button) => button.label || button.testid || button.text)
        .slice(0, 60);
    } catch (_) {}
    return facts;
  }

  async function probe() {
    const checks = [];
    const add = (name, ok, detail) => checks.push({ name, ok: !!ok, detail: detail || '' });
    const page = pageState();
    add('page', page === 'ok', page);
    add('enabled', state.enabled, state.enabled ? 'on' : 'off (popup switch)');
    let idleCount = 0;
    try {
      idleCount = document.querySelectorAll(IDLE_SLOT).length;
    } catch (_) {}
    add('idleSlot', idleCount > 0, `count=${idleCount}`);
    add('composer', !!composerBox(), composerBox() ? 'found' : 'missing');
    // Read-only: probe must not mutate the page (no slot release, no styles).
    const micCount = micButtons().length;
    add('micSelector', micCount > 0, `count=${micCount}`);
    const stopCount = stopButtons().length;
    const cancelCount = cancelButtons().length;
    add('stopSelector', stopCount === 0, `expected 0 while idle, found ${stopCount}`);
    add('cancelSelector', cancelCount === 0, `expected 0 while idle, found ${cancelCount}`);
    add('stopCandidates', true, stopCandidates());
    const newChatCount = newChatCandidates().length;
    add('newChatNames', newChatCount > 0, `count=${newChatCount}`);
    const facts = pageFacts();
    try {
      facts.micPermission = (await navigator.permissions.query({ name: 'microphone' })).state;
    } catch (_) {
      facts.micPermission = 'unknown';
    }
    add('micPermission', facts.micPermission !== 'denied', facts.micPermission);
    return { checks, dump: composerDump(), facts };
  }

  async function run(msg) {
    if (msg.opts && msg.opts.platform && msg.opts.platform !== PLATFORM) {
      throw new CmdError('wrong-platform', `this tab is ${PLATFORM}, not ${msg.opts.platform}`);
    }
    switch (msg.cmd) {
      case 'status':
        return status();
      case 'start':
        return start(msg.opts || {});
      case 'stop':
        return stop(msg.opts || {});
      case 'cancel':
        return cancel();
      case 'clean':
        return clean();
      case 'clear':
        return clearComposer();
      case 'probe':
        return probe();
      case 'draft-snapshot':
        return draftSnapshot();
      case 'diagnostics-draft-set':
      case 'diagnostics-draft-read': {
        // Dev-only diagnostics (CFG.diagnostics) — never shipped in a frozen
        // build. The text is cleared by the caller after the measurement.
        if (!CFG.diagnostics) throw new CmdError('diagnostics-disabled', 'diagnostics are disabled');
        if (msg.cmd === 'diagnostics-draft-read') return { text: composerText() };
        const box = composerBox();
        if (!box) throw new CmdError('composer-missing', 'no composer on this page');
        await clearComposer();
        box.focus();
        try {
          document.execCommand('insertText', false, String((msg.opts && msg.opts.text) || ''));
        } catch (_) {}
        return { text: composerText() };
      }
      default:
        throw new CmdError('bridge-error', `unknown command ${msg.cmd}`);
    }
  }

  function reply(port, id, ok, result, kind, error, details) {
    const payload = ok
      ? { id, ok: true, result }
      : {
          id,
          ok: false,
          kind: kind || 'bridge-error',
          error: String(error || 'command failed').slice(0, 200),
          details,
        };
    try {
      port.postMessage(payload);
    } catch (_) {}
  }

  chrome.runtime.onConnect.addListener((port) => {
    if (port.name !== 'stt-bridge') return;
    port.onMessage.addListener((msg) => {
      if (!msg || !msg.id) return;
      run(msg)
        .then((result) => reply(port, msg.id, true, result))
        .catch((err) =>
          reply(
            port, msg.id, false, null, (err && err.kind) || 'bridge-error',
            (err && err.message) || err, (err && err.details) || undefined,
          ),
        );
    });
  });
})();
