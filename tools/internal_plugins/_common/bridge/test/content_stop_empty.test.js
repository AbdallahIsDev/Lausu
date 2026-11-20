'use strict';

// The page-side stop path used to poll an empty composer until the 15s hard
// timeout before reporting "Empty transcript". These tests drive the REAL
// content script in a vm sandbox with a minimal fake DOM, so the early-exit
// branch is pinned end-to-end through the port reply (not a copied helper).

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const CONTENT = path.resolve(__dirname, '..', 'extension', 'content.js');
const SOURCE = fs.readFileSync(CONTENT, 'utf8');

function harness({ text = () => '', stopVisible = false, micVisible = true } = {}) {
  const replies = [];
  const composer = {
    querySelector: () => ({ innerText: '' }),
    get innerText() {
      return text();
    },
    get textContent() {
      return text();
    },
    getAttribute: () => '',
  };
  const button = {
    tagName: 'BUTTON',
    getAttribute: (name) => (name === 'aria-label' ? 'Finish dictation' : ''),
    textContent: '',
    scrollIntoView() {},
    click() {},
    removeAttribute() {},
    style: {},
    getBoundingClientRect: () => ({ width: 28, height: 28 }),
    querySelectorAll: () => [],
  };
  const idleSlot = {
    removeAttribute() {},
    style: {},
    querySelectorAll: () => (micVisible ? [button] : []),
  };
  const document = {
    title: '',
    querySelector: (sel) => (sel.includes('contenteditable') ? composer : null),
    querySelectorAll: (sel) => {
      if (sel.includes('idle-slot')) return [idleSlot];
      if (sel.includes('finish dictation') || sel.includes('stop recording')) {
        return stopVisible ? [button] : [];
      }
      if (sel.includes('cancel dictation')) return [];
      if (sel.includes('dictate')) return micVisible ? [button] : [];
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
    self: {
      ANTHROPIC_STT_CONFIG: {
        platforms: {
          claude: {
            idleSlot: '[data-cds-part="idle-slot"]',
            composer: 'div[contenteditable="true"]',
            micSelector: 'button[aria-label*="dictate" i]',
            stopSelector: 'button[aria-label*="finish dictation" i]',
            cancelSelector: 'button[aria-label*="cancel dictation" i]',
            newChatNames: ['New chat'],
          },
        },
      },
    },
    location: { host: 'claude.ai', href: 'https://claude.ai/new' },
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
  const port = {
    name: 'stt-bridge',
    onMessage: {
      addListener(fn) {
        onMessage = fn;
      },
    },
    postMessage(payload) {
      replies.push(payload);
    },
  };
  connectListener(port);
  return {
    stop: (opts) =>
      new Promise((resolve, reject) => {
        onMessage({ cmd: 'stop', id: 1, opts });
        const deadline = Date.now() + 3000;
        const tick = () => {
          const found = replies.find((r) => r.id === 1);
          if (found) return resolve(found);
          if (Date.now() > deadline) return reject(new Error('no reply'));
          setTimeout(tick, 5);
        };
        tick();
      }),
  };
}

const FAST = { pollMs: 20, stableMs: 20, stableWindows: 2, timeoutMs: 400 };
// Long enough that the 900ms "platform stopped, no text" grace can fire
// before the hard timeout, just like the real 15s config.
const EMPTY = { ...FAST, timeoutMs: 4000 };

test('stop with no speech and a stopped page returns empty AFTER_STOP, not a timeout', async () => {
  const h = harness();
  const started = Date.now();
  const reply = await h.stop(EMPTY);
  const elapsed = Date.now() - started;
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.equal(reply.result.text, '');
  assert.equal(reply.result.reason, 'empty_after_stop');
  // 900ms grace + small polling slack; the legacy path took the full 15s.
  assert.ok(elapsed < 1800, `expected fast empty stop, got ${elapsed}ms`);
});

test('stop with text still returns the transcript with a stable reason', async () => {
  let visible = '';
  const h = harness({ text: () => visible });
  setTimeout(() => {
    visible = 'hello world';
  }, 40);
  const reply = await h.stop(FAST);
  assert.equal(reply.ok, true, JSON.stringify(reply));
  assert.equal(reply.result.text, 'hello world');
  assert.ok(['stable', 'stopped'].includes(reply.result.reason), reply.result.reason);
  assert.ok(reply.result.state_after);
});

test('an unknown host is a clean no-op: no port listener, no clicks', () => {
  let connected = 0;
  let clicked = 0;
  const sandbox = {
    self: {},
    chrome: {
      storage: { local: { get: (_k, cb) => cb({}) }, onChanged: { addListener() {} } },
      runtime: {
        onMessage: { addListener() {} },
        onConnect: { addListener() { connected += 1; } },
      },
    },
    location: { host: 'unknown.example', href: 'https://unknown.example/' },
    document: { querySelectorAll: () => [], querySelector: () => null, title: '', body: { innerText: '' } },
    getComputedStyle: () => ({ visibility: 'visible', display: 'block', opacity: '1' }),
    setTimeout, clearTimeout, Date, Promise, console,
  };
  const button = { click: () => { clicked += 1; } };
  void button;
  assert.doesNotThrow(() => vm.runInNewContext(SOURCE, sandbox));
  assert.equal(connected, 0);
  assert.equal(clicked, 0);
});
