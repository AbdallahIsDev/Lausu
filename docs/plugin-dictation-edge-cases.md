# Plugin dictation edge cases — status

Status values: **VERIFIED-LIVE** (real app evidence), **UNIT-ONLY** (fake
browser/process layer named), **OPEN DEFECT**, **UNVERIFIED** (exact reason).

| Case | Expected | Status | Evidence / faked layer |
|---|---|---|---|
| Profile never started; first hotkey | one blank launch tab adopted, 1 tab | VERIFIED-LIVE | 1 ChatGPT/Gemini/Claude tab, 5 runs each |
| Tab closed by hand, profile open | exactly 1 replacement tab, dictation starts | VERIFIED-LIVE | `02:59` failed before; `03:35` tab=loading→ready, recording 2.3 s; 20 ChatGPT cycles |
| Whole profile closed | relaunch and navigate same tab, 1 tab | VERIFIED-LIVE | `02:32` recovery; 20/20 ChatGPT, Gemini cycles |
| Chrome killed during startup (0/0.5/1.5/3/5 s) | immediate abort, relaunch, recording | VERIFIED-LIVE | 5/5 stages recovered in 0.7–7.8 s |
| Chrome killed mid-recording | stop gives clear result, no hang | VERIFIED-LIVE | stage 5 s kill + stop; 10 kill/relaunch cycles |
| Tab=loading with mic in DOM | must NOT pass gate | VERIFIED-LIVE | `02:59` before; `03:35` after state transition to ready |
| Restore pages bubble | never appears, no tab change | VERIFIED-LIVE | Preferences clean-exit before launch; 10 kills → 0 bubbles, 1 tab each |
| Mic permission | granted for exactly 3 origins, no global flag | UNIT-ONLY | profile Preferences inspected; fake layer = tmp file |
| Extension reload / service worker restart | no duplicate tabs | VERIFIED-LIVE | reload driven repeatedly; tabs-dump 1–3, no stray blank |
| Daemon killed | next start respawns, no second daemon | UNIT-ONLY | fake process/launch layer; live kill UNVERIFIED |
| Port busy | no second daemon, clear failure | UNIT-ONLY | liveness helpers; live port occupancy UNVERIFIED |
| Tab discarded by Memory Saver | detect, re-ensure/reload, wait ready | UNIT-ONLY | `ensure_target_ready` re-posts `/ensure-tab` on `tab.discarded`; live `chrome.tabs.discard` UNVERIFIED |
| Tab navigated to other site / login / settings | fail fast with actionable hint, no tab churn | VERIFIED-LIVE (login detection unit only) | `tab.wrong_url` / `signed_in.no` state; live navigation UNVERIFIED |
| Second manual tab of same platform | never close user tab; pick active matching tab | UNIT-ONLY | active-tab selection pinned by tab_resolution tests |
| Double press <300 ms | one cycle, no duplicate tab | UNIT-ONLY | generation/supersede tests with fake session |
| Press during activation / stuck start | new press supersedes old start | UNIT-ONLY | `test_start_supersede.py` fake session |
| Press during stop / plugin switch | single-flight preserved | UNIT-ONLY | C-CONC-1 tests |
| Offline at start / mid-session | actionable failure, no blind 12 s | UNVERIFIED | no admin firewall rule applied |
| Sleep/resume, Windows lock | reconnect, no tab churn | UNVERIFIED | cannot simulate in this session |
| Hidden vs visible mode | logic identical, only visibility differs | VERIFIED-LIVE | 5 cycles each scenario in both modes; 1 tab |
| Plugin off/on | tabs reused, no duplicate | VERIFIED-LIVE | cold start 5 runs each; 1 tab |

Decision: one tab per plugin. Measured 1/2/3 tabs = 1168/1566/2108 MB
working set; ChatGPT navigation 885–2206 ms and drafts lost. Revisit only if
plugins become end-user visible or RAM pressure dominates.
