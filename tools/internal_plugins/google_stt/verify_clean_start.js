// Proves the "clean the prompt box before recording" requirement end to end
// against the live page, using the SAME code the daemon runs
// (ensureCleanComposer from playwright_runner.js — no test copy).
//
// 1. fresh page must be clean
// 2. seed leftover text (what a failed cleanup leaves behind)
// 3. the leftover must be DETECTED
// 4. ensureCleanComposer() must return true
// 5. the box must verify empty afterwards
const { boot, composerText, ensureCleanComposer } = require('./playwright_runner.js');

const results = [];
function check(name, ok, detail) {
  results.push(ok);
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  -- ' + detail : ''}`);
}

(async () => {
  const { ctx, page } = await boot();
  try {
    const fresh = await composerText(page);
    check('fresh page starts clean', fresh === '', `text=${JSON.stringify(fresh)}`);

    const box = page.locator('[role="textbox"]').first();
    await box.click({ timeout: 8000 });
    await page.keyboard.type('LEFTOVER-FROM-LAST-SESSION', { delay: 15 });
    await page.waitForTimeout(600);

    const dirty = await composerText(page);
    check('leftover text is detected', dirty !== '', `text=${JSON.stringify(dirty.slice(0, 60))}`);

    const cleaned = await ensureCleanComposer(page);
    check('ensureCleanComposer reports success', cleaned === true, `returned ${cleaned}`);

    const after = await composerText(page);
    check('box is verifiably empty afterwards', after === '', `text=${JSON.stringify(after.slice(0, 60))}`);
  } finally {
    await ctx.close();
  }
  const failed = results.filter((r) => !r).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  process.exitCode = failed ? 1 : 0;
})().catch((err) => {
  console.error('verify_clean_start failed:', err.message.split('\n')[0]);
  process.exit(1);
});