# Model providers: registry, per-domain routing and chunked local polish

Status: accepted (2026-11-02)

## Context

Lausu shipped exactly one provider slot per model domain: `cloud_*` for cloud
ASR, `tts_engine` (+`tts_voice`/`tts_language`) for speech, and `llm_api_url` /
`llm_model` / `llm_api_key` for polish. A user with an OpenRouter key could not
use it for text, speech and polish independently, and there was no offline text
model at all.

## Decision

1. **One registry, three domain contracts.** `voice_typer/server/model_providers/`
   owns `ProviderDescriptor` (id, label, explicit `frozenset[Domain]`, auth kind,
   catalogue function, client factory) and a process-wide
   `ProviderRegistry`. A client is only built for an advertised capability:
   `ProviderDescriptor.client(domain, model_id)` raises
   `ProviderCapabilityError` otherwise, so a provider can never "almost" satisfy a
   domain. The contracts are `contracts/asr.py` (`transcribe`), `contracts/tts.py`
   (`voices`/`languages`/`synthesize`) and `contracts/llm.py`
   (`complete`/`stream`).
2. **Resolution is call-time.** `routing.resolve(domain, config)` maps the
   per-domain config fields (`{asr,tts,llm}_provider`, `_model_id`,
   `_provider_consent`, `_provider_fallback`) to a descriptor + model id on every
   call. An empty provider reproduces today's behaviour exactly (local ASR/TTS,
   the existing OpenAI-compatible LLM endpoint), so an existing user sees no
   change until they enable a domain.
3. **Consent is additive, never a re-prompt.** `effective_consent()` ORs the new
   per-domain flag with the legacy gate (`llm_polish_consent`,
   `cloud_<provider>_consent`). `provider_requires_consent()` treats Ollama as
   remote when it has a key or a non-loopback base URL. A missing consent or key
   raises a typed `ProviderError` subclass carrying the IPC code the UI renders;
   there is no silent remote→remote fallback.
4. **Keys live in the credential store.** `vault.py` stores one secret per
   provider id through the existing `credential_store`; reads are masked, and the
   existing redaction helpers cover every log path. Catalogues are cached in
   `provider_catalogue.json` with a 6 h TTL; a stale snapshot still lets the
   previously selected model id resolve.
5. **Local ONNX text provider.** `local_onnx/` loads a verified ONNX export once
   and keeps it warm. Generation renders the chat template with jinja2 and runs a
   hand-rolled KV loop with `session.io_binding()` and **device** OrtValues (a
   fresh binding per step): keeping the cache on the device is 79-107 tok/s on
   GPU versus ~3 tok/s when it round-trips through numpy at 3k context. Session
   load is 16-45 s, so it never happens per request.
6. **Chunked polish.** This 2B int4 model copies its input past ~150 words: on
   the owner's dictations it scored 15/100 for polish and 25/100 for translation
   at 250-1750 words, but 77.7% overall with sentence-packed chunks of <=200
   words. Local providers therefore polish chunk-by-chunk at sentence boundaries
   (120-200 words) and concatenate in order with a single space (a dictation is
   one continuous text, so no paragraph breaks are injected). Remote providers
   keep today's single call and the existing `_LLM_POLISH_WORD_LIMIT`.

## Consequences

- `provider_list` / `provider_models` / `provider_test` / `provider_set_key` /
  `provider_clear_key` / `provider_set_domain` are the renderer surface; writes
  go through `set_config` so the SEC-002 allowlist stays the single gate.
- `provider_local_onnx_state` is published on the bus, allowed by the Rust WS
  reader and consumed by the Providers page ("loading model…").
- The runtime matrix is reported, never guessed: onnxruntime 1.22 rejects the
  12-input `GroupQueryAttention` node and DirectML does not implement it; ORT
  1.24.4 + CUDA 12 or ORT 1.29 (CPU, or CUDA 13 for GPU) works. A load failure is
  one actionable provider error, not a crash.
