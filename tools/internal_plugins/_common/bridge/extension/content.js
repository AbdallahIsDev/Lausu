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
      : '';
  // Unknown host: a clean no-op. Never inject a selector set by guessing.
  if (!PLATFORM) return;
  const SEL = (CFG.platforms && CFG.platforms[PLATFORM]) || {};
  const IDLE_SLOT = SEL.idleSlot || '';
  const COMPOSER = SEL.composer || '';
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
    constructor(kind, message) {
      super(message);
      this.kind = kind;
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

  function pageState() {
    if (isSignedOutUrl(location.href)) return 'signed_out';
    if (isChallenge()) return 'challenge';
    return 'ok';
  }

  function composerBox() {
    try {
      return document.querySelector(COMPOSER);
    } catch (_) {
      return null;
    }
  }

  function composerText() {
    const box = composerBox();
    if (!box) return '';
    try {
      const rich = box.querySelector('p');
      if (rich && rich.innerText.trim()) return rich.innerText.trim();
      const text = (box.innerText || box.textContent || '').trim();
      const placeholder =
        box.getAttribute('data-placeholder') || box.getAttribute('aria-placeholder') || '';
      if (placeholder && text === placeholder.trim()) return '';
      return text;
    } catch (_) {
      return '';
    }
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
    return out;
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
      // Prefer the explicit commit label when several controls match.
      const rank = (el) => {
        const label = (el.getAttribute('aria-label') || '').toLowerCase();
        return label.includes('finish dictation') ? 0 : 1;
      };
      return (clickable.length ? clickable : []).sort((a, b) => rank(a) - rank(b));
    } catch (_) {
      return [];
    }
  }

  function cancelButtons() {
    try {
      return Array.from(document.querySelectorAll(CANCEL_SELECTOR));
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
    const mic = micButtons();
    if (!mic.length) throw new CmdError('mic-missing', 'the Dictate control was not found');
    clickElement(mic[0]);
    const budget = Date.now() + (opts.startTimeoutMs || 5000);
    let started = false;
    while (Date.now() < budget) {
      if (recordingState() === 'recording') {
        started = true;
        break;
      }
      await sleep(100);
    }
    if (!started) {
      // Name which signal never arrived: a missing control means the click
      // never registered, a still-idle toggle means the page is not capturing.
      releaseIdleSlot();
      const remaining = micButtons().length;
      throw remaining === 0
        ? new CmdError('no-recording-indicator', 'the Dictate control vanished after the click')
        : new CmdError('platform-not-recording', 'the control never changed to Stop');
    }
    state.recording = true;
    return { ok: true };
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
    // DISCARD: the sibling control that throws the capture away. Falling back
    // to the commit control would transcribe an aborted recording.
    const discard = cancelButtons();
    if (discard.length) {
      clickElement(discard[0]);
      await sleep(1200);
    } else {
      const stopControl = stopButtons();
      if (stopControl.length) {
        clickElement(stopControl[0]);
        await sleep(1200);
      }
    }
    // Discard the text the platform already committed, IN PLACE: a New chat
    // click navigates and reloads the view (owner report 2026-11-20).
    const cleared = await clearComposer();
    if (!cleared.cleared) await newChat();
    return { ok: true };
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
    const steps = [];
    for (const [name, run] of CLEAR_STRATEGIES) {
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

  function probe() {
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
    return { checks, dump: composerDump() };
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
      default:
        throw new CmdError('bridge-error', `unknown command ${msg.cmd}`);
    }
  }

  function reply(port, id, ok, result, kind, error) {
    const payload = ok
      ? { id, ok: true, result }
      : {
          id,
          ok: false,
          kind: kind || 'bridge-error',
          error: String(error || 'command failed').slice(0, 200),
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
          reply(port, msg.id, false, null, (err && err.kind) || 'bridge-error', (err && err.message) || err),
        );
    });
  });
})();
