'use strict';

// Pure request handling for the daemon: no http objects, no I/O beyond the
// relay. run.js owns sockets, files and process lifecycle. Shapes here are the
// contract plugin.py consumes.

function failure(err) {
  const kind = err && err.kind ? err.kind : 'bridge-error';
  const message = String((err && err.message) || err || 'bridge error').slice(0, 200);
  return { status: 500, body: { error: message, kind } };
}

async function snapshot(relay) {
  const browser = relay.browserState();
  if (browser !== 'connected') {
    return {
      recording: false,
      has_text: false,
      state: 'no-page',
      browser,
      page: 'unknown',
      url: '',
    };
  }
  try {
    const status = await relay.request('status');
    return {
      recording: !!relay.recording,
      has_text: !!status.has_text,
      state: status.recording ? 'recording' : 'idle',
      browser,
      page: status.page || 'unknown',
      url: status.url || '',
    };
  } catch (_) {
    // A reachable extension whose tab is gone still has a transport state;
    // the page reading is what is missing, so it is never guessed.
    return {
      recording: !!relay.recording,
      has_text: false,
      state: 'unknown',
      browser,
      page: 'unknown',
      url: '',
    };
  }
}

async function handle(relay, method, pathname) {
  const cfg = relay.config || {};

  if (method === 'GET' && pathname === '/status') {
    return { status: 200, body: await snapshot(relay) };
  }

  // The Python side owns the "open the profile if it is closed" decision, so
  // it asks here instead of duplicating the config layering. Only the two
  // browser knobs leave; the relay token never does.
  if (method === 'GET' && pathname === '/config') {
    return {
      status: 200,
      body: {
        profileDir: String(cfg.profileDir || ''),
        claudeUrl: String(cfg.claudeUrl || ''),
      },
    };
  }

  // Selecting the plugin probes the bridge. The browser can only be opened by
  // the owner now, so a missing extension is reported instead of launched.
  if (method === 'POST' && pathname === '/warm') {
    if (relay.browserState() !== 'connected') {
      return {
        status: 500,
        body: { error: 'the Claude browser extension is not connected', kind: 'browser-not-open' },
      };
    }
    const body = await snapshot(relay);
    return {
      status: 200,
      body: { ok: true, browser: body.browser, page: body.page, url: body.url, state: body.state },
    };
  }

  if (method === 'POST' && pathname === '/start') {
    if (relay.recording) return { status: 200, body: { ok: true, already: true } };
    const started = Date.now();
    try {
      await relay.request('start', {
        claudeUrl: cfg.claudeUrl,
        startTimeoutMs: cfg.startTimeoutMs,
        pollMs: cfg.pollMs,
      });
      relay.setRecording(true);
      return {
        status: 200,
        body: { ok: true },
        logs: [`timing: start-ack=${Date.now() - started}ms`],
      };
    } catch (err) {
      return failure(err);
    }
  }

  if (method === 'POST' && pathname === '/stop') {
    if (!relay.recording) return { status: 409, body: { error: 'not-recording' } };
    try {
      const result = await relay.request('stop', {
        pollMs: cfg.pollMs,
        stableMs: cfg.stableMs,
        stableWindows: cfg.stableWindows,
        timeoutMs: cfg.timeoutMs,
      });
      const text = String(result.text || '').trim();
      const autoStopped = !!result.auto_stopped;
      const started = relay.startTs || Date.now();
      const clickMs = Number(result.click_ms) || 0;
      const scrapeMs = Number(result.scrape_ms) || 0;
      const total = clickMs + scrapeMs;
      relay.setRecording(false);
      const out = {
        status: 200,
        body: {
          text,
          duration_s: Math.max(0, (Date.now() - started) / 1000),
          auto_stopped: autoStopped,
          state: result.state || 'unknown',
          scrape_ms: total,
        },
        cleanup: true,
        logs: [
          `timing: click=${clickMs}ms scrape=${scrapeMs}ms total=${total}ms state=${result.state || 'unknown'} control=${result.control || 'none'} committed=${result.committed === true}`,
        ],
      };
      if (!text) {
        out.record = {
          kind: autoStopped ? 'no-transcript-after-auto-stop' : 'no-transcript',
          detail: autoStopped
            ? 'the platform stopped recording and sent no transcript'
            : 'no transcript appeared before the timeout',
        };
      }
      return out;
    } catch (err) {
      relay.setRecording(false);
      return failure(err);
    }
  }

  // Clear the prompt box after a delivered transcript (best effort: the text
  // is already in the user's app, so a failure here is cosmetic).
  if (method === 'POST' && pathname === '/clear') {
    if (relay.browserState() !== 'connected') {
      return { status: 200, body: { cleared: false, reason: 'browser-not-open' } };
    }
    try {
      const result = await relay.request('clear');
      return { status: 200, body: { cleared: !!result.cleared, reason: result.reason || '' } };
    } catch (err) {
      return { status: 200, body: { cleared: false, reason: String(err && err.message).slice(0, 80) } };
    }
  }

  if (method === 'POST' && pathname === '/cancel') {
    relay.setRecording(false);
    if (relay.browserState() === 'connected') {
      try {
        await relay.request('cancel');
      } catch (_) {}
    }
    return { status: 200, body: { ok: true } };
  }

  if (method === 'POST' && pathname === '/probe') {
    try {
      return { status: 200, body: await relay.request('probe') };
    } catch (err) {
      return failure(err);
    }
  }

  if (method === 'POST' && pathname === '/shutdown') {
    return { status: 200, body: { ok: true }, shutdown: true };
  }

  return { status: 404, body: { error: 'unknown' } };
}

module.exports = { handle };
