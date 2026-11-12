# ADR-0029: Closed lifecycle vocabularies at every boundary

## Status

Accepted (2026-11-09)

## Context

The app has many lifecycles (dictation, waveform bubble, media jobs,
provider loading, hotkeys, chat turns, TTS, sidecar/worker processes). Some
are already modelled well: `AppState` is an enum, the bubble has one pure
`nextBubbleMode` reducer with an exhaustiveness guard, chart visuals have an
explicit `ChartPhase` table, and the sidebar submenu has one state with three
transitions.

The failures cluster at **producers**: a lifecycle is a free string written
from many call sites, the renderer keeps a second literal union, and incoming
values are cast through without validation. Media jobs were the clearest
case: `MediaJob.status`/`phase` were `str` (`media_ingest/jobs.py`), the
progress event declared a five-value TS union, and the renderer assigned
`data.phase` directly. An unknown or renamed phase could stick a row on
"Preparing…" forever; a typo lived only in one producer.

The constraints are the usual ones: Python and TypeScript must agree on wire
values, the app ships a desktop bundle, the renderer is event-driven over
local IPC, and the existing reducers/tests are load-bearing.

## Decision

Adopt a **closed lifecycle vocabulary** policy, detailed in
`docs/code-notes/state-machines.md`:

1. The producer owns a `StrEnum` (Python) or a literal union derived from a
   const array (TS). Wire values are the enum values.
2. Consumers validate incoming values and keep their last known state on an
   unknown value; they never cast an unvalidated value into state.
3. Non-linear transitions live in one pure table/reducer next to the
   vocabulary; side effects stay at the call site.
4. A boundary publishes a snapshot whose fields move together, never two
   flags that can disagree (already required by C-HOME-1 and C-PARITY-2).
5. No state-machine library: the existing reducers are the pattern, and a
   framework would add bundle cost, a second vocabulary, and cross-language
   friction without removing a real risk.

The first implementation is media jobs: `JobStatus`/`JobPhase` in
`voice_typer/server/media_ingest/lifecycle.py`, a `parse_job_phase` guard at
the progress publisher, and `MEDIA_JOB_PHASES`/`isMediaJobPhase` in
`pages/media/hooks/useMediaJobs.ts`. Pins:
`tests/test_media_job_lifecycle.py` and the `useMediaJobs` guard test.

## Consequences

**Positive**

- Impossible or misspelled states cannot reach the UI; an unknown push
  leaves the last valid state instead of half-updating a row.
- One spelling per value across Python, the event payload, and the renderer;
  agents can find the machine in one row of the catalogue.
- Renewed changes get a cheap pin (enum values + parse/guard test) instead of
  a new UI regression class.

**Negative**

- Each migrated lifecycle pays a small migration cost (enum + imports +
  guarded consumers) and a test.
- Wire values are now a deliberate contract: renaming one is a breaking
  change that must update both sides in the same commit (C-TEST-10).
- Guards can hide a producer bug as a stale UI state; the producer logs the
  unknown value so it is diagnosable (C-UXERR-5/C-LOG-5).

**Neutral**

- No new runtime dependency and no code generation.
- The catalogue is normative: a new lifecycle is not complete until its row
  and pinned tests exist.
- Lifecycles that are local flags (single-threaded, never crossing a
  boundary) are out of scope; the policy targets boundary state.
