'use strict';

// Dev-only diagnostics gate. The flag is an opt-in environment variable and is
// ALSO rejected in a frozen build, so a shipped app can never expose tab dumps
// or navigation benchmarking even if a dev profile carries the flag.
const FLAG = 'VOICE_TYPER_PLUGIN_DIAGNOSTICS';
const FROZEN_FLAG = 'VOICE_TYPER_FROZEN';

function frozen(env = process.env) {
  return String(env[FROZEN_FLAG] || '') === '1';
}

function enabled(env = process.env) {
  return String(env[FLAG] || '') === '1' && !frozen(env);
}

module.exports = { FLAG, FROZEN_FLAG, enabled, frozen };
