# Plan: model providers (local + hosted), per-domain routing

> **Status:** planning document, 2026-11-01. Nothing in here is implemented unless
> the row says EXISTS. Written after the owner's decision to grow Lausu from a
> dictation app into a multi-model app: **speech-to-text**, **text-to-speech** and
> **text (LLM)** are now three first-class model domains that must each be able to
> point at a different provider, independently.

## 0. Why this document exists

The app can already transcribe, speak and polish, but every one of those paths is
hard-wired to *one* provider shape:

| domain | today | problem |
|---|---|---|
| speech-to-text | 5 local models + **one** cloud provider at a time (`openai`/`groq`/`deepgram`/`gemini`) via a single `cloud_api_key`/`cloud_api_url`/`cloud_model` set | cannot mix, cannot switch per task, cannot use a second provider without overwriting the first |
| text-to-speech | 2 local engines (`audio8`, `magpie`) driven through a local OpenAI-compatible `/v1/audio/speech` route | no hosted TTS at all |
| text (LLM polish) | **one** OpenAI-compatible endpoint (`llm_api_url` + `llm_api_key` + `llm_model`) | no provider choice, no local inference, no model catalogue |

The target: **one key unlocks a whole catalogue, per domain, opt-in.** Entering an
OpenRouter key must make OpenRouter models *available* everywhere without
switching anything on by itself — the user then decides, per domain, whether to use
the local model, OpenRouter, Ollama or LM Studio, and which model id.

## 1. Verified current state (checked against the code on 2026-11-01)

Legend: **EXISTS** = usable today · **PARTIAL** = some code exists, shape is wrong
for multi-provider · **MISSING** = nothing.

| # | Capability | Status | Evidence |
|---|---|---|---|
| 1 | Local ASR engines, model registry, downloader, integrity hashes | **EXISTS** | `server/model_registry.py` (whisper tiny/large-v3/turbo, parakeet, qwen3-1.7b, qwen3-0.6b), `server/security/model_integrity.py`, `server/model_hashes.json` |
| 2 | Cloud ASR (batch) | **EXISTS** | `server/cloud/_providers/{openai,groq,deepgram,gemini}.py`, selected at call time by `resolve_asr` (`asr_provider = "cloud_direct"` keeps the legacy `cloud_*` slot); per-provider consent flags plus the `asr_provider_consent` domain flag (`server/config/_schema.py:139-171`) |
| 3 | Local TTS engines | **EXISTS** | `server/tts/engines.py` (`audio8`, `magpie`, both via OpenAI-compatible `/v1/audio/speech`), `server/tts/manager.py`, `server/handlers/tts_handlers.py` |
| 4 | Hosted TTS | **EXISTS** | `server/model_providers/hosted_tts.py` (voice validation before the request) wired into `tts/manager.py::speak` through `resolve_tts` |
| 5 | LLM polish | **EXISTS** | `server/llm_polish.py` keeps the default endpoint (`DEFAULT_LLM_API_URL`, `server/_paths.py:14`) and presets; `resolve_llm` in `dictation_pipeline/enhancement_steps.py` routes to any registered LLM provider (cloud, OpenRouter, Ollama, LM Studio, local ONNX) at call time, `""` reproduces today's endpoint |
| 6 | Local LLM inference (ONNX/text) | **EXISTS** | `server/model_providers/local_onnx/` (chunker, manifest verification, chat template, device-KV loop) selected by `llm_provider=local_onnx`; `dictation_pipeline/enhancement_steps.py` polishes in sentence-packed chunks |
| 7 | OpenRouter | **EXISTS** | `server/model_providers/openrouter.py` (catalogue, modality classification, free/paid, LLM/ASR/TTS clients) + `provider_*` IPC commands + Providers page |
| 8 | Ollama (local or cloud) | **EXISTS** | `server/model_providers/ollama.py` (local `/api/tags` + `/api/chat`, hosted mode with consent) reachable through `llm_provider=ollama` |
| 9 | LM Studio | **EXISTS** | `server/model_providers/lmstudio.py` reuses the shared OpenAI-compatible adapter for listing + chat |
| 10 | Per-domain provider selection | **EXISTS** | `server/model_providers/{registry,descriptor,routing}.py` + config keys; resolution is call-time and the dictation (`transcribe_step`), TTS (`manager.speak`) and polish (`enhancement_steps`) paths consume it. `""` defaults stay byte-identical to today |
| 11 | Provider model catalogue / discovery UI | **EXISTS** | `server/model_providers/catalogue.py` TTL cache + `provider_list`/`provider_models` IPC + `pages/providers/Providers.tsx` |
| 12 | Multi-key secret storage | **EXISTS** | `server/model_providers/vault.py` + `credential_store` entries for `openrouter`/`ollama`/`lmstudio`/`custom`, independent rotation, masked reads |
| 13 | Consent gate before sending data out | **EXISTS** (per provider) | `cloud_*_consent` flags, `media_url_consent`, `llm_polish_consent`, plus `{asr,tts,llm}_provider_consent` defaulted from the legacy gates by `model_providers/routing.effective_consent` (an existing user is never re-prompted) |
| 14 | i18n parity (8 locales) for any new string | **EXISTS** (rule) | `C-I18N-1`, `tests/test_i18n_keys_parity.py` |

