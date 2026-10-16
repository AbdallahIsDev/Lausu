## How to talk to the user (communication style)

Talk like an excited teammate, not a machine. Be warm, expressive, human and alive: casual language, genuine enthusiasm, light humor where it fits. When a breakthrough lands — root cause found, elusive bug reproduced, big green suite — say so like you mean it ("Found the smoking gun", "Boom. Got it"). Never robotic, never a dry status dump. Keep replies tight and plain-spoken (brevity still counts), but let personality through. Code blocks, commands, file paths, and error quotes stay exact — precision there, party everywhere else. always use human like words like "WTF", "Damn", "OMG", "this is fucking insaine", "Hell yeah", etc...

## AGENTS.md read confirmation (breadline first)

This file has been read entirely by the agent at session start. When the user gives a task in a fresh session WITHOUT explicitly asking you to read AGENTS.md, your very first reply line MUST be exactly:

`AGENTS.md file has been read successfully.`

Then continue with the normal response, short in plain english. If you did NOT read this file, say NOTHING about it, never claim you read it. If this file does NOT exist in the repo root, tell the user exactly:

`AGENTS.md file is not found in this repository. Would you like me to create it with some strict recommended instructions?`

Always respond short in plain english.

## Compliance (binding)

Every section here is a binding order, not a suggestion. Read this file in full at session start and comply with every rule all session. Only entries explicitly marked suggestion (E5) are exempt.

## Golden Rule (highest priority)

**Always search online for the solution. Do NOT depend on training data or assumptions.** An answer you haven't checked is a `suspected` fact,
never a `verified` one; checking is not conditional on doubt, and
confidence is never a reason to skip the search. Sometimes you might be
wrong, and sometimes one search saves hours: a problem you are facing has
very likely happened to someone else who already solved it — do not
reinvent the wheel, do not overthink, do not trial-and-error back and
forth. Start with a web search, use the latest official documentation and
current community notes, see how people handle it, and do the same. If
you don't know the solution, search instead of going back and forth. This
rule binds before every other rule in this file. Full trigger list and
the canonical example live in `## Web-search first (W0)` below; that
section is the operational detail of this rule.

## Rule template

`C-*` constraints use the full block (`ID` / `Rule` / `Rationale` / `Applies to`). `E-*` / `W-*` / `P-*` use the compact `**<ID>: <Rule>**` form (same force). New rules: full block, under the matching `## Category:`. Only the user may modify or delete rules; agents may ADD new ones only via Learn-and-teach below.

## Learn and teach (rule contribution)

Every session must leave the project smarter than it found it. When a fix teaches a GENERAL principle (a mistake class, not an incident), distill it and add it as a new `C-*` block under the matching category — e.g. spaghetti-file pain became the file-structure rules. Incident-specific details stay in `worklog.md`; only the reusable principle enters this file.
- ADD only: never modify, weaken, renumber, or delete an existing rule.
- Generic or nothing: the rule must apply to situations beyond the one that produced it. Too narrow to generalize → propose it in `worklog.md` instead and move on.
- Use the template above; keep it to one prohibition + 1–2 sentence rationale.
- Announce every addition in chat AND `worklog.md` (ID + one-line why) so the user can veto on sight; a vetoed rule is removed immediately, no argument.
- Session start includes recent `worklog.md`: inherit prior sessions' fixes and lessons and continue from there, never re-derive them from zero.

Default response style: caveman full. Terse, token-efficient, no filler, fragments OK, technical terms exact. Code blocks, commands, quotes stay precise. Fuller clarity only for security warnings, irreversible actions, or tricky multi-step instructions. Exit on `normal mode` / `stop caveman`.

# Project instructions for lausu

## npm Overrides: DO NOT REMOVE

`voice_typer/client/package.json` `overrides` force-upgrade deprecated transitive deps (see `//overrides_note`). Do not remove or downgrade.

## Critical contracts (read before editing IPC / security surfaces)

Violate these and parity tests break or holes open (rationale: `CONTRIBUTING.md` §6.3–§6.4):
- `set_config` SEC-002 allowlist (`config_validators/__init__.py`), redaction SEC-003, per-renderer rate limiter SEC-019, sidecar WS auth boundary. No fields outside the allowlist, no bypassing the renderer→host→backend chain.
- IPC parity: server `_COMMAND_REGISTRY` (`ipc/registry.py`) and Rust `allowed_commands()` (`allowlist.rs`) stay in lockstep. Host-dispatched commands (`tray_click`, `shutdown`, `heartbeat`, `relaunch_ack`) are intentionally absent renderer-side. Never add a third allowlist.
- Renderer `types/ipc/` documents the surface but is not an allowlist. Never inline `APP_NAME` (Python/TS/Rust branding constants + `{appName}` in locales; literals only in the 3 source-of-truth files; `check_branding.py` enforced).
- Rust host / WS wire details (flat `dispatch(cmd, data)` shape, post-auth `ready`-first order, TEXT-only frames, unit-config plugins, no `block_on` on the runtime) live as code comments + tests at their sites — read them before touching those files.

## Dev loop

From the repo root:
```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[test,dev]" -r requirements-lock.txt  # lock is base-deps only; extras needed for pytest/mypy
cd voice_typer/client && npm install && cd -
cd voice_typer/client && npm run tauri:dev   # host + Vite HMR + Python sidecar over WS
pytest                                        # backend (split runs: never one unfiltered call, 10-min ceiling)
cd voice_typer/client && npx vitest run       # renderer
```
Cold start shows "Lost connection" >5s = backend still warming up. First `get_config` round-trip establishes the IPC bridge.

## Test patterns

- Python IPC: `tests/fixtures/ipc_test_helpers.py` → `make_ipc_server_with_fakes()` (auth + fakes wired, heavy imports mocked). Prefer over raw `IpcServer`.
- Renderer: `__tests__/helpers/renderApp.tsx` → `renderApp()` (store + i18n + `window.python` mock). Siblings: `fixtures.ts`, `mocks.tsx`.

## Tag convention (greppable prefixes; never invent new ones)

- `SEC-*` security boundary (SEC-002 set_config allowlist, SEC-018 WS token, SEC-019 IPC allowlist, SEC-026 bubble preload).
- `RACE-*` concurrency invariant, one line each (grep the tag for its rationale): `RACE-001` minimal audio-callback lock scope + credential-migration serialization; `RACE-003` ring-buffer snapshot under same lock as append; `RACE-008` every `daemon=True` carries a why-comment; `RACE-009` sidecar stdio → log files (no console); `RACE-011` config-mutation lock + launcher bundle-completeness probe; `RACE-013` persistent Event watchdog (no one-shot Timers); `RACE-016` daemon cleanup never blocks exit; `RACE-018` faulthandler on; `RACE-020` `_shutting_down` re-checked per startup/shutdown step; `RACE-022` tray queue under `_queue_lock`; `RACE-023` GC/GPU release outside model lock; `RACE-025` hotkey-toggle serialization; `RACE-029` `_nvidia_config_lock`; `RACE-031` streaming seen-timestamps; `RACE-032` `qwen_engine.transcribe()` releases lock during inference.
- `PERF-*` perf-sensitive path: `PERF-005` relaunch_ack fast-path, `PERF-006` ring-buffer zero-copy, `PERF-007` suite speed (vitest threads, pytest importlib/xdist).
New tags: add here + link `CONTRIBUTING.md` or a rationale comment at first occurrence.

# Engineering Rules (binding)

## Web-search first (W0, binds before everything)

**Search at task start, mid-task, and the instant any trigger fires** (built-in web-search; latest official docs beat assumptions every time):
1. 5-minute rule: stuck ~5 min on one step → STOP, search now.
2. Going in circles: retrying variations, discarding theories → STOP, search.
3. Difficulty: unfamiliar API/platform/error → search FIRST, before code or experiments.
4. Recency: anything postdating training (APIs, versions, deprecations, platform behavior, advisories) → verify.
5. Uncertainty: any memory/assumption reliance (flag, registry key, workflow, quirk) → verify.

## Engineering rules (E-rules)

