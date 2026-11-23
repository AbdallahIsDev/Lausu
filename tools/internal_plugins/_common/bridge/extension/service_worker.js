'use strict';

// MV3 service worker: owns the loopback WebSocket and forwards commands to the
// target tab's content script over a runtime port. Chrome 116+ extends the
// worker's lifetime while WebSocket messages flow, so a 20 s ping is sent for
// as long as a socket is open. The alarms entry is the reconnect backstop for
// the case where Chrome terminated the worker while the daemon was down.

importScripts('generated/config.js', 'tab_resolution.js');

const CFG = self.ANTHROPIC_STT_CONFIG || {};
const { createTabResolver } = self.SttTabResolution;
const RECONNECT_ALARM = 'stt-bridge-reconnect';
const PING_MS = 20000;
const HANDSHAKE_MS = 5000;
const BACKOFF_MS = [1000, 2000, 5000, 10000, 30000];
// A tab that was just opened answers the port before its content script is
// listening (document_idle), so a cold start needs more than one retry.
const TAB_RETRY_MS = [300, 700, 1400];
const TAB_DEADLINES = {
  status: 3000,
  start: 32000,
  stop: 80000,
  cancel: 32000,
  clean: 7000,
  probe: 17000,
};

let socket = null;
let accepted = false;
let backoffIndex = 0;
let reconnectTimer = null;
let pingTimer = null;
let cachedStatus = null;

function send(payload) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return false;
  try {
    socket.send(JSON.stringify(payload));
    return true;
  } catch (_) {
    return false;
  }
}

function clearPing() {
  if (pingTimer) {
    clearInterval(pingTimer);
    pingTimer = null;
  }
}

function startPing() {
  clearPing();
  pingTimer = setInterval(() => {
    if (!send({ ping: 1 })) clearPing();
  }, PING_MS);
}

function ensureAlarm() {
  chrome.alarms.get(RECONNECT_ALARM, (alarm) => {
    if (!alarm) chrome.alarms.create(RECONNECT_ALARM, { periodInMinutes: 0.5 });
  });
}

function clearAlarm() {
  chrome.alarms.clear(RECONNECT_ALARM);
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  const delay = BACKOFF_MS[Math.min(backoffIndex, BACKOFF_MS.length - 1)];
  backoffIndex += 1;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, delay);
  // An alarm outlives the worker. If Chrome tears it down while the daemon is
  // down, the alarm wakes it and the next attempt still happens on schedule.
  ensureAlarm();
}

