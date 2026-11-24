'use strict';

// Single authority for the SHARED Chrome-extension bridge config. Both plugins
// load through here: one relay token, one port, one profile directory. The
// per-plugin config.json is a platform descriptor (platform/url/port/token)
// plus that plugin's user settings; it is per-machine and gitignored.

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const paths = require('./install_paths');

const BRIDGE_DIR = __dirname;
const PORT = paths.CFG.relayPort;
const PROFILE_DIR = paths.profileDir().split(path.sep).join('/');
const TOKEN_FILE = path.join(BRIDGE_DIR, 'token.json');
const URLS = {
  claude: 'https://claude.ai/new',
  gemini: 'https://gemini.google.com/app',
  chatgpt: 'https://chatgpt.com/',
};

// Measured 2026-11-19: poll 150 / 2 stable reads / 500ms beat 261 / 2 / 800
// by ~200ms (741ms vs 942ms median scrape). Fixed defaults, not knobs.
const DEFAULTS = {
  platform: 'claude',
  url: URLS.claude,
  claudeUrl: URLS.claude,
  geminiUrl: URLS.gemini,
  chatgptUrl: URLS.chatgpt,
  port: PORT,
  profileDir: PROFILE_DIR,
  pollMs: 150,
  stableMs: 500,
  stableWindows: 2,
  startTimeoutMs: 5000,
  timeoutMs: 15000,
  visible: true,
  notify: true,
};

function configPath(dir) {
  return path.join(dir, 'config.json');
}

function examplePath(dir) {
  return path.join(dir, 'config.example.json');
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch (_) {
    return null;
  }
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

function platformFor(dir, raw) {
  const candidate = raw && raw.platform;
  if (candidate === 'claude' || candidate === 'gemini' || candidate === 'chatgpt') return candidate;
  const name = path.basename(String(dir)).toLowerCase();
  if (name.includes('google')) return 'gemini';
  if (name.includes('chatgpt')) return 'chatgpt';
  return 'claude';
}

// Each platform's own URL key: the descriptor names the tab its plugin owns,
// and the config keeps that name so a plugin never has to know about another
// platform's URL.
const PLATFORM_URL_KEYS = {
  claude: 'claudeUrl',
  gemini: 'geminiUrl',
  chatgpt: 'chatgptUrl',
};

function normalize(dir, raw) {
  const platform = platformFor(dir, raw);
  const out = {};
  for (const key of Object.keys(DEFAULTS)) {
    out[key] = raw && raw[key] !== undefined ? raw[key] : DEFAULTS[key];
  }
  out.platform = platform;
  const urlKey = PLATFORM_URL_KEYS[platform] || 'claudeUrl';
  out.url = (raw && (raw.url || raw[urlKey])) || URLS[platform];
  out[urlKey] = out.url;
  // The profile path belongs to install.json (and its one-time migration),
  // never to a per-plugin config snapshot that can go stale after a rename.
  out.profileDir = paths.profileDir().split(path.sep).join('/');
  out.port = Number(optionsPort(raw) || PORT);
  out.relayToken = raw && typeof raw.relayToken === 'string' ? raw.relayToken : '';
  out.selectorsRef =
    raw && typeof raw.selectorsRef === 'string'
      ? raw.selectorsRef
      : path.relative(dir, path.join(BRIDGE_DIR, 'selectors', `${platform}.json`)).replace(/\\/g, '/');
  return out;
}

function optionsPort(raw) {
  return raw && raw.port;
}

// The one token authority. An existing Anthropic config.json token is adopted
// on first use so an already-installed extension keeps working without a
// rotation; after that the shared file is the only source.
function resolveToken(dir, raw, options = {}) {
  const authority = options.tokenAuthority || TOKEN_FILE;
  const stored = readJson(authority);
  if (stored && typeof stored.relayToken === 'string' && stored.relayToken) return stored.relayToken;
  // Migrate from the plugin descriptor or the former Anthropic-only file.
  const legacy =
    (raw && raw.relayToken) ||
    readJson(path.join(path.dirname(dir), 'anthropic_stt', 'config.json')) ||
    {};
  const token = typeof legacy.relayToken === 'string' && legacy.relayToken ? legacy.relayToken : crypto.randomBytes(32).toString('hex');
  if (options.persist !== false) {
    writeAtomic(authority, { relayToken: token });
  }
  return token;
}

function loadConfig(dir = BRIDGE_DIR, options = {}) {
  const persist = options.persist !== false;
  const file = configPath(dir);
  const existed = fs.existsSync(file);
  const fileRaw = existed ? readJson(file) : null;
  const raw = fileRaw || readJson(examplePath(dir)) || {};
  const config = normalize(dir, raw);
  const tokenMissing = !config.relayToken;
  const token = resolveToken(dir, raw, options);
  config.relayToken = token;
  if (persist && (!existed || tokenMissing)) writeAtomic(file, config);
  return {
    config,
    path: file,
    source: fileRaw ? 'config.json' : 'config.example.json',
    tokenMissing,
  };
}

module.exports = {
  BRIDGE_DIR,
  DEFAULTS,
  PORT,
  PROFILE_DIR,
  TOKEN_FILE,
  URLS,
  configPath,
  examplePath,
  loadConfig,
  normalize,
  resolveToken,
  writeAtomic,
};