## 2. Target architecture

### 2.1 One registry, three domains

```
ProviderDescriptor
  id            "openrouter" | "ollama" | "lmstudio" | "local-onnx" | "openai" | ...
  domains       which of {asr, tts, llm} it can serve      <- capability matrix
  auth          {none | api_key | local_endpoint}
  model_list()  -> [ModelDescriptor]   (remote catalogue or local scan)
  client(domain, model_id) -> a client that speaks that domain's contract
```

Domain contracts (one per domain, so a provider cannot "almost" fit):

* **ASR** — batch file → transcript (+ language, duration). Streaming later.
* **TTS** — text + voice + language → audio bytes.
* **LLM** — messages → text (the polish call).

### 2.2 Per-domain routing config (the core of this plan)

```
asr.provider   = local | openrouter | ollama | lmstudio | cloud_direct
asr.model      = <id>            (e.g. "whisper/large-v3-turbo", "qwen/qwen3-asr-...")
tts.provider   = local | openrouter | ...
tts.model      = <id>
llm.provider   = local_onnx | openrouter | ollama | lmstudio | cloud_direct
llm.model      = <id>            (e.g. "openai/gpt-oss-120b:free", "minicpm5-2b-onnx")
```

Rules the config must enforce:

1. **Availability ≠ enablement.** An OpenRouter key makes OpenRouter rows appear in
   every domain picker, and turns nothing on. Each domain has its own explicit
   provider choice; the default stays local.
2. **Independent per domain.** ASR can be local while TTS is OpenRouter and LLM is
   Ollama. No cross-domain coupling, no shared "cloud on" switch.
3. **Per-domain consent.** Sending audio, text, or TTS requests to a remote provider
   are three different consents (`asr.provider_consent`, `tts.provider_consent`,
   `llm.provider_consent`), because the data classes differ.
4. **One key, many providers' worth of models.** The catalogue is fetched once per
   provider and cached with a TTL; a stale catalogue must still let the user keep a
   previously chosen model id.
5. **Capability filtering.** OpenRouter's ASR/TTS endpoints are paid; the UI must
   show "paid" next to them and the free-tier note next to free LLMs, so a user with
   no credits is never silently pushed onto a paid model.

## 3. Work packages

### WP1 — provider registry + domain contracts — **EXISTS** (blocker for everything)
* `server/model_providers/` package: `registry.py`, `descriptor.py`, `contracts/{asr,tts,llm}.py`.
* Extract the existing calls behind contracts: `CloudEngine` → ASR contract;
  `LLMPolisher` → LLM contract; `tts/manager` engines → TTS contract.
* No behaviour change in this WP: existing paths become the first two registry
  entries (`local`, `cloud_direct`).
* Done when: every existing ASR/TTS/LLM test passes through the registry seam.

### WP2 — routing + per-domain selection — **EXISTS**
* Config keys per domain (§2.2), validated in `config_validators/` (cross-field:
  `provider != local` requires consent + a resolvable auth material).
* Resolution at call time (not at config-save time) so a provider can be offline.
* Fallback policy per domain: `off` (fail with a clear code) or `local`
  (explicitly chosen by the user, never an invisible silent fallback).
