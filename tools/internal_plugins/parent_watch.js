'use strict';

// Shared host-liveness watch for the internal-plugin Node daemons. The Rust
// host forwards its PID to every long-lived child; a daemon that outlives the
// host would keep the browser bridge alive with no UI to stop it.
const PARENT_PID_ENV_VAR = 'VOICE_TYPER_PARENT_PID';
const POLL_INTERVAL_MS = 5000;

function parentPidFromEnv(env) {
  const raw = Number(env[PARENT_PID_ENV_VAR]);
  return Number.isInteger(raw) && raw > 0 ? raw : null;
}

function isParentAlive(pid, kill) {
  try {
    kill(pid, 0);
    return true;
  } catch (err) {
    // EPERM means the pid exists but cannot be signalled: stay alive.
    // Only ESRCH proves it is gone.
    return !(err && err.code === 'ESRCH');
  }
}

function installParentWatch({
  onGone,
  env = process.env,
  intervalMs = POLL_INTERVAL_MS,
  kill = (pid, signal) => process.kill(pid, signal),
  setIntervalFn = setInterval,
  clearIntervalFn = clearInterval,
}) {
  const pid = parentPidFromEnv(env);
  if (pid === null) return null;
  const timer = setIntervalFn(() => {
    if (isParentAlive(pid, kill)) return;
    clearIntervalFn(timer);
    onGone();
  }, intervalMs);
  if (typeof timer.unref === 'function') timer.unref();
  return timer;
}

module.exports = {
  PARENT_PID_ENV_VAR,
  POLL_INTERVAL_MS,
  installParentWatch,
  isParentAlive,
  parentPidFromEnv,
};
