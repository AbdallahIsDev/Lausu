// Shared Playwright boot + stable scrape for the Google STT daemon.
// Headed always — true headless kills mic. `visible:false` parks off-screen.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

function loadConfig() {
  const dir = __dirname;
  for (const f of ['config.json', 'config.example.json']) {
    try {
      return JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
    } catch (_) {}
  }
  throw new Error('no config found');
}

const CFG = loadConfig();
const PROFILE = CFG.profileDir;
const URL = CFG.geminiUrl || 'https://gemini.google.com/app';
const SEL = JSON.parse(fs.readFileSync(path.join(__dirname, 'selectors.json'), 'utf8'));
const WAVEFORM_CLASS = (SEL && SEL.waveformClass) || 'dictation-hidden';
const VISIBLE = CFG.visible !== false;
const OUT = __dirname;

function micName() {
  return /Dictate/i;
}
function stopName() {
  return /Stop dictation/i;
}

// Resolve the installed Chrome binary ourselves.
//
// `channel: 'chrome'` makes Playwright look the path up through the
// Windows environment (PROGRAMFILES). The app spawns this daemon with a
// trimmed environment, so that lookup died with:
//   Chromium distribution 'chrome' is not found at undefined\Program Files\...
// Probing the known install locations works whatever the env says.
function chromeExecutable() {
  const candidates = [
    process.env.LUASU_CHROME_PATH,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    process.env.LOCALAPPDATA
      ? path.join(process.env.LOCALAPPDATA, 'Google/Chrome/Application/chrome.exe')
      : '',
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      if (fs.existsSync(candidate)) return candidate;
    } catch (_) {}
  }
  return '';
}
async function boot() {
  const args = VISIBLE ? [] : ['--window-position=32000,32000'];
  const executablePath = chromeExecutable();
  const options = {
    chromiumSandbox: true,
    headless: false,
    viewport: { width: 1280, height: 800 },
    args,
  };
  if (executablePath) options.executablePath = executablePath;
  else options.channel = CFG.chromeChannel || 'chrome';
  const ctx = await chromium.launchPersistentContext(PROFILE, options);
  await ctx.grantPermissions(['microphone'], { origin: 'https://gemini.google.com' });
  const page = ctx.pages()[0] || (await ctx.newPage());
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(4000);
  return { ctx, page };
}

// Transcript scrape: fast by default, still conservative when the text is
// still settling.
//
// The old version polled every `stableMs` (800) and needed two stable windows,
// so even a transcript that was ready in 200 ms cost ~1.6 s of pure waiting.
// Now the first poll interval is short and backs off (200 → 800) while the
// text keeps changing, and `opts.isDone` lets the platform's own "no longer
// recording" signal end the wait early. The stability rule is unchanged:
// the text must repeat across two consecutive reads.
async function scrapeStable(page, opts = {}) {
  const pollMs = opts.pollMs || CFG.pollMs || 200;
  const windows = opts.stableWindows || CFG.stableWindows || 2;
  const timeoutMs = opts.timeoutMs || CFG.timeoutMs || 15000;
  const isDone = opts.isDone || null;
  const deadline = Date.now() + timeoutMs;
  let last = '';
  let stable = 0;
  let wait = pollMs;
  while (Date.now() < deadline) {
    let cur = '';
    try {
      cur = await composerText(page);
    } catch (_) {}
    cur = (cur || '').trim();
    if (cur && cur === last) {
      stable += 1;
      // Two stable reads is enough on its own; `isDone` short-circuits even
      // that when the platform has already left the recording state, which is
      // its own confirmation that the text will not change again.
      if (stable >= windows) return cur;
      if (stable >= 1 && isDone && (await isDone())) return cur;
    } else {
      stable = 0;
      last = cur;
      // Text still moving: give it longer next time (up to the old cadence).
      wait = Math.min(wait * 2, CFG.stableMs || 800);
    }
    await page.waitForTimeout(wait);
  }
  throw new Error('transcript unstable/empty within timeout');
}

