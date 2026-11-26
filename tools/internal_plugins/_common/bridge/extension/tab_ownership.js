// Identity of tabs WE created. A user's own platform tab is never closed.
// Stored in chrome.storage.session: survives service-worker restarts, but is
// cleared on browser restart / extension reload, so stale ids cannot leak.
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.SttTabOwnership = api;
})(typeof self !== "undefined" ? self : globalThis, function () {
  "use strict";

  const KEY = "ownedTabs";

  function createOwnership(storage) {
    async function load() {
      try {
        const raw = await storage.session.get(KEY);
        const list = raw && raw[KEY];
        return Array.isArray(list) ? list : [];
      } catch (_) {
        return [];
      }
    }

    async function save(records) {
      try {
        await storage.session.set({ [KEY]: records.slice(-20) });
      } catch (_) {}
    }

    async function validate(records, liveTabs) {
      const live = new Map((liveTabs || []).map((tab) => [tab.id, tab]));
      const kept = records.filter((record) => {
        const tab = live.get(record.id);
        return !!tab && tab.windowId === record.windowId &&
          ((tab.url && tab.url.startsWith(record.prefix)) ||
            (tab.pendingUrl && tab.pendingUrl.startsWith(record.prefix)));
      });
      if (kept.length !== records.length) await save(kept);
      return kept;
    }

    async function ids(liveTabs) {
      return (await validate(await load(), liveTabs)).map((record) => record.id);
    }

    async function mark(tab, platform, prefix) {
      if (!tab || typeof tab.id !== "number") return;
      const records = (await load()).filter((record) => record.id !== tab.id);
      records.push({ id: tab.id, platform, prefix, windowId: tab.windowId });
      await save(records);
    }

    async function unmark(tabId) {
      await save((await load()).filter((record) => record.id !== tabId));
    }

    return { ids, mark, unmark, load, validate };
  }

  return { KEY, createOwnership };
});
