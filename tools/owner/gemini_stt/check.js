// One-shot handoff check: can Playwright use the manually-logged-in session?
// Prints final URL + title; closes. Exit 0 = reached Gemini app (not accounts).
const { chromium } = require('playwright');

const PROFILE = 'C:/Users/11/AppData/Local/voice-typer-owner/gemini-profile';
const URL = 'https://gemini.google.com/app';

(async () => {
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    channel: 'chrome',
    chromiumSandbox: true,
    headless: true,
  });
  const page = ctx.pages()[0] || (await ctx.newPage());
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(4000);
  const url = page.url();
  const title = await page.title();
  console.log('URL: ' + url);
  console.log('TITLE: ' + title);
  if (url.includes('accounts.google.com')) {
    console.log('RESULT: SIGNED-OUT (redirected to accounts)');
    process.exitCode = 2;
  } else {
    console.log('RESULT: SESSION-ALIVE');
  }
  await ctx.close();
})().catch((err) => {
  console.error('check.js failed:', err.message.split('\n')[0]);
  process.exit(1);
});