async function platformRecording(page) {
  // The platform's own recording signal: while the mic is capturing, the
  // composer wrapper carries the waveform class (discovered by probe_dom.js
  // idle-vs-recording diff; it vanishes the moment capture ends — button
  // click, platform auto-stop, or page crash). This disambiguates "the
  // platform stopped capturing" from "our stop click failed", which the
  // button name alone cannot tell.
  try {
    return await page.evaluate(
      (cls) => {
        const host =
          document.querySelector('.textarea-wrapper') ||
          document.querySelector('[role="textbox"]');
        return !!(host && host.classList && host.classList.contains(cls));
      },
      WAVEFORM_CLASS,
    );
  } catch (_) {
    return false;
  }
}

async function composerText(page) {
  // Live prompt-box text, '' when empty or when only the placeholder shows.
  try {
    return await page.evaluate(() => {
      const box = document.querySelector('[role="textbox"]');
      if (!box) return '';
      const rich = box.querySelector('p');
      if (rich && rich.innerText.trim()) return rich.innerText.trim();
      const t = (box.innerText || box.textContent || '').trim();
      if (/^Ask Gemini\s*$/.test(t)) return '';
      return t.replace(/^Ask Gemini\s*/, '').trim();
    });
  } catch (_) {
    return '';
  }
}

async function clearComposer(page) {
  const box = page.locator('[role="textbox"]').first();
  try {
    await box.click({ timeout: 4000 });
    await box.evaluate((el) => {
      el.focus();
      document.execCommand('selectAll');
      document.execCommand('delete');
    });
    await page.waitForTimeout(500);
  } catch (_) {}
}

async function newChat(page) {
  // The affordance is a LINK in the aria tree (link "New chat"), not a
  // button — matching on role=button silently found nothing (selector kind mismatch).
  const candidates = [
    page.getByRole('link', { name: /New chat/i }),
    page.getByRole('button', { name: /New chat/i }),
    page.getByRole('link', { name: /Start new chat/i }),
  ];
  for (const loc of candidates) {
    try {
      if ((await loc.count()) > 0) {
        await loc.first().click({ timeout: 4000 });
        await page.waitForTimeout(900);
        break;
      }
    } catch (_) {}
  }
  // Fallback: wipe the composer directly if the box is still dirty.
  if (await composerText(page)) await clearComposer(page);
}

async function ensureCleanComposer(page) {
  // Never record into a dirty box: leftover text would be scraped as if it
  // were dictated. Clean, then VERIFY — a failed click must fail the start
  // instead of silently recording into someone else's text. Returns true
  // when the box is verifiably empty.
  if (!(await composerText(page))) return true;
  await newChat(page);
  return !(await composerText(page));
}

// Pure decision table for "is the platform still capturing?" — split out so
// every combination is testable without a browser.
//
// Two independent signals, because one cannot detect its own breakage:
//   wave  = composer wrapper carries the waveform class
//   toggle = which label the mic toggle currently shows
// Agreement decides; disagreement is reported as such and never guessed,
// so a stale waveform token cannot make us falsely announce an early stop.
function classifyRecordingState(wave, stopBtnCount, micBtnCount) {
  const toggleRecording = stopBtnCount > 0;
  const toggleIdle = stopBtnCount === 0 && micBtnCount > 0;
  if (wave && toggleRecording) return 'recording';
  if (!wave && toggleIdle) return 'auto_stopped';
  return 'signal_disagreement';
}

async function recordingState(page) {
  // Live reading of both signals via the platform, not our own flag.
  if (!page) return 'unknown';
  let wave = false;
  try {
    wave = await platformRecording(page);
    const stopCount = await page.getByRole('button', { name: stopName() }).count();
    const micCount = await page.getByRole('button', { name: micName() }).count();
    return classifyRecordingState(wave, stopCount, micCount);
  } catch (_) {
    return 'unknown';
  }
}

module.exports = {
  boot,
  scrapeStable,
  platformRecording,
  recordingState,
  classifyRecordingState,
  micName,
  stopName,
  composerText,
  clearComposer,
  newChat,
  ensureCleanComposer,
  CFG,
  SEL,
  OUT,
};