function connect() {
  if (
    socket &&
    (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }
  if (!CFG.wsUrl || !CFG.token) {
    console.error('[stt-bridge] generated/config.js has no relay token; run tools/build-extension.js');
    return;
  }
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  let ws;
  try {
    ws = new WebSocket(CFG.wsUrl);
  } catch (_) {
    scheduleReconnect();
    return;
  }
  socket = ws;
  accepted = false;
  const handshake = setTimeout(() => {
    if (!accepted) {
      try {
        ws.close();
      } catch (_) {}
    }
  }, HANDSHAKE_MS);

  ws.onopen = () => {
    if (socket !== ws) return;
    send({ hello: 1, token: CFG.token, version: '1' });
  };

  ws.onmessage = (event) => {
    let msg = null;
    try {
      msg = JSON.parse(event.data);
    } catch (_) {
      return;
    }
    if (msg && msg.hello === 1) {
      clearTimeout(handshake);
      if (msg.ok) {
        accepted = true;
        backoffIndex = 0;
        clearAlarm();
        startPing();
        // Seed the popup snapshot the moment the bridge is up, so the popup
        // shows a real state before the first dictation of the session.
        publishSnapshot(cachedStatus || { page: 'unknown', recording: false });
      } else {
        try {
          ws.close();
        } catch (_) {}
      }
      return;
    }
    if (msg && msg.pong) return;
    if (msg && msg.id) handleCommand(msg);
  };

  ws.onclose = (event) => {
    clearTimeout(handshake);
    clearPing();
    if (socket === ws) {
      socket = null;
      accepted = false;
      publishSnapshot({ page: 'unknown', recording: false });
    }
    if (event && event.code === 1008) {
      console.error(
        '[stt-bridge] relay rejected the connection; re-run tools/build-extension.js and reload the extension',
      );
    }
    scheduleReconnect();
  };

  ws.onerror = () => {
    try {
      ws.close();
    } catch (_) {}
  };
}

const TAB_PATTERNS = {
  claude: 'https://claude.ai/*',
  gemini: 'https://gemini.google.com/*',
};
const TARGET_URLS = {
  claude: (CFG.platforms && CFG.platforms.claude && CFG.platforms.claude.claudeUrl) || 'https://claude.ai/new',
  gemini: (CFG.platforms && CFG.platforms.gemini && CFG.platforms.gemini.geminiUrl) || 'https://gemini.google.com/app',
};
// Commands that may legitimately open a missing target tab. status is a read;
// stop/cancel must never create a tab just to answer a command.
const RESOLVING_COMMANDS = new Set(['start', 'probe', 'clean']);

function reply(id, ok, result, kind, error) {
  if (ok) send({ id, ok: true, result: result || {} });
  else send({ id, ok: false, kind: kind || 'bridge-error', error: String(error || '').slice(0, 200) });
}

function attemptTab(tabId, cmd, opts) {
  return new Promise((resolve, reject) => {
    let port;
    try {
      port = chrome.tabs.connect(tabId, { name: 'stt-bridge' });
    } catch (_) {
      reject({ kind: 'page-not-ready', error: 'the target tab is still loading', retry: true });
      return;
    }
    const id = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    let done = false;
    let answered = false;

    function finish(value, failed) {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try {
        port.disconnect();
      } catch (_) {}
      if (failed) reject(value);
      else resolve(value);
    }

    const timer = setTimeout(() => {
      finish({ kind: 'bridge-timeout', error: `the target tab did not answer ${cmd}` }, true);
    }, TAB_DEADLINES[cmd] || 15000);

    port.onMessage.addListener((msg) => {
      if (!msg || msg.id !== id) return;
      answered = true;
      if (msg.ok) finish(msg.result || {}, false);
      else finish({ kind: msg.kind || 'bridge-error', error: msg.error || 'the tab refused the command' }, true);
    });
    port.onDisconnect.addListener(() => {
      void chrome.runtime.lastError;
      if (!done) {
        // A cold-start tab accepts the port before its content script is
        // listening, then closes it. That is not "window closed"; the caller
        // gets one retry instead of a misleading browser-not-open.
        finish(
          { kind: 'page-not-ready', error: 'the target tab is still loading', retry: !answered },
          true,
        );
      }
    });
    try {
      port.postMessage({ id, cmd, opts });
    } catch (_) {
      finish({ kind: 'page-not-ready', error: 'the target tab is still loading', retry: true }, true);
    }
  });
}

async function sendToTab(tabId, cmd, opts) {
  let lastError = null;
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await attemptTab(tabId, cmd, opts);
    } catch (err) {
      lastError = err;
      if (!err || !err.retry || attempt >= TAB_RETRY_MS.length) break;
      await new Promise((resolve) => setTimeout(resolve, TAB_RETRY_MS[attempt]));
    }
  }
  if (lastError && lastError.retry) {
    throw { kind: 'page-not-ready', error: 'the target tab is still loading' };
  }
  throw lastError;
}

let tabResolver = null;
function resolver() {
  if (!tabResolver) {
    tabResolver = createTabResolver({
      chromeApi: chrome,
      patterns: TAB_PATTERNS,
      targetUrls: TARGET_URLS,
      // A created tab answers the port before its content script listens;
      // sendToTab's own retry ladder covers that window.
      probe: async (tabId) => {
        try {
          await sendToTab(tabId, 'status');
          return true;
        } catch (_) {
          return false;
        }
      },
    });
  }
  return tabResolver;
}

