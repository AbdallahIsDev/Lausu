'use strict';

// ChatGPT's dictation row has THREE distinct controls: the mic that STARTS the
// capture, "Submit dictation" (a checkmark) that COMMITS the transcript, and
// "Stop dictation" that DISCARDS it. Sharing one selector between the commit
// and the discard is exactly the bug C-ASR-4 pins: stopping through the
// discard control throws the whole dictation away.
//
// These tests drive the REAL content script against a REAL DOM (jsdom), so
// the shipped selector strings are exercised by a real CSS engine instead of
// a hand-written matcher, and the transcript is read out of a value-backed
// composer the way ChatGPT's textarea layout stores it.

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const BRIDGE = path.resolve(__dirname, '..');
const CONTENT = path.join(BRIDGE, 'extension', 'content.js');
const SOURCE = fs.readFileSync(CONTENT, 'utf8');
const SELECTORS = JSON.parse(
  fs.readFileSync(path.join(BRIDGE, 'selectors', 'chatgpt.json'), 'utf8'),
);

// jsdom ships with the renderer's dev dependencies. The bridge suite has no
// package manager of its own, so the copy is resolved from the renderer and
// the suite skips (loudly) when it is not installed.
function loadJsdom() {
  const candidates = [
    'jsdom',
    path.resolve(__dirname, '../../../../..', 'voice_typer/client/node_modules/jsdom'),
  ];
  for (const candidate of candidates) {
    try {
      return require(candidate);
    } catch (_) {}
  }
  return null;
}

const jsdom = loadJsdom();
const domTest = jsdom ? test : test.skip;
if (!jsdom) {
  console.warn(
    '[chatgpt] jsdom is not installed: the DOM-level ChatGPT cases are SKIPPED ' +
      '(install voice_typer/client dependencies to run them)',
  );
}

const MIC_PATH = 'M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z';
const CHECK_PATH = 'M20 6L9 17l-5-5';

// The composer form ChatGPT renders today: a value-backed textarea inside the
// composer form, with the trailing actions (Dictate / Send) in a fieldset.
function composerForm({ body, textarea = true }) {
  const editor = textarea
    ? '<textarea id="prompt-textarea" name="prompt" data-testid="prompt-textarea" ' +
      'placeholder="Message ChatGPT"></textarea>'
    : '<div id="prompt-textarea" data-testid="prompt-textarea" contenteditable="true" ' +
      'role="textbox" class="ProseMirror"></div>';
  return (
    '<form data-chatgpt-composer="true">' +
    '<div class="composer-parent">' +
    '<div id="composer-input-container">' +
    editor +
    '</div>' +
    '<fieldset>' +
    body +
    '</fieldset>' +
    '</div>' +
    '</form>'
  );
}

const IDLE_BODY =
  '<button type="button" data-testid="composer-dictate" aria-label="Dictate button" class="composer-btn">' +
  `<svg viewBox="0 0 24 24"><path d="${MIC_PATH}"></path></svg>` +
  '</button>' +
  '<button type="button" data-testid="send-button" aria-label="Send message">Send</button>';

const RECORDING_BODY =
  '<button type="button" data-testid="stop-recording" aria-label="Stop dictation">Stop</button>' +
  '<button type="button" data-testid="submit-dictation" aria-label="Submit dictation">' +
  `<svg viewBox="0 0 24 24"><path d="${CHECK_PATH}"></path></svg>` +
  '</button>';

// The same row with the accessible labels removed: only the glyphs are left,
// which is the case the SVG fallbacks exist for.
const GLYPH_ONLY_BODY =
  '<button type="button" data-testid="composer-dictate">' +
  `<svg viewBox="0 0 24 24"><path d="${MIC_PATH}"></path></svg>` +
  '</button>' +
  '<button type="button" data-testid="submit-dictation">' +
  `<svg viewBox="0 0 24 24"><path d="${CHECK_PATH}"></path></svg>` +
  '</button>';

function pageHtml({ body = IDLE_BODY, textarea = true } = {}) {
  return (
    '<!doctype html><html><body>' +
    '<a href="/" aria-label="New chat">New chat</a>' +
    composerForm({ body, textarea }) +
    '</body></html>'
  );
}

