// Dev-only navigation benchmark. Lives in the extension because only it can
// see tabs, injection and the relay handshake. All timings are wall-clock ms
// from the moment the navigation (or tab switch) starts.
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.SttNavBench = api;
})(typeof self !== 'undefined' ? self : globalThis, function () {
  'use strict';

  const PLATFORMS = ['claude', 'gemini', 'chatgpt'];

  function elapsedFrom(start, now) {
    return Math.max(0, Math.round(now() - start));
  }

  function createNavBench({
    chromeApi,
    resolve,
    sendToTab,
    targetUrls,
    handshakeReady = () => true,
    delay = (ms) => new Promise((r) => setTimeout(r, ms)),
    now = () => Date.now(),
    drafts = true,
  }) {
    function update(tabId, url) {
      return new Promise((resolveUpdate) => {
        try {
          chromeApi.tabs.update(tabId, { url }, () => {
            if (chromeApi.runtime && chromeApi.runtime.lastError) void chromeApi.runtime.lastError;
            resolveUpdate();
          });
        } catch (_) {
          resolveUpdate();
        }
      });
    }

    function tabStatus(tabId) {
      return new Promise((resolveStatus) => {
        try {
          chromeApi.tabs.get(tabId, (tab) => {
            if (chromeApi.runtime && chromeApi.runtime.lastError) {
              void chromeApi.runtime.lastError;
              resolveStatus(null);
              return;
            }
            resolveStatus(tab || null);
          });
        } catch (_) {
          resolveStatus(null);
        }
      });
    }

    async function waitForComplete(tabId, deadlineMs) {
      const started = now();
      for (;;) {
        const tab = await tabStatus(tabId);
        if (tab && tab.status === 'complete') return true;
        if (now() - started >= deadlineMs) return false;
        await delay(100);
      }
    }

    async function pageReady(tabId) {
      try {
        const status = await sendToTab(tabId, 'status', {});
        return {
          ready: !!(status && status.page === 'ok' && status.selectorsReady === true && status.micCount > 0),
          signedIn: !(status && (status.page === 'signed_out' || /auth|signin|login|consent/i.test(status.url || ''))),
          url: (status && status.url) || '',
        };
      } catch (_) {
        return { ready: false, signedIn: false, url: '' };
      }
    }

    async function draftRoundtrip(tabId, marker) {
      if (!drafts) return { checked: false };
      try {
        await sendToTab(tabId, 'diagnostics-draft-set', { text: marker });
        const before = await sendToTab(tabId, 'diagnostics-draft-read', {});
        return { checked: true, before: String(before.text || '') === marker };
      } catch (_) {
        return { checked: false, reason: 'draft-commands-unavailable' };
      }
    }

    async function draftAfter(tabId, marker) {
      if (!drafts) return { checked: false };
      try {
        const result = await sendToTab(tabId, 'diagnostics-draft-read', {});
        const kept = String(result.text || '') === marker;
        await sendToTab(tabId, 'clear', {});
        return { checked: true, kept };
      } catch (_) {
        return { checked: false, reason: 'draft-commands-unavailable' };
      }
    }

    async function benchPlatform(platform, runs) {
      const target = targetUrls[platform];
      const found = await resolve(platform);
      if (!found || typeof found.tabId !== 'number') {
        return { platform, error: 'no-target-tab' };
      }
      const tabId = found.tabId;
      const rows = [];
      for (let run = 0; run < runs; run += 1) {
        const initial = await pageReady(tabId);
        const draft = await draftRoundtrip(tabId, `stt-bench-${platform}-${run}`);
        const start = now();
        await update(tabId, target);
        await waitForComplete(tabId, 20000);
        const completeMs = elapsedFrom(start, now);
        const readyStart = now();
        let page = { ready: false, signedIn: false, url: '' };
        for (let attempt = 0; attempt < 20; attempt += 1) {
          page = await pageReady(tabId);
          if (page.ready) break;
          await delay(100);
        }
        const readyMs = elapsedFrom(readyStart, now);
        const handshakeMs = handshakeReady() ? elapsedFrom(start, now) : -1;
        const switchStart = now();
        const switched = await resolve(platform);
        const switchStatus = switched && typeof switched.tabId === 'number'
          ? await pageReady(switched.tabId)
          : { ready: false };
        const switchMs = elapsedFrom(switchStart, now);
        rows.push({
          run: run + 1,
          navigationStartToCompleteMs: completeMs,
          contentScriptReadyMs: readyMs,
          bridgeHandshakeMs: handshakeMs,
          alreadyOpenSwitchMs: switchMs,
          switchReady: switchStatus.ready,
          signedIn: initial.signedIn && page.signedIn,
          url: page.url,
          draftKept: await draftAfter(tabId, `stt-bench-${platform}-${run}`),
        });
      }
      return { platform, rows };
    }

    return async function runNavBench(options = {}) {
      const runs = Math.max(1, Math.min(10, Number(options.runs) || 2));
      const platforms = Array.isArray(options.platforms) && options.platforms.length
        ? options.platforms.filter((p) => PLATFORMS.includes(p))
        : PLATFORMS;
      const results = [];
      for (const platform of platforms) {
        results.push(await benchPlatform(platform, runs));
      }
      return { at: new Date(now()).toISOString(), runs, results };
    };
  }

  return { PLATFORMS, createNavBench };
});
