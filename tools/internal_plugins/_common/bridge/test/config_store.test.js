'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { DEFAULTS, loadConfig } = require('../config_store');

const PLUGIN_DIR = path.resolve(__dirname, '..', '..', '..', 'anthropic_stt');
const WORKSPACE = path.resolve(__dirname, '..', '..', '..');

function tempDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'anthropic-stt-config-'));
  fs.copyFileSync(path.join(PLUGIN_DIR, 'config.example.json'), path.join(dir, 'config.example.json'));
  fs.copyFileSync(path.join(PLUGIN_DIR, 'plugin.json'), path.join(dir, 'plugin.json'));
  return dir;
}

test('generates one stable token, persists it atomically, and reuses it', () => {
  const dir = tempDir();
  const first = loadConfig(dir, { tokenAuthority: path.join(dir, 'token.json') });
  assert.match(first.config.relayToken, /^[a-f0-9]{64}$/);
  assert.equal(first.source, 'config.example.json');

  const persisted = JSON.parse(fs.readFileSync(path.join(dir, 'config.json'), 'utf8'));
  assert.equal(persisted.relayToken, first.config.relayToken);
  assert.deepEqual(
    fs.readdirSync(dir).filter((name) => name.endsWith('.tmp')),
    [],
  );

  const second = loadConfig(dir, { tokenAuthority: path.join(dir, 'token.json') });
  assert.equal(second.config.relayToken, first.config.relayToken);
  assert.equal(second.source, 'config.json');
});

test('falls back to the example values when config.json is absent', () => {
  const dir = tempDir();
  const { config } = loadConfig(dir, { tokenAuthority: path.join(dir, 'token.json') });
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
  const { config } = loadConfig(dir, { tokenAuthority: path.join(dir, 'token.json') });
  assert.equal(config.pollMs, 350);
  assert.match(config.relayToken, /^[a-f0-9]{64}$/);
  assert.equal(loadConfig(dir, { tokenAuthority: path.join(dir, 'token.json') }).config.relayToken, config.relayToken);
});

test('config.json is the single source; a stale settings.json is ignored', () => {
  const dir = tempDir();
  fs.writeFileSync(
    path.join(dir, 'config.json'),
    JSON.stringify({ pollMs: 300, stableMs: 900, relayToken: 'a'.repeat(64), notify: false }),
  );
  fs.writeFileSync(
    path.join(dir, 'settings.json'),
    JSON.stringify({ pollMs: 650, stableWindows: 3, notify: true }),
  );
  const { config } = loadConfig(dir, { tokenAuthority: path.join(dir, 'token.json') });
  assert.equal(config.pollMs, 300);
  assert.equal(config.stableMs, 900);
  assert.equal(config.notify, false);
  assert.equal(config.stableWindows, DEFAULTS.stableWindows);
  assert.equal(config.timeoutMs, DEFAULTS.timeoutMs);
});

test('the measured scrape defaults are fixed, not user knobs', () => {
  assert.equal(DEFAULTS.pollMs, 150);
  assert.equal(DEFAULTS.stableWindows, 2);
  assert.equal(DEFAULTS.stableMs, 500);
  // Still a safety net internally, just no longer surfaced in the manifest.
  assert.equal(DEFAULTS.timeoutMs, 15000);
  const dir = tempDir();
  // C-PLUGIN-2: a manifest declares IDENTITY, never settings -- the visible
  // and notify switches live in the one main config.json. The assertion used
  // to pin a `settings` array in plugin.json, which the unified settings
  // interface deliberately removed; the file was stale, not the behaviour.
  const manifest = JSON.parse(fs.readFileSync(path.join(dir, 'plugin.json'), 'utf8'));
  assert.equal(manifest.settings, undefined);
});

test('the token and the generated extension config are gitignored', () => {
  const git = (...args) => execFileSync('git', ['-C', WORKSPACE, ...args], { stdio: 'pipe' });
  for (const rel of ['anthropic_stt/config.json', '_common/bridge/extension/generated/config.js', '_common/bridge/token.json']) {
    assert.doesNotThrow(() => git('check-ignore', '-q', rel), `${rel} must be gitignored`);
  }
});
