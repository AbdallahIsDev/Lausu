'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { build, check, generatedPath } = require('../tools/build-extension');
const { loadConfig } = require('../config_store');

const PLUGIN_DIR = path.resolve(__dirname, '..');

function tempPlugin() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'anthropic-stt-build-'));
  fs.copyFileSync(path.join(PLUGIN_DIR, 'selectors.json'), path.join(dir, 'selectors.json'));
  fs.copyFileSync(path.join(PLUGIN_DIR, 'config.example.json'), path.join(dir, 'config.example.json'));
  return dir;
}

function evaluateGenerated(dir) {
  const sandbox = { self: {} };
  vm.runInNewContext(fs.readFileSync(generatedPath(dir), 'utf8'), sandbox);
  return sandbox.self.ANTHROPIC_STT_CONFIG;
}

test('writes selectors and the same token the daemon uses', () => {
  const dir = tempPlugin();
  build({ dir });
  const generated = evaluateGenerated(dir);
  assert.equal(generated.token, loadConfig(dir).config.relayToken);
  assert.match(generated.wsUrl, /^ws:\/\/127\.0\.0\.1:17875\/extension$/);
  const selectors = JSON.parse(fs.readFileSync(path.join(dir, 'selectors.json'), 'utf8'));
  assert.equal(generated.selectors.composer, selectors.composer);
  assert.equal(generated.selectors.idleSlot, selectors.idleSlot);
});

test('is deterministic and check passes on a clean tree', () => {
  const dir = tempPlugin();
  build({ dir });
  const first = fs.readFileSync(generatedPath(dir), 'utf8');
  build({ dir });
  const second = fs.readFileSync(generatedPath(dir), 'utf8');
  assert.equal(first, second);
  assert.equal(check({ dir }).ok, true);
  assert.equal(check({ dir }).tokenMissing, false);
});

test('check never writes: a missing token is reported, not generated', () => {
  const dir = tempPlugin();
  const before = fs.readdirSync(dir).sort();
  const result = check({ dir });
  assert.equal(result.ok, false);
  assert.equal(result.tokenMissing, true);
  assert.deepEqual(fs.readdirSync(dir).sort(), before);
  assert.equal(fs.existsSync(path.join(dir, 'config.json')), false);
  assert.equal(fs.existsSync(generatedPath(dir)), false);
});

test('check fails after a selector edit and leaves the real file untouched', () => {
  const realSelectors = path.join(PLUGIN_DIR, 'selectors.json');
  const before = fs.readFileSync(realSelectors, 'utf8');
  const dir = tempPlugin();
  build({ dir });
  const selectorsFile = path.join(dir, 'selectors.json');
  const selectors = JSON.parse(fs.readFileSync(selectorsFile, 'utf8'));
  selectors.idleSlot = '[data-cds-part="moved-slot"]';
  fs.writeFileSync(selectorsFile, JSON.stringify(selectors, null, 2));
  const result = check({ dir });
  assert.equal(result.ok, false);
  assert.equal(fs.readFileSync(realSelectors, 'utf8'), before);
});
