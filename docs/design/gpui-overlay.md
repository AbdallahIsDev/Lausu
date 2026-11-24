# GPUI bubble overlay — research, design, and spike

Research date: 2026-11-24. Owner task: evaluate a **second** overlay renderer
implementation while keeping the current Tauri bubble unchanged and the default.

## Plain-English summary

- The shipped bubble is a hidden Tauri webview window (`label: "bubble"`) that
  listens to the *existing* sidecar event stream. It is transparent, borderless,
  always-on-top, non-focusable, excluded from the taskbar, and placed before its
  first show. Do not touch it in this task.
- GPUI is a real, GPU-accelerated Rust UI framework. It runs on Windows
  (Win32 windows, DirectX 11 / DirectX rendering, DirectWrite text). It is still
  pre-1.0, and the upstream `gpui` crate on crates.io is stale (0.2.2, published
  2025-10-22); publishing current GPUI is blocked by unpublishable sibling
  crates. A maintained community fork, `gpui-ce` 0.3, is published on crates.io
  and supports Windows.
- **GPUI does not give us the overlay window for free.** Its window options have
  no always-on-top, no per-pixel transparency, no click-through/hit-test mode,
  and no no-activate style. Those are Win32 window-style/DirectComposition
  concerns. The current bubble already gets them from Tauri config plus explicit
  Win32 style calls in the host. A GPUI version must re-create them by hand.
- Status of the other capabilities: multi-monitor placement has a GPUI
  `DisplayId`/`window_bounds` API, but per-monitor DPI correctness and the
  work-area clamp need Win32 verification; text rendering uses Parley +
  DirectWrite (upstream) / DirectX (fork); AccessKit exists in current GPUI but
  screen-reader support on Windows has been an open upstream gap; Japanese IME
  toggle keys have a known Windows issue.
- Recommendation: **needs a local spike, not a go decision.** There is a
  standalone prototype at `tools/overlay-gpui/` that renders the existing bubble
  states from the existing JSON event names. It does not claim the shipped
  overlay window behavior. A local Windows desktop with MSVC + Windows SDK is
  required to decide go/no-go.
- Any future selection uses a canonical config value `overlay_renderer:
  "legacy" | "gpui"`, default `"legacy"`, with no end-user control until the
  owner decides. It is design-only here — no config schema, renderer, setting,
  workflow, or test was changed.

## D1 — Research (upstream documentation, labeled)

Firecrawl CLI was available (`firecrawl --status`: authenticated, credits
647/1000 at task start). All web claims below come from Firecrawl search/scrape
during this task; a URL label indicates the source type.

### Sources

