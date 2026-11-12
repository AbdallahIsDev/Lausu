// DOM-diff probe for the platform's own recording signal.
//
// Dumps the composer subtree while idle vs while recording so the waveform
// element (the animated voice bars that replace the prompt box) gets a
// pinned selector. Output is redacted for account identity. Toggles the mic
// once and stops it; no text is typed, nothing is read.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const { micName, stopName, CFG } = require('./playwright_runner.js');

const PROFILE = CFG.profileDir;
const URL = CFG.geminiUrl || 'https://gemini.google.com/app';
const DEBUG = path.join(__dirname, 'debug');

function redact(s) {
  return String(s)
    .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '<burner-email>')
    .replace(/Google Account:[^"<>]*/g, 'Google Account: <burner-name>');
}

async function composerDump(page) {
  return await page.evaluate(() => {
    const box = document.querySelector('[role="textbox"]');
    if (!box) return 'NO-TEXTBOX';
    // Walk up two levels so siblings (waveform host, buttons) are included.
    let host = box;
    for (let i = 0; i < 2 && host.parentElement; i++) host = host.parentElement;
    const scrub = (el) => {
      for (const a of [...el.attributes]) {
        // volatile tokens that would drown a diff in noise
        if (/^(data-.*|aria-describedby|id|jslog|jsname)$/.test(a.name)) el.removeAttribute(a.name);
      }
      for (const kid of el.children) scrub(kid);
    };
    const clone = host.cloneNode(true);
    scrub(clone);
    return clone.outerHTML;
  });
}

(async () => {
  fs.mkdirSync(DEBUG, { recursive: true });
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    channel: 'chrome',
    chromiumSandbox: true,
    headless: false,
    args: ['--window-position=32000,32000', '--window-size=1280,900'],
  });
  try {
    await ctx.grantPermissions(['microphone'], { origin: new globalThis.URL(URL).origin });
    const page = ctx.pages()[0] || (await ctx.newPage());
    await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(4000);
    if (page.url().includes('accounts.google.com')) throw new Error('signed-out');

    fs.writeFileSync(path.join(DEBUG, 'dom-idle.html'), redact(await composerDump(page)));
    console.log('wrote dom-idle.html');

    await page.getByRole('button', { name: micName() }).first().click({ timeout: 15000 });
    await page.waitForTimeout(3000);
    fs.writeFileSync(path.join(DEBUG, 'dom-recording.html'), redact(await composerDump(page)));
    console.log('wrote dom-recording.html');

    await page.getByRole('button', { name: stopName() }).first().click({ timeout: 15000 });
    await page.waitForTimeout(1500);
    console.log('mic toggled back off');
  } finally {
    await ctx.close();
  }
  console.log('DONE');
})().catch((err) => {
  console.error('probe_dom failed:', err.message.split('\n')[0]);
  process.exit(1);
});