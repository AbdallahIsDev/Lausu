// Persistent plugin daemon: one Playwright ctx, HTTP control plane.
// GET /status -> {recording, has_text} | POST /start | POST /stop -> {text}
// Toast + last_error.json + screenshot on break (no transcript in toast).
const http = require('http');
const fs = require('fs');
const path = require('path');
const {
  boot,
  scrapeStable,
  platformRecording,
  recordingState,
  micName,
  stopName,
  composerText,
  newChat,
  ensureCleanComposer,
  CFG,
  SEL,
} = require('./playwright_runner.js');

const PORT = Number(process.env.GOOGLE_STT_PORT || 17874);
const OUT = __dirname;
let ctx = null;
let page = null;
let recording = false;
let startTs = 0;

function fail(kind, detail) {
  const rec = { ts: new Date().toISOString(), kind, detail: String(detail || '').slice(0, 300) };
  try {
    fs.writeFileSync(path.join(OUT, 'last_error.json'), JSON.stringify(rec, null, 2));
  } catch (_) {}
  try {
    if (page) page.screenshot({ path: path.join(OUT, 'debug', 'last-error.png') }).catch(() => {});
  } catch (_) {}
  // No OS popup here: the app-side plugin surfaces errors through the
  // product tray (no standalone popups wanted).
  console.error('[google-stt]', kind, detail);
  return rec;
}

// A non-null page can still be CLOSED (user closed the window, crash, or a
// kill). Treating "non-null" as "alive" left the daemon permanently broken
// after one browser death, failing every later hotkey press with an opaque
// Playwright error — so liveness is checked, and a dead handle is dropped so
// the next call relaunches.
function pageAlive() {
  if (!page || !ctx) return false;
  try {
    return !page.isClosed();
  } catch (_) {
    return false;
  }
}

async function ensure() {
  if (pageAlive()) return;
  if (page || ctx) {
    try {
      if (ctx) await ctx.close();
    } catch (_) {}
    page = null;
    ctx = null;
    console.warn('[google-stt] browser was closed; relaunching on next use');
  }
  const b = await boot();
  ctx = b.ctx;
  page = b.page;
}

async function start() {
  await ensure();
  const loggedOut = page.url().includes('accounts.google.com');
  if (loggedOut) {
    const e = fail('signed-out', page.url());
    throw new Error('signed-out: ' + e.ts);
  }
  // Never record into a dirty box: leftover text would be scraped as if it
  // were dictated. ensureCleanComposer() cleans AND verifies, so a failed
  // cleanup fails the start instead of recording into stale text.
  if (!(await ensureCleanComposer(page))) {
    const e = fail('composer-dirty', 'prompt box still has text after new chat');
    throw new Error('composer-dirty: ' + e.ts);
  }
  const mic = page.getByRole('button', { name: micName() });
  if ((await mic.count()) === 0) {
    const e = fail('mic-missing', 'Dictate button not found');
    throw new Error('mic-missing: ' + e.ts);
  }
  const tStartClick = Date.now();
  await mic.first().click({ timeout: 10000 });
  // Poll for the platform's own signals instead of sleeping a fixed 1.5 s:
  // the label flip and the waveform normally land within ~200-400 ms.
  const budget = Date.now() + (CFG.startTimeoutMs || 3000);
  let started = false;
  while (Date.now() < budget) {
    if ((await recordingState(page)) === 'recording') {
      started = true;
      break;
    }
    await page.waitForTimeout(100);
  }
  if (!started) {
    // Name which signal never arrived: a missing button means the click never
    // registered, a missing waveform means the page is not capturing audio.
    const stopCount = await page.getByRole('button', { name: stopName() }).count();
    const kind = stopCount === 0 ? 'no-recording-indicator' : 'platform-not-recording';
    const detail =
      stopCount === 0
        ? 'Stop dictation did not appear'
        : 'waveform class missing after start click';
    const e = fail(kind, detail);
    throw new Error(kind + ': ' + e.ts);
  }
  console.log(`[google-stt] timing: start-ack=${Date.now() - tStartClick}ms`);
  recording = true;
  startTs = Date.now();
  return { ok: true };
}

