'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const diagnostics = require('../diagnostics');
const sync = require('../sync_extension');

const SOURCE_MANIFEST = path.join(sync.SOURCE, 'manifest.json');

test('production manifest is copied verbatim when diagnostics are off', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stt-sync-off-'));
  const original = diagnostics.enabled;
  try {
    diagnostics.enabled = () => false;
    sync.sync({ dir: path.resolve(__dirname, '..', '..', '..', 'anthropic_stt'), targetDir: dir, log: { warn() {} } });
    const installed = JSON.parse(fs.readFileSync(path.join(dir, 'manifest.json'), 'utf8'));
    const source = JSON.parse(fs.readFileSync(SOURCE_MANIFEST, 'utf8'));
    assert.deepEqual(installed.permissions, source.permissions);
    assert.ok(!installed.permissions.includes('tabs'));
    assert.ok(!source.permissions.includes('tabs'));
  } finally {
    diagnostics.enabled = original;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});

test('dev diagnostics add tabs to the INSTALLED manifest only', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stt-sync-on-'));
  const original = diagnostics.enabled;
  try {
    diagnostics.enabled = () => true;
    sync.sync({ dir: path.resolve(__dirname, '..', '..', '..', 'anthropic_stt'), targetDir: dir, log: { warn() {} } });
    const installed = JSON.parse(fs.readFileSync(path.join(dir, 'manifest.json'), 'utf8'));
    const source = JSON.parse(fs.readFileSync(SOURCE_MANIFEST, 'utf8'));
    assert.ok(installed.permissions.includes('tabs'));
    assert.ok(!source.permissions.includes('tabs'));
  } finally {
    diagnostics.enabled = original;
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