| Label | URL | What it establishes |
| --- | --- | --- |
| Upstream project site | <https://gpui.rs/> | GPUI intro, docs index, hello-world example; links core docs at `zed-industries/zed/tree/main/crates/gpui`. |
| Upstream docs/examples | <https://gpui.rs/examples/> | "Metal on macOS, DirectX 11 on Windows, wgpu on Linux; X11 or Wayland handles Linux windowing"; AccessKit tree; "GPUI is tied to Zed"; CSS compatibility incomplete. |
| Upstream README (main branch) | <https://github.com/zed-industries/zed/blob/main/crates/gpui/README.md> | Pre-1.0, frequent breaking changes; latest stable Rust; Windows needs no gpui_platform features, uses Win32 + DirectWrite; AccessKit guide link. |
| Upstream crate manifest | <https://raw.githubusercontent.com/zed-industries/zed/main/crates/gpui/Cargo.toml> | `version = "0.2.2"`, `license = "Apache-2.0"`, `publish = true`, `windows-manifest` feature, Windows-only `windows` crate deps. |
| Registry (upstream crate) | <https://crates.io/crates/gpui> | `gpui 0.2.2`, Apache-2.0, 5.05 MiB source, 66K SLoC; README still says "macOS or Linux" (stale relative to main). |
| Upstream maintainer discussion | <https://github.com/zed-industries/zed/discussions/55271> | Current GPUI cannot be published: three path deps have `publish = false`; 0.2.2 predates the platform split; maintainer said on 2026-10-30 that automated weekly releases are being set up, "not quite ready yet". |
| Registry (community fork) | <https://crates.io/crates/gpui-ce> | `gpui-ce 0.3.0`, Apache-2.0, Rust 1.95+, MSVC toolchain + Windows SDK; Windows = Win32 windows + DirectX; Parley text; published ~1 month before research; 1.23 MiB source. |
| Registry (fork platform crate) | <https://crates.io/crates/gpui_ce_platform> | `gpui_ce_platform 0.3.0`, Apache-2.0, 70.6 KiB source. |
| Fork API docs | <https://docs.rs/gpui-ce/0.3.0/gpui/struct.WindowOptions.html> | 18 fields: bounds, titlebar, focus, show, kind, movable, resizable, display_id, `linux_window_background`, …; **no always-on-top, transparency, or hit-test field**. |
| Upstream API docs | <https://docs.rs/gpui/0.2.2/gpui/struct.WindowOptions.html> | 14 fields in the published crate; same gap. |
| Fork platform docs | <https://docs.rs/gpui_ce_platform/0.3.0/gpui_ce_platform/> | `application()` selects the OS platform; no per-OS `cfg` in app code; `headless()` exists for tools/tests. |
| Fork app API docs | <https://docs.rs/gpui-ce/0.3.0/gpui/struct.App.html> | `refresh_windows()` for state outside entities, `App::spawn` + background executor for blocking work. |
| Upstream issue (transparency) | <https://github.com/zed-industries/zed/issues/5040> | Closed transparency feature issue; Linux transparency/blur merged in #10973; Wayland blur needs compositor support. No shipped Windows overlay primitive is claimed here. |
| Upstream issue (Windows blur) | <https://github.com/zed-industries/zed/issues/67282> | Report: acrylic blur broken on Windows 11 once the first DirectComposition frame is presented (status not independently confirmed in this task — **suspected** until re-read on a local machine). |
| Upstream issue (a11y) | <https://github.com/zed-industries/zed/issues/41138> | Windows screen-reader accessibility missing; AccessKit plan; 2026-05 update: PR #56065 "mostly working" (GPUI only, not Zed). |
| Upstream issue (IME) | <https://github.com/zed-industries/zed/issues/40321> | Windows Japanese ATOK IME toggle keys not working properly. |
| Upstream issue (multi-monitor) | <https://github.com/zed-industries/zed/issues/38791> | Font-size settings break with two mixed-DPI monitors. |
| Upstream discussion (Windows roadmap) | <https://github.com/zed-industries/zed/discussions/15764> | Community asks for GPUI Windows support roadmap; useful context only, not a contract. |
| Microsoft docs (window styles) | <https://learn.microsoft.com/en-us/windows/win32/winmsg/window-features> | Layered windows: `WS_EX_LAYERED`; zero-alpha/color-key areas let mouse messages through; `WS_EX_TRANSPARENT` passes mouse events to windows underneath. |
| Microsoft docs (layered API) | <https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-setlayeredwindowattributes> | `SetLayeredWindowAttributes` sets per-window alpha/color key; style is set via `SetWindowLong` after creation. |
| Microsoft docs (extended styles) | <https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles> | `WS_EX_LAYERED`, `WS_EX_TRANSPARENT`, `WS_EX_TOPMOST`, `WS_EX_TOOLWINDOW`, `WS_EX_NOACTIVATE` vocabulary. |
| Microsoft docs (DPI) | <https://learn.microsoft.com/en-us/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows> | Per-monitor DPI awareness is the recommended model for desktop apps. |
| Third-party crate docs (size) | <https://crates.io/crates/gpui-component/0.5.0> | Claims min binary size 12 MB for a GPUI + gpui-component hello world; Apache-2.0. Directional only, not a measurement of this app. |
| Third-party install docs | <https://gpui-kit.com/docs/installation> | Windows 10+, Rust 1.95+, MSVC/SDK; `gpui-pre` naming for published Zed snapshots. |

Verified vs suspected: status/license/backend/build facts above are from the
linked pages. Issue *resolution* states that were not opened individually are
labeled suspected. Nothing here is derived from training data.

### Current status and license

- Upstream `gpui` is pre-1.0 and actively developed for Zed; contributions are
  tied to Zed's monorepo (upstream README / examples site).
- Core crate license is Apache-2.0 (upstream manifest; crates.io metadata).
  `gpui-ce` and `gpui_ce_platform` are also Apache-2.0. Do **not** add
  `gpui-component`/GPL-licensed sibling crates to this work; the prototype draws
  the pill with core elements only.