async function stop() {
  await ensure();
  // Reconcile with the PLATFORM first, using two independent signals. Our
  // `recording` flag only records what we requested; the waveform class and
  // the toggle's label both report what the page is actually doing. Only
  // their AGREEMENT lets us claim the platform auto-stopped — a single
  // stale signal would otherwise announce an early stop on every session.
  let state = 'not_recording';
  let autoStopped = false;
  if (recording) {
    state = await recordingState(page);
    if (state === 'auto_stopped') autoStopped = true;
    if (state === 'signal_disagreement') {
      console.warn(
        '[google-stt] state-disagreement at stop: waveform and toggle label disagree; ' +
          'not claiming an early stop, letting the transcript decide',
      );
    }
  }
  const T0 = Date.now();
  const stop = page.getByRole('button', { name: stopName() });
  if ((await stop.count()) > 0) {
    await stop.first().click({ timeout: 10000 });
  }
  const tClicked = Date.now();
  recording = false;
  let text = '';
  let scrapeError = null;
  try {
    // No fixed settle after the click: polling starts immediately, and the
    // platform's own "left the recording state" signal ends the wait as soon
    // as the text stops moving.
    text = await scrapeStable(page, { isDone: async () => (await recordingState(page)) !== 'recording' });
  } catch (err) {
    scrapeError = (err.message || String(err)).split('\n')[0];
  }
  const tScraped = Date.now();
  // Cleanup runs AFTER we answer: the plugin does not need a clean box until
  // the next start (which verifies it anyway), and clicking New chat costs
  // ~0.9 s that used to sit on the critical path.
  scheduleCleanup(page);
  if (scrapeError) {
    // Distinguish the two empty cases we can see, so the toast explains
    // instead of just failing. autoStopped + text means the platform cut a
    // long session on its own and still delivered; no text after an
    // auto-stop is the known platform non-transcription failure.
    const kind = autoStopped ? 'no-transcript-after-auto-stop' : 'no-transcript';
    fail(kind, scrapeError);
    text = '';
  }
  const total = Date.now() - T0;
  console.log(
    `[google-stt] timing: click=${tClicked - T0}ms scrape=${tScraped - tClicked}ms total=${total}ms state=${state}`,
  );
  return { text, duration_s: (Date.now() - startTs) / 1000, auto_stopped: autoStopped, state, scrape_ms: tScraped - T0 };
}

// Opens a fresh conversation off the request path so the transcript is handed
// back immediately. A leftover box is still reported, just asynchronously.
function scheduleCleanup(page) {
  setTimeout(async () => {
    try {
      await newChat(page);
      const leftover = await composerText(page);
      if (leftover) fail('cleanup-failed', 'prompt box still dirty after new chat');
    } catch (e) {
      console.warn('[google-stt] background cleanup failed:', (e && e.message) || e);
    }
  }, 0);
}

async function cancel() {
  await ensure();
  recording = false;
  const stop = page.getByRole('button', { name: stopName() });
  if ((await stop.count()) > 0) {
    try {
      await stop.first().click({ timeout: 5000 });
    } catch (_) {}
    await page.waitForTimeout(1200);
  }
  await newChat(page);
  return { ok: true };
}

// Exposes the platform's own reading next to our requested flag, so a stale
// `recording` can never be mistaken for reality when debugging.
async function currentState() {
  if (!recording) return 'idle-by-flag';
  return recordingState(page);
}

// Playwright surfaces a closed page/context/browser as an exception from
// whatever call happened to touch it. Recognise it so the daemon reports the
// real cause ("the browser closed") instead of an opaque internal error.
function isClosedTarget(err) {
  const m = (err && err.message) || String(err || '');
  return /Target page, context or browser has been closed|Target closed|has been closed/i.test(m);
}

const server = http.createServer(async (req, res) => {
  const send = (code, obj) => {
    res.writeHead(code, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(obj));
  };
  try {
    if (req.method === 'GET' && req.url === '/status') {
      return send(200, {
        recording,
        state: page ? await currentState() : 'no-page',
        selectors: SEL,
        visible: CFG.visible !== false,
        promptText: page ? await composerText(page) : '',
      });
    }
    // Activation warm-up: the user selecting this plugin in the app has to
    // open the browser NOW (the `visible` setting decides on-screen vs parked
    // off-screen), instead of waiting for the first hotkey press.
    if (req.method === 'POST' && req.url === '/warm') {
      await ensure();
      return send(200, {
        ok: true,
        visible: CFG.visible !== false,
        url: page ? page.url() : '',
        state: page ? await currentState() : 'no-page',
      });
    }
    if (req.method === 'POST' && req.url === '/start') {
      if (recording) return send(200, { ok: true, already: true });
      return send(200, await start());
    }
    if (req.method === 'POST' && req.url === '/stop') {
      if (!recording) return send(409, { error: 'not-recording' });
      return send(200, await stop());
    }
    if (req.method === 'POST' && req.url === '/cancel') {
      recording = false;
      return send(200, await cancel());
    }
    if (req.method === 'POST' && req.url === '/shutdown') {
      recording = false;
      try {
        if (ctx) await ctx.close();
      } catch (_) {}
      page = null;
      ctx = null;
      send(200, { ok: true });
      server.close();
      setTimeout(() => process.exit(0), 25);
      return;
    }
    return send(404, { error: 'unknown' });
  } catch (err) {
    if (isClosedTarget(err)) {
      // Drop the dead handles so the next request relaunches cleanly.
      page = null;
      ctx = null;
      const msg = 'browser-closed';
      fail('browser-closed', 'the Google STT browser window closed');
      return send(500, { error: msg, kind: 'browser-closed' });
    }
    const msg = (err.message || String(err)).slice(0, 200);
    const known = ['signed-out', 'mic-missing', 'no-recording-indicator', 'platform-not-recording', 'composer-dirty'];
    const kind = known.find((k) => msg.startsWith(k)) || 'bridge-error';
    if (kind === 'bridge-error') fail(kind, msg);
    return send(500, { error: msg, kind });
  }
});

server.listen(PORT, '127.0.0.1', () => console.log('google-stt daemon on 127.0.0.1:' + PORT));
process.on('SIGINT', async () => {
  try {
    if (ctx) await ctx.close();
  } catch (_) {}
  process.exit(0);
});
