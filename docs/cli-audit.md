# CLI Audit — Lausu 1.0.0

Audit performed on `main` at baseline commit `38bc7d890196066297c7342f2365390e5e5bc249` (2026-11-28). Evidence is `file:line` plus real command output captured during this audit. Nothing in production code, tests, build scripts or configs was changed.

## (a) Plain-English summary (3 minutes)

The app has **almost no user-facing CLI**. The installed `lausu` command does exactly two things: start the production app (optionally hidden) or start the dev environment with `--dev`. `python -m voice_typer` adds `--debug/--quiet/--no-tray/--config` for running the bare Python app in tests/headless mode. `lausu-server` / `python -m voice_typer.server.ipc_server` is not an operator CLI at all — it is the sidecar process the Tauri host spawns, and without `--ws` it boots the app, then exits with code 4. Its `--help` is silently ignored; this was reproduced.

The **real control surface is IPC**, not CLI: 111 JSON commands (`voice_typer/server/ipc/registry.py:113-252`) over a loopback WebSocket with a per-launch bearer token. It is used by the renderer and host, and by tests via an env-gated stdin path that the CLI entry point never enables. The app's History, analytics, vocabulary, templates, models, TTS, providers, media jobs and dictation control already live behind those commands and their service/handler layers. A future agent CLI should reuse them, not reimplement them.

Plugins are dev-only and gated by one shared GUI-side function (`internal_plugin_hook.internal_surface_enabled`, `voice_typer/server/internal_plugin_hook.py:66`) plus the plugin's own `PLUGINS_ENABLED` marker; packaging excludes the markers and debug folder. `get_plugins` answers locked installs with `available=false` and an empty list. Care is still needed for a future generic config/status/history dump, because those payloads can contain plugin field names or plugin display names from a developer profile.

The biggest gaps versus the owner's wish list are: no agent-facing command runner at all, no JSON output mode, no stable schema/exit-code contract, no documented read-only default, no `--dry-run`/confirmation protocol, and no way to read History/analytics/models through a terminal command. Media transcription and model downloads already exist as IPC commands with job/status/cancel support and can be wrapped.

---

## (b) Command inventory

### User/dev entry points

| Name | Launched as | Lives in | Ships to end users? | Dev-only? | History / why added |
|---|---|---|---|---|---|
| `lausu` | console script (`pyproject.toml:315`), shim found at `C:\Users\11\.local\bin\lausu.cmd` | `voice_typer/server/cli.py:146-167` | Source/venv install; packaged installer uses frozen sidecar + Tauri host, not this console script (`scripts/build/build_sidecar_windows.sh:121-178`) | No, but docs call it legacy/dev (`docs/home-directory.md:145-150`) | `801efe911` (2026-09-30) "route the lausu console script to the production Tauri host entry". Consumed by `tests/test_cli_production_entry.py`, `docs/home-directory.md`, `autostart/tauri_spawn.py:398`. |
| `lausu-server` | console script (`pyproject.toml:316`) | `voice_typer/server/ipc_server.py` → `ipc/entrypoint.py:219` | Declared in package metadata; not on PATH in this dev env (real output: `lausu-server: The term ... is not recognized`) | No | Bare backend entry; comment at `pyproject.toml:312-314` says do not point `lausu` at it. Consumed by renderer bridge tests. |
| `python -m voice_typer` | module | `voice_typer/__main__.py:20-57` | Same Python package; test/headless use | Operational/test | Flags handed off through env vars to `app.main()` (`__main__.py:74-92`). `tests/app/test_main_module_docs.py` pins it is not a duplicate of `cli.py`. |
| `python -m voice_typer.server` / `voice_typer.server.ipc_server` | module | `voice_typer/server/__main__.py:1-6`, `ipc/entrypoint.py:99-197` | Frozen as `python-sidecar` in releases (`scripts/build/build_sidecar_windows.sh:178`) | No | `1216af795` (2026-10-11) split entrypoint; `553c65708` (2026-11-21) freeze gate. |
| `python -m voice_typer.worker` | module / frozen `lausu-worker` | `voice_typer/worker/__main__.py:189-232` | Frozen worker in releases | No | Runtime-pack ASR worker; its own `--version/--debug/--help`. |
| Tauri host `lausu-tauri[.exe]` | direct binary (autostart) | `src-tauri/src/launch_args.rs:36-65` | Yes | No | `781f44eec` (2026-09-19) added `--hidden` / `--delay N` for direct-binary autostart. Unknown args pass through silently. |
| Deep links | `ms-settings:privacy-microphone`, `x-apple...`, `gnome-control-center sound` | `src-tauri/src/host_events.rs:99-129` | Yes | No | OS settings links, not an app-control CLI. |