* Done when: ASR local + TTS OpenRouter + LLM Ollama runs in one session, and the
  log line for each call names the provider+model actually used.

### WP3 — OpenRouter (the "one key, treasure chest") — **EXISTS**
* Auth: one key, stored once. Everything else derives from it.
* Catalogue: `GET /api/v1/models` → per-model: id, name, context length, pricing
  (prompt/completion, and whether one side is `0`), supported input/output
  modalities, so the app can classify each model into **llm / asr / tts** instead of
  guessing from the name.
* Per-domain opt-in (`asr/tts/llm`) with **per-domain model choice** — three
  independent pickers fed by the same catalogue, filtered by capability.
* Free-tier surfacing: models where pricing is 0 are marked **Free**; show the
  request/limit notes the API exposes. Free LLMs are typically 20-30B+ and are the
  main reason this integration matters for a user with no budget.
* Paid domains: ASR/TTS through OpenRouter are paid. The UI must say so before the
  first paid request and record consent once per domain.
* Usage/credits: show remaining credits when the API exposes them, and the
  per-request cost estimate from the selected model's pricing.
* Streaming for LLM (`stream: true`) — the polish UI wants partial text for long
  dictations.
* Failure taxonomy mapped into the existing cloud error classes so the UI copy is
  shared (`CloudAuthError`, `CloudRateLimitError`, ...).
* Done when: one key + three independent choices work end to end, and revoking the
  key turns the three domains back to local with an explanatory toast.

