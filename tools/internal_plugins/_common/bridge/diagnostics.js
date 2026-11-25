'use strict';

// Dev-only diagnostics gate. The opt-in is either an environment variable or
// a local marker file in the plugin workspace (the Tauri host clears most env
// vars on the sidecar spawn boundary). BOTH are rejected in a frozen build,
// so a shipped app can never expose tab dumps or navigation benchmarking.
const fs = require('fs');
const path = require('path');

const FLAG = 'VOICE_TYPER_PLUGIN_DIAGNOSTICS';
const FROZEN_FLAG = 'VOICE_TYPER_FROZEN';
const MARKER = path.join(__dirname, '..', '..', 'DEVELOPER_DIAGNOSTICS');

function frozen(env = process.env) {
  return String(env[FROZEN_FLAG] || '') === '1';
}

function enabled(env = process.env) {
  if (frozen(env)) return false;
  return String(env[FLAG] || '') === '1' || fs.existsSync(MARKER);
}

module.exports = { FLAG, FROZEN_FLAG, MARKER, enabled, frozen };
