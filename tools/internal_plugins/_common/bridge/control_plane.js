'use strict';

// Pure request handling for the shared bridge: no http objects, no I/O beyond
// the relay. Every command is scoped to the owning plugin's platform; a
// connection belonging to the OTHER tab can never drive this plugin.

const paths = require('./install_paths');
const PLATFORM_NAMES = { claude: 'Claude', gemini: 'Gemini', chatgpt: 'ChatGPT' };

function failure(err) {
  const kind = err && err.kind ? err.kind : 'bridge-error';
  const message = String((err && err.message) || err || 'bridge error').slice(0, 200);
  return { status: 500, body: { error: message, kind } };
}

// A stop can land while the tab is reloading after the start (a "New chat"
// navigation re-injects the content script). That is transient, not a lost
// capture: retry against the SAME recording before giving up.
const STOP_RETRY_DELAYS_MS = [400, 1000];

function wait(relay, ms) {
  return relay.wait ? relay.wait(ms) : new Promise((resolve) => setTimeout(resolve, ms));
}

async function stopRequest(relay, opts) {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await relay.request('stop', opts);
    } catch (err) {
      if (err && err.kind === 'page-not-ready' && attempt < STOP_RETRY_DELAYS_MS.length) {
        await wait(relay, STOP_RETRY_DELAYS_MS[attempt]);
        continue;
      }
      throw err;
    }
  }
}

function platformOf(relay) {
  return String((relay.config && relay.config.platform) || 'claude');
}

function platformError(relay) {
  return {
    status: 500,
    body: {
      error: `the connected tab is not a ${PLATFORM_NAMES[platformOf(relay)] || platformOf(relay)} tab`,
      kind: 'wrong-platform',
    },
  };
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
      hasTab: false,
      platform: platformOf(relay),
      url: '',
      installPath: paths.stableExtensionDir(),
      installHint: paths.INSTALL_HINT,
    };
  }
  try {
    const status = await relay.request('status', { platform: platformOf(relay) });
    if (status.platform && status.platform !== platformOf(relay)) {
      return {
        recording: false,
        has_text: false,
        state: 'wrong-platform',
        browser,
        page: 'unknown',
        hasTab: false,
        platform: status.platform,
        url: status.url || '',
      };
    }
    return {
      recording: !!relay.recording,
      has_text: !!status.has_text,
      state: status.recording ? 'recording' : 'idle',
      browser,
      page: status.page || 'unknown',
      hasTab: status.has_tab !== false,
      micCount: Number(status.micCount) || 0,
      selectorsReady: status.selectorsReady === true,
      platform: platformOf(relay),
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
      hasTab: false,
      platform: platformOf(relay),
      url: '',
    };
  }
}

async function handle(relay, method, pathname) {
  const cfg = relay.config || {};
  const platform = platformOf(relay);
  const scoped = (extra = {}) => ({ platform, ...extra });

  if (method === 'GET' && pathname === '/status') {
    return { status: 200, body: await snapshot(relay) };
  }

  // The Python side owns the "open the profile if it is closed" decision, so
  // it asks here instead of duplicating the config layering. Only the browser
  // knobs leave; the relay token never does.
  if (method === 'GET' && pathname === '/config') {
    return {
      status: 200,
      body: {
        platform,
        profileDir: String(cfg.profileDir || ''),
        url: String(cfg.url || ''),
        claudeUrl: String(cfg.claudeUrl || ''),
        geminiUrl: String(cfg.geminiUrl || ''),
        chatgptUrl: String(cfg.chatgptUrl || ''),
      },
    };
  }

  // Selecting a plugin probes the bridge. The browser can only be opened by
  // the owner now, so a missing extension is reported instead of launched.
  if (method === 'POST' && pathname === '/warm') {
    if (relay.browserState() !== 'connected') {
      return {
        status: 500,
        body: {
          error: `the ${PLATFORM_NAMES[platform] || platform} browser extension is not connected`,
          kind: 'browser-not-open',
          installPath: paths.stableExtensionDir(),
          installHint: paths.INSTALL_HINT,
        },
      };
    }
    const body = await snapshot(relay);
    if (body.state === 'wrong-platform') return platformError(relay);
    return {
      status: 200,
      body: { ok: true, browser: body.browser, page: body.page, platform: body.platform, url: body.url, state: body.state },
    };
  }

  // Resolve or recreate this platform's tab BEFORE /start. The extension owns
  // tab identity; the daemon only sequences the request. Safe to repeat: it is
  // a URL-pattern lookup first and creates only when no match exists.
  if (method === 'POST' && pathname === '/ensure-tab') {
    try {
      const result = await relay.request('ensure-tab', scoped({ url: cfg.url }));
      return { status: 200, body: { ok: true, ...result } };
    } catch (err) {
      return failure(err);
    }
  }

  if (method === 'POST' && pathname === '/start') {
    if (relay.recording) return { status: 200, body: { ok: true, already: true } };
    const started = Date.now();
    try {
      await relay.request('start', scoped({
        url: cfg.url,
        startTimeoutMs: cfg.startTimeoutMs,
        pollMs: cfg.pollMs,
      }));
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
      const result = await stopRequest(relay, scoped({
        pollMs: cfg.pollMs,
        stableMs: cfg.stableMs,
        stableWindows: cfg.stableWindows,
        timeoutMs: cfg.timeoutMs,
      }));
      if (result.platform && result.platform !== platform) return platformError(relay);
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
          state_after: result.state_after || 'unknown',
          empty_reason: result.reason || 'unknown',
          click_ms: clickMs,
          scrape_ms: scrapeMs,
        },
        cleanup: true,
        logs: [
          `timing: click=${clickMs}ms scrape=${scrapeMs}ms total=${total}ms state=${result.state || 'unknown'} state_after=${result.state_after || 'unknown'} reason=${result.reason || 'unknown'} control=${result.control || 'none'} committed=${result.committed === true}`,
        ],
      };
      if (!text) {
        const reason = result.reason || 'timeout_empty';
        const stoppedWithNoText = reason === 'empty_after_stop' || reason === 'no_text';
        out.record = {
          kind: stoppedWithNoText
            ? 'no-text-after-stop'
            : autoStopped
              ? 'no-transcript-after-auto-stop'
              : 'no-transcript',
          detail: stoppedWithNoText
            ? 'the platform stopped recording without producing a transcript'
            : reason === 'timeout_empty'
              ? 'no transcript appeared before the timeout'
              : 'the transcript did not stabilise before the timeout',
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
      const result = await relay.request('clear', scoped());
      return { status: 200, body: { cleared: !!result.cleared, reason: result.reason || '' } };
    } catch (err) {
      return { status: 200, body: { cleared: false, reason: String(err && err.message).slice(0, 80) } };
    }
  }

  if (method === 'POST' && pathname === '/cancel') {
    relay.setRecording(false);
    if (relay.browserState() === 'connected') {
      try {
        await relay.request('cancel', scoped());
      } catch (_) {}
    }
    return { status: 200, body: { ok: true } };
  }

  if (method === 'POST' && pathname === '/probe') {
    try {
      return { status: 200, body: await relay.request('probe', scoped()) };
    } catch (err) {
      return failure(err);
    }
  }

  if (method === 'POST' && pathname === '/shutdown') {
    return { status: 200, body: { ok: true }, shutdown: true };
  }

  return { status: 404, body: { error: 'unknown' } };
}

module.exports = { handle, platformOf, PLATFORM_NAMES };
