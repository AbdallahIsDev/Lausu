'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const paths = require('../install_paths');

function roots() {
  const original = process.env.LOCALAPPDATA;
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dictation-profile-'));
  fs.mkdirSync(path.join(root, 'voice-typer-internal-plugins'), { recursive: true });
  process.env.LOCALAPPDATA = root;
  return {
    root,
    legacy: paths.legacyProfileDir(),
    target: paths.targetProfileDir(),
    restore() {
      if (original === undefined) delete process.env.LOCALAPPDATA;
      else process.env.LOCALAPPDATA = original;
      fs.rmSync(root, { recursive: true, force: true });
    },
  };
}

test('the legacy folder is used until it is moved', (t) => {
  const r = roots();
  t.after(() => r.restore());
  fs.mkdirSync(r.legacy, { recursive: true });

  assert.equal(path.resolve(paths.profileDir()), path.resolve(r.legacy));
  assert.equal(paths.migrateProfile().moved, true);
  assert.equal(path.resolve(paths.profileDir()), path.resolve(r.target));
});

test('migration preserves the signed-in profile contents', (t) => {
  const r = roots();
  t.after(() => r.restore());
  fs.mkdirSync(r.legacy, { recursive: true });
  fs.writeFileSync(path.join(r.legacy, 'Secure Preferences'), '{"signed-in": true}');

  assert.equal(paths.migrateProfile().moved, true);
  assert.equal(fs.existsSync(r.legacy), false);
  assert.equal(
    fs.readFileSync(path.join(r.target, 'Secure Preferences'), 'utf8'),
    '{"signed-in": true}',
  );
});

test('migration never overwrites an existing target', (t) => {
  const r = roots();
  t.after(() => r.restore());
  fs.mkdirSync(r.legacy, { recursive: true });
  fs.mkdirSync(r.target, { recursive: true });
  fs.writeFileSync(path.join(r.target, 'new'), 'new');

  assert.equal(paths.migrateProfile().moved, false);
  assert.equal(fs.readFileSync(path.join(r.target, 'new'), 'utf8'), 'new');
});
