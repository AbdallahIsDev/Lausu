'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { createServer } = require('../run');
const { WebSocket } = require('../relay');

const TOKEN = 'roundtrip-token';
const ORIGIN = 'chrome-extension://abcdefghijklmnopabcdefghijklmnop';
const PLUGIN_DIR = path.resolve(__dirname, '..');

function tempPlugin() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'anthropic-stt-roundtrip-'));
  fs.copyFileSync(path.join(PLUGIN_DIR, 'selectors.json'), path.join(dir, 'selectors.json'));
  fs.copyFileSync(path.join(PLUGIN_DIR, 'plugin.json'), path.join(dir, 'plugin.json'));
  fs.writeFileSync(
    path.join(dir, 'config.json'),
    JSON.stringify({
      claudeUrl: 'https://claude.ai/new',
      pollMs: 50,
      stableMs: 100,
      stableWindows: 2,
      startTimeoutMs: 1000,
      timeoutMs: 1000,
      relayToken: TOKEN,
    }),
  );
  return dir;
}

function listen(server) {
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve(server.address().port));
  });
}

function post(base, pathname) {
  return fetch(base + pathname, { method: 'POST' });
}

function waitFor(predicate, timeout = 1500) {
  const deadline = Date.now() + timeout;
  return new Promise((resolve, reject) => {
    const tick = () => {
      if (predicate()) {
        resolve();
        return;
      }
      if (Date.now() >= deadline) {
        reject(new Error('condition was not met in time'));
        return;
      }
      setTimeout(tick, 20);
    };
    tick();
  });
}

test('one full start/stop cycle over a real socket, then a clean shutdown', async (t) => {
  const dir = tempPlugin();
  const app = createServer({ dir });
  const port = await listen(app.server);
  const base = `http://127.0.0.1:${port}`;
  let cleaned = 0;

  const extension = new WebSocket(`ws://127.0.0.1:${port}/extension`, { origin: ORIGIN });
  extension.on('error', () => {});
  t.after(() => {
    try {
      extension.terminate();
    } catch (_) {}
    app.shutdown();
  });

  const messages = [];
  const startOpts = [];
  const stopOpts = [];
  extension.on('message', (raw) => {
    const msg = JSON.parse(raw.toString());
    messages.push(msg);
    if (msg.hello) return;
    let result = {};
    if (msg.cmd === 'start') {
      startOpts.push(msg.opts);
      result = { ok: true };
    }
    if (msg.cmd === 'stop') {
      stopOpts.push(msg.opts);
      result = { text: 'hello world', state: 'auto_stopped', auto_stopped: true, click_ms: 15, scrape_ms: 25 };
    }
    if (msg.cmd === 'clean') {
      cleaned += 1;
      result = { cleaned: true };
    }
    if (msg.cmd === 'status') {
      result = { url: 'https://claude.ai/new', page: 'ok', recording: true, has_text: false };
    }
    extension.send(JSON.stringify({ id: msg.id, ok: true, result }));
  });

  await new Promise((resolve, reject) => {
    extension.once('open', resolve);
    extension.once('error', reject);
  });
  extension.send(JSON.stringify({ hello: 1, token: TOKEN, version: '1' }));
  await waitFor(() => messages.some((msg) => msg.hello === 1 && msg.ok === true));

  const started = await post(base, '/start');
  assert.equal(started.status, 200);
  assert.deepEqual(await started.json(), { ok: true });
  assert.equal(startOpts[0].pollMs, 50);
  // Written while the daemon is already up: the next command must see it.
  fs.writeFileSync(
    path.join(dir, 'settings.json'),
    JSON.stringify({ pollMs: 900, stableMs: 300, stableWindows: 4, timeoutMs: 5000 }),
  );

  const status = await fetch(base + '/status');
  const statusBody = await status.json();
  assert.equal(statusBody.recording, true);
  assert.equal(statusBody.browser, 'connected');
  assert.equal(statusBody.page, 'ok');

  const stopped = await post(base, '/stop');
  assert.equal(stopped.status, 200);
  const stoppedBody = await stopped.json();
  assert.equal(stoppedBody.text, 'hello world');
  assert.equal(stoppedBody.auto_stopped, true);
  assert.equal(stoppedBody.state, 'auto_stopped');
  assert.equal(stoppedBody.scrape_ms, 40);
  assert.equal(typeof stoppedBody.duration_s, 'number');
  assert.deepEqual(stopOpts[0], { pollMs: 900, stableMs: 300, stableWindows: 4, timeoutMs: 5000 });

  await waitFor(() => cleaned === 1);

  const closed = new Promise((resolve) => app.server.once('close', resolve));
  const shutdown = await post(base, '/shutdown');
  assert.equal(shutdown.status, 200);
  assert.deepEqual(await shutdown.json(), { ok: true });
  await closed;
  assert.equal(app.relay.browserState(), 'disconnected');
  await assert.rejects(fetch(base + '/status'));
});

test('a request carrying an Origin header is forbidden', async (t) => {
  const dir = tempPlugin();
  const app = createServer({ dir });
  const port = await listen(app.server);
  t.after(() => app.shutdown());
  const response = await new Promise((resolve, reject) => {
    const req = http.request(
      {
        host: '127.0.0.1',
        port,
        path: '/status',
        headers: { Origin: 'https://evil.example' },
      },
      (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (chunk) => {
          body += chunk;
        });
        res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(body) }));
      },
    );
    req.on('error', reject);
    req.end();
  });
  assert.equal(response.status, 403);
  assert.deepEqual(response.body, { error: 'forbidden', kind: 'forbidden' });
});

test('the HTTP server answers 404 for unknown paths', async (t) => {
  const dir = tempPlugin();
  const app = createServer({ dir });
  const port = await listen(app.server);
  t.after(() => app.shutdown());
  const response = await fetch(`http://127.0.0.1:${port}/nope`);
  assert.equal(response.status, 404);
  assert.deepEqual(await response.json(), { error: 'unknown' });
});