### Scripts that behave like CLIs (all dev/build tooling, not shipped as user commands)

`scripts/diagnostics.py` (`main()` at `:387`, subcommands `f2`, `cublas`, `runtime`, `test-runner`, `export`; real `--help` output is a usage line and **exit 1**, not argparse help). `scripts/run_bench.py` (benchmark driver; real `--help` crashed with `UnicodeDecodeError: 'charmap' codec can't decode byte 0x81`, exit 1). `scripts/git_safe_commit.py`, `scripts/check_branding.py`, `scripts/mypy_ratchet_check.py`, `scripts/ruff_ratchet_check.py`, `scripts/build/sync_versions.py`, `scripts/build/stage_internal_plugins.py`, `scripts/ci_errors/collect.py`, `scripts/gen_tauri_icons_stub.py`, and the `verify_*` scripts all have argparse/`main()` entry points. They are repository tooling, not product surface. `scripts/dev/fake_audio_chrome.ps1` is a marker-gated dev harness (`scripts/dev/fake_audio_chrome.ps1:4,14-15`).

### Dev diagnostics command channel

`voice_typer/server/plugin_dev_driver.py:28-41` enables a file-based command channel only when not frozen and either `VOICE_TYPER_PLUGIN_DIAGNOSTICS=1` or a `DEVELOPER_DIAGNOSTICS` marker file exists. Commands are JSON files in `tools/internal_plugins/debug/dev-command/`: `toggle`, `hotkey`, `button`, `tray`, `start`, `stop`, `cancel`, `status` (`:23-25`, `:100-116`), with fresh-`seq` checks and consumed-file deletion (`:76-97`). Live check in this audit: `plugin_dev_driver.enabled(...)` returned `True` in the dev checkout. It is gitignored and never staged into packaged builds.

### Real command results (safe commands executed)

| Command | Output / exit | App running? | Notes |
|---|---|---|---|
| `lausu --help` | usage block: `[-h] [--dev] [--hidden]`; exit 0 | no | Real shim output captured. |
| `python -m voice_typer --help` | `[-h] [--version] [--debug] [--quiet] [--no-tray] [--config PATH]`; exit 0 | no | Machine-readable? No. |
| `python -m voice_typer --version` | `voice_typer 1.0.0`; exit 0 | no | Stable text, no JSON. |
| `python -m voice_typer.worker --help` | `usage: voice_typer.worker [--version] [--debug] [--help]`; exit 0 | no | |
| `python -m voice_typer.worker --version` | `voice_typer.worker 1.0.0`; exit 0 | no | |
| `python -m voice_typer.server.ipc_server --version` | `voice_typer.server.ipc_server 1.0.0`; exit 0 | no | Parsed before single-instance lock (`ipc/entrypoint.py:120-122`). |
| `python -m voice_typer.server.ipc_server --help` | **No help.** Booted full app, logged `[IPC] No transport specified...`, exit 4 | no/yes (boots app) | `add_help=False` and no `--help` action (`ipc/entrypoint.py:139-175`); unknown token ignored, then `sys.exit(EXIT_BAD_ARGS)` at `:387-395`. Confusing. |
| `python -m voice_typer.server.ipc_server --port 9876` | `--port is no longer supported...`, exit 4 | no | Rejected before app construction (`ipc/entrypoint.py:183-192`). |
| `lausu --version` | `error: unrecognized arguments: --version`, exit 2 | no | Inconsistent with other entry points. |
| `lausu --hidden` (app not running) | `[CLI] launching local production build ...`, child pid 2888, exit 0 | starts app | Output is human text with coloured ANSI; sensitive env **key names** listed, values redacted. |
| `lausu --hidden` again | spawned child pid 23476, exit 0, but only **one** app process remained | app already running | CLI reports success twice; host single-instance resolves duplicate. |
| `scripts/diagnostics.py --help` | usage line + 5 subcommands, exit 1 | no | Not an argparse `--help`. |
| `scripts/run_bench.py --help` | `UnicodeDecodeError` traceback, exit 1 | no | Broken non-interactive behavior. |
| `lausu --dev` | **not executed: destructive-ish** (launches full dev environment) | n/a | Read at `cli.py:114-119`. |