const FAST = { pollMs: 20, stableMs: 20, stableWindows: 2, timeoutMs: 1500, startTimeoutMs: 1500 };

// Build a live page: a jsdom window with a stubbed layout (jsdom has no
// layout, so every element would measure 0x0 and look hidden), a fake
// `chrome` API and the REAL content script running inside the window.
function createPage({ body = IDLE_BODY, textarea = true, transcript = 'hello world' } = {}) {
  const dom = new jsdom.JSDOM(pageHtml({ body, textarea }), {
    url: 'https://chatgpt.com/',
    runScripts: 'outside-only',
  });
  const { window } = dom;
  window.Element.prototype.getBoundingClientRect = function getBoundingClientRect() {
    return { width: 24, height: 24, top: 0, left: 0, right: 24, bottom: 24, x: 0, y: 0 };
  };

  const doc = window.document;
  const clicks = [];
  let state = 'idle';
  const setState = (next) => {
    state = next;
    const fieldset = doc.querySelector('fieldset');
    if (!fieldset) return;
    fieldset.innerHTML = next === 'recording' ? RECORDING_BODY : IDLE_BODY;
  };

  doc.addEventListener('click', (event) => {
    const button = event.target && event.target.closest ? event.target.closest('button') : null;
    if (!button) return;
    const label =
      button.getAttribute('aria-label') || button.getAttribute('data-testid') || 'unknown';
    clicks.push(label);
    if (label === 'Dictate button' || label === 'composer-dictate') {
      // The platform swaps the mic for the recording row.
      setState('recording');
      return;
    }
    if (label === 'Submit dictation' || label === 'submit-dictation') {
      // The platform commits the transcript into the composer.
      const box = doc.querySelector('#prompt-textarea');
      if (box) box.value = transcript;
    }
    // Either control ends the capture and the row goes back to idle.
    setState('idle');
  });

  const replies = [];
  let connectListener = null;
  window.chrome = {
    storage: {
      local: { get: (_key, cb) => cb({ enabled: true }) },
      onChanged: { addListener() {} },
    },
    runtime: {
      onMessage: { addListener() {} },
      onConnect: {
        addListener(fn) {
          connectListener = fn;
        },
      },
    },
  };
  window.ANTHROPIC_STT_CONFIG = { platforms: { chatgpt: SELECTORS } };
  window.eval(SOURCE);

  let onMessage = null;
  connectListener({
    name: 'stt-bridge',
    onMessage: {
      addListener(fn) {
        onMessage = fn;
      },
    },
    postMessage(payload) {
      replies.push(payload);
    },
  });

  const send = (cmd, opts = {}) =>
    new Promise((resolve, reject) => {
      const id = replies.length + 1;
      onMessage({ cmd, id, opts });
      const deadline = Date.now() + 8000;
      const tick = () => {
        const found = replies.find((r) => r.id === id);
        if (found) return resolve(found);
        if (Date.now() > deadline) return reject(new Error(`no reply for ${cmd}`));
        setTimeout(tick, 5);
      };
      tick();
    });

  return {
    send,
    clicks,
    document: doc,
    window,
    setState,
    state: () => state,
    composer: () => doc.querySelector('#prompt-textarea'),
  };
}

domTest('the mic selector never matches the commit or the discard control', () => {
  const dom = new jsdom.JSDOM(pageHtml({ body: RECORDING_BODY }), { url: 'https://chatgpt.com/' });
  const doc = dom.window.document;
  assert.equal(doc.querySelectorAll(SELECTORS.micSelector).length, 0);
  const commit = doc.querySelectorAll(SELECTORS.stopSelector);
  assert.equal(commit.length, 1);
  assert.match(commit[0].getAttribute('aria-label'), /submit dictation/i);
  const discard = doc.querySelectorAll(SELECTORS.cancelSelector);
  assert.equal(discard.length, 1);
  assert.match(discard[0].getAttribute('aria-label'), /stop dictation/i);
});

