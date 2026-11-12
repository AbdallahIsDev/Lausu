'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { DEFAULTS, loadConfig } = require('../config_store');

const PLUGIN_DIR = path.resolve(__dirname, '..');
const WORKSPACE = path.resolve(PLUGIN_DIR, '..');

function tempDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'anthropic-stt-config-'));
  fs.copyFileSync(path.join(PLUGIN_DIR, 'config.example.json'), path.join(dir, 'config.example.json'));
  fs.copyFileSync(path.join(PLUGIN_DIR, 'plugin.json'), path.join(dir, 'plugin.json'));
  return dir;
}

test('generates one stable token, persists it atomically, and reuses it', () => {
  const dir = tempDir();
  const first = loadConfig(dir);
  assert.match(first.config.relayToken, /^[a-f0-9]{64}$/);
  assert.equal(first.source, 'config.example.json');

  const persisted = JSON.parse(fs.readFileSync(path.join(dir, 'config.json'), 'utf8'));
  assert.equal(persisted.relayToken, first.config.relayToken);
  assert.deepEqual(
    fs.readdirSync(dir).filter((name) => name.endsWith('.tmp')),
    [],
  );

  const second = loadConfig(dir);
  assert.equal(second.config.relayToken, first.config.relayToken);
  assert.equal(second.source, 'config.json');
});

test('falls back to the example values when config.json is absent', () => {
  const dir = tempDir();
  const { config } = loadConfig(dir);
  for (const key of Object.keys(DEFAULTS)) {
    if (key === 'relayToken') continue;
    assert.deepEqual(config[key], DEFAULTS[key]);
  }
  const example = JSON.parse(fs.readFileSync(path.join(PLUGIN_DIR, 'config.example.json'), 'utf8'));
  assert.equal(example.relayToken, '');
});

test('a config.json without a token gains one and keeps custom values', () => {
  const dir = tempDir();
  fs.writeFileSync(
    path.join(dir, 'config.json'),
    JSON.stringify({ claudeUrl: 'https://claude.ai/new', pollMs: 350 }),
  );
  const { config } = loadConfig(dir);
  assert.equal(config.pollMs, 350);
  assert.match(config.relayToken, /^[a-f0-9]{64}$/);
  assert.equal(loadConfig(dir).config.relayToken, config.relayToken);
});

test('settings.json overrides config.json for the five declared keys', () => {
  const dir = tempDir();
  fs.writeFileSync(
    path.join(dir, 'config.json'),
    JSON.stringify({ pollMs: 300, stableMs: 900, relayToken: 'a'.repeat(64) }),
  );
  fs.writeFileSync(
    path.join(dir, 'settings.json'),
    JSON.stringify({ pollMs: 650, stableWindows: 3, notify: false }),
  );
  const { config } = loadConfig(dir);
  assert.equal(config.pollMs, 650);
  assert.equal(config.stableMs, 900);
  assert.equal(config.stableWindows, 3);
  assert.equal(config.notify, false);
  assert.equal(config.timeoutMs, DEFAULTS.timeoutMs);
});

test('invalid and unknown settings are ignored with one warning', () => {
  const dir = tempDir();
  fs.writeFileSync(
    path.join(dir, 'config.json'),
    JSON.stringify({ pollMs: 300, relayToken: 'b'.repeat(64) }),
  );
  fs.writeFileSync(
    path.join(dir, 'settings.json'),
    JSON.stringify({ pollMs: 5, notify: 'yes', stableMs: 500, mystery: 1 }),
  );
  const warnings = [];
  const original = console.warn;
  console.warn = (...args) => warnings.push(args.join(' '));
  let config;
  try {
    ({ config } = loadConfig(dir));
  } finally {
    console.warn = original;
  }
  assert.equal(config.pollMs, 300);
  assert.equal(config.notify, DEFAULTS.notify);
  assert.equal(config.stableMs, 500);
  assert.equal(config.mystery, undefined);
  assert.equal(warnings.length, 1);
  assert.match(warnings[0], /pollMs/);
  assert.match(warnings[0], /notify/);
  assert.match(warnings[0], /mystery/);
});

test('a missing settings.json leaves defaults and config.json values alone', () => {
  const dir = tempDir();
  const { config } = loadConfig(dir);
  for (const key of ['pollMs', 'stableMs', 'stableWindows', 'timeoutMs', 'notify']) {
    assert.deepEqual(config[key], DEFAULTS[key]);
  }
});

test('the token and the generated extension config are gitignored', () => {
  const git = (...args) => execFileSync('git', ['-C', WORKSPACE, ...args], { stdio: 'pipe' });
  for (const rel of ['anthropic_stt/config.json', 'anthropic_stt/extension/generated/config.js']) {
    assert.doesNotThrow(() => git('check-ignore', '-q', rel), `${rel} must be gitignored`);
  }
});