Exit codes are standardized in `voice_typer/__main__.py:12-17`: 0 clean, 1 crash, 2 port conflict, 3 duplicate instance, 4 bad args. IPC handler errors use typed envelopes (`ipc/validation.py`), not shell exit codes.

---

## (c) Architecture (text diagram)

```
Terminal / agent
  └─ lausu (console script, pyproject.toml:315)
       └─ cli.py:146 -> launch_production(hidden) / launch_dev()
            └─ src-tauri/target/.../lausu-tauri.exe (spawned, detaches)
                 └─ Rust host generates bearer token, spawns python-sidecar
                      └─ ipc_server.py --ws  (ipc/entrypoint.py:219)
                           ├─ binds 127.0.0.1:<ephemeral>  (sidecar_ws.py:437-452)
                           ├─ one-shot token auth       (sidecar_ws.py:27-41, :304-322)
                           └─ IPCServer._dispatch       (ipc/dispatcher.py)
                                └─ handlers/*.py -> service/*.py -> LausuApp
                                     ├─ history.db (encrypted text columns)
                                     ├─ config.json (SEC-002 allowlist)
                                     ├─ vocabulary.json / templates.json / correction-usage.json
                                     ├─ model files / TTS packs / HF cache
                                     └─ MediaJobManager (media_ingest/jobs.py:109)
```

Other paths:

```
python -m voice_typer  -> flags via env -> server.app.main() (not cli.py)
python -m voice_typer.server.ipc_server  -> same IPCServer, but no transport without --ws
stdin runner (IPCServer._run, ipc/stdin_runner.py:29-96) -> JSON lines -> same dispatcher
  gated by VOICE_TYPER_ALLOW_STDIN_IPC=1 (ipc/lifecycle.py:105-121)
  main() always sets _tcp_mode=True (ipc/entrypoint.py:336,355), so the CLI never starts it
dev driver: debug/dev-command/command.json -> plugin_dev_driver.run_watcher -> real hotkey wrapper
```

Every command reuses the GUI's service layer; there is no second business-logic copy. Concurrency controls: `_config_mutation_lock` (`config_handlers.py:150-175`), history DB writer/reader split (`history_db_internals/writer.py`, `reader.py`), IPC `_dispatch_lock` with readonly/self-serialized bypass sets (`ipc/registry.py:30-107`), and single-instance host ownership under Tauri (`ipc/entrypoint.py:279-285`). A future CLI should go through the same dispatcher; direct DB/config writes would race the GUI.

---

## (d) Coverage map against the owner's wish list

Legend: **ALREADY EXISTS** = usable today through an existing command/service; **PARTIAL** = backend exists but no terminal-facing command or missing field; **MISSING** = no code path found.