- Publishing is a real constraint: current upstream HEAD cannot be published
  because `gpui_macros`, `gpui_shared_string`, and `gpui_util` are
  `publish = false` (maintainer discussion). Consume either the stale registry
  crate, a pinned git revision, or the community fork; a git dependency is not
  publishable to crates.io, so the fork is the practical registry option today.

### Windows support and maturity

| Area | Evidence | Assessment for our overlay |
| --- | --- | --- |
| Rendering backend | GPUI examples: DirectX 11 on Windows; gpui-ce: Win32 + DirectX; upstream README: Win32 + DirectWrite text | Viable for a small always-on-top pill. DirectX 11 + DirectWrite are mature; fork uses Parley for shaping/hit testing. |
| Transparent / click-through / always-on-top / borderless | Neither `WindowOptions` exposes these; Microsoft docs show they are Win32 layered-window styles. Upstream transparency issue is closed but only claims Linux support | **Gap.** Need `WS_EX_LAYERED` + alpha/color key or `WS_EX_TRANSPARENT`, `WS_EX_TOPMOST`, `WS_EX_TOOLWINDOW`, `WS_EX_NOACTIVATE`, plus a `WM_NCHITTEST` policy for the mic/dismiss buttons. Must be proven on a real desktop. |
| Per-monitor DPI | `WindowOptions.display_id`, `Bounds<Pixels>`, Microsoft per-monitor DPI guidance; upstream issue #38791 shows mixed-DPI bugs exist | Needs spike. Existing host already resolves cursor monitor, physical work area, and scales the edge margin (`commands.rs:95-132`). A GPUI port must match that, including the C-WIN-2 work-area clamp. |
| Multi-monitor placement | `display_id` selects a monitor; host code has `resolve_monitor_at_point` / cursor-monitor fallback (`commands.rs:137-179`) | Feasible, but edge placement and drag session memory must be reimplemented; no free parity. |
| Input handling | GPUI has actions, key dispatch, mouse handlers, and `cx` event APIs (upstream examples); `focus: false` exists in window options | Enough for mic/dismiss buttons. The bubble is deliberately non-focusable; keyboard focus semantics need a decision (current renderer's focus ring never renders — `bubble/constants.ts:58-63`). |
| Accessibility | GPUI uses AccessKit; Windows screen-reader support issue #41138 with PR #56065 "mostly working" in 2026-05 | Risk. Current bubble has `aria-live` + state-aware `aria-label` (`Bubble.tsx:477-493`); parity needs an AccessKit node tree and local screen-reader test. |
| Text rendering / IME | Core Parley + DirectWrite (fork README / upstream README); Windows ATOK IME issue #40321 | Text rendering viable; IME is not exercised by this overlay (labels are fixed), so low risk unless future input fields appear. |
| Binary size | gpui 0.2.2 source 5.05 MiB; gpui-ce 0.3.0 source 1.23 MiB; third-party 12 MB min binary claim | **ESTIMATE** only: a small GPUI binary is plausibly ~10–20 MB before strip/LTO; not measured here (no link on this sandbox). Install impact must be measured on MSVC toolchain. |
| Compile time | Source sizes above; no upstream wall-clock figure | **ESTIMATE**: first clean GPUI build is minutes, not seconds. This task's `cargo check` timing (see D3) is for this sandbox only, not a CI budget. |

### How it is consumed / Windows build requirements

- Upstream: `gpui = { version = "*" }` plus optional `gpui_platform`; repository
  HEAD additionally needs its workspace siblings. `cargo publish -p gpui` fails
  today (maintainer discussion).
- Fork (chosen for the prototype): alias
  `gpui = { package = "gpui-ce", version = "0.3" }` and
  `gpui_platform = { package = "gpui_ce_platform", version = "0.3" }`;
  `gpui_ce_platform::application()` picks the OS backend.
- Windows: Rust 1.95+, MSVC toolchain and Windows SDK (fork crates.io page;
  third-party gpui-kit docs). The app's own dev toolchain is GNU
  (`AGENTS.md` C-TDEV-1) — **do not change it**; a GPUI build needs a separate
  MSVC shell/toolchain.
- `windows-manifest` (upstream feature) embeds a DPI awareness manifest via
  `embed-resource`; per-monitor DPI behavior must be checked for whatever crate
  set we actually ship.

### Known issues / go-no-go inputs

- Windows acrylic blur broken with DirectComposition (#67282, suspected until
  reproduced).
- Windows screen-reader accessibility gap (#41138; AccessKit PR #56065 in
  progress in 2026-05).
- Japanese IME toggle keys (#40321) — low exposure for a label-only bubble.
- Font-size/DPI break on mixed monitors (#38791) — directly relevant to a
  draggable always-on-top pill.
- Cursor style not applied until mouse moves (#67007) and dialog focus flicker
  (#65686) — lower priority UX polish, not blockers.
- Upstream release pipeline unstable (discussion #55271): pin any git revision
  or fork version exactly, with hashes in packaging.

### Current bubble map (file:line, verified by reading this checkout)

**Window creation / host style**

- `src-tauri/tauri.conf.json:45-63` — window label `bubble`, `url: bubble.html`,
  240×80, `decorations: false`, `transparent: true`, `shadow: false`,
  `alwaysOnTop: true`, `skipTaskbar: true`, `visible: false`, `focus: false`,
  `focusable: false`.
- `src-tauri/src/commands/bubble/window.rs:50-81` — adds `WS_EX_NOACTIVATE`
  (show must never steal focus from the dictated field).
- `window.rs:83-116` — on-screen truth: Tauri visibility + `IsWindowVisible` +
  DWM cloaked check.
- `window.rs:118-173` — level-triggered visibility reconciler (2 s tick,
  rate-limited INFO).
- `window.rs:175-208` — show: reassert no-activate style, work-area clamp, show,
  forced `SW_SHOWNOACTIVATE` fallback, chrome hardening.
- `window.rs:210-223` — OS-level show that never activates.
- `src-tauri/src/commands/bubble/commands.rs:79-132` — `bubble_config` edge
  placement before first show; `place_bubble_on_edge` uses cursor monitor,
  `monitor.work_area()`, physical pixels, DIP-scaled margin, no-op when already
  placed.
- `commands.rs:137-179` — monitor resolution with OS hit-test, manual fallback,
  primary-monitor last resort.
- `src-tauri/src/window_events.rs:13,53-69` — moved/resized/scale-factor events
  drive chrome hardening + work-area clamp; `note_bubble_user_moved` clears the
  configured edge for the session.

**Renderer**

- `voice_typer/client/src/renderer/src/bubble-main.tsx:19-50` — bridge install,
  global error handlers, `window.bubble.signalReady()`, `ErrorBoundary
  fallback={null}` render at `bubble-main.tsx:66-72`.
- `.../src/lib/tauri-bridge/bubble-namespace.ts:25-94` — main renderer gets only
  five mutators (`show`, `signalReady`, `setPosition`, `setDraggable`,
  `moveBy`); `bubble-namespace.ts:96-99` enforces the split; `:101-149`
  subscriptions (`bubble_level`, `bubble:show`, `bubble:hide`,
  `bubble:draggable`, `bubble:locale-changed`); `:151-250` bubble-only extras
  (`bubble:config`, `bubble:set-state`, `resizeTo`, `toggleDictation`,
  screenshot capture, `hideComplete`, `dismiss`).
- `.../src/Bubble.tsx:96-131` — UI state (mic button, dismiss, timer, screenshot
  beta, behavior); `:173-205` consumes `bubble:config`; `:407-470` fade/exit
  animation and `hideComplete`/`resizeTo` lifecycle; `:475-519` pill markup,
  `aria-live`, drag region.
- `.../src/bubble/constants.ts:3-13` — mode union (recording, transcribing,
  loading, idle, fading, error, blocked, cancelling, permission_revoked,
  paste_failed); `:107-154` single mode reducer; `:156-180` state payload parser.
- `.../src/bubble/useBubbleStateMachine.ts:87-166` — `bubble:set-state` handler.
- `.../src/bubble/useBubbleBridge.tsx:59-93,138-185,209-236` — central bridge,
  authoritative mode, single listener per event.
- `.../src/bubble/useAudioLevels.ts:160-192,264-359` — rAF visualizer gated by
  authoritative mode; `bubble_level` drives bar heights.
- `.../src/bubble/useThemeSync.ts:8-139,150-165` — theme/locale/text-size sync
  from `bubble:config` and `bubble:locale-changed`.

**Backend → host → bubble event path**

- `voice_typer/server/event_bus.py:38-40,205-209` — event catalogue and
  allowlist entries `bubble_show`, `bubble_hide`, `bubble_level`,
  `bubble_set_state`, `bubble_config`.
- `voice_typer/server/waveform.py:10-25` — active states; `:28-49` callback
  slots; `:66-95` single visibility policy; `:104-151` show/hide/set_state;
  `:177-190` smoothed RMS/peak.
- `voice_typer/server/waveform_bubble_wiring.py:57-68` — publishes show/hide;
  `:70-86` throttles level to ~125 Hz and queues it; `:88-150` bounded queue +
  coalescing worker (RACE-016 daemon with why-comment); `:152-180` publishes
  `bubble_set_state` / `bubble_config` payload subsets.
- `src-tauri/src/sidecar/ws/event_protocol.rs:10-39` — `ALLOWED_EVENT_TYPES`
  (defense in depth); `:142-161` snake_case → `bubble:*` translation.
- `src-tauri/src/sidecar/ws/reader.rs:100-120` — drops unknown event types;
  `:122-146` `bubble_config` edge placement before first show; `:148-161`
  `bubble_level` typed fast path coalesced to ≤30 Hz; `:163-186` show/hide
  window effects.
- `src-tauri/src/main.rs:46-49,124-142` — bubble commands imported and
  registered in `generate_handler!`; `:202-204` dismiss shortcut + reconciler.
- `src-tauri/capabilities/bubble-runtime.json:3-8` — SEC-026 least-privilege
  sandbox for the bubble webview.
- `voice_typer/server/config/_schema.py:259-286` and
  `voice_typer/server/config_validators/allowlist.py:311-324` — canonical bubble
  config fields (`bubble_position`, `bubble_behavior`, `bubble_draggable`,
  `bubble_mic_button`, `bubble_show_recording_timer`, `bubble_x/y/scale`, …).
- Tests that pin current behavior: `src-tauri/src/commands/bubble/{tests,
  placement_tests, clamp_tests, rate_limit_tests, coalesce_tests}.rs`,
  `src-tauri/src/sidecar/ws/event_protocol_tests.rs`, and renderer
  `bubble/__tests__/*` + `bubble-*.test.tsx`. None were modified.

## D2 — Design (design only, nothing wired)

### Architecture options

**Option A — separate Rust binary launched/supervised by the sidecar (preferred
for a spike).** Build `overlay-gpui.exe` from `tools/overlay-gpui/`-derived
production code; the sidecar/host spawns it with a parent-PID watch and OS-level
kill binding (`AGENTS.md` C-HOST-1), only when `overlay_renderer == "gpui"`.
Pros: process isolation — a GPUI/DirectX crash cannot take down the host; the
legacy webview stays compiled and available for fallback; no changes to the
Tauri window/capability surface (SEC-026) and no second IPC allowlist. Cons:
another process to supervise, another binary to sign/package, process-to-host
bridge for the five renderer→host commands.

**Option B — embed GPUI in the Tauri host as a second native window.** Use GPUI
views inside the existing host process, next to the Tauri bubble window. Pros:
no process boundary for commands; easier shared state. Cons: couples Tauri's
runtime to GPUI/DirectX lifetime and toolchain (GNU host vs MSVC GPUI), mixes
two event loops, and any GPUI panic can kill the app. Rejected for first spike.

Recommendation: Option A, behind a build-time/dev flag first; no user-facing
selection until a desktop spike proves parity.

### State / IPC contract — reuse the existing protocol

- Sidecar→renderer events stay exactly `bubble_show`, `bubble_hide`,
  `bubble_level`, `bubble_set_state`, `bubble_config` with their current payload
  shapes (`event_bus.py:38-40`, `waveform_bubble_wiring.py:152-180`). No new
  event names, no "v2" schema, no second authority.
- The host fans the same allowlisted WS frames (`event_protocol.rs:10-39`,
  `reader.rs:100-186`) to whichever renderer is active. The GPUI renderer keeps
  the same mode reducer semantics (`bubble/constants.ts:107-154`), including
  `still_transcribing`/`cloud_cancel_requested` as label-only hints and the
  `fading` override by `recording`/`loading`.
- Renderer→host commands keep the five main mutators and bubble extras' names and
  argument keys: `bubble_show`, `bubble_signal_ready`, `bubble_set_position`
  (`position`), `bubble_set_draggable` (`draggable`), `bubble_move_by`
  (`dx`,`dy`), `bubble_resize` (`width`,`height`), `bubble_hide_complete`,
  `bubble_dismiss`, `bubble_toggle_dictation`,
  `bubble_request_screenshot_capture` (`cycle_id`,`left`,`top`,`width`,`height`)
  (`bubble-namespace.ts:31-248`, `main.rs:124-142`). Transport changes from
  Tauri `invoke` to a pipe/socket envelope; the command names and payload fields
  do not.
- E9/P4: define shared send/receive types and a round-trip test for each
  command/event before wiring. Silent `int`↔`str` coercion is not acceptable.
- Config canonicality (C-CONF-1, SEC-002): `overlay_renderer` lives in the one
  canonical `config.json`, validated through `set_config`'s allowlist. It is
  **not** added by this task — only specified here. No renderer-local switch,
  no plugin-style derived config file.

### Selection, fallback, and hidden rollout

- `overlay_renderer: "legacy" | "gpui"`, default `"legacy"`. Hidden from all
  settings UI/locales/onboarding until the owner approves; C-I18N-1/C-UI-17
  apply if it ever becomes visible.
- Startup: read the value once from canonical config. `legacy` keeps the current
  Tauri window exactly as shipped (no new window flags, no changed default).
- `gpui`: probe for the binary (existence + version/hash + a bounded ready
  handshake). If missing, fails to start, or fails readiness → fall back to
  `legacy` and log one WARN with the reason (C-LOG-6: name the lever, no fake
  "actual" state). Bounded retries only (C-START-3), never one process per
  hotkey press.
- Never run both renderers for the same cycle: one owner of the visible pill
  (C-CONC-1 spirit). Switching renderers mid-recording is a post-spike decision.
- Health: parent-PID watch + OS kill binding (C-HOST-1); no orphaned GPUI window
  after a host crash. If the GPUI process dies, legacy can be shown on next show
  with a fresh state snapshot; do not guess/restore stale transcript state.

### Packaging (ESTIMATE markers)

- Layout: ship `overlay-gpui.exe` as a separate resource/sidecar next to the
  existing helpers; keep the legacy webview assets present in every build until
  the owner flips the default. Build it with MSVC + Windows SDK in a dedicated
  workflow leg; do not change the app's GNU toolchain (`AGENTS.md` C-TDEV-1).
- Integrity: record SHA-256 hashes for the binary and any shipped runtime DLLs
  in the existing manifest/hash location; notices must list Apache-2.0 GPUI-CE,
  Apache-2.0 upstream GPUI lineage, and the Rust/serde licensing. No GPL sibling
  crates.
- Installer size impact: **ESTIMATE** +10–20 MB compressed for a stripped,
  LTO'd GPUI binary plus DLLs; based on the 12 MB third-party hello-world claim
  and source sizes, **not measured** here. Measure with the real MSVC release
  build before any owner decision. No measurements imply no packaging change in
  this task.
- CI: prototype lives outside the app workspace (`[workspace]` in its own
  `Cargo.toml`) and is not referenced by any workflow. Any future production
  port needs explicit CI wiring + full re-run + owner sign-off; CI files are not
  touched here.

### Risks and go/no-go criteria

Go only if a local Windows desktop spike proves all of these:

1. A borderless, transparent, non-activating, always-on-top GPUI window can be
   created on Windows 10/11 and keeps its alpha through DirectX/DirectComposition
   presentation (issue #67282 must not reproduce).
2. Click-through covers the transparent pill body while the mic/dismiss buttons
   remain clickable; no `WS_EX_TRANSPARENT` blanket that kills the controls.
3. Placement matches the host's behavior: cursor monitor, physical work area,
   taskbar clamp (C-WIN-2), configured top/bottom edge before first show
   (C-WIN-1), and session-local drag memory.
4. Per-monitor DPI + mixed-DPI multi-monitor behave correctly; no font-size
   regression of the kind in issue #38791.
5. AccessKit tree exposes label/mode with an `aria-live`-equivalent announcement
   on Windows; local screen-reader smoke test passed (issue #41138).
6. Binary size, cold start, and frame cost measured on target hardware; no
   visible latency vs the current webview bubble.
7. Crash/fallback drill: missing binary, bad hash, readiness timeout, and
   process death all return to legacy with one diagnostic line each.

No-go (do not wire) if 1–3 fail; those are the minimum viability bar for an
overlay. 4–7 are release gates.

### Effort estimate (rough, uncommitted)

- Local desktop spike for items 1–5: ~3–5 engineer-days (Win32 style/DirectX
  experiments + AccessKit smoke test).
- Streaming bridge + command parity + round-trip tests: ~2–3 days.
- Packaging, hash/notices, fallback, installer measurement: ~2–3 days.
- Total ~7–11 engineer-days before owner decision, excluding CI work and a full
  regression suite. These are estimates, not commitments.

## D3 — Standalone prototype

Location: `tools/overlay-gpui/` (own `[workspace]`, outside
`src-tauri/Cargo.toml` workspace and outside all CI workflows).

- `src/protocol.rs` — reuses the existing event envelope and command names;
  unit tests in sibling `src/protocol_tests.rs`.
- `src/state.rs` — mirrors the shipped bubble mode table and config/level/state
  application; unit tests in sibling `src/state_tests.rs`.
- `src/view.rs` — GPUI `Render` placeholder pill (dot + label).
- `src/main.rs` — reads newline-delimited JSON from stdin to EOF, then opens a
  normal GPUI window; `--demo` injects placeholder events. Emits
  `bubble_signal_ready` on stdout as a JSON command line.
- `sample-events.jsonl` — config → show → recording → level → transcribing →
  hide.
- `README.md` — exact Windows/MSVC build and run steps.

`cargo check --all-targets` result: **GREEN (exit 0)** on this sandbox. Exact
sequence:

1. `cargo check --all-targets` (repo GNU toolchain) → `exit=101`, 67.8 s:
   `error: error calling dlltool 'dlltool.exe': program not found` while
   compiling `windows-sys`.
2. Same command with `C:\msys64\mingw64\bin` prepended to `PATH` → `exit=101`,
   148.6 s: `rustc-LLVM ERROR: IO failure on output stream: No space left on
   device` / `os error 112` (C: had ~3.4 GB free; build cache ~1.77 GB).
3. Moved only this task's generated `tools/overlay-gpui/target` to
   `D:\overlay-gpui-target` (338 GB free), set `CARGO_TARGET_DIR` to it, and
   fixed two local API errors (`px` import + f32 cast; `AppContext` trait import,
   `move` closure). → final `cargo check --all-targets`: `exit=0`, 0.8 s
   incremental (full dependency compile in the preceding 181.8 s run).
   `Cargo.lock` pins `gpui-ce 0.3.0` and `gpui_ce_platform 0.3.0`.

This verifies **type/wiring correctness of the prototype source only**. It does
not verify linking, a window opening, overlay styles, DPI, or input — the sandbox
has GNU toolchain, no MSVC/Windows SDK, and no interactive desktop. Those are
the local spike items, so the overall verdict stays "needs local spike".

`cargo test` on the final source state: **4 passed, 0 failed** (protocol envelope
+ command names, hint-state mapping, event-stream visibility), exit 0. Final
`cargo check --all-targets`: exit 0, `Finished dev profile` in 0.62 s, zero
warnings. Logs: `C:\Users\11\AppData\Local\Temp\opencode\overlay-gpui-final2-check.log`
and `...\overlay-gpui-final2-test.log`.

Known prototype limitation by design: it does not set overlay window styles,
does not stream updates after window open, and does not reproduce i18n or the
visualizer; those are the local spike items above.

## D4 — No changes to shipped behavior; dependency/license notes

- No production source, `tauri.conf.json`, config schema, locales, settings UI,
  workflow, test, or `Cargo.toml` of the main app was edited. Current bubble
  behavior and the default renderer remain untouched.
- No commits, pushes, branches, or git write commands were performed.
- PR notes: this is research + a throwaway prototype only. Dependencies used in
  the prototype are Apache-2.0 (`gpui-ce`, `gpui_ce_platform`) and
  MIT/Apache-2.0 (`serde`, `serde_json`). Upstream `gpui` is Apache-2.0. Do not
  introduce GPL-licensed GPUI sibling crates. Licensing must be re-checked when
  an exact production crate revision is chosen.
- Relevant binding rules for any future implementation: C-HOST-1 (child
  liveness), C-WIN-1/C-WIN-2 (placement/work area), C-CONF-1/SEC-002 (one config
  authority + allowlist), SEC-026 (bubble sandbox), C-UI-15 (display only what
  is actually rendering), C-LOG-6 (honest diagnostics), C-I18N-1 (all 8 locales
  if user-facing text is added), C-TEST-6 (full-suite gate before shipping).
