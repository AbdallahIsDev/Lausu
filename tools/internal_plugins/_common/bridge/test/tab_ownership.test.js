'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createTabResolver } = require('../extension/tab_resolution');
const { createOwnership } = require('../extension/tab_ownership');

const PATTERNS = { claude: 'https://claude.ai/*', gemini: 'https://gemini.google.com/*', chatgpt: 'https://chatgpt.com/*' };
const URLS = { claude: 'https://claude.ai/new', gemini: 'https://gemini.google.com/app', chatgpt: 'https://chatgpt.com/' };

function harness(tabs) {
  const state = new Map(tabs.map((tab) => [tab.id, { ...tab, windowId: tab.windowId || 1 }]));
  const removed = [];
  const chromeApi = {
    runtime: { lastError: undefined },
    tabs: {
      query(opts, cb) {
        const all = [...state.values()];
        cb(!opts.url ? all : all.filter((tab) => String(tab.url || '').startsWith(opts.url.slice(0, -1))));
      },
      create(opts, cb) {
        const tab = { id: 99, url: opts.url, active: false, windowId: 1 };
        state.set(tab.id, tab);
        cb(tab);
      },
      update(id, opts, cb) {
        const tab = state.get(id);
        if (tab) Object.assign(tab, opts);
        cb(tab);
      },
      remove(id, cb) {
        removed.push(id);
        state.delete(id);
        cb();
      },
    },
    storage: { session: { get: async (k) => ({ [k]: store[k] }), set: async (v) => Object.assign(store, v) } },
  };
  const store = {};
  const ownership = createOwnership(chromeApi.storage);
  const resolver = createTabResolver({
    chromeApi, patterns: PATTERNS, targetUrls: URLS, ownership,
    probe: async () => true, delay: async () => {},
  });
  return { resolver, removed, state, ownership };
}

test('a user tab is adopted but never closed', async () => {
  const h = harness([
    { id: 7, url: 'https://claude.ai/chat/abc', active: true },
    { id: 8, url: 'https://claude.ai/new', active: false },
  ]);
  await h.ownership.mark({ id: 8, windowId: 1, url: 'https://claude.ai/new' }, 'claude', 'https://claude.ai/');

  const result = await h.resolver.ensure('claude');

  assert.equal(result.tabId, 7);
  assert.ok(!h.removed.includes(7), 'the user tab must survive');
});

test('two user tabs are adopted with no closure', async () => {
  const h = harness([
    { id: 7, url: 'https://claude.ai/chat/a', active: true },
    { id: 8, url: 'https://claude.ai/chat/b', active: false },
  ]);

  await h.resolver.ensure('claude');

  assert.deepEqual(h.removed, []);
});

test('owned surplus tabs are still deduped', async () => {
  const h = harness([
    { id: 7, url: 'https://claude.ai/a', active: true },
    { id: 8, url: 'https://claude.ai/b', active: false },
  ]);
  for (const id of [7, 8]) {
    await h.ownership.mark({ id, windowId: 1, url: 'https://claude.ai/' }, 'claude', 'https://claude.ai/');
  }

  await h.resolver.ensure('claude');

  assert.deepEqual(h.removed, [8]);
});

test('a stale owned id reused by another platform is never closed', async () => {
  const h = harness([
    { id: 7, url: 'https://claude.ai/a', active: true },
    { id: 8, url: 'https://gemini.google.com/app', active: false },
  ]);
  await h.ownership.mark({ id: 8, windowId: 1, url: 'https://claude.ai/' }, 'claude', 'https://claude.ai/');

  await h.resolver.ensure('claude');

  assert.ok(!h.removed.includes(8));
});
