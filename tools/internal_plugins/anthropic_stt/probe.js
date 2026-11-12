#!/usr/bin/env node
'use strict';

// Re-verifies every selector in selectors.json against the live Claude tab,
// through the running daemon and the extension. It toggles nothing, types
// nothing and sends nothing. The redacted composer dump lands in debug/ so a
// selector can be re-derived after a Claude redesign.

const fs = require('fs');
const http = require('http');
const path = require('path');

const BASE = process.env.ANTHROPIC_STT_URL || 'http://127.0.0.1:17875';
const DEBUG = path.join(__dirname, 'debug');

function request(method, pathname) {
  return new Promise((resolve, reject) => {
    const req = http.request(BASE + pathname, { method }, (res) => {
      let raw = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        raw += chunk;
      });
      res.on('end', () => {
        let body = null;
        try {
          body = raw ? JSON.parse(raw) : null;
        } catch (_) {
          body = null;
        }
        resolve({ status: res.statusCode, body });
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function redact(value) {
  return String(value || '')
    .replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, '<account-email>')
    .replace(/Claude account:[^"<]*/g, 'Claude account: <account-name>');
}

(async () => {
  let status;
  try {
    status = await request('GET', '/status');
  } catch (err) {
    console.error(`The Anthropic STT bridge is not running (${err.message}). Start the app first.`);
    process.exitCode = 2;
    return;
  }
  console.log(`bridge: ${status.body.browser}   page: ${status.body.page}`);
  if (status.body.browser !== 'connected') {
    console.log('Open the Chrome window for the dictation profile, load the extension, then retry.');
    process.exitCode = 2;
    return;
  }

  const probe = await request('POST', '/probe');
  if (probe.status !== 200) {
    console.log(`probe failed: ${probe.body && probe.body.error} (${probe.body && probe.body.kind})`);
    process.exitCode = 1;
    return;
  }

  const checks = probe.body.checks || [];
  for (const check of checks) {
    const detail = check.detail ? `  -- ${redact(check.detail)}` : '';
    console.log(`${check.ok ? 'PASS' : 'FAIL'}  ${check.name}${detail}`);
  }

  fs.mkdirSync(DEBUG, { recursive: true });
  const dumpPath = path.join(DEBUG, 'probe-composer.html');
  fs.writeFileSync(dumpPath, redact(probe.body.dump), 'utf8');

  const failed = checks.filter((check) => !check.ok).length;
  console.log(`\n${checks.length - failed}/${checks.length} checks passed`);
  console.log(`composer dump: ${dumpPath}`);
  process.exitCode = failed ? 1 : 0;
})();