function tabFor(platform) {
  return resolver().find(platform);
}

// Resolve on every command, then re-resolve once if the tab vanished between
// resolution and dispatch. That keeps a hotkey press from surfacing
// "the target tab is not open" for a tab the user merely closed.
const { dispatch } = self.SttTabResolution.createDispatcher({
  resolver: { ensure: (platform, opts) => resolver().ensure(platform, opts), find: (platform) => tabFor(platform) },
  sendToTab,
  resolvingCommands: RESOLVING_COMMANDS,
});

// The popup reads this instead of messaging: a status snapshot costs nothing
// and survives the worker being suspended (MV3 keeps the values in storage).
function publishSnapshot(status) {
  try {
    chrome.storage.local.set({
      snapshot: {
        page: (status && status.page) || 'unknown',
        hasTab: !!(status && status.has_tab),
        recording: !!(status && status.recording),
        bridge: !!socket && socket.readyState === WebSocket.OPEN && accepted,
        at: Date.now(),
      },
    });
  } catch (_) {}
}

function handleCommand(msg) {
  (async () => {
    try {
      const platform = (msg.opts && msg.opts.platform) || CFG.platform;
      if (msg.cmd === 'status') {
        const tab = await tabFor(platform);
        if (!tab) {
          // A stale cached page used to make the daemon believe the target
          // tab was alive, so /start was sent to a tab that did not exist.
          const result = {
            url: '',
            page: 'unknown',
            recording: false,
            has_text: false,
            has_tab: false,
          };
          publishSnapshot(result);
          reply(msg.id, true, result);
          return;
        }
        const result = await sendToTab(tab.id, 'status', msg.opts);
        cachedStatus = { ...result, has_tab: true };
        publishSnapshot(cachedStatus);
        reply(msg.id, true, cachedStatus);
        return;
      }
      if (msg.cmd === 'ensure-tab') {
        const resolved = await resolver().ensure(platform, msg.opts);
        if (typeof resolved.tabId !== 'number') {
          reply(msg.id, false, null, 'browser-not-open', resolved.reason === 'create-failed'
            ? 'the extension could not open the target tab'
            : 'the target tab is not open');
          return;
        }
        reply(msg.id, true, {
          ok: true,
          tabId: resolved.tabId,
          created: resolved.created,
          ready: resolved.ready,
          platform,
        });
        return;
      }
      const result = await dispatch(platform, msg.cmd, msg.opts);
      reply(msg.id, true, result);
    } catch (err) {
      reply(
        msg.id,
        false,
        null,
        (err && err.kind) || 'bridge-error',
        (err && (err.error || err.message)) || 'the extension failed',
      );
    }
  })();
}

// The popup cannot ask the daemon directly: its fetch carries an Origin header
// and the daemon's CSRF guard rejects those. Answer from the tab + socket here.
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.type !== 'stt-bridge-popup-status') return false;
  const bridge = !!socket && socket.readyState === WebSocket.OPEN && accepted;
  (async () => {
    try {
      const tab = await tabFor(msg.opts && msg.opts.platform ? msg.opts.platform : CFG.platform);
      if (!tab) {
        sendResponse({ ok: true, bridge, page: 'no-tab', has_tab: false, recording: false });
        return;
      }
      const result = await sendToTab(tab.id, 'status');
      cachedStatus = { ...result, has_tab: true };
      publishSnapshot(cachedStatus);
      sendResponse({
        ok: true,
        bridge,
        page: result.page || 'unknown',
        has_tab: true,
        recording: !!result.recording,
      });
    } catch (err) {
      sendResponse({
        ok: false,
        bridge,
        page: 'unknown',
        recording: false,
        error: String((err && (err.error || err.message)) || err).slice(0, 120),
      });
    }
  })();
  return true; // async response
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === RECONNECT_ALARM) connect();
});
chrome.runtime.onInstalled.addListener(() => connect());
chrome.runtime.onStartup.addListener(() => connect());

connect();
