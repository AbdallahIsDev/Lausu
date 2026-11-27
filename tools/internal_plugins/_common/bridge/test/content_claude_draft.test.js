'use strict';

// Claude streams live words into hidden spans inside a composer that becomes
// read-only while recording. innerText on the outer box is a newline (truthy
// but empty after trim) and the old composer selectors require contenteditable
// =true, so the shipped innerText/composerText path returns "". The real
// content script must use the per-platform textContent structure instead.

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const BRIDGE = path.resolve(__dirname, '..');
const SOURCE = fs.readFileSync(path.join(BRIDGE, 'extension', 'content.js'), 'utf8');
const CLAUDE = JSON.parse(fs.readFileSync(path.join(BRIDGE, 'selectors', 'claude.json'), 'utf8'));
const CHATGPT = JSON.parse(fs.readFileSync(path.join(BRIDGE, 'selectors', 'chatgpt.json'), 'utf8'));

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
if (!jsdom) console.warn('[claude] jsdom missing: DOM cases SKIPPED');

function claudeComposer({ dir = '', text = '', words = [] } = {}) {
  const spans = words
    .map((w) => `<span data-dictation=""><span data-dictation-words="hidden" class="hidden">${w}</span></span>`)
    .join('');
  const end = '<span data-dictation-words="end" contenteditable="false" class="ProseMirror-widget"></span>';
  const separators = '<img class="ProseMirror-separator" alt=""><br class="ProseMirror-trailingBreak">';
  const dirAttr = dir ? ` dir="${dir}"` : '';
  return (
    `<div contenteditable="false" role="textbox" data-testid="chat-input" ` +
    `data-composer-editor="marlin" data-draft-persisted="true" aria-label="Write your prompt to Claude" ` +
    `aria-readonly="true"${dirAttr} class="tiptap ProseMirror">` +
    `<p dir="auto">${spans}${end}${separators}</p></div>` +
    (text ? `<div id="stale-draft">${text}</div>` : '')
  );
}

function createPage({ body, url = 'https://claude.ai/new', platform = 'claude', selectors = CLAUDE }) {
  const dom = new jsdom.JSDOM(`<!doctype html><html><body>${body}</body></html>`, {
    url,
    runScripts: 'outside-only',
  });
  const { window } = dom;
  window.Element.prototype.getBoundingClientRect = function () {
    return { width: 24, height: 24, top: 0, left: 0, right: 24, bottom: 24, x: 0, y: 0 };
  };
  // Chrome's innerText skips hidden content; jsdom has no innerText at all.
  Object.defineProperty(window.Element.prototype, 'innerText', {
    configurable: true,
    get() {
      if (this.hasAttribute && this.hasAttribute('data-testid') && this.getAttribute('data-testid') === 'chat-input') {
        return '\n';
      }
      if (this.tagName === 'P') return '';
      return this.textContent || '';
    },
  });
  let connectListener = null;
  window.chrome = {
    storage: {
      local: { get: (_k, cb) => cb({ enabled: true }) },
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
  window.ANTHROPIC_STT_CONFIG = { platforms: { [platform]: selectors } };
  window.eval(SOURCE);
  let onMessage = null;
  const replies = [];
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
  const send = (cmd) =>
    new Promise((resolve, reject) => {
      const id = replies.length + 1;
      onMessage({ cmd, id, opts: {} });
      const deadline = Date.now() + 5000;
      const tick = () => {
        const found = replies.find((r) => r.id === id);
        if (found) return resolve(found);
        if (Date.now() > deadline) return reject(new Error(`no reply for ${cmd}`));
        setTimeout(tick, 5);
      };
      tick();
    });
  return { send, document: window.document };
}

const SENTENCE = 'This is what your dictated text sounds like when spoken back to you.';

domTest('Claude hidden-span live text is read by textContent, not innerText', async () => {
  const page = createPage({ body: claudeComposer({ words: [SENTENCE] }) });
  const outer = page.document.querySelector('[data-testid="chat-input"]');
  assert.equal(outer.innerText.trim(), '');
  assert.equal(outer.textContent.trim(), SENTENCE);
  const reply = await page.send('draft-snapshot');
  assert.equal(reply.ok, true);
  assert.equal(reply.result.text, SENTENCE);
  assert.equal(reply.result.source, 'live-selector');
});

domTest('Arabic rtl and English ltr/absent dir produce identical logical text', async () => {
  const arabic = 'هذا اختبار للنص المكتوب';
  for (const dir of ['rtl', 'ltr', '']) {
    const page = createPage({ body: claudeComposer({ dir, words: [arabic] }) });
    const reply = await page.send('draft-snapshot');
    assert.equal(reply.result.text, arabic, `dir=${dir || 'absent'}`);
  }
  for (const dir of ['rtl', 'ltr', '']) {
    const page = createPage({ body: claudeComposer({ dir, words: [SENTENCE] }) });
    const reply = await page.send('draft-snapshot');
    assert.equal(reply.result.text, SENTENCE, `dir=${dir || 'absent'}`);
  }
});

domTest('mixed text, emoji and long text keep DOM order', async () => {
  const parts = ['abc ', 'مرحبا', ' 😀 ', 'end '.repeat(100)];
  const page = createPage({ body: claudeComposer({ dir: 'rtl', words: parts }) });
  const reply = await page.send('draft-snapshot');
  assert.equal(reply.result.text, parts.join('').trim());
  assert.equal(reply.result.text.length, parts.join('').trim().length);
});

domTest('empty end widget, separator and br are ignored', async () => {
  const page = createPage({ body: claudeComposer({ words: ['one', '', 'two'] }) });
  const reply = await page.send('draft-snapshot');
  assert.equal(reply.result.text, 'onetwo');
});

domTest('empty Claude composer returns no text', async () => {
  const page = createPage({ body: claudeComposer({ words: [] }) });
  const reply = await page.send('draft-snapshot');
  assert.equal(reply.ok, true);
  assert.equal(reply.result.text, '');
});

domTest('ChatGPT extraction remains unchanged (owner-verified path)', async () => {
  const body =
    '<form data-chatgpt-composer><div data-composer-markdown contenteditable="true" role="textbox" ' +
    `class="ProseMirror" aria-label="Ask ChatGPT"><p>${SENTENCE}</p></div></form>`;
  const page = createPage({
    body,
    url: 'https://chatgpt.com/',
    platform: 'chatgpt',
    selectors: CHATGPT,
  });
  const reply = await page.send('draft-snapshot');
  assert.equal(reply.ok, true);
  assert.equal(reply.result.text, SENTENCE);
});