| Item | Status | Existing code to reuse | Notes |
|---|---|---|---|
| a) History list/filter/metadata/original+translated/by id | **PARTIAL** | `handlers/history_handlers.py:75-147` (`get_history`, `get_favorites`, `search_history`, `get_transcription_text`), `ipc/history_bounds.py:104-121`, `history_db_internals/schema.py:323-337` | `get_history` supports limit/offset, cursor (`before_timestamp`+`before_id`), UTC `start_ts/end_ts`, frame cap 1 MiB−32 KiB. Row fields include `text`, `original_text`, `word_count`, `char_count`, `duration`, `model`, `device`, `language`, `favorite`, `method`, `source_type`. No filter by model/engine/length; no diff view; no single-item-by-id command (`get_transcription_text` exists but is keyed differently). No CLI command exposes any of it. |
| b) Analytics numbers | **PARTIAL** | `pages/Dashboard/hooks/useDashboardData.ts:126-198`, `lib/streaks.ts:30-49`, `ipc/registry.py:32-70` | Page computes todayCount/todayChars/todayWordCount/todayDuration, totalCount, totalWords, totalDuration, favoritesCount, model, device, language, currentStreak, maxStreak, activeDays, sampleSize from a 500-row `get_history` sample + `get_history_count` + `get_correction_usage` + `get_model_status`/config. `get_today_stats` is registered but no longer used by the page (`useDashboardData.ts:10`). No backend aggregator to call and no CLI. |
| c) Vocabulary / snippets | **PARTIAL** | `ipc/registry.py:150-155` (`get_vocabulary`, `save_vocabulary`, `get_correction_usage`, `test_vocabulary_correction`, `get_templates`, `save_templates`), `vocabulary.py:100`, `vocabulary_apply.py:90`, `template_persistence.py:3`, `correction_usage.py:18` | Storage: `vocabulary.json` = user diff vs bundled `corrections.json` + tombstones; `templates.json`; `correction-usage.json`. Pipeline order is Transcribe → TranslationStage → CleanupStage → **VocabularyStage** → TemplatesStage (`dictation_stages.py:230-244`), so dictionary corrections are applied to the *translated* text; `original_text` is stored separately. `test_vocabulary_correction` exists — a ready-made primitive for the agent's "test before save" workflow. No CLI. |
| d) STT models + TTS models | **PARTIAL** | `get_model_catalog` (`model_handlers.py:100-111`), `get_model_status`, `download_model`, `pause/resume/cancel_model_download`, `get_download_queue`, `delete_model`, `import_model`, `tts_status/prepare/delete/speak/stop` (`ipc/registry.py:186-232`), `gguf_model_registry.py:186-209`, `service/tts.py:32-51` | Model metadata includes size, VRAM, backend, languages, description, repo id, distilled flag, speed/accuracy, WER, network behavior (`gguf_model_registry.py:190-205`) — but license/quantization live in `GGUFSizeSpec` (`:36-39`) and are not in `ModelMetadata.to_dict()`; need flattening for a CLI. Download progress/resume/cancel exists via IPC + queue. Active model is `config.model_size`; TTS engine is `config.tts_engine`. No CLI. |
| e) Engine switching (local/cloud/plugin) | **PARTIAL** | `set_config` (`config_handlers.py:156-182`, `:287-302`), `provider_set_domain` (`provider_handlers.py`), `internal_plugin_hook.sync_selection` | GUI state matrix: selecting local model/backend while a plugin is active releases `active_plugin` in the same persisted write (`:162-170`); a refused model switch restores the plugin (`:176-181`); selecting a plugin triggers `sync_selection` (`:287-302`). Cloud routing via `asr_backend="cloud"` + `asr_provider`/provider consent. A CLI must call `set_config`, not write config directly. No CLI command. |
| f) Settings | **PARTIAL** | `get_config`/`get_defaults`/`set_config` (`config_handlers.py:61-99`), allowlist `config_validators/allowlist.py` (~150 lines), schema `config/_schema.py:30-394` | Two plugin settings exist: `plugin_visible`, `plugin_notify` (`allowlist.py:308-309`, schema `:52-53`). All general settings are listed in `config/_schema.py` (hotkey, sample_rate, microphone, model_size, language, translation_* 7 fields, device/beam/vad/hallucination, streaming_* 6, autostart/paste_on_stop/show_notifications/warn_password_paste/fast_startup/offline_pack_consent, ASR/TTS provider fields+consents, clipboard_* 3, recording_mode, esc_cancel_enabled, repaste_hotkey, auto_punctuation, templates_enabled, vocabulary_enabled, cloud/LLM keys, chat_*, sound/crash/bubble/history/theme/accessibility/VAD/volume fields — ~120 fields). Safe/useful small set to expose: `language`, `translation_enabled`, `translation_target_language` (agent's translation workflow); `microphone` + `get_microphones`; `model_size`/`device` (engine choice); `show_notifications`. Reason: all are in the SEC-002 allowlist, have validators, and are meaningful to a headless helper; secret keys, consent flags and dev-only fields should stay out. Full parity explicitly not planned. |
| g) Media file + URL transcription | **PARTIAL** | `ipc/registry.py:215-221` (`media_transcribe_start/cancel/status`), `handlers/media_handlers.py:25-92`, `media_ingest/jobs.py:109`, `jobs.py:378-389`, `media_ingest/storage.py:59`, `yt-dlp` at `pyproject.toml:110`, ffmpeg at `pyproject.toml:102-103` | Local path + URL ingest, job ids, status polling, cancel, progress events, results written to History. Headless-drivable through IPC; no CLI. URL restrictions exist (`media_url_consent`, `media_ingest/errors.py`), long files/job caps need review before exposing. |
| h) Dictation start/stop/status | **PARTIAL** | `get_status` (`status_handlers.py:61-88`), `toggle_dictation`, `force_cancel_transcription` (`ipc/registry.py:115,204`) | `get_status` works. Start/stop exist as IPC commands, but **USER-INITIATED-START RULE** (`AGENTS.md`, added 2026-11-27) says a recording may only start from an explicit user action. A CLI typed by the owner is arguably user-initiated; an AI agent starting the mic is a privacy decision. Facts/options only — no decision proposed here. No CLI command exists. |

