'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { build, check, generatedPath, PLATFORMS } = require('../tools/build-extension');
const { loadConfig } = require('../config_store');

const BRIDGE_DIR = path.resolve(__dirname, '..');
const PLUGIN_DIR = path.resolve(BRIDGE_DIR, '..', '..', 'anthropic_stt');
const SELECTORS = path.join(BRIDGE_DIR, 'selectors');

function tempPlugin() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stt-bridge-build-'));
  fs.copyFileSync(path.join(PLUGIN_DIR, 'config.example.json'), path.join(dir, 'config.example.json'));
  return dir;
}

function options(dir) {
  return { dir, tokenAuthority: path.join(dir, 'token.json'), out: path.join(dir, 'config.js') };
}

function evaluateGenerated(dir) {
  const sandbox = { self: {} };
  vm.runInNewContext(fs.readFileSync(generatedPath(options(dir)), 'utf8'), sandbox);
  return sandbox.self.ANTHROPIC_STT_CONFIG;
}

test('visibility never reaches extension logic', () => {
  const dir = tempPlugin();
  build(options(dir));
  const generated = evaluateGenerated(dir);
  assert.ok(!('visible' in generated), 'Show Browser Window must not reach the extension');
  assert.ok(!('notify' in generated));
});

test('emits BOTH platform selector sets and the same one token the daemon uses', () => {
  const dir = tempPlugin();
  build(options(dir));
  const generated = evaluateGenerated(dir);
  assert.equal(generated.token, loadConfig(dir, options(dir)).config.relayToken);
  assert.match(generated.wsUrl, /^ws:\/\/127\.0\.0\.1:17875\/extension$/);
  assert.deepEqual(Object.keys(generated.platforms).sort(), ['chatgpt', 'claude', 'gemini']);
  for (const platform of PLATFORMS) {
    const selectors = JSON.parse(fs.readFileSync(path.join(SELECTORS, `${platform}.json`), 'utf8'));
    assert.deepEqual(JSON.parse(JSON.stringify(generated.platforms[platform])), selectors);
  }
  assert.equal(generated.platforms.claude.composer.includes('contenteditable'), true);
  assert.equal(generated.platforms.gemini.micSelector, 'button[aria-label^="Dictate"]');
  // ChatGPT's live row has one dictating toggle and no separate discard
  // control, so cancelSelector is deliberately empty (C-ASR-4).
  const chatgpt = generated.platforms.chatgpt;
  assert.ok(chatgpt.stopSelector.includes('data-dictation-button="dictating"'));
  assert.equal(chatgpt.cancelSelector, '');
  assert.notEqual(chatgpt.stopSelector, chatgpt.cancelSelector);
});

test('is deterministic and check passes on a clean tree', () => {
  const dir = tempPlugin();
  build(options(dir));
  const first = fs.readFileSync(generatedPath(options(dir)), 'utf8');
  build(options(dir));
  const second = fs.readFileSync(generatedPath(options(dir)), 'utf8');
  assert.equal(first, second);
  assert.equal(check(options(dir)).ok, true);
  assert.equal(check(options(dir)).tokenMissing, false);
});

test('check never writes: a missing token is reported, not generated', () => {
  const dir = tempPlugin();
  const before = fs.readdirSync(dir).sort();
  const result = check(options(dir));
  assert.equal(result.ok, false);
  assert.equal(result.tokenMissing, true);
  assert.deepEqual(fs.readdirSync(dir).sort(), before);
  assert.equal(fs.existsSync(path.join(dir, 'config.json')), false);
});

test('check fails after a selector edit and leaves the real file untouched', () => {
  const realSelectors = path.join(SELECTORS, 'claude.json');
  const before = fs.readFileSync(realSelectors, 'utf8');
  const dir = tempPlugin();
  build(options(dir));
  try {
    const selectors = JSON.parse(before);
    selectors.idleSlot = '[data-cds-part="moved-slot"]';
    fs.writeFileSync(realSelectors, JSON.stringify(selectors, null, 2) + '\n');
    assert.equal(check(options(dir)).ok, false);
  } finally {
    fs.writeFileSync(realSelectors, before);
  }
  assert.equal(fs.readFileSync(realSelectors, 'utf8'), before);
});
