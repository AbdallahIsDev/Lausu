// Phase-1 selector re-verification against the live UI.
//
// Clicks the mic toggle on the burner session and proves the pinned
// selectors still resolve: idle -> recording -> idle. Uses the SAME
// SEL / micName() / stopName() the daemon uses, so this fails the moment
// the daemon would. Headed + parked off-screen (true headless kills the
// mic, same reason as playwright_runner.js).
//
// Snapshots land in debug/ with the account identity redacted. Nothing is
// typed and no transcript is read: this only toggles the mic.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const { SEL, micName, stopName, CFG } = require('./playwright_runner.js');

const PROFILE = CFG.profileDir;
const URL = CFG.geminiUrl || 'https://gemini.google.com/app';
const DEBUG = path.join(__dirname, 'debug');

function redact(s) {
  return String(s)
    .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '<burner-email>')
    .replace(/Google Account:[^"]*/g, 'Google Account: <burner-name>');
}

const results = [];

function check(name, ok, detail) {
  results.push({ name, ok: !!ok });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  -- ' + detail : ''}`);
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

    check('session alive', !page.url().includes('accounts.google.com'), page.url());

    // Idle state: every pinned selector must resolve before any click.
    fs.writeFileSync(
      path.join(DEBUG, 'probe-before-aria.txt'),
      redact(await page.locator('body').ariaSnapshot()),
    );
    const mic = page.getByRole('button', { name: micName() });
    const box = page.getByRole('textbox', { name: /prompt for gemini/i });
    const micIdle = await mic.count();
    const boxCount = await box.count();
    check('micButton resolves while idle', micIdle > 0, `count=${micIdle} pinned="${SEL.micButton}"`);
    check('promptBox resolves', boxCount > 0, `count=${boxCount} pinned="${SEL.promptBox}"`);
    const stopIdle = await page.getByRole('button', { name: stopName() }).count();
    check('recordingIndicator absent while idle', stopIdle === 0, `count=${stopIdle}`);

    // Toggle the mic on: the label must swap (same button, new name).
    await mic.first().click({ timeout: 15000 });
    await page.waitForTimeout(2500);
    fs.writeFileSync(
      path.join(DEBUG, 'probe-after-aria.txt'),
      redact(await page.locator('body').ariaSnapshot()),
    );
    const stop = page.getByRole('button', { name: stopName() });
    const stopCount = await stop.count();
    check('recordingIndicator appears while recording', stopCount > 0, `count=${stopCount} pinned="${SEL.recordingIndicator}"`);
    const micAfter = await page.getByRole('button', { name: micName() }).count();
    check('micButton no longer matches after swap', micAfter === 0, `count=${micAfter}`);

    // Toggle back off: the idle label must return.
    if (stopCount > 0) {
      await stop.first().click({ timeout: 15000 });
      await page.waitForTimeout(2000);
      const back = await page.getByRole('button', { name: micName() }).count();
      check('micButton returns after stop', back > 0, `count=${back}`);
    }
  } finally {
    await ctx.close();
  }

  const failed = results.filter((r) => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exitCode = failed ? 1 : 0;
})().catch((err) => {
  console.error('probe failed:', err.message.split('\n')[0]);
  process.exit(1);
});