---

## (e) Plugin leak risk

How plugins are gated today:

- `internal_plugin_hook.internal_surface_enabled()` (`internal_plugin_hook.py:66-84`): developer mode (`config.developer_mode`) plus a usable workspace; `VOICE_TYPER_INTERNAL_PLUGINS=1` is a dev escape hatch.
- `plugins_enabled()` (`internal_plugin_hook.py:87-107`): adds selected plugin id and the plugin's own `PLUGINS_ENABLED` marker (`tools/internal_plugins/_common/daemon.py:38-40`).
- Packaging: `scripts/build/stage_internal_plugins.py:31-46` excludes `debug`, `generated`, `test(s)`, `PLUGINS_ENABLED`, `DEVELOPER_DIAGNOSTICS`, config/token files; dev driver's frozen checks are at `plugin_dev_driver.py:32-40`.
- GUI gate is **one shared function** (`internal_surface_enabled`) used by `get_plugins`, routing, activation and settings application — not scattered ad-hoc checks.

| Path | Safe today? | Evidence |
|---|---|---|
| `get_plugins` | **Safe** | `handlers/plugin_handlers.py:22-38`: locked install returns `{"available": false, "plugins": []}`. |
| `get_config` / `get_defaults` | **Mostly safe, caveat** | Secrets redacted by pattern (`ipc/history_bounds.py:43-97`, `service/config_service.py:35-42`), but field *names* `active_plugin`, `plugin_visible`, `plugin_notify`, `developer_mode` are present in every config. Values are empty/default in a locked install; a developer profile carried into a packaged build can reveal a plugin id. A future generic config dump must use an allowlist. |
| `get_status` | **Caveat** | `service/status.py:154-198` returns tray `message`; a dev profile's message can include "Claude STT serves dictation". Production locked installs have no plugin owner. |
| `provider_list` / `provider_models` | **Safe** | Cloud model providers only (`handlers/provider_handlers.py:66-75`); no internal plugin enumeration. |
| `get_model_catalog` / `get_model_status` | **Safe** | Local GGUF/TTS inventory (`model_handlers.py:100-111`); no plugins. |
| History rows (`model`, `method`) | **Caveat** | `schema.py:323-337` stores model/method; plugin delivery writes plugin labels and `method="recovered (partial)"`. A CLI `history list` on a shared developer profile could reveal those rows in a packaged build. |
| Error messages / help / completions | **Safe** | Generic envelopes (`handlers/_base.py:100-113` redacts paths/secrets); CLI help mentions only `--dev/--hidden`; no shell-completion generator exists. |
| Dev driver | **Safe** | Frozen/marker gated (`plugin_dev_driver.py:28-41`), files gitignored, consumed commands deleted. |