domTest('the commit and the discard selectors never overlap', () => {
  const dom = new jsdom.JSDOM(pageHtml({ body: RECORDING_BODY }), { url: 'https://chatgpt.com/' });
  const doc = dom.window.document;
  for (const el of doc.querySelectorAll(SELECTORS.stopSelector)) {
    assert.doesNotMatch(
      el.getAttribute('aria-label') || '',
      /stop dictation/i,
      'the commit control must not be the discard control',
    );
  }
  for (const el of doc.querySelectorAll(SELECTORS.cancelSelector)) {
    assert.doesNotMatch(
      el.getAttribute('aria-label') || '',
      /submit dictation/i,
      'the discard control must not be the commit control',
    );
  }
});

domTest('the glyph fallbacks find the mic and the commit control when the labels are gone', () => {
  const dom = new jsdom.JSDOM(pageHtml({ body: GLYPH_ONLY_BODY }), { url: 'https://chatgpt.com/' });
  const doc = dom.window.document;
  const mic = doc.querySelectorAll(SELECTORS.micSelector);
  assert.equal(mic.length, 1, 'the microphone glyph must still be found');
  assert.equal(mic[0].getAttribute('data-testid'), 'composer-dictate');
  const commit = doc.querySelectorAll(SELECTORS.stopSelector);
  assert.equal(commit.length, 1, 'the checkmark glyph must still be found');
  assert.equal(commit[0].getAttribute('data-testid'), 'submit-dictation');
});

domTest('the composer is anchored to the composer form, never to a page-wide editable', () => {
  const dom = new jsdom.JSDOM(
    pageHtml({ body: IDLE_BODY }) +
      '<div contenteditable="true" role="textbox" id="sidebar-note">a note field</div>',
    { url: 'https://chatgpt.com/' },
  );
  const doc = dom.window.document;
  const matches = doc.querySelectorAll(SELECTORS.composer);
  assert.equal(matches.length, 1);
  assert.equal(matches[0].id, 'prompt-textarea');
  // The stray editable outside the composer form must not be picked up.
  assert.notEqual(doc.querySelector(SELECTORS.composer).id, 'sidebar-note');
});

domTest('start clicks the microphone and reports that the platform is recording', async () => {
  const page = createPage();
  const reply = await page.send('start', FAST);
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.ok(page.clicks.includes('Dictate button'), JSON.stringify(page.clicks));
  assert.equal(page.state(), 'recording');
});

domTest('stop commits through "Submit dictation" and never through "Stop dictation"', async () => {
  const page = createPage();
  await page.send('start', FAST);
  const reply = await page.send('stop', FAST);
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.ok(page.clicks.includes('Submit dictation'), JSON.stringify(page.clicks));
  assert.ok(
    !page.clicks.includes('Stop dictation'),
    `the discard control must never be used to finish a dictation: ${JSON.stringify(page.clicks)}`,
  );
  // C-ASR-4: stop() reports WHICH control it clicked.
  assert.match(reply.result.control, /submit dictation/i);
  assert.equal(reply.result.committed, true);
  // The transcript is read out of the value-backed composer.
  assert.equal(reply.result.text, 'hello world');
});

domTest('cancel discards through "Stop dictation" and never commits', async () => {
  const page = createPage();
  await page.send('start', FAST);
  const reply = await page.send('cancel', {});
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.ok(page.clicks.includes('Stop dictation'), JSON.stringify(page.clicks));
  assert.ok(
    !page.clicks.includes('Submit dictation'),
    `a discarded dictation must not be committed: ${JSON.stringify(page.clicks)}`,
  );
  assert.equal(reply.result.via, 'discard');
  assert.match(reply.result.control, /stop dictation/i);
});

domTest('a delivered transcript is cleared out of the textarea value in place', async () => {
  const page = createPage();
  await page.send('start', FAST);
  await page.send('stop', FAST);
  const box = page.composer();
  assert.equal(box.value, 'hello world');
  const reply = await page.send('clean', {});
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.equal(reply.result.cleaned, true, JSON.stringify(reply));
  assert.equal(reply.result.via, 'clear', JSON.stringify(reply));
  assert.equal(page.composer().value, '', 'the textarea value must be emptied');
});

domTest('an empty composer is never scraped as a transcript', async () => {
  const page = createPage({ transcript: '' });
  await page.send('start', FAST);
  const reply = await page.send('stop', FAST);
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.equal(reply.result.text, '');
  assert.ok(reply.result.reason !== 'timeout_with_text', reply.result.reason);
});
