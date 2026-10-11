# Architecture Decision Records (ADR) Index

Unique, zero-padded ADR numbers: one decision per file.
Tooling note: `adr-tools` and similar expect unique `NNNN-*.md` names; this directory now satisfies that constraint.

> **Historical note (2026-10-11):** ADRs `0002`, `0003`, `0004`, `0013`,
> `0014`, `0015`, `0018`, `0019` existed and were deleted in commit
> `79622772` ("Stale ADR drafts removed"). Their rows below are kept as
> historical pointers; the `File` column is marked `(file removed)`.
> ADR-0020 was deleted in the same commit and later restored — it is the
> live file in-tree today.
> **Naming note:** four files share the `0024-*` prefix. They are NOT four
> ADRs: `0024-runtime-pack-worker-handoff.md` is the decision record; the
> other three are annexes (a superseded progress snapshot, the Step-6
> verification checklist, the Step-7 slim-gate draft). Each row below
> states its kind explicitly.

| ADR | File | Title | Status |
|-----|------|-------|--------|
| 0000 | `0000-adr-process.md` | Architecture Decision Records | Accepted |
| 0001 | `0001-record-architecture-decisions.md` | Record Architecture Decisions | Accepted (process live; host-background section superseded by ADR-0020, see note in file) |
| 0002 | `0002-desktop-host-migration.md` (file removed) | predecessor + Python Architecture (Initial) | REMOVED 2026-10-11 (`79622772`); was SUPERSEDED — predecessor host removed 2026-09-17; Tauri sole host (ADR-0020). Historical pointer only. |
| 0003 | `0003-desktop-host-python-architecture.md` (file removed) | predecessor + Python Architecture (Refined) | REMOVED 2026-10-11 (`79622772`); was SUPERSEDED — predecessor host removed 2026-09-17; Tauri sole host (ADR-0020). Historical pointer only. |
| 0004 | `0004-ipc-protocol.md` (file removed) | TCP IPC Protocol | REMOVED 2026-10-11 (`79622772`); was SUPERSEDED for transport — predecessor/TCP removed 2026-09-17; live path is Tauri WS (ADR-0020). Historical pointer only. |
| 0005 | `0005-silero-vad.md` | Silero VAD Adoption | Accepted |
| 0006 | `0006-clipboard-security.md` | Clipboard Security Approach | Accepted |
| 0007 | `0007-native-hotkey-architecture.md` | Native subprocess hotkey architecture | Accepted |
| 0008 | `0008-zero-command-hotkey-architecture.md` | Voice Typer: Zero-Command Hotkey Architecture Design | Accepted (CI/packaging refs are predecessor-era; live path is `tauri-*.yml`, see note in file) |
| 0009 | `0009-audio-filter-chain-architecture.md` | Audio Filter Chain Architecture | Implemented (§5 sketch superseded by GT-58 addenda + shipped code, see note in file) |
| 0010 | `0010-dependency-injection-boundary.md` | Dependency Injection Boundary for IPCServer | Accepted |
| 0011 | `0011-prewarm-architecture-analysis.md` | Voice Typer: Prewarm & Autostart Architecture | Superseded (2026-08-13) by worker-startup-phase (plan §6.2 P-1); standalone `prewarm-<triple>[.exe]` deleted. Body historical. |
| 0012 | `0012-clipboard-borrow-restore-architecture.md` | Clipboard Borrow/Restore Architecture | Accepted |
| 0013 | `0013-desktop-runtime-migration-analysis.md` (file removed) | Desktop Runtime Migration to Tauri v2 + Python Sidecar (Original, Windows-only) | REMOVED 2026-10-11 (`79622772`); was SUPERSEDED by ADR-0020 cross-platform rewrite. Historical pointer only. |
| 0014 | `0014-tcp-ipc-session-token-auth.md` (file removed) | TCP IPC Session Token Authentication (SEC-018) | REMOVED 2026-10-11 (`79622772`); was SUPERSEDED for predecessor/TCP — token auth lives on Tauri WS. Historical pointer only. |
| 0015 | `0015-host-command-allowlist.md` (file removed) | predecessor-Side Command Allowlist (SEC-019) | REMOVED 2026-10-11 (`79622772`); was SUPERSEDED — live surface is Rust `allowlist.rs`. Historical pointer only. |
| 0016 | `0016-granular-consent-flags.md` | Granular Privacy Consent Flags | Accepted: implemented in `voice_typer/server/config.py` as typed boolean fields on the `Config` dataclass. |
| 0017 | `0017-cloud-url-allowlist-https.md` | Cloud URL Allowlist with HTTPS Enforcement (RELIABILITY-004) | Accepted: implemented in `voice_typer/server/_secrets.py`. |
| 0018 | `0018-heartbeat-watchdog.md` (file removed) | predecessor-Alive Heartbeat Watchdog (RW-10) | REMOVED 2026-10-11 (`79622772`); was SUPERSEDED — Rust supervisor owns liveness; heartbeat disabled under `TAURI_SIDECAR=1`. Historical pointer only. |
| 0019 | `0019-per-connection-rate-limiter.md` (file removed) | Per-Connection Rate Limiter (RELIABILITY-006) | REMOVED 2026-10-11 (`79622772`); was Accepted / live under Tauri WS (`_RateLimiter` per connection). Historical pointer only. |
| 0020 | `0020-desktop-runtime-migration-analysis.md` | Desktop Runtime Migration to Tauri v2 + Python Sidecar (Cross-Platform Edition) | **Current authority.** Cutover complete 2026-09-17: predecessor removed; Tauri is the sole desktop host. Prewarm-binary sections superseded (ADR-0011 / plan §6.2 P-1); Nuitka ML-bundling §§4.2-4.4 superseded (ADR-0024 C7 / ADR-0025); live command count is 85 (see count note in file). |
| 0021 | `0021-transcription-translation-split.md` | Split Transcription from Translation | Accepted (locked 2026-10-07, Sec. 5 + Sec. 6); §9 build-order empty (incomplete, see note in file). |
| 0022 | `0022-ws-tcp-protocol-version-asymmetry.md` | Sidecar WS Protocol-Version Check Stays Advisory (TCP Reject Path Retired) | Accepted, partially superseded 2026-09 (TCP removal, ADR-0020 cutover): WS warn-and-continue is the live single-transport policy; TCP half historical. |
| 0023 | `0023-media-ingest-transcription.md` | Universal Media-to-Text Transcription | Accepted (v1 built 2026-09-25; Deno-in-pack / mini-update surfacing / phase-2 items open, see record in file). |
| 0024 | `0024-runtime-pack-worker-handoff.md` | Runtime-pack worker handoff end-to-end (DECISION RECORD) | Accepted, historical execution record: Steps 0-6 verified 2026-09-26, C7 landed 2026-09-27, Step 8 shipped 2026-09-27; dispatched CI validation 2026-10-03 (run 37128596808) green for sidecar/worker freezes + gates. 45 MB refs point to ADR-0026 (80 MB wins). |
| 0024-aux | `0024-progress-step5.md` (ANNEX: superseded snapshot) | ADR-0024 Steps 5–7 prep — progress record | Superseded snapshot (2026-09-26): Step-5/6/7 state as known that day; superseded by the parent ADR's verified record. Do not act on its checkboxes. |
| 0024-aux | `0024-step6-verification-checklist.md` (ANNEX: checklist) | ADR-0024 Step 6 — real-machine verification checklist | Annex to ADR-0024: SIGNED OFF 2026-09-26 (real Windows host, dev worker). Evidence pointers for the parent record. |
| 0024-aux | `0024-step7-slim-gate-draft.md` (ANNEX: superseded draft) | ADR-0024 Step 7 - slim-build gate | Superseded draft: ratchet gate landed + C7 cutover shipped (ADR-0025); 45 MB gate superseded by ADR-0026 (80 MB). Kept for the ownership-decision trail. |
| 0025 | `0025-dictation-worker-cutover.md` | Dictation cutover to the runtime-pack worker | Accepted (C1–C7 code-complete 2026-09-27, unit-verified; host/CI gates per parent ADR + status doc — see note in file). |
| 0026 | `0026-slim-core-installer-80mb-target.md` | Slim-core installer target is 80 MB, not 45 MB | Accepted (owner decision): WINS over all 45 MB refs (plan §11.4, ADR-0024). |
| — | `rest-encryption.md` (unnumbered design doc) | At-Rest Encryption for User Data | Implemented (AES-256-GCM per-row flag design, §16 shipped; §5 sketch historical — see note in file). |
| — | `app-reexport-migration.md` (unnumbered migration note) | `app.py` Test-Seam Re-Export Migration Plan | In Progress (27 `app.X` sites remain 2026-10-11, was 174; see note in file). |
| — | `module-hacks-migration.md` (unnumbered migration note) | Migration away from `_RecordingModule` sys.modules hack | Accepted: COMPLETE for recording (2026-08-25); `_pkg.X` removal addendum 2026-08-26 (see note in file). |
| — | `source-text-test-migration.md` (unnumbered migration note) | Source-text-pinning tests migration | Accepted (chip-away migration in progress; content active). |
| — | `test-2-time-sleep-migration.md` (unnumbered migration note) | `time.sleep` → condition-wait migration | Accepted (chip-away migration in progress; content active). |

## Template

- `template.md` Boilerplate scaffold for new ADRs (not a decision itself).

## How to add a new ADR

1. Copy `template.md` to `<next-number>-<kebab-title>.md` (zero-padded, hyphen separator).
2. Set the H1 to `# ADR <next-number>: <Title>`.
3. Set Status (Proposed / Accepted / Deprecated / Superseded).
4. Update this index and any cross-references in other ADRs/docs.
