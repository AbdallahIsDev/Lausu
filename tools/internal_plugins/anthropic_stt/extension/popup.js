'use strict';

// Extension popup: live bridge status + the per-profile enable switch.
// The switch is the answer to "the plugin is installed in two Chrome profiles
// and both answer the app": the daemon keeps the newest connection, so the
// profile you do not dictate from must be switched off here.

const STORAGE_KEY = 'enabled';

const enabledEl = document.getElementById('enabled');

async function loadEnabled() {
	const stored = await chrome.storage.local.get(STORAGE_KEY);
	// Absent means enabled: an existing install must keep working after the
	// switch is introduced.
	enabledEl.checked = stored[STORAGE_KEY] !== false;
}

enabledEl.addEventListener('change', async () => {
	await chrome.storage.local.set({ [STORAGE_KEY]: enabledEl.checked });
	// Tell the open Claude tab immediately so the next hotkey press obeys it.
	const tabs = await chrome.tabs.query({ url: 'https://claude.ai/*' });
	for (const tab of tabs) {
		chrome.tabs
			.sendMessage(tab.id, { type: 'anthropic-stt-enabled', enabled: enabledEl.checked })
			.catch(() => {});
	}
});

void loadEnabled();
