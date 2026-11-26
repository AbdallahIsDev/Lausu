# Plugin dictation edge cases — status

Statuses: **VERIFIED-LIVE**, **UNIT-ONLY** (faked layer named), **OPEN DEFECT**, **UNVERIFIED** (reason).

| Case | Expected | Status | Evidence / reason |
|---|---|---|---|
| 5 taps at 150 ms | one started recording, no stop | VERIFIED-LIVE | `17:14:04` one start, no stop; gate rejects rest |
| 2 taps at 300 ms | one gesture | UNIT-ONLY | fake clock `tests/test_dictation_gate.py` |
| press during starting | ignored, no replay | VERIFIED-LIVE | `17:14` burst; unit replay pin |
| press during stopping | ignored | UNIT-ONLY | gate state test |
| press while profile launching | relaunch then one recording | VERIFIED-LIVE | graceful close 5/5 at 0.5 s |
| press 1 s after recording | stops normally | VERIFIED-LIVE | `17:14:37` stop + `17:14:43` next start |
| Esc during starting | aborts, no late start | UNIT-ONLY | generation bump in `cancel()` |
| Chrome closed gracefully during start | relaunch bounded, one recording | VERIFIED-LIVE | 5/5 graceful at 0.5 s, 0.1–6.0 s |
| Chrome killed during start | same | OPEN DEFECT | 3/5 at same stage; cooldown/late-WMI race under investigation |
| Chrome closed during recording | one-line WARN, idle, next press works | VERIFIED-LIVE | `17:18:38` WARN no traceback; `17:19:08` next recording |
| Bridge disconnect during recording | same + text recovery | UNVERIFIED | text recovery requires page alive; not driven |
| Tab closed by hand | one replacement, ready | VERIFIED-LIVE | 20/20 ChatGPT prior round |
| Tab discarded | reload then ready | UNIT-ONLY | ownership/re-ensure tests; live discard UNVERIFIED |
| User's own platform tab | never closed, adopted | UNIT-ONLY | `tab_ownership.test.js`, no live second tab |
| 65 s activation | bounded few seconds | VERIFIED-LIVE | `17:13:31` prepare 4.8 s (was 64.9 s) |
| Hidden vs visible | logic identical | VERIFIED-LIVE | earlier 5-cycle both modes; not repeated after gate |
| Offline | actionable failure | UNVERIFIED | no firewall rule applied |
| Sleep/resume, lock screen | reconnect | UNVERIFIED | cannot simulate here |
| Local/cloud engine burst | one gesture | UNVERIFIED | no local model file/API key available; gate unit tests cover all engines |

Decision: one tab per plugin. 1/2/3 tabs = 1168/1566/2108 MB working set;
ChatGPT navigation 885–2206 ms, composer text lost. Revisit only if plugins
become end-user visible or RAM pressure dominates.
