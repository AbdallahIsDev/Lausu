'use strict';

// A platform without a discard control (Gemini: the Dictate button only
// relabels to "Stop dictation") must still dictate. Requiring a cancel
// selector made `start` answer `selectors-missing` forever, which is how the
// Google plugin became unusable after the shared-bridge refactor. Cancel is
// optional; a REAL discard control is still preferred whenever one exists.

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const CONTENT = path.resolve(__dirname, '..', 'extension', 'content.js');
const SOURCE = fs.readFileSync(CONTENT, 'utf8');

const GEMINI_SELECTORS = {
  idleSlot: 'div[data-node-type="speech_dictation_mic_button"]',
  composer: 'div[role="textbox"][contenteditable="true"]',
  micSelector: 'button[aria-label^="Dictate"]',
  stopSelector: 'button[aria-label^="Stop dictation"]',
  cancelSelector: '',
  newChatNames: ['New chat'],
};

function harness({ selectors = GEMINI_SELECTORS } = {}) {
  const replies = [];
  let micClicks = 0;
  const button = {
    tagName: 'BUTTON',
    getAttribute: (name) => (name === 'aria-label' ? 'Dictate' : ''),
    textContent: '',
    scrollIntoView() {},
    click() {
      micClicks += 1;
    },
    removeAttribute() {},
    style: {},
    getBoundingClientRect: () => ({ width: 28, height: 28 }),
    querySelectorAll: () => [],
  };
  const idleSlot = {
    removeAttribute() {},
    style: {},
    querySelectorAll: () => [button],
  };
  const composer = {
    querySelector: () => ({ innerText: '' }),
    innerText: '',
    textContent: '',
    getAttribute: () => '',
  };
  const document = {
    title: 'Google Gemini',
    querySelector: (sel) => (sel.includes('contenteditable') ? composer : null),
    querySelectorAll: (sel) => {
      if (sel.includes('speech_dictation_mic_button')) return [idleSlot];
      if (sel.includes('Dictate')) return [button];
      return [];
    },
  };
  let connectListener = null;
  const chrome = {
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
  const sandbox = {
    self: { ANTHROPIC_STT_CONFIG: { platforms: { gemini: selectors } } },
    location: { host: 'gemini.google.com', href: 'https://gemini.google.com/app' },
    chrome,
    document,
    getComputedStyle: () => ({ visibility: 'visible', display: 'block', opacity: '1' }),
    setTimeout,
    clearTimeout,
    Date,
    Promise,
    console,
  };
  vm.runInNewContext(SOURCE, sandbox);
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
  return {
    start: (opts) =>
      new Promise((resolve, reject) => {
        onMessage({ cmd: 'start', id: 7, opts });
        const deadline = Date.now() + 4000;
        const tick = () => {
          const found = replies.find((r) => r.id === 7);
          if (found) return resolve(found);
          if (Date.now() > deadline) return reject(new Error('no reply'));
          setTimeout(tick, 5);
        };
        tick();
      }),
    micClicks: () => micClicks,
  };
}

const FAST = { pollMs: 20, stableMs: 20, stableWindows: 2, timeoutMs: 300, startTimeoutMs: 300 };

test('start without a discard control is not rejected as selectors-missing', async () => {
  const h = harness();
  const reply = await h.start(FAST);
  assert.notEqual(reply.kind, 'selectors-missing', JSON.stringify(reply));
  // The platform's own control was clicked, so the flow ran past the gate.
  assert.equal(h.micClicks(), 1, JSON.stringify(reply));
});

test('a platform WITH a discard control still reports selectors-missing when the composer is absent', async () => {
  const h = harness({
    selectors: { ...GEMINI_SELECTORS, composer: '', cancelSelector: 'button[aria-label^="Cancel"]' },
  });
  const reply = await h.start(FAST);
  assert.equal(reply.kind, 'selectors-missing', JSON.stringify(reply));
});
