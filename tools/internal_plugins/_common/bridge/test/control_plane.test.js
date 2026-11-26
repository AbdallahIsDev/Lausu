'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const { handle } = require('../control_plane');
const { BridgeError } = require('../relay');

function fakeRelay({ browser = 'connected', recording = false, responses = {} } = {}) {
  return {
    recording,
    startTs: recording ? Date.now() - 1500 : 0,
    config: {
      platform: 'claude',
      url: 'https://claude.ai/new',
      claudeUrl: 'https://claude.ai/new',
      geminiUrl: 'https://gemini.google.com/app',
      profileDir: 'C:/Users/11/AppData/Local/voice-typer-internal-plugins/dictation-profile',
      pollMs: 200,
      stableMs: 800,
      stableWindows: 2,
      startTimeoutMs: 5000,
      timeoutMs: 15000,
    },
    browserState() {
      return browser;
    },
    setRecording(value) {
      this.recording = !!value;
      this.startTs = value ? Date.now() : 0;
    },
    async request(cmd, opts) {
      this.lastOpts = opts;
      const response = responses[cmd];
      if (response instanceof Error) throw response;
      return response === undefined ? {} : response;
    },
  };
}

test('GET /status reports the bridge and the page', async () => {
  const relay = fakeRelay({
    responses: {
      status: { url: 'https://claude.ai/new', page: 'ok', recording: true, has_text: true },
    },
  });
  const result = await handle(relay, 'GET', '/status');
  assert.equal(result.status, 200);
  assert.equal(result.body.browser, 'connected');
  assert.equal(result.body.page, 'ok');
  assert.equal(result.body.has_text, true);
  assert.equal(result.body.recording, false);
});

test('GET /status without an extension is 200 with browser disconnected', async () => {
  const result = await handle(fakeRelay({ browser: 'disconnected' }), 'GET', '/status');
  assert.equal(result.status, 200);
  assert.equal(result.body.browser, 'disconnected');
  assert.equal(result.body.page, 'unknown');
  assert.equal(result.body.state, 'no-page');
});

test('GET /config exposes only browser knobs, never the token', async () => {
  const relay = fakeRelay();
  relay.config.profileDir = 'C:/Users/me/AppData/Local/dictation-profile';
  relay.config.relayToken = 'must-not-leak';
  const result = await handle(relay, 'GET', '/config');
  assert.equal(result.status, 200);
  assert.equal(result.body.platform, 'claude');
  assert.equal(result.body.profileDir, 'C:/Users/me/AppData/Local/dictation-profile');
  assert.equal(result.body.url, 'https://claude.ai/new');
  assert.equal(JSON.stringify(result.body).includes('must-not-leak'), false);
  assert.ok(!('visible' in result.body) && !('notify' in result.body));
});

test('a status from the other platform is reported as wrong-platform', async () => {
  const relay = fakeRelay({ responses: { status: { platform: 'gemini', page: 'ok', has_text: false } } });
  const result = await handle(relay, 'GET', '/status');
  assert.equal(result.status, 200);
  assert.equal(result.body.state, 'wrong-platform');
  assert.equal(result.body.platform, 'gemini');
});

test('start is always scoped to the owning platform', async () => {
  const relay = fakeRelay({ responses: { start: { ok: true } } });
  await handle(relay, 'POST', '/start');
  assert.deepEqual(relay.lastOpts, { platform: 'claude', url: 'https://claude.ai/new', startTimeoutMs: 5000, pollMs: 200 });
});

test('POST /ensure-tab resolves a tab for the owning platform', async () => {
  const relay = fakeRelay({ responses: { 'ensure-tab': { tabId: 42, created: false, ready: true } } });
  const result = await handle(relay, 'POST', '/ensure-tab');
  assert.equal(result.status, 200);
  assert.equal(result.body.ok, true);
  assert.deepEqual(relay.lastOpts, { platform: 'claude', url: 'https://claude.ai/new' });
});

test('GET /status reports a missing target tab without inventing a page', async () => {
  const relay = fakeRelay({
    responses: { status: { url: '', page: 'unknown', recording: false, has_text: false, has_tab: false } },
  });
  const result = await handle(relay, 'GET', '/status');
  assert.equal(result.status, 200);
  assert.equal(result.body.hasTab, false);
  assert.equal(result.body.page, 'unknown');
});

test('POST /start returns ok and records the session', async () => {
  const relay = fakeRelay({ responses: { start: { ok: true } } });
  const result = await handle(relay, 'POST', '/start');
  assert.equal(result.status, 200);
  assert.deepEqual(result.body, { ok: true });
  assert.equal(relay.recording, true);
  assert.match(result.logs[0], /^timing: start-ack=\d+ms$/);
});

test('POST /start is idempotent while recording', async () => {
  const result = await handle(fakeRelay({ recording: true }), 'POST', '/start');
  assert.equal(result.status, 200);
  assert.deepEqual(result.body, { ok: true, already: true });
});

test('POST /start with no extension is a 500 envelope with browser-not-open', async () => {
  const relay = fakeRelay({
    responses: { start: new BridgeError('browser-not-open', 'the extension is not connected') },
  });
  const result = await handle(relay, 'POST', '/start');
  assert.equal(result.status, 500);
  assert.deepEqual(result.body, {
    error: 'the extension is not connected',
    kind: 'browser-not-open',
  });
});

test('POST /stop retries a page that is still loading without losing the session', async () => {
  const relay = fakeRelay({ recording: true });
  const attempts = [];
  relay.wait = async () => {};
  relay.request = async (cmd) => {
    attempts.push(cmd);
    if (attempts.length === 1) {
      throw new BridgeError('page-not-ready', 'the target tab is still loading');
    }
    return { text: 'dictated words', state: 'idle', state_after: 'idle' };
  };

  const result = await handle(relay, 'POST', '/stop');

  assert.equal(result.status, 200);
  assert.equal(result.body.text, 'dictated words');
  assert.equal(attempts.length, 2);
  assert.equal(relay.recording, false);
});

