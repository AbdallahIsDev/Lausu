'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {
  PARENT_PID_ENV_VAR,
  POLL_INTERVAL_MS,
  installParentWatch,
  isParentAlive,
  parentPidFromEnv,
} = require('../../../parent_watch');

const PLUGINS_DIR = path.resolve(__dirname, '..', '..', '..');

test('env contract matches the Python/Rust parent-pid variable', () => {
  assert.equal(PARENT_PID_ENV_VAR, 'VOICE_TYPER_PARENT_PID');
  assert.equal(POLL_INTERVAL_MS, 5000);
});

test('only a positive integer pid enables the watch', () => {
  assert.equal(parentPidFromEnv({ VOICE_TYPER_PARENT_PID: '4242' }), 4242);
  assert.equal(parentPidFromEnv({}), null);
  assert.equal(parentPidFromEnv({ VOICE_TYPER_PARENT_PID: 'abc' }), null);
  assert.equal(parentPidFromEnv({ VOICE_TYPER_PARENT_PID: '0' }), null);
  assert.equal(parentPidFromEnv({ VOICE_TYPER_PARENT_PID: '-5' }), null);
});

test('probe sends signal 0 and fails alive except on ESRCH', () => {
  const signals = [];
  assert.equal(isParentAlive(1, (pid, sig) => signals.push([pid, sig])), true);
  assert.deepEqual(signals, [[1, 0]]);
  assert.equal(isParentAlive(1, () => { throw Object.assign(new Error('gone'), { code: 'ESRCH' }); }), false);
  assert.equal(isParentAlive(1, () => { throw Object.assign(new Error('denied'), { code: 'EPERM' }); }), true);
  assert.equal(isParentAlive(1, () => { throw new Error('unknown'); }), true);
});

test('dead parent fires onGone once, live parent never does, and the timer is unref’d', () => {
  const timer = { unref: () => { unrefCalls += 1; } };
  let unrefCalls = 0;
  function arm({ alive, onGone }) {
    let callback = null;
    let stopped = false;
    let cleared = 0;
    const result = installParentWatch({
      onGone,
      env: { VOICE_TYPER_PARENT_PID: '4242' },
      kill: alive ? () => {} : () => { throw Object.assign(new Error('gone'), { code: 'ESRCH' }); },
      setIntervalFn: (fn) => { callback = fn; return timer; },
      clearIntervalFn: () => { stopped = true; cleared += 1; },
    });
    assert.equal(result, timer);
    return {
      fire: () => { if (!stopped) callback(); },
      clears: () => cleared,
    };
  }

  let gone = 0;
  const noop = arm({ alive: true, onGone: () => {} });
  assert.equal(unrefCalls, 1);
  assert.equal(noop.clears(), 0);

  const dead = arm({ alive: false, onGone: () => { gone += 1; } });
  dead.fire();
  dead.fire();
  assert.equal(gone, 1, 'shutdown must be signalled once, then the timer stops');
  assert.equal(dead.clears(), 1);

  const live = arm({ alive: true, onGone: () => { gone += 1; } });
  live.fire();
  assert.equal(gone, 1, 'a live parent must not shut the daemon down');
  assert.equal(live.clears(), 0);
});

test('no parent pid disables the watch entirely', () => {
  let calls = 0;
  assert.equal(
    installParentWatch({
      onGone: () => {},
      env: {},
      setIntervalFn: () => { calls += 1; return {}; },
    }),
    null,
  );
  assert.equal(calls, 0);
});

test('the one shared daemon installs the parent watch for both plugins', () => {
  const source = fs.readFileSync(path.join(PLUGINS_DIR, '_common', 'bridge', 'run.js'), 'utf8');
  assert.match(source, /installParentWatch\({ onGone: app\.shutdown }\)/,
    'the shared run.js must exit when the host dies');
  for (const plugin of ['anthropic_stt', 'google_stt']) {
    const entry = fs.readFileSync(path.join(PLUGINS_DIR, plugin, 'plugin.py'), 'utf8');
    assert.match(entry, /daemon_script=|_common/,
      `${plugin} must spawn the shared daemon, not its own transport`);
  }
});
