# CI error report workflow (round 24)

Operator documentation for the `CI-errors.md` digest. This file is documentation only; it does not change workflows, hooks, scripts, or Git state.

Status labels used below: **VERIFIED** means checked against the local checkout at the time this file was written; **UNVERIFIED** means the claim is part of the approved design but was not proven locally (see [Verification status](#verification-status)).

## 1. Approved design in one paragraph

A GitHub Actions collector writes `CI-errors.md` to the orphan data branch `ci-reports`. `main` untracks and gitignores the file, so it never receives bot commits. A local, stdlib-only sync script fetches exactly one ref (`refs/heads/ci-reports`) and atomically replaces the single local file; it never touches the index, `HEAD`, other refs, or other working-tree files. The local copy is refreshed by a VS Code folder-open task, husky hooks, an explicit command, and (optionally on Windows) a 5-minute scheduled task.

```
workflow_run(completed)  ->  .github/workflows/ci-error-collector.yml
                              -> python -m ci_errors.collect -> CI-errors.md
                              -> git push origin HEAD:ci-reports
origin/ci-reports:CI-errors.md
    -> git fetch --no-tags origin +refs/heads/ci-reports:refs/remotes/origin/ci-reports
    -> git show origin/ci-reports:CI-errors.md
    -> temp file + fsync + os.replace  ->  local CI-errors.md
```

VERIFIED locally: `.gitignore` ends with `CI-errors.md` (comment: "Generated on the ci-reports branch and synced locally by scripts/sync_ci_errors.py"), `CI-errors.md` is staged as `D` in the index, and the old "Write CI-errors.md" / "Commit and push CI-errors.md" steps were removed from `.github/workflows/build.yml`. UNVERIFIED: the remote `ci-reports` ref does not exist yet (`git ls-remote --heads origin ci-reports` returned no refs), so no collected report has been pushed in practice.

## 2. Agent rule (add to AGENTS.md, verbatim)

> CI-errors.md is generated on the ci-reports branch and synced locally; never edit or commit it; run `python scripts/sync_ci_errors.py` to refresh; main no longer receives bot commits

UNVERIFIED: this text is not yet present in `AGENTS.md` (out of scope for this document; the owner applies it).

## 3. Collector

- Workflow: `.github/workflows/ci-error-collector.yml` (VERIFIED: file present).
- Triggers: `workflow_run` with `types: [completed]` and an explicit `workflows:` name list, plus `workflow_dispatch` with optional `run_id` / `rebuild` inputs for ingest or a `--rebuild --limit 200` rebuild.
- Guardrails: skips forks and `workflow_run` events from a fork (`head_repository.full_name != github.repository`); `concurrency.group: ci-errors-writer`, `cancel-in-progress: false`; `permissions: contents: write, actions: read`.
- Branch handling: seeds an orphan `ci-reports` branch from the tracked `CI-errors.md` if the branch is absent, otherwise `git checkout -B ci-reports refs/remotes/origin/ci-reports`. Commits as `github-actions[bot]` and pushes `HEAD:ci-reports` with a bounded 3-attempt rebase/regenerate retry.
- Generation: `python -m ci_errors.collect --repo AbdallahIsDev/Lausu --output CI-errors.md` from `scripts/ci_errors/` (`collect.py`, `github.py`, `fixtures.py`, `extract.py`, `analyze.py`, `render.py`). `--input DIR` is the offline fixture mode; no network is used.
- The collector excludes itself and the retired mutation workflow from reporting (`COLLECTOR_EXCLUSIONS` in `analyze.py`); the explicit workflow-name list is mirrored by `TRACKED_WORKFLOWS` (`analyze.py`) as a drift guard — updating one requires updating the other.
- **No bot commits to `main`.** The collector only ever commits/pushes on `ci-reports`.

### Why explicit workflow names instead of globs

GitHub docs confirm `on.workflow_run.workflows` **does support glob patterns**: "The `workflows` filters accept glob patterns that use characters like `*`, `**`, `+`, `?`, `!` and others to match more than one workflow name" — <https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax>. We still enumerate every workflow name explicitly, one per line, so renaming or adding a workflow becomes a visible drift-guard failure instead of a silent change in what the collector watches. Do not "simplify" the list to `["*"]`.

### Why the push cannot loop

GitHub docs: events triggered with the repository's `GITHUB_TOKEN` do not create a new workflow run, with exceptions for `workflow_dispatch`, `repository_dispatch`, and `pull_request` events with activity types `opened`, `synchronize`, `reopened` (not `labeled`, `edited`, `closed`) — <https://docs.github.com/en/actions/concepts/security/github_token>. The collector pushes with the token but only to `ci-reports` and only as a `push` event, which is not one of those exceptions, so no recursive run is created. This is also why the old build.yml in-job commit could claim the same property; the difference is the destination branch, not the token semantics.

## 4. Report sections, size cap, cancelled/skipped policy

The generated file has a header (`# CI Errors`, `> Generated: ...`, `> Data branch commit: ...`) and exactly three sections, in this order (VERIFIED: `scripts/ci_errors/render.py:10-14`):

1. **Currently failing** — one entry per non-green latest completed `main` run per workflow. A `success` conclusion clears the group; `failure` is reported immediately; `cancelled` / `timed_out` are reported only after `CANCEL_GRACE = 3 hours` measured against the newest input run's own timestamp (`generation_time`), never wall clock, so regeneration is idempotent. A `skipped`/neutral conclusion neither clears the group nor becomes an entry. Collector exclusions never appear here.
2. **Recent failures** — the last `MAX_RECENT = 60` runs with conclusion `failure`, restricted to `main` plus `workflow_dispatch` failures on any branch. Cancelled/timed-out runs are *not* added here; they are only represented in Currently failing after the grace period.
3. **Resolved recently** — pairs of `(fixing success, red run immediately before it)`, newest first, capped at `MAX_RESOLVED = 20`; each red entry is annotated `Fixed by: [run id](url)`.

Per-entry detail: at most `MAX_JOB_ENTRIES = 8` non-green jobs per run (`failure`, `timed_out`, `cancelled`; skipped jobs are excluded); log excerpts are ANSI-stripped, secret-bearing lines are dropped, then capped at `MAX_EXCERPT_LINES = 40` / `MAX_EXCERPT_CHARS = 4096`. Categories include `infrastructure/cancelled/timeout` for cancelled/timeout conclusions. At most `MAX_DETAIL_FETCH = 100` runs get job/log enrichment per collection.

Size cap: `REPORT_CAP_BYTES = 400 * 1024` (409,600 UTF-8 bytes). `render_report()` drops the **oldest Recent failures** until the report fits and records `> Recent failures rotated out to fit the size cap: N.` in the header. Currently failing and Resolved recently are never dropped for size. An empty section renders `_None._`.

KNOWN ISSUE at snapshot time (UNVERIFIED end-to-end): `scripts/ci_errors/analyze.py:138` references `_BAD`, which is not defined in that module (only `BAD_CONCLUSIONS` at line 39). Step-level extraction raises `NameError` whenever a job with steps is present until that is fixed. Treat any generated report from this snapshot as provisional.

## 5. Local sync script

Command: `python scripts/sync_ci_errors.py` (from the repo root). VERIFIED: `scripts/sync_ci_errors.py` present, stdlib-only, cross-platform.

Contract (from the script's own docstring and implementation):

- Fetches **only** `+refs/heads/ci-reports:refs/remotes/origin/ci-reports` with `--quiet --no-tags`; no prune, no tag fetch, no index/HEAD/other-ref writes, no working-tree writes other than `CI-errors.md`.
- Uses `GIT_TERMINAL_PROMPT=0`, `GIT_OPTIONAL_LOCKS=0`, `GCM_INTERACTIVE=never` and `CREATE_NO_WINDOW` on Windows: no credential prompt, no optional index lock, no console flash.
- Reads the blob with `git show origin/ci-reports:CI-errors.md`, writes a temp file in the same directory, `fsync`s it, preserves the mode, then `os.replace`s it. Identical bytes are never rewritten (mtime untouched).
- Silent no-op with exit 0 for offline, unauthenticated, missing ref, missing file, git unavailable, or timeout. `--verbose` prints one-line diagnostics to stderr. Unexpected local write/read errors exit 3.
- `--check` never writes: prints `CI-errors.md: MATCH` / `CI-errors.md: MISMATCH`, exits 1 only on a real mismatch. Unavailable remote is a silent no-op with exit 0; a missing local file with a readable remote is a mismatch. Intended for hooks/lightweight gates.
- `--timeout SECONDS` (default 20; hooks use 3). Hidden `--repo DIR` flag exists only as a test/integration escape hatch.

## 6. Automation and operator instructions

### VS Code folder-open task

UNVERIFIED: `.vscode/tasks.json` is not present at snapshot time. The approved task shape (add to that file if the automation is wanted) is a shell task with `runOptions.runOn: "folderOpen"` that invokes the repo interpreter from the existing workspace setting:

```jsonc
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Sync CI errors",
      "type": "shell",
      "command": "${config:python.defaultInterpreterPath}",
      "args": ["${workspaceFolder}/scripts/sync_ci_errors.py"],
      "runOptions": { "runOn": "folderOpen" },
      "problemMatcher": []
    }
  ]
}
```

`python.defaultInterpreterPath` is already set to the repo `.venv` in `.vscode/settings.json` (VERIFIED). The task is best-effort and never gates the window opening because the script itself is a silent no-op offline.

### Husky hooks

VERIFIED: four hooks refresh the digest, each with the same backgrounded, output-discarded, never-fail block using `--timeout 3`:

- `.husky/post-checkout` (new) — after checkout / branch switch.
- `.husky/post-merge` (new) — after a merge or pull.
- `.husky/pre-commit` (appended block).
- `.husky/pre-push` (appended block).

Each block resolves the repo root with `git rev-parse --show-toplevel`, prefers `.venv/Scripts/python.exe` then `.venv/bin/python`, falls back to `python3`/`python`, and runs the sync in the background. Following the repo's husky v9 single-installer architecture, the user-level files live in `.husky/` and are sourced by the generated `.husky/_/*` shims; do not edit `.husky/_/*` directly.

### Optional Windows scheduled task: `Lausu-sync-ci-errors`, every 5 minutes

VERIFIED: `C:\Users\11\voice-typer\.venv\Scripts\pythonw.exe` exists; the script self-locates the repo root via `git rev-parse --show-toplevel` with a `__file__`-based fallback, so the task needs no `cd` wrapper. UNVERIFIED: no scheduled task was registered or executed here.

Create / overwrite (run from an elevated or normal `cmd.exe`; the path is this machine's checkout — adjust on other machines):

```bat
schtasks /Create /TN "Lausu-sync-ci-errors" /TR "\"C:\Users\11\voice-typer\.venv\Scripts\pythonw.exe\" \"C:\Users\11\voice-typer\scripts\sync_ci_errors.py\"" /SC MINUTE /MO 5 /F
```

Delete:

```bat
schtasks /Delete /TN "Lausu-sync-ci-errors" /F
```

Inspect (last-run result is in `Last Run Result`):

```bat
schtasks /Query /TN "Lausu-sync-ci-errors" /FO LIST /V
```

`pythonw.exe` suppresses the console window; the script's silent-offline contract means a failed network every 5 minutes does nothing and produces no dialog. `/F` overwrites an existing task / deletes without a confirmation prompt. UNVERIFIED on macOS/Linux: no equivalent timer is part of this round.

## 7. Fallback AGENTS.md rule — round-23 Git lesson (verbatim)

Source: `.agent-workflow/documentation/AGENT_RULES_GIT_UNTRACKING.md`. Apply this text if the owner can isolate the `AGENTS.md` hunk; it is deliberately not edited by this document.

```text
Never run `git commit -- <paths>` when deletions made with `git rm --cached`
are staged. Git then commits the working-tree bytes of those paths instead of
the deletions. To untrack a file: `git rm --cached -- <paths>`, verify
`git diff --cached --name-status` shows exactly the intended `D` lines and
nothing else, then run `git commit` WITHOUT a pathspec. Prove the result with
`git ls-tree -r HEAD --name-only | grep <path>` returning nothing.
```

Safe sequence from the same source: `git rm --cached -- <paths>` → `git diff --cached --name-status` (only `D  <path>` lines) → `git commit -m "..."` (no pathspec, no `-a`, no `--no-verify`) → `git ls-tree -r HEAD --name-only | grep <path>` (no output) → confirm the file still exists on disk and is ignored via `git check-ignore -v`. This is exactly the hazard created by untracking `CI-errors.md`, hence its inclusion here.

## 8. Verification status

| Item | Status |
| --- | --- |
| Collector workflow file, sync script, report modules and tests present locally | VERIFIED |
| `CI-errors.md` staged `D`, `.gitignore` entry present, old build.yml commit steps removed | VERIFIED |
| Husky hook blocks present in `post-checkout`, `post-merge`, `pre-commit`, `pre-push` | VERIFIED |
| `.venv/Scripts/pythonw.exe` exists | VERIFIED |
| GitHub docs statements in §3 (globs / `GITHUB_TOKEN` exceptions) | VERIFIED against the linked official docs |
| Report section names, caps and cancelled/skipped policy in §4 | VERIFIED in source; generated-report correctness UNVERIFIED (`_BAD` bug) |
| Remote `ci-reports` branch / any pushed report | UNVERIFIED — no ref found on `origin`, no GitHub run performed |
| `.vscode/tasks.json` folder-open task | UNVERIFIED — file absent |
| Scheduled task `Lausu-sync-ci-errors` created / run | UNVERIFIED — commands above not executed |
| AGENTS.md rule texts in §2 and §7 applied | UNVERIFIED — not edited here, by assignment scope |
| Real end-to-end hook execution and atomic rewrite under a scheduled task | UNVERIFIED |
