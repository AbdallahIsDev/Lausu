'use strict';

// One authority for the STABLE extension install path and shared identities.
// Both the sync step and the operator instructions resolve through here, so a
// refactor cannot orphan Chrome's absolute-path registration again.

const fs = require('fs');
const path = require('path');

const AUTHORITY = path.join(__dirname, 'install.json');
const CFG = JSON.parse(fs.readFileSync(AUTHORITY, 'utf8'));

function dataRoot() {
  if (process.env.LOCALAPPDATA) return process.env.LOCALAPPDATA;
  if (process.env.APPDATA) return path.dirname(process.env.APPDATA);
  const os = require('os');
  return path.join(os.homedir(), 'AppData', 'Local');
}

function stableExtensionDir() {
  return path.join(dataRoot(), ...CFG.extensionRelativePath.split('/'));
}

function targetProfileDir() {
  return path.join(dataRoot(), ...CFG.profileRelativePath.split('/'));
}

function legacyProfileDir() {
  return CFG.legacyProfileRelativePath
    ? path.join(dataRoot(), ...CFG.legacyProfileRelativePath.split('/'))
    : null;
}

// The old folder is used until it has been moved, so a rename never strands
// the owner's signed-in session or the extension registration.
function profileDir() {
  const target = targetProfileDir();
  if (!fs.existsSync(target)) {
    const legacy = legacyProfileDir();
    if (legacy && fs.existsSync(legacy)) return legacy;
  }
  return target;
}

// Atomic same-volume move: never copies or deletes, and fails cleanly while
// Chrome holds files open (the next daemon boot retries).
function migrateProfile() {
  const target = targetProfileDir();
  const legacy = legacyProfileDir();
  if (!legacy || !fs.existsSync(legacy) || fs.existsSync(target)) return { moved: false };
  try {
    fs.renameSync(legacy, target);
    return { moved: true, to: target };
  } catch (err) {
    return { moved: false, blocked: true, error: String(err && err.message) };
  }
}

// Chrome derives an unpacked id from the path SPELLING it was loaded with, so a
// second load (or a path change) leaves install.json's id unregistered while
// another id points at our folder. Match by path first, fall back to the id.
function registeredPath(profile = profileDir()) {
  try {
    const raw = JSON.parse(
      fs.readFileSync(path.join(profile, CFG.profileDirectory, 'Secure Preferences'), 'utf8'),
    );
    const settings = (raw && raw.extensions && raw.extensions.settings) || {};
    const ours = path.resolve(stableExtensionDir());
    for (const entry of Object.values(settings)) {
      if (entry && typeof entry.path === 'string' && path.resolve(entry.path) === ours) {
        return entry.path;
      }
    }
    const entry = settings[CFG.extensionId];
    return entry && typeof entry.path === 'string' ? entry.path : null;
  } catch (_) {
    return null;
  }
}

function repoRoot() {
  return path.resolve(__dirname, '..', '..', '..', '..');
}

function pointsIntoRepo(target) {
  if (!target) return false;
  const resolved = path.resolve(target);
  const root = repoRoot();
  return resolved === root || resolved.startsWith(root + path.sep);
}

const INSTALL_HINT =
  `The dictation extension is not connected. Open chrome://extensions in the dictation profile, ` +
  `enable Developer mode, choose "Load unpacked", and select ${stableExtensionDir()}. ` +
  `Then reload the Claude, Gemini or ChatGPT tab and press the hotkey again.`;

module.exports = {
  AUTHORITY,
  CFG,
  INSTALL_HINT,
  dataRoot,
  profileDir,
  targetProfileDir,
  legacyProfileDir,
  migrateProfile,
  pointsIntoRepo,
  registeredPath,
  repoRoot,
  stableExtensionDir,
};
