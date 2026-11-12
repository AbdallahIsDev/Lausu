'use strict';

// Loopback bridge between the HTTP control plane and the browser extension.
// The extension lives in the owner's Chrome profile; this side never starts a
// browser. A connection is only accepted after an extension Origin and the
// shared hello token both check out.

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// `ws` lives in the external node-deps folder named by NODE_PATH. Node used to
// append `node_modules` to each NODE_PATH entry; newer releases do not, so both
// layouts are accepted and the app's existing NODE_PATH keeps working.
function loadWs() {
  try {
    return require('ws');
  } catch (_) {}
  const candidates = [];
  for (const entry of String(process.env.NODE_PATH || '').split(path.delimiter)) {
    const root = entry.trim();
    if (!root) continue;
    candidates.push(path.join(root, 'ws'), path.join(root, 'node_modules', 'ws'));
  }
  if (process.env.LOCALAPPDATA) {
    candidates.push(
      path.join(process.env.LOCALAPPDATA, 'voice-typer-internal-plugins', 'node-deps', 'node_modules', 'ws'),
    );
  }
  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) return require(candidate);
    } catch (_) {}
  }
  throw new Error('the ws package is missing; install it into the plugin node-deps folder');
}

const { WebSocketServer, WebSocket } = loadWs();

const PATH = '/extension';
const HANDSHAKE_TIMEOUT_MS = 5000;
const DEADLINES = {
  status: 2000,
  start: 30000,
  stop: 75000,
  cancel: 30000,
  clean: 5000,
  probe: 15000,
};

class BridgeError extends Error {
  constructor(kind, message) {
    super(message);
    this.kind = kind;
  }
}

class Relay {
  constructor({ token, log = console, port = 17875, deadlines = DEADLINES } = {}) {
    this.token = token || '';
    this.log = log;
    this.port = port;
    this.deadlines = deadlines;
    this.wss = new WebSocketServer({ noServer: true, maxPayload: 1024 * 1024 });
    this.server = null;
    this.client = null;
    this.pending = new Map();
    this.recording = false;
    this.startTs = 0;
    this._onUpgrade = this._onUpgrade.bind(this);
  }

  attach(server) {
    this.server = server;
    server.on('upgrade', this._onUpgrade);
  }

  browserState() {
    return this.client && this.client.ws.readyState === WebSocket.OPEN ? 'connected' : 'disconnected';
  }

  setRecording(value) {
    this.recording = !!value;
    this.startTs = this.recording ? Date.now() : 0;
  }

  request(cmd, opts = {}) {
    const client = this.client;
    if (!client || client.ws.readyState !== WebSocket.OPEN) {
      return Promise.reject(
        new BridgeError('browser-not-open', 'the Claude browser extension is not connected'),
      );
    }
    const id = crypto.randomUUID();
    const deadline = this.deadlines[cmd] || 15000;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new BridgeError('bridge-timeout', `${cmd} did not answer within ${deadline} ms`));
      }, deadline);
      this.pending.set(id, { resolve, reject, timer });
      try {
        client.ws.send(JSON.stringify({ id, cmd, opts }));
      } catch (_) {
        clearTimeout(timer);
        this.pending.delete(id);
        reject(new BridgeError('browser-not-open', 'the extension connection dropped'));
      }
    });
  }

  close() {
    this._failPending('browser-not-open', 'the bridge is shutting down');
    if (this.server) this.server.removeListener('upgrade', this._onUpgrade);
    for (const ws of this.wss.clients) {
      try {
        ws.close(1000, 'bridge shutting down');
      } catch (_) {}
    }
    this.client = null;
    this.recording = false;
    this.startTs = 0;
    try {
      this.wss.close();
    } catch (_) {}
  }

  _onUpgrade(req, socket, head) {
    let pathname = '';
    try {
      pathname = new URL(req.url, 'http://127.0.0.1').pathname;
    } catch (_) {
      pathname = '';
    }
    if (pathname !== PATH) {
      socket.destroy();
      return;
    }
    this.wss.handleUpgrade(req, socket, head, (ws) => this._onConnection(ws, req));
  }

  _onConnection(ws, req) {
    const origin = String(req.headers.origin || '');
    const state = { ws, origin, lastSeen: Date.now(), accepted: false };
    if (!origin.startsWith('chrome-extension://')) {
      this._reject(state, 'origin is not a Chrome extension');
      return;
    }
    const handshake = setTimeout(() => this._reject(state, 'no hello frame'), HANDSHAKE_TIMEOUT_MS);
    if (handshake.unref) handshake.unref();
    ws.on('message', (raw) => {
      state.lastSeen = Date.now();
      let msg = null;
      try {
        msg = JSON.parse(raw.toString());
      } catch (_) {
        msg = null;
      }
      if (!state.accepted) {
        const matches =
          msg && msg.hello === 1 && typeof msg.token === 'string' && msg.token === this.token;
        if (!matches) {
          clearTimeout(handshake);
          this._reject(state, 'hello token rejected');
          return;
        }
        clearTimeout(handshake);
        state.accepted = true;
        this._register(state);
        this._send(state, { hello: 1, ok: true });
        return;
      }
      if (msg && msg.ping) {
        this._send(state, { pong: 1 });
        return;
      }
      if (msg && msg.id) this._settle(msg);
    });
    ws.on('close', () => {
      clearTimeout(handshake);
      this._drop(state);
    });
    ws.on('error', () => {});
  }

  _reject(state, reason) {
    this.log.warn(`[anthropic-stt] extension connection refused: ${reason}`);
    try {
      state.ws.close(1008, 'unauthorized');
    } catch (_) {}
  }

  _register(state) {
    const previous = this.client;
    if (previous && previous !== state) {
      this.log.warn('[anthropic-stt] a second extension connection replaced the first');
      this._failPending('browser-not-open', 'another extension window replaced this connection');
      this.client = null;
      try {
        previous.ws.close(1000, 'replaced');
      } catch (_) {}
    }
    this.client = state;
    this.log.log(
      `[anthropic-stt] extension connected (${state.origin}); ` +
        `relay listening on ws://127.0.0.1:${this.port}${PATH}`,
    );
  }

  _settle(msg) {
    const entry = this.pending.get(msg.id);
    if (!entry) return;
    this.pending.delete(msg.id);
    clearTimeout(entry.timer);
    if (msg.ok) entry.resolve(msg.result || {});
    else entry.reject(new BridgeError(msg.kind || 'bridge-error', msg.error || 'extension command failed'));
  }

  _drop(state) {
    if (this.client !== state) return;
    this.client = null;
    this.recording = false;
    this.startTs = 0;
    this._failPending('browser-not-open', 'the Claude browser extension disconnected');
    this.log.warn('[anthropic-stt] extension disconnected');
  }

  _failPending(kind, message) {
    for (const [id, entry] of this.pending) {
      clearTimeout(entry.timer);
      entry.reject(new BridgeError(kind, message));
      this.pending.delete(id);
    }
  }

  _send(state, payload) {
    if (state.ws.readyState !== WebSocket.OPEN) return false;
    try {
      state.ws.send(JSON.stringify(payload));
      return true;
    } catch (_) {
      return false;
    }
  }
}

module.exports = { Relay, BridgeError, DEADLINES, PATH, WebSocket };