Options for a future leak-proof CLI (not implemented): (1) reuse `internal_surface_enabled()` as the single gate for any engine/plugin/config command, with plugin fields absent from output when false — cheap, shares GUI truth; (2) build-time exclusion of plugin code from packaged sidecar — stronger, bigger build change and would need full CI re-run; (3) add a test that fails if production CLI JSON/help output contains plugin ids or the strings `plugin_visible/plugin_notify/active_plugin` — cheap guard, complements rather than replaces the gate. Recommendation: (1) + (3); keep (2) as a later hardening decision.

---

## (f) Security and safety findings

1. **No agent-facing CLI exists today**, so there is no CLI access audit log, no `--dry-run`, no read-only mode, no confirmation protocol, and no JSON output flag (verified across all help output above).
2. **History contains private dictated text.** `get_history` returns full `text` and `original_text` (`history_db_internals/schema.py:326,336`; `history_handlers.py:133-147`). At-rest encryption exists (`text_is_encrypted`), but there is no per-call redaction option and no CLI opt-in gate. Any local process that can authenticate to the WS can read it.
3. **Local WS is loopback + token.** `sidecar_ws.py:27-41` documents one-shot 256-bit bearer token generated per spawn by the host, ephemeral `127.0.0.1:0` bind, no replay protection. This is reasonable for local IPC; an agent CLI would need the host token, which is deliberately not exposed.
4. **Unauthenticated stdin IPC is env-gated and unreachable from the real CLI.** `ipc/lifecycle.py:105-121` requires `VOICE_TYPER_ALLOW_STDIN_IPC=1`; `ipc/entrypoint.py:336,355` sets `_tcp_mode=True` so `main()` never starts it. `--allow-stdin` was removed (`2302f92c3`, 2026-09-21).
5. **Destructive commands exist in IPC** (`delete_history`, `clear_history`, `delete_model`, `tts_delete`, `quit_app`, `shutdown`, `restore_history`, vocabulary save, templates save) with no CLI confirmation layer. Arcjet's agent-CLI design (`https://arcjet.com/blog/designing-a-cli-for-ai-agents`, Firecrawl, 2026-11-28) recommends a JSON confirmation envelope + explicit `--confirm` rather than an interactive prompt, stable additive command contracts, hard failures with distinct exit codes, and JSON-by-default when stdout is not a TTY. CircleCI's MCP-vs-CLI comparison (same research) notes CLI wins on token cost/local iteration, MCP wins on schema/audit/credential boundary; most teams use both. Those conventions matter more for an agent-facing CLI than decorative output.
6. **Concurrency**: GUI + a future CLI must share `_config_mutation_lock`, history writer queue, IPC dispatch lock and download single-flight (`ipc/registry.py:30-107`, `config_handlers.py:150-175`). Direct file/DB access from a CLI would race.
7. **Environment inheritance**: `lausu --hidden` logs the *names* of 10 sensitive env keys inherited by the child (values redacted) — safe output, but a CLI that dumps environment would be dangerous.
8. **File permissions**: POSIX sidecar sets `umask(0o077)` (`ipc/entrypoint.py:226-228`) and config writes use `_secure_atomic_write`. Windows ACL details were **UNVERIFIED** (exact reason: no ACL inspection was needed to answer the audit questions; no evidence gathered).

