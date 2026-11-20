'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { Relay, BridgeError, WebSocket } = require('../relay');

const TOKEN = 'test-token';
const ORIGIN = 'chrome-extension://abcdefghijklmnopabcdefghijklmnop';

function startRelay(options = {}, t) {
  return new Promise((resolve) => {
    const server = http.createServer();
    const relay = new Relay({ token: TOKEN, log: { log() {}, warn() {} }, ...options });
    relay.attach(server);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      const clients = [];
      t.after(async () => {
        for (const client of clients) {
          try {
            client.ws.terminate();
          } catch (_) {}
        }
        relay.close();
        await new Promise((done) => server.close(done));
      });
      resolve({
        server,
        relay,
        clients,
        url: `ws://127.0.0.1:${port}/extension`,
      });
    });
  });
}

function fakeClient(url, options = {}) {
  const ws = new WebSocket(url, {
    origin: options.origin === undefined ? ORIGIN : options.origin,
  });
  const messages = [];
  const waiters = [];
  const closed = new Promise((resolve) => ws.once('close', (code) => resolve(code)));
  ws.on('message', (raw) => {
    let msg;
    try {
      msg = JSON.parse(raw.toString());
    } catch (_) {
      return;
    }
    messages.push(msg);
    for (let i = waiters.length - 1; i >= 0; i -= 1) {
      if (waiters[i].predicate(msg)) {
        const waiter = waiters.splice(i, 1)[0];
        clearTimeout(waiter.timer);
        waiter.resolve(msg);
      }
    }
  });
  ws.on('error', () => {});
  const opened = new Promise((resolve, reject) => {
    ws.once('open', resolve);
    ws.once('error', reject);
  });
  const waitFor = (predicate, timeout = 1500) =>
    new Promise((resolve, reject) => {
      const found = messages.find(predicate);
      if (found) {
        resolve(found);
        return;
      }
      const timer = setTimeout(() => reject(new Error('no matching message')), timeout);
      waiters.push({ predicate, resolve, timer });
    });
  return { ws, messages, opened, closed, waitFor };
}

async function acceptedClient(ctx, token = TOKEN) {
  const client = fakeClient(ctx.url);
  ctx.clients.push(client);
  await client.opened;
  client.ws.send(JSON.stringify({ hello: 1, token, version: '1' }));
  const hello = await client.waitFor((msg) => msg.hello === 1);
  assert.equal(hello.ok, true);
  return client;
}

test('accepts an extension origin with the right token', async (t) => {
  const ctx = await startRelay({}, t);
  await acceptedClient(ctx);
  assert.equal(ctx.relay.browserState(), 'connected');
});

test('rejects a wrong token with 1008 and dispatches nothing', async (t) => {
  const ctx = await startRelay({}, t);
  const client = fakeClient(ctx.url);
  ctx.clients.push(client);
  await client.opened;
  client.ws.send(JSON.stringify({ hello: 1, token: 'wrong', version: '1' }));
  assert.equal(await client.closed, 1008);
  assert.deepEqual(
    client.messages.filter((msg) => msg.id),
    [],
  );
  assert.equal(ctx.relay.browserState(), 'disconnected');
});

test('rejects a non-extension origin with 1008', async (t) => {
  const ctx = await startRelay({}, t);
  const client = fakeClient(ctx.url, { origin: 'https://evil.example' });
  ctx.clients.push(client);
  assert.equal(await client.closed, 1008);
  assert.equal(ctx.relay.browserState(), 'disconnected');
});

test('rejects a bad first frame with 1008', async (t) => {
  const ctx = await startRelay({}, t);
  const client = fakeClient(ctx.url);
  ctx.clients.push(client);
  await client.opened;
  client.ws.send(JSON.stringify({ cmd: 'status' }));
  assert.equal(await client.closed, 1008);
  assert.deepEqual(
    client.messages.filter((msg) => msg.id),
    [],
  );
});

test('correlates a command with its reply', async (t) => {
  const ctx = await startRelay({}, t);
  const client = await acceptedClient(ctx);
  const pending = ctx.relay.request('status');
  const command = await client.waitFor((msg) => msg.cmd === 'status');
  client.ws.send(JSON.stringify({ id: command.id, ok: true, result: { page: 'ok' } }));
  assert.deepEqual(await pending, { page: 'ok' });
});

test('a silent client fails its command with bridge-timeout', async (t) => {
  const ctx = await startRelay({ deadlines: { status: 40 } }, t);
  await acceptedClient(ctx);
  await assert.rejects(ctx.relay.request('status'), (err) => {
    assert.ok(err instanceof BridgeError);
    assert.equal(err.kind, 'bridge-timeout');
    return true;
  });
});

test('a client disconnect fails the pending command with browser-not-open', async (t) => {
  const ctx = await startRelay({}, t);
  const client = await acceptedClient(ctx);
  const pending = ctx.relay.request('status');
  await client.waitFor((msg) => msg.cmd === 'status');
  client.ws.close();
  await assert.rejects(pending, (err) => {
    assert.equal(err.kind, 'browser-not-open');
    return true;
  });
  assert.equal(ctx.relay.browserState(), 'disconnected');
  assert.equal(ctx.relay.recording, false);
});

test('ping is answered with pong and keeps the client registered', async (t) => {
  const ctx = await startRelay({}, t);
  const client = await acceptedClient(ctx);
  client.ws.send(JSON.stringify({ ping: 1 }));
  await client.waitFor((msg) => msg.pong === 1);
  assert.equal(ctx.relay.browserState(), 'connected');
});

test('a second extension connection replaces the first', async (t) => {
  const ctx = await startRelay({}, t);
  const first = await acceptedClient(ctx);
  const second = await acceptedClient(ctx);
  assert.equal(await first.closed, 1000);
  const pending = ctx.relay.request('status');
  const command = await second.waitFor((msg) => msg.cmd === 'status');
  second.ws.send(JSON.stringify({ id: command.id, ok: true, result: { page: 'ok' } }));
  assert.deepEqual(await pending, { page: 'ok' });
});
