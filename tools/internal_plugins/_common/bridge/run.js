#!/usr/bin/env node
'use strict';

// Wiring for the ONE shared bridge: config -> generated extension config ->
// relay -> HTTP control plane. The profile is started by chrome_profile.py
// (plain flags only); nothing here watches or drives the browser window.

const http = require('http');
const fs = require('fs');
const path = require('path');
const installPaths = require('./install_paths');
const { loadConfig, PORT } = require('./config_store');
const { Relay } = require('./relay');
const { handle } = require('./control_plane');
const { build } = require('./tools/build-extension');
const { sync } = require('./sync_extension');
const { installParentWatch } = require('../../parent_watch');

const BRIDGE_DIR = __dirname;
const LOG = '[stt-bridge]';

function argValue(name) {
  const flag = `--${name}=`;
  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith(flag)) return arg.slice(flag.length);
  }
  return '';
}

// A packaged install passes the owning plugin dir explicitly; a direct node
// run defaults to the Claude plugin so the historical invocation still works.
function pluginDir() {
  const value = argValue('plugin-dir') || process.env.STT_PLUGIN_DIR || '';
  if (value) return path.resolve(value);
  return path.resolve(BRIDGE_DIR, '..', '..', 'anthropic_stt');
}

function recordError(dir, kind, detail) {
  const rec = {
    ts: new Date().toISOString(),
    kind: String(kind || 'bridge-error'),
    detail: String(detail || '').slice(0, 300),
  };
  try {
    fs.writeFileSync(path.join(dir, 'last_error.json'), JSON.stringify(rec, null, 2) + '\n', 'utf8');
  } catch (_) {}
  console.error(LOG, rec.kind, rec.detail);
}

function createServer(options = {}) {
  const dir = options.dir || pluginDir();
  const config = options.config || loadConfig(dir, { tokenAuthority: options.tokenAuthority }).config;
  const port = Number(options.port || process.env.STT_BRIDGE_PORT || process.env.ANTHROPIC_STT_PORT || config.port || PORT);
  // Staging never ships generated/, and a stale generated file is why the
  // extension used to start without a token. Regenerate on every daemon boot.
  try {
    build({ dir, config, persist: options.persist !== false, tokenAuthority: options.tokenAuthority, out: options.out });
    // Chrome registers unpacked extensions by absolute path: the registration
    // must point at stable app-data, never at the moving source tree.
    sync({
      dir,
      config,
      persist: options.persist !== false,
      tokenAuthority: options.tokenAuthority,
      targetDir: options.syncTarget,
      log: console,
    });
  } catch (err) {
    console.error(LOG, 'could not regenerate or sync the extension config:', String(err));
  }
  const relay = new Relay({ token: config.relayToken, port, log: console });
  relay.config = config;
  let closing = false;

  function shutdown() {
    if (closing) return;
    closing = true;
    relay.close();
    setImmediate(() => {
      if (typeof server.closeAllConnections === 'function') server.closeAllConnections();
    });
    server.close(() => {
      if (options.exitOnShutdown) process.exit(0);
    });
    if (options.exitOnShutdown) setTimeout(() => process.exit(0), 1000).unref();
  }

  const server = http.createServer(async (req, res) => {
    req.resume();
    // The Plugins page writes config.json while the daemon may already be
    // running, so the declared knobs are re-read per request instead of being
    // frozen at startup. A settings change also refreshes the generated file.
    if (!options.config) {
      const fresh = loadConfig(dir, { persist: false }).config;
      // One daemon serves all platforms: the owning plugin is carried on
      // every request, so a switch never inherits the first plugin's
      // process-wide descriptor (C-PARITY-1).
      const requested = new URL(req.url, 'http://127.0.0.1').searchParams.get('platform');
      const urlKeys = { claude: 'claudeUrl', gemini: 'geminiUrl', chatgpt: 'chatgptUrl' };
      if (requested && urlKeys[requested]) {
        fresh.platform = requested;
        fresh.url = String(fresh[urlKeys[requested]] || fresh.url);
      }
      relay.config = fresh;
      try {
        build({ dir, config: fresh, persist: false, tokenAuthority: options.tokenAuthority, out: options.out });
        sync({
          dir,
          config: fresh,
          persist: false,
          tokenAuthority: options.tokenAuthority,
          targetDir: options.syncTarget,
          log: console,
        });
      } catch (_) {}
    }
    // The Python client sends no Origin. A browser page always does, and must
    // not be able to drive the control plane just because it is on loopback.
    if (Object.prototype.hasOwnProperty.call(req.headers, 'origin')) {
      res.writeHead(403, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'forbidden', kind: 'forbidden' }));
      return;
    }
    let result;
    try {
      const requestUrl = new URL(req.url, 'http://127.0.0.1');
      const { pathname } = requestUrl;
      result = await handle(relay, req.method, pathname);
    } catch (err) {
      result = {
        status: 500,
        body: { error: String((err && err.message) || err).slice(0, 200), kind: 'bridge-error' },
      };
    }
    res.writeHead(result.status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(result.body));
    for (const line of result.logs || []) console.log(`${LOG} ${line}`);
    if (result.record) recordError(dir, result.record.kind, result.record.detail);
    else if (result.status >= 500 && result.body && result.body.kind) {
      recordError(dir, result.body.kind, result.body.error);
    }
    // Cleanup stays off the request path: the transcript is already answered
    // and the next start verifies a clean box anyway.
    if (result.cleanup) {
      setTimeout(() => {
        relay
          .request('clean', { platform: relay.config.platform })
          .then((cleaned) => {
            if (cleaned && cleaned.cleaned === false) {
              recordError(dir, 'cleanup-failed', 'the prompt box still had text after New chat');
            }
          })
          .catch(() => {});
      }, 0);
    }
    if (result.shutdown) shutdown();
  });

  relay.attach(server);
  return { server, relay, config, shutdown };
}

if (require.main === module) {
  const migrated = installPaths.migrateProfile();
  if (migrated.moved) console.log(`${LOG} migrated dictation profile to ${migrated.to}`);
  else if (migrated.blocked) {
    console.warn(`${LOG} dictation profile is still at the old path; close its Chrome window to finish the rename`);
  }
  const dir = pluginDir();
  const config = loadConfig(dir).config;
  const port = Number(process.env.STT_BRIDGE_PORT || process.env.ANTHROPIC_STT_PORT || config.port || PORT);
  const app = createServer({ exitOnShutdown: true, dir, config, port });
  app.server.listen(port, '127.0.0.1', () =>
    console.log(`${LOG} listening on 127.0.0.1:${port} (platform=${config.platform})`),
  );
  process.on('SIGINT', app.shutdown);
  process.on('SIGTERM', app.shutdown);
  installParentWatch({ onGone: app.shutdown });
}

module.exports = { createServer, pluginDir, recordError, BRIDGE_DIR };