---

## (g) Design debt and top extension risks

- `lausu-server --help` boots the app then exits 4; `--port` is a retained stub only for tests (`ipc/entrypoint.py:144-150`, `2302f92c3`). Adding subcommands to this entry point risks inheriting that broken help behavior.
- Two different flag sets: `lausu` has `--dev/--hidden`; `python -m voice_typer` has `--debug/--quiet/--no-tray/--config`; Tauri host has `--hidden/--delay`. No unified grammar.
- 111 IPC commands have no CLI, no shell completions, no command schema/version, and no documented JSON contract. `get_today_stats` is registered but retired from the Dashboard.
- `scripts/run_bench.py --help` crashes on cp1252 decode; `scripts/diagnostics.py --help` exits 1. These are dev tools but show the low priority of non-interactive ergonomics.
- `pyproject.toml:316` declares `lausu-server`, but it was not on PATH in this checkout; docs call `lausu` a legacy/dev entry. A future "ships to all users?" decision is unresolved.
- No TODO/FIXME in `cli.py` or `ipc/entrypoint.py`; the main known maintenance note is the `VT_EARLY_SERVER_STARTED` sunset checklist at `ipc/entrypoint_args.py:32-40`.
- Riskiest extensions: (1) reimplementing business logic instead of calling services/IPC; (2) exposing plugin/config fields from a developer profile in a packaged CLI; (3) letting an agent start the microphone without owner consent; (4) output shape changes after agents depend on them; (5) direct DB/config writes racing the GUI.

---

## (h) Open questions for the owner (for Phase 2 interview)

1. Who is the CLI for — your own agents, all end users' agents, scripts, or CI? Does it ship in the packaged installer?
2. Plain CLI, local MCP server, or both? (Audit facts: CLI is zero-schema and familiar; MCP gives typed tools/audit/credential boundary.)
3. Should output be JSON by default when stdout is not a TTY, with a versioned schema and stable exit codes?
4. Read-only by default? How should destructive commands (delete history/model/vocabulary) be confirmed without an interactive prompt?
5. History privacy: should agent access require a GUI opt-in toggle, redaction, row limits, and an audit log?
6. Must the app be running? Should the CLI start it headlessly, or fail with a clear code?
7. Dictation start/stop: does the CLI expose start at all, given the USER-INITIATED-START RULE?
8. Plugin exposure: hard gate + test that production CLI output never mentions plugins?
9. Dictionary workflow: expose "which entries were applied to this history item", `test_vocabulary_correction`, duplicate/conflict checks, per-language entries?
10. History comparison: diff view original vs final, suspicious-segment flags, pagination, bulk export limits, date filters?
11. Analytics: which fields — the DashboardData list, raw DB counts, or trend windows?
12. Model downloads: progress format, resume, disk-space checks, checksum verification, cancel, concurrent downloads, metered-network behavior?
13. Media: max file size/duration, URL restrictions, job ids/status polling/cancel, where results go, time/cost estimates?
14. Which five general settings are important? (Audit lists all keys; owner must pick.)
15. Mic selection edge cases; command grammar (`noun verb` vs `verb noun`), aliases, completions; generated `help --json`/SKILL doc for agents; testing strategy; phased rollout; explicit out-of-scope items.

---

# Addendum: bare `lausu` launch bug (owner report, 2026-11-28)

**Owner report:** typing bare `lausu` in a terminal was expected to launch the built/production app, but an Edge window opened with "Hmmm… can't reach this page — localhost refused to connect — ERR_CONNECTION_REFUSED". No code was changed to investigate this.

## How `lausu` resolves what to launch

