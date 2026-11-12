#!/usr/bin/env node
'use strict';

// Wiring only: config -> relay -> HTTP control plane. The profile is started
// by the Python side (chrome_profile.py, plain flags only); nothing here
// watches or drives the browser window.

const http = require('http');
const fs = require('fs');
const path = require('path');
const { loadConfig } = require('./config_store');
const { Relay } = require('./relay');
const { handle } = require('./control_plane');

const HERE = __dirname;

function recordError(dir, kind, detail) {
  const rec = {
    ts: new Date().toISOString(),
    kind: String(kind || 'bridge-error'),
    detail: String(detail || '').slice(0, 300),
  };
  try {
    fs.writeFileSync(path.join(dir, 'last_error.json'), JSON.stringify(rec, null, 2) + '\n', 'utf8');
  } catch (_) {}
  console.error('[anthropic-stt]', rec.kind, rec.detail);
}

function createServer(options = {}) {
  const dir = options.dir || HERE;
  const config = options.config || loadConfig(dir).config;
  const port = Number(process.env.ANTHROPIC_STT_PORT || 17875);
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
    // The Plugins page writes settings.json while the daemon may already be
    // running, so the five declared knobs are re-read per request instead of
    // being frozen at startup.
    if (!options.config) relay.config = loadConfig(dir, { persist: false }).config;
    // The Python client sends no Origin. A browser page always does, and must
    // not be able to drive the control plane just because it is on loopback.
    if (Object.prototype.hasOwnProperty.call(req.headers, 'origin')) {
      res.writeHead(403, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'forbidden', kind: 'forbidden' }));
      return;
    }
    let result;
    try {
      const { pathname } = new URL(req.url, 'http://127.0.0.1');
      result = await handle(relay, req.method, pathname);
    } catch (err) {
      result = {
        status: 500,
        body: { error: String((err && err.message) || err).slice(0, 200), kind: 'bridge-error' },
      };
    }
    res.writeHead(result.status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(result.body));
    for (const line of result.logs || []) console.log(`[anthropic-stt] ${line}`);
    if (result.record) recordError(dir, result.record.kind, result.record.detail);
    else if (result.status >= 500 && result.body && result.body.kind) {
      recordError(dir, result.body.kind, result.body.error);
    }
    // Cleanup stays off the request path: the transcript is already answered
    // and the next start verifies a clean box anyway.
    if (result.cleanup) {
      setTimeout(() => {
        relay
          .request('clean')
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
  const port = Number(process.env.ANTHROPIC_STT_PORT || 17875);
  const app = createServer({ exitOnShutdown: true });
  app.server.listen(port, '127.0.0.1', () =>
    console.log(`[anthropic-stt] listening on 127.0.0.1:${port}`),
  );
  process.on('SIGINT', app.shutdown);
  process.on('SIGTERM', app.shutdown);
}

module.exports = { createServer, recordError };
