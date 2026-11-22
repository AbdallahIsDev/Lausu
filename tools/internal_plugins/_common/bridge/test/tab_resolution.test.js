'use strict';

// Target-tab identity lives in the extension: it is the only layer with the
// chrome.tabs API. These cases pin the resolution policy both plugins rely on.

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createTabResolver, createDispatcher } = require('../extension/tab_resolution');

const PATTERNS = {
  claude: 'https://claude.ai/*',
  gemini: 'https://gemini.google.com/*',
};
const URLS = {
  claude: 'https://claude.ai/new',
  gemini: 'https://gemini.google.com/app',
};

function urlMatches(pattern, url) {
  return String(url).startsWith(pattern.slice(0, -1));
}

function fakeChrome(initial = []) {
  const tabs = new Map();
  let nextId = 100;
  for (const tab of initial) {
    tabs.set(tab.id, {
      id: tab.id,
      url: tab.url,
      active: !!tab.active,
      windowId: 1,
    });
  }
  const calls = { query: [], create: [], update: [] };
  const api = {
    tabs: {
      query(opts, cb) {
        calls.query.push(opts);
        cb(
          [...tabs.values()].filter(
            (tab) => !opts.url || urlMatches(opts.url, tab.url),
          ),
        );
      },
      create(opts, cb) {
        calls.create.push(opts);
        const tab = {
          id: nextId++,
          url: opts.url,
          active: !!opts.active,
          windowId: 1,
        };
        tabs.set(tab.id, tab);
        cb(tab);
      },
      update(id, opts, cb) {
        calls.update.push([id, opts]);
        const tab = tabs.get(id);
        if (tab) Object.assign(tab, opts);
        cb(tab);
      },
    },
    runtime: { lastError: undefined },
  };
  return { api, calls, tabs, close: (id) => tabs.delete(id) };
}

function resolverFor(chrome, overrides = {}) {
  return createTabResolver({
    chromeApi: chrome.api,
    patterns: PATTERNS,
    targetUrls: URLS,
    probe: async () => true,
    delay: async () => {},
    ...overrides,
  });
}

test('reuses an existing matching tab without creating another', async () => {
  const chrome = fakeChrome([{ id: 7, url: 'https://claude.ai/new' }]);
  const result = await resolverFor(chrome).ensure('claude');

  assert.equal(result.tabId, 7);
  assert.equal(result.created, false);
  assert.equal(chrome.calls.create.length, 0);
});

test('picks the active matching tab when two tabs exist for one plugin', async () => {
  const chrome = fakeChrome([
    { id: 7, url: 'https://claude.ai/chat/old' },
    { id: 8, url: 'https://claude.ai/new', active: true },
  ]);
  const result = await resolverFor(chrome).ensure('claude');

  assert.equal(result.tabId, 8);
  assert.equal(chrome.calls.create.length, 0);
});

test('falls back to the lowest tab id when no matching tab is active', async () => {
  const chrome = fakeChrome([
    { id: 9, url: 'https://claude.ai/chat/newer' },
    { id: 7, url: 'https://claude.ai/chat/older' },
  ]);
  const result = await resolverFor(chrome).ensure('claude');

  assert.equal(result.tabId, 7);
  assert.equal(chrome.calls.create.length, 0);
});

test('creates exactly one replacement tab when the target tab was closed', async () => {
  const chrome = fakeChrome([{ id: 2, url: 'https://www.google.com/' }]);
  const result = await resolverFor(chrome).ensure('claude');

  assert.equal(result.created, true);
  assert.equal(chrome.calls.create.length, 1);
  assert.deepEqual(chrome.calls.create[0], {
    url: 'https://claude.ai/new',
    active: false,
  });
  assert.equal(result.tabId, 100);
  assert.equal(chrome.tabs.has(2), true, 'unrelated tab must not be closed');
});

test('matches a navigated route on the same platform domain', async () => {
  const chrome = fakeChrome([{ id: 11, url: 'https://gemini.google.com/app?auth=1' }]);
  const result = await resolverFor(chrome).ensure('gemini');

  assert.equal(result.tabId, 11);
  assert.equal(result.created, false);
});

test('never selects an unrelated active tab just because it is active', async () => {
  const chrome = fakeChrome([{ id: 3, url: 'https://example.com/', active: true }]);
  const result = await resolverFor(chrome).ensure('claude');

  assert.equal(chrome.calls.create.length, 1);
  assert.equal(urlMatches(PATTERNS.claude, chrome.tabs.get(result.tabId).url), true);
});

test('coalesces simultaneous resolutions into one created tab', async () => {
  const chrome = fakeChrome();
  const resolver = resolverFor(chrome);

  const [first, second] = await Promise.all([
    resolver.ensure('claude'),
    resolver.ensure('claude'),
  ]);

  assert.equal(chrome.calls.create.length, 1);
  assert.equal(first.tabId, second.tabId);
});

test('re-resolves once when the tab disappears before dispatch', async () => {
  const ensured = [];
  const sent = [];
  const resolver = {
    async ensure() {
      ensured.push('ensure');
      return { tabId: ensured.length === 1 ? 7 : 8, created: false };
    },
    async find() {
      return { id: 7 };
    },
  };
  const dispatcher = createDispatcher({
    resolver,
    resolvingCommands: new Set(['start']),
    sendToTab: async (tabId) => {
      sent.push(tabId);
      if (sent.length === 1) throw { kind: 'browser-not-open', error: 'the target tab is not open' };
      return { ok: true };
    },
  });

  const result = await dispatcher.dispatch('claude', 'start', {});
  assert.deepEqual(result, { ok: true });
  assert.deepEqual(ensured, ['ensure', 'ensure']);
  assert.deepEqual(sent, [7, 8]);
});

test('stop and cancel never create a replacement tab', async () => {
  let ensured = 0;
  let found = 0;
  const dispatcher = createDispatcher({
    resolver: {
      async ensure() {
        ensured += 1;
        return { tabId: 9 };
      },
      async find() {
        found += 1;
        return { id: 9 };
      },
    },
    resolvingCommands: new Set(['start']),
    sendToTab: async () => ({ ok: true }),
  });

  await dispatcher.dispatch('claude', 'stop', {});
  assert.equal(ensured, 0);
  assert.equal(found, 1);
});

test('find never creates a tab, so a status probe cannot open one', async () => {
  const chrome = fakeChrome();
  const result = await resolverFor(chrome).find('claude');

  assert.equal(result, null);
  assert.equal(chrome.calls.create.length, 0);
});