1. The installed shim `C:\Users\11\.local\bin\lausu.cmd` runs `python.exe -c "from voice_typer.server.cli import main; sys.exit(main(sys.argv[1:]))"`. It does **not** use `python -m ...`.
2. `cli.main()` (`voice_typer/server/cli.py:146-167`) parses only `--dev` and `--hidden`; with no flags it calls `launch_production(hidden=False)` (`:167`).
3. `find_production_binary()` (`:36-51`) first asks `_tauri_binary()` from `autostart/tauri_spawn.py:82-134`, which checks `VT_TAURI_BINARY` then OS install paths from `tauri-binaries.json:27-30` (`%LOCALAPPDATA%\Programs\Lausu\lausu-tauri.exe`, `%PROGRAMFILES%\Lausu\lausu-tauri.exe`).
4. If no installed binary is found, `find_production_binary()` falls back to two **local build** candidates (`cli.py:30-33`): `src-tauri/target/release/lausu-tauri.exe` and `src-tauri/target/debug/lausu-tauri.exe` (`:48-50`).
5. `_is_local_build()` (`:54-61`) marks either candidate as "developer-owned artifact", and `launch_production()` (`:91-107`) spawns it directly with launcher env and hidden flags. This branch **treats a debug host as production**.
6. If no binary at all is found, `launch_production()` logs `[CLI] Production app binary not found...` and prints plain English to stderr, returning 1 (`:76-89`). That branch did not fire here.
7. The localhost URL comes from `src-tauri/tauri.conf.json:8` (`"devUrl": "http://localhost:1420"`), alongside `"frontendDist"` at `:7`. A debug host built by `cargo tauri dev`/`cargo build` uses that dev URL; `tauri.dev.conf.json:3` only blanks `beforeDevCommand`, and `voice_typer/client/scripts/tauri-dev.mjs:74,407` passes that config to `tauri dev`.
8. `lausu --dev` (`:114-119`) deliberately calls `launch_dev_console("tauri:dev")`, which starts the dev server. `--hidden` (`:151-160`) sets `VT_START_HIDDEN=1` in the local-build branch and passes `hidden` to the installed branch (`:109-111`).

**Why this machine ended up in the dev path:** on this checkout `src-tauri/target/debug/lausu-tauri.exe` exists (`find_production_binary()` returned that path during the audit), and a Vite dev server was running from earlier work, so spawning it appeared to work. On a machine with a leftover debug host but **no dev server**, the same branch gives the Edge `ERR_CONNECTION_REFUSED` page. The bug is the fallback at `cli.py:48-50,91-107`, not the missing-binary branch.

**Proposed fix (plan item for the spec, not implemented):** only installed binaries (and explicitly release-built local binaries) count as production; a `target/debug` host must never be spawned by bare `lausu`. If no production binary exists, print a plain-English error such as "Lausu is not installed/built on this machine. Run the installer, or use `lausu --dev` for development." and exit non-zero. Bare `lausu` must never open a browser/dev URL by itself; `--dev` remains the only explicit dev entry.

## Entry points that violate the app-name-first rule

Owner decision: every public command must be `lausu <command> [flags]`. These entries exist but are internal/dev tools and must not be presented as the public CLI:

- `python -m voice_typer` (`voice_typer/__main__.py:1-57`)
- `python -m voice_typer.server` / `python -m voice_typer.server.ipc_server` (`voice_typer/server/__main__.py:1-6`, `ipc/entrypoint.py:99-197`)
- `python -m voice_typer.worker` (`voice_typer/worker/__main__.py:189-232`)
- `scripts/*.py` and `scripts/build/*.py` argparse tools (`scripts/diagnostics.py:387`, `scripts/run_bench.py`, `scripts/git_safe_commit.py`, ratchet checks, etc.)
- `lausu-server` console script (`pyproject.toml:316`): starts with the app name but is a bare backend, not an operator CLI.
- Tauri host direct binary `lausu-tauri[.exe] --hidden/--delay` (`src-tauri/src/launch_args.rs:36-65`): autostart-only.
- The file-based dev diagnostics channel (`voice_typer/server/plugin_dev_driver.py:23-25,44-116`): not a shell command at all.

`lausu` itself conforms; the bug is what it launches, not its name.