test('POST /stop without a recording is 409', async () => {
  const result = await handle(fakeRelay(), 'POST', '/stop');
  assert.equal(result.status, 409);
  assert.deepEqual(result.body, { error: 'not-recording' });
});

test('POST /stop returns the transcript shape and schedules cleanup', async () => {
  const relay = fakeRelay({
    recording: true,
    responses: {
      stop: {
        text: 'hello world',
        state: 'auto_stopped',
        auto_stopped: true,
        click_ms: 15,
        scrape_ms: 25,
      },
    },
  });
  const result = await handle(relay, 'POST', '/stop');
  assert.equal(result.status, 200);
  assert.equal(result.body.text, 'hello world');
  assert.equal(result.body.auto_stopped, true);
  assert.equal(result.body.state, 'auto_stopped');
  assert.equal(typeof result.body.duration_s, 'number');
  assert.equal(result.cleanup, true);
  // Split phases, not a combined total: the Python log prints both.
  assert.equal(result.body.click_ms, 15);
  assert.equal(result.body.scrape_ms, 25);
  assert.match(result.logs[0], /timing: click=15ms scrape=25ms total=40ms/);
  assert.equal(relay.recording, false);
});

test('POST /stop with an empty transcript records the right kind', async () => {
  const relay = fakeRelay({
    recording: true,
    responses: { stop: { text: '', state: 'auto_stopped', auto_stopped: true } },
  });
  const result = await handle(relay, 'POST', '/stop');
  assert.equal(result.status, 200);
  assert.equal(result.body.text, '');
  assert.equal(result.record.kind, 'no-transcript-after-auto-stop');

  const manual = fakeRelay({
    recording: true,
    responses: { stop: { text: '', state: 'not_recording', auto_stopped: false } },
  });
  const manualResult = await handle(manual, 'POST', '/stop');
  assert.equal(manualResult.record.kind, 'no-transcript');
});

test('POST /stop distinguishes "platform stopped, no speech" from a timeout', async () => {
  const relay = fakeRelay({
    recording: true,
    responses: {
      stop: {
        text: '',
        state: 'recording',
        state_after: 'auto_stopped',
        reason: 'empty_after_stop',
        auto_stopped: false,
      },
    },
  });
  const result = await handle(relay, 'POST', '/stop');
  assert.equal(result.body.empty_reason, 'empty_after_stop');
  assert.equal(result.body.state_after, 'auto_stopped');
  assert.equal(result.record.kind, 'no-text-after-stop');
  assert.match(result.record.detail, /stopped recording without producing/);
  assert.match(result.logs[0], /state_after=auto_stopped reason=empty_after_stop/);

  const timedOut = fakeRelay({
    recording: true,
    responses: {
      stop: { text: '', state: 'recording', state_after: 'recording', reason: 'timeout_empty' },
    },
  });
  const timedOutResult = await handle(timedOut, 'POST', '/stop');
  assert.equal(timedOutResult.record.kind, 'no-transcript');
  assert.match(timedOutResult.record.detail, /before the timeout/);
});

test('POST /cancel always answers ok', async () => {
  const connected = fakeRelay({ recording: true, responses: { cancel: { ok: true } } });
  const result = await handle(connected, 'POST', '/cancel');
  assert.equal(result.status, 200);
  assert.deepEqual(result.body, { ok: true });
  assert.equal(connected.recording, false);

  const disconnected = fakeRelay({ browser: 'disconnected' });
  assert.deepEqual((await handle(disconnected, 'POST', '/cancel')).body, { ok: true });
});

test('POST /probe returns checks and dump', async () => {
  const relay = fakeRelay({
    responses: { probe: { checks: [{ name: 'page', ok: true, detail: 'ok' }], dump: '<div></div>' } },
  });
  const result = await handle(relay, 'POST', '/probe');
  assert.equal(result.status, 200);
  assert.equal(result.body.checks[0].name, 'page');
  assert.equal(result.body.dump, '<div></div>');
});

test('POST /probe without an extension is a browser-not-open envelope', async () => {
  const relay = fakeRelay({
    responses: { probe: new BridgeError('browser-not-open', 'not connected') },
  });
  const result = await handle(relay, 'POST', '/probe');
  assert.equal(result.status, 500);
  assert.equal(result.body.kind, 'browser-not-open');
});

test('POST /warm reports the bridge without launching anything', async () => {
  const connected = fakeRelay({
    responses: { status: { url: 'https://claude.ai/new', page: 'ok', recording: false, has_text: false } },
  });
  const warm = await handle(connected, 'POST', '/warm');
  assert.equal(warm.status, 200);
  assert.equal(warm.body.ok, true);
  assert.equal(warm.body.browser, 'connected');

  const missing = await handle(fakeRelay({ browser: 'disconnected' }), 'POST', '/warm');
  assert.equal(missing.status, 500);
  assert.equal(missing.body.kind, 'browser-not-open');
});

test('POST /shutdown asks the wiring layer to close', async () => {
  const result = await handle(fakeRelay(), 'POST', '/shutdown');
  assert.equal(result.status, 200);
  assert.deepEqual(result.body, { ok: true });
  assert.equal(result.shutdown, true);
});

test('unknown paths are 404', async () => {
  const result = await handle(fakeRelay(), 'GET', '/nope');
  assert.equal(result.status, 404);
  assert.deepEqual(result.body, { error: 'unknown' });
});
