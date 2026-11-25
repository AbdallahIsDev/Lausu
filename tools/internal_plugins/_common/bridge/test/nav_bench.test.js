'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createNavBench } = require('../extension/nav_bench');

const URLS = {
  claude: 'https://claude.ai/new',
  gemini: 'https://gemini.google.com/app',
  chatgpt: 'https://chatgpt.com/',
};

function harness() {
  const tab = { id: 7, status: 'complete', url: URLS.claude };
  const chromeApi = {
    runtime: { lastError: undefined },
    tabs: {
      update(id, opts, cb) {
        tab.url = opts.url;
        tab.status = 'loading';
        setTimeout(() => {
          tab.status = 'complete';
          cb(tab);
        }, 0);
      },
      get(id, cb) {
        cb(tab);
      },
    },
  };
  const commands = [];
  let draftText = '';
  const sendToTab = async (_id, cmd, opts = {}) => {
    commands.push(cmd);
    if (cmd === 'status') {
      return { page: 'ok', micCount: 1, selectorsReady: true, url: tab.url };
    }
    if (cmd === 'diagnostics-draft-set') {
      draftText = String(opts.text || '');
      return { text: draftText };
    }
    if (cmd === 'diagnostics-draft-read') {
      return { text: draftText };
    }
    if (cmd === 'clear') {
      draftText = '';
      return {};
    }
    return {};
  };
  const bench = createNavBench({
    chromeApi,
    resolve: async () => ({ tabId: tab.id }),
    sendToTab,
    targetUrls: URLS,
    handshakeReady: () => true,
    delay: async () => {},
  });
  return { bench, commands, tab };
}

test('nav-bench measures navigation, ready, handshake and an already-open switch', async () => {
  const { bench } = harness();
  const result = await bench({ platforms: ['claude'], runs: 2 });

  assert.equal(result.runs, 2);
  assert.equal(result.results.length, 1);
  assert.equal(result.results[0].rows.length, 2);
  for (const row of result.results[0].rows) {
    assert.equal(typeof row.navigationStartToCompleteMs, 'number');
    assert.equal(typeof row.contentScriptReadyMs, 'number');
    assert.equal(typeof row.bridgeHandshakeMs, 'number');
    assert.equal(typeof row.alreadyOpenSwitchMs, 'number');
    assert.equal(row.switchReady, true);
    assert.equal(row.signedIn, true);
    assert.equal(row.draftKept.kept, true);
  }
});

test('nav-bench clears the draft marker after measuring it', async () => {
  const { bench, commands } = harness();
  await bench({ platforms: ['gemini'], runs: 1 });
  assert.ok(commands.includes('diagnostics-draft-set'));
  assert.ok(commands.includes('clear'));
});

test('nav-bench refuses unknown platforms without touching tabs', async () => {
  const { bench } = harness();
  const result = await bench({ platforms: ['not-a-platform'], runs: 1 });
  assert.equal(result.results.length, 0);
});