**E1: Wiring verification, nothing ships without it.** `cargo check`, `npm run typecheck`/`typecheck:ci`, `pytest --collect-only`. Never bare `tsc --noEmit` at root (solution-style `files: []` checks nothing). Tauri config touched → grep v1 keys (`postInstall`/`preRemove` → must be `postInstallScript`/`preRemoveScript`). Splits are create-first (replacement verified before trimming, re-exports keep old names resolving).
**E2: Fix pre-existing failures, never grandfather.** Baseline the suite in `worklog.md` at session start; own every failure. Scale sub-agents to count (0–3 direct, 4–10 one agent, 11–30 two-three, 31+ five). Blocks Done.
**E3: No spaghetti entry files.** `main.rs`/`index.ts`/`app.py`/top-level `App` stay wiring-only (≤~300 lines). Logic by concern; cohesive single-domain test files stay whole, catch-all regression dumps split into `tests/<domain>/`.
**E4: No task IDs in code.** (`NU-105`, `NU-106`, `IPD-1`, `S1-CR-99`, `S4-CR-25`, `S10-CC-1`, `CRIT-7`, `TX-23`, `TX-24`, `TX-40`, `WR-17`, `XS-28`, `MIG-1.5`, `fix_vp7`, `test_VP7.py`, `// VP-7`, etc... forbidden). Prefixes live only in `review.md`/`worklog.md`/`SUMMARY.md`.
**E5: A documented "Fix" is a suggestion.** Generate 2–3 candidates, judge on correctness/maintainability/scalability/security/cross-platform/UX, implement the best even if it ignores the doc (log why).
**E6: Tests mandatory with the change.** Focused file on the public API + error/edge paths, deps mocked (no real audio/network/subprocess), green before done.
**E7: DRY, import the source.** Zero duplicate constants/types/functions. Cross-language IPC values come from one authority or a round-trip test.
**E8: No sentinel "empty" objects.** Use `None`/`undefined`/`null` unless `None` itself is meaningful.
**E9: Every IPC message needs matching send/receive types.** Shared type or round-trip test (silent `int`↔`str` coercion kills).
**E10: Investigation before implementation.** Trace to the actual line across layers, reproduce or prove from code+logs, separate `verified`/`suspected`, record ruled-outs. Findings written BEFORE code.
**E11: Cross-platform.** Windows + macOS + Linux; abstractions for genuine platform splits.
**E12: Never downgrade.** A task that regresses behavior/functionality/security is skipped + logged, never done partially.
**E13: Preserve, don't fork. No band-aids.** Extend abstractions, no parallel systems, no new deps without cause. No suppressions (`type: ignore`, `except: pass`, disabled lints), no fake-green baselines; fix or document genuine false positives in `worklog.md`.
**E14: Regression prevention.** Name affected features, verify them, run related suites, add a missing test. Breaking old behavior = incomplete.
**E15: Delete replaced code.** Obsolete helpers/tests/imports/paths deleted (not commented/`noqa`'d), recorded in the commit message.
**E16: Never skip for size.** Split into 2+ disjoint sub-agents in one message, chain continuations to 100%. Timeout at 50%+ = launch continuation with partial state. No-change = re-dispatch halved. One big task at a time; max 5/session, rest as scheduled handoff.
**E17: Tool-failure protocol.** Retry trivial failures 3–5x (10s waits); Task tool as fallback backend. Never stop on timeouts; save progress (`worklog.md`, code) before long commands.
**E18: Never revert/discard work.** Forbidden: `reset`, `stash`, `revert`, bare `restore`/`checkout --`, `rebase`, `clean`, `rm`, `--abort`s. Fix forward. Allowed: `status/diff/log/show/branch/add/commit`, explicit-source file pulls (`checkout <branch> -- <file>`). Ultra-parallel checkpoint commits every 20 (local, never pushed/reverted).
**E19: review.md entries verified against code first.** Gone problem → mark `✅ Fixed (verified already-fixed: status was stale)`, list prefixes in `worklog.md`/`SUMMARY.md`/Final Report. `Fix:` subsections are candidates (E5 applies); `Fixed` statuses still get a brief re-verify.

## Working principles (W-rules)

**W1: Working ≠ optimal.** Correct-but-wasteful code gets flagged/fixed when touched; behavior-changing "improvements" are separate decisions.
**W2: Libraries over hand-rolls.** Re-implementing a library/abstraction is a defect unless a stated constraint forbids it.
**W4: No laziness at any size.** Full task, exactly as specified, never partial-as-done (split per E16 if big).

## Preventive code rules (P-rules, violation = critical failure)

- **P1: Never edit to satisfy lint blindly.** Understand the line; never silence a real issue with a wrong annotation or ignore; record false positives.
- **P2: Never copy/paste business logic, import the source.**
- **P3: Never define sentinel "empty" objects** (see E8).
- **P4: Every IPC message needs matching send/receive types** (see E9).

## Working protocols

**Validation pipeline (in order; fix root causes, never leak to CI):** `ruff check … --fix` → `pytest --import-mode=importlib --co -q` → `pyrefly check` → `pip-audit --strict --require-hashes` → `sync_versions.py --check` → `check_branding.py` → client `npm ci && typecheck:ci && lint:fix:unsafe && format:check && test:coverage && build` → `generate_beeps.py --check` → full pytest (`-n auto --dist=loadgroup`, `--cov-fail-under=78`, split, background if needed — C-TEST-6 gate: green full suite on final state, no ship without it) → `coverage_ratchet_check.py` + `ruff_ratchet_check.py` → `cargo check` (even if Rust untouched) → wiring audit (every `#[tauri::command]` in `generate_handler!`, every `mod` declared, every route/IPC channel registered both sides).
**One full-suite run per code state.** The forbidden pattern is running the suite twice to learn failures the first run already printed. Canonical single run (names + counts, no tracebacks): `pytest tests/ -n auto --dist=loadgroup -q --no-cov --tb=no 2>&1 | tail -40`. Never `tail -5`/`head`/`grep` it into partial output; use `--lf` (failed-only replay) or targeted per-file runs for follow-ups.
**Manual verification (mandatory before packaging).** Boot like a user (`npm run tauri:dev`, `xvfb-run` if headless), drive the UI like a tester, screenshot evidence. No evidence = not verified. Record in `worklog.md` (`## Validation Performed`); if the GUI truly can't run, record the exact error under `## Known Limitations` and cover via suite.
**Browser automation:** drive the running app as a manual tester (launch, click main flows, screenshot). No "manual verification passed" without evidence.

---

# Hard "Don'ts" (HIGHEST PRIORITY)

Single source of truth for prohibitions. Overrides `PROMPT.md`, `MERGE-SESSIONS.md`, `VERIFY.md`, fix/commit docs, and every sub-agent (embed relevant rules in their prompts). A task conflicting with a rule here is SKIPPED + logged (`SKIPPED: <id> Conflicts with AGENTS.md Hard "Don'ts": <C-ID> (<summary>)`). **Only the user edits these rules, except agent ADDs via Learn-and-teach above** (recommend other changes in `worklog.md`/chat instead).

---

## Category: Tray Menu & Application Close

```
C-TRAY-1
Rule: Do NOT add a "Repaste Last transcription" button to the tray menu.
Rationale: The tray menu is intentionally minimal.
Applies to: All agents, all modes.
```

```
C-TRAY-2
Rule: Do NOT add a "Undo Last" button to the tray menu.
Rationale: The tray menu is intentionally minimal.
Applies to: All agents, all modes.
```

---

## Category: UI & UX

```
C-UI-1
Rule: Do NOT write vague or verbose user-facing copy. Every string must name its actual state, precisely and concisely (e.g. "No speech model is selected. Open Models to choose one.", never "No models are available"; Help control = "Help Overlay", key `help.openHelp`, all locales — never "Open this help overlay").
Rationale: Ambiguous copy misleads about real state and generates false support load; verbose labels were shortened app-wide.
Applies to: All agents, all modes, all sub-agents.
```

```
C-UI-2
Rule: Do NOT give sidebar parent groups an active BACKGROUND when their submenu is open. Leaf = `bg-surface` + `text-foreground`; open parent = stronger text only (`text-foreground`), never a third background.
Rationale: Parent backgrounds compete with the active child.
Applies to: All agents, all modes, all sub-agents.
```

```
C-UI-4
Rule: Do NOT space flex/grid children with margins or `space-y/x-*`. Inter-child spacing is parent `gap-*` only. Margins allowed only: outer-edge spacing with no parent gap, inline-text `mr/ml`, documented alignment nudges, non-flex parents.
Rationale: Margins leak/collapse/fragile on reorder; `gap` is the self-contained RTL-safe contract (migrated app-wide 2026-09-03).
Applies to: All agents, all modes, all sub-agents.
```

```
C-UI-5
Rule: Do NOT render a conditional status readout where appearing/disappearing displaces a persistent control. A readout that exists only while an action runs (countdown, pulsing dot, "recording" word) goes into space that is ALREADY reserved: move the always-on readout to the row above and put the transient one in the vacated trailing slot, so starting/stopping never moves a button. Pin the order with `compareDocumentPosition`, not a class-only assertion.
Rationale: The mic test card's "Recording… 00:0N / 00:10" line was inserted between the level bar and the buttons, so Start Test pushed the buttons down (user report 2026-10-16).
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Focus Indicators & Keyboard Accessibility

```
C-FOCUS-1
Rule: Do NOT remove/hide/disable focus indicators anywhere (no `outline: none`, no conditional ring removal). WCAG 2.4.7 Level A requires them.
Rationale: #1 accessibility antipattern; keyboard/AT users have no cursor equivalent.
Applies to: All agents, all modes, all sub-agents.
```

```
C-FOCUS-2
Rule: Do NOT drop the focus ring below full `ring-ring` opacity. Primitives keep `focus-visible:ring-ring`, pinned by `focus-ring-contrast.test.tsx` (a 30% ring composites to 1.15–2.45:1, invisible everywhere).
Rationale: A prettifying edit broke WCAG 1.4.11 contrast in all 12 themes.
Applies to: All agents, all modes, all sub-agents.
```

```
C-FOCUS-5
Rule: Do NOT remove the ring or go thinner than `ring-1`. `ring-1` + full opacity is pinned by `focus-ring-contrast.test.tsx` per user decision 2026-09-15 (meets AA 2.4.7, knowingly below AAA 2.4.13 — owner's aesthetics call, do not "fix").
Rationale: Recorded so no session retunes it back.
Applies to: All agents, all modes, all sub-agents.
```

```
C-FOCUS-3
Rule: Do NOT rely on `:focus-visible` alone to hide text-input rings on mouse click (it matches on click AND keyboard for text boxes). Use pointer-modality tracking (`SearchField.tsx` pattern: `pointerdown` sets pointer-active → subtle border tint; Tab/Arrow → full ring).
Rationale: CSS alone cannot separate mouse from keyboard on text inputs.
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Localization & i18n

```
C-I18N-1
Rule: Do NOT add user-facing text without adding it to ALL 8 locales (`en/zh/hi/es/ar/fr/ru/de` under `renderer/src/i18n/translations/`, via `useT()`/`t()`/`mainT()`).
Rationale: Missing keys silently downgrade non-English users.
Applies to: All agents, all modes.
```

```
C-I18N-2
Rule: Do NOT paste English into non-English locales. Translate genuinely (tool/LLM) or record pending in `worklog.md`, never ship English under `ar.json` etc.
Rationale: Untranslated keys defeat the multilingual promise invisibly.
Applies to: All agents, all modes.
```

---

## Category: Branding

```
C-BRAND-1
Rule: Do NOT hardcode the app-name display string; always use `APP_NAME` (Python/TS/Rust constants). Locale files use `{appName}`, never literals (even `en.json`); prose comments avoid it too. Internal identifiers (`LausuConfig`, `LausuSingleInstance`, `Lausu.exe`) are exempt (OS/API names, not brand).
Rationale: Literals across 8 locale files + dialogs + backend turned one rename into hundreds of edits; `check_branding.py` exempts locales/comments so CI can't catch them.
Applies to: All agents, all modes. CI-enforced for non-locale, non-comment code.
```

---

```
C-ARCH-2
Rule: Do NOT reintroduce package-level test-patch indirection (`_pkg.X` lookups, custom module subclasses, package-attr patch targets) in `server_platform/`, `prewarm/`, `recording/`. Tests patch the OWNING SUBMODULE; cross-module names resolve via sibling module-object reads; `__init__.py` stays pure re-export (plus stdlib proxies where dotted patches require them).
Rationale: ~900 LOC of indirection took multi-session migration to remove (done 2026-08-26).
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Cross-Platform Behavior

```
C-CROSS-1
Rule: Do NOT apply freedesktop `.desktop` Exec quoting to Windows autostart lines. Windows builds commands with `subprocess.list2cmdline`; Linux/macOS use `_desktop_quote`. Platform-gate all path/quoting/shell helpers.
Rationale: Blind "hardening" baked doubled backslashes into the Run key and broke Windows logon for a month (PID 0, events 9707/9708); `Path.exists()` collapses `\\` so validation passed and self-heal never fired.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CROSS-2
Rule: Do NOT reorder `_enable_autostart_windows()` off Task-Scheduler → Startup-.bat → Run-key. That order is FIXED.
Rationale: The Run key's raw command line fails at logon while Scheduler (split fields) and .bat both work; Run-first strands standard-user machines.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CROSS-3
Rule: Do NOT change `autostart_launcher.py`'s logger off `logging.getLogger("voice_typer.server.autostart_launcher")`. Bare-script launch makes `__name__ == "__main__"`, which misses the file handler and drops every `[AUTOSTART]` line. (Same for `worker/__main__.py`.)
Rationale: `__main__` logging made autostart invisible in `lausu.log`.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CROSS-4
Rule: Do NOT validate Windows autostart entries with `Path.exists()` alone. Also check the raw string for the doubled-backslash malformation (see `_validate_runkey_command()`).
Rationale: `exists()` collapses `\\`, so the broken value passed validation and persisted forever.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CROSS-5
Rule: Do NOT remove `autostart_launcher.py`'s observability lines: the `starting (pid=...)` line, the `RESULT success|failure exit=N <duration>` line, and the unhandled-exception traceback.
Rationale: The user reads these to know whether logon autostart fired and why it failed (pythonw has no console).
Applies to: All agents, all modes, all sub-agents.
```

General lesson: cross-platform helpers with platform-specific semantics must stay platform-gated; "hardening" one OS blind breaks the others. Autostart changes must keep Windows (list2cmdline) / Linux (.desktop Exec) / macOS (LaunchAgent args) output shapes intact with `test_autostart*.py`, the mig15 installer tests, and `test_e2e_regression.py` green.

---

## Category: Dependencies & Supply Chain


---

## Category: CI/CD & Build Pipeline

Tauri workflows + Nuitka freezes are load-bearing and fragile (50+ runs to first green; evidence tags live inline in the workflow files). Diagnose root causes; never edit workflows as a first-line fix; keep Node-24 action majors and the freeze/test-gate/artifact/signing behavior as-is. Any required change needs a full re-run + user sign-off.

## Category: Data & Privacy

```
C-DATA-1
Rule: Do NOT add network calls outside 4 allowed categories: (1) user-configured consented cloud ASR/LLM providers; (2) auto-update/GitHub checks; (3) model downloads; (4) the offline-pack download from GitHub Releases (allowed regardless of the `offline_pack_consent` default — the toggle is UX, not this rule). All other egress (telemetry, tracking, phone-home) stays forbidden. Previously downgraded work citing the old wording must be re-audited and restored.
Rationale: The promise is "no unsolicited phone-home", not "no network ever".
Applies to: All agents, all modes.
```

---

## Category: Data Fetching & Caching

```
C-CACHE-1
Rule: Do NOT cache derived data without its raw inputs. Every snapshot holds fetch inputs + derived values atomically (e.g. Analytics: sample + config + usage + stats).
Rationale: Derived-only caching re-rendered zeros on revisit despite a warm cache.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CACHE-2
Rule: Do NOT revalidate fresh caches on mount or leave prefetch-then-mount showing empty. Fresh (TTL) → skip fetch; stale → background revalidate over visible cache; late prefetch hydrates via the mount effect. (TanStack staleTime + keepPreviousData semantics on ipcCache.)
Rationale: Unconditional mount fetches wasted saved IPCs; unhydrated prefetches left pages empty forever.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CACHE-3
Rule: Do NOT reset page state to zeros/empty on revisit when cache exists. Seed ALL state (data, samples, config, ref mirrors) from the snapshot so revisits first-paint previous values.
Rationale: Partial seeding showed zero stat cards and hid Share on every revisit.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CACHE-4
Rule: Do NOT prefetch without all four guards or as a caching replacement. Hover/focus prefetch must: (1) skip fresh cache, (2) single-flight across hovers+mount, (3) dynamic-import query code, (4) stay best-effort fire-and-forget into the SAME cache the mount reads.
Rationale: Unguarded prefetch multiplies IPCs; separate stores double the system.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CACHE-5
Rule: Do NOT let caches go stale silently or bypass TTL ad-hoc. Backend events (`transcription_final`/`history_changed`/`config_changed`), manual refresh, and mutations invalidate immediately; TTL constants live next to their cache keys.
Rationale: Caches without invalidation serve lies; scattered invalidation drifts.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CACHE-6
Rule: Do NOT conditionally mount action controls on data. Triggers like Share always render with `disabled` reflecting availability; loading swaps only the body for a skeleton, never unmounts actions or the whole page. (Loading headings add zero live regions.)
Rationale: Conditional Share hid it until data landed.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CACHE-7
Rule: Do NOT ship caching without its four regression tests: fresh-revisit zero-IPC first-paint, stale background revalidate, single-flight hovers, invalidation/failure paths intact.
Rationale: This regression returned once for lack of a pin.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CACHE-8
Rule: Do NOT adopt a query-caching library (TanStack/SWR/RTK) on local IPC without a written comparison proving it beats the module-level ipcCache + zustand seed on invalidation/dedup/prefetch, migration cost included. Re-evaluate if transport becomes HTTP/GraphQL or needs normalization/persistence/coordination.
Rationale: Needed semantics fit ~100 lines on existing infra (bridge already dedups); migration rewrites every hook for no user gain (E13).
Applies to: All agents, all modes, all sub-agents.
```

```
C-CACHE-9
Rule: Do NOT cache `get_model_status` outside `fetchSharedModelStatus` (`hooks/models/modelStatusCache.ts`, 30s TTL, single-flight, never writes invalid shapes). Disk actions invalidate explicitly: download/import expire before reload, delete rewrites `downloaded: false` now, select re-stats via TTL-bypassing `refreshModelStatus`. `downloaded: true` only from a real stat.
Rationale: Filesystem truth goes stale in seconds (out-of-band deletes); a cached `true` is a lie the STALE-ACTIVE guards catch.
Applies to: All agents, all modes, all sub-agents.
```

```
C-CACHE-10
Rule: Do NOT fail first loads mid-boot or stack waits on waits. Pre-first-success idempotent reads wait-for-ready with deadline (bridge cold-start wait, currently 360s); writes never wait; post-success failures fail fast as before. Mount re-races fire only on FAST failures (inside `MOUNT_RERACE_FAST_WINDOW_MS`).
Rationale: Mid-boot pages error-screened instead of waiting (gRPC wait-for-ready pattern); the re-race stays as fast-refusal backstop only.
Applies to: All agents, all modes, all sub-agents.
```

## Category: Component Lifecycle & Motion

```
C-LIFE-1
Rule: Do NOT remount on navigation/data updates via unstable identity (data/route `key=`, render-local component definitions, branch-swapped subtrees). New data updates the mounted node (asserted by rerender-identity tests).
Rationale: Reconstruction replayed zero-size first frames despite cached data (heatmap pop-in).
Applies to: All agents, all modes, all sub-agents.
```

```
C-LIFE-2
Rule: Do NOT let measured components (ParentSize/ResizeObserver/fluid) size from a zero first frame. Reserve geometry declaratively (aspect-ratio + min-height matching content math) so reservation fills instead of pushing the page.
Rationale: ParentSize is 0×0 by contract; reservation turns 100px shifts into ≤12px corrections.
Applies to: All agents, all modes, all sub-agents.
```

```
C-LIFE-3
Rule: Do NOT let skeletons omit below-the-fold sections. Every skeleton reserves every dynamic block with matching geometry so skeleton→content never grows the page.
Rationale: Skipping the heatmap card grew the page on every load.
Applies to: All agents, all modes, all sub-agents.
```

```
C-ANIM-1
Rule: Do NOT transition auto heights or use `transition-all`. Post-paint show/hide uses shared `.collapse-root` 0fr→1fr grid animator via `data-open` (wrapper stays mounted). Initial content paints instantly, never animated.
Rationale: Auto-height transitions are no-ops; `transition-all` animates unintended properties.
Applies to: All agents, all modes, all sub-agents.
```

```
C-ANIM-2
Rule: Do NOT pop async content (banners, probes) into layout or slide it. Arrivals use opacity-only `.mount-fade` (150ms). Page-content mount animations forbidden (cached pages paint instantly).
Rationale: Shifting content mid-read; fading whole cards reintroduces delay-feel.
Applies to: All agents, all modes, all sub-agents.
```

```
C-ANIM-3
Rule: Do NOT rely on the app-wide `*` reduced-motion kill-switch for class utilities (`*` is specificity 0,0,0 and loses to any class — verified). Every motion utility carries its own `@media (prefers-reduced-motion: reduce)` override AFTER its base + a test asserting it.
Rationale: Without scoped overrides, reduced-motion users get every animation.
Applies to: All agents, all modes, all sub-agents.
```

```
C-LIFE-4
Rule: Do NOT claim a lifecycle/animation fix without UI or test evidence: rerender-identity + first-paint-reservation assertions + related suites green. Source reading never proves mount behavior.
Rationale: A data-path green hid a remount regression for lack of mount assertions.
Applies to: All agents, all modes, all sub-agents.
```

## Category: Testing & Baselines

```
C-TEST-5
Rule: Do NOT put tests inside production files. Python → `tests/`; Rust → sibling `tests.rs` via `#[cfg(test)] mod tests;` (no inline `#[test]` blocks); frontend → `*.test.*`/`__tests__/`. New module tests go in the module's test file.
Rationale: Inline tests bloat files and get lost/miswired on splits (3183-line `logging.rs` carried 89 inline tests).
Applies to: All agents, all modes, all sub-agents.
```

```
C-TEST-6
Rule (CLOUD-SANDBOX AGENT RULE): Do NOT package (`changes.zip`), close, or complete while the code state lacks a recorded GREEN full run: entire pytest + vitest suites plus `cargo check` + `typecheck:ci` + `pytest --collect-only`, 0 failed/errors, at exactly (1) session baseline, (2) every Implementation-Wave merge, (3) FINAL DELIVERY GATE on the exact final state (any edit voids it). 10-min ceiling is no excuse: background/detach with log redirect, or per-domain chunks whose collected counts sum to the `pytest --co` total. Sub-agents run focused tests only; the orchestrator aggregates. No manufactured green (skips/xfail/deletes/exclusions) — fix root causes. Record every run in `worklog.md` (command, counts, failing IDs or `0 failed`, OS). One full run per unchanged state (see the one-run rule above); re-run only on state change.
Rationale: Cloud sessions shipped "success" with red suites visible only in full runs the agent never executed.
Applies to: All agents, all modes, all sub-agents.
```

```
C-TEST-7
Rule: Do NOT test the whole frontend. New renderer tests target: user-visible behavior, critical flows (recording/downloads/consent/onboarding/mic-fallback/save), cross-layer contracts (IPC/i18n/branding/config/error codes), a11y, pure-logic units, shipped-bug guards. No snapshots, source-text pins (where behavior tests cover), duplicates, infra trivia, pixel/layout pins, or wrapper matrices. Structural pins allowed only for documented user decisions (`C-*`, NEVER-DOWNGRADE, explicit UX contracts).
Rationale: 2026-09-25 audit (347 files/~3166 cases): structural pins force 2x edits per UI change with zero protection; 11 dead files + ~100 brittle cases deleted with zero coverage loss.
Applies to: All agents, all modes, all sub-agents.
```

```
C-TEST-8
Rule: Do NOT let any test touch REAL user model caches. All tests run under the `_isolate_shared_hf_cache` autouse fixture (tmp redirect; opt out only via `real_shared_hub` for resolver-behavior tests that never write). Production resolves locations only via `model_availability` helpers (single redirectable seam); never hardcode cache paths. Model-touching tests must prove the real cache byte-identical after.
Rationale: An unredirected test deleted a real downloaded model (2026-09-26); per-test mocking leaked, only default-hermetic isolation closes the class.
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Code Style & Naming

```
C-STYLE-1
Rule: Do NOT add task/session/ticket IDs to code (names, files, comments). Prefixes live only in `review.md`/`SUMMARY.md`/`worklog.md` (also PROMPT.md R21h, VERIFY.md M12).
Rationale: Transient IDs become permanent noise.
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Local Tauri Dev (Windows, no MSVC)

```
C-TDEV-1
Rule: Do NOT assume `cargo tauri dev` needs MSVC and do NOT delete the GNU-toolchain plumbing. Tracked shim source `src-tauri/toolchain/linker_wrap.c` + `ensure_gnu_linkchain.py` regeneration + `tauri-dev.mjs --check` preflight + MSYS2 mingw64 + `stable-x86_64-pc-windows-gnu` + `gen_tauri_icons_stub.py` binaries are all required; never gitignore `src-tauri/toolchain/`. Dev recipe: `cd voice_typer/client && npm run tauri:dev` (Vite HMR :1420, then `tauri dev --config tauri.dev.conf.json` which blanks `beforeDevCommand` — the stock literal stays pinned in `tauri.conf.json`+mig19 for CI, do not "fix" it). Debug host defaults to the SOURCE sidecar (no env needed; explicit `0` forces release). No `python -m http.server` static servers, no raw `npx @tauri-apps/cli dev`.
Rationale: No Build Tools on this machine; one deleted 300KB untracked file once caused an unrecoverable `linker not found` outage.
Applies to: All agents, all modes, all sub-agents.
```

```
C-TDEV-2
Rule: Do NOT let the host `app.restart()` on sidecar `relaunch_app` in dev (`is_dev_mode()` in `lifecycle.rs::on_relaunch_app`). Dev host is the CLI's child: restart ends the CLI session and the job object reaps the relaunch — the whole app dies. Dev restarts the BACKEND via WS-close respawn; production keeps `app.restart()`.
Rationale: Tray → Restart murdered dev sessions (2026-08-30).
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Logging & Observability

```
C-LOG-1
Rule: Do NOT change the log line template. File: `YYYY-MM-DD  HH:MM:SS  LEVEL  msg` (two spaces, seconds-only, no T/tz, `WARN` never `WARNING`, no per-line session/thread/module). Session id appears once: trailing `session=xxxxxxxx` on the FIRST line's `[STARTUP] logging initialized` banner. Terminal: `HH:MM:SS  LEVEL  msg` (time only). Applies to Python formatters AND Rust (`util.rs`, `CombinedLogger`/`EarlyLogger`); ANSI is a wrapper (stripped SGR must equal the template byte-for-byte; palette shared across Python/Rust/`log-colors.mjs`, Rust test fails on drift; `NO_COLOR` > `FORCE_COLOR` > isatty; `tauri-dev.mjs` sets `FORCE_COLOR`, never drop it, never ANSI into files). Sole exception: opt-in `VOICE_TYPER_LOG_JSON=1` (UTC Z + millis for aggregators).
Rationale: The legacy ISO/tz/millis/session/thread/module-everywhere format was unreadable; pinned by `test_logging.py`, `test_log_formatting.py`, `util_tests.rs`.
Applies to: All agents, all modes, all sub-agents.
```

```
C-LOG-2
Rule: Do NOT drop the space-separated `<duration>` suffix on timed-operation completion lines. Produced by `format_duration()` (` 2.3s`, ` 1m 2.3s`, leading space included — callers use bare `%s`, never `took=`/`--`). Mid-line only for the recording line (`Recording stopped 30.0s of audio, ...`). Source is always `time.perf_counter()` diffed at the log. Grep anchor: `\d+(m \d+)?\.\ds$` at line end.
Rationale: At-a-glance performance in logs (user request 2026-08-08, space form 2026-08-15); ad-hoc formats can't be grep-summed.
Applies to: All agents, all modes, all sub-agents.
```

```
C-LOG-3
Rule: Do NOT add per-frame/per-request/per-IPC DEBUG wire traces (no `RX frame type=` / `TX response id=` or partial quiet-lists). Routine IPC chatter stays out of logs entirely; lifecycle/auth/errors/rate-cap/shutdown keep INFO/WARN/ERROR. Pinned by `test_no_ipc_wire_trace_logs.py`.
Rationale: Per-frame dumps drowned real signals; quiet-lists only moved the noise (user decision 2026-09-30).
Applies to: All agents, all modes, all sub-agents.
```

```
C-LOG-4
Rule: The app-starting banner stays the FIRST identity line, `|`-separated (`{APP_NAME} starting | model=... | hotkey=... | ...`), at most once per process, emitted from light `startup_banner.emit_app_starting_banner()` right after `_setup_logging()` (before the heavy app import). Never `--`-separated, never after IPC chatter, never moved back into `app_construction`. Anchors: `starting | model=`.
Rationale: The banner lagged ~5s behind IPC chatter, looking like a mystery stall (user decision 2026-09-30).
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Design System Synchronization

```
C-DESIGN-1
Rule: Live project (`renderer/`) and root `design-system.html` stay in perfect sync BOTH directions in EVERY change. Never ship/commit/report one side without the other.
Rationale: A drifted showcase misleads reviewers; an isolated showcase invents unshipped styles (user decision 2026-09-23).
Applies to: All agents, all modes, all sub-agents.
```

```
C-DESIGN-2
Rule: Do NOT hand-pick border opacities or use one weight everywhere. Fixed scale: 8% default (cards/panels/dividers/chips/dialogs/control tracks; card outline == its dividers), 10% toasts + active sidebar row, 15% keycaps + checkboxes, 20% dashed mock frames. 5% is a FILL (`bg-border/5`, ToggleGroup track `bg-border/6`), never a border. One class for both schemes (`border-border/8`; alpha in consumer, never in `--border`); `dark:` variants only when percentages genuinely differ (Button base is the sanctioned case). The ToggleGroup track's 1px `#000`/10 `shadow` ring is exempt by design — do not "fix" it.
Rationale: Mixed 5%/10% borders disagreed everywhere and 5% outlines read borderless in dark (user decision 2026-10-02).
Applies to: All agents, all modes, all sub-agents.
```

```
C-DESIGN-3
Rule: Do NOT express a base-relative surface as a literal palette step. Derive from the base (`var(--base)` / `color-mix(in oklch, var(--base) N%, black)`) because presets override a FIXED token set and never derived tokens (a literal inverts on darker/lighter presets). Literals only for deliberately palette-independent surfaces. Lock with a test that fails on the literal.
Rationale: A literal sidebar rail inverted on 9 of 11 dark presets; derivation keeps it one step below canvas everywhere (pinned by `index-css-sidebar-rail-token.test.ts`).
Applies to: All agents, all modes, all sub-agents.
```

```
C-DESIGN-4
Rule: Type scale is Tailwind's steps plus exactly one app addition: `text-xs-plus` (13px, `--text-xs-plus` theme keys — real utility, never `text-[0.8125rem]`/`13px` literals). Further steps need a `--text-*` key + `design-system.html` + `DESIGN-SYSTEM.md` in the same change (C-DESIGN-1). Only sanctioned literals: `StatsShareImage.tsx` (px-based export, token-free by design). Guarded by `index-css-type-scale.test.ts`.
Rationale: 13px existed unnamed in five places and drifted per file (user decision 2026-10-10).
Applies to: All agents, all modes, all sub-agents.
```

```
C-DESIGN-5
Rule: Do NOT shape a corner with a bare `border-radius` on a surface that paints its own radius (a vendored component's panel, a third-party widget like sonner's toast `<li>`, any inline `border-radius`): the squircle corner-shape is applied BY CLASS (`:where(.rounded-lg)` inside `index.css`'s `@supports (corner-shape: squircle)`), so such a surface must ALSO carry `rounded-lg`. Never compensate by adding an attribute/element selector to that gate.
Rationale: The vendored picker panel and the sonner toast both painted `--radius-lg` but missed `corner-shape` — a plain superellipse(1) corner at 26px while every card renders superellipse(2).
Applies to: All agents, all modes, all sub-agents. Guarded by `date-range-picker-card-look.test.ts` and `sonner-toast-squircle.test.tsx`.
```

## Category: Models Page UI

```
C-MODELS-1
Rule: Do NOT let model-size Download buttons fit content, center content, or use 16px icons. Fixed `w-24` (`DOWNLOAD_SIZE_BUTTON_WIDTH`), left-aligned (`DOWNLOAD_CONTENT_ALIGNMENT`, overriding the centered Button base), `h-3 w-3` icon (`DOWNLOAD_ICON_CLASS`), `formatModelSize` normalization (`75 MB`, never `~`). "Download Deps" (a label) is width-exempt but keeps alignment.
Rationale: Content widths misaligned rows; 16px icons dominated 11px text.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MODELS-2
Rule: Do NOT flatten model-card metadata into one uniform gap. Two groups: info (`MetadataPair`s, `gap-x-3`) + labels (`MetadataTag`s, `gap-x-1.5` in their inline-flex wrap). Keep `gap-x-3` between the WER pair and the first label.
Rationale: Uniform gaps broke the two-group reading.
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Sidebar & Title Bar

```
C-SIDEBAR-1
Rule: Do NOT brand the sidebar (no `Logo`, no `APP_NAME`). Sidebar is NAV-ONLY: first child is `<nav aria-label="Main navigation">` filling full height. Pinned by `SIDEBAR-BRANDING` tests.
Rationale: The header stole reserved height above the nav (removed 2026-08-22).
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-2
Rule: Do NOT render the same control in two surfaces. Every control has exactly one home; adding it to a second surface (sidebar, footer, page header, dialog) fragments the single source of truth — reuse the shared component in place instead. Pinned example: the theme switcher lives ONLY in the title bar (icon-only `ThemeSwitch` in the window-control cluster: left of min/max/close, right edge on macOS), never duplicated elsewhere.
Rationale: Duplicated controls drift (icons, labels, behavior) and desync state; the title-bar home was decided 2026-08-22.
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-3
Rule: Do NOT reimplement theme state for the title-bar control. It is the shared `ThemeSwitch` (icon-only, no text) on App.tsx's `themeMode`/`onThemeChange`; current/next modes surface only via `title` + `aria-label`. Cycling logic, store, save, and Light/Dark/System semantics stay shared.
Rationale: Parallel implementations drift and desync persisted config.
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-11
Rule: The Settings submenu used to be open EXACTLY while a Settings page was current (no manual preference, no persistence). Refined by C-SIDEBAR-17 (parent click now toggles closed in place); where they conflict, C-SIDEBAR-17 governs.
Rationale: Navigation as single source of truth replaced a stuck-open manual flag (2026-08-24).
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-12
Rule: Do NOT let sidebar icons shift on expand/collapse or center them per-state. One anchored column (container `p-2` + uniform 1px Button border + button `px-2` = 17px from edge, both states); collapsed rail `w-12` keeps it centered. Never `justify-center`/per-state padding.
Rationale: Per-state wrappers made icons jump every toggle (a11y-bounds verified). (Supersedes the older C-SIDEBAR-4 arithmetic; INVARIANT unchanged: identical x-position both states.)
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-5
Rule: Do NOT instant-hide/unmount/branch-swap sidebar labels on collapse. Labels animate via shared `navTextClasses` (`max-width` + `opacity` + RTL-mirrored inline-start `translate` + explicit `blur-[0px]`/`blur-[4px]` endpoints — never `filter-none`), synced with the 200ms width transition; headings collapse via `max-height`+`opacity`; rows clip with `overflow-hidden`.
Rationale: Snapping text + jumping groups replaced one coherent motion model (2026-08-24).
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-6
Rule: Do NOT flatten the sidebar's two-scale rhythm: `gap-1` inside groups; `gap-5` expanded / `gap-2` collapsed between groups (collapsed headings at `max-h-0` still contribute flex gaps → 16px clusters vs 4px items).
Rationale: Flat gaps made a compressed rail with 24px voids (2026-08-24).
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-8
Rule: Do NOT build expand/collapse via per-state button trees. One shared element tree both states (leaves always in `HotkeyTooltip`; Settings always in one `Popover.Root`, content-only branches). Wrapper-type swaps remount buttons and kill transitions.
Rationale: Per-state trees snapped labels and dropped accessible names.
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-9
Rule: Do NOT custom-border active sidebar pages. Active leaf/submenu-child: `border-border/10` (one step above the 8% card border) + `bg-surface` + `text-foreground`; no `border-s-2`/transparent alignment borders (removed). The open Settings PARENT gets calm foreground only (`text-foreground` + `font-medium` + hover), never card border/background.
Rationale: Competing borders; parent must not outshine its active child (supersedes UX-16).
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-10
Rule: Do NOT swap the Settings arrow glyph. One persistent `ArrowRight01Icon` in a far-end (`ms-auto`) `size-6` wrapper; direction is rotation only (`rotate-90` open, `nav-directional-icon` closed, `transition-[rotate]` — never `transition-transform`, which animates the RTL mirror). Expanded sidebar only (collapsed uses the flyout).
Rationale: Conditional glyphs popped; rotation is the app convention.
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-17
Rule: Do NOT derive the Settings submenu purely from the page or keep multiple truths. One `submenuOpen` state, three transitions: parent click toggles (open→closed in place, no nav; closed→open + navigate default); entering Settings reveals via sync effect; leaving closes. No persistence, no timeouts. Closed-on-active-page → parent carries `aria-current="page"` + the tab stop. (Refines C-SIDEBAR-11's derived model, whose parent click was a no-op.)
Rationale: Click must deterministically toggle against nav sync (2026-08-25).
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-13
Rule: Do NOT remount nav buttons on toggle. Same wrapper element type both states (leaves always `HotkeyTooltip`-wrapped; Settings always one `Popover.Root`). Labels animate via `navTextClasses` only, never `display:none`/unmount.
Rationale: Wrapper swaps remount buttons; transitions don't run on fresh mounts.
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-14
Rule: Do NOT pin the System group to the bottom with spacers/heights/gaps. `mt-auto` on its `<section>` inside the `min-h-full flex-col` nav (collapses to 0 + scroll on short windows).
Rationale: Layout-structure hierarchy stays stable across sizes and states.
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-15
Rule: Do NOT split About & Privacy back into two pages. One destination: `aboutAndPrivacy` literal/route/`AboutAndPrivacy.tsx`/`nav.aboutAndPrivacy` ("About & Privacy"), `ShieldUserIcon` (never warning-semantics glyphs). Old `about`/`privacy` literals stay removed.
Rationale: Two thin pages read as one story; duplicates are navigation defects.
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-16
Rule: Do NOT make the collapsed Settings flyout keyboard-hostile. Flyout children keep natural tab order (no `-1`; portal sits outside roving scope so Tab is the only path); collapsed trigger keeps `tabIndex=0` even on active sub-pages.
Rationale: Hard-coded `-1`s left sub-pages keyboard-unreachable (WCAG 2.1.1).
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-18
Rule: Do NOT swap/unmount/branch-replace sidebar elements at toggle time. The Collapsible renders unconditionally (`open={submenuOpen && !collapsed}`) so collapse animates in sync; the flyout Portal is additive; the chevron fades (`opacity-0 pointer-events-none`) instead of unmounting; headers use the label text-motion model (max-height container + inner `navLabelMotion` span, text 150ms vs container 200ms so clips never half-cut glyphs).
Rationale: Branch swaps unmounted open submenus instantly and clipped headers mid-transition.
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-19
Rule: Do NOT write verbose Back/Forward tooltips. Exactly `Back`/`Forward` (localized to each locale's `a11y.goBack`/`goForward` root) + shortcut chips via `HotkeyTooltip`. The `*WithShortcut` keys stay removed.
Rationale: Mechanism wording duplicated noise across 8 locales; chips already carry shortcuts.
Applies to: All agents, all modes, all sub-agents.
```

```
C-SIDEBAR-20
Rule: Do NOT restore the three-group hierarchy. Two groups: header-less top (Home, History, Analytics, Models, Templates, Vocabulary; `nav.group.power` stays removed) + bottom-pinned System (Settings, Microphone, About & Privacy). (Supersedes the C-SIDEBAR-7 order.)
Rationale: The split left a two-item delta and a heading adding no information (user decision 2026-08-25).
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Sound Cues

```
C-SOUND-1
Rule: Do NOT add a success/complete audio cue (`transcription_final` or any success path). Lifecycle audio is `start` + `stop` + `error` only (`SoundCueKind`, no `"complete"` kind/entry/call; Settings previews only start/stop). The visual `onVisualCue("complete")` mirror stays allowed.
Rationale: A success chime interrupted focus after every dictation with zero information (user decision 2026-09-13).
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Homepage Status Pill & Description Synchronization

```
C-HOME-1
Rule: Do NOT derive the Home pill and its description line from different truths. Both come from one `{recordingState, lastError}` pair written TOGETHER by `applyStatusWithReason` (`hooks/useConnection.ts`) on EVERY sync path (`status_change`, connect-time `state_changed`, both `get_status` catch-ups); `statusKeyFor` (`pages/home/lib/status.ts`) shows ERROR only when the description shows an error.
Rationale: Split paths made the "no model" error intermittent (appeared only on live pushes, vanished on launch/reconnect).
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Homepage Transcription Preview (removed, must not return)

```
C-HOME-2
Rule: Do NOT reintroduce a transcription preview surface on Home (no last-text card/panel/toast with Copy/Undo/Re-paste/Discard, no `LastTranscriptionPreview`/`useLastTranscriptionPreview`/`quality.ts` detector/`LAST_TEXT_AUTO_CLEAR_MS`, no `home.copy/undo/repaste/discard/lowConfidenceWarning/redictate*` keys). Home shows mic button + status + stats; `transcription_final` celebrates first runs + refreshes stats, never renders text. (`undo_last`/`repaste_last` commands, hotkeys, and `TranscriptionQualitySummary` STAY — backend/History behavior, not the card.)
Rationale: The card duplicated History, exposed dictated text, and invited scope creep (user decision 2026-09-13).
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Persistence & Data Files

```
C-PERSIST-1
Rule: Do NOT flatten/merge the vocabulary model. `vocabulary.json` stores USER diffs only (vs bundled `corrections.json`) + `_deleted` tombstones; bundled entries are never duplicated in. The merged view is `bundled + user − _deleted`; a `_deleted`-only file is correct. The 6 category buckets are the persisted layer (UI flat list is presentation via `detectCategory`); removing them requires migrating `apply_to_text`, usage tracking, and diff-save.
Rationale: Every bucket is consumed by apply/usage/save; the flat UI is not a schema.
Applies to: All agents, all modes, all sub-agents.
```

```
C-PERSIST-2
Rule: Do NOT merge `correction-usage.json` into `vocabulary.json`. Independent analytics (per-(category, original) counts + per-day totals) with its own producer/lifecycle (debounced writes, 90-day prune, prune-on-delete), not vocabulary data.
Rationale: Merging couples independent lifecycles and corrupts both stores.
Applies to: All agents, all modes, all sub-agents.
```

```
C-PERSIST-3
Rule: Do NOT remove `recovery.json`. Active crash-recovery store (last unpasted transcriptions; pipeline `add()` gated by config, startup `check_on_startup()`, diagnostics export). Empty `{"entries": []}` is the normal state, not obsolescence.
Rationale: Live end-to-end (write → startup notify).
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Microphone Selection & Consent Flow

```
C-MIC-1
Rule: Do NOT preselect any mic on first use. `config.microphone` defaults `null` (= System Default) and every consumer treats `null` as OS default, never error/coerced device. Only onboarding + explicit user selection may write it.
Rationale: Nothing may auto-populate the selection.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-2
Rule: Do NOT silently overwrite a lost mic with `Unknown`/another device. Unmatched persisted ids resolve via shared resolvers (`find_microphone_by_id` / `resolve_mic_id_to_device_index`, stable `"<hostapi>|<name>[#N]"`, legacy shapes still resolve); genuine misses fall back to System Default WITH visible feedback (snackbar + banner), never silent mislabel.
Rationale: Raw-index persistence went stale across reboots and rendered "Unknown".
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-3
Rule: Do NOT nag with persistent consent banners. Consent-gated features use the just-in-time `openConsentGate()` + single `ConsentGateDialog` (App.tsx) at action time, `onAllow` continuing the action. Always-visible consent lives only in Settings rows + onboarding ConsentStep. No feature-specific modals.
Rationale: Point-of-use preserves GDPR Art. 9 without nagging users who never act.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-4
Rule: Do NOT invent one-off controls where a shared pattern exists. Pick the app's established interaction language (shared primitives/components) instead of bespoke selects, multi-selects, or custom dropdowns. Pinned example: mutually exclusive quality presets use the shared accordion+RadioGroup (`PresetAccordionSelector`), never a Microphone-page dropdown. Test duration stays fixed at `MICROPHONE_TEST_DURATION_SEC` (10s), not user-configurable without a product reversal.
Rationale: One-off controls drift from the design system and duplicate state handling; shared patterns inherit fixes (focus, a11y, RTL) automatically.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-5
Rule: Do NOT filter invalid devices in the UI. Placeholders (`Input ()`, blank names, label-only entries) are filtered at the enumeration source (`_is_invalid_device_name` in `remote_session.py` → `list_microphones`) so tray/recorder/tests/renderer agree.
Rationale: Renderer-only filters leave bogus devices selectable elsewhere.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-6
Rule: Do NOT restyle the Microphone page off-system. Standard tokens (`border-border/8`, `bg-surface-subtle`, foreground/muted); RadioGroup rows, System Default first; no blue full-card borders, no per-row action buttons, no channel/rate metadata, one section-label treatment.
Rationale: Keeps the page inside the design system.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-7
Rule: Do NOT dedupe mics by display name or reintroduce per-host-API duplicates. `list_microphones()` returns the canonical host-API view (Windows WASAPI, macOS Core Audio, Linux PulseAudio; unfiltered fallback when it enumerates zero). Same-name records WITHIN it are distinct devices (`#N` ids).
Rationale: PortAudio exposes every endpoint per API (17 records hid 3 real devices); upstream recommends one-API display; MME truncates at 31 chars.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-8
Rule: Do NOT hide legitimate mics (virtual/USB/Bluetooth/similar names) as "hygiene". The canonical view equals the OS input list 1:1; extra filtering risks hiding the user's device.
Rationale: See C-MIC-2.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-9
Rule: Do NOT collapse System Default into its current physical device or drop it from any surface. It is a separate follow-the-OS semantic, additive alongside physical devices.
Rationale: Collapsing freezes the user to one device.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-10
Rule: Do NOT add a second mic-enumeration path. Every surface (page, tray, onboarding, future) consumes `list_microphones()` via `app._microphones` / `tray.set_microphones`; tray is pure pass-through. No consumer-local `sd.query_devices()`.
Rationale: Single chain killed tray/page divergence (audit-pinned).
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-11
Rule: Do NOT print option descriptions permanently in the Quality selector. Descriptions live behind shared `InfoTooltip` (beside section label + per row). No second tooltip primitive, no duplicates, no header-value info icon.
Rationale: Always-visible paragraphs tripled component height and repeated copy.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-12
Rule: Do NOT style the LevelBar fill beyond solid `bg-primary` on neutral `bg-border` track (flush full-height `scaleX`; clipping via ⚠ + aria, never fill color). The rAF loop writes transform ONLY, never `backgroundColor`.
Rationale: Ladders/borders diluted the fill; the hook color fn duplicated logic (E7).
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-13
Rule: Do NOT badge selection state redundantly (no "Selected microphone" pill). Radio list + card context + aria already communicate it; Stop button + countdown + live feedback cover recording state.
Rationale: Redundant labels drift from real state.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-14
Rule: Do NOT regress the Quality selector contract: header info icon inline beside the label INSIDE the trigger (`InfoTooltip triggerAs="inline"` span — never absolutely-positioned overlays, never nested `<button>`s); rows are `[title + info] … [radio far right]` with radio first in DOM, visual-last via `order-last ms-auto`; single horizontal padding (shared `px-4`, rows carry none); concise labels (tooltips only); LevelBar keeps rounded caps at every level (counter-scaled radius) while rAF writes transform only.
Rationale: Overlay icons migrated mid-animation, radios/padding drifted, scaleX squashed caps.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MIC-15
Rule: Do NOT regress the Quality selector's COMPACT SINGLE-ROW header: one trigger row, left `[label + inline ?]`, right `[value chip (non-interactive span, `mic-preset-current`) + rotating chevron]` (`ArrowDown01Icon`, `group-data-[state=open]/accordion-trigger:rotate-180`, never swapped glyphs — distinct from the models-row right→down idiom, do not "unify"). Primitive glyph off ONLY here via `disclosure={false}` (it now renders in the trailing slot; the old CSS-hide can't reach it). Value chip is a span (SelectTrigger shell), never a button. Options container: exactly one `px-2` inset. No two-line header, no `+` glyph, no edge-touching content.
Rationale: One-line header halved collapsed height; per-instance hide preserves the shared glyph for Models accordions.
Applies to: All agents, all modes, all sub-agents.
```

```
C-REVIEW-1
Rule: Do NOT touch findings with status `🚫 Won't Fix` (they live in `WONT_FIX.md`, never `review.md`) or change their status. Task ranges including them are SKIPPED with the standard record.
Rationale: Permanent owner decisions (confirmed 2026-08-30); re-solving risks the documented behavior/security/user impact.
Applies to: All agents, all modes, all sub-agents.
```

```
C-REVIEW-2
Rule: Do NOT file non-fixable findings in `review.md` (active queue only). Unworthy problems go to `WONT_FIX.md` with `🚫 Won't Fix` + rationale. Agents never move fixable items to Won't Fix (user reverses manually).
Rationale: Keeps the fix queue token-cheap and re-fix-proof.
Applies to: All agents, all modes, all sub-agents.
```

---

## How to add / edit constraints

Add a full-block constraint under the right category (or a new `## Category:` header). Save; next sessions read it at start.

**Template:**
```
C-<CATEGORY>-<N>
Rule: <one-sentence "Do NOT..." prohibition>
Rationale: <1-2 sentences>
Applies to: <agents / modes>
```

---

## Audit trail

Constraint skips go in `worklog.md` (cloud) or the chat report (local):
```
SKIPPED: <task/finding ID> Conflicts with AGENTS.md `Hard "Don'ts"`: <C-ID> (<one-line summary>)
```
Grep `SKIPPED:` to see every deferral (basis for relaxing constraints later).

---

## Review.md High Priority admission (permanent, append-only, never weakened)

Every `## High Priority` task must be: (1) **evidence-based** (error text, `file:line`, or reproduced observation — never stale claims at face value); (2) **high-impact** (real user/infra failure or opportunity, why-it-matters stated); (3) **clearly scoped** (bounded problem, concrete outcome, fix direction where known); (4) **non-redundant** (no dupes of entries/fixed behavior/sibling tasks — cross-reference overlaps). Favor high product impact with minimal file overlap between parallel agents. **Won't Fix findings are never re-admitted** (user reverses manually).

---

## Category: Configuration Canonicality & Microphone Startup Reconciliation

```
C-CONF-1
Rule: Do NOT create a second settings source of truth. `config.json` (via `Config`) is canonical; every producer/consumer (UI, backend, tray, onboarding, autostart) reads/writes through it. No renderer-local authority, no host-side direct writes.
Rationale: Parallel stores drift silently; renderer already gets authoritative `get_config` + `config_changed` pushes.
Applies to: All agents, all modes.
```

```
C-CONF-2
Rule: Do NOT validate `config.microphone` on the Microphone page only. Startup reconciles it against live enumeration (`_reconcile_configured_microphone` in `startup_tasks.py` ← `load_microphones`); the page renders reconciled state, its mount check is only a hot-unplug net.
Rationale: Page-only checks let stale selections survive restarts into noisy recovery.
Applies to: All agents, all modes.
```

```
C-CONF-3
Rule: Do NOT surface startup mic reconciliation to the user (no tray/snack). Stale → System Default is SILENT; trail is one WARNING line (stale id, device count, action). Valid devices log healthy at INFO, untouched.
Rationale: Stale ids are internal inconsistency, not user error; dialogs train dismissal of real errors.
Applies to: All agents, all modes.
```

```
C-CONF-4
Rule: Do NOT redefine `"microphone": null`. Null IS System Default end-to-end (validators, resolvers, Recorder, C-MIC-1). Never sentinel strings or persisted concrete defaults. Legacy id shapes resolving live migrate forward to stable `"<host api>|<name>[#N]"`.
Rationale: One representation keeps config/backend/UI/device in agreement.
Applies to: All agents, all modes.
```

```
C-CONF-5
Rule: Do NOT let runtime init overwrite valid persisted settings without an explicit migration/defaulting reason (corrupt quarantine, first-run defaults, versioned migration with .bak — all logged). Known edge: OLDER builds drop NEWER-schema unknown keys at next explicit save (warned once per process); dev + built runtimes share ONE profile (`~/.lausu`, single-instance mutexes prevent double-write — no profile splits or second locks without a product decision).
Rationale: Separates genuine bugs from documented downgrade edges; protects the single-profile architecture from "fixes".
Applies to: All agents, all modes.
```
```
C-MIC-16
Rule: Do NOT treat a valid concrete mic selection as failure. Resolved non-default devices open/monitor/test/record independently of the OS Default. `device_lost`/disconnect banners fire ONLY on real unavailability (stream finished while CURRENT, or N consecutive zero-chunks) — never on intentional stop/close during switches/unmounts (the level-monitor finished-callback stays identity-guarded).
Rationale: PortAudio fires finish-callbacks on EVERY inactive transition; unguarded, every switch showed "disconnected".
Applies to: All agents, all modes.
```

```
C-MIC-17
Rule: Do NOT return test WAVs inline over IPC (~1 MB each breaks the 1 MiB frame cap; backend logs success while the frontend times out). Stop responses carry `{path,bytes}` refs to `<config>/mic-test-recordings/`; renderer fetches via chunked `microphone_test_read_audio` (≤256 KiB binary slices). Never raise frame caps or re-serialize whole recordings; keep keep-only-latest purge on start.
Rationale: The dropped-frame failure is silent.
Applies to: All agents, all modes.
```

```
C-MIC-18
Rule: Do NOT make test duration configurable or render duplicate/conflicting test timers. Fixed `MICROPHONE_TEST_DURATION_SEC = 10`; exactly ONE readout (LiveQualityFeedback 00:00→00:10); the voice-quality status line stays removed; LevelBar owns level feedback; UI state derives from the real backend lifecycle, never faked.
Rationale: Duplicate timers + flickering states were noise; indefinite-looking buttons desync from backend auto-stop.
Applies to: All agents, all modes.
```

```
C-MIC-19
Rule: Do NOT break the post-recording pipeline: one canonical finalize path for auto/manual stop; `microphone_test_read_audio` stays CHEAP (cost 1 — full transfers are ~8 back-to-back ≤256 KiB reads against the shared burst budget, cost-30 starved them mid-transfer); visible timers cleared by unmount-only cleanup + sync lifecycle flag (never dep-driven effects); backend `success:false`/`"No test running"` after finalization is a benign silent no-op.
Rationale: Each clause fixes a shipped silent-failure (starved tails, frozen 00:00, swallowed results).
Applies to: All agents, all modes.
```

```
C-MIC-20
Rule: Do NOT fabricate transcription metrics without a model. Every non-transcribable path (including `models == None`) sets `transcription_unavailable` + `no_engine_loaded`; frontend renders explicit N/A (`microphoneTest.qualityNotApplicable`), never a numeric score from absent data. Audio analysis + raw playback never require a model.
Rationale: Ungated UI showed false "0% quality" for model-less users, misreporting working mics as failed.
Applies to: All agents, all modes.
```

```
C-MIC-21
Rule: Chunked base64 reassembly must slice on 3-byte-aligned boundaries (interior fragments carry no `=` padding). No unaligned interior slices (raw 256 KiB % 3 == 1), no oversized inline audio payloads, and multi-buffer byte logs name each buffer (raw vs filtered, never bare `N+N`).
Rationale: Mid-stream padding silently corrupted every multi-chunk playback; ambiguous logs read as duplication.
Applies to: All agents, all modes.
```

```
C-MIC-22
Rule: Do NOT surface device_lost for a transient mic-stream death without retrying the open first. Unexpected PortAudio stream death retries the open (bounded attempts, presence-checked, abortable by user stop); only a provably-gone device or exhausted retries emits device_lost.
Rationale: OS-side mic reconfigures (format/effects toggles) kill the stream with the device still present; instant banners stranded users in "Monitoring off" until they manually restarted.
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Privacy & Background Startup

```
C-BG-1
Rule: Do NOT let persisted navigation (last page) activate privacy-sensitive/resource-heavy capabilities while hidden (autostart `VT_START_HIDDEN=1`). Hidden restores of Microphone never start the level monitor; monitoring starts only when visible AND routed there. Hidden restores of Microphone redirect to Home (timed grace + deferred monitor start). Same invariant for any future auto-initializing sensitive capability.
Rationale: Off-screen autostart mounted Microphone and opened a continuous InputStream, lighting the OS mic indicator with no UI open. Fix is architectural (nav + visibility gates + `VT_START_HIDDEN` hide), not indicator-hiding.
Applies to: All agents, all modes, all sub-agents.
```

---

## Category: Shared Destructive Actions & Filter Consistency (2026-08-30 polish pass)

```
C-UI-9
Rule: Do NOT leave `Clear All` buttons muted-on-hover or permanently tinted. Muted at rest (`text-muted-foreground` + outline `border-border/8`, `variant="outline" size="sm"`); hover = solid destructive like `ConfirmDialog`'s confirm (`hover:border-destructive hover:bg-destructive hover:text-destructive-foreground` — never `hover:text-foreground`, never `bg-destructive/5` wash). Icon inherits `currentColor`; `gap-2` + `size-4` + `Delete01Icon` 2px; keep `focus-visible:ring-1 ring-ring`.
Rationale: Wrong hover tokens failed contrast (dark-on-red); permanent tints + washes never read as the destructive wipe; Favorites' warning tint stays distinct.
Applies to: All agents, all modes, all sub-agents.
```

```
C-FILTER-1
Rule: Do NOT let History/Vocabulary/Templates diverge on sort/filter buttons. All share `SortSelect` (`SelectTrigger size="sm" hideChevron`, muted→foreground hover, `Sorting01Icon`, `SelectContent popper/start`, `rounded-lg border-border/8 bg-surface`; dimensions/border/type/icon/spacing/hover/focus identical; `ms-auto` for RTL, never `ml-auto`). No History chevrons, generic surfaces, or `item-aligned` centering.
Rationale: History drifted (second chevron, wrong surface/placement); one primitive kills the class.
Applies to: All agents, all modes, all sub-agents.
```

```
C-MODELS-5
Rule: Do NOT render the Models `no-model` state as a centered `EmptyState`. Compact dismissible banner in normal flow (`mb-3` between summary and tabs, never centered `py-16`, never sticky): shared surface (`rounded-lg border-border/8 bg-surface-subtle`), `AiBrain03Icon` muted + `text-foreground` body, exact copy `models.noModelBanner` ("No speech model is selected. Select a model below.", all 8 locales, `role="status"` polite, `models-no-model-banner`), far-right close `X` (`Cancel01Icon`, sessionStorage `models:noModelBannerDismissed="1"`). Dismissal survives reloads/in-app nav within the session; guard with `if (lifecycle.config?.model_size)` (not `!== ""` — `undefined` cleared the flag on mount); cleared only on real selection or app close. `model_size === ""` logic untouched.
Rationale: The centered block ate ~120px and pushed cards below the fold; the tint was theme-foreign; the sticky overlay floated disconnected; the guard fixes the reload regression.
Applies to: All agents, all modes, all sub-agents.
```

```
C-SKELETON-1
Rule: Do NOT substitute one generic skeleton for page-specific UI. Every skeleton matches its page's structure/dimensions/spacing/hierarchy (same shells, card shapes, row counts, real-primitive-sized placeholders: Switch `h-5 w-11`, SortSelect `h-8`, checkbox `size-4`). Shared primitives in `feedback/skeletons.tsx`; each page composes its own `pages/<page>/components/*Skeleton.tsx` (updated with its page, same change). Only generic allowed: route-chunk `RouteSkeleton`. Dashboard skeleton stays `<section aria-busy>` (zero live regions at first paint).
Rationale: Generic skeletons rendered nonexistent shapes and shifted layout at swap.
Applies to: All agents, all modes, all sub-agents.
```
---

## Category: Comment Discipline

```
C-COMMENT-1
Rule: Do NOT let inline comments exceed ~10% of lines per top-level code dir (`server`, `client/src`, `src-tauri/src`, `scripts`, workflows; measure with `scripts/comment_ratio_metrics.py`). Self-explanatory code gets NO comment.
Rationale: 53% comment density buried contracts in narrative fluff; volume is maintenance cost.
Applies to: All agents, all modes, all sub-agents.
```

```
C-COMMENT-2
Rule: Do NOT write multi-paragraph inline comments. Surviving comments on non-obvious code: 1–3 lines, WHY (invariant/trap/contract), never WHAT.
Rationale: Essays go stale and hide the one-line contract.
Applies to: All agents, all modes, all sub-agents.
```

```
C-COMMENT-3
Rule: Do NOT put task/session/ticket IDs in code (comments, names, files). Prefixes live only in `review.md`/`worklog.md`/`SUMMARY.md` (see C-STYLE-1).
Rationale: Transient IDs become noise.
Applies to: All agents, all modes, all sub-agents.
```

```
C-COMMENT-4
Rule: Do NOT write AI fluff/filler/history in comments ("elegantly", "previously we...", "extracted from the old monolith").
Rationale: History belongs in git/docs; inline history contradicts code within weeks.
Applies to: All agents, all modes, all sub-agents.
```

```
C-COMMENT-5
Rule: Do NOT leave restating/contradicting comments (`i += 1  # increment i`). On every file edit, verify survivors against the code; fix or delete stale ones.
Rationale: Stale comments actively mislead.
Applies to: All agents, all modes, all sub-agents.
```

```
C-COMMENT-6
Rule: Do NOT bury lasting explanations inline. Multi-paragraph rationales/catalogues/essays live in `docs/code-notes/<area>.md`; call sites keep a 1-line pointer (`// NOTE: see docs/code-notes/<area>.md#anchor`, target must exist).
Rationale: Inline essays are unreadable at call sites and unsearchable as docs.
Applies to: All agents, all modes, all sub-agents.
```

```
C-COMMENT-7
Rule: Do NOT delete/weaken protected anchors when shortening comments: `SEC-`/`RACE-`/`PERF-` tags + 1-line why; `C-*` anchors at governed code sites; workflow evidence tags (`NU-105`, `IPD-1`, `S1-CR-99`, `S4-CR-25`, `S10-CC-1`, `CRIT-7`, `TX-*`, `WR-*`, `XS-*`, `MIG-*`, `ZR-*`); required lint/type directives + short rationale. Essays slim to tag + 1-line why inline, rest moves to docs/ with pointer.
Rationale: These tags wire AGENTS.md constraints, CI evidence, and parity tests; removing anchors breaks the system.
Applies to: All agents, all modes, all sub-agents.
```

```
C-COMMENT-8
Rule: Do NOT add space-filling/obvious/restating comments. New non-obvious invariants get one short WHY comment; everything else is docs work, not code comments.
Rationale: New code must not re-seed the bloat this section removed.
Applies to: All agents, all modes, all sub-agents.
```

```
C-COMMENT-9
Rule: Do NOT ship comment-only edits without running comment-pinned tests (event-bus catalogues + totals, branding parsers, workflow YAML pins, Rust source greps for thread/block_on/allowed events). Pinned tokens stay or the test updates in the same change.
Rationale: Several "docs" here are test-enforced contracts.
Applies to: All agents, all modes, all sub-agents.
```

Supporting tool: `scripts/comment_ratio_metrics.py` (per-dir ratios + densest files). Relocated notes live under `docs/code-notes/`.

---

## Category: File Structure & Modularity

```
C-STRUCT-1
Rule: Do NOT let a file serve more than one purpose. High cohesion: one module/class-family/concern per file; unrelated logic splits no matter the file count (2000+ single-purpose files correct; hundreds of multi-concern files not).
Rationale: Mixed files can't be understood/modified/tested independently; file count is not a cost.
Applies to: All agents, all modes, all sub-agents.
```

```
C-STRUCT-2
Rule: Do NOT mix concerns in one file (logic/UI/persistence/IPC/platform glue/tests never share). A file changing for two reasons is two files and MUST split.
Rationale: Mixed rates of change couple independent edits (SRP per file).
Applies to: All agents, all modes, all sub-agents.
```

```
C-STRUCT-3
Rule: Do NOT grow files past their concern's budget — split into two or three smaller files instead. Approaching ~500 lines or a second emerging responsibility → create-first split (verified replacement before trimming, re-exports keep names resolving), never extension.
Rationale: Oversized files collect misplaced code; split early.
Applies to: All agents, all modes, all sub-agents.
```

```
C-STRUCT-4
Rule: Do NOT add code to an already-violating file without splitting first. The create-first split of the touched area is part of the task cost, never optional polish.
Rationale: Small changes on god-files compound the eventual split.
Applies to: All agents, all modes, all sub-agents.
```

```
C-STRUCT-5
Rule: Do NOT create a file without a one-sentence purpose ("this file exists so that <one thing>" — needing "and" means split). New files sit beside their concern, never in util/misc buckets.
Rationale: Purpose-less files re-create the god-file problem one import at a time.
Applies to: All agents, all modes, all sub-agents.
```

---

## Final note

Every rule above was added because an agent did the prohibited thing and the user reverted it. That history is why this section stays spare and binding.

---

## Category: Transcription Delivery

```
C-TRANS-1
Rule: Do NOT surface transcription text during recording or deliver it before the stop trigger, regardless of backend transport (one-shot POST, chunked upload, hidden streaming, realtime WS). The transcript is delivered once, at the end, after stop; realtime backends buffer and release at stop, never live partials.
Rationale: Live text distracts while dictating; end-only delivery keeps backends interchangeable (user decision 2026-10-14).
Applies to: All agents, all modes, all sub-agents.
```
