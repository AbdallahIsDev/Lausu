'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const diagnostics = require('../diagnostics');
const { handle } = require('../control_plane');
const { compile } = require('../tools/build-extension');

function fakeRelay() {
  return {
    config: { platform: 'claude', url: 'https://claude.ai/new' },
    browserState: () => 'connected',
    async request(cmd) {
      this.lastCommand = cmd;
      return { tabs: [] };
    },
  };
}

function setEnv(flag, frozen) {
  if (flag === undefined) delete process.env[diagnostics.FLAG];
  else process.env[diagnostics.FLAG] = flag;
  if (frozen === undefined) delete process.env[diagnostics.FROZEN_FLAG];
  else process.env[diagnostics.FROZEN_FLAG] = frozen;
}

test('diagnostics are opt-in and refuse in a frozen build', () => {
  setEnv(undefined, undefined);
  assert.equal(diagnostics.enabled(), false);

  setEnv('1', undefined);
  assert.equal(diagnostics.enabled(), true);

  // Frozen simulation: the flag may leak from a dev profile, but a shipped
  // build must still refuse (same standard as C-PLUGIN-4).
  setEnv('1', '1');
  assert.equal(diagnostics.frozen(), true);
  assert.equal(diagnostics.enabled(), false);
});

test('control plane refuses every diagnostics route when disabled or frozen', async () => {
  setEnv(undefined, undefined);
  let result = await handle(fakeRelay(), 'GET', '/diagnostics/tabs-dump');
  assert.equal(result.status, 403);
  assert.equal(result.body.kind, 'diagnostics-disabled');

  setEnv('1', '1');
  result = await handle(fakeRelay(), 'GET', '/diagnostics/tabs-dump');
  assert.equal(result.status, 403);
});

test('control plane serves tabs-dump only with the dev flag', async () => {
  setEnv('1', undefined);
  const relay = fakeRelay();
  const result = await handle(relay, 'GET', '/diagnostics/tabs-dump');
  assert.equal(result.status, 200);
  assert.equal(relay.lastCommand, 'tabs-dump');
  assert.deepEqual(result.body.tabs, []);
  setEnv(undefined, undefined);
});

test('generated extension config carries the gate and hides it in frozen builds', () => {
  setEnv('1', undefined);
  assert.equal(compile({ persist: false }).value.diagnostics, true);
  setEnv('1', '1');
  assert.equal(compile({ persist: false }).value.diagnostics, false);
  setEnv(undefined, undefined);
});
