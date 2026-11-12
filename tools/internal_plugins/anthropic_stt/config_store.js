'use strict';

// Single authority for the plugin's config.json. The daemon, the relay and the
// extension generator all load through here so defaults and the relay token can
// never disagree. The token is generated once, persisted, and never logged.
//
// The Plugins page writes <plugin>/settings.json (manifest-declared values).
// Those five keys override config.json here; config.json stays the fallback
// layer for keys settings.json does not carry.

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const DEFAULTS = {
  claudeUrl: 'https://claude.ai/new',
  profileDir: 'C:/Users/11/AppData/Local/voice-typer-internal-plugins/google-stt-profile',
  pollMs: 200,
  stableMs: 800,
  stableWindows: 2,
  startTimeoutMs: 5000,
  timeoutMs: 15000,
  notify: true,
};

// Only these manifest-declared settings are daemon knobs. Anything else in
// settings.json is ignored: plugin.json is the authority on type and range.
const SETTING_KEYS = ['pollMs', 'stableMs', 'stableWindows', 'timeoutMs', 'notify'];

function configPath(dir) {
  return path.join(dir, 'config.json');
}

function examplePath(dir) {
  return path.join(dir, 'config.example.json');
}

function settingsPath(dir) {
  return path.join(dir, 'settings.json');
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (_) {
    return null;
  }
}

function normalize(raw) {
  const out = {};
  for (const key of Object.keys(DEFAULTS)) {
    out[key] = raw && raw[key] !== undefined ? raw[key] : DEFAULTS[key];
  }
  out.relayToken = raw && typeof raw.relayToken === 'string' ? raw.relayToken : '';
  return out;
}

function validSetting(spec, value) {
  if (spec.type === 'bool') return typeof value === 'boolean';
  if (spec.type === 'int') {
    if (!Number.isInteger(value)) return false;
    if (typeof spec.min === 'number' && value < spec.min) return false;
    if (typeof spec.max === 'number' && value > spec.max) return false;
    return true;
  }
  return false;
}

function applySettings(dir, config) {
  const file = settingsPath(dir);
  if (!fs.existsSync(file)) return config;
  const raw = readJson(file);
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    console.warn('[anthropic-stt] ignoring invalid settings.json');
    return config;
  }
  const manifest = readJson(path.join(dir, 'plugin.json'));
  const declared = new Map();
  if (manifest && Array.isArray(manifest.settings)) {
    for (const spec of manifest.settings) {
      if (spec && typeof spec.key === 'string') declared.set(spec.key, spec);
    }
  }
  const ignored = [];
  for (const key of Object.keys(raw)) {
    if (!SETTING_KEYS.includes(key)) {
      ignored.push(key);
      continue;
    }
    const spec = declared.get(key);
    if (!spec || !validSetting(spec, raw[key])) {
      ignored.push(key);
      continue;
    }
    config[key] = raw[key];
  }
  if (ignored.length) {
    console.warn(`[anthropic-stt] ignoring settings.json value(s): ${ignored.sort().join(', ')}`);
  }
  return config;
}

function writeAtomic(file, value) {
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2) + '\n', 'utf8');
  try {
    fs.renameSync(tmp, file);
  } catch (err) {
    try {
      fs.unlinkSync(tmp);
    } catch (_) {}
    throw err;
  }
}

function loadConfig(dir = __dirname, options = {}) {
  const persist = options.persist !== false;
  const file = configPath(dir);
  const existed = fs.existsSync(file);
  const fileRaw = existed ? readJson(file) : null;
  const raw = fileRaw || readJson(examplePath(dir)) || {};
  const config = normalize(raw);
  const tokenMissing = !config.relayToken;
  if (tokenMissing) config.relayToken = crypto.randomBytes(32).toString('hex');
  if (persist && (!existed || tokenMissing)) writeAtomic(file, config);
  applySettings(dir, config);
  return {
    config,
    path: file,
    source: fileRaw ? 'config.json' : 'config.example.json',
    tokenMissing,
  };
}

module.exports = {
  DEFAULTS,
  SETTING_KEYS,
  configPath,
  examplePath,
  loadConfig,
  normalize,
  settingsPath,
  writeAtomic,
};