### WP4 — Ollama — **EXISTS**
* Two modes under one provider: **local** (`http://localhost:11434`) and **cloud**
  (Ollama's hosted API with its own key), auto-detected by probing `/api/tags`.
* Local mode: list pulled models, allow "pull model" with progress, never assume a
  model is present.
* LLM only at first (Ollama serves text models); ASR/TTS rows stay disabled with a
  reason, not hidden.
* Done when: local Ollama appears without any key, lists what is actually pulled,
  and polish works offline through it.

### WP5 — LM Studio — **EXISTS**
* Local OpenAI-compatible server (`http://localhost:1234/v1`), `/v1/models` gives
  the currently loaded model(s).
* Same shape as Ollama-local minus pulling; reuse the OpenAI-compatible adapter.
* Done when: with LM Studio running, the LLM domain can select it and polish works.

### WP6 — local ONNX LLM provider (`local_onnx`) — **EXISTS**
Verified outside the repo on 2026-11-01 with `MiniCPM5-2B` q4f16 ONNX (1.76 GB,
14/14 files sha256-verified):
* ORT **1.24.4** (CUDA 12) runs the export on an RTX 5060: **84-107 tok/s decode**,
  ~3.8k tok/s prefill, a 118-token prompt + 96-token answer in **1.16 s**.
  CPU (ORT 1.29) is 13 tok/s, ~11 s for the same work.
* ORT 1.29 rejects it unless the CUDA 13 runtime is installed; ORT 1.22 rejects the
  graph (12-input `GroupQueryAttention`); DirectML fails on that node.
* Needs in-repo: a generation loop (hand-rolled KV cache, proven) **or**
  `onnxruntime-genai` + a `genai_config.json`; chat-template rendering (`jinja2`);
  model registry entry + downloader + hash; `llm.provider = "local_onnx"`.
* Keep the model warm: session creation costs 16-45 s; load once, reuse.

**Two hard-won engineering facts from the prototype (both cost hours, do not repeat):**

1. **The KV cache must stay on the GPU.** A hand-rolled loop over
   `session.run(numpy feeds)` copies all 84 `present.*` tensors to host memory and
   back on every token (≈126 MB per token at a 3k context): decoding collapses from
   ~100 tok/s to **~3 tok/s**. `IOBinding` + `OrtValue.ortvalue_from_numpy(...,
   "cuda")` re-feeds the device tensors directly and restores 66-107 tok/s at 1k-10k
   context. Use a fresh binding per step so run N+1 cannot overwrite the KV tensors
   run N is still reading.
2. **Quality is length-bounded, not task-bounded.** Measured on the owner's real
   dictations (see the eval harness at `D:\polish_eval\llm`, outside this repo): the
   same polish/grammar prompt is perfect at 30-60 words, degrades to "copy the input
   back" past ~150 words, and a 1748-word translation collapses into repetition
   loops and truncates at the token cap. **A 2B int4 model is a short-segment
   editor.** Any product use must chunk dictation (~100-word segments) or route long
   text to a larger provider — which is exactly the argument for per-domain routing.

* Done when: polish runs with the network cable unplugged, on chunked input.

### WP7 — hosted TTS — **EXISTS**
* The engines already speak OpenAI-compatible `/v1/audio/speech`; adding a remote
  base URL + key turns `tts.provider` into `openrouter | openai | custom`.
* Voice/language lists differ per provider — fetch or declare them; never send a
  voice id the provider does not know.

### WP8 — secrets — **EXISTS**
* Today: `llm_api_key`, `cloud_api_key`. Needed: one entry per provider id, with
  redaction in every log path that already exists (`_secrets.redact_secret`).
* Rotation must not require touching the other domains' keys.

### WP9 — UI — **EXISTS**
* "Providers" page: add/remove provider, paste key, test connection, show status.
* Per-domain blocks (Dictation / Speech / Polish) each with: provider select,
  model select, enable/disable, "uses your OpenRouter credits" note, consent gate.
* Model picker must be searchable, show context length + price/free, and remember
  the last chosen model per domain per provider.
* Copy in all 8 locales (`en, ar, de, es, fr, hi, ru, zh`) + parity tests.

### WP10 — docs, ADR, tests — **EXISTS**
* ADR for the provider registry + routing (ADR-0020 §16 discipline for any new IPC
  command; `docs/ipc-reference.md`, `docs/code-notes/event-catalogue.md`).
* Tests: registry capability matrix, routing resolution, consent enforcement
  (no remote call without consent), catalogue classification (llm/asr/tts from
  modalities, never from the model name), free-vs-paid labelling, key redaction,
  fallback policy, i18n parity.
* Every remote provider gets a fake-transport test suite: no network in CI.

## 4. Non-goals (for now)

* No silent fallback from a remote provider to another remote provider.
* No per-model custom prompts in this phase (the four presets stay).
* No local ASR/TTS re-architecture: those already work; they only need to sit behind
  the contracts.
* No auto-download of a 1.76 GB LLM without an explicit user action.

## 5. Open questions for the owner

1. **Default after a key is added:** stay `local` everywhere (my assumption) or
   switch the LLM domain to a free OpenRouter model immediately?
2. **Credits safety:** hard cap per domain (e.g. "never spend more than X per day")?
3. **Free-model churn:** OpenRouter free ids change; do we pin a snapshot list or
   always show the live catalogue?
4. **Ollama cloud:** treat it as the same provider as local Ollama (one toggle) or
   as a separate provider row?
5. **TTS voices:** when the provider is remote, do we keep the two local voice lists
   as "custom voice id" input, or fetch per provider?

## 6. Suggested order

```
WP1 registry + contracts   (nothing else can land cleanly before it)
        ├── WP2 routing/config + WP8 secrets
        ├── WP3 OpenRouter  ── depends on WP2, WP9 (UI)
        ├── WP4 Ollama / WP5 LM Studio  ── cheap, same OpenAI-compatible adapter
        ├── WP6 local ONNX LLM  ── independent of OpenRouter
        └── WP7 hosted TTS ── reuses WP2 + WP9
```

## Appendix — how to re-verify this document's "current state" table

```bash
# OpenRouter / Ollama / LM Studio: expect no matches in shipped code
grep -rn "openrouter\|ollama\|lm.studio" voice_typer/server voice_typer/client/src | grep -v __tests__

# one cloud ASR slot, one LLM endpoint
grep -n "cloud_api_key\|cloud_api_url\|cloud_model\|cloud_provider" voice_typer/server/config/_schema.py
grep -n "llm_api_url\|llm_api_key\|llm_model\|llm_preset" voice_typer/server/config/_schema.py

# local ASR catalogue + TTS engines
grep -n "name=\|backend=" voice_typer/server/model_registry.py | head -40
sed -n '1,20p' voice_typer/server/tts/engines.py
```
