'use strict';

// Clearing the prompt box after delivery must happen IN PLACE. Clicking the
// platform's "New chat" control navigates, which reloads the whole view and
// discards the page state the user is working in (owner report 2026-11-20).
// New chat stays as the fallback for a composer that resists in-place
// clearing, so a stuck editor can never block the next dictation.

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const CONTENT = path.resolve(__dirname, '..', 'extension', 'content.js');
const SOURCE = fs.readFileSync(CONTENT, 'utf8');

const SELECTORS = {
  idleSlot: 'div[data-node-type="speech_dictation_mic_button"]',
  composer: 'div[role="textbox"][contenteditable="true"]',
  micSelector: 'button[aria-label^="Dictate"]',
  stopSelector: 'button[aria-label^="Stop dictation"]',
  cancelSelector: '',
  newChatNames: ['New chat'],
};

// `honoursDelete` decides whether the fake editor reacts to execCommand (a
// cooperative editor) or ignores it (a framework editor that needs the input
// event / New chat fallback).
function harness({ text = 'already typed', honoursDelete = true, nodeEmptyWorks = true, newChatWorks = true } = {}) {
  const replies = [];
  const clicks = { mic: 0, newChat: 0, stop: 0 };
  let composerState = text;

  const box = {
    tagName: 'DIV',
    focus() {},
    get textContent() {
      return composerState;
    },
    set textContent(value) {
      // A framework editor that re-renders from its own model ignores direct
      // node writes; only New chat resets that model.
      if (nodeEmptyWorks || value === '') {
        if (nodeEmptyWorks) composerState = value;
      }
    },
    get innerText() {
      return composerState;
    },
    getAttribute: () => '',
    dispatchEvent: () => true,
    querySelector: () => ({ innerText: composerState }),
    querySelectorAll: () => [],
    scrollIntoView() {},
    style: {},
    getBoundingClientRect: () => ({ width: 100, height: 20 }),
  };
  const newChatLink = {
    tagName: 'A',
    getAttribute: (name) => (name === 'aria-label' ? 'New chat' : ''),
    textContent: 'New chat',
    click() {
      clicks.newChat += 1;
      if (newChatWorks) composerState = '';
    },
    scrollIntoView() {},
    style: {},
    getBoundingClientRect: () => ({ width: 60, height: 20 }),
    querySelectorAll: () => [],
  };
  const button = {
    tagName: 'BUTTON',
    getAttribute: (name) => (name === 'aria-label' ? 'Dictate' : ''),
    textContent: '',
    click() {
      clicks.mic += 1;
    },
    scrollIntoView() {},
    style: {},
    getBoundingClientRect: () => ({ width: 28, height: 28 }),
    querySelectorAll: () => [],
  };
  const idleSlot = {
    removeAttribute() {},
    style: {},
    querySelectorAll: () => [button],
  };

  const document = {
    title: 'Google Gemini',
    querySelector: (sel) => (sel.includes('contenteditable') ? box : null),
    querySelectorAll: (sel) => {
      if (sel.includes('speech_dictation_mic_button')) return [idleSlot];
      if (sel.includes('a, button')) return [newChatLink, button];
      if (sel.includes('Dictate')) return [button];
      if (sel.includes('Stop dictation')) return [];
      return [];
    },
    createRange: () => ({ selectNodeContents() {} }),
    execCommand: (cmd) => {
      if (cmd === 'delete' && honoursDelete) composerState = '';
      return true;
    },
  };
  const window = {
    getSelection: () => ({ removeAllRanges() {}, addRange() {} }),
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
    self: { ANTHROPIC_STT_CONFIG: { platforms: { gemini: SELECTORS } } },
    location: { host: 'gemini.google.com', href: 'https://gemini.google.com/app' },
    chrome,
    document,
    window,
    InputEvent: class {
      constructor(type, init) {
        this.type = type;
        this.bubbles = Boolean(init && init.bubbles);
      }
    },
    Event: class {
      constructor(type) {
        this.type = type;
      }
    },
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

  const send = (cmd, opts) =>
    new Promise((resolve, reject) => {
      const id = Math.floor(Math.random() * 100000);
      onMessage({ cmd, id, opts });
      const deadline = Date.now() + 6000;
      const tick = () => {
        const found = replies.find((r) => r.id === id);
        if (found) return resolve(found);
        if (Date.now() > deadline) return reject(new Error('no reply'));
        setTimeout(tick, 5);
      };
      tick();
    });

  return { send, clicks, composer: () => composerState };
}

test('clean clears the composer in place and never clicks New chat', async () => {
  const h = harness({ text: 'hello there' });
  const reply = await h.send('clean', {});
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.equal(reply.result.cleaned, true, JSON.stringify(reply));
  assert.equal(reply.result.via, 'clear', JSON.stringify(reply));
  assert.equal(h.composer(), '');
  assert.equal(h.clicks.newChat, 0, 'a completed dictation must not navigate the page');
});

test('an unfocused window still clears in place (editing commands are no-ops without focus)', async () => {
  // The normal case: the user is typing in another app while the dictation
  // window sits in the background, where document.execCommand silently does
  // nothing. The DOM strategies must carry that case without navigating.
  const h = harness({ text: 'delivered text', honoursDelete: false, nodeEmptyWorks: true });
  const reply = await h.send('clean', {});
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.equal(reply.result.cleaned, true, JSON.stringify(reply));
  assert.equal(reply.result.via, 'clear', JSON.stringify(reply));
  assert.equal(h.composer(), '');
  assert.equal(h.clicks.newChat, 0, 'a background window must not reload the page');
});

test('clean falls back to New chat only when the composer resists in-place clearing', async () => {
  const h = harness({ text: 'hello there', honoursDelete: false, nodeEmptyWorks: false });
  const reply = await h.send('clean', {});
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.equal(reply.result.cleaned, true, JSON.stringify(reply));
  assert.equal(h.clicks.newChat, 1, JSON.stringify(reply));
});

test('an already-empty composer needs no clear and no navigation', async () => {
  const h = harness({ text: '' });
  const reply = await h.send('clean', {});
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.equal(reply.result.cleaned, true, JSON.stringify(reply));
  assert.equal(h.clicks.newChat, 0);
});
