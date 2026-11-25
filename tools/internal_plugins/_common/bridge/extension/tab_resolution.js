// Target-tab identity for the shared STT bridge. Only the extension can use
// chrome.tabs.*, so reuse/create policy lives here and is identical for both
// plugins. UMD wrapper: importScripts() in the worker, require() in node:test.
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.SttTabResolution = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  const SETTLE_POLL_MS = 150;
  const SETTLE_MAX_MS = 8000;

  function matchesUrl(url, pattern) {
    if (typeof url !== "string" || typeof pattern !== "string") return false;
    return pattern.endsWith("*")
      ? url.startsWith(pattern.slice(0, -1))
      : url === pattern;
  }

  // A tab launched from the Chrome command line can still have a pending URL
  // (or be mid-redirect) while its committed `url` is about:blank. Match both
  // so the second tab is never created (Item 3).
  function tabMatches(tab, pattern) {
    return matchesUrl(tab.url, pattern) || matchesUrl(tab.pendingUrl, pattern);
  }

  function queryTabs(chromeApi, pattern) {
    return new Promise((resolve) => {
      try {
        chromeApi.tabs.query({ url: pattern }, (tabs) => {
          if (chromeApi.runtime && chromeApi.runtime.lastError) {
            void chromeApi.runtime.lastError;
            resolve([]);
            return;
          }
          resolve(
            (tabs || []).filter(
              (tab) =>
                tab &&
                typeof tab.id === "number" &&
                tabMatches(tab, pattern),
            ),
          );
        });
      } catch (_) {
        resolve([]);
      }
    });
  }

  // Deterministic: the active matching tab wins; otherwise the lowest id.
  // Never pick a tab merely because it is active -- it must match the URL.
  function pickTab(tabs) {
    const active = tabs.find((tab) => tab.active);
    if (active) return active;
    return tabs.reduce((best, tab) => (!best || tab.id < best.id ? tab : best), null);
  }

  function createTab(chromeApi, url, logEvent = () => {}) {
    logEvent({ action: 'tabs.create', url, caller: 'tab_resolution.resolve' });
    return new Promise((resolve, reject) => {
      try {
        chromeApi.tabs.create({ url, active: false }, (tab) => {
          if (chromeApi.runtime && chromeApi.runtime.lastError) {
            void chromeApi.runtime.lastError;
            reject(new Error("chrome refused to create the target tab"));
            return;
          }
          logEvent({
            action: 'tabs.create.result',
            url,
            tabId: tab && tab.id,
            caller: 'tab_resolution.resolve',
          });
          resolve(tab || null);
        });
      } catch (err) {
        reject(err);
      }
    });
  }

  // Tab selection inside Chrome, never window focus: the dictation path must
  // not steal focus from the user's target field.
  function removeTab(chromeApi, tabId) {
    return new Promise((resolve) => {
      try {
        chromeApi.tabs.remove(tabId, () => {
          if (chromeApi.runtime && chromeApi.runtime.lastError) void chromeApi.runtime.lastError;
          resolve();
        });
      } catch (_) {
        resolve();
      }
    });
  }

  function navigateTab(chromeApi, tabId, url, logEvent = () => {}) {
    logEvent({ action: 'tabs.update.navigate', url, tabId, caller: 'tab_resolution.adoptBlank' });
    return new Promise((resolve) => {
      try {
        chromeApi.tabs.update(tabId, { url }, () => {
          if (chromeApi.runtime && chromeApi.runtime.lastError) void chromeApi.runtime.lastError;
          resolve();
        });
      } catch (_) {
        resolve();
      }
    });
  }

  // A cold launch opens ONE about:blank tab. Adopting it keeps the profile at
  // one tab instead of leaving a blank tab beside the platform tab.
  function findBlank(chromeApi) {
    return new Promise((resolve) => {
      try {
        chromeApi.tabs.query({}, (tabs) => {
          if (chromeApi.runtime && chromeApi.runtime.lastError) {
            void chromeApi.runtime.lastError;
            resolve(null);
            return;
          }
          const all = tabs || [];
          const blanks = all.filter(
            (tab) =>
              tab &&
              typeof tab.id === 'number' &&
              !tab.pendingUrl &&
              (!tab.url || tab.url === 'about:blank' || tab.url === 'chrome://newtab'),
          );
          resolve(all.length === 1 && blanks.length === 1 ? blanks[0] : null);
        });
      } catch (_) {
        resolve(null);
      }
    });
  }

  function activateTab(chromeApi, tabId) {
    return new Promise((resolve) => {
      try {
        chromeApi.tabs.update(tabId, { active: true }, () => {
          if (chromeApi.runtime && chromeApi.runtime.lastError) {
            void chromeApi.runtime.lastError;
          }
          resolve();
        });
      } catch (_) {
        resolve();
      }
    });
  }

  function targetUrl(platform, opts, patterns, targetUrls) {
    const prefix = patterns[platform].slice(0, -1);
    const configured = opts && opts.url;
    if (typeof configured === "string" && configured.startsWith(prefix)) {
      return configured;
    }
    return targetUrls[platform];
  }

  function createTabResolver({
    chromeApi,
    patterns,
    targetUrls,
    probe = async () => true,
    logEvent = () => {},
    delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    maxWaitMs = SETTLE_MAX_MS,
    activate = true,
  }) {
    const inflight = new Map();

    async function allMatches(platform) {
      const pattern = patterns[platform];
      return pattern ? queryTabs(chromeApi, pattern) : [];
    }

    async function find(platform) {
      return pickTab(await allMatches(platform));
    }

    // `tabs.query({url})` matches committed URLs only (Chrome docs). Query all
    // tabs as a fallback so a launch/redirect in flight is still recognised.
    async function pendingMatches(platform) {
      const pattern = patterns[platform];
      if (!pattern) return [];
      return new Promise((resolve) => {
        try {
          chromeApi.tabs.query({}, (tabs) => {
            if (chromeApi.runtime && chromeApi.runtime.lastError) {
              void chromeApi.runtime.lastError;
              resolve([]);
              return;
            }
            resolve((tabs || []).filter((tab) => tab && tabMatches(tab, pattern)));
          });
        } catch (_) {
          resolve([]);
        }
      });
    }

    async function findPending(platform) {
      return pickTab(await pendingMatches(platform));
    }

    // One tab per platform. Only surplus tabs that matched THIS platform's
    // URL pattern are removed; other platforms and unrelated tabs are never
    // touched, and the preferred tab is always kept.
    async function dropSurplus(tabs, keepId) {
      for (const tab of tabs) {
        if (tab.id === keepId) continue;
        await removeTab(chromeApi, tab.id);
      }
    }

    async function waitForTab(platform, expectedId) {
      const started = Date.now();
      for (;;) {
        const tab = await find(platform);
        if (tab && (tab.id === expectedId || !expectedId)) return tab;
        if (Date.now() - started >= maxWaitMs) return null;
        await delay(SETTLE_POLL_MS);
      }
    }

    async function resolve(platform, opts = {}) {
      const pattern = patterns[platform];
      if (!pattern) return { tabId: null, created: false, ready: false, reason: "unknown-platform" };

      let matches = await allMatches(platform);
      let tab = pickTab(matches);
      if (tab) {
        await dropSurplus(matches, tab.id);
        if (activate && opts.activate !== false) await activateTab(chromeApi, tab.id);
        return { tabId: tab.id, created: false, ready: true, url: tab.url };
      }

      const pending = await findPending(platform);
      if (pending) {
        const pendingDupes = new Map();
        for (const tab of [...(await allMatches(platform)), ...(await pendingMatches(platform))]) {
          pendingDupes.set(tab.id, tab);
        }
        await dropSurplus([...pendingDupes.values()], pending.id);
        if (activate && opts.activate !== false) await activateTab(chromeApi, pending.id);
        return {
          tabId: pending.id,
          created: false,
          ready: true,
          url: pending.url || pending.pendingUrl,
        };
      }

      const blank = await findBlank(chromeApi);
      if (blank) {
        await navigateTab(chromeApi, blank.id, targetUrl(platform, opts, patterns, targetUrls), logEvent);
        tab = await waitForTab(platform, blank.id);
        if (tab) {
          await dropSurplus(await allMatches(platform), tab.id);
          if (activate && opts.activate !== false) await activateTab(chromeApi, tab.id);
          let ready = false;
          try {
            ready = !!(await probe(tab.id));
          } catch (_) {}
          return { tabId: tab.id, created: true, adopted: true, ready, url: tab.url };
        }
      }

      let created;
      try {
        created = await createTab(
          chromeApi,
          targetUrl(platform, opts, patterns, targetUrls),
          (event) => logEvent({ ...event, platform }),
        );
      } catch (_) {
        return { tabId: null, created: false, ready: false, reason: "create-failed" };
      }
      if (!created) return { tabId: null, created: false, ready: false, reason: "create-failed" };

      tab = await waitForTab(platform, created.id);
      if (!tab) {
        // A tab can appear after the settle budget expires; still collapse
        // duplicates before reporting the miss.
        matches = await allMatches(platform);
        await dropSurplus(matches, created.id);
        return { tabId: created.id, created: true, ready: false, reason: "not-visible" };
      }
      matches = await allMatches(platform);
      await dropSurplus(matches, tab.id);
      if (activate && opts.activate !== false) await activateTab(chromeApi, tab.id);
      let ready = false;
      try {
        ready = !!(await probe(tab.id));
      } catch (_) {}
      return { tabId: tab.id, created: true, ready, url: tab.url };
    }

    // Two hotkey presses (or an /ensure-tab racing /start) must not both
    // observe "no tab" and both create one.
    function ensure(platform, opts = {}) {
      if (inflight.has(platform)) return inflight.get(platform);
      const task = resolve(platform, opts);
      inflight.set(platform, task);
      const clear = () => {
        if (inflight.get(platform) === task) inflight.delete(platform);
      };
      task.then(clear, clear);
      return task;
    }

    return { find, ensure };
  }

  function createDispatcher({ resolver, sendToTab, resolvingCommands }) {
    async function dispatch(platform, cmd, opts) {
      const mayCreate = resolvingCommands.has(cmd);
      for (let attempt = 0; attempt < 2; attempt += 1) {
        const resolved = mayCreate
          ? await resolver.ensure(platform, opts)
          : { tabId: (await resolver.find(platform))?.id };
        if (typeof resolved.tabId !== "number") {
          throw { kind: "browser-not-open", error: "the target tab is not open" };
        }
        try {
          return await sendToTab(resolved.tabId, cmd, opts);
        } catch (err) {
          const retryable = err && (err.kind === "page-not-ready" || err.kind === "browser-not-open");
          if (attempt === 0 && retryable) continue;
          throw err;
        }
      }
      throw { kind: "browser-not-open", error: "the target tab is not open" };
    }
    return { dispatch };
  }

  return { createTabResolver, createDispatcher, matchesUrl, pickTab };
});
