// Phase 0: open the isolated burner-profile Chrome for ONE manual login.
// Resolves `playwright` via NODE_PATH (node-deps live outside the repo).
// Keeps running until Ctrl+C so the owner can log in, grant mic, close,
// relaunch (same command) and confirm the session persists.
const { chromium } = require('playwright');

const PROFILE = 'C:/Users/11/AppData/Local/voice-typer-owner/gemini-profile';
const URL = 'https://gemini.google.com/app';

(async () => {
  // Visible by default (owner must see the window to log in).
  // GEMINI_OFFSCREEN=1 parks it off-screen (Phase 3 posture).
  const args = process.env.GEMINI_OFFSCREEN === '1' ? ['--window-position=32000,32000'] : [];
  const ctx = await chromium.launchPersistentContext(PROFILE, {
    channel: 'chrome',
    chromiumSandbox: true, // omit --no-sandbox: Google flags it (retry per owner)
    headless: false,
    viewport: { width: 1280, height: 800 },
    args,
  });
  await ctx.grantPermissions(['microphone'], { origin: 'https://gemini.google.com' });
  const page = ctx.pages()[0] || (await ctx.newPage());
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  console.log('Login window open. Log in with the BURNER Gmail, grant mic, then Ctrl+C here.');
  console.log('Relaunch this same command afterwards: still logged in = Phase 0 exit.');
  await new Promise((resolve) => process.on('SIGINT', resolve));
  await ctx.close();
})().catch((err) => {
  console.error('login.js failed:', err.message);
  process.exit(1);
});
