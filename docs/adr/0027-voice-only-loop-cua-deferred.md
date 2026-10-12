# ADR-0027: Voice-only conversational loop first (STT → LLM → TTS), CUA deferred

## Status

Proposed (documented for future implementation, no code yet).

## Context

Owner vision has 4 parts: (1) STT dictation (exists), (2) TTS spoken replies,
(3) decision model (TypeSafe Jev: `typesafe/jev-1.13` via OpenRouter Decisions
API), (4) CUA Driver desktop control (MIT, Win/Mac/Linux, MCP/CLI/SDK).

Owner decisions 2026-10-11/12: scope v1 to option C — voice-only chat loop,
no computer control. CUA stays documented, explicitly deferred.
`llm_polish.py` (cloud) is DEFERRED for this feature — v1 brain MUST be a
local model, fully offline. Prefs: local-first + BYO Jev key only as
opt-in upgrade, TTS budget ≤ 1 GB, auto-act when confident
(applies to future CUA phase, not v1).

Current stack (verified):

- STT: faster-whisper (ctranslate2) + Qwen3-ASR ONNX + Parakeet ONNX + cloud
  (OpenAI/Groq/Deepgram) via `voice_typer/server/cloud_engines.py`.
- LLM text path: `voice_typer/server/llm_polish.py` exists (cloud,
  consent-gated, ADR-0017) but is OUT OF SCOPE for this feature —
  owner order: local model only. No local chat LLM yet, no TTS engine
  yet. Project is torch-free (Phase 1c): local LLM MUST NOT reintroduce
  torch/transformers into the sidecar; run via native GGUF binary
  (llama.cpp-style sidecar) or onnxruntime-genai, as an on-demand pack.
- Packaging: slim-core target 80 MB (ADR-0026), runtime-pack split
  (`docs/plan-runtime-pack-split.md`): installer ~226 MB today,
  installed ~700 MB. New engines MUST ship as on-demand packs, never
  in the base installer.
- Constraints: C-DATA-1 (cloud only if user-configured + consented),
  C-MIC-3 (JIT consent gate, no persistent banners), C-BG-1 (no mic
  when hidden), C-BRAND-1 (`{appName}` placeholder), 8-locale parity,
  two-allowlist IPC parity (`registry.py` + `allowlist.rs`).

Web findings (2026-10-11):

- Jev is decision-only, not a planner: text-in → typed Choice/Score/Noul +
  calibrated probs, no generation, no tool calls, no multi-step
  (openrouter.ai/blog/insights/what-is-jev). Pricing $0.042/M input,
  output free, 32k ctx, ~$0.00002/call. Weights closed, hosted-only —
  no HF local Jev exists. Mainly-offline therefore needs a local
  surrogate (tiny classifier or local-LLM structured choice) with
  Jev API as opt-in upgrade.
- CUA Driver: `model → harness → Driver → OS a11y+input`
  (cua.ai/docs/cua-driver/concepts/how-cua-driver-works). One exact
  target per call, ladder element-bg → pixel-bg → page/CDP → foreground,
  `effect/verified/escalation` per call, re-observe after anything
  short of `confirmed`. Daemon identity per OS (TCC, interactive
  session, Wayland bg-key refusal). Deferred whole.
- TTS: Piper 61 MB model, GPL-3.0, 30+ langs, CPU-first, peak ~2.6 GB
  bench / ~300 MB resident, FTTS ~1720 ms bench (~40 ms first-audio
  streaming); Kokoro-82M 82M params Apache-2.0, 341 MB model, 8 langs,
  54 voices, peak ~2.0 GB / ~900 MB resident, ~90 ms first-audio, no
  cloning; XTTS v2 ~4.5 GB — rejected over budget
  (picovoice.ai/blog/on-device-tts, contracollective.com 2026 bench).
  Both Piper + Kokoro fit ≤ 1 GB; latency > 700 ms feels broken
  (turn-taking research).
