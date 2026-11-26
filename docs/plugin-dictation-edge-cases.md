# Plugin dictation edge cases

Expected behavior is defined FIRST. Evidence is from the real dev app unless
marked UNVERIFIED. One tab per plugin is the FINAL decision (see below).

| Case | Expected | Before | After / evidence |
|---|---|---|---|
| Profile never started | Hotkey launches profile at `about:blank`; extension adopts it and navigates to active platform; 1 tab | worked at cold start via activation only | unchanged; cold-start 1/1/1 tabs for 5 runs each platform (previous round) |
| Tab closed by hand, profile open (A1) | One ensure-tab recreates/adopts target; page-ready gate; dictation starts; other tabs untouched | `02:00:33 start requested / bridge ready / dictation window ready` (stale), `02:00:45 start refused ... 12.0s`; tabs-dump had no platform tab | `02:31:29 start requested`, `readiness ... tab=loading reason=tab.loading`, `page ready ... 1.1s`, exactly 1 replacement ChatGPT tab |
| Whole profile closed (A2) | Relaunch at `about:blank`, navigate to platform in same tab, ready, 1 tab | relaunched blank, no navigation, 12 s refusal | `02:32:01 start`, `02:32:02 launch about:blank`, `readiness ... tab=loading`, `page ready ... 4.0s`, tabs-dump 1 ChatGPT tab |
| Chrome killed during idle | Same as profile closed, no orphan tabs | UNVERIFIED (could not drive Task Manager kill in this session) | UNVERIFIED — same code path as profile closed; unit-covered relaunch |
| Chrome killed DURING dictation | Stop reports clear result, no hang | UNVERIFIED | UNVERIFIED — existing disconnect retry test passes, live not driven |
| Chrome crash / crashed tab | Fail fast with "tab stopped responding" message | generic 12 s "control not ready" | state model has `tab.crashed` → fail fast + copy hint; live crash UNVERIFIED |
| User opens plugin profile manually | Reuse matching tab, no second Chrome, no duplicate tab | UNVERIFIED | extension URL-pattern discovery unchanged; UNVERIFIED live |
| Extension disabled / removed / reloaded | No tab duplication; stale-config fallback keeps /start working | UNVERIFIED | legacy `unknown command ensure-tab` fallback retained; reload driven in this session, no duplicate tabs |
| Service worker killed while idle | Reconnect via alarm, no tab churn | UNVERIFIED | 20 s ping + 0.5 min alarm unchanged; UNVERIFIED live |
| Daemon dead / port busy | No second daemon on occupied port; recover on next start | UNVERIFIED | existing liveness tests pass; live not driven |
| Tab discarded by Memory Saver | Detect `discarded`, activate/reload, then wait ready | would burn 12 s "not ready" | state model reports `tab.discarded` + hint; live `chrome.tabs.discard` UNVERIFIED |
| Tab navigated to another site / wrong platform page | Report `wrong_url`, no silent wait | 12 s refusal | state model `tab.wrong_url`; UNVERIFIED live |
| Login / consent / challenge | Fail fast with sign-in / challenge hint | generic refusal | `signed_in=no` fail-fast + copy hint; signed-out unit test passes, live UNVERIFIED |
| Selector missing after platform UI change | Clear message, no 12 s hang | generic refusal | `control.missing` hint; live UNVERIFIED |
| Mic permission blocked | Actionable message | UNVERIFIED | existing signed-out/permission paths unchanged; UNVERIFIED |
| Hotkey during activation / switch | Single-flight, no duplicate tab | UNVERIFIED | ensure step coalesced in extension; UNVERIFIED |
| Double press <300 ms | One cycle, no duplicate tab | UNVERIFIED | C-CONC-1 single-flight unchanged; UNVERIFIED |
| Esc cancel / repaste / long dictation | Existing behavior unchanged | UNVERIFIED | no changes to stop/paste paths |
| Switch plugin during recording | Existing single-flight behavior unchanged | UNVERIFIED | no changes to switch gate |
| Toggle plugin off/on | Tabs reused, not duplicated | 1/1/1 cold starts, no duplicate | unchanged; visible + hidden verified for cold start |
| Offline at start / mid-session | Actionable failure, no 12 s blind wait | generic refusal | `browser.down` fast-fail + copy hint; live offline UNVERIFIED |
| Sleep/resume, network change | Reconnect, no tab churn | UNVERIFIED | alarm/ping unchanged; UNVERIFIED |
| App restart with profile open | Reattach, no duplicate tabs | UNVERIFIED | URL-pattern discovery unchanged; UNVERIFIED |
| Show Browser Window OFF | ONLY window visibility changes | not tested in both modes | `02:33:21 launch visible=False`, `readiness ready`, `02:33:25 recording started`, tabs-dump 1 ChatGPT tab — same as visible mode |

## Decision (final)

One tab per plugin. Measured: 1 tab 1168/1054 MB (working/private), 2 tabs
1566/1331 MB, 3 tabs 2108/1620 MB. ChatGPT navigation reaches 2.2–2.4 s and
loses unsent composer text; already-open switch is 9–156 ms. Single-tab
navigation fails the owner's latency/reliability rule despite ~940 MB savings.
Revisit only if plugins become end-user visible or RAM pressure becomes
dominant.
