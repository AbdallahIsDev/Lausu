'use strict';

// Syncs the SOURCE extension into the STABLE app-data install path on every
// daemon boot and after a settings change. Chrome registers unpacked
// extensions by absolute path, so the install location must never move with
// the repository. The source tree stays the single source of truth.

const fs = require('fs');
const path = require('path');
const { build } = require('./tools/build-extension');
const paths = require('./install_paths');

const SOURCE = path.join(__dirname, 'extension');
const SCRIPT_FILES = ['manifest.json', 'content.js', 'service_worker.js', 'popup.html', 'popup.js'];
const ICONS_DIR = 'icons';
const GENERATED_DIR = 'generated';
const GENERATED_FILE = 'config.js';
const LOG = '[stt-bridge]';

function expectedTopLevel() {
  return new Set([...SCRIPT_FILES, ICONS_DIR, GENERATED_DIR]);
}

function copyFresh(source, target) {
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.copyFileSync(source, target);
}

function removeStale(targetDir) {
  const keep = expectedTopLevel();
  for (const entry of fs.readdirSync(targetDir, { withFileTypes: true })) {
    if (!keep.has(entry.name)) {
      fs.rmSync(path.join(targetDir, entry.name), { recursive: true, force: true });
      continue;
    }
    if (entry.name === ICONS_DIR && entry.isDirectory()) {
      const sourceIcons = new Set(fs.readdirSync(path.join(SOURCE, ICONS_DIR)));
      for (const icon of fs.readdirSync(path.join(targetDir, ICONS_DIR))) {
        if (!sourceIcons.has(icon)) fs.rmSync(path.join(targetDir, ICONS_DIR, icon), { force: true });
      }
    }
    if (entry.name === GENERATED_DIR && entry.isDirectory()) {
      for (const file of fs.readdirSync(path.join(targetDir, GENERATED_DIR))) {
        if (file !== GENERATED_FILE) fs.rmSync(path.join(targetDir, GENERATED_DIR, file), { force: true });
      }
    }
  }
}

function warnAboutRepoRegistration(log) {
  const registered = paths.registeredPath();
  if (registered && paths.pointsIntoRepo(registered)) {
    const message =
      `${LOG} the dictation extension is registered from the source tree (${registered}). ` +
      `Load unpacked again from ${paths.stableExtensionDir()}; a repo move removes that registration.`;
    log.warn(message);
    return message;
  }
  return null;
}

function sync(options = {}) {
  const targetDir = options.targetDir || paths.stableExtensionDir();
  const log = options.log || console;
  fs.mkdirSync(targetDir, { recursive: true });
  for (const name of SCRIPT_FILES) copyFresh(path.join(SOURCE, name), path.join(targetDir, name));
  for (const icon of fs.readdirSync(path.join(SOURCE, ICONS_DIR))) {
    copyFresh(path.join(SOURCE, ICONS_DIR, icon), path.join(targetDir, ICONS_DIR, icon));
  }
  build({
    dir: options.dir,
    config: options.config,
    persist: options.persist !== false,
    tokenAuthority: options.tokenAuthority,
    out: path.join(targetDir, GENERATED_DIR, GENERATED_FILE),
  });
  removeStale(targetDir);
  warnAboutRepoRegistration(log);
  return { targetDir, files: syncedFiles(targetDir) };
}

function syncedFiles(targetDir) {
  const out = [];
  for (const entry of fs.readdirSync(targetDir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      for (const child of fs.readdirSync(path.join(targetDir, entry.name))) {
        out.push(`${entry.name}/${child}`);
      }
    } else {
      out.push(entry.name);
    }
  }
  return out.sort();
}

module.exports = { ICONS_DIR, SCRIPT_FILES, GENERATED_FILE, SOURCE, sync, syncedFiles, warnAboutRepoRegistration };