- Safety: pop-up IDPI 86% ASR + EchoLeak CVE-2025-32711 zero-click —
  why open-ended + auto-confirm must wait for the CUA phase with
  Jev gating, denylist, audit log (see § Future).

## Decision

1. v1 = voice-only loop, no CUA binary, no harness, no `cua-driver`
   dependency, no desktop-control IPC.
   Pipeline: hotkey/record → existing STT → conversational LLM →
   TTS speak + transcript in History. Dictation (paste-to-app) unchanged.
2. Brain = local small chat model, fully offline. `llm_polish.py`
   cloud path NOT used by this feature. Candidate class: 0.5–1B
   GGUF quant (~700 MB–1 GB file, min 4 GB RAM; useful 3B needs
   ~6 GB) via llama.cpp-style native binary, or ORT-genai equivalent.
   Ships as versioned on-demand pack (manifest + verify-before-use,
   like runtime-pack), NOT in base installer. Short spoken-style
   replies, no paste. Cloud stays available only in the existing
   polish feature, never as the assistant brain.
3. TTS = separate on-demand pack (mirrors runtime-pack pattern):
   default Piper voice (~61 MB), optional Kokoro voice pack
   (~341 MB). Engine + voices verify-before-use
   (`pack-manifest.json` pattern), background download, "Preparing
   voice…" degraded line, speaker-output via existing audio path
   (no mic-path changes). Apache-2.0 Kokoro preferred where
   redistribution matters; Piper GPL-3.0 noted at pack boundary.
4. Decision model in v1 = local heuristic router only
   (dictate vs chat vs help — deterministic, no network). Full
   Jev/local-surrogate gating ships with the future CUA phase.
   If user already has an OpenRouter key, v1 MAY log (not enforce)
   a Jev `Noul` relevance check; never blocks without consent.
5. CUA explicitly deferred. Re-entry requires: voice loop green +
   safety gate (Jev-or-surrogate + denylist + per-action audit) +
   harness design + pack + parity tests. No CUA strings, no MCP
   lifecycle, no screenshot/a11y capture in v1.

## Consequences

Positive:

- Smallest increment proving the loop (mic → words → reply → speech)
  without desktop-control risk, perms, or IDPI surface.
- Zero installer growth: base stays on ADR-0026 80 MB track; TTS is
  opt-in download under the 1 GB budget.
- Reuses hardened pack-verify pattern; zero new network code —
  v1 makes NO chat network calls (C-DATA-1 clean by construction).

Negative:

- v1 brain is weaker than frontier cloud (small local model:
  shorter context, dumber reasoning); quality scales with pack size.
- Extra download: chat-model pack (~1 GB class) + TTS pack on top of
  the existing runtime-pack; total disk must be tracked against the
  plan-runtime-pack budget.
- Two TTS voices to license/track (GPL-3.0 vs Apache-2.0); Kokoro
  only 8 langs vs Piper 30+.
- Bench peak RAM (2+ GB) means TTS is desktop/server tier, not
  embedded, despite small model files.

Neutral:

- New user strings (voice pack states, chat errors, TTS pickers) need
  all 8 locales + `{appName}` at implementation time (not in this ADR).
- New IPC (`chat_reply`, `tts_speak/stop`, pack events) must extend
  BOTH allowlists + `ALLOWED_EVENT_TYPES` + parity tests when built.
- Future CUA phase inherits owner prefs recorded here: mainly-offline
  surrogate + BYO Jev, open-ended scope, ≤ 1 GB TTS, auto-when-confident
  thresholds (approve ≥ 0.9 / block ≤ 0.1 / else review per Jev
  gate-tool-calls cookbook).

## References

- https://cua.ai/cua-driver
- https://cua.ai/docs/cua-driver/concepts/how-cua-driver-works
- https://openrouter.ai/blog/insights/what-is-jev/
- https://openrouter.ai/docs/cookbook/building-agents/gate-tool-calls-with-jev
- https://picovoice.ai/blog/on-device-tts/
- `docs/plan-runtime-pack-split.md`, ADR-0026, ADR-0017, ADR-0016
