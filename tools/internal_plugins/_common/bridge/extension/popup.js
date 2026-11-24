'use strict';

// Extension popup: live bridge status + the per-profile enable switch.
// The switch is the answer to "the plugin is installed in two Chrome profiles
// and both answer the app": the daemon keeps the newest connection, so the
// profile you do not dictate from must be switched off here.

const STORAGE_KEY = 'enabled';

// Every platform the shared bridge drives. The switch is per Chrome PROFILE,
// so a profile that is switched off must be told on EVERY open platform tab:
// notifying only Claude left a ChatGPT or Gemini tab capturing anyway.
const PLATFORM_URLS = ['https://claude.ai/*', 'https://gemini.google.com/*', 'https://chatgpt.com/*'];

const enabledEl = document.getElementById('enabled');

async function loadEnabled() {
	const stored = await chrome.storage.local.get(STORAGE_KEY);
	// Absent means enabled: an existing install must keep working after the
	// switch is introduced.
	enabledEl.checked = stored[STORAGE_KEY] !== false;
}

enabledEl.addEventListener('change', async () => {
	await chrome.storage.local.set({ [STORAGE_KEY]: enabledEl.checked });
	// Tell every open platform tab immediately so the next hotkey press obeys
	// the switch, whichever platform it targets.
	const tabs = await chrome.tabs.query({ url: PLATFORM_URLS });
	for (const tab of tabs) {
		chrome.tabs
			.sendMessage(tab.id, { type: 'stt-bridge-enabled', enabled: enabledEl.checked })
			.catch(() => {});
	}
});

void loadEnabled();
